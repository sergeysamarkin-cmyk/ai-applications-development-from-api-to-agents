from typing import Any

from t8_agent.task.tools.users.base import BaseUserServiceTool


class SearchUsersTool(BaseUserServiceTool):

    @property
    def name(self) -> str:
        return "search_users"

    @property
    def description(self) -> str:
        return (
            "Searches users by name, surname, email or gender. All filters are optional and can be combined. "
            "Use it to find users when the ID is not known."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "User name, for example: John"},
                "surname": {"type": "string", "description": "User surname, for example: Adams"},
                "email": {"type": "string", "description": "User email"},
                "gender": {"type": "string", "description": "User gender, for example: female"},
            },
            "required": [],
        }

    def execute(self, arguments: dict[str, Any]) -> str:
        try:
            return self._user_client.search_users(**arguments)
        except Exception as e:
            return f"Error while searching users: {str(e)}"
