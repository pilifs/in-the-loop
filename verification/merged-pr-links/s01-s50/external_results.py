"""Score the independent consumer builds and native executions at the public observations in the brief."""
import hashlib
import json
from pathlib import Path
import zlib

HERE = Path(__file__).resolve().parent
LAYER_RECEIPT = "gradle/S47-isolated.json"


def read(name):
    return json.loads((HERE / name).read_text())


def side(outcome, expected=None):
    verdict = "observed only" if expected is None else ("matched" if outcome == expected else "refuted")
    return dict(outcome=outcome, verdict=verdict)


def metadata():
    data = read("gradle/S10.json")
    result = [{}, {}, {}]
    for name in ("parent","fix"):
        d = data[name]
        def values(stage, parsed):
            row = d[stage]
            if row["parsed"] != parsed:
                raise ValueError("different Gradle incremental source set")
            return [row["some"],row["more"]]
        clean, incremental = ["MoreProperties","SomeProperties"], ["MoreProperties"]
        if values("initial",clean) != ["Original description.","Before edit."]:
            raise ValueError("different original Gradle source comments")
        edited = ["Original description.","Edited description."]
        deleted = ["Original description.",None]
        result[0][name] = side(values("editedIncremental",incremental),edited if name == "fix" else [None,edited[1]])
        result[1][name] = side(values("editedClean",clean),edited)
        pair = [values("removedIncremental",incremental),values("removedClean",clean)]
        result[2][name] = side(pair,[deleted,deleted] if name == "fix" else None)
    return result


def layers():
    data = read(LAYER_RECEIPT)
    result = [{}, {}, {}]
    for name in ("parent","fix"):
        d = data[name]
        for i, role in enumerate(("intent","control","challenge")):
            items = ["org/example/Open","org/example/internal/Hidden"]
            expected = ["public","rest"] if role == "intent" and name == "fix" else ["rest","public"]
            if role == "challenge":
                items.append("other/Third")
                expected = ["public","rest","rest"] if name == "fix" else None
            if set(d[role]) != set(items):
                raise ValueError(f"{name} {role} has a different set of packaged fixture classes")
            result[i][name] = side([d[role][item] for item in items],expected)
    return result


def webflux():
    data = read("webflux-2017/reconstructed-observations.json")
    if data["historicalSnapshotIdentityEstablished"]:
        raise ValueError("the reconstructed Framework profile cannot identify the original snapshot binaries")
    result = [{}, {}, {}]
    for name in ("parent","fix"):
        rows = data["sides"][name]["observations"]
        result[0][name] = side(rows["intent"]["public"],"200:first_name=Ada/200:Lin" if name == "fix" else None)
        result[1][name] = side(rows["control"]["public"],"200:firstName=Ada")
        if name == "fix":
            result[2][name] = side(rows["challenge"]["public"],"Mia/Mia")
    return result


def maven_wars(revisions):
    """Check the Maven goal against the actual resources and physical input ordering."""
    files = {side: HERE / "maven-war" / (side + ".json") for side in revisions}
    if not any(path.exists() for path in files.values()):
        return None
    location = "WEB-INF/classes/META-INF/sbom/application.cdx.json"
    for side, path in files.items():
        data = json.loads(path.read_text())
        if data["revision"] != revisions[side] or data["mavenBuilds"] != 2:
            raise ValueError(f"{side} Maven revision or number of consumer builds differs")
        rows = data["observations"]
        if set(rows) != {"intent", "challenge"}:
            raise ValueError(f"{side} Maven WAR evidence is incomplete")
        for role, row in rows.items():
            if row["inputDecoyBeforeSbom"] != ("true" if role == "challenge" else "single"):
                raise ValueError(f"{side} {role} Maven did not receive the registered input ordering")
            expected = ("CycloneDX", location, '{"fixture":"original"}') if side == "fix" else ("null", "null", "absent")
            if (row["format"], row["location"], row["payload"]) != expected:
                raise ValueError(f"{side} {role} Maven manifest or selected WAR bytes differ")
    return {side: str(path.relative_to(HERE)) for side, path in files.items()}


def migrations():
    result = [{}, {}, {}]
    sql = (HERE / "native-flyway/V2__users.sql").read_bytes()
    crc = zlib.crc32(b"".join(sql.splitlines()))
    checksum = crc if crc < 2**31 else crc - 2**32
    applied = dict(runtime="native", version="2", checksum=checksum, row=73, applied=1)
    for name in ("parent","fix"):
        data = read(f"native-flyway/{name}.json")
        parsed = {}
        for layout in ("root","nested","deep"):
            record = data[layout]
            if record["sqlSha256"] != hashlib.sha256(sql).hexdigest():
                raise ValueError(f"{name} {layout} received different migration SQL")
            expected_control = {**applied, "runtime":"jvm"}
            if record["JVM"] != expected_control or record["AOT JVM"] != expected_control:
                raise ValueError("missing ordinary/AOT JVM migration control")
            native = record["native"]
            if native.get("outcome") == "migration failed":
                flattened = any("Unable to obtain inputstream for resource: db/migration/V2__users.sql" in item
                                for item in native["diagnostics"])
                parsed[layout] = "failed opening flattened path" if flattened else "other migration failure"
            else:
                parsed[layout] = native
        result[0][name] = side(parsed["nested"],applied if name == "fix" else "failed opening flattened path")
        result[1][name] = side(parsed["root"],applied)
        result[2][name] = side([parsed["nested"],parsed["deep"]],[applied,applied] if name == "fix" else None)
    return result


MEASUREMENTS = {
    "S10": ("Gradle consumer build", ["gradle/S10.json"], metadata),
    "S16": ("Original Boot source slices on the reconstructed July Framework codec profile",
            ["webflux-2017/reconstructed-observations.json"], webflux),
    "S47": ("Gradle bootJar", [LAYER_RECEIPT], layers),
    "S50": ("GraalVM native executable and JDBC", ["native-flyway/parent.json","native-flyway/fix.json"], migrations),
}
