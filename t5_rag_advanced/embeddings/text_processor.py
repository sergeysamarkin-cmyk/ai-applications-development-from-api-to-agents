import os
from enum import StrEnum

import psycopg2
from psycopg2.extras import RealDictCursor

from t5_rag_advanced.embeddings.embeddings_client import EmbeddingsClient
from t5_rag_advanced.utils.text import chunk_text


class SearchMode(StrEnum):
    EUCLIDIAN_DISTANCE = "euclidean"  # Euclidean distance (<->)
    COSINE_DISTANCE = "cosine"  # Cosine distance (<=>)


class TextProcessor:
    """Processor for text documents that handles chunking, embedding, storing, and retrieval"""

    def __init__(self, embeddings_client: EmbeddingsClient, db_config: dict):
        self.embeddings_client = embeddings_client
        self.db_config = db_config

    def _get_connection(self):
        """Get database connection"""
        return psycopg2.connect(
            host=self.db_config['host'],
            port=self.db_config['port'],
            database=self.db_config['database'],
            user=self.db_config['user'],
            password=self.db_config['password']
        )

    def process_text_file(
            self,
            file_name: str,
            chunk_size: int,
            overlap: int,
            dimensions: int,
            truncate_table: bool = True
    ) -> None:
        """Load the file, split it into chunks, embed every chunk and store everything in the `vectors` table"""
        if truncate_table:
            self._truncate_table()

        with open(file_name, "r", encoding="utf-8") as file:
            content = file.read()

        chunks = chunk_text(content, chunk_size, overlap)
        print(f"📖 '{os.path.basename(file_name)}' split into {len(chunks)} chunks "
              f"(chunk_size={chunk_size}, overlap={overlap})")

        embeddings = self.embeddings_client.get_embeddings(chunks, dimensions)

        document_name = os.path.basename(file_name)[:64]  # `document_name` column is VARCHAR(64)
        with self._get_connection() as connection:
            with connection.cursor() as cursor:
                for index, chunk in enumerate(chunks):
                    self._save_chunk(cursor, document_name, chunk, embeddings[index])
            connection.commit()
        print(f"💾 Saved {len(chunks)} chunks with {dimensions}-dimensional embeddings to the database")

    def _truncate_table(self) -> None:
        """Remove all rows from the `vectors` table"""
        with self._get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("TRUNCATE TABLE vectors")
            connection.commit()
        print("🧹 Table `vectors` truncated")

    @staticmethod
    def _save_chunk(cursor, document_name: str, text: str, embedding: list[float]) -> None:
        """Insert one chunk with its embedding. The embedding is passed as a string list and cast to `vector`"""
        cursor.execute(
            "INSERT INTO vectors (document_name, text, embedding) VALUES (%s, %s, %s::vector)",
            (document_name, text, str(embedding))
        )

    def search(
            self,
            search_mode: SearchMode,
            user_request: str,
            top_k: int,
            score: float,
            dimensions: int
    ) -> list[str]:
        """
        Find the chunks that are the closest to the user request.

        Args:
            search_mode: Euclidean (`<->`) or cosine (`<=>`) distance
            user_request: text to search for
            top_k: max number of chunks to return
            score: max allowed distance (smaller distance = more similar chunk)
            dimensions: dimensions of the request embedding, must match the dimensions stored in the DB
        """
        request_embedding = self.embeddings_client.get_embeddings(user_request, dimensions)[0]
        embedding_str = str(request_embedding)

        operator = "<->" if search_mode == SearchMode.EUCLIDIAN_DISTANCE else "<=>"
        query = f"""
            SELECT text, embedding {operator} %s::vector AS distance
            FROM vectors
            WHERE embedding {operator} %s::vector <= %s
            ORDER BY distance
            LIMIT %s
        """

        with self._get_connection() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, (embedding_str, embedding_str, score, top_k))
                rows = cursor.fetchall()

        for row in rows:
            print(f"📄 distance={row['distance']:.4f} ({search_mode.value})\n{row['text']}\n")
        if not rows:
            print("⚠️ No relevant chunks found")
        return [row["text"] for row in rows]


# SELECT text, embedding <->  '[0.23, -0.45, 0.67, ..., 0.12]'::vector AS distance
# FROM vectors
# WHERE embedding <->  '[0.23, -0.45, 0.67, ..., 0.12]'::vector <= {score}
# ORDER BY distance
# LIMIT {top_k};
