from typing import Any

from commons.user_service.user_info import UserUpdate
from t10_mcp_advanced.mcp_server.tools.users.base import BaseUserServiceTool


class UpdateUserTool(BaseUserServiceTool):

    @property
    def name(self) -> str:
        return "update_user"

    @property
    def description(self) -> str:
        return (
            "Updates an existing user by the numeric user ID. Put only the fields that should change into new_info."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        new_info_schema = UserUpdate.model_json_schema()
        # nested models are referenced as #/$defs/... which must be at the root of the schema
        defs = new_info_schema.pop("$defs", {})
        return {
            "type": "object",
            "properties": {
                "id": {"type": "number", "description": "User ID that should be updated"},
                "new_info": new_info_schema,
            },
            "required": ["id"],
            "$defs": defs,
        }

    async def execute(self, arguments: dict[str, Any]) -> str:
        user_id = int(arguments["id"])
        new_info = UserUpdate.model_validate(arguments.get("new_info") or {})
        return self._user_client.update_user(user_id, new_info)
