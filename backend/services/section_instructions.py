"""
Section instruction template parser with fuzzy matching.

Parses backend/templates/section_instructions.md into:
- generic: always-apply instructions
- specific: fallback instructions (when no section match)
- sections: dict of section_name → instructions

Fuzzy matches GPT section names against template headings.
"""

import re
from pathlib import Path

from rapidfuzz import fuzz, process

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "section_instructions.md"

FUZZY_THRESHOLD = 75


def _parse_template(text: str) -> tuple[str, str, dict[str, str]]:
    """Parse the markdown template into (generic, specific, sections)."""
    generic = ""
    specific = ""
    sections: dict[str, str] = {}

    # Split by ## headings
    parts = re.split(r"^## ", text, flags=re.MULTILINE)

    for part in parts:
        if not part.strip():
            continue
        lines = part.strip().split("\n", 1)
        heading = lines[0].strip()
        body = lines[1].strip() if len(lines) > 1 else ""

        if heading == "Generic":
            generic = body
        elif heading == "Specific":
            specific = body
        elif heading == "Sections":
            # Parse ### sub-headings
            section_parts = re.split(r"^### ", body, flags=re.MULTILINE)
            for sp in section_parts:
                if not sp.strip():
                    continue
                sp_lines = sp.strip().split("\n", 1)
                section_name = sp_lines[0].strip()
                section_body = sp_lines[1].strip() if len(sp_lines) > 1 else ""
                if section_name:
                    sections[section_name] = section_body

    return generic, specific, sections


def load_section_instructions() -> tuple[str, str, dict[str, str]]:
    """Load and parse the section instructions template."""
    if not TEMPLATE_PATH.exists():
        return "", "", {}
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    return _parse_template(text)


def get_instructions_for_section(section_name: str) -> dict:
    """Get instructions for a section. Returns:
    {
        "generic": str,
        "instructions": str,  # section-specific if matched, else global specific
        "matched": bool,      # whether a section-specific match was found
        "matched_name": str | None,  # the template section name that matched
    }
    """
    generic, specific, sections = load_section_instructions()

    if not sections:
        return {
            "generic": generic,
            "instructions": specific,
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
        return {
            "generic": generic,
            "instructions": sections[matched_name],
            "matched": True,
            "matched_name": matched_name,
        }

    return {
        "generic": generic,
        "instructions": specific,
        "matched": False,
        "matched_name": None,
    }


def get_raw_section_instructions(section_name: str) -> dict:
    """Get raw section-specific instructions (exact or fuzzy match).
    Returns {"instructions": str, "matched_name": str | None} for the editor UI.
    """
    _, _, sections = load_section_instructions()

    # Try exact match first
    if section_name in sections:
        return {"instructions": sections[section_name], "matched_name": section_name}

    # Fuzzy match
    if sections:
        match = process.extractOne(
            section_name,
            sections.keys(),
            scorer=fuzz.WRatio,
        )
        if match and match[1] >= FUZZY_THRESHOLD:
            return {"instructions": sections[match[0]], "matched_name": match[0]}

    return {"instructions": "", "matched_name": None}


def list_all_sections() -> dict[str, str]:
    """List all section-specific entries."""
    _, _, sections = load_section_instructions()
    return sections


def save_section_instructions(section_name: str, instructions: str) -> None:
    """Save or update section-specific instructions in the template file."""
    text = TEMPLATE_PATH.read_text(encoding="utf-8") if TEMPLATE_PATH.exists() else ""
    generic, specific, sections = _parse_template(text)

    # Check if fuzzy match exists — update that entry instead of creating duplicate
    if section_name not in sections and sections:
        match = process.extractOne(
            section_name,
            sections.keys(),
            scorer=fuzz.WRatio,
        )
        if match and match[1] >= FUZZY_THRESHOLD:
            # Remove old entry, use new name
            del sections[match[0]]

    sections[section_name] = instructions
    _write_template(generic, specific, sections)


def delete_section_instructions(section_name: str) -> bool:
    """Remove a section-specific entry. Returns True if found and deleted."""
    text = TEMPLATE_PATH.read_text(encoding="utf-8") if TEMPLATE_PATH.exists() else ""
    generic, specific, sections = _parse_template(text)

    # Exact match first
    if section_name in sections:
        del sections[section_name]
        _write_template(generic, specific, sections)
        return True

    # Fuzzy match
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


def _write_template(generic: str, specific: str, sections: dict[str, str]) -> None:
    """Write the template file back."""
    lines = ["# Section Analysis Instructions", ""]
    lines += ["## Generic", generic, ""]
    lines += ["## Specific", specific, ""]
    lines += ["## Sections"]

    for name, body in sorted(sections.items()):
        lines += ["", f"### {name}", body]

    lines.append("")  # trailing newline
    TEMPLATE_PATH.write_text("\n".join(lines), encoding="utf-8")
