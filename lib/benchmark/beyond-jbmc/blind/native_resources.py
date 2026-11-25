"""Scaffold and measure strict release-owned resource lookup and replay on unmodified original classpaths."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import zipfile

from scaffold_first import DEST, HERE, JDK, compile_java, digest, javaenv, read, registered, save, scratch
from history import ROOT, benchmark, encoded
from release_cases import Claim, Subject, jvm_controls, measure_subject
from stock_history import classpath

OUT = DEST / "native-resource"
MISSING = "META-INF/missing"
NAMES = {
    "plain": "META-INF/paint",
    "compensating": "META-INF/paint",
    "context": "META-INF/services/probe$Marker",
    "index": "META-INF/annotations/java.lang.Deprecated",
    "dom4j": "META-INF/services/javax.xml.parsers.SAXParserFactory",
}


def resource(jar, name, contents):
    with zipfile.ZipFile(jar, "w") as archive:
        archive.writestr(zipfile.ZipInfo(name), contents)


def original(classes, jars, work, main="PairResourceGate"):
    cmd = [JDK / "bin/java", "-XX:-UsePerfData", "-ea", "-cp", classpath([classes, *jars]), main]
    return subprocess.check_output(cmd, cwd=work, env=javaenv(), text=True, timeout=40).strip()


def bridge_control(work, sides):
    source = work / "ReadOriginalLoaders.java"
    source.write_text("""import witness.OriginalGraph;
public class ReadOriginalLoaders {
    public static void main(String[] args) {
        ClassLoader caller = Thread.currentThread().getContextClassLoader();
        for (int side : new int[]{0, 1, 1, 0}) {
            Object v = OriginalGraph.call(side, "PairResourceGate", "read", new Class<?>[]{boolean.class}, true);
            System.out.println(v);
            if (Thread.currentThread().getContextClassLoader() != caller) throw new AssertionError("loader leaked on return");
        }
        try {
            OriginalGraph.call(0, "PairResourceGate", "missingMethod", new Class<?>[]{});
            throw new AssertionError("missing method returned");
        } catch (IllegalStateException expected) {
            if (Thread.currentThread().getContextClassLoader() != caller) throw new AssertionError("loader leaked on failure");
        }
    }
}""")
    classes = work / "bridge"
    env = javaenv()
    compile_java([HERE.parent / "wire-more/OriginalGraph.java", source], classes, [], env)
    for side, key in (("old", "WIRE_ORIGINAL_BEFORE"), ("new", "WIRE_ORIGINAL_AFTER")):
        original_classes, jars = sides[side]
        env[key] = classpath([original_classes, *jars])
    data = subprocess.check_output([JDK / "bin/java", "-XX:-UsePerfData", "-cp", classes, "ReadOriginalLoaders"],
                                   cwd=work, env=env, text=True, timeout=30).splitlines()
    if data != ["65", "66", "66", "65"]:
        raise ValueError("the context loader escaped its original release")
    return data


def build(work, case):
    template = (HERE / "resource-native/PairResourceGate.java").read_text()
    graphs = {s: [] for s in ("old", "new")}
    if case in ("index", "dom4j"):
        _, _, _, _, graphs = registered("15" if case == "index" else "16")
    results, sides = {}, {}
    for i, side in enumerate(("old", "new")):
        folder = work / side
        folder.mkdir()
        src = folder / "PairResourceGate.java"
        code = template.replace("META-INF/paint", NAMES[case])
        if case == "index":
            code = code.replace("PairResourceGate.class", "org.jvnet.hudson.annotation_indexer.Index.class")
        elif case == "dom4j":
            code = code.replace("PairResourceGate.class", "org.dom4j.DocumentHelper.class")
        elif case == "context":
            code = code.replace("PairResourceGate.class.getClassLoader()", "Thread.currentThread().getContextClassLoader()")
        if i:
            code = code.replace("return value;", "return value - 1;" if case == "compensating" else "return value & 255;")
        src.write_text(code)
        jars = list(graphs[side])
        sources = [src]
        fixture = folder / "fixture.jar"
        if case != "dom4j":
            data = [b"p.A\np.B\n", b"q.A\np.B\n"][i] if case == "index" else bytes([65+i])
            resource(fixture, NAMES[case], data)
            jars.append(fixture)
        if case == "index":
            consumer = folder / "ReadIndex.java"
            consumer.write_text("""import java.util.TreeSet;
import org.jvnet.hudson.annotation_indexer.Index;
public class ReadIndex {
    public static void main(String[] args) throws Exception {
        ClassLoader loader = Index.class.getClassLoader();
        System.out.println(new TreeSet<>(Index.listClassNames(Deprecated.class, loader)));
        System.out.println(new TreeSet<>(Index.listClassNames(Override.class, loader)));
    }
}""")
            sources.append(consumer)
        classes = folder / "classes"
        compile_java(sources, classes, jars, javaenv())
        got = original(classes, jars, work)
        expected = -1 if case == "dom4j" else 112+i if case == "index" else 65 if case == "compensating" else 65+i
        if got != f"-1,{expected}":
            raise ValueError(f"{case} {side} physical values differ: {got}")
        results[side] = {"observations": [-1, expected], "sourceSha256": digest(src), "classSha256": digest(classes / "PairResourceGate.class"),
                         "orderedJarDigests": [digest(j) for j in jars]}
        if case == "index":
            names = original(classes, jars, work, "ReadIndex").splitlines()
            if names != [["[p.A, p.B]", "[]"], ["[p.B, q.A]", "[]"]][i]:
                raise ValueError("original indexer did not consume the registered resources")
            results[side]["publicIndexContents"] = names
        sides[side] = classes, jars
    registered_scope = {"case": case, "target": "PairResourceGate#read", "inputs": [False, True],
                        "entry": "ClassLoader.getResources, first URL and first original stream byte",
                        "selected": NAMES[case], "control": MISSING, "jdkModulesSha256": digest(JDK / "lib/modules"), "sides": results}
    if case == "context":
        registered_scope["bridgeOldNewNewOld"] = bridge_control(work, sides)
    return sides, registered_scope


def check(checker, work, sides, label, expected, zipfile_out, *, paired=False, cache="repeat"):
    cache_path = work / ("cache-" + cache)
    old, new = sides["old"], sides["new"]
    cmd = [checker, "equivalence", "--before", old[0], "--after", new[0], "--before-classpath", classpath(old[1]),
           "--classpath", classpath(new[1]), "--target", "PairResourceGate#read", "--engine", "native",
           "--gaps", "strict", "--unwind", "16", "--max-array-length", "8", "--timeout", "120",
           "--work", work / ("check-" + label), "--cache", cache_path, "--json"]
    if paired:
        cmd += ["--assume", "true"]
    measured = benchmark.measure(list(map(str, cmd)), 180)
    result = benchmark.outcome_of({"kind": "regression"}, measured["stdout"]) or {}
    trace = {"name": label, "rawVerdict": result.get("verdict"), "firstProblem": result.get("problem"),
             "reuse": result.get("reuse"), "witness": result.get("counterexample"), "replay": result.get("replay"),
             "assumptions": (result.get("stated") or {}).get("assumptions", []),
             "seconds": measured["seconds"], "cpuSeconds": measured["cpuSeconds"]}
    for stream in ("stdout", "stderr"):
        zipfile_out.writestr(label + "/" + stream, measured[stream])
    zipfile_out.writestr(label + "/argv.json", encoded(list(map(str, cmd))))
    verdict = trace["rawVerdict"]
    if not verdict or measured["killed"]:
        raise ValueError("missing native outcome")
    if expected[0] != expected[1] and verdict == "verified":
        raise ValueError(f"incorrect resource proof: {label}")
    if verdict == "violation":
        witness = trace["witness"]
        if expected[0] == expected[1] or witness["inputs"][0]["value"] is not True or [witness["before"], witness["after"]] != list(map(str, expected)):
            raise ValueError(f"resource witness does not reproduce on original JVMs: {label}")
    return trace


def direct_profiles(case, work, sides, scope, checker, selected):
    """Keep each original binary on its own graph for the two conjuncts of the finite relation."""
    for side in selected:
        directory = work / ("profiles-" + side)
        directory.mkdir()
        expected = scope["sides"][side]["observations"]
        source = directory / "ResourceConjunct.java"
        source.write_text(f"""public class ResourceConjunct {{
    public static boolean primary(boolean selected) throws Exception {{
        return PairResourceGate.read(selected) == (selected ? {expected[1]} : {expected[0]});
    }}
    public static boolean wrong(boolean selected) throws Exception {{
        return !primary(selected);
    }}
}}""")
        env = javaenv()
        caller, jars = sides[side]
        classes = directory / "claims"
        compile_java([source], classes, [caller, *jars], env)
        cp = [classes, caller, *jars]
        both = (("false",), ("true",))
        subject = Subject(0, "ResourceConjunct", "original deployment", (
            Claim("primary", "boolean selected", holds=both), Claim("wrong", "boolean selected", holds=(), fails=both)), 8, 16)
        physical = jvm_controls(subject, directory, cp, env)
        record = {"jvm": physical, "rows": [], "source": os.environ.get("VERIFY_SOURCE_COMMIT"), "job": os.environ.get("VERIFY_JOB_ID"),
                  "checkerSha256": digest(checker), "question": source.read_text(), "registered": digest(OUT / "registrations" / (case + ".json"))}
        measure_subject(case, subject, "separate original inputs", directory, env, cp, record, OUT / "comparators" / case / side, False)


def run(case, prepare_only, profiles):
    registry = OUT / "registrations" / (case + ".json")
    with scratch(prefix="release-resource-scope-") as tmp:
        work = Path(tmp)
        sides, scope = build(work, case)
        if prepare_only:
            save(registry, scope)
            print(case, [v["observations"] for v in scope["sides"].values()], flush=True)
            return
        if read(registry) != scope:
            raise ValueError("original caller or resource bytes differ from preregistration")
        os.environ.update(javaenv())
        checker = Path(os.environ.get("JVMCONTRACT", ROOT / "lib/target/release/jvmcontract")).resolve()
        if profiles:
            direct_profiles(case, work, sides, scope, checker, profiles)
            return
        out = OUT / case
        out.mkdir(parents=True, exist_ok=True)
        rows = []
        expected = [v["observations"][1] for v in scope["sides"].values()]
        with zipfile.ZipFile(out / "executions.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            for label in ("cold", "warm", "clean", "paired"):
                rows.append(check(checker, work, sides, label, expected, archive, paired=label == "paired",
                                  cache="clean" if label == "clean" else "repeat"))
            if case == "plain":
                jar = sides["new"][1][-1]
                shutil.copyfile(sides["old"][1][-1], jar)
                if original(*sides["new"], work) != "-1,65":
                    raise ValueError("equal replacement did not reach the original JVM")
                for label in ("equal-replacement", "equal-warm"):
                    rows.append(check(checker, work, sides, label, [65,65], archive))
                resource(jar, NAMES[case], b"C")
                if original(*sides["new"], work) != "-1,67":
                    raise ValueError("changed same-path provider not observed")
                rows.append(check(checker, work, sides, "changed-replacement", [65,67], archive))
                if rows[-1]["rawVerdict"] != "violation" or rows[-1]["reuse"] or (rows[-2]["reuse"] or {}).get("kind") != "exact":
                    raise ValueError("resource-dependent proof cache reused the wrong input")
            if case != "dom4j":
                wanted = "verified" if expected[0] == expected[1] else "violation"
                if any(r["rawVerdict"] != wanted for r in rows[:3]):
                    raise ValueError(f"{case}: ordinary original-scope checks did not reach {wanted}: {rows[0]['firstProblem']}")
        save(out / "summary.json", {"job": os.environ.get("VERIFY_JOB_ID"), "source": os.environ.get("VERIFY_SOURCE_COMMIT"),
                                    "checkerSha256": digest(checker), "scopeSha256": digest(registry), "rows": rows,
                                    "archiveSha256": digest(out / "executions.zip")})
        print(case, [(r["name"],r["rawVerdict"]) for r in rows], flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("cases", nargs="+", choices=NAMES)
    p.add_argument("--register", action="store_true")
    p.add_argument("--profiles", nargs="+", choices=("old", "new"))
    args = p.parse_args()
    for case in args.cases:
        run(case, args.register, args.profiles)
