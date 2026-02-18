"""
Section chat: grounded GPT conversation about a specific section.

Provides:
- chat response based on reference/test section crops and extracted text elements
- context payload for UI (data URLs + short text excerpts)
"""

import asyncio
import base64
import json
import logging
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz

from . import analysis_store
from .page_map import extract_page_map
from .paired_sections import _get_client, _render_page_image
from .section_analysis import _crop_section

logger = logging.getLogger(__name__)

UPLOADS_DIR = Path(__file__).resolve().parent.parent / "uploads"
MODEL_NAME = "gpt-4.1"
MAX_TOKENS = 4096

SYSTEM_PROMPT = """You are analyzing one section from two report versions.

You receive:
- an old/reference section image
- a new/test section image
- extracted text grounding for both versions
- a user question

Answer carefully using only these images and grounded text.
If evidence is insufficient, state that clearly instead of guessing."""

FUZZY_THRESHOLD = 75


def _find_section(analysis, section_name: str):
    """Find a section by name in a PageAnalysis, with fuzzy fallback."""
    if not analysis:
        return None
    for s in analysis.sections:
        if s.name == section_name:
            return s

    best_score = 0
    best_section = None
    for s in analysis.sections:
        score = fuzz.WRatio(section_name, s.name)
        if score > best_score:
            best_score = score
            best_section = s
    if best_score >= FUZZY_THRESHOLD and best_section:
        return best_section
    return None


def _filter_elements(page_map: dict, section) -> list[dict]:
    """Filter page_map elements to those belonging to a section."""
    if not section or not page_map:
        return []
    ids = set(section.element_ids)
    return [
        {"id": el["id"], "type": el["type"], "bbox": el["bbox"], "content": el.get("content")}
        for el in page_map.get("elements", [])
        if el["id"] in ids
    ]


def _to_data_url(image_bytes: bytes | None) -> str | None:
    if not image_bytes:
        return None
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _build_text_excerpt(elements: list[dict]) -> str:
    lines: list[str] = []
    for el in elements:
        content = (el.get("content") or "").strip()
        if content:
            lines.append(content)
    return "\n".join(lines).strip()


async def _collect_section_context(
    job_id: str,
    pair_id: str,
    filename: str,
    section_name: str,
    page: int,
) -> dict[str, Any]:
    """Collect section crops and element grounding for ref/test."""
    ref_path = str(UPLOADS_DIR / job_id / "reference" / filename)
    test_path = str(UPLOADS_DIR / job_id / "test" / filename)

    ref_analysis = analysis_store.get(job_id, pair_id, "reference", page)
    test_analysis = analysis_store.get(job_id, pair_id, "test", page)

    ref_section = _find_section(ref_analysis, section_name)
    test_section = _find_section(test_analysis, section_name)

    ref_image, test_image = await asyncio.gather(
        asyncio.to_thread(_render_page_image, ref_path, page),
        asyncio.to_thread(_render_page_image, test_path, page),
    )

    ref_crop = _crop_section(ref_image, ref_section.bbox) if ref_section else None
    test_crop = _crop_section(test_image, test_section.bbox) if test_section else None

    ref_map = await asyncio.to_thread(extract_page_map, ref_path, page)
    test_map = await asyncio.to_thread(extract_page_map, test_path, page)

    ref_elements = _filter_elements(ref_map, ref_section)
    test_elements = _filter_elements(test_map, test_section)

    return {
        "ref_crop": ref_crop,
        "test_crop": test_crop,
        "ref_elements": ref_elements,
        "test_elements": test_elements,
    }


def _build_user_content(
    section_name: str,
    ref_crop: bytes | None,
    test_crop: bytes | None,
    ref_elements: list[dict],
    test_elements: list[dict],
    message: str,
) -> list[dict[str, Any]]:
    """Build multipart user content for grounded section chat."""
    content: list[dict[str, Any]] = [{"type": "text", "text": f'Section: "{section_name}"'}]

    if ref_crop:
        b64 = base64.b64encode(ref_crop).decode("ascii")
        content.append({"type": "text", "text": "=== OLD / REFERENCE IMAGE ==="})
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})

    if test_crop:
        b64 = base64.b64encode(test_crop).decode("ascii")
        content.append({"type": "text", "text": "=== NEW / TEST IMAGE ==="})
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})

    if ref_elements:
        content.append({
            "type": "text",
            "text": f"=== OLD / REFERENCE TEXT GROUNDING ===\n{json.dumps(ref_elements, ensure_ascii=False)}",
        })

    if test_elements:
        content.append({
            "type": "text",
            "text": f"=== NEW / TEST TEXT GROUNDING ===\n{json.dumps(test_elements, ensure_ascii=False)}",
        })

    content.append({"type": "text", "text": f"=== USER QUESTION ===\n{message}"})
    return content


async def get_section_chat_context(
    job_id: str,
    pair_id: str,
    filename: str,
    section_name: str,
    page: int,
) -> dict[str, str | None]:
    """Return UI context for section chat modal (top image comparison + short text grounding)."""
    context = await _collect_section_context(job_id, pair_id, filename, section_name, page)
    ref_elements = context["ref_elements"]
    test_elements = context["test_elements"]

    return {
        "reference_image_data_url": _to_data_url(context["ref_crop"]),
        "test_image_data_url": _to_data_url(context["test_crop"]),
        "reference_text_excerpt": _build_text_excerpt(ref_elements),
        "test_text_excerpt": _build_text_excerpt(test_elements),
    }


async def chat_with_section(
    job_id: str,
    pair_id: str,
    filename: str,
    section_name: str,
    page: int,
    message: str,
) -> str:
    """Send a grounded chat message about a section to GPT."""
    context = await _collect_section_context(job_id, pair_id, filename, section_name, page)

    user_content = _build_user_content(
        section_name=section_name,
        ref_crop=context["ref_crop"],
        test_crop=context["test_crop"],
        ref_elements=context["ref_elements"],
        test_elements=context["test_elements"],
        message=message,
    )

    client = _get_client()
    resp = await client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        max_tokens=MAX_TOKENS,
    )
    return resp.choices[0].message.content or ""
