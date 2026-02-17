"""
Paired GPT section analysis service.

Exact copy of experiment_gpt_v5.py logic, converted to async for FastAPI.
Pipeline: resolve_overlaps → assign_elements → recompute regions → drop empty → sort.
"""

import base64
import json
import logging
import os
import ssl
from typing import Any

import fitz
import httpx
from openai import AsyncOpenAI

from ..models import PageAnalysis, Section
from .page_map import extract_page_map

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

RENDER_DPI = 300
SCALE = RENDER_DPI / 72

MODEL_NAME = "gpt-4.1"  # overridden by AZURE_OPENAI_DEPLOYMENT after dotenv load
TEMPERATURE = 0
TOP_P = 1
SEED = 12345
MAX_TOKENS = 16384

ALLOWED_CONTENT_TYPES = {"table", "chart", "text_block", "metadata", "mixed"}

_client: AsyncOpenAI | None = None


class StripAuthTransport(httpx.AsyncHTTPTransport):
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        request.headers.pop("authorization", None)
        return await super().handle_async_request(request)


def _get_client() -> AsyncOpenAI:
    global _client, MODEL_NAME
    if _client is None:
        from dotenv import load_dotenv
        env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
        load_dotenv(env_path)

        if os.environ.get("AZURE_OPENAI_ENDPOINT"):
            endpoint = os.environ["AZURE_OPENAI_ENDPOINT"].rstrip("/")
            deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT")
            if not deployment:
                raise RuntimeError("AZURE_OPENAI_DEPLOYMENT is required when AZURE_OPENAI_ENDPOINT is set")

            MODEL_NAME = deployment
            api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

            cert_path = os.environ.get("CLIENT_CERT_PATH")
            key_path = os.environ.get("CLIENT_KEY_PATH")
            if not cert_path or not key_path:
                raise RuntimeError("CLIENT_CERT_PATH and CLIENT_KEY_PATH are required for Azure mTLS mode")

            key_password = os.environ.get("CLIENT_KEY_PASSWORD") or None
            ca_path = os.environ.get("CA_CERT_PATH")

            ssl_context = ssl.create_default_context(cafile=ca_path) if ca_path else ssl.create_default_context()
            ssl_context.load_cert_chain(
                certfile=cert_path,
                keyfile=key_path,
                password=key_password,
            )

            transport = StripAuthTransport(verify=ssl_context)
            http_client = httpx.AsyncClient(
                transport=transport,
                timeout=30.0,
            )

            _client = AsyncOpenAI(
                base_url=f"{endpoint}/openai/deployments/{deployment}",
                http_client=http_client,
                api_key="nothing",
                default_query={"api-version": api_version},
            )
        else:
            # Direct OpenAI
            _client = AsyncOpenAI(api_key=os.environ["OPENAI_KEY"])
    return _client


# ---------------------------------------------------------------------------
# GPT prompt — identical to experiment_gpt_v5.py
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You segment TWO versions of the SAME financial report page into non-overlapping section REGIONS.

You receive layout blocks for BOTH pages (reference and test). They share the same report layout but may differ in data values or have sections added/removed.

Return TWO separate sets of section regions using CONSISTENT names across both pages so matching sections can be paired.

INPUT:
1) Reference page image (PNG)
2) Reference page map (JSON) — elements already merged into blocks with id, bbox, content
3) Test page image (PNG)
4) Test page map (JSON) — elements already merged into blocks with id, bbox, content

OUTPUT — ONLY valid JSON matching the schema:
{"ref_sections":[{"name":"...","content_type":"...","region":[x0,y0,x1,y1]}],
 "test_sections":[{"name":"...","content_type":"...","region":[x0,y0,x1,y1]}]}

content_type: "table" | "chart" | "text_block" | "metadata" | "mixed"

────────────────────────────────────────
CORE STRUCTURE RULES
────────────────────────────────────────

1) HEADER (optional)
   - ALL top-of-page metadata elements — logo, portfolio/fund name, report date, subtitle, classification label — belong in ONE "Header" region, content_type "metadata"
   - These elements are often spread across the full width (logo left, date right) but MUST be grouped into a single region
   - The header region ends where the first real content headline begins
   - Must NOT include the first real content headline or section
   - Only include if visually present — do NOT invent a header
   - NEVER combine header metadata with actual content sections below it — they are always separate regions
   - If a full-width horizontal line appears below the header, everything below that line is NOT part of the header DONT MERGE THAT
   - If the page map includes "header_separator_y", the header region MUST NOT extend below that y-coordinate — it marks a detected horizontal divider line
   - Often just a single word

2) SECTION SEGMENTATION
   - A headline + ALL content blocks under it (until the next headline) = ONE region.
   - The region includes the headline, plus every chart, table, and text block that belongs to it.
   - A section ends immediately before the next headline.
   - Example: "ESG score" heading + score chart + explanation text = ONE region named "ESG score"

3) WITHIN A SECTION REGION
   - A region may contain a headline + one or more charts, tables, text blocks.
   - NEVER merge content from TWO different headlines into one region.

4) FOOTER (optional)
   - Bottom page number / branding / legal text is ONE region, content_type "metadata"
   - Only include if clearly present — do NOT invent a footer

────────────────────────────────────────
TEXT PARAGRAPH HANDLING (CRITICAL)
────────────────────────────────────────

A) A headline followed by any combination of content (charts, tables, text)
   with NO sub-headlines in between:
   → ALL of it is ONE region. Name it after the headline.

B) If sub-headlines appear under a main headline:
   → Each sub-headline + its content = its own region.
   → The main headline belongs to its own region only if it has content before the first sub-headline.

C) Sub-headlines must NOT be merged into the previous section's text.
   A sub-headline ALWAYS starts a new region.

D) Paragraphs separated only by whitespace but under the same headline
   must remain in the same text_block region.

E) Bullet lists or short stacked lines under the same headline
   count as ONE text_block region unless separated by a new sub-headline.

────────────────────────────────────────
LAYOUT RULES
────────────────────────────────────────

- Two-column layouts: each column element is its own region.
- Full-width sections: the region MUST span the full content width (left margin to right margin).
- Headings can appear to the LEFT of their content (not just above). Each heading-on-the-left + its right-side content is a SEPARATE horizontal band.
- A region MUST NOT extend ABOVE its own title/heading. Boxes above a title belong to the PREVIOUS region.
- Legends belong to their chart, not to a neighbouring table.

────────────────────────────────────────
STRICT RULES
────────────────────────────────────────

- Regions MUST NOT OVERLAP NEVER.
- Regions must be within page bounds [0..width] x [0..height].
- Every element id must end up in exactly one region (code assigns by centroid).
- Use the SAME name for matching sections across ref and test.
- If a section exists on one page but not the other, include it only in that page's set.

────────────────────────────────────────
NAMING
────────────────────────────────────────

- Short descriptive label based on the section's visible heading or content.
- Strip dates, fund/client names, unit qualifiers (e.g. "in %", "in CHF").
- If two sections would have the same name, add distinguishing context (e.g. "Portfolio table" vs "Benchmark table").
- The name MUST be unique on the page.
- Examples: "Header", "Footer", "ESG score & subscores heading", "ESG score & subscores chart", "Largest positions table"

NO OVERLAPS. Return ONLY valid JSON.
"""

_SECTION_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "name": {"type": "string", "minLength": 1, "maxLength": 200},
        "content_type": {"type": "string", "enum": sorted(list(ALLOWED_CONTENT_TYPES))},
        "region": {
            "type": "array",
            "minItems": 4,
            "maxItems": 4,
            "items": {"type": "number"},
        },
    },
    "required": ["name", "content_type", "region"],
}

SECTION_LAYOUT_SCHEMA: dict[str, Any] = {
    "name": "section_layout",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "ref_sections": {"type": "array", "items": _SECTION_ITEM_SCHEMA},
            "test_sections": {"type": "array", "items": _SECTION_ITEM_SCHEMA},
        },
        "required": ["ref_sections", "test_sections"],
    },
}

SINGLE_LAYOUT_SCHEMA: dict[str, Any] = {
    "name": "section_layout",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "sections": {"type": "array", "items": _SECTION_ITEM_SCHEMA},
        },
        "required": ["sections"],
    },
}

_RULES_SECTION = SYSTEM_PROMPT.split("────────────────────────────────────────\nCORE STRUCTURE RULES\n────────────────────────────────────────")[1]

SINGLE_SYSTEM_PROMPT = """You segment a financial report page into non-overlapping section REGIONS.

You receive ONE page with its image and layout map.

INPUT:
1) Page image (PNG)
2) Page map (JSON) — elements already merged into blocks with id, bbox, content

OUTPUT — ONLY valid JSON matching the schema:
{"sections":[{"name":"...","content_type":"...","region":[x0,y0,x1,y1]}]}

content_type: "table" | "chart" | "text_block" | "metadata" | "mixed"

────────────────────────────────────────
CORE STRUCTURE RULES
────────────────────────────────────────""" + _RULES_SECTION


# ---------------------------------------------------------------------------
# Geometry utilities — identical to v5
# ---------------------------------------------------------------------------

def _clip_region(region: list[float], w: float, h: float) -> list[float]:
    x0, y0, x1, y1 = [float(v) for v in region]
    x0 = max(0.0, min(x0, w))
    x1 = max(0.0, min(x1, w))
    y0 = max(0.0, min(y0, h))
    y1 = max(0.0, min(y1, h))
    if x1 < x0: x0, x1 = x1, x0
    if y1 < y0: y0, y1 = y1, y0
    return [x0, y0, x1, y1]


def _rect_intersection_area(a: list[float], b: list[float]) -> float:
    ix0, iy0 = max(a[0], b[0]), max(a[1], b[1])
    ix1, iy1 = min(a[2], b[2]), min(a[3], b[3])
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    return (ix1 - ix0) * (iy1 - iy0)


def _bbox_union(bboxes: list[list[float]]) -> list[float]:
    return [
        min(b[0] for b in bboxes),
        min(b[1] for b in bboxes),
        max(b[2] for b in bboxes),
        max(b[3] for b in bboxes),
    ]


def _contains_point(region: list[float], x: float, y: float) -> bool:
    return (region[0] <= x <= region[2]) and (region[1] <= y <= region[3])


def _centroid(bbox: list[float]) -> tuple[float, float]:
    return ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)


# ---------------------------------------------------------------------------
# Overlap resolver — identical to v5
# ---------------------------------------------------------------------------

def _resolve_overlaps(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # If two sections overlap, merge them into a single section
    # (union their regions, combine names, pick dominant content_type).
    out = [dict(s) for s in sections]
    changed = True
    while changed:
        changed = False
        i = 0
        while i < len(out):
            j = i + 1
            while j < len(out):
                if _rect_intersection_area(out[i]["region"], out[j]["region"]) > 0:
                    # Merge j into i
                    out[i]["region"] = _bbox_union([out[i]["region"], out[j]["region"]])
                    out[i]["name"] = out[i]["name"] + " + " + out[j]["name"]
                    # Prefer non-metadata content_type
                    if out[i]["content_type"] == "metadata":
                        out[i]["content_type"] = out[j]["content_type"]
                    elif out[j]["content_type"] != "metadata" and out[i]["content_type"] != out[j]["content_type"]:
                        out[i]["content_type"] = "mixed"
                    # Combine element_ids if present (critical for second resolve pass)
                    if "element_ids" in out[i] and "element_ids" in out[j]:
                        out[i]["element_ids"] = out[i]["element_ids"] + out[j]["element_ids"]
                    out.pop(j)
                    changed = True  # restart — merged region may now overlap others
                else:
                    j += 1
            i += 1
    return out


# ---------------------------------------------------------------------------
# Element assignment — identical to v5
# ---------------------------------------------------------------------------

def _assign_elements_to_sections(
    page_map: dict, sections: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    elements = page_map["elements"]
    if not sections:
        return [{"name": "Page", "content_type": "mixed",
                 "element_ids": [e["id"] for e in elements],
                 "region": [0, 0, page_map["width"], page_map["height"]]}]

    sec_out = [{**s, "element_ids": []} for s in sections]

    for el in elements:
        eid = el["id"]
        bx0, by0, bx1, by1 = map(float, el["bbox"])
        cx, cy = _centroid([bx0, by0, bx1, by1])

        containing = [si for si, s in enumerate(sec_out) if _contains_point(s["region"], cx, cy)]

        if containing:
            if len(containing) == 1:
                chosen = containing[0]
            else:
                best_si, best_key = None, None
                for si in containing:
                    inter = _rect_intersection_area(sec_out[si]["region"], [bx0, by0, bx1, by1])
                    key = (-inter, si)
                    if best_key is None or key < best_key:
                        best_key = key
                        best_si = si
                chosen = int(best_si)
        else:
            best_si, best_key = None, None
            for si, s in enumerate(sec_out):
                rx0, ry0, rx1, ry1 = s["region"]
                dy = 0.0 if (ry0 <= cy <= ry1) else min(abs(cy - ry0), abs(cy - ry1))
                dx = 0.0 if (rx0 <= cx <= rx1) else min(abs(cx - rx0), abs(cx - rx1))
                key = (dy * dy + dx * dx, si)
                if best_key is None or key < best_key:
                    best_key = key
                    best_si = si
            chosen = int(best_si)

        sec_out[chosen]["element_ids"].append(eid)

    # Dedup
    seen = set()
    for s in sec_out:
        uniq = []
        for eid in s["element_ids"]:
            if eid not in seen:
                uniq.append(eid)
                seen.add(eid)
        s["element_ids"] = uniq

    return sec_out


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _render_page_image(pdf_path: str, page_num: int) -> bytes:
    doc = fitz.open(pdf_path)
    page = doc[page_num - 1]
    pix = page.get_pixmap(matrix=fitz.Matrix(SCALE, SCALE))
    png = pix.tobytes("png")
    doc.close()
    return png


# ---------------------------------------------------------------------------
# GPT call (async) — identical to v5 logic
# ---------------------------------------------------------------------------

def _normalize_sections(raw_sections: list, w: float, h: float) -> list[dict[str, Any]]:
    norm: list[dict[str, Any]] = []
    for s in raw_sections:
        if not isinstance(s, dict):
            continue
        name = str(s.get("name", "")).strip()
        ctype = str(s.get("content_type", "mixed")).strip()
        region = s.get("region")
        if not name:
            continue
        if ctype not in ALLOWED_CONTENT_TYPES:
            ctype = "mixed"
        if not (isinstance(region, list) and len(region) == 4):
            continue
        r = _clip_region([float(x) for x in region], w, h)
        norm.append({"name": name[:200], "content_type": ctype, "region": r})
    norm.sort(key=lambda s: (s["region"][1], s["region"][0]))
    return norm


def _page_map_to_json(page_map: dict) -> str:
    """Convert page map to compact JSON for GPT, stripping internal fields."""
    compact: dict[str, Any] = {
        "width": page_map["width"],
        "height": page_map["height"],
        "elements": [],
    }
    if page_map.get("header_separator_y") is not None:
        compact["header_separator_y"] = page_map["header_separator_y"]
    for el in page_map["elements"]:
        entry: dict[str, Any] = {
            "id": el["id"],
            "bbox": el["bbox"],
        }
        if el.get("content"):
            entry["content"] = el["content"][:200]
        compact["elements"].append(entry)
    return json.dumps(compact, ensure_ascii=False)


async def _call_gpt_layout_paired(
    ref_page_map: dict, ref_image: bytes,
    test_page_map: dict, test_image: bytes,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    client = _get_client()

    user_content: list[dict[str, Any]] = []

    user_content.append({"type": "text", "text": "=== REFERENCE PAGE ==="})
    b64_ref = base64.b64encode(ref_image).decode("ascii")
    user_content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_ref}"}})
    user_content.append({"type": "text", "text": _page_map_to_json(ref_page_map)})

    user_content.append({"type": "text", "text": "=== TEST PAGE ==="})
    b64_test = base64.b64encode(test_image).decode("ascii")
    user_content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_test}"}})
    user_content.append({"type": "text", "text": _page_map_to_json(test_page_map)})

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
        response_format={"type": "json_schema", "json_schema": SECTION_LAYOUT_SCHEMA},
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
    w, h = float(ref_page_map["width"]), float(ref_page_map["height"])
    ref_sections = _normalize_sections(parsed.get("ref_sections", []), w, h)
    test_w, test_h = float(test_page_map["width"]), float(test_page_map["height"])
    test_sections = _normalize_sections(parsed.get("test_sections", []), test_w, test_h)
    return ref_sections, test_sections


async def _call_gpt_layout_single(
    page_map: dict, page_image: bytes,
) -> list[dict[str, Any]]:
    """Single-page GPT call — analyzes one page independently."""
    client = _get_client()

    user_content: list[dict[str, Any]] = []
    b64 = base64.b64encode(page_image).decode("ascii")
    user_content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
    user_content.append({"type": "text", "text": _page_map_to_json(page_map)})

    kwargs: dict[str, Any] = dict(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SINGLE_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=TEMPERATURE,
        top_p=TOP_P,
        max_tokens=MAX_TOKENS,
        seed=SEED,
        response_format={"type": "json_schema", "json_schema": SINGLE_LAYOUT_SCHEMA},
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
    w, h = float(page_map["width"]), float(page_map["height"])
    return _normalize_sections(parsed.get("sections", []), w, h)


# ---------------------------------------------------------------------------
# Apply layout to single page — identical to v5 pipeline
# ---------------------------------------------------------------------------

def _apply_layout_to_page(
    page_map: dict, layout: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Apply a layout: resolve overlaps, assign elements, recompute regions, drop empty."""
    layout_copy = [dict(s) for s in layout]

    # Clip header sections at detected separator line
    header_sep_y = page_map.get("header_separator_y")
    if header_sep_y is not None:
        for s in layout_copy:
            if s.get("content_type") == "metadata" and s["region"][1] < header_sep_y:
                # Header section — clip bottom to separator line
                if s["region"][3] > header_sep_y:
                    s["region"][3] = header_sep_y
                    logger.debug("Clipped header '%s' at separator y=%.1f", s["name"], header_sep_y)

    # Resolve any GPT overlaps
    layout_copy = _resolve_overlaps(layout_copy)

    # Assign elements to sections by centroid
    sections = _assign_elements_to_sections(page_map, layout_copy)

    # Recompute regions from assigned elements
    elements_by_id = {e["id"]: e for e in page_map["elements"]}
    for s in sections:
        if s["element_ids"]:
            bboxes = [list(map(float, elements_by_id[eid]["bbox"])) for eid in s["element_ids"] if eid in elements_by_id]
            if bboxes:
                s["region"] = _bbox_union(bboxes)

    # Resolve overlaps created by region recomputation
    sections = _resolve_overlaps(sections)

    # Drop empty sections
    sections = [s for s in sections if s.get("element_ids")]

    # Sort by reading order
    sections.sort(key=lambda s: (s["region"][1], s["region"][0]))

    return sections


# ---------------------------------------------------------------------------
# Bbox computation
# ---------------------------------------------------------------------------

def _compute_bbox(section: dict, elements_by_id: dict) -> list[float]:
    x0s, y0s, x1s, y1s = [], [], [], []
    for eid in section.get("element_ids", []):
        el = elements_by_id.get(eid)
        if el:
            b = el["bbox"]
            x0s.append(b[0]); y0s.append(b[1]); x1s.append(b[2]); y1s.append(b[3])
    if not x0s:
        return [0, 0, 0, 0]
    return [min(x0s), min(y0s), max(x1s), max(y1s)]


# ---------------------------------------------------------------------------
# Public API: analyze a page pair
# ---------------------------------------------------------------------------

async def analyze_page_pair(
    ref_path: str, test_path: str, page_num: int, mode: str = "paired",
) -> tuple[PageAnalysis, PageAnalysis]:
    """Analyze a single page from both ref and test PDFs.

    mode="paired": one GPT call with both pages (consistent naming).
    mode="single": two independent GPT calls (one per page).
    """
    import asyncio

    # Extract page maps and render images in parallel
    ref_map, test_map, ref_image, test_image = await asyncio.gather(
        asyncio.to_thread(extract_page_map, ref_path, page_num),
        asyncio.to_thread(extract_page_map, test_path, page_num),
        asyncio.to_thread(_render_page_image, ref_path, page_num),
        asyncio.to_thread(_render_page_image, test_path, page_num),
    )

    if mode == "elements":
        # Elements mode: show raw pdfplumber merged elements as sections (GPT input)
        def map_to_sections(page_map: dict) -> PageAnalysis:
            sections = []
            for el in page_map["elements"]:
                sections.append(Section(
                    name=f'{el["id"]}: {(el.get("content") or el["type"])[:60]}',
                    content_type=el["type"],
                    element_ids=[el["id"]],
                    bbox=el["bbox"],
                ))
            return PageAnalysis(
                page_number=page_num,
                page_width=page_map["width"],
                page_height=page_map["height"],
                sections=sections,
            )
        return map_to_sections(ref_map), map_to_sections(test_map)

    # Handle empty pages
    if not ref_map["elements"] and not test_map["elements"]:
        return (
            PageAnalysis(page_number=page_num, page_width=ref_map["width"], page_height=ref_map["height"], sections=[]),
            PageAnalysis(page_number=page_num, page_width=test_map["width"], page_height=test_map["height"], sections=[]),
        )

    if mode == "single":
        # Two independent GPT calls
        ref_layout, test_layout = await asyncio.gather(
            _call_gpt_layout_single(ref_map, ref_image),
            _call_gpt_layout_single(test_map, test_image),
        )
    else:
        # One paired GPT call
        ref_layout, test_layout = await _call_gpt_layout_paired(
            ref_map, ref_image, test_map, test_image,
        )

    if mode == "raw":
        # Raw mode: use GPT bounding boxes directly, no post-processing
        def to_raw_sections(layout: list[dict], page_map: dict) -> list[Section]:
            result = []
            for s in layout:
                result.append(Section(
                    name=s["name"],
                    content_type=s["content_type"],
                    element_ids=[],
                    bbox=s["region"],
                ))
            return result

        ref_analysis = PageAnalysis(
            page_number=page_num,
            page_width=ref_map["width"],
            page_height=ref_map["height"],
            sections=to_raw_sections(ref_layout, ref_map),
        )
        test_analysis = PageAnalysis(
            page_number=page_num,
            page_width=test_map["width"],
            page_height=test_map["height"],
            sections=to_raw_sections(test_layout, test_map),
        )

        logger.info("Page %d (raw): ref=%d sections, test=%d sections",
                     page_num, len(ref_layout), len(test_layout))
        return ref_analysis, test_analysis

    # Apply layout to each page
    ref_sections_raw = _apply_layout_to_page(ref_map, ref_layout)
    test_sections_raw = _apply_layout_to_page(test_map, test_layout)

    # Convert to model objects
    ref_elements_by_id = {e["id"]: e for e in ref_map["elements"]}
    test_elements_by_id = {e["id"]: e for e in test_map["elements"]}

    def to_sections(raw: list[dict], elements_by_id: dict) -> list[Section]:
        result = []
        for s in raw:
            result.append(Section(
                name=s["name"],
                content_type=s["content_type"],
                element_ids=s["element_ids"],
                bbox=_compute_bbox(s, elements_by_id),
            ))
        return result

    ref_analysis = PageAnalysis(
        page_number=page_num,
        page_width=ref_map["width"],
        page_height=ref_map["height"],
        sections=to_sections(ref_sections_raw, ref_elements_by_id),
    )
    test_analysis = PageAnalysis(
        page_number=page_num,
        page_width=test_map["width"],
        page_height=test_map["height"],
        sections=to_sections(test_sections_raw, test_elements_by_id),
    )

    logger.info(
        "Page %d: ref=%d sections (%d/%d elements), test=%d sections (%d/%d elements)",
        page_num,
        len(ref_analysis.sections),
        sum(len(s.element_ids) for s in ref_analysis.sections),
        ref_map["element_count"],
        len(test_analysis.sections),
        sum(len(s.element_ids) for s in test_analysis.sections),
        test_map["element_count"],
    )

    return ref_analysis, test_analysis
