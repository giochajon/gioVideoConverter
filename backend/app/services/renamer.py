import os
import re

_BRACKET_RE = re.compile(r"\s*\[[^\]]*\]")


def strip_and_tag(filename: str, preset_name: str) -> str:
    """Remove any existing [..] tags from the filename stem and append [preset_name]."""
    stem, ext = os.path.splitext(filename)
    cleaned = _BRACKET_RE.sub("", stem).strip()
    tag = preset_name.replace("/", "-").strip()
    return f"{cleaned} [{tag}]{ext}"
