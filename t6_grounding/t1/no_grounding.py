import asyncio
from typing import Any

from openai import AsyncOpenAI

from commons.constants import OPENAI_API_KEY, OPENAI_LUNA_MODEL
from t6_grounding.user_service_client import UserServiceClient

BATCH_SYSTEM_PROMPT = """You are a user search assistant.
You receive a list of users and a search question.
- Analyze the search criteria from the user question
- Examine each user in the provided list and determine if they match the criteria
- Return full details of matching users in their original format
- Do not invent, change or summarize user data
- Return exactly "NO_MATCHES_FOUND" if no users match
"""

FINAL_SYSTEM_PROMPT = """You are a user search assistant that compiles final search results.
You receive results of several batch searches over the user database. Each batch result is either
matching users or "NO_MATCHES_FOUND".
- Review all batch search results
- Combine and deduplicate matching users found across batches (every user id must appear only once)
- Present results in a clear, organized manner, keeping user data exactly as it was given
- If no batch found anyone, say that no users were found and suggest refining the search
"""

USER_PROMPT = """USER DATA:
{context}

SEARCH QUESTION:
{query}"""


class TokenTracker:

    def __init__(self):
        self.total_tokens = 0
        self.batch_tokens = []

    def add_tokens(self, tokens: int):
        self.total_tokens += tokens
        self.batch_tokens.append(tokens)

    def get_summary(self) -> dict:
        return {
            'total_tokens': self.total_tokens,
            'batch_count': len(self.batch_tokens),
            'batch_tokens': self.batch_tokens,
        }


llm_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

token_tracker = TokenTracker()


def join_context(context: list[dict[str, Any]]) -> str:
    result = ""
    for user in context:
        result += "User:\n"
        for key, value in user.items():
            result += f"  {key}: {value}\n"
        result += "\n"
    return result


async def generate_response(system_prompt: str, user_message: str) -> str:
    print("Processing...")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    response = await llm_client.chat.completions.create(
        model=OPENAI_LUNA_MODEL,
        temperature=0.0,
        reasoning_effort="none",  # GPT-5.6 accepts a non-default temperature only without reasoning
        messages=messages,
    )

    tokens = response.usage.total_tokens if response.usage else 0
    token_tracker.add_tokens(tokens)

    content = response.choices[0].message.content or ""
    print(f"Response: {content}\nTokens: {tokens}")
    return content


async def main():
    print("Query samples:")
    print(" - Do we have someone with name John that loves traveling?")

    user_question = input("> ").strip()

    if user_question:
        # 1. FETCH & BATCH USERS
        print("\n--- Searching user database ---")
        users = UserServiceClient().get_all_users()
        batches = [users[i:i + 100] for i in range(0, len(users), 100)]

        # 2. PARALLEL BATCH SEARCH
        coroutines = [
            generate_response(BATCH_SYSTEM_PROMPT, USER_PROMPT.format(context=join_context(batch), query=user_question))
            for batch in batches
        ]
        batch_results = await asyncio.gather(*coroutines)

        # 3. FILTER RESULTS
        print("\n--- Compiling results ---")
        relevant_results = [result for result in batch_results if result.strip() != "NO_MATCHES_FOUND"]

        # 4. FINAL GENERATION
        print("\n=== SEARCH RESULTS ===")
        if relevant_results:
            combined_results = "\n\n".join(relevant_results)
            final_answer = await generate_response(
                FINAL_SYSTEM_PROMPT,
                USER_PROMPT.format(context=combined_results, query=user_question),
            )
            print(final_answer)
        else:
            print("No users found. Try to refine your search question.")

        # 5. PERFORMANCE SUMMARY
        summary = token_tracker.get_summary()
        print("\n=== Performance ===")
        print(f"Total API calls: {summary['batch_count']}")
        print(f"Total tokens: {summary['total_tokens']}")


if __name__ == "__main__":
    asyncio.run(main())


# The problems with No Grounding approach are:
#   - If we load whole users as context in one request to LLM we will hit context window
#   - Huge token usage == Higher price per request
#   - Added + one chain in flow where original user data can be changed by LLM (before final generation)
# User Question -> Get all users -> ‼️parallel search of possible candidates‼️ -> probably changed original context -> final generation
