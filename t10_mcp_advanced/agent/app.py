import os
import asyncio

from commons.models.message import Message
from commons.models.role import Role
from t10_mcp_advanced.agent.agent import CustomAgentMCP
from t10_mcp_advanced.agent.clients.custom_mcp_client import CustomMCPClient
from t10_mcp_advanced.agent.clients.mcp_client import MCPClient
from commons.constants import OPENAI_API_KEY, OPENAI_TERRA_MODEL

UMS_MCP_URL = "http://localhost:8006/mcp"
WEB_SEARCH_MCP_URL = "http://localhost:8010/mcp"

# MCP_CLIENT=custom uses the CustomMCPClient (our own implementation) for the Users Management server,
# by default the official `mcp` library client is used
UMS_CLIENT = os.getenv("MCP_CLIENT", "official").lower()


async def main():
    # Tools from MCP servers and the map tool name -> MCP client that provides it
    tools: list[dict] = []
    tool_name_client_map: dict[str, MCPClient | CustomMCPClient] = {}

    # Users Management MCP server (our server from mcp_server)
    if UMS_CLIENT == "custom":
        ums_client = await CustomMCPClient.create(UMS_MCP_URL)
    else:
        ums_client = await MCPClient.create(UMS_MCP_URL)
    for tool in await ums_client.get_tools():
        tools.append(tool)
        tool_name_client_map[tool["function"]["name"]] = ums_client

    # Web search MCP server (ddg-mcp-server from docker-compose)
    web_client = await MCPClient.create(WEB_SEARCH_MCP_URL)
    for tool in await web_client.get_tools():
        tools.append(tool)
        tool_name_client_map[tool["function"]["name"]] = web_client

    agent = CustomAgentMCP(
        api_key=OPENAI_API_KEY,
        model=OPENAI_TERRA_MODEL,
        tools=tools,
        tool_name_client_map=tool_name_client_map,
    )

    messages: list[Message] = [
        Message(
            role=Role.SYSTEM,
            content=(
                "You are a User Management Agent. Help the user to search, create, update and delete users. "
                "Use the Users Management tools for user data and the web search tool to find public information "
                "about people. Before deleting a user ask for confirmation. Do not reveal sensitive data "
                "(credit card, salary, date of birth). Keep answers short and structured. "
                "When you add a person from web search, fill only the facts that the search results confirm. "
                "Never invent an email, phone or address: if the email is not confirmed by the search results, "
                "do not guess it, ask the user for the email instead of adding the person."
            ),
        )
    ]

    try:
        print("\nType 'exit' to quit.")
        while True:
            user_input = input("\n> ").strip()
            if user_input.lower() == "exit":
                break
            if not user_input:
                continue

            messages.append(Message(role=Role.USER, content=user_input))
            ai_message = await agent.get_completion(messages)
            messages.append(ai_message)
    finally:
        # MCP connections are nested (anyio cancel scopes), so they must be closed in reverse order
        await web_client.close()
        await ums_client.close()


if __name__ == "__main__":
    asyncio.run(main())

# Check if Arkadiy Dobkin present as a user, if not then search info about him in the web and add him
