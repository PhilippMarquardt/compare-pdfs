from pathlib import Path

from .global_analysis import parse_global_template
from .section_instructions import (
    get_generic_instructions,
    save_generic_instructions,
)

GLOBAL_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "global_analysis.md"


def get_general_instructions() -> dict[str, str]:
    global_template = GLOBAL_TEMPLATE_PATH.read_text(encoding="utf-8") if GLOBAL_TEMPLATE_PATH.exists() else ""
    return {
        "section_generic": get_generic_instructions(),
        "global_template": global_template,
    }


def save_general_instructions(section_generic: str, global_template: str) -> None:
    # Validate both payloads before writing anything.
    parse_global_template(global_template)

    previous = get_general_instructions()
    try:
        save_generic_instructions(section_generic)
        GLOBAL_TEMPLATE_PATH.write_text(global_template, encoding="utf-8")
    except Exception:
        # Best-effort rollback if one write succeeds and the other fails.
        try:
            save_generic_instructions(previous["section_generic"])
            GLOBAL_TEMPLATE_PATH.write_text(previous["global_template"], encoding="utf-8")
        except Exception:
            pass
        raise
