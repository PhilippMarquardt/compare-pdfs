"""
Global page analysis service.

Reads strict checklist definitions from templates/global_analysis.md, sends both
page images to GPT, and returns structured pass/unclear/fail semantics via
ok/maybe/issue statuses.
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
BULLET_RE = re.compile(r"^\s*[-*]\s*(?:\[\s*\]\s*)?(.+?)\s*$")


def _parse_checklist_block(text: str, block_name: str) -> list[str]:
    items: list[str] = []
    invalid_lines: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = BULLET_RE.match(raw_line)
        if not match:
            invalid_lines.append(line)
            continue
        item = match.group(1).strip()
        if item:
            items.append(item)

    if invalid_lines:
        preview = ", ".join(invalid_lines[:3])
        raise ValueError(
            f'{block_name} must contain only bullet checklist items. Invalid lines: {preview}'
        )

    if not items:
        raise ValueError(f"{block_name} must contain at least one bullet checklist item.")

    return items


def parse_global_template(text: str) -> list[tuple[str, list[str]]]:
    parts = re.split(r"^### ", text, flags=re.MULTILINE)
    checks: list[tuple[str, list[str]]] = []

    for part in parts[1:]:
        chunk = part.strip()
        if not chunk:
            continue
        lines = chunk.split("\n", 1)
        check_name = lines[0].strip()
        check_body = lines[1].strip() if len(lines) > 1 else ""
        if not check_name:
            continue
        items = _parse_checklist_block(check_body, f'Global check "{check_name}"')
        checks.append((check_name, items))

    if not checks:
        raise ValueError("Global analysis template must contain at least one '### <Check Name>' block.")

    return checks


def validate_global_template_file() -> None:
    if not TEMPLATE_PATH.exists():
        raise ValueError("Global analysis template file is missing.")
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    parse_global_template(text)


def _render_checklist(checks: list[tuple[str, list[str]]]) -> str:
    lines: list[str] = []
    for check_name, items in checks:
        lines.append(f"### {check_name}")
        lines += [f"- {item}" for item in items]
        lines.append("")
    return "\n".join(lines).strip()


def _load_template() -> tuple[list[str], str]:
    if not TEMPLATE_PATH.exists():
        raise ValueError("Global analysis template file is missing.")
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    checks = parse_global_template(text)
    check_names = [name for name, _ in checks]
    checklist_text = _render_checklist(checks)
    return check_names, checklist_text


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
1) A reference page image
2) A test page image
3) A checklist grouped by check name and bullet criteria

Return exactly one output object per check_name.
Evaluate all bullet criteria under each check_name before setting status.

Status rules:
- ok: all criteria clearly satisfied
- issue: any criterion clearly violated
- maybe: evidence is insufficient to decide

Never return ok if your explanation indicates missing content, mismatches, or failed criteria.
Write concise factual explanations (1-2 sentences) and explicitly state whether criteria are satisfied."""


async def analyze_page_global(
    ref_path: str, test_path: str, page_num: int,
) -> GlobalPageAnalysis:
    """Run global checks on a single page pair."""
    import asyncio

    check_names, checklist_text = _load_template()

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
        {"type": "text", "text": f"=== CHECKLIST ===\n{checklist_text}"},
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
    for check in parsed.get("checks", []):
        status = check.get("status", "maybe")
        if status not in ("ok", "maybe", "issue"):
            status = "maybe"
        checks.append(
            GlobalCheckResult(
                check_name=check.get("check_name", "Unknown"),
                status=status,
                explanation=check.get("explanation", ""),
            )
        )

    return GlobalPageAnalysis(page_number=page_num, checks=checks)
