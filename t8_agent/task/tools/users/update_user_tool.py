from typing import Any

from commons.user_service.user_info import UserUpdate
from t8_agent.task.tools.users.base import BaseUserServiceTool


class UpdateUserTool(BaseUserServiceTool):

    @property
    def name(self) -> str:
        return "update_user"

    @property
    def description(self) -> str:
        return (
            "Updates an existing user by ID. Provide only the fields that should change in `new_info`; "
            "fields that are not provided are left unchanged."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        new_info_schema = UserUpdate.model_json_schema()
        # `$ref` links inside the nested schema point to the root document, so `$defs` must live at the root
        defs = new_info_schema.pop("$defs", {})
        schema: dict[str, Any] = {
            "type": "object",
            "properties": {
                "id": {"type": "number", "description": "User ID that should be updated."},
                "new_info": new_info_schema,
            },
            "required": ["id"],
        }
        if defs:
            schema["$defs"] = defs
        return schema

    def execute(self, arguments: dict[str, Any]) -> str:
        try:
            user_id = int(arguments["id"])
            user_update_model = UserUpdate.model_validate(arguments.get("new_info") or {})
            return self._user_client.update_user(user_id, user_update_model)
        except Exception as e:
            return f"Error while updating user: {str(e)}"
