from __future__ import annotations

import re
from typing import Optional


def clean_go_code(code: str) -> Optional[str]:
    code = (
        str(code or "")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
        .strip()
    )
    if not re.search(r"(?m)^\s*package\s+[A-Za-z_]\w*\s*$", code):
        return None
    return code


def extract_go_code(completion: str) -> Optional[str]:
    if not completion:
        return None
    text = re.sub(r"(?is)<think>.*?</think>", "", completion).strip()
    tagged = re.search(r"(?is)<code\b[^>]*>(.*?)</code>", text)
    if tagged:
        return clean_go_code(tagged.group(1))
    fenced = re.search(r"(?is)```(?:go|golang)?\s*\n?(.*?)```", text)
    if fenced:
        return clean_go_code(fenced.group(1))
    package_pos = re.search(r"(?m)^\s*package\s+[A-Za-z_]\w*\s*$", text)
    if package_pos:
        return clean_go_code(text[package_pos.start():])
    return None

