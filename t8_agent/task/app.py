import os

from commons.constants import OPENAI_API_KEY, ANTHROPIC_API_KEY, OPENAI_TERRA_MODEL, ANTHROPIC_SONNET_MODEL
from commons.models.conversation import Conversation
from commons.models.message import Message
from commons.models.role import Role
from commons.user_service.client import UserServiceClient

from t8_agent.task.agents.anthropic import AnthropicBasedAgent
from t8_agent.task.agents.openai import OpenAIBasedAgent
from t8_agent.task.prompts import SYSTEM_PROMPT
from t8_agent.task.tools.users.create_user_tool import CreateUserTool
from t8_agent.task.tools.users.delete_user_tool import DeleteUserTool
from t8_agent.task.tools.users.get_user_by_id_tool import GetUserByIdTool
from t8_agent.task.tools.users.search_users_tool import SearchUsersTool
from t8_agent.task.tools.users.update_user_tool import UpdateUserTool
from t8_agent.task.tools.web_search import WebSearchTool

# AGENT_PROVIDER=openai (default) or AGENT_PROVIDER=anthropic switches the LLM provider
AGENT_PROVIDER = os.getenv("AGENT_PROVIDER", "openai").lower()


def main():
    user_client = UserServiceClient()
    tools = [
        WebSearchTool(OPENAI_API_KEY),
        GetUserByIdTool(user_client),
        SearchUsersTool(user_client),
        CreateUserTool(user_client),
        UpdateUserTool(user_client),
        DeleteUserTool(user_client),
    ]

    if AGENT_PROVIDER == "anthropic":
        agent = AnthropicBasedAgent(
            model=ANTHROPIC_SONNET_MODEL, api_key=ANTHROPIC_API_KEY, tools=tools, system_prompt=SYSTEM_PROMPT
        )
    else:
        agent = OpenAIBasedAgent(
            model=OPENAI_TERRA_MODEL, api_key=OPENAI_API_KEY, tools=tools, system_prompt=SYSTEM_PROMPT
        )

    conversation = Conversation()
    print(f"User management agent ({AGENT_PROVIDER}). Type 'exit' to quit.")
    print("Try: 'Add Andrej Karpathy as a new user', 'Find all female users', 'Delete user with id 3'")

    while True:
        user_input = input("> ").strip()
        if not user_input:
            continue
        if user_input.lower() in ["exit", "quit"]:
            break

        conversation.add_message(Message(role=Role.USER, content=user_input))
        ai_message = agent.get_response(conversation.get_messages())
        conversation.add_message(ai_message)
        print(f"\nAI: {ai_message.content}\n")


main()
