from enum import StrEnum
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, Field

from commons.constants import OPENAI_API_KEY, OPENAI_LUNA_MODEL
from t6_grounding.user_service_client import UserServiceClient

QUERY_ANALYSIS_PROMPT = """You are a query analysis system for a user database.
Available search fields: name, surname, email.
- Analyze the user question and extract explicit search values
- Map extracted values to the appropriate search fields
- Only extract values that are clearly stated - do not infer or assume
- Examples:
  "Who is John?" -> name: "John"
  "Find John Smith" -> name: "John", surname: "Smith"
  "Find users with surname Adams" -> surname: "Adams"
- If no search values are stated, return an empty list
"""

SYSTEM_PROMPT = """You are a RAG-powered assistant that answers questions about users.
The user message contains two sections: RAG CONTEXT and USER QUESTION.
- Answer ONLY based on the provided RAG CONTEXT
- If there is no relevant information in RAG CONTEXT, say that the question cannot be answered
- Format user information clearly when presenting it
"""

USER_PROMPT = """##RAG CONTEXT:
{context}

##USER QUESTION:
{query}"""


class SearchField(StrEnum):
    NAME = "name"
    SURNAME = "surname"
    EMAIL = "email"


class SearchRequest(BaseModel):
    search_field: SearchField = Field(description="Search field")
    search_value: str = Field(description="Search value. Sample: Adam.")


class SearchRequests(BaseModel):
    search_request_parameters: list[SearchRequest] = Field(
        description="List of search parameters to execute",
        default_factory=list
    )


llm_client = OpenAI(api_key=OPENAI_API_KEY)

user_client = UserServiceClient()


def retrieve_context(user_question: str) -> list[dict[str, Any]]:
    messages = [
        {"role": "system", "content": QUERY_ANALYSIS_PROMPT},
        {"role": "user", "content": user_question},
    ]
    response = llm_client.beta.chat.completions.parse(
        model=OPENAI_LUNA_MODEL,
        temperature=0.0,
        reasoning_effort="none",
        messages=messages,
        response_format=SearchRequests,
    )
    parameters = response.choices[0].message.parsed.search_request_parameters

    if parameters:
        search_params = {param.search_field.value: param.search_value for param in parameters}
        print(f"Searching with parameters: {search_params}")
        return user_client.search_users(**search_params)

    print("No specific search parameters found!")
    return []


def augment_prompt(user_question: str, context: list[dict[str, Any]]) -> str:
    context_text = ""
    for user in context:
        context_text += "User:\n"
        for key, value in user.items():
            context_text += f"  {key}: {value}\n"
        context_text += "\n"

    augmented = USER_PROMPT.format(context=context_text, query=user_question)
    print(augmented)
    return augmented


def generate_answer(augmented_prompt: str) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": augmented_prompt},
    ]
    response = llm_client.chat.completions.create(
        model=OPENAI_LUNA_MODEL,
        temperature=0.0,
        reasoning_effort="none",
        messages=messages,
    )
    return response.choices[0].message.content or ""


def main():
    print("Query samples:")
    print(" - I need user emails that filled with hiking and psychology")
    print(" - Who is John?")
    print(" - Find users with surname Adams")
    print(" - Do we have smbd with name John that love painting?")

    while True:
        user_question = input("> ").strip()
        if user_question:
            if user_question.lower() in ['quit', 'exit']:
                break

            print("\n--- Retrieving context ---")
            context = retrieve_context(user_question)
            if context:
                print("\n--- Augmenting prompt ---")
                augmented_prompt = augment_prompt(user_question, context)
                print("\n--- Generating answer ---")
                answer = generate_answer(augmented_prompt)
                print(f"\nAnswer: {answer}\n")
            else:
                print("\n--- No relevant information found ---")


if __name__ == "__main__":
    main()


# The problems with API based Grounding approach are:
#   - We need a Pre-Step to figure out what field should be used for search (Takes time)
#   - Values for search should be correct (✅ John -> ❌ Jonh)
#   - Is not so flexible
# Benefits are:
#   - We fetch actual data (new users added and deleted every 5 minutes)
#   - Costs reduce
