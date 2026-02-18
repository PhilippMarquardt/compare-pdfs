"""
Strict section instruction template parser with fuzzy section matching.

Template format:
- ## Generic: bullet checklist items only
- ## Specific: bullet checklist items only (may be empty)
- ## Sections / ### Name: bullet checklist items only
"""

import re
from pathlib import Path

from rapidfuzz import fuzz, process

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "section_instructions.md"

FUZZY_THRESHOLD = 95
BULLET_RE = re.compile(r"^\s*[-*]\s*(?:\[\s*\]\s*)?(.+?)\s*$")


def _parse_checklist_block(text: str, block_name: str, *, required: bool = False) -> list[str]:
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
            f"{block_name} must contain only bullet checklist items. Invalid lines: {preview}"
        )

    if required and not items:
        raise ValueError(f"{block_name} must contain at least one bullet checklist item.")

    return items


def _items_to_markdown(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _parse_template(text: str) -> tuple[list[str], list[str], dict[str, list[str]]]:
    generic: list[str] = []
    specific: list[str] = []
    sections: dict[str, list[str]] = {}

    parts = re.split(r"^## ", text, flags=re.MULTILINE)

    for part in parts:
        if not part.strip():
            continue
        lines = part.strip().split("\n", 1)
        heading = lines[0].strip()
        body = lines[1].strip() if len(lines) > 1 else ""

        if heading == "Generic":
            generic = _parse_checklist_block(body, "Generic", required=True)
        elif heading == "Specific":
            specific = _parse_checklist_block(body, "Specific", required=False)
        elif heading == "Sections":
            section_parts = re.split(r"^### ", body, flags=re.MULTILINE)
            for section_part in section_parts:
                if not section_part.strip():
                    continue
                section_lines = section_part.strip().split("\n", 1)
                section_name = section_lines[0].strip()
                section_body = section_lines[1].strip() if len(section_lines) > 1 else ""
                if section_name:
                    sections[section_name] = _parse_checklist_block(
                        section_body,
                        f'Section "{section_name}"',
                        required=True,
                    )

    if not generic:
        raise ValueError("Generic must contain at least one bullet checklist item.")

    return generic, specific, sections


def load_section_instructions() -> tuple[list[str], list[str], dict[str, list[str]]]:
    """Load and strictly parse the section instructions template."""
    if not TEMPLATE_PATH.exists():
        raise ValueError("Section instructions template file is missing.")
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    return _parse_template(text)


def validate_section_instructions_template() -> None:
    """Raise ValueError when the template is not strict checklist format."""
    load_section_instructions()


def get_instructions_for_section(section_name: str) -> dict:
    """
    Returns:
    {
      "generic": str,         # markdown bullet list
      "instructions": str,    # markdown bullet list
      "generic_items": list[str],
      "specific_items": list[str],
      "matched": bool,
      "matched_name": str | None
    }
    """
    generic, specific, sections = load_section_instructions()

    if not sections:
        return {
            "generic": _items_to_markdown(generic),
            "instructions": _items_to_markdown(specific),
            "generic_items": generic,
            "specific_items": specific,
            "matched": False,
            "matched_name": None,
        }

    match = process.extractOne(
        section_name,
        sections.keys(),
        scorer=fuzz.WRatio,
    )

    if match and match[1] >= FUZZY_THRESHOLD:
        matched_name = match[0]
        section_items = sections[matched_name]
        return {
            "generic": _items_to_markdown(generic),
            "instructions": _items_to_markdown(section_items),
            "generic_items": generic,
            "specific_items": section_items,
            "matched": True,
            "matched_name": matched_name,
        }

    return {
        "generic": _items_to_markdown(generic),
        "instructions": _items_to_markdown(specific),
        "generic_items": generic,
        "specific_items": specific,
        "matched": False,
        "matched_name": None,
    }


def get_raw_section_instructions(section_name: str) -> dict:
    """Get editable section checklist markdown (exact or fuzzy section match)."""
    _, _, sections = load_section_instructions()

    if section_name in sections:
        return {
            "instructions": _items_to_markdown(sections[section_name]),
            "matched_name": section_name,
        }

    if sections:
        match = process.extractOne(
            section_name,
            sections.keys(),
            scorer=fuzz.WRatio,
        )
        if match and match[1] >= FUZZY_THRESHOLD:
            return {
                "instructions": _items_to_markdown(sections[match[0]]),
                "matched_name": match[0],
            }

    return {"instructions": "", "matched_name": None}


def list_all_sections() -> dict[str, str]:
    """List all section-specific entries as markdown bullet lists."""
    _, _, sections = load_section_instructions()
    return {name: _items_to_markdown(items) for name, items in sections.items()}


def get_generic_instructions() -> str:
    """Get Generic section checklist as markdown bullets."""
    generic, _, _ = load_section_instructions()
    return _items_to_markdown(generic)


def save_generic_instructions(instructions: str) -> None:
    """Save Generic section checklist."""
    text = TEMPLATE_PATH.read_text(encoding="utf-8") if TEMPLATE_PATH.exists() else ""
    _, specific, sections = _parse_template(text)
    generic = _parse_checklist_block(instructions, "Generic", required=True)
    _write_template(generic, specific, sections)


def save_section_instructions(section_name: str, instructions: str) -> None:
    """Save or update section-specific checklist items."""
    text = TEMPLATE_PATH.read_text(encoding="utf-8") if TEMPLATE_PATH.exists() else ""
    generic, specific, sections = _parse_template(text)
    items = _parse_checklist_block(
        instructions,
        f'Section "{section_name}"',
        required=True,
    )

    if section_name not in sections and sections:
        match = process.extractOne(
            section_name,
            sections.keys(),
            scorer=fuzz.WRatio,
        )
        if match and match[1] >= FUZZY_THRESHOLD:
            del sections[match[0]]

    sections[section_name] = items
    _write_template(generic, specific, sections)


def delete_section_instructions(section_name: str) -> bool:
    """Remove a section-specific entry. Returns True if found and deleted."""
    generic, specific, sections = load_section_instructions()

    if section_name in sections:
        del sections[section_name]
        _write_template(generic, specific, sections)
        return True

    if sections:
        match = process.extractOne(
            section_name,
            sections.keys(),
            scorer=fuzz.WRatio,
        )
        if match and match[1] >= FUZZY_THRESHOLD:
            del sections[match[0]]
            _write_template(generic, specific, sections)
            return True

    return False


def _write_template(generic: list[str], specific: list[str], sections: dict[str, list[str]]) -> None:
    """Write template back in strict checklist format."""
    lines = ["# Section Analysis Instructions", ""]

    lines += ["## Generic"]
    lines += [f"- {item}" for item in generic]
    lines += [""]

    lines += ["## Specific"]
    lines += [f"- {item}" for item in specific]
    lines += [""]

    lines += ["## Sections"]
    for name, items in sorted(sections.items()):
        lines += ["", f"### {name}"]
        lines += [f"- {item}" for item in items]

    lines.append("")
    TEMPLATE_PATH.write_text("\n".join(lines), encoding="utf-8")
