"""Local SQLite vector database for document embeddings."""

import sqlite3
import json
from pathlib import Path
from typing import List, Tuple, Optional
from sentence_transformers import SentenceTransformer, util
import numpy as np

# Database path: code/embeddings/db.py -> project_root/embeddings.db
DB_PATH = Path(__file__).parent.parent.parent / "embeddings.db"

# Embedding model (small, fast, local)
MODEL_NAME = "all-MiniLM-L6-v2"  # 80MB, 384-dim vectors

class EmbeddingDB:
    """Local SQLite vector database for document embeddings."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.model = None
        self.conn = None
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database schema."""
        self.conn = sqlite3.connect(str(self.db_path))
        cursor = self.conn.cursor()

        # Create documents table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company TEXT NOT NULL,
                doc_path TEXT NOT NULL UNIQUE,
                title TEXT,
                content TEXT,
                embedding TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create index for company
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_company ON documents(company)")

        self.conn.commit()

    def _get_model(self):
        """Lazy-load embedding model."""
        if self.model is None:
            print(f"[EMBEDDINGS] Loading {MODEL_NAME} model...")
            self.model = SentenceTransformer(MODEL_NAME)
            print("[EMBEDDINGS] Model loaded")
        return self.model

    def add_document(self, company: str, doc_path: str, title: str, content: str) -> bool:
        """Add a document with embedding to the database.

        Args:
            company: HackerRank, Claude, or Visa
            doc_path: Relative file path
            title: Document title
            content: Full document content

        Returns:
            True if added, False if already exists
        """
        try:
            model = self._get_model()

            # Embed the content
            embedding = model.encode(content, convert_to_tensor=False)
            embedding = np.array(embedding, dtype=np.float32)
            embedding_json = json.dumps(embedding.tolist())

            # Insert into database
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO documents (company, doc_path, title, content, embedding)
                VALUES (?, ?, ?, ?, ?)
            """, (company, doc_path, title, content, embedding_json))

            self.conn.commit()
            return True

        except sqlite3.IntegrityError:
            # Document already exists
            return False
        except Exception as e:
            print(f"[ERROR] Failed to add document {doc_path}: {str(e)}")
            return False

    def search(self, company: str, query: str, top_k: int = 3) -> List[Tuple[str, str, float]]:
        """Search for documents using semantic similarity.

        Args:
            company: Filter by company
            query: Search query text
            top_k: Number of results to return

        Returns:
            List of (title, content, similarity_score) tuples
        """
        try:
            model = self._get_model()

            # Embed the query
            query_embedding = model.encode(query, convert_to_tensor=False)
            query_embedding = np.array(query_embedding, dtype=np.float32)

            # Get all documents for this company
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT id, title, content, embedding
                FROM documents
                WHERE company = ?
            """, (company,))

            rows = cursor.fetchall()

            if not rows:
                return []

            # Calculate similarity for each document
            similarities = []
            for doc_id, title, content, embedding_json in rows:
                embedding = np.array(json.loads(embedding_json), dtype=np.float32)
                # Cosine similarity
                similarity = float(util.pytorch_cos_sim(
                    query_embedding,
                    embedding
                )[0][0])

                similarities.append((title, content, similarity))

            # Sort by similarity and return top-k
            similarities.sort(key=lambda x: x[2], reverse=True)
            return similarities[:top_k]

        except Exception as e:
            print(f"[ERROR] Search failed: {str(e)}")
            return []

    def get_stats(self) -> dict:
        """Get database statistics."""
        cursor = self.conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM documents")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT company, COUNT(*) FROM documents GROUP BY company")
        by_company = dict(cursor.fetchall())

        return {
            "total_documents": total,
            "by_company": by_company,
            "db_path": str(self.db_path)
        }

    def clear(self):
        """Clear all embeddings from database."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM documents")
        self.conn.commit()

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()


def init_embedding_db() -> EmbeddingDB:
    """Initialize and return embedding database."""
    return EmbeddingDB()
