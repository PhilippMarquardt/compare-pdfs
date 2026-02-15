"""
PDF page map extraction using v5 pipeline:
raw elements → recursive rect merge → proximity merge.
"""

import pdfplumber


MERGE_TOLERANCE = 1  # pts for rect touching
PROXIMITY_GAP = 5    # pts for nearby element merging


def extract_page_map(pdf_path: str, page_num: int) -> dict:
    """
    Extract a structured page map from a single PDF page.
    page_num is 1-based.
    Pipeline: raw → rect merge → proximity merge → assign IDs.
    """
    raw = _extract_raw(pdf_path, page_num)
    elements = _recursive_rect_merge(raw["elements"], raw["width"], raw["height"])
    elements = _merge_nearby(elements)

    # Assign IDs and round bboxes
    for i, el in enumerate(elements):
        el["id"] = f"E{i+1}"
        el["bbox"] = [round(v, 1) for v in el["bbox"]]

    elements.sort(key=lambda e: (e["bbox"][1], e["bbox"][0]))

    result = {
        "page_number": page_num,
        "width": round(raw["width"], 1),
        "height": round(raw["height"], 1),
        "element_count": len(elements),
        "elements": elements,
    }

    # Detect header separator line
    sep_y = _detect_header_separator(raw["elements"], raw["width"], raw["height"])
    if sep_y is not None:
        result["header_separator_y"] = round(sep_y, 1)

    return result


def _detect_header_separator(raw_elements: list, page_width: float, page_height: float) -> float | None:
    """Detect a long horizontal line in the top 15% of the page that likely separates the header.

    Returns the y-coordinate of the separator line, or None if not found.
    """
    top_zone = page_height * 0.15
    min_width_fraction = 0.5  # line must span at least 50% of page width
    max_thickness = 3.0  # must be thin (essentially a line)

    candidates = []
    for el in raw_elements:
        if el["type"] not in ("line", "rect"):
            continue
        x0, y0, x1, y1 = el["bbox"]
        width = x1 - x0
        height = y1 - y0

        # Must be horizontal (wide and thin)
        if height > max_thickness:
            continue
        if width < page_width * min_width_fraction:
            continue
        # Must be in top zone
        mid_y = (y0 + y1) / 2
        if mid_y > top_zone:
            continue

        candidates.append(mid_y)

    if not candidates:
        return None

    # Return the lowest (furthest down) candidate — the one most likely to be
    # the separator between header and content
    return max(candidates)


def _extract_raw(pdf_path: str, page_num: int) -> dict:
    """Extract raw pdfplumber elements with NO merging."""
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_num - 1]
        elements = []

        words = page.extract_words(
            x_tolerance=2, y_tolerance=2,
            keep_blank_chars=False, use_text_flow=False,
        )
        for w in words:
            elements.append({
                "type": "text",
                "bbox": [w["x0"], w["top"], w["x1"], w["bottom"]],
                "content": w["text"][:80],
            })

        for r in page.rects:
            elements.append({
                "type": "rect",
                "bbox": [r["x0"], r["top"], r["x1"], r["bottom"]],
                "content": None,
            })

        for ln in page.lines:
            elements.append({
                "type": "line",
                "bbox": [ln["x0"], ln["top"], ln["x1"], ln["bottom"]],
                "content": None,
            })

        for c in page.curves:
            pts = c["pts"]
            elements.append({
                "type": "curve",
                "bbox": [
                    min(pt[0] for pt in pts), min(pt[1] for pt in pts),
                    max(pt[0] for pt in pts), max(pt[1] for pt in pts),
                ],
                "content": None,
            })

        for img in page.images:
            elements.append({
                "type": "image",
                "bbox": [img["x0"], img["top"], img["x1"], img["bottom"]],
                "content": None,
            })

        return {
            "width": float(page.width),
            "height": float(page.height),
            "elements": elements,
        }


def _contains(outer, inner, tol=MERGE_TOLERANCE):
    return (inner[0] >= outer[0] - tol and
            inner[1] >= outer[1] - tol and
            inner[2] <= outer[2] + tol and
            inner[3] <= outer[3] + tol)


def _touches(a, b, tol=MERGE_TOLERANCE):
    return (a[0] <= b[2] + tol and b[0] <= a[2] + tol and
            a[1] <= b[3] + tol and b[1] <= a[3] + tol)


def _bbox_area(b):
    return max(0, b[2] - b[0]) * max(0, b[3] - b[1])


def _group_bbox(group):
    x0 = min(e["bbox"][0] for e in group)
    y0 = min(e["bbox"][1] for e in group)
    x1 = max(e["bbox"][2] for e in group)
    y1 = max(e["bbox"][3] for e in group)
    return [x0, y0, x1, y1]


def _recursive_rect_merge(elements, page_width, page_height, max_page_fraction=0.5):
    """Recursively merge elements inside rects, then merge touching rects."""
    page_area = page_width * page_height
    filtered = []
    for e in elements:
        if e["type"] == "rect" and _bbox_area(e["bbox"]) / page_area > max_page_fraction:
            continue
        filtered.append(e)
    elements = filtered

    rects = [e for e in elements if e["type"] == "rect"]
    others = [e for e in elements if e["type"] != "rect"]

    if not rects:
        return elements

    rects.sort(key=lambda e: _bbox_area(e["bbox"]), reverse=True)
    rect_groups = [[r] for r in rects]
    free = list(others)

    changed = True
    while changed:
        changed = False

        still_free = []
        for el in free:
            absorbed = False
            for group in rect_groups:
                union = _group_bbox(group)
                if _contains(union, el["bbox"]):
                    group.append(el)
                    absorbed = True
                    changed = True
                    break
            if not absorbed:
                still_free.append(el)
        free = still_free

        merged_flags = [False] * len(rect_groups)
        for i in range(len(rect_groups)):
            if merged_flags[i]:
                continue
            union_i = _group_bbox(rect_groups[i])
            for j in range(i + 1, len(rect_groups)):
                if merged_flags[j]:
                    continue
                union_j = _group_bbox(rect_groups[j])
                if _contains(union_i, union_j):
                    rect_groups[i].extend(rect_groups[j])
                    merged_flags[j] = True
                    changed = True
                elif _contains(union_j, union_i):
                    rect_groups[j].extend(rect_groups[i])
                    merged_flags[i] = True
                    changed = True
                    break
        rect_groups = [g for i, g in enumerate(rect_groups) if not merged_flags[i]]

        merged_flags = [False] * len(rect_groups)
        for i in range(len(rect_groups)):
            if merged_flags[i]:
                continue
            union_i = _group_bbox(rect_groups[i])
            for j in range(i + 1, len(rect_groups)):
                if merged_flags[j]:
                    continue
                union_j = _group_bbox(rect_groups[j])
                if _touches(union_i, union_j):
                    rect_groups[i].extend(rect_groups[j])
                    merged_flags[j] = True
                    changed = True
        rect_groups = [g for i, g in enumerate(rect_groups) if not merged_flags[i]]

    result = []
    for group in rect_groups:
        bbox = _group_bbox(group)
        texts = [e["content"] for e in group if e.get("content")]
        result.append({
            "type": "merged",
            "bbox": bbox,
            "content": " | ".join(texts[:5]) if texts else None,
            "child_count": len(group),
        })
    result.extend(free)
    return result


def _merge_nearby(elements, gap=PROXIMITY_GAP):
    """Merge ALL elements (including rect-merged groups) within gap pts of each other."""
    if len(elements) <= 1:
        return elements

    clusters = [
        [[*e["bbox"]], {e["type"]}, [e.get("content", "") or ""], 1]
        for e in elements
    ]

    changed = True
    while changed:
        changed = False
        merged_flags = [False] * len(clusters)
        new_clusters = []
        for i in range(len(clusters)):
            if merged_flags[i]:
                continue
            bbox_i, types_i, texts_i, count_i = clusters[i]
            for j in range(i + 1, len(clusters)):
                if merged_flags[j]:
                    continue
                bbox_j, types_j, texts_j, count_j = clusters[j]
                if (bbox_i[0] <= bbox_j[2] + gap and bbox_j[0] <= bbox_i[2] + gap and
                        bbox_i[1] <= bbox_j[3] + gap and bbox_j[1] <= bbox_i[3] + gap):
                    bbox_i[0] = min(bbox_i[0], bbox_j[0])
                    bbox_i[1] = min(bbox_i[1], bbox_j[1])
                    bbox_i[2] = max(bbox_i[2], bbox_j[2])
                    bbox_i[3] = max(bbox_i[3], bbox_j[3])
                    types_i.update(types_j)
                    texts_i.extend(texts_j)
                    count_i += count_j
                    clusters[i][3] = count_i
                    merged_flags[j] = True
                    changed = True
            new_clusters.append([bbox_i, types_i, texts_i, count_i])
        clusters = new_clusters

    result = []
    for bbox, types, texts, count in clusters:
        text_content = [t for t in texts if t]
        has_text = "text" in types or "merged" in types
        only_text = types <= {"text", "merged"}
        if only_text and has_text:
            btype = "text_block"
        elif not has_text:
            btype = "drawing_block"
        else:
            btype = "mixed_block"
        result.append({
            "type": btype,
            "bbox": bbox,
            "content": " ".join(text_content[:10]) if text_content else None,
        })
    return result
