"""
Per-section comparison analysis.

Crops section regions from page images and sends to GPT for comparison.
Returns a list of checks per section.
"""

import base64
import io
import json
import logging
from typing import Any

from PIL import Image

from ..models import CheckStatus, SectionCheck, SectionCheckResult
from .paired_sections import SCALE, _get_client
from .section_instructions import get_instructions_for_section

logger = logging.getLogger(__name__)

MODEL_NAME = "gpt-4.1"
TEMPERATURE = 0
TOP_P = 1
SEED = 12345
MAX_TOKENS = 4096

SYSTEM_PROMPT = """You compare two cropped section images from a financial report: a reference version and a test version.

The pages may represent different points in time, so data values (numbers, dates, percentages) are EXPECTED to differ. Do NOT flag value differences as issues.

You will receive checklists as bullet items. Treat EACH bullet item as one required check.
Evaluate every checklist bullet before deciding status.

For each check, report:
- "check_name": short label for what was checked (3-5 words)
- "status": "ok", "maybe", or "issue"
- "explanation": brief factual observation (1-2 sentences)

Status rules:
- ok: checklist criterion is clearly satisfied
- issue: checklist criterion is clearly violated
- maybe: evidence is insufficient to decide

Never return "ok" if explanation says missing content, mismatch, failed criterion, or unclear evidence.
Return all checks as a list. Be concise and factual."""

SECTION_SCHEMA: dict[str, Any] = {
    "name": "section_checks",
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
                        "check_name": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": ["ok", "maybe", "issue"],
                        },
                        "explanation": {"type": "string"},
                    },
                    "required": ["check_name", "status", "explanation"],
                },
            },
        },
        "required": ["checks"],
    },
}


def _crop_section(page_png: bytes, bbox: list[float]) -> bytes:
    """Crop a section region from a full page PNG image."""
    img = Image.open(io.BytesIO(page_png))
    pixel_bbox = (
        int(bbox[0] * SCALE),
        int(bbox[1] * SCALE),
        int(bbox[2] * SCALE),
        int(bbox[3] * SCALE),
    )
    pixel_bbox = (
        max(0, pixel_bbox[0]),
        max(0, pixel_bbox[1]),
        min(img.width, pixel_bbox[2]),
        min(img.height, pixel_bbox[3]),
    )
    cropped = img.crop(pixel_bbox)
    buf = io.BytesIO()
    cropped.save(buf, format="PNG")
    return buf.getvalue()


def _render_numbered_items(items: list[str]) -> str:
    return "\n".join(f"{i}. {item}" for i, item in enumerate(items, start=1))


async def analyze_section(
    ref_crop: bytes,
    test_crop: bytes,
    section_name: str,
) -> SectionCheckResult:
    """Compare two cropped section images using GPT. Returns multiple checks."""
    instructions = get_instructions_for_section(section_name)
    generic_items = instructions["generic_items"]
    specific_items = instructions["specific_items"]
    matched = instructions["matched"]

    instruction_text_parts: list[str] = []
    if generic_items:
        instruction_text_parts.append(
            "=== GENERAL CHECKLIST ===\n"
            f"{_render_numbered_items(generic_items)}"
        )
    if specific_items:
        label = "SECTION-SPECIFIC CHECKLIST" if matched else "DEFAULT CHECKLIST"
        instruction_text_parts.append(
            f"=== {label} ===\n"
            f"{_render_numbered_items(specific_items)}"
        )
    instruction_text = "\n\n".join(instruction_text_parts)

    client = _get_client()

    b64_ref = base64.b64encode(ref_crop).decode("ascii")
    b64_test = base64.b64encode(test_crop).decode("ascii")

    user_content: list[dict[str, Any]] = [
        {"type": "text", "text": f'Section: "{section_name}"'},
        {"type": "text", "text": "=== REFERENCE ==="},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_ref}"}},
        {"type": "text", "text": "=== TEST ==="},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_test}"}},
    ]
    if instruction_text:
        user_content.append({"type": "text", "text": instruction_text})

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
        response_format={"type": "json_schema", "json_schema": SECTION_SCHEMA},
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
    checks_raw = parsed.get("checks", [])

    checks = []
    for c in checks_raw:
        status = c.get("status", "maybe")
        if status not in ("ok", "maybe", "issue"):
            status = "maybe"
        checks.append(
            SectionCheck(
                check_name=c.get("check_name", "Check"),
                status=CheckStatus(status),
                explanation=c.get("explanation", ""),
            )
        )

    return SectionCheckResult(
        section_name=section_name,
        checks=checks,
        matched_instructions=matched,
    )
