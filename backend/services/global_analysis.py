"""
Global page analysis service.

Reads check definitions from templates/global_analysis.md, sends both page images
to GPT, returns structured ok/maybe/issue verdicts per check.
"""

import base64
import json
import logging
import re
from pathlib import Path
from typing import Any

from ..models import GlobalCheckResult, GlobalPageAnalysis
from .paired_sections import _get_client, _render_page_image

logger = logging.getLogger(__name__)

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "global_analysis.md"

MODEL_NAME = "gpt-4.1"
TEMPERATURE = 0
TOP_P = 1
SEED = 12345
MAX_TOKENS = 4096


def _load_template() -> tuple[str, list[str]]:
    """Load the template and extract check names from ### headings."""
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    check_names = re.findall(r"^### (.+)$", text, re.MULTILINE)
    return text, check_names


def _build_schema(check_names: list[str]) -> dict[str, Any]:
    return {
        "name": "global_analysis",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "checks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "check_name": {
                                "type": "string",
                                "enum": check_names,
                            },
                            "status": {
                                "type": "string",
                                "enum": ["ok", "maybe", "issue"],
                            },
                            "explanation": {
                                "type": "string",
                                "maxLength": 500,
                            },
                        },
                        "required": ["check_name", "status", "explanation"],
                    },
                },
            },
            "required": ["checks"],
        },
    }


SYSTEM_PROMPT = """You are a QA analyst comparing two versions of a financial report page.

You will receive:
1) A reference page image (the correct/expected version)
2) A test page image (the version to verify)
3) A checklist of items to verify

For each check, respond with:
- "ok" — no issues found
- "maybe" — minor concern or ambiguous, worth reviewing
- "issue" — clear problem detected

Be concise in explanations (1-2 sentences). Focus on factual observations, not speculation."""


async def analyze_page_global(
    ref_path: str, test_path: str, page_num: int,
) -> GlobalPageAnalysis:
    """Run global checks on a single page pair."""
    import asyncio

    template_text, check_names = _load_template()

    ref_image, test_image = await asyncio.gather(
        asyncio.to_thread(_render_page_image, ref_path, page_num),
        asyncio.to_thread(_render_page_image, test_path, page_num),
    )

    client = _get_client()

    b64_ref = base64.b64encode(ref_image).decode("ascii")
    b64_test = base64.b64encode(test_image).decode("ascii")

    user_content: list[dict[str, Any]] = [
        {"type": "text", "text": "=== REFERENCE PAGE ==="},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_ref}"}},
        {"type": "text", "text": "=== TEST PAGE ==="},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_test}"}},
        {"type": "text", "text": f"=== CHECKLIST ===\n{template_text}"},
    ]

    schema = _build_schema(check_names)

    kwargs: dict[str, Any] = dict(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=TEMPERATURE,
        top_p=TOP_P,
        max_tokens=MAX_TOKENS,
        seed=SEED,
        response_format={"type": "json_schema", "json_schema": schema},
    )

    try:
        resp = await client.chat.completions.create(**kwargs)
    except TypeError:
        kwargs.pop("response_format", None)
        kwargs.pop("seed", None)
        resp = await client.chat.completions.create(**kwargs)

    raw = (resp.choices[0].message.content or "{}").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

    parsed = json.loads(raw)

    checks = []
    for c in parsed.get("checks", []):
        status = c.get("status", "maybe")
        if status not in ("ok", "maybe", "issue"):
            status = "maybe"
        checks.append(GlobalCheckResult(
            check_name=c.get("check_name", "Unknown"),
            status=status,
            explanation=c.get("explanation", ""),
        ))

    return GlobalPageAnalysis(page_number=page_num, checks=checks)
