"""Measure identical generated resource questions on strict native, staged JBMC and stock JBMC."""
import argparse
import json
import os
from pathlib import Path
import subprocess

from resource_transfer import OUT, manifests
from scaffold_first import DEST, JDK, compile_java, digest, javaenv, read, scratch
from history import JBMC, MODELS, ROOT
from release_cases import Claim, Subject, measure_subject
from stock_history import classpath


def predicate(case, side):
    methods, counts = [], {}
    for row in read(case / "workflows.json")["workflows"]:
        name = row["id"]
        scope = read(case / row["scope"])
        changed = {c["input"]: c["expectedNew"]["return"] for c in row["intent"].get("allowedChanges", [])} if isinstance(row["intent"], dict) else {}
        variants = []
        for i, c in enumerate(scope["cases"]):
            expect = c["expected"]["return"]
            if side == "new":
                expect = changed.get(i, expect)
            args = ", ".join(json.dumps(a) for a in c["args"])
            variants.append(f"case {i}: return {json.dumps(expect)}.equals(UpgradeProbe.observe(new String[]{{{args}}}));")
        counts[name] = len(variants)
        methods.append(f"public static boolean {name}(int n) throws Exception {{ switch (n) {{\n" +
                       "\n".join(variants) + "\ndefault: return true; } }")
    methods.append(f"public static boolean inverse(int n) throws Exception {{return n < 0 || n >= {counts['primary']} || !primary(n);}}")
    methods.append("""public static void main(String[] args) throws Exception {
        int n = Integer.parseInt(args[1]);
        boolean answer = args[0].equals("primary") ? primary(n) : args[0].equals("control") ? control(n) : inverse(n);
        System.out.println("ORIGINAL " + answer);
    }""")
    return "public class ResourcePredicate {\n" + "\n".join(methods) + "\n}\n", counts


def run(slot, side):
    registered = OUT / slot
    row, = read(registered / "discovery.json")["candidates"]
    case = registered / row["directory"]
    reg = read(case / "registration.json")
    probe = case / "UpgradeProbe.java"
    if read(case / "scaffold.json")["stage"] != "original JVM controls passed" or digest(probe) != reg["probeSha256"]:
        raise ValueError("unqualified generated caller")
    with scratch(prefix="resource-profiles-") as tmp:
        work = Path(tmp)
        manifests(slot, work, neutral=False)
        deploy = read(work / (side + ".json"))
        jars = [Path(r["file"]) for r in deploy["classpath"]]
        source = work / "ResourcePredicate.java"
        body, counts = predicate(case, side)
        source.write_text(body)
        classes = work / "classes"
        env = javaenv()
        compile_java([probe, source], classes, jars, env)
        cp = [classes, *jars]
        claims = []
        observations = []
        for name, count in [*counts.items(), ("inverse", counts["primary"])]:
            truth = name != "inverse"
            seeds = tuple((str(i),) for i in range(count))
            claims.append(Claim(name, "int n", holds=seeds if truth else (), fails=() if truth else seeds))
            for (seed,) in seeds:
                cmd = [JDK / "bin/java", "-Xmx256m", "-XX:-UsePerfData", "-ea", "-cp", classpath(cp),
                       "ResourcePredicate", name, seed]
                lines = subprocess.check_output(cmd, cwd=work, env=env, text=True, timeout=30).splitlines()
                if lines != ["ORIGINAL " + str(truth).lower()]:
                    raise ValueError("independent original JVM predicate differed")
                observations.append([name, int(seed), truth])
        subject = Subject(0, "ResourcePredicate", "one original distribution", tuple(claims), bound=16, unwind=16)
        checker = Path(os.environ.get("JVMCONTRACT", ROOT / "lib/target/release/jvmcontract"))
        record = {"rows": [], "jvm": {"stdout": f"{len(observations)} fresh original JVM predicates matched", "rows": observations},
                  "probeSha256": digest(probe), "predicateSource": body, "registered": digest(case / "registration.json"),
                  "inputs": deploy["classpath"], "jdkModulesSha256": digest(JDK / "lib/modules"),
                  "checkerSha256": digest(checker), "jbmcSha256": digest(JBMC), "modelsSha256": digest(MODELS),
                  "job": os.environ.get("VERIFY_JOB_ID"), "source": os.environ.get("VERIFY_SOURCE_COMMIT")}
        measure_subject(slot, subject, "generated resources", work, env, cp, record, DEST / "resource-comparators" / slot / side, False)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("slot")
    p.add_argument("side", choices=("old", "new"))
    args = p.parse_args()
    run(args.slot, args.side)
