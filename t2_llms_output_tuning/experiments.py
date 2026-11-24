"""
Runs the TODO experiments from the *_task.py files one by one, so every parameter can be compared side by side.

Usage (from the repository root):
    python -m t2_llms_output_tuning.experiments gemini            # all TODOs, pause after each one
    python -m t2_llms_output_tuning.experiments gemini 2          # only the 2nd experiment
    python -m t2_llms_output_tuning.experiments gemini --full     # do not trim long answers
    python -m t2_llms_output_tuning.experiments openai_chat
    python -m t2_llms_output_tuning.experiments openai_responses
    python -m t2_llms_output_tuning.experiments anthropic

The same kwargs can be passed directly to run(...) in the corresponding *_task.py file.
"""
import contextlib
import io
import json
import sys

from commons.constants import OPENAI_TERRA_MODEL, GEMINI_FLASH_MODEL, ANTHROPIC_HAIKU_MODEL
from commons.models.message import Message
from commons.models.role import Role

# Models that still accept the "classic" sampling params (stop, penalties, seed, max_tokens)
OPENAI_CLASSIC_MODEL = "gpt-4o"

COFFEE = "Give me a name for a coffee shop"
PAPERCLIP = "List 5 alternative uses for a paperclip"
ROBOT = "Write a one-sentence story about a robot"
QUANTUM = "Explain quantum computing"
LANGUAGES = "List 3 programming languages with their year of creation"
STRAWBERRY = "How many r's are in the word strawberry?"
COUNT = "Count from 1 to 20, comma separated"
OCEAN = "Write a paragraph about the ocean"
WHITE = "Why white is white?"

OPENAI_LANGUAGES_SCHEMA = {
    "type": "object",
    "properties": {
        "languages": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "year": {"type": "integer"}},
                "required": ["name", "year"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["languages"],
    "additionalProperties": False,
}


def v(label, params, model=None, repeat=1, full=False):
    return {"label": label, "params": params, "model": model, "repeat": repeat, "full": full}


EXPERIMENTS = {
    "gemini": [
        {"todo": "TODO 1", "title": "temperature", "query": COFFEE, "max_lines": 4, "variants": [
            v("temperature=0.0 (run 1)", {"generationConfig": {"temperature": 0.0}}),
            v("temperature=0.0 (run 2)", {"generationConfig": {"temperature": 0.0}}),
            v("temperature=2.0 (run 1)", {"generationConfig": {"temperature": 2.0}}),
            v("temperature=2.0 (run 2)", {"generationConfig": {"temperature": 2.0}}),
        ]},
        {"todo": "TODO 2", "title": "topP", "query": PAPERCLIP, "variants": [
            v("topP=0.1", {"generationConfig": {"topP": 0.1}}),
            v("topP=0.95", {"generationConfig": {"topP": 0.95}}),
        ]},
        {"todo": "TODO 3", "title": "topK", "query": ROBOT, "variants": [
            v("topK=1", {"generationConfig": {"topK": 1}}),
            v("topK=64", {"generationConfig": {"topK": 64}}),
        ]},
        {"todo": "TODO 4", "title": "maxOutputTokens", "query": QUANTUM, "variants": [
            v("maxOutputTokens=50", {"generationConfig": {"maxOutputTokens": 50}}),
            v("maxOutputTokens=50 + thinkingBudget=0", {"generationConfig": {
                "maxOutputTokens": 50, "thinkingConfig": {"thinkingBudget": 0}}}),
            v("maxOutputTokens=2048", {"generationConfig": {"maxOutputTokens": 2048}}),
        ]},
        {"todo": "TODO 5", "title": "responseMimeType + responseSchema", "query": LANGUAGES, "variants": [
            v("responseMimeType=application/json + responseSchema", {"generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "array",
                    "items": {"type": "object",
                              "properties": {"name": {"type": "string"}, "year": {"type": "integer"}}},
                },
            }}),
        ]},
        {"todo": "TODO 7", "title": "thinkingConfig", "query": STRAWBERRY, "variants": [
            v("thinkingBudget=0 (no thinking)", {"generationConfig": {"thinkingConfig": {"thinkingBudget": 0}}}),
            v("thinkingBudget=5000, includeThoughts=true", {"generationConfig": {
                "thinkingConfig": {"thinkingBudget": 5000, "includeThoughts": True}}}),
        ]},
    ],
    "openai_chat": [
        {"todo": "TODO 1", "title": "n", "query": COFFEE, "variants": [
            v("n=3 (3 choices in the response)", {"n": 3, "max_completion_tokens": 1000}, full=True),
        ]},
        {"todo": "TODO 2", "title": "temperature (needs reasoning_effort=none on GPT-5.6)", "query": WHITE, "variants": [
            v("temperature=0.0", {"temperature": 0.0, "reasoning_effort": "none", "max_completion_tokens": 300}),
            v("temperature=2.0", {"temperature": 2.0, "reasoning_effort": "none", "max_completion_tokens": 300}),
        ]},
        {"todo": "TODO 3", "title": "top_p (needs reasoning_effort=none on GPT-5.6)", "query": PAPERCLIP, "variants": [
            v("top_p=0.1", {"top_p": 0.1, "reasoning_effort": "none", "max_completion_tokens": 300}),
            v("top_p=0.9", {"top_p": 0.9, "reasoning_effort": "none", "max_completion_tokens": 300}),
        ]},
        {"todo": "TODO 4", "title": "max_tokens / max_completion_tokens", "query": QUANTUM, "variants": [
            v("max_tokens=50 (gpt-4o)", {"max_tokens": 50}, model=OPENAI_CLASSIC_MODEL),
            v("max_tokens=2048 (gpt-4o)", {"max_tokens": 2048}, model=OPENAI_CLASSIC_MODEL),
            v("max_completion_tokens=50 (GPT-5.6)", {"max_completion_tokens": 50}),
        ]},
        {"todo": "TODO 5", "title": "stop", "query": COUNT, "variants": [
            v("stop=['5'] (gpt-4o)", {"stop": ["5"]}, model=OPENAI_CLASSIC_MODEL),
        ]},
        {"todo": "TODO 6", "title": "response_format (json_schema)", "query": LANGUAGES, "variants": [
            v("response_format=json_schema", {"response_format": {
                "type": "json_schema",
                "json_schema": {"name": "languages", "strict": True, "schema": OPENAI_LANGUAGES_SCHEMA}},
                "max_completion_tokens": 1000}),
        ]},
        {"todo": "TODO 7", "title": "frequency_penalty", "query": OCEAN, "variants": [
            v("frequency_penalty=0.0 (gpt-4o)", {"frequency_penalty": 0.0}, model=OPENAI_CLASSIC_MODEL),
            v("frequency_penalty=1.5 (gpt-4o)", {"frequency_penalty": 1.5}, model=OPENAI_CLASSIC_MODEL),
        ]},
        {"todo": "TODO 8", "title": "presence_penalty", "query": OCEAN, "variants": [
            v("presence_penalty=0.0 (gpt-4o)", {"presence_penalty": 0.0}, model=OPENAI_CLASSIC_MODEL),
            v("presence_penalty=1.5 (gpt-4o)", {"presence_penalty": 1.5}, model=OPENAI_CLASSIC_MODEL),
        ]},
        {"todo": "TODO 9", "title": "seed", "query": COFFEE, "variants": [
            v("seed=42 (run 1, gpt-4o)", {"seed": 42}, model=OPENAI_CLASSIC_MODEL),
            v("seed=42 (run 2, gpt-4o)", {"seed": 42}, model=OPENAI_CLASSIC_MODEL),
        ]},
        {"todo": "TODO 10", "title": "reasoning_effort", "query": STRAWBERRY, "variants": [
            v("reasoning_effort=low", {"reasoning_effort": "low", "max_completion_tokens": 2000}),
            v("reasoning_effort=high", {"reasoning_effort": "high", "max_completion_tokens": 4000}),
        ]},
    ],
    "openai_responses": [
        {"todo": "TODO 1", "title": "temperature (needs reasoning effort none on GPT-5.6)", "query": COFFEE, "variants": [
            v("temperature=0.0", {"temperature": 0.0, "reasoning": {"effort": "none"}}),
            v("temperature=2.0", {"temperature": 2.0, "reasoning": {"effort": "none"}}),
        ]},
        {"todo": "TODO 2", "title": "top_p (needs reasoning effort none on GPT-5.6)", "query": PAPERCLIP, "variants": [
            v("top_p=0.1", {"top_p": 0.1, "reasoning": {"effort": "none"}}),
            v("top_p=0.9", {"top_p": 0.9, "reasoning": {"effort": "none"}}),
        ]},
        {"todo": "TODO 3", "title": "max_output_tokens", "query": QUANTUM, "variants": [
            v("max_output_tokens=50", {"max_output_tokens": 50}),
            v("max_output_tokens=2048", {"max_output_tokens": 2048}),
        ]},
        {"todo": "TODO 4", "title": "text (structured output)", "query": LANGUAGES, "variants": [
            v("text.format=json_schema", {"text": {"format": {
                "type": "json_schema", "name": "languages", "strict": True, "schema": OPENAI_LANGUAGES_SCHEMA}}}),
        ]},
        {"todo": "TODO 5", "title": "truncation", "query": COFFEE, "variants": [
            v("truncation=auto", {"truncation": "auto"}, full=True),
        ]},
        {"todo": "TODO 6", "title": "metadata", "query": COFFEE, "variants": [
            v("metadata={project: demo, user: student-1}", {"metadata": {"project": "demo", "user": "student-1"}},
              full=True),
        ]},
        {"todo": "TODO 7", "title": "reasoning", "query": STRAWBERRY, "variants": [
            v("reasoning.effort=low", {"reasoning": {"effort": "low"}}),
            v("reasoning.effort=high", {"reasoning": {"effort": "high"}}),
        ]},
    ],
    "anthropic": [
        {"todo": "TODO 1", "title": "temperature", "query": COFFEE, "variants": [
            v("temperature=0.0", {"temperature": 0.0}),
            v("temperature=1.0", {"temperature": 1.0}),
        ]},
        {"todo": "TODO 2", "title": "top_p", "query": PAPERCLIP, "variants": [
            v("top_p=0.1", {"top_p": 0.1}),
            v("top_p=0.9", {"top_p": 0.9}),
        ]},
        {"todo": "TODO 3", "title": "top_k", "query": ROBOT, "variants": [
            v("top_k=1", {"top_k": 1}),
            v("top_k=50", {"top_k": 50}),
        ]},
        {"todo": "TODO 4", "title": "stop_sequences", "query": COUNT, "variants": [
            v("stop_sequences=['10']", {"stop_sequences": ["10"]}),
        ]},
        {"todo": "TODO 5", "title": "output_config (structured output)", "query": LANGUAGES, "variants": [
            v("output_config=json_schema", {"output_config": {"format": {"type": "json_schema", "schema": {
                "type": "object", "additionalProperties": False,
                "properties": {"languages": {"type": "array", "items": {
                    "type": "object", "additionalProperties": False,
                    "properties": {"name": {"type": "string"}, "year": {"type": "integer"}},
                    "required": ["name", "year"]}}}}}}}),
        ]},
        {"todo": "TODO 6", "title": "thinking", "query": STRAWBERRY, "variants": [
            v("thinking enabled, budget_tokens=5000", {"thinking": {"type": "enabled", "budget_tokens": 5000},
                                                       "max_tokens": 8000}),
        ]},
    ],
}


def make_client(provider: str, model: str | None):
    if provider == "gemini":
        from t2_llms_output_tuning._clients.gemini_client import GeminiAIClient
        return GeminiAIClient(model or GEMINI_FLASH_MODEL)
    if provider == "openai_chat":
        from t2_llms_output_tuning._clients.openai_chat_completions_client import OpenAIChatCompletionsClient
        return OpenAIChatCompletionsClient(model or OPENAI_TERRA_MODEL)
    if provider == "openai_responses":
        from t2_llms_output_tuning._clients.openai_responses_client import OpenAIResponsesClient
        return OpenAIResponsesClient(model or OPENAI_TERRA_MODEL)
    if provider == "anthropic":
        from t2_llms_output_tuning._clients.anthropic_client import AnthropicAIClient
        return AnthropicAIClient(model or ANTHROPIC_HAIKU_MODEL)
    raise SystemExit(f"Unknown provider '{provider}'. Choose from: {', '.join(EXPERIMENTS)}")


# Long answers do not fit into one screenshot, so only the first lines are shown. Use --full to see everything.
MAX_LINES = 10


def run_group(provider: str, group: dict, show_full: bool = False) -> None:
    print("\n" + "#" * 100)
    print(f"# {provider} | {group['todo']}: {group['title']}")
    print(f"# Query: \"{group['query']}\"")
    print("#" * 100)
    for variant in group["variants"]:
        for _ in range(variant["repeat"]):
            client = make_client(provider, variant["model"])
            print(f"\n>>> {variant['label']}")
            print(f"    params: {json.dumps(variant['params'])}")
            buffer = io.StringIO()
            try:
                with contextlib.redirect_stdout(buffer):
                    message = client.response(
                        messages=[Message(Role.USER, group["query"])],
                        print_request=False,
                        print_only_content=not variant["full"],
                        **variant["params"],
                    )
            except Exception as e:
                print(f"    ERROR: {str(e)[:600]}")
                continue

            # Drop the "=== RESPONSE ===" banners printed by the client and trim long output
            lines = [l for l in buffer.getvalue().splitlines() if not l.startswith("=" * 20)]
            limit = group.get("max_lines", MAX_LINES) * (4 if variant["full"] else 1)
            if not message.content.strip() and not variant["full"]:
                print("    <empty response: the token limit was reached while the model was still thinking>")
                continue
            for line in (lines if show_full else lines[:limit]):
                print("    " + line)
            if not show_full and len(lines) > limit:
                print(f"    ... ({len(lines) - limit} more lines hidden, run with --full to see all)")


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--full"]
    show_full = "--full" in sys.argv
    if not args or args[0] not in EXPERIMENTS:
        raise SystemExit(__doc__)
    provider = args[0]
    groups = EXPERIMENTS[provider]
    if len(args) > 1:
        groups = [groups[int(args[1]) - 1]]
    for i, group in enumerate(groups):
        run_group(provider, group, show_full)
        if i < len(groups) - 1:
            input("\n[Take a screenshot now, then press Enter for the next experiment] ")


if __name__ == "__main__":
    main()
