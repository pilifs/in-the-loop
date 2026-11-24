"""Standalone, exception-aware assertions on the 187 pinned historical programs."""
import argparse
from collections import defaultdict
import gzip
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile

from history import scratch, HERE, JDK, JBMC, MODELS, OUTPUT, ROOT, benchmark, check_pin, digest, encoded, input_files, population
from standalone import decode  # the existing JBMC JSON property reader

RELOCATOR = ROOT / "examples/tools/contracts/src/main/java/net/terminalvalue/contracts/Relocate.java"


def classpath(entries):
    return os.pathsep.join(map(str, entries))


def compile_java(src, out, cp=()):
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run([JDK / "bin/javac", "-g", "-parameters", "-proc:none", "-cp", classpath(cp), "-d", out, *src], check=True)


def version(case):
    return case.get("after", case.get("classes", "conformance"))


def signature(case, files):
    owner, method = case["target"].split("#")
    source, = [p for p in files[version(case)] if p.name == owner.rsplit(".", 1)[-1] + ".java"]
    signature, = re.findall(r"\bpublic\s+static\s+([\w.\[\]]+)\s+" + re.escape(method) + r"\s*\(([^()]*)\)", source.read_text())
    ret, params = signature
    return owner, method, ret, [tuple(p.strip().split()) for p in params.split(",") if p.strip()]


def guard(case, params):
    arrays = [(t, n) for t, n in params if t.endswith("[]")]
    conditions = [f"{n} != null && {n}.length <= 8" for t, n in arrays]
    conditions += [f"{a} != {b}" for i, (t, a) in enumerate(arrays) for u, b in arrays[:i] if t == u]
    if case.get("assume"):
        conditions.append(case["assume"])
    if case.get("unchangedUnless"):
        excluded = case["unchangedUnless"]
        if "\\forall" in excluded:
            patterns = {r"!(\forall int i; 0 <= i && i < a.length - 1; a[i] <= a[i + 1])": "a[i] > a[i+1]",
                        r"!(\forall int i; 0 <= i && i < matches.length - 1; matches[i] < matches[i + 1])": "matches[i] >= matches[i+1]"}
            name = arrays[0][1]
            conditions.append(f"{name} != null")
            loop = f"for (int i=0; i+1 < {name}.length; ++i) if ({patterns[excluded]}) return 2;"
        else:
            conditions.append(f"!({excluded})")
            loop = ""
    else:
        loop = ""
    domain = " && ".join("(" + c + ")" for c in conditions)
    return ([f"if (!({domain})) return 2;"] if domain else []) + ([loop] if loop else [])


def property_body(case, owner, method, ret, params):
    body = []
    assertion = case["assert"]
    if r"\old" in assertion:
        if r"\old(out[0])" not in assertion:
            raise ValueError("unknown entry observation")
        body.append("byte entry = out.length == 0 ? 0 : out[0];")
        assertion = assertion.replace(r"\old(out[0])", "entry")
    signals = [clause.split(" when ") for clause in case.get("throws", [])]
    body.append("int expected = 0;")
    for i, (_, when) in enumerate(signals, 1):
        body.append(("if" if i == 1 else "else if") + f" ({when}) expected = {i};")
    args = ", ".join(n for _, n in params)
    body.extend([f"{ret} result;", f"try {{ result = {owner}.{method}({args}); }}", "catch (Throwable t) {"])
    for i, (typ, _) in enumerate(signals, 1):
        body.append(f"    if (t instanceof {typ}) return expected == {i} ? -2 : -1;")
    body += ["    return -1;", "}", f"return expected == 0 && ({assertion}) ? 1 : 0;"]
    return body


def relational_body(owner, method, ret, params):
    body, sides = [], [[], []]
    frame = []
    for typ, name in params:
        if typ.endswith("[]"):
            body += [f"{typ} old_{name} = new {typ[:-2]}[{name}.length];",
                     f"for (int i=0; i<{name}.length; ++i) old_{name}[i] = {name}[i];"]
            sides[0].append("old_" + name)
            sides[1].append(name)
            frame.append(f"for (int i=0; i<{name}.length; ++i) if (old_{name}[i] != {name}[i]) equal=false;")
        elif typ == "Interval":
            cls = owner.rsplit(".", 1)[0] + ".Interval"
            for index, prefix in enumerate(("before.", "")):
                dst = f"r{index}_{name}"
                ctor = f"new {prefix}{cls}({name}_lo, {name}_hi)"
                # The identical checked constructors exclude reversed intervals on both sides.
                body += [f"{prefix}{cls} {dst};", f"try {{ {dst} = {ctor}; }} catch (IllegalArgumentException e) {{ return 2; }}"]
                sides[index].append(dst)
        else:
            for side in sides:
                side.append(name)
    for i, prefix in enumerate(("before.", "")):
        body.append(f"Throwable t{i} = null;")
        if ret != "void":
            initial = "false" if ret == "boolean" else "null" if ret.endswith("[]") else "0"
            body.append(f"{ret} v{i} = {initial};")
        assign = f"v{i} = " if ret != "void" else ""
        body.append(f"try {{ {assign}{prefix}{owner}.{method}({', '.join(sides[i])}); }} catch (Throwable e) {{ t{i}=e; }}")
    body.append("boolean normal = t0 == null && t1 == null;")
    body.append("boolean equal = normal || (t0 != null && t1 != null && t0.getClass() == t1.getClass());")
    if ret != "void":
        if ret.endswith("[]"):
            body += ["if (normal && v0 != v1) {",
                     "    if (v0 == null || v1 == null || v0.length != v1.length) equal=false;",
                     "    else for (int i=0; i<v0.length; ++i) if (v0[i] != v1[i]) equal=false;", "}"]
        else:
            body.append("if (normal && v0 != v1) equal=false;")
    return body + frame + ["return normal ? (equal ? 1 : 0) : (equal ? -2 : -1);"]


def adapter(case, name, files):
    owner, method, ret, params = signature(case, files)
    flat = []
    for t, n in params:
        flat += [("int", n + "_lo"), ("int", n + "_hi")] if t == "Interval" else [(t, n)]
    decl = ", ".join(t + " " + n for t, n in flat)
    args = ", ".join(n for _, n in flat)
    body = guard(case, flat)
    if case["kind"] == "property":
        body += property_body(case, owner, method, ret, params)
    else:
        body += relational_body(owner, method, ret, params)
    code = [f"public final class {name} {{", f"    public static int observe({decl}) {{"]
    code += ["        " + line for line in body]
    code += ["    }", f"    public static void target({decl}) {{ int o=observe({args}); assert o==2 || o==1 || o == -2; }}",
             f"    public static void reach({decl}) {{ int o=observe({args}); assert o!=0 && o!=1; }}", "}"]
    return "\n".join(code) + "\n", flat


def original_classes(build, cases, source):
    classes = {**benchmark.compile_sources(build, source), **benchmark.compile_examples(build, cases)}
    tools = build / "helpers"
    compile_java([RELOCATOR, HERE / "java/PairClasses.java", HERE / "java/StockReplay.java", benchmark.RUNNER_SOURCE], tools)
    for v in sorted({c["before"] for c in cases if c["kind"] == "regression"}):
        relocated = build / "relocated" / v
        subprocess.run([JDK / "bin/java", "-cp", tools, "net.terminalvalue.contracts.PairClasses", classes[v], relocated], check=True)
        classes["before-" + v] = relocated
    return classes, tools


def adapters(build, cases, source):
    files = input_files(cases)
    files["conformance"] = [source]
    classes, helpers = original_classes(build, cases, source)
    for c in cases:
        if c["target"].startswith("bench.held.Overlap#"):
            record = Path("bench/held/Interval.class")
            if digest(classes[c["before"]] / record) != digest(classes[c["after"]] / record):
                raise ValueError("the interval constructors no longer have identical admission semantics")
    groups = defaultdict(list)
    for i, case in enumerate(cases):
        cp = [classes[version(case)]]
        if case["kind"] == "regression":
            cp.append(classes["before-" + case["before"]])
        groups[tuple(cp)].append((case, f"StockCase{i:03d}"))
    subjects = []
    for index, (cp, group) in enumerate(groups.items()):
        folder = build / f"group{index:02d}"
        folder.mkdir()
        sources = []
        for case, name in group:
            path = folder / (name + ".java")
            code, params = adapter(case, name, files)
            path.write_text(code)
            sources.append(path)
            subjects.append((case, name, params, path, [folder, *cp]))
        compile_java(sources, folder, cp)
    return subjects, classes, helpers


def scalar(typ, value):
    if typ == "boolean":
        return {"true": True, "false": False}[value["data"]]
    bits = value["binary"]
    number = int(bits, 2)
    if typ in ("float", "double"):
        width = 32 if typ == "float" else 64
        if len(bits) != width:
            raise ValueError("floating input has the wrong width")
        return f"bits:0x{number:0{width//4}x}"
    return number - (1 << len(bits)) if typ != "char" and bits[0] == "1" else number


def arguments(trace, name, method, params, bound):
    values, memory = {}, {}
    types = dict((n, t) for t, n in params)
    for s in trace:
        if s.get("stepType") == "assignment":
            memory[s["lhs"]] = s["value"]
        if s.get("stepType") != "input" or not s.get("sourceLocation", {}).get("function", "").startswith(f"java::{name}.{method}:"):
            continue
        key = s["inputID"]
        if key not in types:
            continue
        typ, val = types[key], s["values"][0]
        if not typ.endswith("[]"):
            values[key] = scalar(typ, val)
        else:
            ptr = val["data"]
            if ptr == "null":
                values[key] = None
                continue
            length = int(memory[ptr + ".length"]["data"])
            if not 0 <= length <= bound:
                raise ValueError("input outside the declared bound")
            items = []
            if length:
                backing = memory[ptr + ".data"]["data"]
                items = [scalar(typ[:-2], memory[f"{backing}[{i}L]"]) for i in range(length)]
            values[key] = items
    return [values[n] for _, n in params]


def stock_run(name, method, cp, params, archive, prefix, *, bound=8, unwind=16):
    cmd = [str(JBMC), name, "--classpath", classpath([*cp, MODELS]), "--function", f"{name}.{method}",
           "--unwind", str(unwind), "--unwinding-assertions", "--throw-runtime-exceptions", "--max-nondet-array-length", str(bound),
           "--max-nondet-tree-depth", "4", "--sat-solver", "cadical", "--trace", "--json-ui"]
    measured = benchmark.measure(cmd, 120)
    archive.writestr(prefix + "/argv.json", encoded(cmd))
    archive.writestr(prefix + "/stdout", measured["stdout"])
    archive.writestr(prefix + "/stderr", measured["stderr"])
    row = decode(measured["stdout"].encode(), measured["stderr"].encode(), 124 if measured["killed"] else measured["exit"], method, name)
    row.pop("inputs", None)
    row.update({k: measured[k] for k in ("seconds", "cpuSeconds", "peakMB", "exit", "killed")})
    if row["status"] == "FAILURE":
        data = json.loads(measured["stdout"])
        target, = [p for part in data for p in part.get("result", []) if p["property"] == row["target"]["property"]]
        try:
            row["arguments"] = arguments(target["trace"], name, method, params, bound)
        except (KeyError, ValueError, IndexError):
            row["inputStatus"] = "trace not reconstructed"
    return row


def replay(name, row, cp, helpers):
    if "arguments" not in row:
        return
    tokens = ";".join(benchmark.token(v, chars=False) for v in row["arguments"])
    cmd = [str(JDK / "bin/java"), "-ea", "-cp", classpath([helpers, *cp]), "StockReplay", name, tokens]
    result = subprocess.run(cmd, text=True, capture_output=True, timeout=30)
    row["jvmReplay"] = {"argv": cmd, "exit": result.returncode, "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}
    return tokens


def run(phase, out, prepare_only):
    os.environ.update(JAVA_HOME=str(JDK), PATH=str(JDK / "bin") + os.pathsep + os.environ["PATH"])
    cases, _ = population()
    with scratch(prefix="stock-history-") as tmp:
        build = Path(tmp)
        pin, source = check_pin(build)
        subjects, classes, helpers = adapters(build, cases, source)
        if len(subjects) != 187 or len({c["id"] for c, *_ in subjects}) != 187:
            raise ValueError("incomplete stock adapters")
        controls = {}
        for c, name, _, _, cp in subjects:
            if "witness" in c:
                control = {"arguments": c["witness"]}
                replay(name, control, cp, helpers)
                if control["jvmReplay"]["stdout"] not in ("observation=0", "observation=-1") or control["jvmReplay"]["exit"]:
                    raise ValueError("stock caller missed the independent JVM witness: " + c["id"])
                controls[c["id"]] = control
        if prepare_only:
            print(f"Compiled 187 target/reach adapters with isolated versions; replayed {len(controls)} archived JVM witnesses")
            return
        out.mkdir(parents=True, exist_ok=True)
        rows, reference, independent = {}, [], []
        with zipfile.ZipFile(out / "executions.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            for c, name, params, java, cp in subjects:
                cid = c["id"]
                archive.write(java, cid + "/" + java.name)
                archive.write(cp[0] / (name + ".class"), cid + "/" + name + ".class")
                row = {"expected": c["expected"], "entry": name, "originalClasspath": [str(p) for p in cp],
                       "profile": "ubuntu-24.04-packaged", "inputs": params, "sourceSha256": digest(java)}
                for method in ("target", "reach"):
                    data = stock_run(name, method, cp, params, archive, cid + "/" + method)
                    tokens = replay(name, data, cp, helpers)
                    if method == "target" and tokens is not None and c["group"] in (2, 3):
                        reference.append(f"{cid}\tcheck\t{tokens}")
                        independent.append(data)
                    row[method] = data
                rows[cid] = row
                print(cid, row["target"]["status"], row["reach"]["status"], flush=True)
        if reference:
            answers = benchmark.on_the_jvm(benchmark.HERE / "Reference.java", [str(classes["v1"].parent)], reference, build, "stock-witnesses")
            if len(answers) != len(reference):
                raise ValueError("incomplete independent replay")
            for query, data, answer in zip(reference, independent, answers):
                if answer.split("\t")[0] != query.split("\t")[0]:
                    raise ValueError("wrong replay identity")
                data["independentJvm"] = answer
        hashes = {k: {p.relative_to(folder).as_posix(): digest(p) for p in sorted(folder.rglob("*.class"))}
                  for k, folder in classes.items()}
        report = {"phase": phase, "schema": "beyond-jbmc-historical-stock/v1", "frozenSha256": pin["archive"]["sha256"],
                  "classesSha256": hashes, "jbmcSha256": digest(JBMC), "modelsSha256": digest(MODELS),
                  "jdkModulesSha256": digest(JDK / "lib/modules"), "archiveSha256": digest(out / "executions.zip"),
                  "job": os.environ.get("VERIFY_JOB_ID"), "sourceCommit": os.environ.get("VERIFY_SOURCE_COMMIT"),
                  "archivedWitnessesOnJvm": controls, "rows": [{"case": c["id"], **rows[c["id"]]} for c in cases]}
        (out / "results.json.gz").write_bytes(gzip.compress(encoded(report), mtime=0))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("phase", choices=("opening", "closing"))
    ap.add_argument("--output", type=Path)
    ap.add_argument("--prepare-only", action="store_true")
    args = ap.parse_args()
    run(args.phase, args.output or OUTPUT / args.phase / "stock", args.prepare_only)
