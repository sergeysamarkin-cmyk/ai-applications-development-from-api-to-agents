from pathlib import Path
from typing import Any

from t12_skills.custom.file_utils import get_file_content
from t12_skills.custom.tools.base import BaseTool


class ReadSkillTool(BaseTool):
    """Reads files from the local skills directory by path."""

    def __init__(self, skills_dir: Path):
        self._skills_dir = skills_dir.resolve()

    @property
    def name(self) -> str:
        return "read_skill"

    @property
    def description(self) -> str:
        return (
            "Reads a file from the skills directory. Call it to load a skill's SKILL.md before you act on a "
            "request that matches the skill, and to read any reference file or script the skill points to. "
            "The path starts with the skill folder name, for example '/unit-converter/SKILL.md' or "
            "'/unit-converter/examples.md'."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Path inside the skills directory, starting with the skill name and a slash, "
                        "for example '/unit-converter/SKILL.md'."
                    ),
                }
            },
            "required": ["path"],
        }

    async def _execute(self, arguments: dict[str, Any]) -> str:
        relative_path = arguments["path"].lstrip("/")
        full_path = (self._skills_dir / relative_path).resolve()

        # Keep the agent inside the skills directory (no ../ escapes)
        if not full_path.is_relative_to(self._skills_dir):
            return f"ERROR: path is outside the skills directory: {arguments['path']}"

        return get_file_content(full_path)
