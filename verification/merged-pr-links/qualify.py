"""Cross-check finite public histories at original JVM method entries."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "examples/tools"))
from targets import public_comparison, upgrade_replay


ENTRIES = {
    "409": ("M07-jackson-dataformats-text", "csv/src/main/java",
            "tools.jackson.dataformat.csv.CsvParser#nextToken()Ltools/jackson/core/JsonToken;"),
    "411": ("M09-avro", "lang/java/idl/src/main/java",
            "org.apache.avro.idl.IdlUtils#writeIdlSchema(Ljava/io/Writer;Lorg/apache/avro/Schema;)V"),
    "412": ("M10-ical4j", "src/main/java",
            "net.fortuna.ical4j.model.ComponentGroup#calculateRecurrenceSet(Lnet/fortuna/ical4j/model/Period;)Ljava/util/List;"),
    "419": ("M17-jOOL", {"jool": "jOOL/src/main/java", "jool-java-8": "jOOL-java-8/src/main/java"}, "org.jooq.lambda.WindowImpl#lastValue()Ljava/util/Optional;"),
    "425": ("L03-picocli", "src/main/java",
            "picocli.CommandLine$Model$CommandSpec#aliases([Ljava/lang/String;)Lpicocli/CommandLine$Model$CommandSpec;"),
    "429": ("L07-jgrapht", "jgrapht-core/src/main/java",
            "org.jgrapht.alg.shortestpath.BaseKDisjointShortestPathsAlgorithm#getPaths(Ljava/lang/Object;Ljava/lang/Object;I)Ljava/util/List;"),
    "430": ("L08-commons-statistics", "commons-statistics-distribution/src/main/java",
            "org.apache.commons.statistics.distribution.CauchyDistribution#inverseCumulativeProbability(D)D"),
    "431": ("L09-rdf4j", "core/queryalgebra/evaluation/src/main/java",
            "org.eclipse.rdf4j.query.algebra.evaluation.iterator.GroupIterator#buildEntries()Ljava/util/Collection;"),
    "432": ("L10-calcite", "core/src/main/java",
            "org.apache.calcite.rel.rules.ProjectSetOpTransposeRule#onMatch(Lorg/apache/calcite/plan/RelOptRuleCall;)V"),
    "436": ("L14-iceberg", "core/src/main/java",
            "org.apache.iceberg.data.GenericRecord#<init>(Lorg/apache/iceberg/data/GenericRecord;)V"),
    "438": ("L16-guava", {"jre": "guava/src", "android": "android/guava/src"},
            "com.google.common.util.concurrent.AggregateFuture#init()V"),
    "440": ("L18-RxJava", "src/main/java",
            "io.reactivex.rxjava3.internal.operators.flowable.FlowableGroupBy$State#cancel()V"),
    "442": ("L20-JSqlParser", "src/main/java",
            "net.sf.jsqlparser.util.deparser.AlterDeParser#deParseAction(Lnet/sf/jsqlparser/statement/alter/AlterExpression;)V"),
    "443": ("M01-RoaringBitmap", "roaringbitmap/src/main/java",
            "org.roaringbitmap.buffer.ImmutableRoaringBitmap#contains(JJ)Z"),
    "444": ("M02-jackson-databind", "src/main/java",
            "tools.jackson.databind.deser.bean.BeanDeserializerBase#collectAllPropertyNamesTo(Ljava/util/Set;)V"),
    "445": ("M03-vavr", "vavr/src/main/java",
            "io.vavr.collection.Iterator#findLast(Ljava/util/function/Predicate;)Lio/vavr/control/Option;"),
    "446": ("M04-commons-compress", "src/main/java",
            "org.apache.commons.compress.archivers.zip.ZipFile#positionAtCentralDirectory32()V"),
    "447": ("M05-commons-rng", "commons-rng-core/src/main/java",
            "org.apache.commons.rng.core.source32.JDKRandom#setStateInternal([B)V"),
    "448": ("M06-agrona", "agrona/src/main/java",
            "org.agrona.collections.Int2IntHashMap$EntryIterator#next()Ljava/util/Map$Entry;"),
    "449": ("M07-spatial4j", "src/main/java",
            "org.locationtech.spatial4j.io.jackson.GeometryAsGeoJSONSerializer#serialize"
            "(Lorg/locationtech/jts/geom/Geometry;Lcom/fasterxml/jackson/core/JsonGenerator;"
            "Lcom/fasterxml/jackson/databind/SerializerProvider;)V"),
    "451": ("M09-libgdx", "gdx/src",
            "com.badlogic.gdx.math.Intersector#intersectPolygons"
            "(Lcom/badlogic/gdx/math/Polygon;Lcom/badlogic/gdx/math/Polygon;Lcom/badlogic/gdx/math/Polygon;)Z"),
    "452": ("M10-tinkerpop", "gremlin-core/src/main/java",
            "org.apache.tinkerpop.gremlin.process.traversal.step.filter.DedupGlobalStep#modulateBy"
            "(Lorg/apache/tinkerpop/gremlin/process/traversal/Traversal$Admin;)V"),
    "453": ("N01-commons-cli", "src/main/java", "org.apache.commons.cli.DefaultParser#handleProperties(Ljava/util/Properties;)V"),
    "454": ("N02-HdrHistogram", "src/main/java", "org.HdrHistogram.AbstractHistogram#equals(Ljava/lang/Object;)Z"),
    "455": ("N03-threeten-extra", "src/main/java",
            "org.threeten.extra.chrono.BritishCutoverDate#until(Ljava/time/chrono/ChronoLocalDate;)Ljava/time/chrono/ChronoPeriod;"),
    "456": ("N04-geometry-api-java", "src/main/java", "com.esri.core.geometry.TopologicalOperations#restorePolylineParts_(IIIII)V"),
    "466": ("O09", "spring-web/src/main/java", "org.springframework.http.codec.ServerSentEventHttpMessageReader"
            "#buildEvent(Ljava/util/List;Lorg/springframework/core/ResolvableType;ZLjava/util/Map;)Ljava/lang/Object;"),
    "475": ("O18", "spring-jms/src/main/java", "org.springframework.jms.connection.SingleConnectionFactory#initConnection()V"),
    "484": ("P07", "spring-context-support/src/main/java",
            "org.springframework.mail.SimpleMailMessage#copyTo(Lorg/springframework/mail/MailMessage;)V"),
    "497": ("P20", "spring-r2dbc/src/main/java",
            "org.springframework.r2dbc.connection.R2dbcTransactionManager#doCleanupAfterCompletion"
            "(Lorg/springframework/transaction/reactive/TransactionSynchronizationManager;Ljava/lang/Object;)Lreactor/core/publisher/Mono;"),
    "513": ("Q06", "spring-core/src/main/java", "org.springframework.util.CompositeCollection#remove(Ljava/lang/Object;)Z"),
    "520": ("Q13", "spring-jdbc/src/main/java", "org.springframework.jdbc.core.JdbcTemplate#queryForStream"
            "(Ljava/lang/String;Lorg/springframework/jdbc/core/RowMapper;)Ljava/util/stream/Stream;"),
    "535": ("Q28", "spring-aop/src/main/java", "org.springframework.aop.retry.AbstractRetryInterceptor$ReactorDelegate#adaptReactiveResult"
            "(Ljava/lang/Object;Lorg/springframework/core/ReactiveAdapter;Lorg/springframework/aop/retry/MethodRetrySpec;"
            "Ljava/lang/reflect/Method;)Ljava/lang/Object;"),
    "549": ("R12-commons-io", "src/main/java", "org.apache.commons.io.input.BoundedReader#skip(J)J"),
    "581": ("R44-RxJava", "src/main/java",
            "io.reactivex.rxjava3.internal.operators.observable.ObservableGroupBy$GroupByObserver#onNext(Ljava/lang/Object;)V"),
    "582": ("R45-resilience4j", "resilience4j-retry/src/main/java",
            "io.github.resilience4j.retry.internal.RetryImpl$AsyncContextImpl#onResult(Ljava/lang/Object;)J"),
    "585": ("R48-assertj", "assertj-core/src/main/java",
            "org.assertj.core.util.introspection.Introspection#findGetter(Ljava/lang/String;Ljava/lang/Object;)Ljava/lang/reflect/Method;"),
}


def write(path, obj):
    data = json.dumps(obj, indent=2) + "\n"
    if path.suffix == ".gz":
        path.write_bytes(gzip.compress(data.encode(), mtime=0))
    else:
        path.write_text(data)


VIA = "PublicCaller#observe([Ljava/lang/String;)Ljava/lang/String;"


def registered_fixtures(physical):
    """Describe the source and the files each fresh JVM receives under its fixtures directory."""
    inputs = physical["inputs"]
    caller = {"kind": "java", "class": "PublicCaller", "file": "PublicCaller.java",
              "sha256": inputs["caller/PublicCaller.java"]}
    resources = [{"kind": "resource", "file": path.removeprefix("fixtures/"), "sha256": inputs[path]}
                 for path in sorted(inputs) if path.startswith("fixtures/")]
    return [caller, *resources]


def check_receipt(entry, questions, pins, runtime, variant, physical, report):
    """Bind a saved debugger report to the entire requested domain and the measured caller."""
    recorded = physical["deployments"][variant]
    deployment = runtime["deployments"][variant]
    outcomes = {(r["side"], r["id"]): r["outcome"] for r in recorded["observations"]}
    cases = [{"args": q["args"], "expected": outcomes["parent", q["id"]]} for q in questions]
    if report["cases"] != cases or report["entry"] != entry or report.get("originalInvocation") != entry:
        raise ValueError(f"{variant}: different method, question arguments or parent observations")
    sources = {"probeSha256": Path(__file__).with_name("UpgradeProbe.java"), "launcherSha256": upgrade_replay.LAUNCHER,
               "tracerSha256": upgrade_replay.TRACER, "lookupSha256": upgrade_replay.LOOKUP}
    current = {key: upgrade_replay.sha(path) for key, path in sources.items()}
    # Receipts made before ordered entry discovery identify this exact pair of observers (d3ff87053d).
    historical = {**current, "tracerSha256": "60580c7a8f6cce3e4254e2855016ef92a64812888f34aa9958b5be1c7a5e0f50",
                  "lookupSha256": "6fe4c785f389c1f41849617ea9e68e702dad3aaebd93f157e0b67d06c8d68b08"}
    if {key: report[key] for key in sources} not in (current, historical):
        raise ValueError(f"{variant}: changed debugger or launcher")
    if report["originalFixtures"] != registered_fixtures(physical):
        raise ValueError(f"{variant}: different public caller source or fixture")
    if any(report["probeClasses"].get(name.removesuffix(".class")) != digest
           for name, digest in recorded["callerClasses"].items()):
        raise ValueError(f"{variant}: debugger and physical caller bytecode differ")
    caller = report["observerInvocation"]
    if report["invocationVia"] != VIA or caller["declaration"] != VIA or not caller["codeIndices"]:
        raise ValueError(f"{variant}: different public observer")
    differences = [i for i, q in enumerate(questions) if outcomes["parent", q["id"]] != outcomes["fix", q["id"]]]
    decision = "changed" if differences else "preserved"
    if report["status"] != decision or report["differences"] != differences or report["oldOracleDisagreements"]:
        raise ValueError(f"{variant}: debugger verdict disagrees with public observations")
    for side, label in (("parent", "old"), ("fix", "new")):
        measured = report["sides"][label]
        classpath = [runtime["sha256"][f] for f in deployment["classpath"][side]]
        if (measured["commit"] != pins[side] or measured["classpath"] != classpath
                or measured["dependency"] != classpath[0] or entry.split("#")[0] not in measured["loadedDependencyClasses"]):
            raise ValueError(f"{variant} {side}: different revision, classpath or loaded class")
        for index, (q, trial) in enumerate(zip(questions, measured["trials"], strict=True)):
            calls = trial["entryInvocations"]
            if (trial["input"] != index or trial["qualifiedMethodEntries"] != 2 or trial["loadedUpgradeOnEachReplay"] is not True
                    or trial["observations"] != [outcomes[side, q["id"]]] * 2 or len(calls) != 2
                    or any(c["dispatchedTo"] != VIA or c["observerCodeIndex"] not in caller["codeIndices"] for c in calls)):
                raise ValueError(f"{variant} {side}: entry, call site or return differs for {q['id']}")


def qualify(number, output, only=None, check_only=False, compressed=False):
    folder, = (ROOT / "examples").glob(number + "-*")
    spec = public_comparison.read(folder / "comparison.json")
    runtime = public_comparison.read(folder / "runtime.json")
    physical = public_comparison.read(folder / "observations.json")
    source = folder / "caller/PublicCaller.java"
    resources = sorted(p for p in (folder / "fixtures").rglob("*") if p.is_file())
    if (physical["inputs"] != {p.relative_to(folder).as_posix(): upgrade_replay.sha(p) for p in [source, *resources]}
            or physical["runtimeSha256"] != upgrade_replay.sha(folder / "runtime.json")
            or physical["comparisonSha256"] != upgrade_replay.sha(folder / "comparison.json")):
        raise ValueError("physical receipt differs from the registered caller or deployment")
    cache = Path(os.environ.get("PUBLIC_COMPARISON_CACHE", Path.home() / ".cache/in-the-loop" / runtime["cache"]))
    jdk = Path(os.environ.get("PUBLIC_COMPARISON_JDK", Path.home() / ".sdkman/candidates/java" / runtime["jdk"]))
    if not check_only and upgrade_replay.sha(jdk / "release") != runtime["jdkReleaseSha256"]:
        raise ValueError("registered JVM differs")
    project, roots, entry = ENTRIES[number]
    roles = (only,) if isinstance(only, str) else (only or ("Control", "Challenge"))
    if not check_only:
        output.mkdir(parents=True, exist_ok=True)
    for variant, deployment in runtime["deployments"].items():
        measured = {(r["side"], r["id"]): r["outcome"] for r in physical["deployments"][variant]["observations"]}
        questions = [r for r in spec["questions"] if r["role"] in roles]
        if set(roles) != {q["role"] for q in questions} or any(q.get("omit") for q in questions):
            raise ValueError(f"{number}: qualification requires paired histories for every selected role")
        file = output / (number + "-" + variant + (".json.gz" if compressed else ".json"))
        if check_only:
            data = gzip.decompress(file.read_bytes()) if compressed else file.read_bytes()
            check_receipt(entry, questions, spec["revisions"], runtime, variant, physical, json.loads(data))
            print(number, variant, entry, len(questions) * 4, "verified saved JVM trials", flush=True)
            continue
        with tempfile.TemporaryDirectory(prefix="qualified-public-") as t:
            work = Path(t)
            manifests, deps = [], []
            for side in public_comparison.SIDES:
                pin = spec["revisions"][side]
                checkout = cache / "worktrees" / (project + "-" + side)
                source_path = roots[variant] if isinstance(roots, dict) else roots
                tree = subprocess.check_output(["git", "-C", checkout, "ls-tree", "-rz", pin, "--", source_path])
                owner = entry.split("#")[0].split("$")[0].replace(".", "/")
                original_source = (Path(source_path) / (owner + ".java")).as_posix().encode()
                if not any(row.endswith(b"\t" + original_source) for row in tree.split(b"\0")):
                    raise ValueError(f"{number} {variant}: missing source for {entry} at {pin}")
                cp = [{"file": str(cache / name), "sha256": runtime["sha256"][name]}
                      for name in deployment["classpath"][side]]
                manifest = work / (side + ".json")
                write(manifest, {"commit": pin, "sourceSha256": hashlib.sha256(tree).hexdigest(), "classpath": cp})
                manifests.append(manifest)
                deps.append(cp[0]["sha256"])
            fixture_dir = source.parent
            if resources:
                fixture_dir = work / "inputs"
                shutil.copytree(folder / "fixtures", fixture_dir)
                if (fixture_dir / source.name).exists():
                    raise ValueError("resource path collides with the registered caller")
                shutil.copyfile(source, fixture_dir / source.name)
            scope = {"entry": entry, "probeClass": "UpgradeProbe",
                     "invocationVia": VIA,
                     "observer": "Same public observer as the physical receipt, with an original-method breakpoint.",
                     "basis": "Cross-check the previously measured typed returns on both revisions against two independent debugger trials.",
                     "fixtures": registered_fixtures(physical),
                     "cases": [{"args": r["args"], "expected": measured["parent", r["id"]]} for r in questions]}
            scope_path = work / "scope.json"
            write(scope_path, scope)
            report = upgrade_replay.evaluate(scope_path, *manifests, Path(__file__).with_name("UpgradeProbe.java"),
                    jdk, deps, 180, fixtures=fixture_dir, application_change=True)
            write(file, report)
            if report["status"] not in ("preserved", "changed"):
                raise ValueError(f"{number} {variant}: {report.get('reason', 'qualified replay open')}")
            check_receipt(entry, questions, spec["revisions"], runtime, variant, physical, report)
            print(number, variant, entry, len(questions) * 4, "qualified JVM trials", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("examples", nargs="+", choices=ENTRIES)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--check", action="store_true", help="audit saved trials offline without launching a JVM")
    parser.add_argument("--gzip", action="store_true", help="store or check complete reports compressed as .json.gz")
    parser.add_argument("--only", action="append", choices=("Intent", "Control", "Challenge"),
                        help="include this role (repeatable; defaults to Control and Challenge)")
    args = parser.parse_args()
    for example in args.examples:
        qualify(example, args.output, args.only, args.check, args.gzip)
