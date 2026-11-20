"""Compare inlined and independently checked finite stage facts on one unchanged importer."""

from copy import deepcopy
import hashlib
import json
import os
import resource
from pathlib import Path
import sys
import tempfile
import time
import zipfile

EXAMPLE = Path(__file__).resolve().parents[1]
EXAMPLES = EXAMPLE.parent
sys.path.insert(0, str(EXAMPLES / "tools"))
from targets import finite_check, route, runtime, runtime_jdk, runtime_maven


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def jar_classes(dir_):
    return {p.relative_to(dir_).as_posix(): runtime.sha256(p) for p in sorted(dir_.rglob("*.class"))}


def job_basis(number, revision, task_ids):
    (folder,) = EXAMPLES.glob(str(number) + "-*")
    example = json.loads((folder / "example.json").read_text())
    target = json.loads((folder / "target.json").read_text())
    checked = []
    for task in task_ids:
        plan = route.resolve(folder, example, target, task + "-" + revision)
        for path in sorted((folder / "records/finite-proofs").glob("*/" + plan.task + ".json"), reverse=True):
            record = json.loads(path.read_text())
            if record.get("status") not in ("established", "refuted"):
                continue
            finite_check.validate_record(plan, record)
            checked.append(
                {
                    "task": plan.task,
                    "sourceKey": plan.claim["key"],
                    "status": record["status"],
                    "receipt": str(path.relative_to(EXAMPLES.parent)),
                    "sha256": runtime.sha256(path),
                }
            )
            break
        else:
            raise ValueError(f"{number} {plan.task} needs a checked producer receipt")
    return checked


class Experiment:
    def __init__(self, work, table, catalog):
        self.work = work
        self.table = table
        self.catalog = catalog
        self.home = Path(runtime_jdk.home("21"))
        self.jdk = runtime_jdk.identity(self.home)
        self.jars = {}
        self.metrics = []
        self.count = 0
        cache = runtime_maven.Cache()
        for name, item in catalog.items():
            file = work / (name + ".jar")
            ok, why = cache.restore(item["sha256"], file)
            if not ok:
                raise ValueError(f"{name}: {why}; rebuild its recorded artifact")
            self.jars[name] = file
        self.app = work / "application"
        self.app.mkdir()
        self.classes = {}
        self.env = runtime._verifier_env(self.jdk)
        self.runner = EXAMPLE / "controls/composition/measure"
        self.compile(
            "application",
            self.app,
            [self.jars[n] for n in ("csv-fix", "io-api", "codec")],
            [EXAMPLE / "client/importer/PageImporter.java"],
        )
        expected = json.loads((EXAMPLE / "records/matrix/matrix.json").read_text())["clientClasses"]
        if {Path(n).name: v for n, v in jar_classes(self.app).items()} != expected:
            raise ValueError("the compiler produced different application bytes from the original matrix")
        self.unused = []
        for value in (0, 1):
            dest = work / f"unused-{value}"
            dest.mkdir()
            src = dest / "Marker.java"
            src.write_text(
                f"package unrelated; public final class Marker {{ public static int value() {{ return {value}; }} }}\n"
            )
            self.compile("unrelated control", dest, [], [src])
            archive = work / f"unused-{value}.jar"
            with zipfile.ZipFile(archive, "w") as jar:
                info = zipfile.ZipInfo("unrelated/Marker.class", (2026, 1, 1, 0, 0, 0))
                jar.writestr(info, (dest / "unrelated/Marker.class").read_bytes())
            self.unused.append(archive)
        if runtime.sha256(self.unused[0]) == runtime.sha256(self.unused[1]):
            raise ValueError("unused JAR control does not differ")
        self.setup = self.metrics[:]
        self.metrics.clear()

    def measured(self, label, argv):
        self.count += 1
        stdout = self.work / f"stdout-{self.count}"
        stderr = self.work / f"stderr-{self.count}"
        usage = {}
        status, code, took = runtime._run_one(
            list(map(str, argv)), self.work, stdout, stderr, 120, env=self.env, usage=usage
        )
        if status != "exited" or code != 0:
            raise ValueError(f"{label}: {status} {code}: {stderr.read_text()[-1500:]}")
        self.metrics.append({"phase": label, "wallSeconds": took, **usage})
        return stdout.read_bytes()

    def compile(self, label, dest, cp, sources):
        flags = ["--release", "21", "-encoding", "UTF-8", "-parameters", "-g", "-implicit:none", "-proc:none"]
        self.measured(
            "compile " + label,
            [self.home / "bin/javac", *flags, "-cp", os.pathsep.join(map(str, cp)), "-d", dest, *sources],
        )

    def tool(self, name):
        if name in self.classes:
            return self.classes[name]
        dest = self.work / name
        dest.mkdir()
        paths = [self.app]
        sources = [self.runner / (name + ".java")]
        if name != "IOFact":
            sources.append(EXAMPLES / "tools/targets/java/org/intheloop/controls/Grid.java")
            paths += [self.jars[k] for k in ("csv-fix", "io-api", "codec")]
        self.compile(name, dest, paths, sources)
        self.classes[name] = (dest, digest(jar_classes(dest)))
        return self.classes[name]

    def launch(self, name, paths, rows, label):
        dest, _ = self.tool(name)
        input_ = self.work / f"inputs-{self.count}"
        input_.write_text("".join("\t".join(map(str, row)) + "\n" for row in rows))
        log = self.work / f"loaded-{self.count}"
        cp = os.pathsep.join(map(str, [dest, *paths]))
        output = self.measured(
            label,
            [
                self.home / "bin/java",
                "-XX:-UsePerfData",
                f"-Xlog:class+load=info:file={log}",
                "-cp",
                cp,
                "measure." + name,
                input_,
            ],
        )
        loads = log.read_text()
        if "unrelated.Marker source:" in loads:
            raise ValueError("the unused control class was loaded")
        if name == "IOFact" and "org.apache.commons.csv." in loads:
            raise ValueError("the byte producer loaded CSV")
        return output.decode().splitlines()

    @staticmethod
    def inputs(case):
        i = case["input"]
        source = (b"\xef\xbb\xbf" if i["bom"] else b"") + i["doc"].encode()
        return (source.hex(), int(i["oneByte"]), int(i["preview"]), i["start"], i["cap"])

    def inline(self, io, csv, unused, cache, force=False):
        dest, code = self.tool("Inline")
        paths = [self.app, self.jars[io], self.jars[csv], self.jars["codec"], self.unused[unused]]
        cp = [digest(jar_classes(self.app)), *[runtime.sha256(p) for p in paths[1:]]]
        key = digest([code, self.jdk["release"], cp, self.table])
        if key in cache and not force:
            return cache[key], {"computed": 0, "reused": len(self.table)}, cp
        rows = [(c["id"], *self.inputs(c)) for c in self.table]
        direct = {
            x["id"]: x["direct"]
            for x in map(json.loads, self.launch("Inline", paths, rows, "inline JVM checking"))
        }
        if set(direct) != set(range(len(self.table))):
            raise ValueError("incomplete direct matrix")
        cache[key] = direct
        return direct, {"computed": len(rows), "reused": 0}, cp

    def composed(self, io, csv, unused, cache):
        _, code = self.tool("IOFact")
        io_inputs = sorted({self.inputs(c)[:3] for c in self.table})
        io_key = digest(
            [code, jar_classes(self.app), self.jdk["release"], runtime.sha256(self.jars[io]), io_inputs]
        )
        fresh_io = io_key not in cache
        if fresh_io:
            result = self.launch(
                "IOFact",
                [self.app, self.jars[io]],
                [(i, *v) for i, v in enumerate(io_inputs)],
                "IO and decoder JVM checking",
            )
            io_rows = {}
            for line in result:
                index, raw, units, eof = line.split("\t")
                if (
                    bytes.fromhex(raw).decode("utf-8") != bytes.fromhex(units).decode("utf-16-be")
                    or eof != "-1"
                ):
                    raise ValueError(
                        "the decoder or the second EOF observation disagrees with the byte postcondition"
                    )
                if int(index) in io_rows:
                    raise ValueError("duplicate IO fact")
                io_rows[int(index)] = (raw, units)
            if set(io_rows) != set(range(len(io_inputs))):
                raise ValueError("incomplete IO facts")
            cache[io_key] = io_rows
        io_rows = cache[io_key]
        io_for = dict(zip(io_inputs, [io_rows[i] for i in range(len(io_inputs))]))
        keys = sorted({(io_for[self.inputs(c)[:3]][1], *self.inputs(c)[3:]) for c in self.table})
        _, code = self.tool("CSVFact")
        csv_paths = [self.jars[io], self.jars[csv], self.jars["codec"]]
        csv_closure = [code, self.jdk["release"], *[runtime.sha256(p) for p in csv_paths]]
        by_input = {k: digest([csv_closure, k]) for k in keys}
        pending = [k for k in keys if by_input[k] not in cache]
        if pending:
            results = self.launch(
                "CSVFact", csv_paths, [(i, *k) for i, k in enumerate(pending)], "CSV JVM checking"
            )
            accepted = set()
            for row in map(json.loads, results):
                index = row["id"]
                if index in accepted or tuple(row["input"]) != pending[index]:
                    raise ValueError("CSV fact has another precondition")
                accepted.add(index)
                cache[by_input[pending[index]]] = row["direct"]
            if accepted != set(range(len(pending))):
                raise ValueError("incomplete CSV facts")
        outputs = {}
        for c in self.table:
            raw, units = io_for[self.inputs(c)[:3]]
            pre = (units, *self.inputs(c)[3:])
            outputs[c["id"]] = {"bytes": raw, **cache[by_input[pre]]}
        counts = {
            "IO": {"computed": len(io_inputs) if fresh_io else 0, "reused": 0 if fresh_io else len(io_inputs)},
            "CSV": {"computed": len(pending), "reused": len(keys) - len(pending)},
            "linkedInputs": len(outputs),
        }
        facts = {
            "IO": {
                "key": io_key,
                "classpath": [digest(jar_classes(self.app)), runtime.sha256(self.jars[io])],
                "rows": [
                    {"input": v, "bytes": io_rows[i][0], "utf16": io_rows[i][1], "eof": -1}
                    for i, v in enumerate(io_inputs)
                ],
            },
            "CSV": {
                "classpath": csv_closure[2:],
                "rows": [{"input": k, "key": by_input[k], "observed": cache[by_input[k]]} for k in keys],
            },
        }
        return outputs, counts, facts

    def judge(self, outputs, io, csv, unused):
        failures = {k: [] for k in ("bytes", "count", "page")}
        for case in self.table:
            row = outputs[case["id"]]
            for k, expected in case["expected"].items():
                observed = list(bytes.fromhex(row[k])) if k == "bytes" else row[k]
                if observed != expected:
                    failures[k].append(case["id"])
        witnesses = {k: v[0] for k, v in failures.items() if v}
        if witnesses:
            ids = sorted(set(witnesses.values()))
            selected = [(i, *self.inputs(self.table[i])) for i in ids]
            fresh = self.launch(
                "Inline",
                [self.app, self.jars[io], self.jars[csv], self.jars["codec"], self.unused[unused]],
                selected,
                "independent JVM witness replay",
            )
            evidence = {x["id"]: x["direct"] for x in map(json.loads, fresh)}
            if evidence != {i: outputs[i] for i in ids}:
                raise ValueError("counterexample did not reproduce on the full ordered classpath")
        return {
            "differences": {k: len(v) for k, v in failures.items()},
            "witnesses": witnesses,
            "allRowsSha256": digest(outputs),
        }


def execute(work, strategy, catalog, table):
    t0 = time.monotonic()
    e = Experiment(work, table, catalog)
    setup = time.monotonic() - t0
    baseline = {}
    outputs = []
    transfers = {}
    scenarios = [
        ("clean", "parent", "parent", 0),
        ("unchanged", "parent", "parent", 0),
        ("change-io", "fix", "parent", 0),
        ("change-csv", "parent", "fix", 0),
        ("change-unused", "parent", "parent", 1),
        ("both-fixes", "fix", "fix", 0),
    ]
    for name, i, c, unused in scenarios:
        cache = deepcopy(baseline)
        e.metrics.clear()
        io, csv = "io-" + i, "csv-" + c
        start = time.monotonic()
        runtime_path = [digest(jar_classes(e.app)), e.catalog[io]["sha256"], e.catalog[csv]["sha256"],
                        e.catalog["codec"]["sha256"], runtime.sha256(e.unused[unused])]
        prepared_key = digest([e.jdk["release"], runtime_path, digest(table), ["bytes", "count", "page"]])
        if strategy == "inline":
            actual, counts, cp = e.inline(io, csv, unused, cache)
            extra = {"classpath": cp}
            counts["wholeClaimsReused"] = 3 if counts["reused"] else 0
            counts["wholeClaimsComputed"] = 3 - counts["wholeClaimsReused"]
        else:
            actual, counts, facts = e.composed(io, csv, unused, cache)
            transfers[name] = facts
            extra = {"stageFactsSha256": digest(facts)}
            counts["claimsJoinedFromCheckedFacts"] = ["bytes", "count", "page"]
        result = e.judge(actual, io, csv, unused)
        measured = time.monotonic() - start
        if name == "clean":
            baseline = cache
        phases = list(e.metrics)
        if name == "clean":
            phases = e.setup + phases
        wall = measured + (setup if name == "clean" else 0.0)
        outputs.append(
            {
                "scenario": name,
                "cell": [i, c],
                "unusedJarSha256": runtime.sha256(e.unused[unused]),
                "preparedKey": prepared_key,
                "runtimeClasspath": runtime_path,
                "coordinatorRssHighwaterBytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
                "outcomes": result,
                "work": counts,
                "wallSeconds": round(wall, 5),
                "preparationSeconds": round(
                    sum(p["wallSeconds"] for p in phases if p["phase"].startswith("compile")), 5
                ),
                "checkingSeconds": round(
                    sum(p["wallSeconds"] for p in phases if p["phase"].endswith("JVM checking")), 5
                ),
                "replaySeconds": round(
                    sum(p["wallSeconds"] for p in phases if p["phase"] == "independent JVM witness replay"), 5
                ),
                "peakChildRssBytes": max((p["peakRssBytes"] for p in phases), default=0),
                "phases": phases,
                **extra,
            }
        )
    return outputs, transfers


def main():
    table = json.loads((EXAMPLE / "controls/table.json").read_text())["cases"]
    catalog = json.loads((EXAMPLE / "controls/libraries.json").read_text())
    basis = {
        str(n): {rev: job_basis(n, rev, keys) for rev in ("parent", "fix")}
        for n, keys in ((338, ("bytes", "eof")), (339, ("count", "labels", "fields")))
    }
    report = {
        "schema": "finite-importer-composition/v1",
        "strategy": "Exhaustive finite JVM evaluation and independently replayed counterexamples",
        "producerPrecedents": basis,
        "assumptions": [
            "stock pinned JDK",
            "fresh input streams and parsers",
            "three literal documents and the frozen 96 selectors",
        ],
        "costScope": "Each strategy starts with a fresh application build and empty proof cache. Updates individually start from the cold parent/parent proof store. JVM wall and process RSS include launch. The OS page cache is uncontrolled; the four separate Maven builds are recorded separately.",
        "reuse": "The byte-only client runs without CSV or Codec. A CSV stage is keyed by the complete runtime IO/CSV/Codec closure and the exact UTF-16 text, start and cap. An unrelated JAR is omitted only from the isolated producers; every scenario is also checked on the full classpath.",
    }
    report["transferContracts"] = {}
    for producer in (338, 339):
        (folder,) = EXAMPLES.glob(str(producer) + "-*")
        path = folder / "controls/importer-transfer.json"
        contract = json.loads(path.read_text())
        if contract["consumer"] != "345" or set(contract["sourceClaims"]) != {
            r["task"] for group in basis[str(producer)].values() for r in group
        }:
            raise ValueError("the available producer receipts differ from the declared transfer contract")
        report["transferContracts"][str(producer)] = {
            "path": str(path.relative_to(EXAMPLES.parent)),
            "sha256": runtime.sha256(path),
        }
    with tempfile.TemporaryDirectory(prefix="importer-composition-") as directory:
        for strategy in ("inline", "composed"):
            where = Path(directory) / strategy
            where.mkdir()
            report[strategy], facts = execute(where, strategy, catalog, table)
        # Independently recompute every complete call and observer on the four actual artifact pairs.
        authoritative = json.loads((EXAMPLE / "records/matrix/matrix.json").read_text())["configurations"]
        for direct, composed in zip(report["inline"], report["composed"], strict=True):
            cell = "-".join(direct["cell"])
            raw = (EXAMPLE / "records/matrix" / (cell + ".jsonl")).read_bytes()
            if hashlib.sha256(raw).hexdigest() != authoritative[cell]["stdoutSha256"]:
                raise ValueError("the original independently calibrated JVM stream changed")
            rows = {}
            for row in map(json.loads, raw.splitlines()):
                observed = dict(row["direct"])
                observed["bytes"] = bytes(observed["bytes"]).hex()
                rows[row["id"]] = observed
            if (
                direct["outcomes"] != composed["outcomes"]
                or direct["preparedKey"] != composed["preparedKey"]
                or direct["outcomes"]["allRowsSha256"] != digest(rows)
                or direct["outcomes"]["differences"] != authoritative[cell]["mismatches"]
            ):
                raise ValueError("stage composition differs from the independently run full client")
        for key in ("IO", "CSV"):
            (folder,) = EXAMPLES.glob(("338" if key == "IO" else "339") + "-*")
            target = folder / "records/importer-facts.json"
            target.write_text(json.dumps({name: rows[key] for name, rows in facts.items()}, indent=2) + "\n")
    out = EXAMPLE / "records/composition.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print("six scenarios match all original byte/count/page outcomes; records/composition.json")


if __name__ == "__main__":
    main()
