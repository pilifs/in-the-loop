"""Fingerprint visible tool and assistant values independently of the CLI's JSON display indentation."""

import hashlib
import json


def signal(text):
    content = text.strip()
    try:
        value = json.loads(content)
    except (ValueError, RecursionError):
        pass
    else:
        if isinstance(value, (dict, list)):
            content = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(content.encode()).hexdigest()


def contained(value, depth=0):
    if isinstance(value, str):
        yield signal(value)
        if depth < 4 and len(value.encode()) <= 131072:
            try:
                nested = json.loads(value)
            except (ValueError, RecursionError):
                return
            if isinstance(nested, (dict, list)):
                yield from contained(nested, depth + 1)
    elif isinstance(value, dict) and depth < 4:
        for child in value.values():
            yield from contained(child, depth + 1)
    elif isinstance(value, list) and depth < 4:
        for child in value:
            yield from contained(child, depth + 1)
