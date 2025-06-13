"""initial migration

Revision ID: 1a2b3c4d5e6f
Revises:
Create Date: 2024-03-19 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1a2b3c4d5e6f"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create users table
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("password_hash", sa.String(length=256), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("last_login", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_index(op.f("ix_user_created_at"), "user", ["created_at"], unique=False)
    op.create_index(op.f("ix_user_username"), "user", ["username"], unique=True)

    # Create greetings table
    op.create_table(
        "greeting",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_greeting_created_at"), "greeting", ["created_at"], unique=False
    )
    op.create_index(
        "idx_greeting_user_created", "greeting", ["user_id", "created_at"], unique=False
    )


def downgrade():
    # Drop greetings table
    op.drop_index("idx_greeting_user_created", table_name="greeting")
    op.drop_index(op.f("ix_greeting_created_at"), table_name="greeting")
    op.drop_table("greeting")

    # Drop users table
    op.drop_index(op.f("ix_user_username"), table_name="user")
    op.drop_index(op.f("ix_user_created_at"), table_name="user")
    op.drop_table("user")
