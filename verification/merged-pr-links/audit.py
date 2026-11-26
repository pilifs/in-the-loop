"""Check coverage of the merged-PR brief, source pins, input digests and every finite JVM prediction."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "examples/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from targets import public_comparison as comparison
from qualify import ENTRIES, check_receipt


def require(condition, message):
    if not condition:
        raise ValueError(message)


def spring_builds(setup, campaign, prefix):
    """The 6.x rows give jar names once, then give parent digests in the same order."""
    table = setup.split("## Digests of the built artifacts\n", 1)[1].split("\n## ", 1)[0]
    names = {}
    builds = {}
    for case, side, jars in re.findall(rf"^\| ({prefix}\d\d) \| (fix|parent) \| (.*?) \|", table, re.M):
        listed = re.findall(r"`([^`]+\.jar)`", jars)
        if listed:
            names[case] = listed
        for jar, digest in zip(names[case], re.findall(r"`([0-9a-f]{64})`", jars), strict=True):
            builds[f"artifacts/{case}-{side}/jars/{jar}"] = digest
    companions = Path(__file__).with_name(campaign) / "project-jars.sha256"
    for line in companions.read_text().splitlines():
        digest, name = line.split()
        require(re.fullmatch(rf"artifacts/{prefix}\d\d-(parent|fix)/tree/.+\.jar", name) and name not in builds,
                "invalid Spring companion build record")
        builds[name] = digest
    return builds


def check_prepared_spring_pair(number, deployment, recorded, setup, series="P"):
    case = f"{series}{number:02}"
    if case == "P04":
        classes = recorded["callerClassesBySide"]
        require(deployment.get("compilePerSide") and classes["fix"] == recorded["callerClasses"] and
                classes["parent"]["PublicCaller.class"] == classes["fix"]["PublicCaller.class"] and
                classes["parent"]["Flatten.class"] != classes["fix"]["Flatten.class"],
                "P04 needs the same caller with separately compiled YAML adapters")
    if case == "P16":
        descriptor = "(Ljava/io/LineNumberReader;Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;"
        sites = recorded["callerInvocations"]
        require(deployment.get("compileAgainst") == "parent" and not deployment.get("compilePerSide")
                and sites["parent"] == sites["fix"] and
                [(s["method"], s["descriptor"]) for s in sites["parent"]] == [("readScript", descriptor)],
                "P16 needs the parent-compiled three-argument readScript call")
    if "upstreamTestInputs" in deployment:
        require(deployment["upstreamTestInputs"]["tree"] == f"worktrees/{case}-fix",
                f"{case}: wrong original test fixture tree")
    if case == "Q05":
        classes = recorded["callerClassesBySide"]
        require(deployment.get("kotlinCompiler") and classes["fix"] == recorded["callerClasses"]
                and classes["parent"]["PublicCaller.class"] == classes["fix"]["PublicCaller.class"]
                and classes["parent"]["KotlinCallsKt.class"] != classes["fix"]["KotlinCallsKt.class"],
                "Q05 needs Kotlin calls inlined from each revision with the same Java caller")
    if case == "Q11":
        image = deployment.get("postgresImage", "")
        require(deployment.get("service") == "postgres" and re.fullmatch(r"postgres@sha256:[0-9a-f]{64}", image)
                and image.split(":")[-1][:12] in setup and recorded.get("postgresVersionNumber") == 170012,
                "Q11 requires the setup's PostgreSQL 17 instance")
    slices = (5, 9, 11, 16, 18, 19, 23) if series == "P" else (4, 10, 17, 18, 19, 20, 25, 26)
    if number not in slices:
        require(not deployment.get("preparedSlice") and "preparedSliceClasses" not in recorded,
                f"{case}: expected the complete module builds")
        return
    cp = deployment["classpath"]
    require(deployment.get("preparedSlice") and cp["parent"][1:] == cp["fix"][1:],
            f"{case}: original classes need identical released companions")
    for side in comparison.SIDES:
        label = f"{case}-{side}"
        require(cp[side][0] == f"slices/{label}/{label}-slice.jar" and 0 in deployment["providers"].values(),
                f"{label}: source slice must supply a loaded class")
    if series == "Q":
        # The setup prints the top-level class rows. Its independent build also
        # writes every nested class digest to the per-pin main.SHA256SUMS.
        inventory = comparison.read(Path(__file__).with_name("q01-q30") / "slice-classes.json")
        expected = {side: inventory[cp[side][0]] for side in comparison.SIDES}
        require(recorded["preparedSliceClasses"] == expected and expected["parent"] != expected["fix"],
                f"{case}: compiled slice differs from setup's class inventory")
        rows = re.findall(rf"^\| {case} \| `([\w$]+\.class)` \| (.*?) \| (.*?) \|$", setup, re.M)
        require(rows, f"{case}: missing independent class digests")
        for name, parent, fix in rows:
            for side, value in (("parent", parent), ("fix", parent if fix == "the same" else fix)):
                matches = [d for member, d in expected[side].items() if Path(member).name == name]
                require(matches == ([] if value == "absent" else [value.strip("`")]),
                        f"{case} {side}: {name} differs from the upstream build table")
        return
    expected = {side: {} for side in comparison.SIDES}
    table = setup.split("**Slice class digests (sha256).**", 1)[1].split("**What the slice route", 1)[0]
    for member, parent, fix in re.findall(rf"^\| {case} \| `([^`]+)` \| `([0-9a-f]{{64}})` \| (.*?) \|$", table, re.M):
        if member.startswith("…/"):
            member = package + member[1:]
        else:
            package = member.rsplit("/", 1)[0]
        expected["parent"][member] = parent
        expected["fix"][member] = parent if fix == "the same" else re.search(r"`([0-9a-f]{64})`", fix)[1]
    require(expected["parent"] and expected["parent"] != expected["fix"] and
            recorded["preparedSliceClasses"] == expected, f"{case}: bytecode differs from upstream setup")


def check_spring_deployment(number, deployment, recorded, setup):
    if number == 3:
        callers = recorded["callerClassesBySide"]
        require(deployment.get("compilePerSide") and callers["fix"] == recorded["callerClasses"]
                and callers["fix"]["PublicCaller.class"] != callers["parent"]["PublicCaller.class"],
                "O03 requires separate compilations of the common source")
        scalar = "(Ljava/lang/String;[Lorg/hamcrest/Matcher;)Lorg/springframework/test/web/client/RequestMatcher;"
        for side in comparison.SIDES:
            sites = recorded["callerInvocations"][side]
            for caller in ("inferred", "observe"):
                expected = scalar.replace("[Lorg/hamcrest", "Lorg/hamcrest") if (caller, side) == ("inferred", "parent") else scalar
                require([(s["method"], s["descriptor"]) for s in sites if s["caller"] == caller]
                        == [("header", expected), ("queryParam", expected)], "O03 matcher call descriptors differ")
    if number not in (11, 14):
        require("sourceSlice" not in deployment, "expected a complete Spring module build")
        return
    source = deployment["sourceSlice"]
    cls = ("org.springframework.jdbc.core.namedparam.NamedParameterUtils" if number == 11 else
           "org.springframework.transaction.reactive.TransactionalOperatorImpl")
    require(source["class"] == cls and source["path"].endswith("/src/main/java/" + cls.replace(".", "/") + ".java"),
            "wrong original Spring source slice")
    require(deployment["classpath"]["parent"] == deployment["classpath"]["fix"], "source slices need common companions")
    member = cls.replace(".", "/") + ".class"
    for side in comparison.SIDES:
        match = re.search(rf"^\| O{number:02} {side} \| [^|]+ \| `([0-9a-f]{{40}})`", setup, re.M)
        require(match and source["blobs"][side] == match[1] and source["worktrees"][side] == f"worktrees/O{number:02}-{side}",
                "source slice differs from the setup's original git blob")
        require(re.fullmatch("[0-9a-f]{64}", recorded["sourceSliceClasses"][side][member]), "missing original slice class")
    require(recorded["sourceSliceClasses"]["parent"][member] != recorded["sourceSliceClasses"]["fix"][member],
            "both source slices supplied the same changed class")
    if number == 11:
        require(deployment.get("service") == "postgres" and deployment["postgresImage"] in setup
                and recorded.get("postgresVersionNumber") == 170012, "O11 requires the registered PostgreSQL server")


def check_r_build(number, name, deployment, runtime, recorded, classes, section, replay):
    """Tie a deployment to the setup JAR or the original class table where it lists only classes."""
    label = f"R{number:02}"
    overlay = number in (39, 42)
    require(bool(deployment.get("preparedSlice")) == overlay, f"{label}: wrong build type")
    cache = Path(os.environ.get("PUBLIC_COMPARISON_CACHE", Path.home() / ".cache/in-the-loop" / runtime["cache"]))
    cp = deployment["classpath"]
    require(0 in deployment["providers"].values(), f"{label}: missing original provider")
    if overlay:
        require(cp["parent"][1:] == cp["fix"][1:], f"{label}: different overlay companions")
        base, provider = (("m2/org/apache/parquet/parquet-hadoop/1.18.2/parquet-hadoop-1.18.2.jar",
                           "org.apache.parquet.hadoop.ParquetFileReader") if number == 39 else
                          ("m2/io/projectreactor/reactor-core/3.1.1.RELEASE/reactor-core-3.1.1.RELEASE.jar",
                           "reactor.core.publisher.Flux"))
        require(cp["fix"][1] == base and deployment["providers"].get(provider) == 1,
                f"{label}: the released base must supply its original public entry")
    for side, paths in cp.items():
        first = paths[0]
        expected_dir = f"artifacts/{label}-{side}" + ("-android" if name == "android" else "")
        if number == 42:
            require(first == f"slices/R42-slice-{side}/slice.jar", f"{label}: wrong Reactor slice")
        else:
            require(str(Path(first).parent) == expected_dir, f"{label}: wrong original JAR")
        members = classes.get(first, {})
        named_jar = runtime["sha256"][first] in section
        require(named_jar or (members and all(d in section for d in members.values())),
                f"{label}: no original build digest in the setup record")
        if overlay:
            require(members and recorded["preparedSliceClasses"][side] == members,
                    f"{label}: different original overlay classes")
        if replay and members:
            with zipfile.ZipFile(cache / first) as archive:
                for member, digest in members.items():
                    require(hashlib.sha256(archive.read(member)).hexdigest() == digest,
                            f"{label}: {member} differs from the original build")


def audit(replay=False, campaign="original"):
    series = {"original": ("organic-java-merged-pr-links-brief", "M", None),
              "l01-l20": ("organic-java-merged-pr-links-l01-l20-brief", "L", 20),
              "m01-m10": ("organic-java-merged-pr-links-m01-m10-brief", "M", 10),
              "n01-n05": ("organic-java-merged-pr-links-n01-n05-brief", "N", 5),
              "o01-o20": ("spring-framework-pr-links-o01-o20-brief", "O", 20),
              "p01-p30": ("spring-framework-pr-links-p01-p30-brief", "P", 30),
              "q01-q30": ("spring-framework-pr-links-q01-q30-brief", "Q", 30),
              "r01-r50": ("organic-java-merged-pr-links-r01-r50-brief", "R", 50)}
    brief_name, case_prefix, case_count = series[campaign]
    brief = ROOT / "llm-dlc/loops" / (brief_name + ".md")
    setup = brief.with_name(brief.stem + "-setup.md").read_text()
    # N01–N05's build record puts every module in one table, including the nested Spring JARs.
    build_table = {f"artifacts/{case}-{side}/{path}": digest for case, side, path, digest in re.findall(
        r"^\| (N\d\d) \| (parent|fix) \| `([^`]+)` \| `([0-9a-f]{64})` \|$", setup, re.MULTILINE)}
    spring_series = campaign in ("o01-o20", "p01-p30", "q01-q30")
    if spring_series:
        build_table = spring_builds(setup, campaign, case_prefix)
    r_series = campaign == "r01-r50"
    if r_series:
        classes = comparison.read(Path(__file__).with_name(campaign) / "build-classes.json")
    references = {}
    for section in brief.read_text().split("\n## "):
        link = re.search(r"https://github.com/([\w.-]+/[\w.-]+)/compare/([0-9a-f]{40})\.{3}([0-9a-f]{40})", section)
        if not link:
            continue
        repo, parent, fix = link.groups()
        questions = {}
        for line in section.splitlines():
            if line.startswith("| ") and " · " in line:
                label, history, prediction, basis, refutation = [s.strip() for s in line.strip("|").split(" | ")]
                question, role = label.split(" · ")
                require(question not in questions, f"duplicate brief question {question}")
                questions[question] = (role, history, prediction, basis)
                if case_count:
                    questions[question] += (refutation,)
        key = next(iter(questions)).rsplit(".", 1)[0]
        require(key not in references, f"duplicate case {key}")
        references[key] = ({"parent": parent, "fix": fix}, questions)
    if case_count:
        require(len(references) == case_count, f"expected all {case_count} comparisons in {campaign}")
        for case, (_, rows) in references.items():
            roles = ["Intent", "Control", "Challenge"]
            if campaign == "n01-n05" and case == "ThreeTen/threeten-extra#463":
                roles += ["Intent", "Intent"]
            if campaign == "o01-o20":
                pr = case.rsplit("#", 1)[1]
                if pr == "37218":
                    roles.append("Date validator")
                elif pr in ("37403", "37600"):
                    roles.insert(2, "Eviction" if pr == "37403" else "Put and eviction")
            if campaign == "p01-p30":
                pr = case.rsplit("#", 1)[1]
                if pr == "22260":
                    roles.insert(1, "Intent")
                elif pr in ("22392", "34723", "30020"):
                    roles.append({"22392": "Compatibility", "34723": "Challenge", "30020": "Configuration"}[pr])
            if campaign == "q01-q30" and case.endswith(("#37332", "#37465")):
                roles.append("Challenge" if case.endswith("#37332") else "Compatibility challenge")
            require([row[0] for row in rows.values()] == roles,
                    f"{case}: incomplete or reordered questions")
    fields = ("role", "history", "prediction", "basis")
    if case_count:
        fields += ("refutation",)
    folders = {}
    for folder in (ROOT / "examples").glob("[0-9][0-9][0-9]-*/comparison.json"):
        spec = comparison.read(folder)
        key = spec["questions"][0]["id"].rsplit(".", 1)[0]
        if key in references:
            require(key not in folders, f"duplicate example {key}")
            folders[key] = folder.parent
    require(set(references) == set(folders), f"uncovered cases {references.keys() - folders.keys()}")
    result = {"cases": [], "totals": {}}
    counters = Counter()
    for number, (case, (pins, questions)) in enumerate(references.items(), 1):
        folder = folders[case]
        prefix = f"{folder.name}: "
        plan = comparison.comparison_plan(folder)
        spec = comparison.read(folder / "comparison.json")
        runtime = comparison.read(folder / "runtime.json")
        recorded = comparison.read(folder / "observations.json")
        ex = comparison.read(folder / "example.json")
        repo, pr = case.split("#")
        require(spec["source"] == ex["source"]["url"] == f"https://github.com/{repo}/pull/{pr}", prefix + "source")
        require(plan["revisions"] == pins and plan["questions"] == list(questions), prefix + "pins or question order")
        require(recorded["schema"] == "public-observations/v1", prefix + "record format")
        for key, path in [("comparisonSha256", folder / "comparison.json"), ("runtimeSha256", folder / "runtime.json"),
                          ("launcherSha256", comparison.upgrade_replay.LAUNCHER)]:
            require(comparison.upgrade_replay.sha(path) == recorded[key], prefix + key)
        sources = sorted((folder / "caller").rglob("*.java")) + sorted((folder / "adapters").rglob("*.java"))
        sources += sorted((folder / "caller").rglob("*.kt"))
        fixtures = [p for p in (folder / "fixtures").rglob("*") if p.is_file()]
        require(recorded["inputs"] == {p.relative_to(folder).as_posix(): comparison.upgrade_replay.sha(p)
                                       for p in sources + fixtures}, prefix + "caller or fixtures")
        require(runtime["deployments"].keys() == recorded["deployments"].keys(), prefix + "deployment names")
        evidence = {q: {} for q in questions}
        used_files = set()
        setup_section = (setup if spring_series else
                         setup.split(f"\n### {case_prefix}{number:02} · ", 1)[1].split("\n### " + case_prefix, 1)[0])
        supplied = {}
        inventory = folder / "setup/artifacts.sha256"
        if inventory.is_file():
            supplied = dict(line.split(None, 1)[::-1] for line in inventory.read_text().splitlines() if line.strip())
        if r_series:
            variants = (["jre", "android"] if number in (5, 9) else
                        ["overlay"] if number in (39, 42) else ["pins"])
            require(list(runtime["deployments"]) == variants, prefix + "missing or unexpected deployment")
        for variant, deployment in runtime["deployments"].items():
            result_rows = recorded["deployments"][variant]
            if r_series:
                check_r_build(number, variant, deployment, runtime, result_rows, classes, setup_section, replay)
                counters["pinnedSourcePairs" if variant == "overlay" else "fullBuildPairs"] += 1
            if campaign == "o01-o20":
                check_spring_deployment(number, deployment, result_rows, setup)
                counters["pinnedSourcePairs" if "sourceSlice" in deployment else "fullBuildPairs"] += 1
            if campaign in ("p01-p30", "q01-q30"):
                check_prepared_spring_pair(number, deployment, result_rows, setup, case_prefix)
                counters["pinnedSourcePairs" if deployment.get("preparedSlice") else "fullBuildPairs"] += 1
            if campaign == "n01-n05" and case == "spring-projects/spring-framework#37322":
                require(deployment.get("service") == "mysql" and
                        re.fullmatch(r"mysql@sha256:[0-9a-f]{64}", deployment.get("mysqlImage", "")) and
                        deployment["mysqlImage"] in setup_section and result_rows.get("mysqlVersion") == "9.1.0",
                        prefix + "durable histories require the registered MySQL deployment")
            require("PublicCaller.class" in result_rows["callerClasses"], prefix + "compiled caller absent")
            for side, files in deployment["classpath"].items():
                used_files.update(files)
                require(len(files) == len(set(files)), prefix + "duplicate classpath entry")
                for f in files:
                    digest = runtime["sha256"][f]
                    require(re.fullmatch("[0-9a-f]{64}", digest), prefix + "artifact digest")
                    if r_series and f.startswith("artifacts/snapshots-B/"):
                        require(number in (28, 29, 30) and digest in setup and Path(f).stem.split("-")[-2] in setup,
                                prefix + "different dated Jackson dependency")
                    elif f.startswith("artifacts/"):
                        if case_count:
                            label = re.match(rf"artifacts/{case_prefix}{number:02}[-/].*?\b(parent|fix)\b", f)
                            require(label and label[1] == side, prefix + f"{f} belongs to a different revision")
                        if r_series:
                            require(supplied.get(f) == digest, prefix + f"{side} {f} differs from its setup inventory")
                        elif spring_series or campaign == "n01-n05":
                            require(build_table.get(f) == digest, prefix + f"{side} {f} differs from pin-build table")
                        else:
                            require(digest in setup_section or supplied.get(f) == digest,
                                    prefix + f"{side} {f} absent from pin-build record")
                        if campaign == "m01-m10":
                            # Setup lists individual build JARs by name and reactor JARs in parent/fix columns.
                            row, = (line for line in setup_section.splitlines()
                                    if line.startswith(f"| `{Path(f).name}`"))
                            columns = re.findall(r"`([0-9a-f]{64})`", row)
                            require(len(columns) in (1, 2) and digest == columns[-1 if side == "fix" else 0],
                                    prefix + f"{side} digest for {f} differs from the setup inventory")
                indices = [*deployment["providers"].values(), *deployment.get("childProviders", {}).values()]
                require(all(type(i) is int and 0 <= i < len(files) for i in indices), prefix + "provider index")
                require(any(files[i].startswith("artifacts/") for i in indices) or
                        (campaign == "o01-o20" and number in (11, 14) and "sourceSlice" in deployment) or
                        (campaign in ("p01-p30", "q01-q30", "r01-r50") and deployment.get("preparedSlice")),
                        prefix + "no pin-built provider")
            expected_keys = [(s, q["id"]) for s in comparison.SIDES for q in spec["questions"]
                             if s not in q.get("omit", {})]
            require([(r["side"], r["id"]) for r in result_rows["observations"]] == expected_keys,
                    prefix + "missing, duplicated or extra observations")
            for q in spec["questions"]:
                key = q["id"]
                require(tuple(q[k] for k in fields) == questions[key], prefix + key + " differs from the brief")
                require("fix" in q["expected"], prefix + key + " has no merged prediction")
                by_side = {}
                for row in (r for r in result_rows["observations"] if r["id"] == key):
                    side, actual = row["side"], row["outcome"]
                    require(set(actual) in ({"throws"}, {"return"}), prefix + "ambiguous observation")
                    pred = q["expected"].get(side)
                    expected = ("observed only" if pred is None else
                                "matched" if comparison.agrees(pred, actual) else "refuted")
                    require(expected == row["prediction"], prefix + key + " decision disagrees with observation")
                    by_side[side] = {"prediction": expected, "outcome": actual}
                evidence[key][variant] = by_side
            counters["freshJvms"] += len(expected_keys)
            counters["deploymentPairs"] += 1
        require(used_files == runtime["sha256"].keys(), prefix + "unused or missing runtime digest")
        refuted = [key for key, variants in evidence.items()
                   if any(sides["fix"]["prediction"] == "refuted" for sides in variants.values())]
        paired = all(all("parent" in sides for sides in evidence[key].values()) for key in questions)
        intents = [key for key, desc in questions.items() if desc[0] == "Intent"]
        def different(key):
            return all("parent" in sides and sides["parent"]["outcome"] != sides["fix"]["outcome"]
                       for sides in evidence[key].values())
        controls = [key for key, desc in questions.items() if desc[0] == "Control"]
        def matched_on_fix(key):
            return all(sides["fix"]["prediction"] == "matched" for sides in evidence[key].values())
        unchanged = sum(all(set(sides) == set(comparison.SIDES) and
                            sides["parent"]["outcome"] == sides["fix"]["outcome"] and
                            all(r["prediction"] == "matched" for r in sides.values())
                            for sides in evidence[key].values()) for key in controls)
        counters.update(cases=1, questions=len(questions), fixedRefutations=len(refuted),
                        fixedPredictionsMatched=sum(map(matched_on_fix, questions)), fixedIntentsMatched=sum(map(matched_on_fix, intents)),
                        pairedIntentChanges=sum(map(different, intents)), unchangedControls=unchanged,
                        omittedParentHistories=sum("parent" in q.get("omit", {}) for q in spec["questions"]))
        result["cases"].append({"example": ex["id"], "case": case, "observationsSha256": comparison.upgrade_replay.sha(folder / "observations.json"),
                                "deployments": list(runtime["deployments"]), "allHistoriesPaired": paired, "fixedRefutations": refuted})
        if spring_series or campaign in ("m01-m10", "n01-n05", "r01-r50"):
            require(paired, prefix + "expected both original revisions for every history")
            for key, desc in questions.items():
                if desc[0] == "Control" or (desc[0] == "Intent" and not r_series):
                    require(all(sides["parent"]["prediction"] != "observed only" for sides in evidence[key].values()),
                            prefix + key + " missing parent prediction")
            parent_refuted = [key for key, variants in evidence.items()
                              if any(sides["parent"]["prediction"] == "refuted" for sides in variants.values())]
            result["cases"][-1]["parentRefutations"] = parent_refuted
            counters["parentRefutations"] += len(parent_refuted)
            counters["controlsMatchedOnBoth"] += sum(all(
                all(side["prediction"] == "matched" for side in sides.values()) for sides in evidence[key].values()
            ) for key in controls)
        if r_series:
            for q in spec["questions"]:
                counters["parentHistoriesWithoutPrediction"] += int("parent" not in q["expected"])
                competing = q.get("alternativeExpected", {}).get("fix")
                require(bool(competing) == (number in (12, 37) and q["role"] == "Challenge"),
                        prefix + "missing or unexpected competing prediction")
                if competing:
                    counters["competingPredictionsMatched"] += int(all(
                        comparison.agrees(competing, sides["fix"]["outcome"]) for sides in evidence[q["id"]].values()))
        if campaign == "n01-n05":
            for q in spec["questions"]:
                open_parent = q["id"] == "Esri/geometry-api-java#329.3"
                require(("parent" not in q["expected"]) == open_parent, prefix + q["id"] + " parent prediction")
                counters["parentHistoriesWithoutPrediction"] += int(open_parent)
        for receipt in sorted(Path(__file__).with_name("entry-receipts").glob(ex["id"] + "-*.json")):
            qualified = comparison.read(receipt)
            variant = receipt.stem.split("-", 1)[1]
            by_args = {tuple(q["args"]): q for q in spec["questions"]}
            args = [tuple(case["args"]) for case in qualified["cases"]]
            require(args and len(set(args)) == len(args) and set(args) <= by_args.keys(), prefix + "qualified inputs")
            check_receipt(ENTRIES[ex["id"]][2], [by_args[a] for a in args], pins, runtime, variant, recorded, qualified)
            counters["retainedMethodEntryTrials"] += 4 * len(args)
        if replay:
            comparison.replay(folder)
    result["totals"] = dict(counters)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", choices=("original", "l01-l20", "m01-m10", "n01-n05", "o01-o20", "p01-p30", "q01-q30", "r01-r50"), default="original")
    parser.add_argument("--replay", action="store_true", help="also rebuild every caller and repeat the physical trials")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.replay, args.campaign)
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["totals"], sort_keys=True))
