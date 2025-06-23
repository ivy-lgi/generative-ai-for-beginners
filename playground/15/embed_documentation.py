#!/usr/bin/env python3
"""
Script to enrich Qdrant vector database with embeddings from RST documentation files.
This script parses RST files, creates appropriate chunks with section context,
generates embeddings using Azure OpenAI, and stores them in Qdrant.
"""

import os
import re
import glob
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import logging
from dotenv import load_dotenv
from openai import AzureOpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import hashlib
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    """Represents a chunk of documentation with metadata."""

    content: str
    file_path: str
    file_title: str
    section_title: str
    section_level: int
    chunk_id: str
    metadata: Dict


class RSTParser:
    """Parser for RST documentation files."""

    def __init__(self):
        # RST section patterns for different levels
        self.section_patterns = [
            (r"^([A-Z][A-Za-z0-9\s\-_]+)\n([=]{3,})$", 1),  # Level 1: ===
            (r"^([A-Z][A-Za-z0-9\s\-_]+)\n([-]{3,})$", 2),  # Level 2: ---
            (r"^([A-Z][A-Za-z0-9\s\-_]+)\n([~]{3,})$", 3),  # Level 3: ~~~
            (r"^([A-Z][A-Za-z0-9\s\-_]+)\n([\^]{3,})$", 4),  # Level 4: ^^^
        ]

        # RST directive patterns
        self.directive_patterns = [
            r"^\.\.\s+(\w+)::\s*(.*)$",
            r"^\.\.\s+(\w+):\s*(.*)$",
        ]

    def extract_file_title(self, content: str) -> str:
        """Extract the main title from an RST file."""
        lines = content.split("\n")
        for line in lines:
            line = line.strip()
            if line and not line.startswith("..") and not line.startswith("="):
                # Look for the first meaningful line that could be a title
                if len(line) > 3 and not line.startswith("|"):
                    return line
        return "Untitled"

    def parse_rst_file(self, file_path: str) -> List[DocumentChunk]:
        """Parse an RST file and extract chunks with section information."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return []

        file_title = self.extract_file_title(content)
        chunks = []

        # Split content into sections
        sections = self._split_into_sections(content)

        for section in sections:
            if section["content"].strip():
                chunk = DocumentChunk(
                    content=section["content"].strip(),
                    file_path=file_path,
                    file_title=file_title,
                    section_title=section["title"],
                    section_level=section["level"],
                    chunk_id=self._generate_chunk_id(file_path, section["title"]),
                    metadata={
                        "file_path": file_path,
                        "file_title": file_title,
                        "section_title": section["title"],
                        "section_level": section["level"],
                        "content_length": len(section["content"]),
                    },
                )
                chunks.append(chunk)

        return chunks

    def _split_into_sections(self, content: str) -> List[Dict]:
        """Split RST content into sections based on headers."""
        lines = content.split("\n")
        sections = []
        current_section = {"title": "Introduction", "level": 0, "content": []}

        i = 0
        while i < len(lines):
            line = lines[i]

            # Check if this line is a section header
            section_info = self._is_section_header(lines, i)

            if section_info:
                # Save current section if it has content
                if current_section["content"]:
                    sections.append(
                        {
                            "title": current_section["title"],
                            "level": current_section["level"],
                            "content": "\n".join(current_section["content"]).strip(),
                        }
                    )

                # Start new section
                current_section = {
                    "title": section_info["title"],
                    "level": section_info["level"],
                    "content": [],
                }
                i += 2  # Skip the underline
            else:
                # Add line to current section content
                current_section["content"].append(line)
                i += 1

        # Add the last section
        if current_section["content"]:
            sections.append(
                {
                    "title": current_section["title"],
                    "level": current_section["level"],
                    "content": "\n".join(current_section["content"]).strip(),
                }
            )

        return sections

    def _is_section_header(self, lines: List[str], index: int) -> Optional[Dict]:
        """Check if a line is a section header."""
        if index >= len(lines) - 1:
            return None

        current_line = lines[index].strip()
        next_line = lines[index + 1].strip()

        # Skip empty lines and directives
        if not current_line or current_line.startswith(".."):
            return None

        # Check for section patterns
        for pattern, level in self.section_patterns:
            match = re.match(pattern, f"{current_line}\n{next_line}")
            if match:
                return {"title": current_line, "level": level}

        return None

    def _generate_chunk_id(self, file_path: str, section_title: str) -> str:
        """Generate a unique ID for a chunk."""
        content = f"{file_path}:{section_title}"
        return hashlib.md5(content.encode()).hexdigest()


class EmbeddingGenerator:
    """Handles embedding generation using Azure OpenAI."""

    def __init__(self, client: AzureOpenAI, embedding_deployment: str):
        self.client = client
        self.embedding_deployment = embedding_deployment

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a text chunk."""
        try:
            response = self.client.embeddings.create(
                input=text, model=self.embedding_deployment
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise


class QdrantManager:
    """Manages Qdrant vector database operations."""

    def __init__(self, host: str = "localhost", port: int = 6333):
        self.client = QdrantClient(host=host, port=port)
        self.collection_name = "documentation_embeddings"

    def create_collection(self, vector_size: int = 1536):
        """Create the collection if it doesn't exist."""
        try:
            # Check if collection exists
            collections = self.client.get_collections()
            collection_names = [col.name for col in collections.collections]

            if self.collection_name not in collection_names:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=vector_size, distance=Distance.COSINE
                    ),
                )
                logger.info(f"Created collection: {self.collection_name}")
            else:
                logger.info(f"Collection {self.collection_name} already exists")
        except Exception as e:
            logger.error(f"Error creating collection: {e}")
            raise

    def upsert_embeddings(
        self, chunks: List[DocumentChunk], embeddings: List[List[float]]
    ):
        """Upsert embeddings into the collection."""
        try:
            points = []
            for chunk, embedding in zip(chunks, embeddings):
                point = PointStruct(
                    id=chunk.chunk_id,
                    vector=embedding,
                    payload={
                        "content": chunk.content,
                        "file_path": chunk.file_path,
                        "file_title": chunk.file_title,
                        "section_title": chunk.section_title,
                        "section_level": chunk.section_level,
                        "metadata": chunk.metadata,
                    },
                )
                points.append(point)

            # Upsert in batches
            batch_size = 100
            for i in range(0, len(points), batch_size):
                batch = points[i : i + batch_size]
                self.client.upsert(collection_name=self.collection_name, points=batch)
                logger.info(
                    f"Upserted batch {i//batch_size + 1}/{(len(points) + batch_size - 1)//batch_size}"
                )

            logger.info(f"Successfully upserted {len(points)} embeddings")
        except Exception as e:
            logger.error(f"Error upserting embeddings: {e}")
            raise


def find_rst_files(directory: str) -> List[str]:
    """Find all RST files in the given directory and subdirectories."""
    rst_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".rst"):
                rst_files.append(os.path.join(root, file))
    return rst_files


def main():
    """Main function to process documentation and create embeddings."""
    # Load environment variables
    load_dotenv()

    # Configuration
    docs_directory = "/home/lgi/dev/master/doc/source"
    qdrant_host = "localhost"
    qdrant_port = 6333

    # Azure OpenAI configuration
    api_version = os.environ["AZURE_OPENAI_API_VERSION"]
    azure_endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
    api_key = os.environ["AZURE_OPENAI_API_KEY"]
    deployment = os.environ["AZURE_OPENAI_DEPLOYMENT"]
    embedding_deployment = os.environ["AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT"]

    # Validate environment variables
    required_vars = [api_version, azure_endpoint, api_key, embedding_deployment]
    if not all(required_vars):
        logger.error(
            "Missing required environment variables. Please check your .env file."
        )
        return

    try:
        # Initialize components
        logger.info("Initializing components...")
        openai_client = AzureOpenAI(
            api_version=api_version,
            azure_endpoint=azure_endpoint,
            api_key=api_key,
        )

        parser = RSTParser()
        embedding_gen = EmbeddingGenerator(openai_client, embedding_deployment)
        qdrant_manager = QdrantManager(qdrant_host, qdrant_port)

        # Create collection
        logger.info("Setting up Qdrant collection...")
        qdrant_manager.create_collection()

        # Find all RST files
        logger.info(f"Scanning for RST files in {docs_directory}...")
        rst_files = find_rst_files(docs_directory)
        logger.info(f"Found {len(rst_files)} RST files")

        # Process each file
        all_chunks = []
        for file_path in rst_files:
            logger.info(f"Processing {file_path}...")
            chunks = parser.parse_rst_file(file_path)
            all_chunks.extend(chunks)
            logger.info(f"Extracted {len(chunks)} chunks from {file_path}")

        logger.info(f"Total chunks extracted: {len(all_chunks)}")

        # Generate embeddings
        logger.info("Generating embeddings...")
        embeddings = []
        for i, chunk in enumerate(all_chunks):
            logger.info(
                f"Generating embedding {i+1}/{len(all_chunks)}: {chunk.section_title}"
            )

            # Create context-rich text for embedding
            context_text = f"File: {chunk.file_title}\nSection: {chunk.section_title}\n\n{chunk.content}"

            embedding = embedding_gen.generate_embedding(context_text)
            embeddings.append(embedding)

        # Store in Qdrant
        logger.info("Storing embeddings in Qdrant...")
        qdrant_manager.upsert_embeddings(all_chunks, embeddings)

        logger.info("Documentation embedding process completed successfully!")

        # Print summary
        print(f"\nSummary:")
        print(f"- Processed {len(rst_files)} RST files")
        print(f"- Created {len(all_chunks)} chunks")
        print(f"- Generated {len(embeddings)} embeddings")
        print(f"- Stored in Qdrant collection: {qdrant_manager.collection_name}")

    except Exception as e:
        logger.error(f"Error during processing: {e}")
        raise


if __name__ == "__main__":
    main()
