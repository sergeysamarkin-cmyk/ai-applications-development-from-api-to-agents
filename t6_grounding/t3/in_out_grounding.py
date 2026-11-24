import asyncio
import json
from typing import Any

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from commons.constants import OPENAI_API_KEY, OPENAI_EMBEDDINGS_MODEL, OPENAI_LUNA_MODEL
from t6_grounding.user_service_client import UserServiceClient

# TASK: Info about app:
# HOBBIES SEARCHING WIZARD
# Searches users by hobbies and provides their full info in JSON format:
#   Input: `I need people who love to go to mountains`
#   Output:
#     ```json
#       "rock climbing": [{full user info JSON},...],
#       "hiking": [{full user info JSON},...],
#       "camping": [{full user info JSON},...]
#     ```
# ---
# 1. Since we are searching hobbies that persist in `about_me` section - we need to embed only user `id` and `about_me`!
#    It will allow us to reduce context window significantly.
# 2. Pay attention that every 5 minutes in User Service will be added new users and some will be deleted. We will at the
#    'cold start' add all users for current moment to vectorstor and with each user request we will update vectorstor on
#    the retrieval step, we will remove deleted users and add new - it will also resolve the issue with consistency
#    within this 2 services and will reduce costs (we don't need on each user request load vectorstor from scratch and pay for it).
# 3. We ask LLM make NEE (Named Entity Extraction) https://cloud.google.com/discover/what-is-entity-extraction?hl=en
#    and provide response in format:
#    {
#       "{hobby}": [{user_id}, 2, 4, 100...]
#    }
#    It allows us to save significant money on generation, reduce time on generation and eliminate possible
#    hallucinations (corrupted personal info or removed some parts of PII (Personal Identifiable Information)). After
#    generation we also need to make output grounding (fetch full info about user and in the same time check that all
#    presented IDs are correct).
# 4. In response we expect JSON with grouped users by their hobbies.
# ---
# This sample is based on the real solution where one Service provides our Wizard with user request, we fetch all
# required data and then returned back to 1st Service response in JSON format.
# ---
# Useful links:
# Chroma DB: https://docs.langchain.com/oss/python/integrations/vectorstores/index#chroma
# Document#id: https://docs.langchain.com/oss/python/langchain/knowledge-base#1-documents-and-document-loaders
# ---
# TASK:
# Implement such application as described on the `flow.png` with adaptive vector based grounding and 'lite' version of
# output grounding (verification that such user exist and fetch full user info)

COLLECTION_NAME = "users_about_me"
EMBEDDING_BATCH_SIZE = 100  # Gemini and OpenAI limit the number of inputs per embeddings request
EMBEDDING_DIMENSIONS = 384
TOP_K = 30  # how many closest users we take from the vector store for the request
SCORE_THRESHOLD = 0.2  # cosine similarity; closer to 1 means more similar

HOBBY_EXTRACTION_PROMPT = """You are a named entity extraction system for user profiles.
You receive a user request about hobbies and a list of users, each with an id and an about_me text.
- Find hobbies or activities that the request is looking for and that are mentioned in the users' about_me
  (for example, "mountains" can match "hiking", "rock climbing" or "camping" if these are written in about_me)
- For each hobby, list the ids of the users whose about_me clearly mentions this hobby
- Use only ids from the provided list, never invent ids and never change the text
- Write hobbies in lowercase
- If no user matches, return an empty list
"""


class HobbyUsers(BaseModel):
    hobby: str = Field(description="Hobby or activity from about_me, in lowercase")
    user_ids: list[int] = Field(description="Ids of the users who have this hobby", default_factory=list)


class HobbyGroups(BaseModel):
    hobbies: list[HobbyUsers] = Field(description="Hobbies with user ids", default_factory=list)


class HobbiesWizard:
    def __init__(self, embeddings: OpenAIEmbeddings):
        self.user_client = UserServiceClient()
        self.llm_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        self.vectorstore = Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=embeddings,
            collection_metadata={"hnsw:space": "cosine"},
        )

    @staticmethod
    def _to_document(user: dict[str, Any]) -> Document:
        # only id and about_me are embedded and stored, the full user data is fetched later (output grounding)
        return Document(id=str(user["id"]), page_content=user["about_me"], metadata={"user_id": user["id"]})

    async def sync_vectorstore(self) -> None:
        """Adaptive update: add new users, delete users that were removed from the User Service."""
        users = await asyncio.to_thread(self.user_client.get_all_users)
        current = {str(user["id"]): user for user in users if user.get("about_me")}

        stored_ids = set(self.vectorstore.get(include=[])["ids"])
        new_ids = [uid for uid in current if uid not in stored_ids]
        deleted_ids = [uid for uid in stored_ids if uid not in current]

        if deleted_ids:
            self.vectorstore.delete(ids=deleted_ids)
        for i in range(0, len(new_ids), EMBEDDING_BATCH_SIZE):
            batch_ids = new_ids[i:i + EMBEDDING_BATCH_SIZE]
            documents = [self._to_document(current[uid]) for uid in batch_ids]
            await self.vectorstore.aadd_documents(documents, ids=batch_ids)

        print(f"Vector store synced: {len(current)} users, {len(new_ids)} added, {len(deleted_ids)} deleted")

    async def retrieve_candidates(self, request: str) -> list[dict[str, Any]]:
        results = await self.vectorstore.asimilarity_search_with_relevance_scores(request, k=TOP_K)

        candidates = []
        for doc, score in results:
            if score < SCORE_THRESHOLD:
                continue
            candidates.append({"user_id": doc.metadata["user_id"], "about_me": doc.page_content})
            print(f"Candidate (score {score:.3f}): id={doc.metadata['user_id']}")
        return candidates

    async def extract_hobbies(self, request: str, candidates: list[dict[str, Any]]) -> HobbyGroups:
        users_text = "\n".join(f"[id={c['user_id']}] {c['about_me']}" for c in candidates)
        messages = [
            {"role": "system", "content": HOBBY_EXTRACTION_PROMPT},
            {"role": "user", "content": f"USER REQUEST: {request}\n\nUSERS:\n{users_text}"},
        ]
        response = await self.llm_client.beta.chat.completions.parse(
            model=OPENAI_LUNA_MODEL,
            temperature=0.0,
            reasoning_effort="none",
            messages=messages,
            response_format=HobbyGroups,
        )
        return response.choices[0].message.parsed or HobbyGroups()

    async def ground_output(self, groups: HobbyGroups, candidates: list[dict[str, Any]]) -> dict[str, list[dict]]:
        """Lite output grounding: keep only ids that were retrieved, fetch full user data from the User Service."""
        allowed_ids = {c["user_id"] for c in candidates}

        requested_ids = {uid for group in groups.hobbies for uid in group.user_ids if uid in allowed_ids}
        fetched = await asyncio.gather(
            *[self.user_client.get_user(uid) for uid in requested_ids], return_exceptions=True
        )
        full_users = {}
        for uid, result in zip(requested_ids, fetched):
            if isinstance(result, BaseException):
                print(f"User {uid} was not found in the User Service, skipped")
                continue
            full_users[uid] = result

        output: dict[str, list[dict]] = {}
        for group in groups.hobbies:
            hobby = group.hobby.strip().lower()
            for uid in group.user_ids:
                if uid in full_users:
                    users_for_hobby = output.setdefault(hobby, [])
                    if full_users[uid] not in users_for_hobby:
                        users_for_hobby.append(full_users[uid])
        return output


async def main():
    embeddings = OpenAIEmbeddings(
        model=OPENAI_EMBEDDINGS_MODEL,
        api_key=OPENAI_API_KEY,
        dimensions=EMBEDDING_DIMENSIONS,
        check_embedding_ctx_length=False,
    )
    wizard = HobbiesWizard(embeddings)

    print("Query samples:")
    print(" - I need people who love to go to mountains")
    print(" - Who likes painting or photography?")

    await wizard.sync_vectorstore()  # cold start

    while True:
        request = input("> ").strip()
        if not request:
            continue
        if request.lower() in ["quit", "exit"]:
            break

        await wizard.sync_vectorstore()
        candidates = await wizard.retrieve_candidates(request)
        if not candidates:
            print(json.dumps({}, indent=2))
            continue

        groups = await wizard.extract_hobbies(request, candidates)
        output = await wizard.ground_output(groups, candidates)
        print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
