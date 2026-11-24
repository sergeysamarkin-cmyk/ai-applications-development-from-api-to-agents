"""
Runs the very same RAG application (app.py) on Gemini instead of OpenAI.

Gemini exposes an OpenAI-compatible API, so the same LangChain clients work with a different base_url, key and models.
Useful when there is no OpenAI balance. A separate FAISS index folder is used, because embedding sizes differ.

Run from the repository root:
    python -m t4_rag_fundamentals.run_with_gemini
"""
import os

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import SecretStr

from commons.constants import GEMINI_API_KEY, GEMINI_FLASH_MODEL
from t4_rag_fundamentals.app import MicrowaveRAG, main

GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_EMBEDDINGS_MODEL = "gemini-embedding-001"

if __name__ == "__main__":
    main(
        MicrowaveRAG(
            embeddings=OpenAIEmbeddings(
                model=GEMINI_EMBEDDINGS_MODEL,
                api_key=SecretStr(GEMINI_API_KEY),
                base_url=GEMINI_OPENAI_BASE_URL,
                # Send raw text instead of OpenAI token ids
                check_embedding_ctx_length=False,
                # Gemini accepts at most 100 texts per embeddings request
                chunk_size=50,
            ),
            llm_client=ChatOpenAI(
                temperature=0.0,
                reasoning_effort="none",
                model=GEMINI_FLASH_MODEL,
                api_key=SecretStr(GEMINI_API_KEY),
                base_url=GEMINI_OPENAI_BASE_URL,
            ),
            index_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "microwave_faiss_index_gemini"),
        )
    )
