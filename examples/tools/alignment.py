#!/usr/bin/env python3
"""The ground truth for alignment inference: step A1 of `llm-dlc/loops/foundations-alignment.md`.

`alignment/ground-truth.json` holds the mappings people wrote by hand for the regression examples 121-139: which old
method the new one replaces (`--before-target`), the old version's arguments as expressions over the new one's
(`--before-arguments`), and how the results relate (`--results-agree-when`). Each is broken into parts, one per old
input, new input without a counterpart, method and result, and each part says whether something outside the method
fixes it (an anchored part, which inference must leave as it is) or it relates internal representations (which
inference may propose). Every later step of alignment inference is scored against it.

  python3 examples/tools/alignment.py check               # the table agrees with every example.json's flags
  python3 examples/tools/alignment.py check --signatures  # and with the compiled classes (javac and javap, ~20 s)
  python3 examples/tools/alignment.py signatures 128      # an example's two signatures, as the check reads them
  python3 examples/tools/alignment.py render              # rewrite the table in alignment/README.md
  python3 examples/tools/alignment.py score               # run `jvmcontract align` on every example and score it
  python3 examples/tools/alignment.py score --record      # and keep the score in alignment/scores/, for the page
  python3 examples/tools/alignment.py score --step proofs --record   # each proposal proved (a verification job)

What each field means is in alignment/README.md.
"""
import argparse
import datetime
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
TRUTH = HERE / "alignment" / "ground-truth.json"
PAGE = HERE / "alignment" / "README.md"
SCORES = HERE / "alignment" / "scores"

# The vocabulary of the table. An input part's anchor, a result part's relation, and who decides a part.
ANCHORS = {
    "anchored": "the same parameter in both versions (name and type): its mapping is fixed to itself",
    "internal": "a representation that changed: inference may propose how the two relate",
    "new": "a new input with no old counterpart: left free by the mapping; restricting it is a person's decision",
}
RESULTS = {
    "equal": "the result compared by equality, as the contract requires",
    "components": "a record result whose every old component is compared with the same-named new one",
    "changed": "a result whose meaning changed: the relation is a person's decision",
}
DECIDES = {"infer", "person"}
PART_KINDS = {"method", "input", "new-input", "result"}


def load(path=TRUTH):
    return json.loads(Path(path).read_text())


def example_dir(example_id):
    found = sorted(REPO.glob(f"examples/{example_id}-*/example.json"))
    if len(found) != 1:
        raise SystemExit(f"example {example_id}: {len(found)} folders")
    return found[0].parent


def example_json(example_id):
    return json.loads((example_dir(example_id) / "example.json").read_text())


def flags_of(example):
    """The hand-written mapping of an example, as its example.json gives it to the tool."""
    change = example["change"]
    return {k: change[k] for k in ("previousSymbol", "previousArguments", "resultsAgreeWhen") if change.get(k)}


def inputs_of(sig):
    """A version's inputs in the order `--before-arguments` gives them: the receiver `this` of an instance method
    first, then the parameters."""
    return ([] if sig["static"] else ["this"]) + [name for name, _ in sig["parameters"]]


def flags_from_parts(entry):
    """The flags an entry's parts amount to: what a person would have to write, and the tool's defaults left out (the
    same symbol, the arguments by position, the results compared by equality)."""
    flags = {}
    method = [p for p in entry["parts"] if p["kind"] == "method"]
    if method:
        flags["previousSymbol"] = method[0]["old"]
    inputs = [p for p in entry["parts"] if p["kind"] == "input"]
    before, after = inputs_of(entry["before"]), inputs_of(entry["after"])
    if [p["old"] for p in inputs] != before:
        raise ValueError(f"{entry['example']}: the input parts are not the old inputs in order ({', '.join(before)})")
    by_position = len(before) == len(after) and all(p["new"] == a for p, a in zip(inputs, after))
    if not by_position:
        flags["previousArguments"] = ", ".join(p["new"] for p in inputs)
    result = [p for p in entry["parts"] if p["kind"] == "result"]
    if len(result) != 1:
        raise ValueError(f"{entry['example']}: one result part, not {len(result)}")
    if result[0]["relation"] != "equal":
        flags["resultsAgreeWhen"] = result[0]["holds"]
    return flags


def problems(entry, example):
    """What is wrong with an entry, against its example.json: an empty list when it agrees."""
    out = []
    eid = entry["example"]
    for p in entry["parts"]:
        if p["kind"] not in PART_KINDS:
            out.append(f"{eid}: unknown part kind {p['kind']}")
        if p.get("decide") not in DECIDES:
            out.append(f"{eid}: part {p.get('old') or p.get('new')}: decide is infer or person")
        if p["kind"] == "method" and p.get("how") not in ("renamed", "moved"):
            out.append(f"{eid}: method {p['old']}: how is renamed or moved")
        if p["kind"] == "input" and p.get("anchor") not in ("anchored", "internal"):
            out.append(f"{eid}: input {p['old']}: anchor is anchored or internal")
        if p["kind"] == "input" and p.get("anchor") == "anchored" and p["new"] != p["old"]:
            out.append(f"{eid}: input {p['old']} is anchored, so it maps to itself, not {p['new']}")
        if p["kind"] == "new-input" and p.get("anchor") != "new":
            out.append(f"{eid}: new input {p['new']}: anchor is new")
        if p["kind"] == "result" and p.get("relation") not in RESULTS:
            out.append(f"{eid}: result relation {p.get('relation')}")
        if p["kind"] == "result" and p.get("relation") == "changed" and p.get("decide") != "person":
            out.append(f"{eid}: a changed result is a person's decision")
        if not p.get("why"):
            out.append(f"{eid}: part {p.get('old') or p.get('new')} says why")
    try:
        mine = flags_from_parts(entry)
    except ValueError as e:
        return out + [str(e)]
    theirs = flags_of(example)
    if mine != theirs:
        out.append(f"{eid}: the parts amount to {mine}, the example's flags are {theirs}")
    if entry["verdict"] != example["expected"]["verdict"]:
        out.append(f"{eid}: verdict {entry['verdict']}, the example expects {example['expected']['verdict']}")
    scope = example["change"].get("intendedInputs")
    if entry.get("scope") != scope:
        out.append(f"{eid}: scope {entry.get('scope')!r}, the example declares {scope!r}")
    before = flags_of(example).get("previousSymbol") or example["subject"]["symbol"]
    if entry["before"]["symbol"] != before or entry["after"]["symbol"] != example["subject"]["symbol"]:
        out.append(f"{eid}: the symbols are not the example's")
    return out


# The compiled signatures, read with javap from the classes build.py compiles (`-parameters -g`).

def javap(classes, cls, *flags):
    proc = subprocess.run(["javap", *flags, "-cp", str(classes), cls], capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"javap {cls}: {proc.stderr}")
    return proc.stdout


def signature(classes, symbol):
    """A method's signature in compiled classes: whether it is static, its parameters (name, type), its return type,
    and for an instance method of a record, the receiver's components (name, type)."""
    cls, name = symbol.split("#")
    text = javap(classes, cls, "-p", "-v")
    header = re.compile(rf"^  (?P<mods>(?:\w+ )*)(?P<ret>[\w.$\[\]]+) {re.escape(name)}\((?P<params>[^)]*)\);$", re.M)
    found = list(header.finditer(text))
    if len(found) != 1:
        raise SystemExit(f"{symbol}: {len(found)} methods of that name")
    m = found[0]
    types = [t.strip() for t in m["params"].split(",") if t.strip()]
    body = text[m.end():]
    nxt = re.search(r"^  \S", body, re.M)
    body = body[: nxt.start()] if nxt else body
    names = []
    mp = re.search(r"MethodParameters:\n\s+Name\s+Flags\n((?:\s{6}\S.*\n?)*)", body)
    if mp:
        names = [line.split()[0] for line in mp.group(1).splitlines() if line.strip()]
    if len(names) != len(types):
        raise SystemExit(f"{symbol}: {len(types)} parameters but {len(names)} names (compiled without -parameters?)")
    static = "static" in m["mods"].split()
    out = {"symbol": symbol, "static": static, "parameters": [[n, t] for n, t in zip(names, types)], "returns": m["ret"]}
    if not static:
        plain = javap(classes, cls, "-p")
        if re.search(r"extends java\.lang\.Record\b", plain):
            out["receiver"] = [[f.group(2), f.group(1)] for f in re.finditer(r"^  private final ([\w.$\[\]]+) (\w+);$", plain, re.M)]
    return out


def versions(example):
    """Compiles an example's two versions as build.py does: the module unpatched, and patched. Returns (before, after)
    class directories."""
    sys.path.insert(0, str(HERE))
    import build
    app = build.app_of(example)
    root = build.scratch() / f"alignment-{example['id']}"
    part = build.TOOL_APPS[app]["root"]
    shutil.copytree(REPO / part, root / part, ignore=build.IGNORE)
    build.apply_patch((example_dir(example["id"]) / example["change"]["patch"]).read_text(), root)
    after = build.tool_compile(app, root, tests=False)[0]
    return build.tool_before_classes(app), after


def signatures(example):
    before, after = versions(example)
    symbol = example["subject"]["symbol"]
    return signature(before, example["change"].get("previousSymbol") or symbol), signature(after, symbol)


def signature_problems(entry, sigs):
    out = []
    for version, sig in zip(("before", "after"), sigs):
        mine = {k: entry[version].get(k) for k in ("symbol", "static", "parameters", "returns", "receiver") if k in entry[version] or k in sig}
        if mine != sig:
            out.append(f"{entry['example']} {version}: the table says {mine}, the classes {sig}")
    return out


# Scoring.

OUTCOMES = ("found", "asked", "wrong", "missed")


def bare(symbol):
    """`pkg.Class#name(int, long)` as the table names it, `pkg.Class#name`."""
    return symbol.split("(")[0]


def short(symbol):
    """`Class#name`, without the package, in backticks."""
    head, _, tail = symbol.partition("#")
    return f"`{head.rsplit('.', 1)[-1]}#{tail}`"


def align(before, after, prove=None):
    """`jvmcontract align` on two class directories; with `prove`, an example, also `--prove` for its subject, under
    the scope and the proof options build.py gives the example's own proof."""
    sys.path.insert(0, str(HERE))
    import build
    extra = []
    if prove is not None:
        extra = ["--prove", "--subject", prove["subject"]["symbol"]] + build.proof_options(prove)
        if prove["change"].get("intendedInputs"):
            extra += ["--unchanged-unless", prove["change"]["intendedInputs"]]
    out = subprocess.run([str(build.jvmcontract()), "align", "--before", str(before), "--after", str(after), "--json", *extra],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def score_method(entry, report):
    """Step A2's score for an example: its method part, or, where the method kept its name, the method itself, which
    must be the only proposal (or no hint, when the method's own code is unchanged). Returns (scored, outcome, what was
    proposed)."""
    old, new = entry["before"]["symbol"], entry["after"]["symbol"]
    part = next((p for p in entry["parts"] if p["kind"] == "method"), None)
    scored = f"method {part['how']}" if part else "method kept its name"
    match = next((m for m in report["methods"] if bare(m["before"]) == old), None)
    if match is None:
        return (scored, "found", "no hint: its code is unchanged") if part is None else (scored, "missed", "reported unchanged")
    candidates = [bare(c["after"]) for c in match["candidates"]]
    shown = ", ".join(f"{short(x['after'])} ({x['score']})" for x in match["candidates"])
    if not candidates:
        return scored, "missed", "no candidate"
    if match["leads"]:
        return scored, "found" if candidates[0] == new else "wrong", f"leads: {shown}"
    return scored, "asked" if new in candidates else "wrong", f"none leads: {shown}"


def score_methods(truth, reports=None):
    rows = []
    for entry in truth["examples"]:
        example = example_json(entry["example"])
        report = reports[entry["example"]] if reports else align(*versions(example))
        scored, outcome, proposed = score_method(entry, report)
        others = [m for m in report["methods"] if bare(m["before"]) != entry["before"]["symbol"]]
        rows.append({"example": entry["example"], "part": scored, "table": entry["after"]["symbol"], "outcome": outcome,
                     "proposed": proposed, "otherChanged": sum(m["change"] == "changed" for m in others),
                     "otherVanished": [f"{short(m['before'])} → {short(m['candidates'][0]['after']) if m['leads'] else 'none leads'}"
                                       for m in others if m["change"] == "vanished"]})
    return rows


def norm(expression):
    """An expression without its spacing, and a conjunction as the set of its conjuncts, so that two that differ only
    in spacing or in the order of `&&` compare equal."""
    return frozenset("".join(c.split()) for c in expression.split("&&"))


def find_mapping(entry, report):
    old, new = entry["before"]["symbol"], entry["after"]["symbol"]
    return next((m for m in report.get("mappings", []) if bare(m["before"]) == old and bare(m["after"]) == new), None)


def score_part(part, mapping, unchanged=False):
    """Step A3's score for one input, new-input or result part, against the mapping `align` proposed for the
    example's pair (None if it proposed none). Returns (part label, the table's, outcome, what was proposed)."""
    kind = part["kind"]
    if kind == "input":
        label, table = f"input {part['anchor']}", part["new"]
    elif kind == "new-input":
        label, table = "new input", part["new"]
    else:
        label, table = f"result {part['relation']}", part.get("holds", "equality")
    if mapping is None:
        return (label, table, "found", "no hint: the method is unchanged") if unchanged else (label, table, "missed", "no mapping for the pair")
    complete = not mapping["unsupported"] and all(i["candidates"] for i in mapping["inputs"])
    if kind == "new-input":
        if not complete:
            return label, table, "missed", "no complete mapping"
        return (label, table, "found", "left free") if table in mapping["free"] else (label, table, "wrong", "used by a candidate")
    if kind == "input":
        i = next((x for x in mapping["inputs"] if x["old"] == part["old"]), None)
        if i is None or not i["candidates"]:
            return label, table, "missed", "no candidate" + (f" ({'; '.join(mapping['unsupported'])})" if mapping["unsupported"] else "")
        exprs = [c["expression"] for c in i["candidates"]]
        if i["leads"]:
            outcome = "found" if norm(exprs[0]) == norm(table) and part["decide"] == "infer" else "wrong"
            return label, table, outcome, f"{exprs[0]} ({i['anchor']})"
        return label, table, "asked" if norm(table) in map(norm, exprs) else "wrong", "a question: " + " | ".join(exprs)
    r = mapping["result"]
    exprs = [c["expression"] for c in r["candidates"]]
    if part["relation"] == "equal":
        return (label, table, "found", "equal") if r["kind"] == "equal" else (label, table, "wrong", f"{r['kind']}: {' | '.join(exprs)}")
    if not exprs:
        return label, table, "missed", f"{r['kind']}, no candidate"
    decided = r["inferred"] and len(exprs) == 1
    if decided:
        outcome = "found" if norm(exprs[0]) == norm(table) and part["decide"] == "infer" else "wrong"
        return label, table, outcome, f"{r['kind']}: {exprs[0]}"
    return label, table, "asked" if norm(table) in map(norm, exprs) else "wrong", f"{r['kind']}, a question: " + " | ".join(exprs)


def score_mapping(entry, report):
    """Step A3's rows for an example: one per input, new-input and result part."""
    mapping = find_mapping(entry, report)
    unchanged = mapping is None and entry["before"]["symbol"] == entry["after"]["symbol"] and not any(bare(m["before"]) == entry["before"]["symbol"] for m in report["methods"])
    rows = []
    for part in entry["parts"]:
        if part["kind"] == "method":
            continue
        label, table, outcome, proposed = score_part(part, mapping, unchanged)
        name = part.get("old") or part.get("new") or "result"
        rows.append({"example": entry["example"], "part": label, "table": f"{name}: {table}" if part["kind"] == "input" else table,
                     "outcome": outcome, "proposed": proposed})
    return rows


def score_mappings(truth, reports=None):
    rows = []
    for entry in truth["examples"]:
        report = reports[entry["example"]] if reports else align(*versions(example_json(entry["example"])))
        rows += score_mapping(entry, report)
    return rows


def find_proof(entry, report):
    old, new = entry["before"]["symbol"], entry["after"]["symbol"]
    return next((p for p in report.get("proofs", []) if bare(p["before"]) == old and bare(p["after"]) == new), None)


def squash(flags):
    return {k: "".join(v.split()) for k, v in flags.items() if v}


def score_proof(entry, example, report):
    """Step A3's second half for an example: what the proofs settled for its pair, against the example's verdict.
    A verified example's hand-written mapping should be the one proved (found), or among a question's (asked); a
    violation should leave no mapping proved, its counterexamples shown (found). A proved mapping that is not the
    table's, or any proved mapping of a violation, is wrong, and since a proof accepted it, wrong and accepted.
    Returns (outcome, what was settled, accepted wrongly)."""
    proof, mapping = find_proof(entry, report), find_mapping(entry, report)
    if proof is None or mapping is None:
        return "missed", "no proof: no complete mapping for the pair", False
    want = squash({FLAG_NAMES[k]: v for k, v in flags_of(example).items()})
    flags = lambda i: squash(mapping["proposals"][i]["flags"])
    settled, verified = proof["settled"], entry["verdict"] == "verified"
    tried = len(proof["attempts"])
    if settled["outcome"] == "none-proved":
        return ("missed" if verified else "found"), f"none of {tried} proved", False
    if settled["outcome"] == "asked":
        shown = " | ".join(json.dumps(mapping["proposals"][i]["flags"]) for i in settled["proved"])
        same = any(flags(i) == want for i in settled["proved"])
        return ("asked" if verified and same else "wrong"), f"a question, {len(settled['proved'])} proved of {tried}: {shown}", not verified
    group = [settled["proposal"]] + settled["equivalent"]
    right = verified and any(flags(i) == want for i in group)
    note = f"; {settled['note']}" if settled.get("note") else ""
    collapsed = f", {len(settled['equivalent'])} equivalent collapsed" if settled["equivalent"] else ""
    return ("found" if right else "wrong"), f"#{settled['proposal'] + 1} of {tried} proved{collapsed}: {json.dumps(mapping['proposals'][settled['proposal']]['flags'])}{note}", not right


def score_proofs(truth, reports):
    rows = []
    for entry in truth["examples"]:
        outcome, settled, accepted = score_proof(entry, example_json(entry["example"]), reports[entry["example"]])
        rows.append({"example": entry["example"], "part": f"proof, {entry['verdict']}", "table": json.dumps(flags_of(example_json(entry["example"]))),
                     "outcome": outcome, "proposed": settled, "accepted": accepted,
                     "summary": (find_proof(entry, reports[entry["example"]]) or {}).get("summary", "")})
    return rows


FLAG_NAMES = {"previousSymbol": "before_target", "previousArguments": "before_arguments", "resultsAgreeWhen": "results_agree_when"}


def flags_agree(entry, example, report):
    """Where the example's hand-written flags are among the proposals `align` made for its pair: `proposed` (the one
    proposal), `asked` (among a question's, whose order decides nothing), or `no`."""
    mapping = find_mapping(entry, report)
    want = {FLAG_NAMES[k]: "".join(v.split()) for k, v in flags_of(example).items()}
    if mapping is None:
        unchanged = not want and not any(bare(m["before"]) == entry["before"]["symbol"] for m in report["methods"])
        return "proposed" if unchanged else "no"
    proposed = [{k: "".join(v.split()) for k, v in p["flags"].items()} for p in mapping["proposals"]]
    return "proposed" if proposed == [want] else "asked" if want in proposed else "no"


def tally(rows):
    by = {}
    for r in rows:
        by.setdefault(r["part"], dict.fromkeys(OUTCOMES, 0))[r["outcome"]] += 1
    return by


def record(step, rows, flags=None):
    sys.path.insert(0, str(HERE))
    import build
    tool = hashlib.sha256(Path(build.jvmcontract()).read_bytes()).hexdigest()
    SCORES.mkdir(exist_ok=True)
    out = {"step": step, "date": datetime.date.today().isoformat(), "tool": f"sha256:{tool}",
           "wrongAndAccepted": [r["example"] for r in rows if r.get("accepted")], "counts": tally(rows), "rows": rows}
    if flags is not None:
        out["flags"] = flags
    (SCORES / f"{step}.json").write_text(json.dumps(out, indent=2) + "\n")


def render_scores():
    blocks = []
    for path in sorted(SCORES.glob("*.json")) if SCORES.is_dir() else []:
        s = json.loads(path.read_text())
        lines = [f"**{s['step']}** ({s['date']}, `jvmcontract` {s['tool'][:19]}…; "
                 f"[{path.name}](scores/{path.name})). Wrong and accepted: "
                 + (", ".join(s["wrongAndAccepted"]) or "none") + ".", "",
                 "| Part | " + " | ".join(OUTCOMES) + " |", "|---|" + "---|" * len(OUTCOMES)]
        lines += [f"| {k} | " + " | ".join(str(v[o]) for o in OUTCOMES) + " |" for k, v in sorted(s["counts"].items())]
        if s["rows"] and "otherChanged" in s["rows"][0]:
            lines += ["", "| Example | Part | Table | Score | Proposed | Elsewhere in the module |", "|---|---|---|---|---|---|"]
            for r in s["rows"]:
                elsewhere = f"{r['otherChanged']} changed" + (f"; vanished: {'; '.join(r['otherVanished'])}" if r["otherVanished"] else "")
                lines.append(f"| {r['example']} | {r['part']} | `{r['table'].split('.')[-1]}` | {r['outcome']} | {cell(r['proposed'])} | {cell(elsewhere)} |")
        else:
            if "flags" in s:
                f = s["flags"]
                count = lambda v: sum(1 for x in f.values() if x == v)
                lines += ["", f"The example's hand-written flags are what the mapping amounts to in {count('proposed')} of {len(f)} examples, "
                          f"one of a question's alternatives in {count('asked')}, and neither in {count('no')}"
                          + (f" ({', '.join(k for k, v in sorted(f.items()) if v == 'no')})" if count("no") else "") + "."]
            lines += ["", "Every part that isn't found:", "", "| Example | Part | Table | Score | Proposed |", "|---|---|---|---|---|"]
            for r in s["rows"]:
                if r["outcome"] != "found":
                    lines.append(f"| {r['example']} | {r['part']} | `{cell(r['table'])}` | {r['outcome']} | {cell(r['proposed'])} |")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) or "No step has been scored yet."


def print_scores(rows):
    for r in rows:
        print(f"{r['example']}  {r['outcome']:6}  {r['part']:22}  {r['table']}: {r['proposed']}")
        for v in r.get("otherVanished", []):
            print(f"        also vanished: {v}")
    for k, v in sorted(tally(rows).items()):
        print(f"{k}: " + ", ".join(f"{v[o]} {o}" for o in OUTCOMES))


# The page.

def cell(text):
    return text.replace("|", "\\|")


def render_table(truth):
    rows = ["| Example | Verdict | Part | Old | New | Anchor or relation | Decided by | Why |", "|---|---|---|---|---|---|---|---|"]
    for entry in truth["examples"]:
        first = True
        for p in entry["parts"]:
            if p["kind"] == "method":
                old, new, what = p["old"].split(".")[-1], p["new"].split(".")[-1], p["how"]
            elif p["kind"] == "input":
                old, new, what = p["old"], p["new"], p["anchor"]
            elif p["kind"] == "new-input":
                old, new, what = "", p["new"], "new"
            else:
                old, new, what = "result", p.get("holds", "result"), p["relation"]
            head = (f"[{entry['example']}](../../{example_dir(entry['example']).name}/README.md)", entry["verdict"]) if first else ("", "")
            rows.append(f"| {head[0]} | {head[1]} | {p['kind']} | `{cell(old)}` | `{cell(new)}` | {what} | {p['decide']} | {cell(p['why'])} |".replace("``", ""))
            first = False
        if entry.get("scope"):
            rows.append(f"| | | scope | | `{cell(entry['scope'])}` | intended change | person | the inputs the change is declared to affect: a person's decision, not a mapping |")
    return "\n".join(rows)


def counts(truth):
    parts = [p for e in truth["examples"] for p in e["parts"]]
    by = {}
    for p in parts:
        key = (p["kind"], p.get("anchor") or p.get("relation") or p.get("how"), p["decide"])
        by[key] = by.get(key, 0) + 1
    return len(truth["examples"]), len(parts), by


def render(truth):
    text = PAGE.read_text()
    begin, end = "<!-- table:begin (generated by examples/tools/alignment.py render) -->", "<!-- table:end -->"
    n, parts, by = counts(truth)
    summary = (f"{n} examples, {parts} parts: "
               + ", ".join(f"{v} {k[0]} {k[1]} ({k[2]})" for k, v in sorted(by.items(), key=lambda kv: (kv[0][0], str(kv[0][1]), kv[0][2]))) + ".")
    new = f"{begin}\n\n{summary}\n\n{render_table(truth)}\n\n{end}"
    if begin not in text or end not in text:
        raise SystemExit(f"{PAGE}: no table markers")
    text = text[: text.index(begin)] + new + text[text.index(end) + len(end):]
    begin, end = "<!-- scores:begin (generated by examples/tools/alignment.py render) -->", "<!-- scores:end -->"
    if begin not in text or end not in text:
        raise SystemExit(f"{PAGE}: no score markers")
    return text[: text.index(begin)] + f"{begin}\n\n{render_scores()}\n\n{end}" + text[text.index(end) + len(end):]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="command", required=True)
    c = sub.add_parser("check")
    c.add_argument("--signatures", action="store_true", help="also compile each example's versions and compare the signatures")
    s = sub.add_parser("signatures")
    s.add_argument("example")
    sub.add_parser("render")
    sc = sub.add_parser("score")
    sc.add_argument("--record", action="store_true", help="keep the score in alignment/scores/ and rewrite the page")
    sc.add_argument("--step", choices=("methods", "mappings", "proofs", "all"), default="all",
                    help="methods (A2), mappings (A3: the input, new-input and result parts), both (all, the default), or "
                         "proofs (A3's second half: each example's proposals proved; runs proofs, so run it as a job)")
    args = p.parse_args(argv)
    truth = load()
    if args.command == "score":
        examples = {e["example"]: example_json(e["example"]) for e in truth["examples"]}
        prove = args.step == "proofs"
        reports = {k: align(*versions(ex), prove=ex if prove else None) for k, ex in examples.items()}
        if prove:
            rows = score_proofs(truth, reports)
            print("A3-proofs:")
            print_scores(rows)
            for r in rows:
                print(f"  {r['example']}: {r['summary']}")
            if args.record:
                record("A3-proofs", rows)
                PAGE.write_text(render(truth))
            return 0
        for step, name, score in (("methods", "A2-methods", score_methods), ("mappings", "A3-mappings", score_mappings)):
            if args.step in (step, "all"):
                rows = score(truth, reports)
                print(f"{name}:")
                print_scores(rows)
                flags = None
                if step == "mappings":
                    flags = {e["example"]: flags_agree(e, example_json(e["example"]), reports[e["example"]]) for e in truth["examples"]}
                    print("flags: " + ", ".join(f"{k} {v}" for k, v in flags.items()))
                if args.record:
                    record(name, rows, flags)
        if args.record:
            PAGE.write_text(render(truth))
        return 0
    if args.command == "signatures":
        print(json.dumps(signatures(example_json(args.example)), indent=2))
        return 0
    if args.command == "render":
        PAGE.write_text(render(truth))
        return 0
    errors = []
    for entry in truth["examples"]:
        example = example_json(entry["example"])
        errors += problems(entry, example)
        if args.signatures:
            errors += signature_problems(entry, signatures(example))
    if PAGE.read_text() != render(truth):
        errors.append(f"{PAGE.relative_to(REPO)} is stale: run `python3 examples/tools/alignment.py render`")
    for e in errors:
        print(e)
    n, parts, _ = counts(truth)
    print(f"{n} examples, {parts} parts: {len(errors)} problem{'s' if len(errors) != 1 else ''}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
