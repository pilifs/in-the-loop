"""Recount the registered statements from collected outputs and check the report against those bytes."""

import argparse
import hashlib
from collections import Counter
import json
from pathlib import Path
import struct
import tarfile

from measure import EVIDENCE, FAMILIES, ROOT, digest, load
from campaign import wire
from standalone import decode
from scorecard import collected, job_receipt, location, require, short_problem

PAGE = ROOT / "llm-dlc/loops/jbmc-fast-follow-calls-conversions-and-arrays-results.md"
COHORTS = {
    "callbacks": "Method-reference conversions",
    "direct": "Direct Guava twins",
    "chain": "Guava ComparisonChain",
    "numeric": "Primary numeric conversions",
    "classification": "All Jackson disagreements",
    "intrinsic": "Direct conversion opcode",
    "mantissa": "Long-mantissa adapter",
    "ragged": "Direct reversal and live iterator",
    "identity": "Direct row identity and reachability",
    "builder": "Explicit primitive builders",
    "matrix": "Commons Math equal-width and singleton controls",
    "matrix-exceptions": "Commons Math exception observations",
    "string-order": "Two-string public comparisons",
    "string-alias": "Same-reference string diagonal",
    "queue": "Four-operation queue histories",
    "fill": "Reference fills",
}


def grade(row):
    if row["verdict"] == "process error":
        return "process error"
    if row["verdict"] == "verified":
        if row["expected"] == "violation":
            return "JVM-contradicted proof"
        return "proved" if row["disposition"] == "correct" else row["disposition"]
    if row["verdict"] == "violation":
        if row.get("jvmReplay", {}).get("outcome") != "refuted":
            return "unreproduced witness"
        return "refuted" if row["expected"] == "violation" else "unexpected JVM refutation"
    reason = row.get("firstUnproved") or ""
    if (
        row["disposition"] == "frontend refusal"
        or reason.startswith("parameter ")
        and " has type " in reason
        or reason == "outside the fragment: a double parameter"
        or " takes a String (a parameter" in reason
    ):
        return "entry refused"
    if "does not reproduce" in reason:
        return "unreproduced witness"
    return "open"


def measurement(path, family, lane, joined=False):
    report = load(path)
    require(report["family"] == family and report["lane"] == lane, f"wrong family or lane in {path}")
    job, source = report["job"], report["measuredSource"]
    collected(path, job, source)
    raw = path.with_name("raw.tar.gz")
    collected(raw, job, source)
    require(digest(raw) == report["rawSha256"], f"changed archive {path}")
    receipt = job_receipt(job)
    require(receipt["sourceCommit"] == source, f"wrong measurement source {path}")
    (folder,) = (ROOT / "examples").glob(str(FAMILIES[family]) + "-*")
    tasks = {t["id"]: t for t in load(folder / "target.json")["tasks"] if t["kind"] == "prove"}
    with tarfile.open(raw) as archive:
        rows = {}
        for row in report["rows"]:
            key = row["task"]
            require(key not in rows and key in tasks, f"duplicate or unknown statement {key}")
            task = tasks[key]
            require(
                row["target"] == task["target"]
                and row["expected"] == task["expected"]
                and row["specSha256"] == digest(folder / task["claim"]),
                f"statement drift: {key}",
            )
            if joined:
                require(
                    row.get("descriptor") and row["descriptor"].endswith(")Z"), f"missing public descriptor {key}"
                )
            for engine in ("native", "jbmc") if lane == "paired" else (lane,):
                if engine not in ("native", "jbmc"):
                    continue
                r = row[engine]
                data = archive.extractfile(f"raw/{key}/{engine}/stdout.json").read()
                if r["disposition"] in ("process error", "frontend refusal", "timeout") and not data:
                    continue
                actual = wire.decode(data.decode(errors="replace"), "prove")
                require(actual.ok and len(actual.outcomes) == 1, f"invalid wire response {key}/{engine}")
                (obj,) = actual.outcomes
                require(
                    obj["target"] == row["target"] and obj["verdict"] == r["verdict"],
                    f"changed wire outcome {key}/{engine}",
                )
                if grade(r) in ("proved", "refuted"):
                    require(
                        obj["search"]["engine"] == engine
                        and obj["stated"]["gap_mode"] == "strict"
                        and not obj["stated"]["checker"].get("fallback"),
                        f"different strict engine {key}",
                    )
                    if grade(r) == "proved":
                        require(
                            obj["stated"]["bounds"]["complete"]
                            and obj["stated"]["vacuity"]["status"] == "non-vacuous",
                            f"incomplete proof {key}",
                        )
                    else:
                        require(
                            r["jvmReplay"]["inputs"] == obj["counterexample"]["inputs"]
                            and r["jvmReplay"]["exit"] == 0,
                            f"different original witness {key}",
                        )
                if r.get("rowInput"):
                    source_info = r["rowInput"]
                    require(
                        hashlib.sha256(
                            archive.extractfile(f"raw/{key}/{engine}/{source_info['source']}").read()
                        ).hexdigest()
                        == source_info["sha256"],
                        "different scalar input factory",
                    )
            if lane not in ("native", "jbmc", "paired"):
                for check in ("target", "reached"):
                    saved = row[lane][check]
                    owner, method = saved["entry"].split(".")
                    stdout = archive.extractfile(f"raw/{key}/{lane}/{check}.json").read()
                    stderr = archive.extractfile(f"raw/{key}/{lane}/{check}.stderr").read()
                    decoded = decode(
                        stdout,
                        stderr,
                        saved.get("exit", 124 if saved["status"] == "timeout" else 1),
                        method,
                        owner,
                    )
                    require(
                        all(saved.get(k) == v for k, v in decoded.items()),
                        "changed named standalone assertion " + key,
                    )
            rows[key] = row
    return report, rows


def outcome(row):
    return {
        "status": grade(row),
        "verdict": row["verdict"],
        "disposition": row["disposition"],
        "seconds": row["seconds"],
        "firstUnproved": row.get("firstUnproved", ""),
        **({"jvmReplay": row["jvmReplay"]} if "jvmReplay" in row else {}),
    }


def stock_entry(result, replay):
    target, reach = result["target"], result["reached"]
    return {
        "target": target["status"],
        "property": (target.get("target") or {}).get("property"),
        "postReturn": reach["status"],
        "otherFailures": [p["property"] for p in target.get("otherFailures", [])],
        "reachFailures": [p["property"] for p in reach.get("otherFailures", [])],
        "warnings": target.get("warnings", []),
        "seconds": target["seconds"],
        **({"jvmReplay": replay} if replay else {}),
    }


def jvm_observations(family, report):
    (folder,) = (ROOT / "examples").glob(f"{FAMILIES[family]}-*")
    frozen = load(folder / "controls/original.json")["cases"]
    raw = EVIDENCE / report["phase"] / family / "paired/raw.tar.gz"
    with tarfile.open(raw) as archive:
        stdout = archive.extractfile("raw/Cases.stdout").read()
    require(
        hashlib.sha256(stdout).hexdigest() == report["originalJvm"]["Cases"]["sha256"],
        f"original JVM output differs for {family}",
    )
    physical = [json.loads(line) for line in stdout.splitlines()]
    expected = [(v["id"], v["input"], v["expected"]) for v in frozen]
    require(
        [(v["id"], v["input"], v["direct"]) for v in physical] == expected,
        f"original JVM cases disagree with the frozen {family} observations",
    )
    by_target = {}
    for case in physical:
        target = case["input"]["entry"]
        by_target.setdefault(target, []).append(
            {"id": case["id"], "arguments": case["input"]["arguments"], "holds": case["direct"]["holds"]}
        )
    return by_target


def summarize(stage):
    replays = load(EVIDENCE / "standalone-replays.json")
    data = {
        "schema": "jbmc-fast-follow-scorecard/v1",
        "stage": stage,
        "subjects": {},
        "cohorts": {},
        "graphs": {},
        "jobs": set(),
    }
    for family, number in FAMILIES.items():
        left, opening = measurement(EVIDENCE / "opening" / family / "paired/measurement.json", family, "paired")
        right, closing = measurement(EVIDENCE / stage / family / "paired/measurement.json", family, "paired", True)
        require(opening.keys() == closing.keys(), f"{family}: missing final statements")
        for attr in (
            "productClasses",
            "driverClasses",
            "jars",
            "jdkModulesSha256",
            "javaSha256",
            "jbmcSha256",
            "coreModelsSha256",
        ):
            require(left[attr] == right[attr], f"{family}: changed {attr}")
        require(
            {k: v["sha256"] for k, v in left["originalJvm"].items()}
            == {k: v["sha256"] for k, v in right["originalJvm"].items()},
            f"{family}: JVM observations changed",
        )
        data["jobs"].update([left["job"], right["job"]])
        graph = {
            "example": number,
            "openingSource": left["measuredSource"],
            "openingChecker": left["checkerSha256"],
            "source": right["measuredSource"],
            "checker": right["checkerSha256"],
            "jars": right["jars"],
            "classBindings": right["classBindings"],
            "jdkModules": right["jdkModulesSha256"],
            "jvm": right["originalJvm"],
            "opening": location(EVIDENCE / "opening" / family / "paired/measurement.json"),
            "final": location(EVIDENCE / stage / family / "paired/measurement.json"),
            "profiles": {},
        }
        profiles = {}
        for lane in ("packaged", "comparator", "alias", "packaged-22", "arrays"):
            p = EVIDENCE / "opening" / family / lane / "measurement.json"
            if not p.exists():
                continue
            report, profiles[lane] = measurement(p, family, lane)
            require(
                report["productClasses"] == left["productClasses"] and report["jars"] == left["jars"],
                "different standalone product",
            )
            require(replays[f"{family}/{lane}"]["rawSha256"] == report["rawSha256"], "unbound stock replays")
            graph["profiles"][lane] = {
                "path": location(p),
                "binary": report["jbmcSha256"],
                "models": report["coreModelsSha256"],
            }
            data["jobs"].add(report["job"])
        data["graphs"][family] = graph
        jvm = jvm_observations(family, right)
        require(set(jvm) == {r["target"] for r in closing.values()}, f"{family}: missing original JVM controls")
        for key, b in closing.items():
            a = opening[key]
            require(
                all(
                    a[k] == b[k]
                    for k in ("cohort", "parameters", "bounds", "reachGuard", "expected", "specSha256")
                ),
                "different scope " + key,
            )
            stock = {}
            for lane, rows in profiles.items():
                if key not in rows:
                    continue
                sr = rows[key][lane]
                replay = replays[f"{family}/{lane}"]["replays"].get(key)
                if sr["target"]["status"] == "FAILURE":
                    require(replay, "unreconstructed stock input " + key)
                stock[lane] = stock_entry(sr, replay)
            d = {
                "family": family,
                "target": b["target"],
                "descriptor": b["descriptor"],
                "scope": b["parameters"],
                "reachGuard": b["reachGuard"],
                "bounds": b["bounds"],
                "expected": b["expected"],
                "cohort": b["cohort"],
                "standalone": stock,
                "originalJvm": jvm[b["target"]],
                "opening": {e: outcome(a[e]) for e in ("native", "jbmc")},
                "final": {e: outcome(b[e]) for e in ("native", "jbmc")},
            }
            data["subjects"][key] = d
            cohort = data["cohorts"].setdefault(
                d["cohort"], {"total": 0, "openingNative": 0, "native": 0, "openingJbmc": 0, "jbmc": 0}
            )
            cohort["total"] += 1
            for phase, engine, name in [
                ("opening", "native", "openingNative"),
                ("final", "native", "native"),
                ("opening", "jbmc", "openingJbmc"),
                ("final", "jbmc", "jbmc"),
            ]:
                cohort[name] += int(d[phase][engine]["status"] in ("proved", "refuted"))
    require(
        len({g["checker"] for g in data["graphs"].values()}) == 1
        and len({g["source"] for g in data["graphs"].values()}) == 1,
        "final checker sources or executables differ",
    )
    claims = data["subjects"]

    def witness(key, engine="native"):
        result = claims[key]["final"][engine]
        require(result["status"] == "refuted", key + " needs a replayed witness")
        return [arg["value"] for arg in result["jvmReplay"]["inputs"]]

    for engine in ("native", "jbmc"):
        (x,) = witness("node-checks-wrong-subnormal", engine)
        require(struct.pack(">d", float(x)).hex() == "3690000000000000", "incorrect direct underflow endpoint")
        (n,) = witness("node-checks-same", engine)
        k = int(n) - (1 << 54)
        delta = (k & 0x7FFFFFFF) - (1 << 30)
        require(0 <= k < 1 << 54 and delta in ((-1, -2) if k >> 31 & 1 else (1, 2)), "incorrect Jackson witness")
        (shared,) = witness("ragged-proof-distinct", engine)
        require(
            len(shared) == 2
            and isinstance(shared[0], list)
            and len(shared[0]) > 0
            and shared[1] == {"sameCell": 0},
            "missing shared nonempty witness",
        )
        (distinct,) = witness("row-identities-no-distinct-equal-rows", engine)
        require(distinct == [[-2147483648], [-2147483648]], "distinct equal rows lost")
        require(
            witness("row-identities-non-null-outer", engine) == [None]
            and witness("row-identities-no-empty-outer", engine) == [[]],
            "missing null or empty outer",
        )
    require(
        claims["node-checks-public-subnormal"]["descriptor"] == "(D)Z"
        and claims["matrix-rows-rectangular"]["descriptor"] == "([[J)Z",
        "different input descriptor",
    )
    data["jobs"] = sorted(data["jobs"])
    return data


def campaign_jobs():
    jobs = {}
    for file in (ROOT / "verification/jobs/2026/11/23").glob("*.json"):
        if not "20261123-160648" <= file.stem <= "20261123-175431-compare-the-same-ragged-operations-with":
            continue
        spec = load(file)
        if not (
            any(o.startswith("verification/jbmc-fast-follow/") for o in spec.get("outputs", []))
            or "lib/benchmark/jbmc-fast-follow" in spec.get("links", {}).get("paths", [])
            or spec["title"] == "Recheck proof-tier conformance after method-reference replay"
        ):
            continue
        record = job_receipt(spec["id"])
        jobs[spec["id"]] = {
            "title": spec["title"],
            "status": record["status"],
            "source": record["sourceCommit"],
            "summary": record["summary"],
            "attention": record["attention"],
        }
    return dict(sorted(jobs.items()))


def owner_job(file, jobs):
    name = location(file)
    sha = digest(file)
    hits = [
        job
        for job in jobs
        if job_receipt(job)["status"] == "passed"
        and any(o["path"] == name and o["sha256"] == sha for o in job_receipt(job)["outputs"])
    ]
    require(len(hits) == 1, "no unique collector for " + name)
    collected(file, hits[0])
    return hits[0]


def predecessor(data, stage):
    base = EVIDENCE / stage / "regressions"
    rows = {"native": Counter(), "jbmc": Counter()}
    (checker,) = {g["checker"] for g in data["graphs"].values()}
    for f in sorted((base / "callers").glob("*/measurement.json")):
        report = load(f)
        collected(f, report["job"], report["source"])
        collected(f.with_name("raw.tar.gz"), report["job"], report["source"])
        require(report["checkerSha256"] == checker, "different predecessor checker")
        for r in report["runs"]:
            rows[r["engine"]][grade(r)] += 1
    require(sum(rows["native"].values()) == sum(rows["jbmc"].values()) == 60, "missing preceding callers")
    history = {"native": Counter(), "jbmc": Counter()}
    cohorts = {}
    seen = set()
    for f in (base / "historical").glob("*.json"):
        owner_job(f, data["verification"])
        h = load(f)
        require(h["binaries"]["jvmcontract"] == checker, "different historical checker")
        for r in h["runs"]:
            key = (r["engine"], r["case"])
            require(key not in seen, "duplicate historical case")
            seen.add(key)
            status = r["verdict"] if r["class"] == "correct" else r["class"]
            history[r["engine"]][status] += 1
            if r["engine"] == "native":
                cohort = h["historical"][r["case"]]["historical"]
                tally = cohorts.setdefault(cohort, {"correct": 0, "total": 0})
                tally["total"] += 1
                tally["correct"] += int(r["class"] == "correct")
    require(len(seen) == 76, "missing historical results")
    decimal_file = base / "decimal/paired/measurement.json"
    decimal = load(decimal_file)
    collected(decimal_file, decimal["job"], decimal["source"])
    require(decimal["checkerSha256"] == checker, "different decimal checker")
    return {
        "callers": rows,
        "historical": history,
        "nativeHistoricalCohorts": cohorts,
        "decimal": {k: {e: grade(v) for e, v in t["runs"].items()} for k, t in decimal["tasks"].items()},
        "path": location(base),
        "decimalPath": location(decimal_file),
    }


def ordinary(data):
    file = EVIDENCE / "successor/example-tasks/measurement.json"
    report = load(file)
    collected(file, report["job"], report["source"])
    require(
        report["checkerSha256"] == next(iter(data["graphs"].values()))["checker"], "different ordinary checker"
    )
    expected = {k: r["expected"] for k, r in data["subjects"].items()}
    actual = {}
    for tasks in report["examples"].values():
        for task, info in tasks.items():
            path = ROOT / info["receipt"]
            collected(path, report["job"], report["source"])
            require(
                digest(path) == info["sha256"] and load(path)["conclusion"]["status"] == info["status"],
                "changed task " + task,
            )
            require(task not in actual and expected[task] == info["status"], "unexpected ordinary result " + task)
            actual[task] = info
    require(actual.keys() == expected.keys(), "incomplete ordinary routes")
    return actual


def row_diagnostics(data):
    path = EVIDENCE / "row-layout/measurement.json"
    report = load(path)
    collected(path, report["job"], report["source"])
    graph = data["graphs"]["rows"]
    require(
        report["checkerSha256"] == graph["checker"]
        and report["originalClass"] == graph["classBindings"]["RaggedProof"]["sha256"],
        "different original row checker or class",
    )
    require(
        len(report["instructionsAndHandlers"]) == 6
        and report["builderClass"] == graph["classBindings"]["MadeRows"]["sha256"],
        "different builder methods",
    )
    for lanes in report["runs"].values():
        for result in lanes.values():
            if grade(result) == "refuted":
                require(
                    result["originalClassReplay"]["outcome"] == "refuted"
                    and result["jvmReplay"]["inputs"] == result["originalClassReplay"]["inputs"],
                    "different original-layout counterexample",
                )
    settings = load(EVIDENCE / "row-settings.json")
    require(
        settings["source"] == graph["source"] and len(settings["replays"]) == 5,
        "missing assertion-setting observations",
    )
    for key, observed in settings["replays"].items():
        require(
            observed["enabled"] == observed["disabled"] == "refuted"
            and observed["inputs"] == data["subjects"][key]["final"]["native"]["jvmReplay"]["inputs"],
            "incorrect assertion-setting replay",
        )
    return {
        "layout": location(path),
        "settings": location(EVIDENCE / "row-settings.json"),
        "statuses": {k: {e: grade(v) for e, v in by.items()} for k, by in report["runs"].items()},
    }


def matrix_section(data, stage):
    path = EVIDENCE / stage / "matrix/measurement.json"
    report = load(path)
    collected(path, report["job"], report["source"])
    require(report["checker"] == data["graphs"]["rows"]["checker"], "different matrix checker")
    first = EVIDENCE / "matrix/measurement.json"
    old = load(first)
    collected(first, old["job"], old["source"])
    return {
        "initial": {
            "path": location(first),
            "memoryMiB": old.get("jbmcMemoryMiB", 4096),
            "jbmc": {k: v["jbmc"]["verdict"] for k, v in old["direct"].items()},
            "firstUnproved": {k: v["jbmc"]["firstUnproved"] for k, v in old["direct"].items()},
            "attention": job_receipt(old["job"])["attention"],
        },
        "path": location(path),
        "entry": report["entry"],
        "direct": {k: {e: r["verdict"] for e, r in by.items()} for k, by in report["direct"].items()},
        "metadata": {k: {e: grade(r) for e, r in by.items()} for k, by in report["metadata"].items()},
        "firstUnproved": {
            k: {e: r["firstUnproved"] for e, r in by.items() if r["verdict"] == "unverifiable"}
            for k, by in report["direct"].items()
        },
        "memoryMiB": report.get("jbmcMemoryMiB", 4096),
    }


def timed(info):
    return f"{info['status']} ({info['seconds']:.2f} s)"


def describe_boundary(reason):
    if " takes a String (a parameter" in reason:
        return "The integrated String input model cannot enforce the stated UTF-16 domain."
    if "otherwise than the JVM (" in reason:
        operations = reason.split("otherwise than the JVM (", 1)[1].split("), so the proof", 1)[0]
        sites = dict.fromkeys(operations.split(", "))
        return "Strict checking rejected the solver proof at " + ", ".join(f"`{site}`" for site in sites) + "."
    if "does not reproduce" in reason and " approximates (" in reason:
        call = reason.partition("counterexample ")[2].partition(" does not reproduce")[0]
        model = reason.partition(" approximates (")[2].partition("): a stub")[0]
        return f"The interpreter returned true for `{call}`. The comparator approximates `{model}`."
    if "(--gaps strict): " in reason:
        site = short_problem(reason).split("; --gaps", 1)[0]
        return f"Strict checking refused the approximation at `{site}`."
    if "ran out of memory" in reason:
        return "out of memory"
    if "killed before it finished" in reason:
        return "process killed"
    return short_problem(reason)


def md_table(lines, headings, rows):
    lines.extend(["", "| " + " | ".join(headings) + " |", "|" + "---|" * len(headings)])
    for row in rows:
        lines.append("| " + " | ".join(str(c).replace("|", "\\|").replace("\n", " ") for c in row) + " |")


def link(title, path):
    return "[" + title + "](../../" + path + ")"


def markdown(data):
    claims = list(data["subjects"].values())
    native = Counter(r["final"]["native"]["status"] for r in claims)
    decided = {"proved", "refuted"}
    opening = sum(r["opening"]["native"]["status"] in decided for r in claims)
    comparator = sum(r["final"]["jbmc"]["status"] in decided for r in claims)
    core = [r for r in claims if r["family"] in {"callbacks", "numeric", "rows"}]
    core_open = sum(r["opening"]["native"]["status"] in decided for r in core)
    observed = sum(len(r["originalJvm"]) for r in claims)
    lines = [
        "# Java callbacks, numeric conversions and caller-owned arrays",
        "",
        f"**Ordinary native decisions rose from {opening}/{len(claims)} to {native['proved'] + native['refuted']}/{len(claims)}.** "
        f"The final checker proved {native['proved']} statements and refuted {native['refuted']} on witnesses reproduced by the original JVM. "
        f"The three primary examples opened at {core_open}/{len(core)}. "
        f"The two reserve examples opened later at {opening - core_open}/{len(claims) - len(core)}. "
        f"Strict integrated JBMC decided {comparator}/{len(claims)} at matching scope. The original JVM also ran {observed} frozen single-input controls.",
        "",
        "The public callers use Temurin 21.0.13, pinned release JARs in their original order and explicit strict engines. The original historical benchmark uses its JDK 25 harness. The standalone numeric comparison used the Ubuntu 22.04 JBMC 6.11.0 package. Callbacks, rows and queue histories used the 24.04 package. Both packages ran the bounded strings. The Comparator and Arrays overlays came from the measured JDK image. A qualified refutation has a witness replayed on the original JVM. Times in parentheses cover the checker calls. The job receipts also record preparation and JVM replay. [Per-statement evidence, bounds and first unresolved operations](../../verification/jbmc-fast-follow/scorecard.json)",
    ]
    table = []
    for cohort, title in COHORTS.items():
        if cohort not in data["cohorts"]:
            continue
        c = data["cohorts"][cohort]
        total = c["total"]
        table.append((title, total, f"{c['openingNative']} → {c['native']}", f"{c['openingJbmc']} → {c['jbmc']}"))
    md_table(
        lines,
        [
            "Cohort",
            "Statements",
            "Native decisions, opening → final",
            "Integrated JBMC decisions, opening → final",
        ],
        table,
    )
    lines.extend(
        [
            "",
            "## Public behavior",
            "",
            "At opening, native stopped at method-reference conversion on all seven callback statements. Its long conversions reached a 64-tuple enumeration limit, and the two direct-double statements stopped at parameter intake. Both project engines refused the direct nested-array inputs before the library method. The primitive builders had their own narrower construction histories.",
            "",
            "The original integrated Guava run exited 101 during witness replay. The corrected adapters widen the signed result for both Guava interfaces and the Commons Lang short interface. Unboxing a null argument on an active comparison throws. A settled ComparisonChain skips that argument. "
            + link(
                "Independent five-claim Guava qualification",
                "verification/jbmc-fast-follow/guava/callbacks/paired/measurement.json",
            ),
            "",
            "Across the 2⁵⁴ admitted long inputs, the two Jackson paths differ at two neighbors of a midpoint in each of 2²³ bins. Even retained significands disagree at offsets +1 and +2, odd ones at −1 and −2, giving 16,777,216 inputs. At 0x0040000040000001L direct conversion gives float bits 0x5a800001 and conversion through double gives 0x5a800000. The direct double interval contains 2⁵² + 1 values. Its halfway endpoint converts to positive zero. "
            + link(
                "Qualification after the five primary decisions",
                "verification/jbmc-fast-follow/classification/numeric/paired/measurement.json",
            ),
            "",
            "The direct row domain includes a null outer array, independently sized nullable rows, arbitrary signed cells and shared row references. Both dimensions are bounded by two in the comparison. The original JVM census found 12 shared nonempty graphs among 209 two-slot cases. The stock tree generator accepted the false distinct-row assertion. Explicit alias choice produced a replayed counterexample. "
            + link("Independent standalone JVM replays", "verification/jbmc-fast-follow/standalone-replays.json"),
            "",
            "The first direct native run proved reversal and live iteration. Its row counterexample search stopped at a class assertion setting because the search could vary the input heap along with that setting. Fixing the concrete input graph allows the checker to vary the JVM setting independently. The companion regression keeps a genuinely setting-dependent claim open. "
            + link(
                "Initial direct-row comparison", "verification/jbmc-fast-follow/final/rows/paired/measurement.json"
            ),
        ]
    )
    layout = data["rowDiagnostics"]
    builders = [by for k, by in layout["statuses"].items() if k.startswith("made-rows-")]
    native = sum(r["native"] in ("proved", "refuted") for r in builders)
    jbmc = sum(r["jbmc"] in ("proved", "refuted") for r in builders)
    lines += [
        "",
        f"A separate layout moved the assertion methods out of RaggedProof. Its six public and helper method instruction and handler lists matched, and the MadeRows class bytes matched. On the three explicit primitive builders that layout yielded {native}/3 native and {jbmc}/3 integrated decisions. Both layouts agreed on all 209 physical graphs with both assertion settings. "
        + link("Separated assertion drivers", layout["layout"])
        + " · "
        + link("Five ordinary counterexamples on both JVM settings", layout["settings"]),
    ]
    m = data["matrix"]
    lines.extend(
        [
            "",
            "The released Commons Math method was also checked directly at `"
            + m["entry"]
            + "`. Its equal-width and singleton-null inputs return normally. Its unequal-width inputs throw DimensionMismatchException. Independent JVM enumeration found eight normal returns, seven null-pointer exceptions and six mismatches across 21 non-null shapes. Swapping the two exception fields fails on every unequal non-null pair. "
            + link("Original descriptor and field results", m["path"]),
        ]
    )
    md_table(
        lines,
        [
            "Direct Commons Math scope",
            "Native",
            "Integrated JBMC at " + str(m["initial"]["memoryMiB"]) + " MiB",
            "Integrated JBMC at " + str(m["memoryMiB"]) + " MiB",
        ],
        [
            (key, value["native"], describe_boundary(m["initial"]["firstUnproved"][key]), value["jbmc"])
            for key, value in m["direct"].items()
        ],
    )
    matrix_limits = {}
    for k, by in m["firstUnproved"].items():
        for engine, reason in by.items():
            matrix_limits.setdefault((engine, describe_boundary(reason)), []).append(k)
    for (engine, reason), scopes in matrix_limits.items():
        lines.extend(["", f"{engine.upper()} on {', '.join(scopes)}. {reason}"])
    sr = load(EVIDENCE / "standalone-replays.json")
    physical = [v for group in sr.values() for v in group["replays"].values()]
    lines += [
        "",
        f"Independent JVM runs reconstructed all {len(physical)} failing standalone target traces. {sum(v['outcome'] == 'refuted' for v in physical)} refuted the original observation. The JVM observation held for the long-mantissa candidate, the packaged replacement candidate and both covariant-fill candidates. "
        + link(
            "Witness values, identities and physical outcomes",
            "verification/jbmc-fast-follow/standalone-replays.json",
        ),
    ]
    if "strings" in data["graphs"]:
        lines.extend(
            [
                "",
                "The separate string grid checked 5,329 pairs. Sign normalization failed on 4,756, including U+D800 versus U+D802, where the difference is −2. Guava retained the first reference on all 73 equal-valued, distinct pairs. The same-reference case has its own row.",
                "",
                "All 256 four-operation queue histories were checked against a two-slot oracle. On 128 histories, isFull differed from occupancy. The ArrayFill transfer observes both overwritten references and a later write through the shared replacement. A covariant empty array returns normally, while the nonempty incompatible store throws before replacing its first cell. The packaged JBMC model accepted the stale-slot claim. Adding the original JDK Arrays class corrected the replacement and stale-slot results. Its covariant candidate still held on the JVM.",
            ]
        )
    lines.extend(
        [
            "",
            "The standalone tables show the selected assertion and its post-return sentinel separately. "
            "A failed sentinel establishes that the caller returned. Other failed obligations are counted beside the target.",
        ]
    )
    for family, g in data["graphs"].items():
        lines.extend(
            [
                "",
                "## "
                + {
                    "callbacks": "Method references",
                    "numeric": "Numeric conversions",
                    "rows": "Primitive row graphs",
                    "strings": "Bounded UTF-16 ordering",
                    "queue": "Queue and fill",
                }[family],
                "",
                "The opening source was `"
                + g["openingSource"][:12]
                + "` with checker `"
                + g["openingChecker"][:16]
                + "`. The successor was `"
                + g["source"][:12]
                + "` with checker `"
                + g["checker"][:16]
                + "`. The JVM and verifier agreed on "
                + str(len(g["classBindings"]))
                + " product and release class bindings. "
                + link("Opening paired responses", g["opening"])
                + " · "
                + link("Final paired responses", g["final"])
                + " · "
                + " · ".join(link(k + " JBMC profile", v["path"]) for k, v in g["profiles"].items()),
            ]
        )
        rows = []
        for r in data["subjects"].values():
            if r["family"] != family:
                continue
            stock = []
            for k, x in r["standalone"].items():
                label = x["target"] + " / " + x["postReturn"]
                if x["otherFailures"]:
                    label += f" + {len(x['otherFailures'])} other failure(s)"
                if "jvmReplay" in x:
                    label += ", JVM " + x["jvmReplay"]["outcome"]
                stock.append(k + " " + label)
            rows.append(
                (
                    "`" + r["target"] + r["descriptor"] + "`",
                    r["expected"],
                    timed(r["opening"]["native"]) + " → " + timed(r["final"]["native"]),
                    timed(r["opening"]["jbmc"]) + " → " + timed(r["final"]["jbmc"]),
                    "<br>".join(stock) or "No standalone profile",
                    f"{sum(case['holds'] for case in r['originalJvm'])} held, "
                    f"{sum(not case['holds'] for case in r['originalJvm'])} failed"
                    + (", checker witness replayed" if r["final"]["native"].get("jvmReplay") else ""),
                )
            )
        md_table(
            lines,
            [
                "Original entry",
                "Expected",
                "Native",
                "Integrated JBMC",
                "Standalone target / post-return sentinel",
                "Original JVM controls",
            ],
            rows,
        )
    lines.extend(
        [
            "",
            "## Remaining operations",
            "",
            "Each row below names an entry in the frozen comparison. To reproduce a single integrated claim, use "
            + '`python3 -B lib/benchmark/jbmc-fast-follow/measure.py repro rows jbmc --methods reversed --output "$TMPDIR"` '
            + "as the verification job step. Substitute the family and method from the per-statement scorecard. "
            + "The raw responses retain the full diagnostics and the concrete arguments for any proposed violation.",
            "",
        ]
    )
    gaps = {}
    for r in data["subjects"].values():
        for engine in ("native", "jbmc"):
            out = r["final"][engine]
            if out["status"] in ("proved", "refuted"):
                continue
            why = describe_boundary(out["firstUnproved"]) or out["status"]
            if len(why) > 440:
                why = why[:437] + "…"
            gaps.setdefault((engine, why), []).append(r["target"])
    for (engine, why), targets in gaps.items():
        lines.append("- " + engine.upper() + " on " + ", ".join("`" + x + "`" for x in targets) + ". " + why)
    lines.extend(
        [
            "",
            "## Handoff to receiver construction",
            "",
            "The ordinary verifier accepts direct float and double words and one bounded int[][] or long[][] root alongside primitive arguments. Row witnesses preserve null, shared rows, distinct equal values and every cell bit. The native row factory supports bounds through 32. Integrated JBMC uses a scalar descriptor that must fit in 255 JVM argument slots. Constructor-made receivers sharing this heap and cross-engine confirmation of these row inputs remain open. A reachable floating conversion with an unspecified NaN payload also has its own refusal. [Receiver construction and property discovery](receiver-construction-and-property-discovery-brief.md)",
            "",
            "The numbered examples retain "
            + str(len(data["ordinaryTasks"]))
            + " ordinary task receipts. "
            + link(
                "Native receipts by example",
                "verification/jbmc-fast-follow/successor/example-tasks/measurement.json",
            ),
            "",
            "## Predecessor controls and verification",
            "",
        ]
    )
    prev = data["predecessor"]
    count = prev["callers"]["native"]
    hist = prev["historical"]["native"]
    old_jbmc_only = prev["nativeHistoricalCohorts"]["jbmc-only"]
    old_native_only = prev["nativeHistoricalCohorts"]["native-only"]
    lines.append(
        f"The successor retained {count.get('proved', 0)} proofs and {count.get('refuted', 0)} replayed refutations among the 60 preceding statements. The three ordinary monitor statements still first reach Thread construction. Native retained {hist.get('verified', 0)} historical proofs and {hist.get('violation', 0)} refutations among the 38 historical checks, including {old_jbmc_only['correct']}/{old_jbmc_only['total']} formerly JBMC-only cases and {old_native_only['correct']}/{old_native_only['total']} formerly native-only controls. The 187-row distribution belongs to the original historical benchmark. "
        + link("Historical and public caller repeats", prev["path"])
        + " · "
        + link("Decimal cases and exact JVM values", prev["decimalPath"])
    )
    old_jbmc = prev["callers"]["jbmc"]
    decimal = Counter(engines["native"] for engines in prev["decimal"].values())
    lines.extend(
        [
            "",
            f"On the preceding 60, integrated JBMC returned {old_jbmc['proved']} correct proofs and "
            f"{old_jbmc['refuted']} replayed refutations. The JVM contradicted {old_jbmc['JVM-contradicted proof']} "
            f"other proofs. The four decimal decisions comprised {decimal['proved']} native proofs and "
            f"{decimal['refuted']} replayed refutation.",
        ]
    )
    states = Counter(j["status"] for j in data["verification"].values())
    lines += [
        "",
        f"The verification ledger contains {len(data['verification'])} campaign jobs, "
        + ", ".join(f"{v} {k}" for k, v in sorted(states.items()))
        + ". The first direct Commons Math run recorded two kernel process kills at its memory limit. The separate retry retained the 120-second claim deadlines and the original release JAR.",
        "",
        "Recount the saved evidence with `python3 -B lib/benchmark/jbmc-fast-follow/results.py --check`. Repeat the independent standalone JVM witnesses with `python3 -B lib/benchmark/jbmc-fast-follow/stock_replays.py --check`. The numbered examples expose their ordinary task plans and JVM controls.",
    ]
    return "\n".join(lines) + "\n"


def example_pages(data, check):
    findings = {
        "callbacks": "The integrated Guava (0, 1) witness originally exited during replay. The same input now returns a signed negative long through the method reference. A settled ComparisonChain skips null unboxing and a tied chain performs it.",
        "numeric": "The Jackson conversions disagree at 16,777,216 of the 2⁵⁴ admitted long values. The direct binary64 underflow interval contains 2⁵² + 1 values, including the halfway input that rounds to positive zero.",
        "rows": "Both dimensions and every cell are independent at the direct entry. An alias names an earlier row, while equal separate rows have their own cell lists. The 209-graph JVM census contains 12 shared nonempty cases. The direct Commons Math transfer retains actual and expected mismatch dimensions.",
        "strings": "The JVM checked 5,329 boundary pairs. Sign normalization failed on 4,756, and Guava min kept the first reference on all 73 equal-valued distinct ties.",
        "queue": "The independent two-slot oracle checked all 256 histories. Full occupancy disagreed with isFull on 128. Reference fill preserves the array and replacement identity and checks covariance on the first store.",
    }
    for family, graph in data["graphs"].items():
        (folder,) = (ROOT / "examples").glob(str(graph["example"]) + "-*")
        source = folder / "example.json"
        example = load(source)
        subjects = {k: v for k, v in data["subjects"].items() if v["family"] == family}
        wins = sum(r["final"]["native"]["status"] in ("proved", "refuted") for r in subjects.values())
        label = f"Ordinary native {wins}/{len(subjects)}"
        note = findings[family]
        page = folder / "README.md"
        base = page.read_text().split("\n## Measured results", 1)[0].rstrip()
        lines = [base, "", "## Measured results", "", label + ". " + note]

        def receipt_link(info):
            relative = Path(info["receipt"]).relative_to(folder.relative_to(ROOT))
            return f"[{info['status']}]({relative.as_posix()})"

        md_table(
            lines,
            ["Original entry", "Opening native", "Final native", "Integrated JBMC", "Ordinary task receipt"],
            [
                (
                    r["target"],
                    r["opening"]["native"]["status"],
                    r["final"]["native"]["status"],
                    r["final"]["jbmc"]["status"],
                    receipt_link(data["ordinaryTasks"][key]),
                )
                for key, r in subjects.items()
            ],
        )
        lines += [
            "",
            link("Paired measurements", graph["final"])
            + " · [Campaign results](../../llm-dlc/loops/jbmc-fast-follow-calls-conversions-and-arrays-results.md)",
        ]
        doc = "\n".join(lines) + "\n"
        if check:
            require(
                example.get("verdictLabel") == label and note in example["notes"] and page.read_text() == doc,
                "example page drift: " + family,
            )
        else:
            example["verdictLabel"] = label
            if note not in example["notes"]:
                example["notes"].append(note)
            source.write_text(json.dumps(example, indent=2, ensure_ascii=False) + "\n")
            page.write_text(doc)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    stage = "successor"
    data = summarize(stage)
    data["verification"] = campaign_jobs()
    data["predecessor"] = predecessor(data, stage)
    data["matrix"] = matrix_section(data, stage)
    data["ordinaryTasks"] = ordinary(data)
    data["rowDiagnostics"] = row_diagnostics(data)
    example_pages(data, args.check)
    doc = markdown(data)
    output = EVIDENCE / "scorecard.json"
    if args.check:
        require(data == load(output), "scorecard changed")
        require(doc == PAGE.read_text(), "results page changed")
    else:
        output.write_text(json.dumps(data, indent=2) + "\n")
        PAGE.write_text(doc)
    print(
        f"{len(data['subjects'])} frozen statements, {len(data['ordinaryTasks'])} ordinary task receipts, "
        f"{len(data['verification'])} verification jobs and 98 predecessor controls checked, plus four decimal cases"
    )


if __name__ == "__main__":
    main()
