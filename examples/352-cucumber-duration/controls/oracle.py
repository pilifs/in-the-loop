"""Compare every direct caller and adapter result on the frozen grid."""
import base64
import json

COUNT = 18

def driver_args():
    return ["--all"]

def expected(code):
    return f"{(0, 1, 59)[code // 6]}.{(0, 1, 999)[(code // 2) % 3]:03d}"

def rows(lines):
    seen = []
    for line in lines:
        row = json.loads(line)
        code, direct, adapter = row["code"], row["direct"], row["adapter"]
        values = [base64.b64decode(field, validate=True).decode("utf-8") for field in (direct, adapter)]
        seen.append((int(code), *values))
    if [code for code, _, _ in seen] != list(range(COUNT)):
        raise ValueError("Incomplete or repeated selector in JVM output")
    return seen

def problems(lines):
    return [(code, {"actual": direct, "expected": expected(code)})
            for code, direct, _ in rows(lines) if direct != expected(code)]

def correspondence(lines):
    seen = rows(lines)
    return {"cases": len(seen), "disagreements": sum(direct != adapter for _, direct, adapter in seen)}
