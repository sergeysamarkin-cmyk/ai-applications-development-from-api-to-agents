from typing import Any

from t10_mcp_advanced.mcp_server.tools.users.base import BaseUserServiceTool


class SearchUsersTool(BaseUserServiceTool):

    @property
    def name(self) -> str:
        return "search_users"

    @property
    def description(self) -> str:
        return (
            "Searches users by name, surname, email or gender. All filters are optional and can be combined. "
            "Use it to find user IDs and to check whether a user already exists."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "First name, partial match"},
                "surname": {"type": "string", "description": "Last name, partial match"},
                "email": {"type": "string", "description": "Email, partial match"},
                "gender": {"type": "string", "description": "Exact match: male, female, other, prefer_not_to_say"},
            },
            "required": [],
        }

    async def execute(self, arguments: dict[str, Any]) -> str:
        return self._user_client.search_users(**arguments)
