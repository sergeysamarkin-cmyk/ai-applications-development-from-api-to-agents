import json
import anthropic
from anthropic.lib import files_from_dir
from pathlib import Path

from commons.constants import ANTHROPIC_API_KEY, ANTHROPIC_SONNET_MODEL


SKILLS_VERSION = "skills-2025-10-02"
CODE_EXECUTION_VERSION = "code-execution-2025-08-25"


def get_or_create_skill(skill_title: str, skill_dir: Path,  client: anthropic.Anthropic) -> str:
    # Look for an existing custom skill with the same title
    for skill in client.beta.skills.list(source="custom", betas=[SKILLS_VERSION]):
        if skill.display_name == skill_title:
            print(f"Skill '{skill_title}' already exists: id={skill.id}, latest_version={skill.latest_version_id}")
            return skill.id

    # Otherwise upload the skill folder as a new custom skill
    skill = client.beta.skills.create(
        display_name=skill_title,
        files=files_from_dir(skill_dir),
        betas=[SKILLS_VERSION],
    )
    print(f"Created skill '{skill_title}': id={skill.id}")
    return skill.id


def delete_skills(client: anthropic.Anthropic):
    for skill in client.beta.skills.list(source="custom", betas=[SKILLS_VERSION]):
        # A skill can only be deleted after all of its versions are deleted
        for version in client.beta.skills.versions.list(skill_id=skill.id, betas=[SKILLS_VERSION]):
            client.beta.skills.versions.delete(version=version.id, skill_id=skill.id, betas=[SKILLS_VERSION])
            print(f"Deleted version {version.id} of skill {skill.id}")

        client.beta.skills.delete(skill.id, betas=[SKILLS_VERSION])
        print(f"Deleted skill '{skill.display_name}' ({skill.id})")


def chat(client: anthropic.Anthropic, skill_id: str, log_request: bool=True, log_response: bool = True):
    """Multi-turn chat loop that reuses the container across turns."""
    messages = []
    container_id = None
    print("\nStyle Guide Agent is ready. Ask it to write, rewrite, or review any text.")
    print("Type 'exit' to quit.\n")

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() == "exit":
            break

        messages.append({"role": "user", "content": user_input})

        container = {
            "skills": [{"type": "custom", "skill_id": skill_id, "version": "latest"}],
        }
        if container_id:
            container["id"] = container_id

        request_payload = {
            "model": ANTHROPIC_SONNET_MODEL,
            "max_tokens": 4096,
            "messages": messages,
            "container": container,
            "betas": [CODE_EXECUTION_VERSION, SKILLS_VERSION],
            "tools": [{"type": "code_execution_20250825", "name": "code_execution"}],
        }

        if log_request:
            print("\n--- REQUEST ---")
            print(json.dumps(request_payload, indent=2, default=str))

        response = client.beta.messages.create(**request_payload)

        if log_response:
            print("\n--- RESPONSE ---")
            print(response.model_dump_json(indent=2))
        else:
            text = "".join(block.text for block in response.content if block.type == "text")
            print(f"Claude: {text}")

        if response.container:
            container_id = response.container.id

        messages.append({"role": "assistant", "content": response.content})


STYLE_SKILL_TITLE = "style-guide"
STYLE_SKILL_DIR = Path(__file__).parent / "_skills" / STYLE_SKILL_TITLE

CALCULATOR_SKILL_TITLE = "calculator"
CALCULATOR_SKILL_DIR = Path(__file__).parent / "_skills" / CALCULATOR_SKILL_TITLE


def main():
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    try:
        skill_id = get_or_create_skill(STYLE_SKILL_TITLE, STYLE_SKILL_DIR, client)
        chat(client, skill_id)
    finally:
        delete_skills(client)


if __name__ == "__main__":
    main()
