from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    jwt_required,
    get_jwt_identity,
)
from flask_swagger_ui import get_swaggerui_blueprint
from flask_caching import Cache
from werkzeug.security import generate_password_hash, check_password_hash
from marshmallow import Schema, fields, validate, ValidationError
import logging
from logging.handlers import RotatingFileHandler
from typing import Dict, Any, Optional, List
import os
from functools import wraps
import time
from datetime import datetime, timedelta
import json
import prometheus_client
from prometheus_client import Counter, Histogram
import threading
from queue import Queue
from sqlalchemy import event, Index
from sqlalchemy.engine import Engine
import sqlite3
import pytest

# Configure logging
if not os.path.exists("logs"):
    os.makedirs("logs")

file_handler = RotatingFileHandler("logs/app.log", maxBytes=10240, backupCount=10)
file_handler.setFormatter(
    logging.Formatter(
        "%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"
    )
)
file_handler.setLevel(logging.INFO)

logger = logging.getLogger(__name__)
logger.addHandler(file_handler)
logger.setLevel(logging.INFO)

app = Flask(__name__)
CORS(app)

# Database configuration
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///app.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_size": 10,
    "pool_recycle": 3600,
    "pool_pre_ping": True,
}
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# JWT configuration
jwt = JWTManager(app)
app.config["JWT_SECRET_KEY"] = os.getenv("SECRET_KEY", "your-secret-key-here")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=24)
app.config["JWT_TOKEN_LOCATION"] = ["headers"]
app.config["JWT_HEADER_NAME"] = "Authorization"
app.config["JWT_HEADER_TYPE"] = "Bearer"

# Cache configuration
app.config["CACHE_TYPE"] = "SimpleCache"
app.config["CACHE_DEFAULT_TIMEOUT"] = 300
cache = Cache(app)


# Rate limiting configuration
def rate_limit_exceeded_handler(e):
    return jsonify({"error": "Rate limit exceeded"}), 429


limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
    strategy="fixed-window",
    on_breach=rate_limit_exceeded_handler,
)

# Configuration
app.config.update(
    DEBUG=os.environ.get("FLASK_DEBUG", "False").lower() == "true",
    SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", "dev-key-please-change"),
    API_VERSION="1.0.0",
)

# Background task queue
task_queue = Queue()


def background_worker():
    """Background worker to process tasks."""
    while True:
        task = task_queue.get()
        try:
            task()
        except Exception as e:
            logger.error(f"Error processing background task: {str(e)}")
        finally:
            task_queue.task_done()


# Start background worker
worker_thread = threading.Thread(target=background_worker, daemon=True)
worker_thread.start()

# Metrics configuration
REQUEST_COUNT = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"]
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds", "HTTP request latency", ["method", "endpoint"]
)

# OpenAPI/Swagger configuration
SWAGGER_URL = "/api/docs"
API_URL = "/static/swagger.json"

# Generate OpenAPI specification
openapi_spec = {
    "openapi": "3.0.0",
    "info": {
        "title": "Flask API",
        "version": app.config["API_VERSION"],
        "description": "A Flask API with authentication and metrics",
    },
    "servers": [{"url": "/", "description": "Default server"}],
    "components": {
        "securitySchemes": {
            "bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
        }
    },
    "paths": {
        "/auth/register": {
            "post": {
                "summary": "Register a new user",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "username": {
                                        "type": "string",
                                        "minLength": 3,
                                        "maxLength": 80,
                                    },
                                    "password": {"type": "string", "minLength": 8},
                                },
                                "required": ["username", "password"],
                            }
                        }
                    },
                },
                "responses": {
                    "201": {"description": "User registered successfully"},
                    "400": {"description": "Invalid input"},
                    "500": {"description": "Internal server error"},
                },
            }
        },
        "/auth/login": {
            "post": {
                "summary": "Login user and get JWT token",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "username": {"type": "string"},
                                    "password": {"type": "string"},
                                },
                                "required": ["username", "password"],
                            }
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Login successful",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"access_token": {"type": "string"}},
                                }
                            }
                        },
                    },
                    "401": {"description": "Invalid credentials"},
                },
            }
        },
        "/": {
            "post": {
                "summary": "Create a greeting",
                "security": [{"bearerAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "minLength": 1,
                                        "maxLength": 80,
                                    }
                                },
                                "required": ["name"],
                            }
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Greeting created successfully",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "message": {"type": "string"},
                                        "status": {"type": "string"},
                                        "timestamp": {"type": "number"},
                                        "greeting_id": {"type": "integer"},
                                    },
                                }
                            }
                        },
                    }
                },
            }
        },
    },
}

# Save OpenAPI specification
os.makedirs("static", exist_ok=True)
with open("static/swagger.json", "w") as f:
    json.dump(openapi_spec, f)

swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL, API_URL, config={"app_name": "Flask API"}
)
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)


# Custom exceptions
class APIError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


# Request validation schemas
class UserSchema(Schema):
    username = fields.Str(required=True, validate=validate.Length(min=3, max=80))
    password = fields.Str(required=True, validate=validate.Length(min=8))


class GreetingSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=80))


# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    last_login = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Greeting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


# Create indexes
Index("idx_greeting_user_created", Greeting.user_id, Greeting.created_at)


# SQLite foreign key support
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# Create database tables
with app.app_context():
    db.create_all()


def validate_name(name: str) -> bool:
    """Validate the name parameter."""
    return isinstance(name, str) and len(name.strip()) > 0


def add_security_headers(response):
    """Add security headers to all responses."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains"
    )
    return response


def version_required(f):
    """Decorator to check API version."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        version = request.headers.get("X-API-Version")
        if version and version != app.config["API_VERSION"]:
            raise APIError(
                f"API version mismatch. Required: {app.config['API_VERSION']}, Provided: {version}",
                400,
            )
        return f(*args, **kwargs)

    return decorated_function


def validate_request(schema: Schema):
    """Decorator to validate request data against a schema."""

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                if request.is_json:
                    data = request.get_json()
                    schema().load(data)
                return f(*args, **kwargs)
            except ValidationError as e:
                raise APIError(str(e), 400)

        return decorated_function

    return decorator


def track_metrics(f):
    """Decorator to track request metrics."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()
        try:
            response = f(*args, **kwargs)
            status = response.status_code
        except Exception as e:
            status = getattr(e, "status_code", 500)
            raise
        finally:
            REQUEST_COUNT.labels(
                method=request.method, endpoint=request.endpoint, status=status
            ).inc()
            REQUEST_LATENCY.labels(
                method=request.method, endpoint=request.endpoint
            ).observe(time.time() - start_time)
        return response

    return decorated_function


def log_request():
    """Log request details."""
    logger.info(f"Request: {request.method} {request.url}")
    if request.is_json:
        logger.info(f"Request body: {request.get_json()}")
    logger.info(f"Response status: {getattr(request, '_response_status', 'N/A')}")


@app.before_request
def before_request():
    """Log request details before processing."""
    log_request()


@app.after_request
def after_request(response):
    """Add security headers and log response."""
    request._response_status = response.status_code
    return add_security_headers(response)


@app.route("/auth/register", methods=["POST"])
@limiter.limit("5 per minute")
def register():
    """Register a new user."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Validate input
        try:
            data = UserSchema().load(data)
        except ValidationError as err:
            return jsonify({"error": err.messages}), 400

        # Check if user already exists
        if User.query.filter_by(username=data["username"]).first():
            return jsonify({"error": "Username already exists"}), 409

        # Create new user
        user = User(username=data["username"])
        user.set_password(data["password"])
        db.session.add(user)
        db.session.commit()

        return jsonify({"message": "User registered successfully"}), 201

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error registering user: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


def send_welcome_email(username: str):
    """Send welcome email to new user."""
    logger.info(f"Sending welcome email to {username}")
    # Implement email sending logic here
    time.sleep(1)  # Simulate email sending


@app.route("/auth/login", methods=["POST"])
@limiter.limit("5 per minute")
def login():
    """Login user and return JWT token."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Validate input
        try:
            data = UserSchema().load(data)
        except ValidationError as err:
            return jsonify({"error": err.messages}), 400

        # Find user
        user = User.query.filter_by(username=data["username"]).first()
        if not user or not user.check_password(data["password"]):
            return jsonify({"error": "Invalid username or password"}), 401

        # Update last login
        user.last_login = datetime.utcnow()
        db.session.commit()

        # Create access token with user ID as string
        access_token = create_access_token(identity=str(user.id))
        return (
            jsonify({"access_token": access_token, "message": "Login successful"}),
            200,
        )

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error in login endpoint: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@app.route("/")
@jwt_required()
@limiter.limit("30 per minute")
def hello():
    """Return a greeting message."""
    try:
        name = request.args.get("name", "World")
        if not validate_name(name):
            return jsonify({"error": "Invalid name parameter"}), 400

        # Get current user
        current_user_id = int(get_jwt_identity())  # Convert string ID to integer
        user = User.query.get(current_user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404

        # Create greeting
        greeting = Greeting(name=name, user_id=user.id)
        db.session.add(greeting)
        db.session.commit()

        # Log the greeting
        app.logger.info(f"Greeting created for user {user.username}: {name}")

        return jsonify({"message": f"Hello, {name}!"}), 200

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error in hello endpoint: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@app.route("/greetings")
@jwt_required()
@limiter.limit("30 per minute")
def get_greetings():
    """Get all greetings for the current user."""
    try:
        # Get current user
        current_user_id = int(get_jwt_identity())  # Convert string ID to integer
        user = User.query.get(current_user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404

        # Get all greetings for the user
        greetings = (
            Greeting.query.filter_by(user_id=user.id)
            .order_by(Greeting.created_at.desc())
            .all()
        )

        return (
            jsonify(
                {
                    "greetings": [
                        {
                            "id": g.id,
                            "name": g.name,
                            "created_at": g.created_at.isoformat(),
                        }
                        for g in greetings
                    ]
                }
            ),
            200,
        )

    except Exception as e:
        app.logger.error(f"Error in get_greetings endpoint: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@app.route("/metrics")
@limiter.exempt
def metrics():
    """Prometheus metrics endpoint."""
    return prometheus_client.generate_latest()


@app.route("/health")
@limiter.exempt
@track_metrics
def health_check() -> Dict[str, Any]:
    """Health check endpoint."""
    try:
        db_status = "healthy" if db.engine.pool.checkedout() == 0 else "degraded"
        cache_status = "healthy" if cache.get("health_check") is None else "degraded"

        # Test database connection
        db.session.execute("SELECT 1")

        return jsonify(
            {
                "status": "healthy",
                "version": app.config["API_VERSION"],
                "timestamp": time.time(),
                "database": db_status,
                "cache": cache_status,
                "background_tasks": task_queue.qsize(),
            }
        )
    except Exception as e:
        logger.error(f"Error in health check: {str(e)}")
        return (
            jsonify(
                {
                    "status": "degraded",
                    "version": app.config["API_VERSION"],
                    "timestamp": time.time(),
                    "error": str(e),
                }
            ),
            500,
        )


@app.route("/api/info")
@limiter.limit("30 per minute")
@version_required
@track_metrics
def api_info() -> Dict[str, Any]:
    """API information endpoint."""
    return jsonify(
        {
            "version": app.config["API_VERSION"],
            "endpoints": {
                "/": "Greeting endpoint (requires authentication)",
                "/auth/register": "Register new user",
                "/auth/login": "Login and get JWT token",
                "/greetings": "Get user's greeting history",
                "/health": "Health check endpoint",
                "/metrics": "Prometheus metrics endpoint",
                "/api/info": "API information endpoint",
                "/api/docs": "API documentation (Swagger UI)",
            },
            "rate_limits": {
                "default": "200 per day, 50 per hour",
                "hello": "10 per minute",
                "api_info": "30 per minute",
                "auth": "5 per minute",
            },
        }
    )


@app.errorhandler(APIError)
def handle_api_error(error):
    """Handle API errors."""
    response = jsonify({"error": error.message})
    response.status_code = error.status_code
    return response


@app.errorhandler(404)
def not_found(error) -> Dict[str, Any]:
    """Handle 404 errors."""
    return jsonify({"error": "Resource not found"}), 404


@app.errorhandler(500)
def internal_error(error) -> Dict[str, Any]:
    """Handle 500 errors."""
    return jsonify({"error": "Internal server error"}), 500


@app.errorhandler(429)
def ratelimit_handler(error) -> Dict[str, Any]:
    """Handle rate limit errors."""
    return (
        jsonify({"error": "Rate limit exceeded", "retry_after": error.description}),
        429,
    )


# Unit tests
@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.session.remove()
            db.drop_all()


def test_register_user(client):
    """Test user registration."""
    response = client.post(
        "/auth/register", json={"username": "testuser", "password": "testpass123"}
    )
    assert response.status_code == 201
    assert response.json["message"] == "User registered successfully"


def test_register_duplicate_user(client):
    """Test duplicate user registration."""
    # First registration
    client.post(
        "/auth/register", json={"username": "testuser", "password": "testpass123"}
    )
    # Second registration with same username
    response = client.post(
        "/auth/register", json={"username": "testuser", "password": "testpass123"}
    )
    assert response.status_code == 400
    assert response.json["error"] == "Username already exists"


def test_login_success(client):
    """Test successful login."""
    # Register user
    client.post(
        "/auth/register", json={"username": "testuser", "password": "testpass123"}
    )
    # Login
    response = client.post(
        "/auth/login", json={"username": "testuser", "password": "testpass123"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json


def test_login_invalid_credentials(client):
    """Test login with invalid credentials."""
    response = client.post(
        "/auth/login", json={"username": "testuser", "password": "wrongpass"}
    )
    assert response.status_code == 401
    assert response.json["error"] == "Invalid credentials"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
