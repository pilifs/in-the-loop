"""Every test in the repository, what it calls, and what past runs say it cost, without running any of it.

test_costs.py's `estimate` writes lib/tests/costs.json from this; the cost lint reads the same listing. Three sources:

- The tests themselves. Rust tests are found by reading lib/src and lib/tests (strings and comments blanked, so the Java
  sources the tests embed don't count), Python tests by parsing each test_*.py with `ast`. What a test calls is read
  from its body and the helpers of the same file (and module files it declares) that it calls, transitively.
- Past sessions' redacted logs, through llm-dlc/tools/tool_time.py: the output of every cargo test and Python test run
  the agent kept. A section of cargo output that ran one test gives that test's time; a section that ran several
  bounds each of them by the section's time (tests run in parallel, so none took longer); "has been running for over
  60 seconds" bounds it from below. A Python run of one file bounds each of its tests by the file's time (they run one
  after another).
- Past pipeline jobs' logs in verification/results/, read the same way.

Standard library only.
"""
from __future__ import annotations

import ast
import json
import re
import shlex
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "lib"
TOOLS = ROOT / "llm-dlc" / "tools"


# --- reading Rust ---------------------------------------------------------------------------------------------------

def blank(src: str, strings: bool = True) -> str:
    """SRC with comments (and, if STRINGS, the contents of string and char literals) replaced by spaces, newlines
    kept, so that positions and line numbers stay the same and braces inside them don't count."""
    out = list(src)
    i, n = 0, len(src)

    def wipe(a, b):
        for k in range(a, b):
            if out[k] != "\n":
                out[k] = " "

    while i < n:
        c = src[i]
        if src.startswith("//", i):
            j = src.find("\n", i)
            j = n if j < 0 else j
            wipe(i, j)
            i = j
        elif src.startswith("/*", i):
            depth, j = 1, i + 2
            while j < n and depth:
                if src.startswith("/*", j):
                    depth, j = depth + 1, j + 2
                elif src.startswith("*/", j):
                    depth, j = depth - 1, j + 2
                else:
                    j += 1
            wipe(i, j)
            i = j
        elif (m := re.compile(r'b?r(#*)"').match(src, i)) and (i == 0 or not (src[i - 1].isalnum() or src[i - 1] == "_")):
            end = src.find('"' + m[1], m.end())
            end = n if end < 0 else end
            if strings:
                wipe(m.end(), end)
            i = end + 1 + len(m[1])
        elif c == '"':
            j = i + 1
            while j < n and src[j] != '"':
                j += 2 if src[j] == "\\" else 1
            if strings:
                wipe(i + 1, j)
            i = j + 1
        elif c == "'":
            m = re.compile(r"'(?:\\(?:u\{[0-9a-fA-F]+\}|x[0-9a-fA-F]{2}|.)|[^\\'])'").match(src, i)
            if m:
                if strings:
                    wipe(i + 1, m.end() - 1)
                i = m.end()
            else:
                i += 1  # a lifetime
        else:
            i += 1
    return "".join(out)


def _match(code: str, i: int, open_: str, close: str) -> int:
    """Index of the bracket closing the one at I."""
    depth = 0
    for j in range(i, len(code)):
        if code[j] == open_:
            depth += 1
        elif code[j] == close:
            depth -= 1
            if not depth:
                return j
    return len(code) - 1


def _attributes(src: str, code: str, at: int) -> list[str]:
    """The outer attributes (`#[...]`, as written) before the item starting at AT, nearest last."""
    attrs, i = [], at
    while True:
        j = i
        while j > 0 and code[j - 1].isspace():
            j -= 1
        m = re.search(r"(?:\bpub(?:\([^)]*\))?|\basync|\bunsafe|\bconst|\bextern\s*\"?\w*\"?)$", code[:j])
        if m and j:
            i = m.start()
            continue
        if j and code[j - 1] == "]":
            depth, k = 0, j - 1
            while k >= 0:
                if code[k] == "]":
                    depth += 1
                elif code[k] == "[":
                    depth -= 1
                    if not depth:
                        break
                k -= 1
            if k > 0 and code[k - 1] == "#":
                attrs.insert(0, src[k - 1:j])
                i = k - 1
                continue
        return attrs


ITEM = re.compile(r"\b(?:mod\s+(\w+)\s*([{;])|fn\s+(\w+))")


def rust_items(src: str, prefix: tuple[str, ...] = ()) -> list[dict]:
    """Every `fn` of a Rust file outside another fn's body: its path (module path within the file, under PREFIX, and
    its name), its attributes, and its body's span. Modules declared with `mod x;` are listed as `{"mod": x}`."""
    code = blank(src)
    items, i, stack = [], 0, []  # stack: (module name, index of its closing brace)
    while m := ITEM.search(code, i):
        while stack and m.start() > stack[-1][1]:
            stack.pop()
        path = prefix + tuple(s[0] for s in stack)
        if m[1]:
            if m[2] == "{":
                brace = m.end() - 1
                stack.append((m[1], _match(code, brace, "{", "}")))
            else:
                items.append({"mod": m[1], "path": path})
            i = m.end()
            continue
        j = m.end()
        while j < len(code) and code[j] not in "{;":
            if code[j] in "([<":
                j = _match(code, j, code[j], {"(": ")", "[": "]", "<": ">"}[code[j]]) if code[j] != "<" else j
            j += 1
        if j >= len(code) or code[j] == ";":
            i = j + 1
            continue
        end = _match(code, j, "{", "}")
        attrs = _attributes(src, code, m.start())
        items.append({"name": "::".join(path + (m[3],)), "fn": m[3], "attrs": attrs, "start": m.start(),
                      "body": (j, end + 1), "line": src.count("\n", 0, m.start()) + 1,
                      "test": any(re.fullmatch(r"#\[\s*test\s*\]", a) for a in attrs),
                      "ignore": next((_ignore_reason(a) for a in attrs if re.match(r"#\[\s*ignore\b", a)), None)})
        i = end + 1
    return items


def _ignore_reason(attr: str) -> str:
    m = re.search(r'=\s*"((?:[^"\\]|\\.)*)"', attr, re.S)
    return re.sub(r"\\\n\s*", "", m[1]) if m else ""


def _module_prefix(rel: Path) -> tuple[str, ...]:
    """lib/src/bmc/sat.rs -> ("bmc", "sat"); lib/src/bmc/mod.rs -> ("bmc",); lib/src/lib.rs -> ()."""
    parts = list(rel.relative_to("lib/src").with_suffix("").parts)
    if parts[-1] in ("mod", "lib", "main"):
        parts.pop()
    return tuple(parts)


def rust_files(root: Path = ROOT) -> list[tuple[str, Path, list[Path]]]:
    """(binary as cargo names it, file with tests, the module files it declares) for every Rust test target."""
    lib = root / "lib"
    out = [("src/lib.rs", p, []) for p in sorted((lib / "src").rglob("*.rs")) if p.name != "main.rs"]
    out.append(("src/main.rs", lib / "src" / "main.rs", []))
    for p in sorted((lib / "tests").glob("*.rs")):
        mods = [m["mod"] for m in rust_items(p.read_text()) if "mod" in m]
        files = [f for m in mods for f in (lib / "tests" / m / "mod.rs", lib / "tests" / f"{m}.rs") if f.exists()]
        out.append((f"tests/{p.name}", p, files))
    return out


# --- what a test calls -------------------------------------------------------------------------------------------

# What a test's code (with its comments blanked, its strings kept) shows it runs. Read on the test's body and every
# helper of its file it calls. Order: a stand-in first, since a stand-in JBMC is named like the real one.
RUST_CALLS = [
    ("stand-in", r"#!/bin/(?:ba)?sh|#!/usr/bin/env|\bfake_jbmc\b|\bstand_in_jbmc\b|\bstaged_jbmc\b"),
    ("jbmc", r"Engine::(?:Jbmc|Auto)\b|\bhas_jbmc\(|\bjbmc_check\(|\bmissing\(\"JBMC\"\)|"
             r"\"--engine\",\s*\"(?:jbmc|auto)\"|\"--engine=(?:jbmc|auto)\""),
    ("tlc", r"\btla2tools\b|\"tlc\"|tlc2\.TLC|\brun_tlc\(|\btlc_command\(|\bmissing\(\"TLC\"\)"),
    ("javac", r"\"javac\"|\bhas_javac\(|\bjavac\("),
    ("java", r"\"java\"|run_on_jvm\(|jvm_witness::|witness::replay\("),
    ("jvmcontract", r"CARGO_BIN_EXE_jvmcontract"),
    ("process", r"Command::new\("),
]
# Library entry points that run JBMC unless told otherwise: their options' default engine is JBMC. A test that names
# the native engine, or points JBMC at a path that doesn't exist, runs without it.
RUST_DEFAULT_JBMC = r"\b(?:equivalence|property)::run\("
RUST_NATIVE = r"Engine::Native\b|\"native\"|/nonexistent/jbmc|\bNO_JBMC\b"
# Helpers not followed: constructors, whose engine field is a default, not a run.
NOT_FOLLOWED = {"default", "new", "from", "into", "clone"}


def _calls(text: str) -> set[str]:
    return set(re.findall(r"(?<![.\w])(\w+)\s*(?:::<[^>]*>)?\s*\(", text))


def rust_tests(root: Path = ROOT) -> list[dict]:
    """Every Rust test: binary, name (as cargo prints it), file, line, ignore reason, and what it calls."""
    out = []
    for binary, path, mods in rust_files(root):
        src = path.read_text()
        prefix = _module_prefix(path.relative_to(root)) if binary.startswith("src/") else ()
        sources = [(src, rust_items(src, prefix))] + [(m.read_text(), rust_items(m.read_text())) for m in mods]
        if not any(it.get("test") for it in sources[0][1]):
            continue
        texts: dict[str, list[str]] = {}
        for s, items in sources:
            nc = blank(s, strings=False)
            for it in items:
                if "fn" in it:
                    texts.setdefault(it["fn"], []).append(nc[it["start"]:it["body"][1]])
        for it in sources[0][1]:
            if not it.get("test"):
                continue
            seen, todo, reach = {it["fn"]}, [blank(src, strings=False)[it["start"]:it["body"][1]]], []
            while todo:
                text = todo.pop()
                reach.append(text)
                for name in _calls(blank(text)) - seen - NOT_FOLLOWED:
                    if name in texts:
                        seen.add(name)
                        todo += texts[name]
            body = "\n".join(reach)
            calls = {kind for kind, rx in RUST_CALLS if re.search(rx, body)}
            if re.search(RUST_DEFAULT_JBMC, body) and not re.search(RUST_NATIVE, body):
                calls.add("jbmc")
            if "stand-in" in calls:
                calls.discard("jbmc")  # the JBMC it names is the stand-in
            out.append({"binary": binary, "name": it["name"], "file": str(path.relative_to(root)), "line": it["line"],
                        "ignore": it["ignore"], "calls": sorted(calls), "helpers": sorted(seen - {it["fn"]})})
    return out


# --- the tier helper in the tests ----------------------------------------------------------------------------------

TOOL_TIER = re.compile(r"[ \t]*\b(?:jvmcontract|crate)::tool_tier!\((pending)?\);[ \t]*\n?")


def wanted_tier_call(row: dict | None) -> str | None:
    """The `tool_tier!` call a test's inventory row asks for: `pending` for `retier: pending`, empty for the tool tier,
    None for a unit-tier or ignored test (and one the inventory doesn't list)."""
    if row is None or row["tier"] == "unit" or row.get("ignored") is not None:
        return None
    return "pending" if row.get("retier") == "pending" else ""


def tier_calls(src: str, rel: str, rows: dict) -> tuple[str, int]:
    """SRC with each test's first statement the `tool_tier!` call its row in ROWS ({name: row}) asks for, and no
    other: (new source, tests changed). REL is the file's path from the repository root."""
    prefix = _module_prefix(Path(rel)) if rel.startswith("lib/src/") else ()
    krate = "crate" if rel.startswith("lib/src/") else "jvmcontract"
    edits, changed = [], 0  # edits: (start, end, text), applied from the end
    for it in rust_items(src, prefix):
        if not it.get("test"):
            continue
        want = wanted_tier_call(rows.get(it["name"]))
        open_, close = it["body"]
        body = src[open_ + 1:close - 1]
        have = [(m.start() + open_ + 1, m.end() + open_ + 1, m[1] or "") for m in TOOL_TIER.finditer(body)]
        first = re.match(r"[ \t]*\n?", body).end() + open_ + 1
        if want is None and not have or have and len(have) == 1 and have[0][0] == first and have[0][2] == want:
            continue
        line = src.rfind("\n", 0, it["start"]) + 1
        indent = re.match(r"[ \t]*", src[line:]).group() + "    "
        changed += 1
        edits += [(a, b, "") for a, b, _ in have]
        if want is not None:
            edits.append((open_ + 1, open_ + 1, f"\n{indent}{krate}::tool_tier!({want});"))
    for a, b, text in sorted(edits, key=lambda e: (e[0], e[1]), reverse=True):
        src = src[:a] + text + src[b:]
    return src, changed


# --- reading Python -----------------------------------------------------------------------------------------------

PY_CALLS = [
    ("process", r"\bsubprocess\b|\bos\.system\(|\bPopen\(|\bposix_spawn|\bos\.exec"),
    ("network", r"\burllib\.request\.urlopen\(|\bhttp\.client\b|\bsocket\.socket\("),
]


def python_tests(root: Path = ROOT, files=None) -> list[dict]:
    """Every Python test method: file, name (Class.method), line, and what it calls."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_costs import python_test_files
    out = []
    for path in files if files is not None else python_test_files(root):
        src = path.read_text()
        tree = ast.parse(src)
        funcs = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}

        def methods(cls, seen=()):
            own = {n.name: n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
            for b in cls.bases:
                name = b.id if isinstance(b, ast.Name) else None
                if name in classes and name not in seen:
                    own = {**methods(classes[name], seen + (name,)), **own}
            return own

        def is_case(cls, seen=()):
            for b in cls.bases:
                name = b.id if isinstance(b, ast.Name) else b.attr if isinstance(b, ast.Attribute) else None
                if name in ("TestCase", "IsolatedAsyncioTestCase"):
                    return True
                if name in classes and name not in seen and is_case(classes[name], seen + (name,)):
                    return True
            return False

        for cname, cls in classes.items():
            if not is_case(cls):
                continue
            ms = methods(cls)
            setup = [ms[k] for k in ("setUp", "setUpClass", "tearDown", "asyncSetUp") if k in ms]
            setup += [funcs[k] for k in ("setUpModule",) if k in funcs]
            for mname, node in ms.items():
                if not mname.startswith("test"):
                    continue
                seen, todo, reach = set(), [node, *setup], []
                while todo:
                    n = todo.pop()
                    reach.append(ast.get_source_segment(src, n) or "")
                    for c in ast.walk(n):
                        if isinstance(c, ast.Call):
                            f = c.func
                            name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
                            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id in ("self", "cls"):
                                target = ms.get(name)
                            else:
                                target = funcs.get(name) if isinstance(f, ast.Name) else None
                            if target is not None and (target.name, id(target)) not in seen:
                                seen.add((target.name, id(target)))
                                todo.append(target)
                body = "\n".join(reach)
                calls = {kind for kind, rx in PY_CALLS if re.search(rx, body)}
                out.append({"file": str(path.relative_to(root)), "name": f"{cname}.{mname}", "line": node.lineno,
                            "calls": sorted(calls)})
    return out


# --- what past runs say ---------------------------------------------------------------------------------------------

RUNNING = re.compile(r"Running (?:unittests )?(\S+?\.rs)\b")
RESULT = re.compile(r"test result: \w+\. (\d+) passed; (\d+) failed; (\d+) ignored; \d+ measured; (\d+) filtered out;"
                    r" finished in ([\d.]+)s")
TEST_LINE = re.compile(r"^test (\S+) \.\.\. (ok|FAILED|ignored)")
OVER_60 = re.compile(r"test (\S+) has been running for over 60 seconds")


def cargo_sections(text: str, command: str = "") -> list[dict]:
    """The cargo test output in TEXT, a section per binary: its binary, the tests it names, how many ran (passed or
    failed), how many it filtered out, its time, and the tests that ran over 60 s."""
    single = re.findall(r"--test[ =](\w+)", command)
    out, cur, names, over = [], None, [], []
    for line in text.splitlines():
        line = line.strip()
        if m := RUNNING.search(line):
            cur, names, over = m[1].removeprefix("lib/"), [], []
        elif m := TEST_LINE.match(line):
            if m[2] != "ignored":
                names.append(m[1])
        elif m := OVER_60.search(line):
            over.append(m[1])
        elif m := RESULT.search(line):
            binary = cur or (f"tests/{single[0]}.rs" if len(single) == 1 else None)
            if binary:
                out.append({"binary": binary, "names": names, "ran": int(m[1]) + int(m[2]), "ignored": int(m[3]),
                            "filtered": int(m[4]), "seconds": float(m[5]), "over_60": over})
            cur, names, over = None, [], []
    return out


PY_RAN = re.compile(r"^Ran (\d+) tests? in ([\d.]+)s", re.M)


def python_runs(command: str, text: str, root: Path = ROOT, known: dict | None = None) -> list[dict]:
    """A Python test run of one file, or of one test, in COMMAND: its file, the test if one, how many ran, its time."""
    m = PY_RAN.search(text)
    cwd = ""
    if mc := re.match(r"\s*cd\s+(\S+)\s*&&\s*", command):
        cwd, command = mc[1], command[mc.end():]
    if not m or len(PY_RAN.findall(text)) > 1:
        return []
    try:
        words = shlex.split(command, comments=True)
    except ValueError:
        words = command.split()
    words = [w.strip(";&|()") for w in words]
    files = [w for w in words if re.search(r"(?:^|/)test_\w+\.py$", w)]
    dotted = [w for w in words if re.fullmatch(r"(?:\w+\.)*test_\w+(?:\.\w+)*", w) and not w.endswith(".py")]
    found = []
    for f in files:
        p = Path(f) if f.startswith("/") else root / cwd / f
        try:
            rel = str(p.resolve().relative_to(root.resolve()))
        except ValueError:
            continue
        if not (root / rel).exists() and known and len(known.get(Path(f).name, [])) == 1:
            rel = known[Path(f).name][0]  # run from another directory: the one test file of that name
        found.append((rel, None))
    for d in dotted:
        parts = d.split(".")
        k = next((i for i, p in enumerate(parts) if p.startswith("test_")), None)
        if k is None:
            continue
        mod = "/".join(parts[:k + 1]) + ".py"
        for base in (root / cwd, root / cwd / "examples" / "tools"):
            if (base / mod).exists():
                rest = ".".join(parts[k + 1:])
                found.append((str((base / mod).resolve().relative_to(root.resolve())), rest or None))
                break
    if len(set(found)) != 1:
        return []
    rel, test = found[0]
    return [{"file": rel, "test": test, "ran": int(m[1]), "seconds": float(m[2])}]


def session_evidence(root: Path = ROOT, fetch: bool = False, exclude=()) -> tuple[list[dict], list[dict], list[str]]:
    """Cargo sections and Python runs from every loop session's redacted log tool_time.py finds, each with its source
    `log:SHA256`, and the sessions with no log here."""
    sys.path.insert(0, str(TOOLS))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import tool_time
    from test_costs import python_test_files
    known: dict[str, list[str]] = {}
    for p in python_test_files(root):
        known.setdefault(p.name, []).append(str(p.relative_to(root)))
    cargo, python, missing = [], [], []
    for sid, brief in sorted(tool_time.discover(root).items()):
        if brief in exclude:
            continue
        entries = tool_time.load_entries(root, sid, fetch)
        if entries is None:
            missing.append(sid)
            continue
        sha = json.loads((root / "llm-dlc" / "traces" / sid / "manifest.json").read_text())["log"]["sha256"]
        for c in tool_time.read_calls(entries):
            text, command = c["text"], (c["input"] or {}).get("command") or ""
            if "test result:" in text or "running for over 60" in text:
                for s in cargo_sections(text, command):
                    cargo.append({**s, "source": f"log:{sha}"})
            if "Ran " in text and c["name"] == "Bash":
                for r in python_runs(command, text, root, known):
                    python.append({**r, "source": f"log:{sha}"})
    return cargo, python, missing


def job_evidence(root: Path = ROOT) -> list[dict]:
    """Cargo sections from every past job's step logs, each with its source `job:ID`."""
    out = []
    for result in sorted((root / "verification" / "results").glob("*/result.json")):
        r = json.loads(result.read_text())
        for step in r.get("steps") or []:
            log = (step.get("log") or {}).get("path")
            if not log or not (result.parent / log).exists():
                continue
            text = (result.parent / log).read_text(errors="replace")
            for s in cargo_sections(text, step.get("run") or ""):
                out.append({**s, "source": f"job:{r['id']}"})
    return out


# --- putting them together ------------------------------------------------------------------------------------------

def _source_order(source: str) -> tuple:
    return (source.startswith("job:"), source)


def rust_evidence(tests: list[dict], sections: list[dict]) -> dict:
    """(binary, name) -> what the sections say of that test: `single` [(s, source)], `over_60` [source],
    `bound` (s, source), the least time of a section it ran in."""
    by_binary: dict[str, list[dict]] = {}
    for t in tests:
        by_binary.setdefault(t["binary"], []).append(t)
    out = {(t["binary"], t["name"]): {"single": [], "over_60": [], "bound": None} for t in tests}
    for s in sections:
        mine = by_binary.get(s["binary"], [])
        known = {t["name"] for t in mine}
        for name in s["over_60"]:
            if name in known:
                out[(s["binary"], name)]["over_60"].append(s["source"])
        names = [n for n in s["names"] if n in known]
        if s["ran"] == 1 and len(s["names"]) == 1:
            if names:
                out[(s["binary"], names[0])]["single"].append((s["seconds"], s["source"]))
            continue
        if not s["ran"]:
            continue
        if names:
            ran = names
        elif s["filtered"] == 0 and not s["names"]:
            ran = [t["name"] for t in mine if s["ignored"] == 0 or t["ignore"] is None]
        else:
            ran = []
        for name in ran:
            e = out[(s["binary"], name)]
            if e["bound"] is None or s["seconds"] < e["bound"][0]:
                e["bound"] = (s["seconds"], s["source"])
    return out


def python_evidence(tests: list[dict], runs: list[dict]) -> dict:
    by_file: dict[str, list[dict]] = {}
    for t in tests:
        by_file.setdefault(t["file"], []).append(t)
    out = {(t["file"], t["name"]): {"single": [], "over_60": [], "bound": None} for t in tests}
    for r in runs:
        mine = by_file.get(r["file"], [])
        if r["test"] and r["ran"] == 1:
            hit = [t for t in mine if t["name"] == r["test"] or t["name"].endswith("." + r["test"])]
            if len(hit) == 1:
                out[(r["file"], hit[0]["name"])]["single"].append((r["seconds"], r["source"]))
            continue
        if r["test"]:
            ran = [t for t in mine if t["name"] == r["test"] or t["name"].startswith(r["test"] + ".")]
        elif r["ran"] * 2 >= len(mine):
            ran = mine
        else:
            ran = []
        for t in ran:
            e = out[(r["file"], t["name"])]
            if e["bound"] is None or r["seconds"] < e["bound"][0]:
                e["bound"] = (r["seconds"], r["source"])
    return out


def cost(e: dict) -> dict:
    """What a test's evidence says it costs, and from where."""
    if e["single"]:
        times = [s for s, _ in e["single"]]
        sources = sorted({src for _, src in e["single"]}, key=_source_order, reverse=True)
        return {"seconds": round(statistics.median(times), 2), "kind": "run alone", "runs": len(times),
                "max_seconds": round(max(times), 2), "sources": sources[:3]}
    if e["over_60"]:
        return {"seconds": 60, "kind": "over 60 s", "runs": len(e["over_60"]),
                "sources": sorted(set(e["over_60"]), key=_source_order, reverse=True)[:3]}
    if e["bound"]:
        return {"seconds": round(e["bound"][0], 2), "kind": "at most", "sources": [e["bound"][1]]}
    return {"seconds": None, "kind": "estimated", "sources": []}
