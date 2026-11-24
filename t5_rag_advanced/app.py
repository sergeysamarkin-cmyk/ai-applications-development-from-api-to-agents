import os

from commons.constants import OPENAI_API_KEY, OPENAI_EMBEDDINGS_ENDPOINT, OPENAI_CHAT_COMPLETIONS_ENDPOINT, OPENAI_EMBEDDINGS_MODEL, OPENAI_TERRA_MODEL
from commons.models.conversation import Conversation
from commons.models.message import Message
from commons.models.role import Role
from t5_rag_advanced.chat.chat_completion_client import ChatCompletionClient
from t5_rag_advanced.embeddings.embeddings_client import EmbeddingsClient
from t5_rag_advanced.embeddings.text_processor import TextProcessor, SearchMode

SYSTEM_PROMPT = """
You are a RAG-powered assistant that helps users with their microwave oven, using the microwave user manual.

Every user message consists of 2 sections:
- `##RAG CONTEXT:` - fragments of the microwave manual that were retrieved for the user question
- `##USER QUESTION:` - the actual question of the user

Instructions:
- Use the `RAG CONTEXT` to answer the `USER QUESTION`. You may also use the previous messages of this conversation.
- Do not use your own knowledge and do not make assumptions.
- If the `RAG CONTEXT` is empty or does not contain the answer, say that you cannot answer because there is no such
  information in the microwave manual.
- Strictly refuse to answer questions that are not related to the microwave usage, are not covered by the
  `RAG CONTEXT`, or are out of the conversation history scope (general knowledge, history, opinions, other products).
- Keep the answers concise and precise.
"""

USER_PROMPT = """##RAG CONTEXT:
{context}


##USER QUESTION:
{query}"""

DB_CONFIG = {
    'host': 'localhost',
    'port': 5433,
    'database': 'vectordb',
    'user': 'postgres',
    'password': 'postgres'
}

MANUAL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "embeddings", "microwave_manual.txt")


def start(
        embeddings_client: EmbeddingsClient,
        chat_client: ChatCompletionClient,
        search_dimensions: int = 384,
        search_embeddings_client: EmbeddingsClient | None = None,
        min_score: float = 0.5
) -> None:
    """
    Run the console RAG chat.

    Args:
        embeddings_client: client used to create the embeddings of the document when the context is loaded
        chat_client: client used for the answer generation
        search_dimensions: dimensions of the request embedding used for search (stored vectors have 384)
        search_embeddings_client: client used to embed the user request, `embeddings_client` by default.
            Different clients for loading and searching are needed for the "embedding model mismatch" experiment
        min_score: max allowed distance between the request and a chunk (cosine distance is in range 0..2)
    """
    text_processor = TextProcessor(embeddings_client=embeddings_client, db_config=DB_CONFIG)
    search_processor = TextProcessor(
        embeddings_client=search_embeddings_client or embeddings_client,
        db_config=DB_CONFIG
    )

    load_context = input("Load context to the database? (y/n): ").strip().lower()
    if load_context == "y":
        text_processor.process_text_file(
            file_name=MANUAL_PATH,
            chunk_size=300,
            overlap=40,
            dimensions=384,
            truncate_table=True
        )

    conversation = Conversation()
    conversation.add_message(Message(Role.SYSTEM, SYSTEM_PROMPT))

    print("🎯 Microwave Manual Assistant. Type 'exit' to quit.")
    while True:
        user_request = input("\n> ").strip()
        if user_request.lower() in ("exit", "quit"):
            print("Bye!")
            break
        if not user_request:
            continue

        # Step 1: Retrieval
        print(f"{'=' * 100}\n🔍 STEP 1: RETRIEVAL\n{'-' * 100}")
        context_chunks = search_processor.search(
            search_mode=SearchMode.COSINE_DISTANCE,
            user_request=user_request,
            top_k=5,
            score=min_score,
            dimensions=search_dimensions
        )

        # Step 2: Augmentation
        print(f"{'=' * 100}\n🔗 STEP 2: AUGMENTATION\n{'-' * 100}")
        augmented_prompt = USER_PROMPT.format(context="\n\n".join(context_chunks), query=user_request)
        print(augmented_prompt)
        conversation.add_message(Message(Role.USER, augmented_prompt))

        # Step 3: Generation
        print(f"{'=' * 100}\n🤖 STEP 3: GENERATION\n{'-' * 100}")
        ai_message = chat_client.get_completion(conversation.get_messages())
        conversation.add_message(ai_message)
        print(f"Answer: {ai_message.content}")
        print("=" * 100)


if __name__ == "__main__":
    # PAY ATTENTION THAT YOU NEED TO RUN Postgres DB ON THE 5433 WITH PGVECTOR EXTENSION! (docker-compose.yml)
    start(
        embeddings_client=EmbeddingsClient(
            endpoint=OPENAI_EMBEDDINGS_ENDPOINT,
            model_name=OPENAI_EMBEDDINGS_MODEL,
            api_key=OPENAI_API_KEY
        ),
        chat_client=ChatCompletionClient(
            endpoint=OPENAI_CHAT_COMPLETIONS_ENDPOINT,
            model_name=OPENAI_TERRA_MODEL,
            api_key=OPENAI_API_KEY
        ),
    )
