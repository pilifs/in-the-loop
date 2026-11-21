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
import functools
import json
import re
import shlex
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _verification_layout():
    """verification/layout.py: where a job and its result are kept, by id (flat, or under the day it was submitted)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("verification_layout", Path(__file__).resolve().parents[2] / "verification" / "layout.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


layout = _verification_layout()
LIB = ROOT / "lib"
TOOLS = ROOT / "llm-dlc" / "tools"


# --- reading Rust ---------------------------------------------------------------------------------------------------

# What starts a comment or a literal. A raw string's `r` must not end an identifier (`for"` is no raw string).
_OPENER = re.compile(r"//|/\*|(?<!\w)b?r(#*)\"|\"|'")
_COMMENT_END = re.compile(r"/\*|\*/")
_STRING_BODY = re.compile(r'[^"\\]*(?:\\.[^"\\]*)*', re.S)
_CHAR = re.compile(r"'(?:\\(?:u\{[0-9a-fA-F]+\}|x[0-9a-fA-F]{2}|.)|[^\\'])'")
_NOT_NEWLINE = re.compile(r"[^\n]")


@functools.lru_cache(maxsize=512)
def blank(src: str, strings: bool = True) -> str:
    """SRC with comments (and, if STRINGS, the contents of string and char literals) replaced by spaces, newlines
    kept, so that positions and line numbers stay the same and braces inside them don't count. Cached: the lint
    reads each file several times."""
    parts, kept, i, n = [], 0, 0, len(src)

    def wipe(a, b):
        nonlocal kept
        parts.append(src[kept:a])
        parts.append(_NOT_NEWLINE.sub(" ", src[a:b]))
        kept = b

    while (m := _OPENER.search(src, i)):
        i, tok = m.start(), m[0]
        if tok == "//":
            j = src.find("\n", i)
            j = n if j < 0 else j
            wipe(i, j)
            i = j
        elif tok == "/*":
            depth, j = 1, i + 2
            while depth and (c := _COMMENT_END.search(src, j)):
                depth, j = depth + (1 if c[0] == "/*" else -1), c.end()
            j = j if not depth else n
            wipe(i, j)
            i = j
        elif tok.endswith('"') and tok != '"':  # a raw string: no escapes, it ends at `"` and its hashes
            end = src.find('"' + m[1], m.end())
            end = n if end < 0 else end
            if strings:
                wipe(m.end(), end)
            i = end + 1 + len(m[1])
        elif tok == '"':
            j = _STRING_BODY.match(src, i + 1).end()
            j = j if j < n and src[j] == '"' else n
            if strings:
                wipe(i + 1, j)
            i = j + 1
        else:
            c = _CHAR.match(src, i)
            if c:
                if strings:
                    wipe(i + 1, c.end() - 1)
                i = c.end()
            else:
                i += 1  # a lifetime
    parts.append(src[kept:])
    return "".join(parts)


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


_QUALIFIER = re.compile(r"(?:\bpub(?:\([^)]*\))?|\basync|\bunsafe|\bconst|\bextern\s*\"?\w*\"?)$")


def _attributes(src: str, code: str, at: int) -> list[str]:
    """The outer attributes (`#[...]`, as written) before the item starting at AT, nearest last."""
    attrs, i = [], at
    while True:
        j = i
        while j > 0 and code[j - 1].isspace():
            j -= 1
        w = max(0, j - 200)
        m = _QUALIFIER.search(code[w:j])
        if m and j:
            i = w + m.start()
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


@functools.lru_cache(maxsize=1024)
def rust_items(src: str, prefix: tuple[str, ...] = ()) -> list[dict]:
    """Every `fn` of a Rust file outside another fn's body: its path (module path within the file, under PREFIX, and
    its name), its attributes, and its body's span. Modules declared with `mod x;` are listed as `{"mod": x}`.
    Cached, so the list is shared: don't change it."""
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


@functools.lru_cache(maxsize=None)
def _kinds(text: str) -> frozenset[str]:
    """The RUST_CALLS kinds TEXT (a fn, comments blanked) shows, and `default jbmc` and `native` for
    RUST_DEFAULT_JBMC and RUST_NATIVE. A test's are the union of its own and its helpers'."""
    found = {kind for kind, rx in RUST_CALLS if re.search(rx, text)}
    return frozenset(found | {k for k, rx in (("default jbmc", RUST_DEFAULT_JBMC), ("native", RUST_NATIVE))
                              if re.search(rx, text)})


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
        texts: dict[str, list[tuple[str, str]]] = {}  # fn name: (its text with comments blanked, and strings too)
        for s, items in sources:
            nc, code = blank(s, strings=False), blank(s)
            for it in items:
                if "fn" in it:
                    span = slice(it["start"], it["body"][1])
                    texts.setdefault(it["fn"], []).append((nc[span], code[span]))
        nc, code = blank(src, strings=False), blank(src)
        for it in sources[0][1]:
            if not it.get("test"):
                continue
            span = slice(it["start"], it["body"][1])
            seen, todo, reach = {it["fn"]}, [(nc[span], code[span])], []
            while todo:
                text, text_code = todo.pop()
                reach.append(text)
                for name in _calls(text_code) - seen - NOT_FOLLOWED:
                    if name in texts:
                        seen.add(name)
                        todo += texts[name]
            found = set().union(*(_kinds(text) for text in reach))
            calls = found - {"default jbmc", "native"}
            if "default jbmc" in found and "native" not in found:
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

# A call, not a mention: a test that patches `subprocess.run` away, refuses `Popen`, or builds a
# `subprocess.CompletedProcess` for a mock to return spawns nothing.
PY_CALLS = [
    ("process", r"\bsubprocess\.(?:run|Popen|call|check_call|check_output|getoutput|getstatusoutput)\("
                r"|(?<![\w.])Popen\(|\bos\.(?:system|popen|posix_spawnp?|exec\w*|spawn\w*)\("
                r"|\bcreate_subprocess_(?:exec|shell)\("),
    ("network", r"\burllib\.request\.urlopen\(|\bhttp\.client\.\w+\(|\bsocket\.(?:socket|create_connection)\("),
    # Counted only beside a process call: a test that names JBMC or TLC to check a plan, a command line or a mock's
    # arguments runs neither. The modules under test (build.py's runners) aren't followed.
    ("jbmc", r"\b(?:run|Popen|call|check_call|check_output)\(\s*\[\s*[\"'](?:jbmc|cbmc)[\"']"),
    ("tlc", r"\btlc2\.TLC\b|\btla2tools\.jar\b"),
]
PY_PROOF_CALLS = {"jbmc", "tlc"}


class PyModule:
    """A parsed Python file: its source, lines, functions and classes by name, and what it imports by local name
    (`{name: (module, attribute or None)}`), so that a TestCase base imported from another file can be followed."""

    def __init__(self, path: Path | None, src: str | None = None):
        self.path = path
        self.src = path.read_text() if src is None else src
        self.tree = ast.parse(self.src)
        self.lines = self.src.split("\n")
        body = self.tree.body
        self.funcs = {n.name: n for n in body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        self.classes = {n.name: n for n in body if isinstance(n, ast.ClassDef)}
        self.imports = {}
        for n in body:
            if isinstance(n, ast.Import):
                for a in n.names:
                    self.imports[a.asname or a.name.split(".")[0]] = (a.name if a.asname else a.name.split(".")[0], None)
            elif isinstance(n, ast.ImportFrom) and not n.level and n.module:
                for a in n.names:
                    self.imports[a.asname or a.name] = (n.module, a.name)

    def segment(self, node) -> str:
        """The lines of NODE's source."""
        return "\n".join(self.lines[node.lineno - 1:node.end_lineno])

    def module(self, dotted: str, root: Path) -> "PyModule | None":
        """The repository file DOTTED names, imported as this file's directory or an ancestor up to ROOT would
        import it (a test file puts its package's parent on sys.path), or None."""
        if self.path is None:
            return None
        rel = Path(*dotted.split("."))
        for d in [self.path.parent, *self.path.parents]:
            for f in (d / rel.with_suffix(".py"), d / rel / "__init__.py"):
                if f.is_file():
                    return _py_module(f.resolve())
            if d == root:
                break
        return None

    def base(self, expr, root: Path) -> "tuple[PyModule, ast.ClassDef] | None":
        """The class a base expression of a class here names, in this file or a repository file it imports."""
        if isinstance(expr, ast.Name):
            if expr.id in self.classes:
                return self, self.classes[expr.id]
            module, attr = self.imports.get(expr.id, (None, None))
            other = self.module(module, root) if attr else None
            return (other, other.classes[attr]) if other and attr in other.classes else None
        if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name):
            module, attr = self.imports.get(expr.value.id, (None, None))
            if module is None:
                return None
            other = self.module(f"{module}.{attr}" if attr else module, root)
            return (other, other.classes[expr.attr]) if other and expr.attr in other.classes else None
        return None


def _py_module(path: Path) -> PyModule:
    st = path.stat()
    return _py_module_as_of(path, st.st_mtime_ns, st.st_size)


@functools.lru_cache(maxsize=None)
def _py_module_as_of(path: Path, _mtime_ns: int, _size: int) -> PyModule:
    return PyModule(path)


def python_cases(mod: PyModule, root: Path = ROOT):
    """Each test method of a parsed test file, inherited ones once per TestCase that has them, bases imported from
    another repository file included: (class name, class node, method name, method node, the class's methods by name
    as {name: (module, node)})."""
    def methods(m, cls, seen=()):
        own = {n.name: (m, n) for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        for b in cls.bases:
            found = m.base(b, root)
            if found and (key := (id(found[0]), found[1].name)) not in seen:
                own = {**methods(*found, seen + (key,)), **own}
        return own

    def is_case(m, cls, seen=()):
        for b in cls.bases:
            name = b.id if isinstance(b, ast.Name) else b.attr if isinstance(b, ast.Attribute) else None
            if name in ("TestCase", "IsolatedAsyncioTestCase"):
                return True
            found = m.base(b, root)
            if found and (key := (id(found[0]), found[1].name)) not in seen and is_case(*found, seen + (key,)):
                return True
        return False

    for cname, cls in mod.classes.items():
        if not is_case(mod, cls):
            continue
        ms = methods(mod, cls)
        for mname, (_m, node) in ms.items():
            if mname.startswith("test"):
                yield cname, cls, mname, node, ms


def _cost_decorator(d) -> str | None:
    """The tag of a decorator node if it is `@cost("...")` or `@cost("...", "reason")`, or None."""
    if (isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == "cost" and 1 <= len(d.args) <= 2
            and isinstance(d.args[0], ast.Constant)):
        return d.args[0].value
    return None


def cost_tag(node) -> str | None:
    """The tag of a `@cost("...")` decorator on a function or class node, or None."""
    return next((t for d in node.decorator_list if (t := _cost_decorator(d)) is not None), None)


def cost_reason(node) -> str | None:
    """The reason of a `@cost(tag, "reason")` decorator on a function or class node, or None."""
    for d in node.decorator_list:
        if _cost_decorator(d) is not None:
            reason = d.args[1] if len(d.args) > 1 else next((k.value for k in d.keywords if k.arg == "reason"), None)
            return reason.value if isinstance(reason, ast.Constant) and isinstance(reason.value, str) else None
    return None


def unconditional_skip(node) -> str | None:
    """The reason of an `@unittest.skip(...)` (or `@skip(...)`) decorator on a function or class node, or None. A
    `skipIf`/`skipUnless` on a missing tool is no cost tag, and isn't returned."""
    for d in node.decorator_list:
        f = d.func if isinstance(d, ast.Call) else d
        if (isinstance(f, ast.Attribute) and f.attr == "skip") or (isinstance(f, ast.Name) and f.id == "skip"):
            arg = d.args[0] if isinstance(d, ast.Call) and d.args else None
            return arg.value if isinstance(arg, ast.Constant) else ""
    return None


def python_tests(root: Path = ROOT, files=None) -> list[dict]:
    """Every Python test method: file, name (Class.method), line, what it calls, and its `@cost` tag."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_costs import python_test_files
    out = []
    for path in files if files is not None else python_test_files(root):
        mod = _py_module(Path(path).resolve())
        for cname, cls, mname, node, ms in python_cases(mod, root):
            setup = [ms[k] for k in ("setUp", "setUpClass", "tearDown", "asyncSetUp") if k in ms]
            setup += [(mod, mod.funcs[k]) for k in ("setUpModule",) if k in mod.funcs]
            seen, todo, reach = set(), [(ms[mname][0], node), *setup], []
            while todo:
                m, n = todo.pop()
                reach.append(m.segment(n))
                for c in ast.walk(n):
                    if isinstance(c, ast.Call):
                        f = c.func
                        name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
                        if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id in ("self", "cls"):
                            target = ms.get(name)
                        else:
                            target = (m, m.funcs[name]) if isinstance(f, ast.Name) and name in m.funcs else None
                        if target is not None and id(target[1]) not in seen:
                            seen.add(id(target[1]))
                            todo.append(target)
            body = "\n".join(reach)
            calls = {kind for kind, rx in PY_CALLS if re.search(rx, body)}
            if "process" not in calls:
                calls -= PY_PROOF_CALLS
            out.append({"file": str(Path(path).resolve().relative_to(root)), "name": f"{cname}.{mname}",
                        "line": node.lineno, "calls": sorted(calls), "cost": cost_tag(node) or cost_tag(cls),
                        "reason": cost_reason(node) if cost_tag(node) else cost_reason(cls),
                        "skip": unconditional_skip(node) if unconditional_skip(node) is not None
                        else unconditional_skip(cls)})
    return out


# --- the `@cost` decorator in the Python tests ----------------------------------------------------------------------

COST_IMPORT = ('sys.path.append(str(Path(__file__).resolve().parents[{depth}] / "lib/tools"))\n'
               'from cost_tier import cost  # noqa: E402\n')
COST_IMPORT_RX = re.compile(r'sys\.path\.append\(str\(Path\(__file__\)\.resolve\(\)\.parents\[\d+\] / "lib/tools"\)\)\n'
                            r'from cost_tier import cost  # noqa: E402\n')
_RANK = (None, "tool", "pending", "proof")


def _lines(src: str) -> list[str]:
    """SRC's lines with their ends, split at newlines alone, as `ast` counts them (`str.splitlines` also splits at a
    form feed or a line separator in a string)."""
    return re.findall(r"[^\n]*\n|[^\n]+$", src)


def wanted_cost_tag(row: dict | None) -> str | None:
    """The `@cost` tag a Python test's inventory row asks for: `pending` for `retier: pending`, `proof` for a test
    the default run skips as proof tier, `tool` for the tool tier, None for the unit tier (and a test the inventory
    doesn't list)."""
    if row is None or row["tier"] == "unit":
        return None
    if row.get("ignored") is not None:
        return "proof"
    return "pending" if row.get("retier") == "pending" else "tool"


def cost_decorators(src: str, rel: str, rows: dict, root: Path | None = ROOT) -> tuple[str, int]:
    """SRC with each test method decorated `@cost(...)` as its row in ROWS ({Class.method: row}) asks for, and no
    other, and the import of `cost` present exactly when a decorator is: (new source, test methods changed). A
    method a base class gives several TestCases takes the highest tag they ask for. REL is the file's path from the
    repository root."""
    mod = PyModule(root / rel if root else None, src)
    want, nodes = {}, {}
    for cname, _cls, mname, node, ms in python_cases(mod, root or ROOT):
        if ms[mname][0] is not mod:
            continue  # a test method another file defines is tagged there
        w = wanted_cost_tag(rows.get(f"{cname}.{mname}"))
        nodes[id(node)] = node
        want[id(node)] = max(want.get(id(node)), w, key=_RANK.index)
    lines = _lines(src)
    edits, changed = [], 0  # (first line, lines removed, text inserted), 0-based, applied from the end
    for key, node in nodes.items():
        have = [d for d in node.decorator_list if _cost_decorator(d) is not None]
        w = want[key]
        if w is None and not have or len(have) == 1 and cost_tag(node) == w:
            continue
        changed += 1
        edits += [(d.lineno - 1, d.end_lineno - d.lineno + 1, "") for d in have]
        if w is not None:
            first = min([d.lineno for d in node.decorator_list] + [node.lineno]) - 1
            edits.append((first, 0, " " * node.col_offset + f'@cost("{w}")\n'))
    for first, n, text in sorted(edits, key=lambda e: (e[0], -e[1]), reverse=True):
        lines[first:first + n] = [text] if text else []
    src = "".join(lines)
    tagged = any(cost_tag(n) is not None for n in ast.walk(ast.parse(src))
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)))
    block = COST_IMPORT_RX.search(src)
    if block and not tagged:
        src = src[:block.start()] + src[block.end():]
    elif tagged and not block:
        tree = ast.parse(src)
        imported = {a.asname or a.name for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))
                    for a in n.names}
        if not {"sys", "Path"} <= imported:
            raise SystemExit(f"{rel}: import sys and pathlib's Path at the top, for the import of `cost`")
        last = max(n.end_lineno for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom)))
        lines = _lines(src)
        lines.insert(last, COST_IMPORT.format(depth=len(Path(rel).parts) - 1))
        src = "".join(lines)
    return src, changed


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
                try:
                    found.append((str((base / mod).resolve().relative_to(root.resolve())), rest or None))
                except ValueError:
                    pass  # run in a folder outside the checkout (an export of another line): not this tree's test
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
    for result in (folder / "result.json" for folder in layout.results(root).values()):
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
