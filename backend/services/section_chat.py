"""
Section chat: free-form GPT conversation about a specific section,
prompted with cropped images from both PDFs and pdfplumber element data.
"""

import asyncio
import base64
import json
import logging
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz

from . import analysis_store
from .paired_sections import _get_client, _render_page_image, SCALE
from .section_analysis import _crop_section
from .page_map import extract_page_map
from .section_instructions import get_instructions_for_section

logger = logging.getLogger(__name__)

UPLOADS_DIR = Path(__file__).resolve().parent.parent / "uploads"
MODEL_NAME = "gpt-4.1"
MAX_TOKENS = 4096

SYSTEM_PROMPT = """You are a helpful assistant analyzing sections of financial report PDFs.

You are given:
- Cropped images of a section from a reference PDF and a test PDF
- Structured element data (text content, bounding boxes) for elements within this section
- Section-specific analysis instructions (if available)
- A user question or message about this section

The pages may represent different points in time, so data values (numbers, dates, percentages) are expected to differ.

Answer the user's question based on what you see in the images and the element data provided. Be concise and factual."""

FUZZY_THRESHOLD = 75


def _find_section(analysis, section_name: str):
    """Find a section by name in a PageAnalysis, with fuzzy fallback."""
    if not analysis:
        return None
    for s in analysis.sections:
        if s.name == section_name:
            return s
    # Fuzzy fallback
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


def _build_user_content(
    section_name: str,
    ref_crop: bytes | None,
    test_crop: bytes | None,
    ref_elements: list[dict],
    test_elements: list[dict],
    instructions: dict,
    message: str,
) -> list[dict[str, Any]]:
    """Build the multipart user content for GPT."""
    content: list[dict[str, Any]] = [
        {"type": "text", "text": f'Section: "{section_name}"'},
    ]

    if ref_crop:
        b64 = base64.b64encode(ref_crop).decode("ascii")
        content.append({"type": "text", "text": "=== REFERENCE IMAGE ==="})
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})

    if test_crop:
        b64 = base64.b64encode(test_crop).decode("ascii")
        content.append({"type": "text", "text": "=== TEST IMAGE ==="})
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})

    if ref_elements:
        content.append({
            "type": "text",
            "text": f"=== REFERENCE ELEMENT DATA ===\n{json.dumps(ref_elements, indent=2)}",
        })

    if test_elements:
        content.append({
            "type": "text",
            "text": f"=== TEST ELEMENT DATA ===\n{json.dumps(test_elements, indent=2)}",
        })

    # Add instructions
    generic = instructions.get("generic", "")
    specific = instructions.get("instructions", "")
    if generic or specific:
        instruction_text = ""
        if generic:
            instruction_text += f"=== GENERAL INSTRUCTIONS ===\n{generic}\n\n"
        if specific:
            label = "SECTION-SPECIFIC INSTRUCTIONS" if instructions.get("matched") else "DEFAULT INSTRUCTIONS"
            instruction_text += f"=== {label} ===\n{specific}"
        content.append({"type": "text", "text": instruction_text})

    content.append({"type": "text", "text": f"=== USER MESSAGE ===\n{message}"})

    return content


async def chat_with_section(
    job_id: str,
    pair_id: str,
    filename: str,
    section_name: str,
    page: int,
    message: str,
) -> str:
    """Send a free-form chat message about a section to GPT."""
    ref_path = str(UPLOADS_DIR / job_id / "reference" / filename)
    test_path = str(UPLOADS_DIR / job_id / "test" / filename)

    # Get section data from analysis store
    ref_analysis = analysis_store.get(job_id, pair_id, "reference", page)
    test_analysis = analysis_store.get(job_id, pair_id, "test", page)

    ref_section = _find_section(ref_analysis, section_name)
    test_section = _find_section(test_analysis, section_name)

    # Render both page images
    ref_image, test_image = await asyncio.gather(
        asyncio.to_thread(_render_page_image, ref_path, page),
        asyncio.to_thread(_render_page_image, test_path, page),
    )

    # Crop sections
    ref_crop = _crop_section(ref_image, ref_section.bbox) if ref_section else None
    test_crop = _crop_section(test_image, test_section.bbox) if test_section else None

    # Get element data
    ref_map = await asyncio.to_thread(extract_page_map, ref_path, page)
    test_map = await asyncio.to_thread(extract_page_map, test_path, page)

    ref_elements = _filter_elements(ref_map, ref_section)
    test_elements = _filter_elements(test_map, test_section)

    # Get instructions
    instructions = get_instructions_for_section(section_name)

    # Build and send GPT request
    user_content = _build_user_content(
        section_name, ref_crop, test_crop,
        ref_elements, test_elements, instructions, message,
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
