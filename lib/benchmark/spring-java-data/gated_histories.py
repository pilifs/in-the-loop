"""Replay every three-decision Spring edit history against a fresh model and two earlier public callers."""
import argparse
from collections import Counter
import gzip
from itertools import permutations, product
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
from time import perf_counter

from domains import binding_steps, roles
from gated_transfer import BINDER, ROLES, PRODUCER, Job, binder_receipts, producer_replay
from measure import HERE, ROOT, digest, read, run_cmd, write
from targets import route, runtime, runtime_jdk, sidecar

ROLE_JOB = "20261122-164312-spring-security-reachable-roles-and-publ"
CASES = (1057, 82977)  # Decline the first name edit on distinct children, or the first invalid edit on shared children.
TRIALS = ("fresh-1", "reuse-1", "reuse-2", "fresh-2")
ORDERS = tuple(permutations(range(3)))
PREFIXES = ("ROLE_", "CUSTOM_PREFIX_")
HEADER = struct.Struct(">4sii")  # Magic and two state indices observed on fresh sessions.
HISTORY = struct.Struct(">8B" + "Bii" * 3)  # Layout, prefix, three edits, three subsets; grant, count, state per step.
CONTROL_JAVA = ROOT / "examples/tools/targets/java"
SOURCES = (ROLES / "companions/GatedHistories.java", CONTROL_JAVA / "LoadedClasses.java",
           CONTROL_JAVA / "org/intheloop/controls/Grid.java")
DEST = Path("verification/spring-java-data/gated-histories")
ARTIFACTS = ((BINDER, "combined", "replay", "binder"), (ROLES, "release", "replay-release", "roles"))


def source_hashes():
    files = (*SOURCES, Path(__file__).resolve(), HERE / "domains.py", HERE / "gated_transfer.py")
    return {p.relative_to(ROOT).as_posix(): digest(p) for p in files}


def release_graph():
    inventory = read(ROOT / "verification/spring-java-data/exact-classpaths/classes.json")
    binder = inventory["368"]["combined"]
    security = inventory["370"]["release"]
    dependencies = binder["orderedJars"][3:]
    if ([r["sha256"] for r in dependencies] != [r["sha256"] for r in security["orderedJars"][3:]]
            or binder["jdk"] != security["jdk"]):
        raise ValueError("the binder and role producers used different release graphs")
    jars = {"binder/" + binder["orderedJars"][2]["path"]: binder["orderedJars"][2]["sha256"],
            "roles/" + security["orderedJars"][2]["path"]: security["orderedJars"][2]["sha256"]}
    jars.update({"binder/" + r["path"]: r["sha256"] for r in dependencies})
    providers = {}
    for previous in (binder, security):
        for name, cls in previous["classes"].items():
            path, = [path for path, sha in jars.items() if sha == cls["jarSha256"]]
            providers[name] = [path, cls["classSha256"]]
    return {"jdk": binder["jdk"]["JAVA_RUNTIME_VERSION"], "classpath": ["observer", *jars],
            "jars": jars, "publicClasses": providers}


def prepare(work, graph):
    for folder, side, task, label in ARTIFACTS:
        example = read(folder / "example.json")
        plan = route.resolve(folder, example, sidecar.load(folder, example), task)
        built = runtime.prepare(plan, side, work / label)
        if built.stage != "artifacts-ready":
            raise ValueError(built.diagnostic)
    if any(digest(work / p) != sha for p, sha in graph["jars"].items()):
        raise ValueError("prepared application JARs or ordered dependencies differ from the public receipts")
    jdk = Path(runtime_jdk.home("21"))
    if runtime_jdk.release(jdk)["JAVA_RUNTIME_VERSION"] != graph["jdk"]:
        raise ValueError("different release JDK")
    observer = work / "observer"
    observer.mkdir()
    cp = os.pathsep.join(str(work / p) for p in graph["classpath"])
    subprocess.run([jdk / "bin/javac", "--release", "21", "-parameters", "-proc:none",
                    "-cp", cp, "-d", observer, *SOURCES], check=True)
    command = [jdk / "bin/java", "-Xmx256m", "-Duser.language=en", "-Duser.country=US",
               "-Duser.timezone=UTC", "-cp", cp, "GatedHistories"]
    return command, digest(observer / "GatedHistories.class")


def state_key(state):
    # JSON distinguishes a boolean from an integer when comparing independently encoded observations.
    return json.dumps(state, sort_keys=True, separators=(",", ":"))


def baseline(shared):
    return next(binding_steps(shared, [None]))


def producers(graph):
    jars = [graph["jars"][p] for p in graph["classpath"][3:]]
    binder_job, role_job = Job(PRODUCER), Job(ROLE_JOB)
    binder, binder_ids, binder_log = producer_replay(binder_job, BINDER, "replay", "combined", jars)
    role, role_ids, role_log = producer_replay(role_job, ROLES, "replay-release", "release", jars)
    receipts = binder_receipts(binder_job, binder_ids)
    for identities, path in zip((binder_ids, role_ids), graph["classpath"][1:3], strict=True):
        original, = [c for c in identities["classpath"] if c["role"] == "original"]
        if original["sha256"] != graph["jars"][path] or identities["jdkRelease"]["JAVA_RUNTIME_VERSION"] != graph["jdk"]:
            raise ValueError("the producer and consumer application JARs or JDKs differ")

    prefixes = {}
    for i, (row, (shared, order)) in enumerate(zip(binder, product((False, True), ORDERS), strict=True)):
        if (row["id"] != i or row["input"] != {"shared": shared, "order": list(order)}
                or row["adapter"] != {"beans": 1, "ledger": 1}):
            raise ValueError("different binder producer inputs or adapter outcomes")
        for length, bean, ledger in zip(range(1, 4), row["direct"]["beans"], row["direct"]["ledger"], strict=True):
            state = state_key([bean, ledger])
            if prefixes.setdefault((shared, order[:length]), state) != state:
                raise ValueError("the same applied edit prefix had two producer states")
    decisions = {}
    for i, (row, (inputs, oracle)) in enumerate(zip(role, roles(), strict=True)):
        expected = {"api": "present", "legacyNames": oracle["legacyNames"], "legacyDecision": oracle["legacyDecision"],
                    "fluentNames": oracle["fluentNames"]["present"], "fluentDecision": oracle["fluentDecision"]["present"]}
        if row["id"] != i or row["input"] != inputs or state_key(row["direct"]) != state_key(expected):
            raise ValueError("the role release replay differs from the independent graph traversal")
        decisions[inputs["prefix"], inputs["subset"]] = row["direct"]["fluentDecision"]
    info = {"binderJob": PRODUCER, "binderReceipts": receipts, "binderReplaySha256": digest(binder_log),
            "nonemptyBinderPrefixes": len(prefixes), "roleJob": ROLE_JOB, "roleReplaySha256": digest(role_log),
            "releaseDecisions": len(decisions)}
    return decisions, prefixes, info


def fresh_trace(shared, order, grants, always_first=False):
    applied = [edit if grant or (always_first and i == 0) else None
               for i, (edit, grant) in enumerate(zip(order, grants, strict=True))]
    count = 0
    for edit, grant, (bean, errors) in zip(applied, grants, binding_steps(shared, applied), strict=True):
        count += edit is not None
        yield [grant, count, bean, errors]


def states_from_jvm(stdout, graph, observer):
    lines = stdout.read_text().splitlines()
    classes = {"GatedHistories": ["observer", observer], **graph["publicClasses"]}
    if lines[:len(classes)] != ["\t".join((name, *identity)) for name, identity in classes.items()]:
        raise ValueError("the JVM loaded a different observer, application or Spring class")
    states = []
    for line in lines[len(classes):]:
        row = json.loads(line)
        if row["id"] != len(states) or row["input"] is not None or row["adapter"] is not None:
            raise ValueError("invalid JVM snapshot dictionary")
        states.append(row["direct"])
    keys = {state_key(state): i for i, state in enumerate(states)}
    if len(keys) != len(states):
        raise ValueError("duplicate JVM snapshot")
    return states, keys


def check_grid(archive, stdout, graph, observer, evidence=None):
    states, keys = states_from_jvm(stdout, graph, observer)
    decisions = (evidence[0] if evidence is not None else
                 {(i["prefix"], i["subset"]): value["legacyDecision"] for i, value in roles()})
    patterns = Counter()
    admitted = empty = denied_with_error = final_errors = 0
    used = set()
    with gzip.open(archive, "rb") as stream:
        magic, *starts = HEADER.unpack(stream.read(HEADER.size))
        if magic != b"SGH1" or starts != [keys[state_key(baseline(shared))] for shared in (False, True)]:
            raise ValueError("different fresh-session baselines")
        for shared, prefix, order in product((False, True), PREFIXES, ORDERS):
            expected = {}
            for grants in product((False, True), repeat=3):
                if evidence is None:
                    steps = [(int(g), n, keys[state_key([b, e])]) for g, n, b, e in fresh_trace(shared, order, grants)]
                else:
                    applied = ()
                    steps = []
                    for edit, grant in zip(order, grants, strict=True):
                        if grant:
                            applied += (edit,)
                        state_id = keys[evidence[1][shared, applied]] if applied else starts[shared]
                        steps.append((int(grant), len(applied), state_id))
                expected[grants] = tuple(steps)
            prefix_bit = 16 * PREFIXES.index(prefix)
            for masks in product(range(16), repeat=3):
                raw = stream.read(HISTORY.size)
                if len(raw) != HISTORY.size:
                    raise ValueError(f"missing history {shared, prefix, order, masks}")
                data = HISTORY.unpack(raw)
                grants = tuple(decisions[prefix, mask] for mask in masks)
                steps = tuple(zip(data[8::3], data[9::3], data[10::3], strict=True))
                if data[:8] != (int(shared), prefix_bit, *order, *masks) or steps != expected[grants]:
                    raise ValueError(f"wrong input, decision, edit count, bean or ledger at {shared, prefix, order, masks}")
                patterns["".join("G" if g else "D" for g in grants)] += 1
                for grant, count, state_id in steps:
                    used.add(state_id)
                    admitted += grant
                    empty += count == 0
                    denied_with_error += not grant and states[state_id][1][0] > 0
                final_errors += states[steps[-1][2]][1][0]
        if stream.read(1) or used != set(range(len(states))):
            raise ValueError("extra history or an unreferenced JVM snapshot")
    histories = sum(patterns.values())
    return {"histories": histories, "attempts": histories * 3, "submittedEdits": admitted, "declines": histories * 3 - admitted,
            "emptyAppliedPrefixes": empty, "nonemptyAppliedPrefixes": histories * 3 - empty,
            "declinesWithEarlierError": denied_with_error, "historiesWithFinalError": final_errors,
            "observedStates": len(states), "decisionPatterns": dict(sorted(patterns.items()))}


def check_control(path, case):
    row = read(path)
    group, word = divmod(case, 4096)
    shared, prefix, order = group >= 12, PREFIXES[(group // 6) % 2], ORDERS[group % 6]
    masks = [(word >> shift) & 15 for shift in (8, 4, 0)]
    grants = [bool(mask & 11) for mask in masks]
    if (row["id"] != case or row["input"] != {"shared": shared, "prefix": prefix, "order": list(order), "masks": masks}
            or state_key(row["direct"]) != state_key(list(fresh_trace(shared, order, grants)))
            or state_key(row["adapter"]) != state_key(list(fresh_trace(shared, order, grants, always_first=True)))):
        raise ValueError(f"wrong public single-history control {case}")
    actual, wrong = row["direct"][-1], row["adapter"][-1]
    return {"case": case, "differentFinalBean": actual[2] != wrong[2], "differentFinalLedger": actual[3] != wrong[3]}


def run(work, out, case):
    started = perf_counter()
    graph = release_graph()
    command, observer = prepare(work, graph)
    if case is not None:
        subprocess.run([*command, "--case", str(case)], check=True)
        return
    sources = source_hashes()
    common = perf_counter() - started
    out.mkdir(parents=True, exist_ok=True)
    report = {"job": os.environ.get("VERIFY_JOB_ID"), "source": os.environ.get("VERIFY_SOURCE_COMMIT"),
              "graph": graph, "sources": sources, "observerClassSha256": observer, "commonSetupSeconds": common,
              "trials": {}, "controls": []}
    for name in TRIALS:
        started = perf_counter()
        evidence = producers(graph) if name.startswith("reuse") else None
        qualification = perf_counter() - started if evidence is not None else 0
        if evidence is not None and report.setdefault("producers", evidence[2]) != evidence[2]:
            raise ValueError("producer evidence changed between trials")
        archive, stdout = out / (name + ".bin.gz"), out / (name + ".stdout")
        cost = run_cmd([*command, archive, work, "GatedHistories", *graph["publicClasses"]], stdout)
        if cost["exit"]:
            raise ValueError(f"{name} public JVM exited {cost['exit']}")
        checking = perf_counter()
        result = check_grid(archive, stdout, graph, observer, evidence)
        archive_sha = digest(archive)
        ended = perf_counter()
        report["trials"][name] = {"jvm": cost, "observationsSha256": archive_sha, "producerCheckSeconds": qualification,
                                  "checkSeconds": ended - checking, "wholeSeconds": common + (ended - started)}
        first = report["trials"][TRIALS[0]]
        if (archive_sha != first["observationsSha256"] or cost["logSha256"] != first["jvm"]["logSha256"]
                or report.setdefault("counts", result) != result):
            raise ValueError("the paired public JVMs observed different trajectories")
    for identifier in CASES:
        path = out / f"control-{identifier}.json"
        cost = run_cmd([*command, "--case", str(identifier)], path)
        if cost["exit"]:
            raise ValueError(f"single-history control {identifier} failed")
        report["controls"].append(check_control(path, identifier))
    if [(r["differentFinalBean"], r["differentFinalLedger"]) for r in report["controls"]] != [(True, False), (False, True)]:
        raise ValueError("the two wrong-caller controls failed to distinguish bean and ledger")
    write(out / "measurement.json", report)
    print(report["counts"], flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEST)
    parser.add_argument("--case", type=int, help="replay a single history on the release JVM, alongside the always-apply-first control")
    args = parser.parse_args()
    if args.case is not None and not 0 <= args.case < 98304:
        parser.error("case must be 0 through 98303")
    with tempfile.TemporaryDirectory(prefix="gated-histories-") as tmp:
        run(Path(tmp), args.output.resolve(), args.case)
