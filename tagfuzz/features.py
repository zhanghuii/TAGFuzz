from __future__ import annotations

import re
from typing import Iterable, Set


def mask_comments_and_strings(code: str) -> str:
    code = re.sub(r"(?s)/\*.*?\*/", " ", code or "")
    code = re.sub(r"(?m)//.*$", " ", code)
    code = re.sub(r"`[^`]*`", '""', code)
    code = re.sub(r'"(?:\\.|[^"\\])*"', '""', code)
    code = re.sub(r"'(?:\\.|[^'\\])+'", "''", code)
    return code


def extract_go_features(code: str) -> Set[str]:
    src = mask_comments_and_strings(code)
    features: Set[str] = set()
    if re.search(r"\bfunc\s+[A-Za-z_]\w*\s*\[[^\]]+\]\s*\(", src):
        features.add("type:generic_func")
    if re.search(r"(?m)^\s*type\s+[A-Za-z_]\w*\s*\[[^\]]+\]", src):
        features.add("type:generic_type")
    if re.search(r"\binterface\s*\{", src):
        features.add("type:interface")
    if "~" in src:
        features.add("type:tilde_constraint")
    if re.search(r"\bfunc\s+\([^)]*\)\s+[A-Za-z_]\w*\s*\(", src):
        features.add("type:method_decl")
    if re.search(r"\[\s*(?:1\s*<<\s*\d+|[1-9]\d{3,})\s*\]", src):
        features.add("type:large_array")
    if "map[" in src:
        features.add("type:map")
    if re.search(r"\*\s*\[[^\]]+\]", src):
        features.add("type:pointer_to_array")
    if re.search(r"\[[^\]\n]*:[^\]\n]*\]", src):
        features.add("expr:slice")
    if "unsafe.Pointer" in src or re.search(r"\buintptr\s*\(", src):
        features.add("expr:unsafe_pointer")
    if re.search(r"(?:\d|\biota\b|0x[0-9a-fA-F]+).*(?:<<|>>)", src):
        features.add("expr:constant_shift")
    if re.search(r"\b(?:u?int(?:8|16|32|64)?|uintptr|float(?:32|64)|complex(?:64|128)?)\s*\(", src):
        features.add("expr:constant_conversion")
    if re.search(r"(?:\[\]|\[[^\]]+\]|struct\s*\{[^}]*\}|[A-Za-z_]\w*)\s*\{", src):
        features.add("expr:composite_literal")
    for builtin in ("append", "copy", "make", "new", "delete"):
        if re.search(rf"\b{builtin}\s*\(", src):
            features.add(f"expr:{builtin}")
    if re.search(r"\bfunc\s*\([^)]*\)", src):
        features.add("ctrl:closure")
    if re.search(r"\bdefer\b", src):
        features.add("ctrl:defer")
    if re.search(r"\b(?:panic|recover)\s*\(", src):
        features.add("ctrl:panic_recover")
    if re.search(r"\bgoto\s+[A-Za-z_]\w*", src):
        features.add("ctrl:goto_label")
    if re.search(r"\brange\b", src):
        features.add("ctrl:range")
    if re.search(r"\brange\b", src) and "map[" in src:
        features.add("ctrl:range_map")
    if re.search(r"\bif\b.*\belse\b", src, flags=re.S):
        features.add("ctrl:branch_merge")
    if re.search(r"\bcomplex(?:64|128)?\s*\(", src) or re.search(r"\b[0-9]+i\b", src):
        features.add("type:complex")
    if features & {"type:generic_func", "type:generic_type", "type:interface", "type:tilde_constraint"}:
        features.add("phase:types2_likely")
    if features & {"expr:slice", "expr:constant_shift", "expr:append", "expr:copy", "ctrl:branch_merge"}:
        features.add("phase:ssa_likely")
    if features & {"expr:unsafe_pointer", "expr:new", "type:method_decl", "ctrl:closure"}:
        features.add("phase:escape_likely")
    return features


def has_all(features: Iterable[str], required: Iterable[str]) -> bool:
    return set(required or []).issubset(set(features or []))

