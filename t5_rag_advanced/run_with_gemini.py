"""
Runs the same RAG chat (app.py) on Gemini instead of OpenAI, through Gemini's OpenAI-compatible API.
Useful when there is no OpenAI balance. Also used for the two additional experiments.

Run from the repository root (the pgvector DB must be running on localhost:5433):

    python -m t5_rag_advanced.run_with_gemini                              # normal run
    python -m t5_rag_advanced.run_with_gemini --search-dims 385            # Experiment 1: dimension mismatch
    python -m t5_rag_advanced.run_with_gemini --search-model gemini-embedding-2
                                                                           # Experiment 2: embedding model mismatch
    ... --min-score 2                  # no distance filtering: shows the closest chunks even if they are irrelevant
Use 'y' to load the context with the default model first, then run an experiment and answer 'n'.
"""
import argparse

from commons.constants import GEMINI_API_KEY, GEMINI_FLASH_MODEL
from t5_rag_advanced.app import start
from t5_rag_advanced.chat.chat_completion_client import ChatCompletionClient
from t5_rag_advanced.embeddings.embeddings_client import EmbeddingsClient

GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
INDEX_MODEL = "gemini-embedding-001"

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--search-dims", type=int, default=384, help="dimensions of the request embedding")
    parser.add_argument("--search-model", default=None, help="embedding model used for the search request")
    parser.add_argument("--min-score", type=float, default=0.5,
                        help="max cosine distance (0..2). Use 2 to see the closest chunks without filtering")
    args = parser.parse_args()

    embeddings_client = EmbeddingsClient(
        endpoint=f"{GEMINI_OPENAI_BASE_URL}/embeddings", model_name=INDEX_MODEL, api_key=GEMINI_API_KEY
    )
    search_client = None
    if args.search_model:
        search_client = EmbeddingsClient(
            endpoint=f"{GEMINI_OPENAI_BASE_URL}/embeddings", model_name=args.search_model, api_key=GEMINI_API_KEY
        )
        print(f"⚠️ EXPERIMENT: context is indexed with '{INDEX_MODEL}', requests are embedded with '{args.search_model}'")
    if args.search_dims != 384:
        print(f"⚠️ EXPERIMENT: DB stores 384-dimensional vectors, request is embedded with {args.search_dims} dimensions")

    start(
        embeddings_client=embeddings_client,
        chat_client=ChatCompletionClient(
            endpoint=f"{GEMINI_OPENAI_BASE_URL}/chat/completions", model_name=GEMINI_FLASH_MODEL, api_key=GEMINI_API_KEY
        ),
        search_dimensions=args.search_dims,
        search_embeddings_client=search_client,
        min_score=args.min_score,
    )
