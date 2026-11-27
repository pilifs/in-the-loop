"""Check archived observations for a named example whose original build runs separately."""
import hashlib
import json
from pathlib import Path
import re


def plan(folder):
    doc = json.loads((folder / "recorded-comparison.json").read_text())
    ids = doc["questions"]
    if (doc.get("schema") != "recorded-public-comparison/v1" or not isinstance(ids,list) or not ids
            or not all(isinstance(q,str) and q for q in ids) or len(set(ids)) != len(ids)):
        raise ValueError("invalid recorded comparison")
    if (not isinstance(doc["evidence"],dict) or not doc["evidence"] or not isinstance(doc["reproduce"],list)
            or not doc["reproduce"] or not all(isinstance(cmd,str) and cmd for cmd in doc["reproduce"])):
        raise ValueError("recorded comparison needs original evidence and its reproduction command")
    base = folder.parent.parent.resolve()
    for relative, digest in doc["evidence"].items():
        path = (base / relative).resolve()
        if (Path(relative).is_absolute() or ".." in Path(relative).parts or not path.is_relative_to(base / "verification")
                or path.suffix != ".json" or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise ValueError("invalid archived verification receipt")
    return {"example": folder.name[:3], "approach": "B8", "executable": True, "notExecuted": None,
            "runner": "recorded-comparison", "operation": "verify archived evidence digests",
            "questions": ids, "evidence": doc["evidence"], "reproduce": doc["reproduce"],
            "tools": {"required": [], "optional": []}}


def check(folder):
    operation = plan(folder)
    root = folder.parent.parent
    for name, expected in operation["evidence"].items():
        with (root / name).open("rb") as data:
            if hashlib.file_digest(data, "sha256").hexdigest() != expected:
                raise ValueError(f"{folder.name}: archived evidence changed: {name}")
    print(f"{folder.name}: verified {len(operation['evidence'])} archived receipt(s)")
    for command in operation["reproduce"]:
        print("Repeat the original experiment with", command)
    return operation
