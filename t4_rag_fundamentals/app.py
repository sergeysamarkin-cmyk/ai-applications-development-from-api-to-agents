import os

from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import FAISS
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.vectorstores import VectorStore
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import SecretStr

from commons.constants import OPENAI_API_KEY, OPENAI_EMBEDDINGS_MODEL, OPENAI_TERRA_MODEL

# Paths are resolved relative to this file, so the app works from any working directory
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_MANUAL_PATH = os.path.join(_BASE_DIR, "microwave_manual.txt")
_INDEX_PATH = os.path.join(_BASE_DIR, "microwave_faiss_index")

_SYSTEM_PROMPT = """
You are a helpful assistant that answers questions about the microwave oven using its user manual.

Every user message consists of 2 blocks:
- `##RAG CONTEXT:` - fragments of the microwave manual, retrieved for the user request
- `##USER QUESTION:` - the actual question of the user

Instructions:
- Answer using ONLY the information from the `RAG CONTEXT` and from this conversation.
- Do not use your own knowledge and do not make assumptions.
- If the `RAG CONTEXT` is empty or does not contain the answer, reply that you cannot answer this question
  because there is no such information in the microwave manual.
- Strictly refuse to answer any question that is not about the microwave or is not covered by the `RAG CONTEXT`
  (general knowledge, history, opinions, other products, etc.).
- Keep the answer concise and precise.
"""

_USER_PROMPT = """##RAG CONTEXT:
{context}


##USER QUESTION:
{query}"""


class MicrowaveRAG:

    def __init__(self, embeddings: OpenAIEmbeddings, llm_client: ChatOpenAI, index_path: str = _INDEX_PATH):
        self.llm_client = llm_client
        self.embeddings = embeddings
        self.index_path = index_path
        self.vectorstore = self._setup_vectorstore()

    def _setup_vectorstore(self) -> VectorStore:
        """
        Load existing FAISS index from disk or create a new one.
        Returns:
              VectorStore: Initialized FAISS vectorstore.
        """
        print("🔄 Initializing Microwave Manual RAG System...")
        if os.path.exists(self.index_path):
            print(f"📂 Loading existing FAISS index from '{self.index_path}'")
            # The index was created by this application, so deserialization is safe
            return FAISS.load_local(
                folder_path=self.index_path,
                embeddings=self.embeddings,
                allow_dangerous_deserialization=True,
            )
        print("🆕 FAISS index not found, creating a new one...")
        return self._create_new_index()

    def _create_new_index(self) -> VectorStore:
        """
        Load the manual, split into chunks, embed, and save a new FAISS index.
        Returns:
              VectorStore: Newly created and saved FAISS vectorstore.
        """
        print(f"📖 Loading '{os.path.basename(_MANUAL_PATH)}'...")
        documents = TextLoader(file_path=_MANUAL_PATH, encoding="utf-8").load()

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=300,
            chunk_overlap=50,
            separators=["\n\n", "\n", "."],
        )
        chunks = splitter.split_documents(documents)
        print(f"✂️ Split into {len(chunks)} chunks")

        vectorstore = FAISS.from_documents(documents=chunks, embedding=self.embeddings)
        vectorstore.save_local(self.index_path)
        print(f"💾 FAISS index saved to '{self.index_path}'")
        return vectorstore

    def retrieve_context(self, query: str, k: int = 4, score=0.3):
        """
        Retrieve the context for a given query.
        Args:
              query (str): The query to retrieve the context for.
              k (int): The number of relevant documents(chunks) to retrieve.
              score (float): The similarity score between documents and query. Range 0.0 to 1.0.
        """
        print(f"{'=' * 100}\n🔍 STEP 1: RETRIEVAL\n{'-' * 100}")
        print(f"Searching for top {k} chunks with relevance score >= {score}")

        results = self.vectorstore.similarity_search_with_relevance_scores(
            query=query,
            k=k,
            score_threshold=score,
        )

        context_parts = []
        for doc, relevance_score in results:
            context_parts.append(doc.page_content)
            print(f"📄 Score: {relevance_score:.4f}\n{doc.page_content}\n")

        if not context_parts:
            print("⚠️ No relevant chunks found")

        print("=" * 100)
        return "\n\n".join(context_parts)

    def augment_prompt(self, query: str, context: str):
        """
        Inject retrieved context and user query into the prompt template.
        Args:
              query (str): The user's question.
              context (str): Retrieved context from the vectorstore.
        Returns:
              str: Formatted prompt ready for the LLM.
        """
        print(f"\n🔗 STEP 2: AUGMENTATION\n{'-' * 100}")
        augmented_prompt = _USER_PROMPT.format(context=context, query=query)
        print(augmented_prompt)
        print("=" * 100)
        return augmented_prompt

    def generate_answer(self, augmented_prompt: str):
        """
        Send the augmented prompt to the LLM and return its response.
        Args:
              augmented_prompt (str): The prompt with injected context and query.
        Returns:
              str: The LLM-generated answer.
        """
        print(f"\n🤖 STEP 3: GENERATION\n{'-' * 100}")
        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=augmented_prompt),
        ]
        response = self.llm_client.invoke(messages)
        print(f"Answer: {response.content}")
        print("=" * 100)
        return response.content


def main(rag: MicrowaveRAG):
    print("🎯 Microwave Manual Assistant")
    print("Ask a question about the microwave oven. Type 'exit' to quit.")

    while True:
        user_question = input("\n> ").strip()
        if user_question.lower() in ("exit", "quit"):
            print("Bye!")
            break
        if not user_question:
            continue

        # Step 1: Retrieval
        context = rag.retrieve_context(user_question)
        # Step 2: Augmentation
        augmented_prompt = rag.augment_prompt(user_question, context)
        # Step 3: Generation
        rag.generate_answer(augmented_prompt)


if __name__ == "__main__":
    main(
        MicrowaveRAG(
            embeddings=OpenAIEmbeddings(
                model=OPENAI_EMBEDDINGS_MODEL,
                api_key=SecretStr(OPENAI_API_KEY),
            ),
            llm_client=ChatOpenAI(
                temperature=0.0,
                reasoning_effort="none",
                model=OPENAI_TERRA_MODEL,
                api_key=SecretStr(OPENAI_API_KEY),
            ),
        )
    )
