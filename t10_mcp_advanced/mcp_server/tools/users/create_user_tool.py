from typing import Any

from commons.user_service.user_info import UserCreate
from t10_mcp_advanced.mcp_server.tools.users.base import BaseUserServiceTool


class CreateUserTool(BaseUserServiceTool):

    @property
    def name(self) -> str:
        return "add_user"

    @property
    def description(self) -> str:
        return (
            "Creates a new user. Required fields: name, surname, email, about_me. "
            "Other fields are optional. Do not invent an email: ask the user if it is unknown."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return UserCreate.model_json_schema()

    async def execute(self, arguments: dict[str, Any]) -> str:
        user_create = UserCreate.model_validate(arguments)
        return self._user_client.add_user(user_create)
