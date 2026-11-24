import asyncio
import json
import os

from commons.constants import OPENAI_API_KEY, DEFAULT_SYSTEM_PROMPT
from commons.models.message import Message
from commons.models.role import Role
from t11_mcp_auth.agent._agent import AgentMCPAuth
from t11_mcp_auth.agent.mcp_clients.api_key_mcp_client import ApiKeyMCPClient
from t11_mcp_auth.agent.mcp_clients.oauth_mcp_client import OauthHttpMCPClient

MCP_API_KEY: str = "dev-secret-key"

# MCP_AUTH=apikey (default, server on 8007) or MCP_AUTH=oauth (Keycloak login, server on 8008)
MCP_AUTH = os.getenv("MCP_AUTH", "apikey").lower()


async def main():
    if MCP_AUTH == "oauth":
        client = OauthHttpMCPClient(mcp_server_url="http://localhost:8008/mcp")
    else:
        client = ApiKeyMCPClient(mcp_server_url="http://localhost:8007/mcp", api_key=MCP_API_KEY)

    async with client as mcp_client:
        tools = await mcp_client.get_tools()
        print("\nAvailable tools:")
        for tool in tools:
            print(json.dumps(tool, indent=2))

        agent = AgentMCPAuth(
            api_key=OPENAI_API_KEY,
            model=os.getenv("OPENAI_MODEL", "gpt-5.6-terra"),
            tools=tools,
            mcp_client=mcp_client,
        )

        messages: list[Message] = [Message(role=Role.SYSTEM, content=DEFAULT_SYSTEM_PROMPT)]

        print(f"\nAgent is ready (auth: {MCP_AUTH}). Type 'exit' to quit.")
        while True:
            user_input = input("\n> ").strip()
            if user_input.lower() == "exit":
                break
            if not user_input:
                continue

            messages.append(Message(role=Role.USER, content=user_input))
            ai_message = await agent.get_completion(messages)
            messages.append(ai_message)


if __name__ == "__main__":
    asyncio.run(main())
