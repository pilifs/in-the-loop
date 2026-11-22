"""Check the default supplier and the original Avro name-validation bytecode after ThreadLocal.get."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

from companions import HERE, ROOT, SHA, document, hash_bytes, invocation, materialize, proof, runtime_jdk, selected_class
from public_run import read
from targets import runtime_jar

SCHEMA = "org/apache/avro/Schema"
FIELDS = {"364": "validateNames", "367": "VALIDATE_NAMES"}
NAME = "(Ljava/lang/String;)Ljava/lang/String;"
EXPLICIT = "(Ljava/lang/String;Ljava/lang/Object;)Ljava/lang/String;"
EXPORTS = [arg for package in ("asm", "asm.tree")
           for arg in ("--add-exports", "java.base/jdk.internal.org.objectweb." + package + "=ALL-UNNAMED")]
QUERIES = {
    "names": ("campaign.NameChecks#names", "code >= 0 && code < 18", (32, 64)),
    "twoAscii": ("campaign.NameChecks#twoAscii", "first >= 0 && first < 128 && second >= 0 && second < 128", (16, 32)),
    "publicUtf": ("campaign.UtfNameChecks#names", "code >= 0 && code < 18", (32, 64)),
}


def qualify_factory(jars, binding):
    name = "org/apache/avro/util/internal/ThreadLocalWithInitial"
    desc = "(Ljava/util/function/Supplier;)Ljava/lang/ThreadLocal;"
    index, entry, body = selected_class(jars, name + ".class")
    _, methods, _ = runtime_jar._declarations(body, with_code=True)
    access, code, catches = methods["of", desc]
    digest = hash_bytes(code)
    pool = hash_bytes(body[10:runtime_jar._pool(body)[1]])
    call = runtime_jar.member_at_code_index(body, "of", desc, 1, code_sha256=digest, pool_sha256=pool)
    if (runtime_jar.this_class(body) != name or ("<clinit>", "()V") in methods or access != 0x0009 or catches
            or len(code) != 5 or code[:2] != bytes((0x2a, 0xb8)) or code[-1] != 0xb0
            or not call or (call["owner"], call["name"], call["descriptor"]) != ("java.lang.ThreadLocal", "withInitial", desc)):
        raise ValueError("different supplier factory")
    return {"jar": binding["orderedJars"][index], "entry": entry, "classSha256": hash_bytes(body), "codeSha256": digest,
            "poolSha256": pool, "target": call}


def qualify(original, projected, supplier, descriptor, field):
    """Bind the cut to two resolved JVM instructions. Every remaining byte and its pool index must agree."""
    _, before, _ = runtime_jar._declarations(original, with_code=True)
    _, after, _ = runtime_jar._declarations(projected, with_code=True)
    pool_end = runtime_jar._pool(original)[1]
    if (runtime_jar.this_class(original) != SCHEMA or runtime_jar.this_class(projected) != "campaign/NameSuffix"
            or projected[10:pool_end] != original[10:pool_end] or set(after) != {("defaultPolicy", descriptor), ("validateName", EXPLICIT)}):
        raise ValueError("different name-validation class or constant pool")
    _, producer, handlers = before[supplier, descriptor]
    _, code, catches = before["validateName", NAME]
    _, explicit, explicit_catches = after["validateName", EXPLICIT]
    _, projected_supplier, supplier_catches = after["defaultPolicy", descriptor]
    if (any((handlers, catches, explicit_catches, supplier_catches)) or producer != projected_supplier
            or explicit != b"\x2b" + bytes(5) + code[6:]):
        raise ValueError("different supplier, consumer instructions or exception handlers")
    pool_sha = hash_bytes(original[10:pool_end])
    def member(index):
        return runtime_jar.member_at_code_index(original, "validateName", NAME, index,
                                                code_sha256=hash_bytes(code), pool_sha256=pool_sha)
    read, get = member(0), member(3)
    if (not read or not get or (read["opcode"], read["owner"], read["name"], read["descriptor"]) !=
            ("getstatic", SCHEMA.replace("/", "."), field, "Ljava/lang/ThreadLocal;")
            or (get["opcode"], get["owner"], get["name"], get["descriptor"]) !=
            ("invokevirtual", "java.lang.ThreadLocal", "get", "()Ljava/lang/Object;")):
        raise ValueError("different thread-local producer")
    return {"field": field, "consumer": "validateName" + NAME, "originalCodeSha256": hash_bytes(code),
            "afterGetSha256": hash_bytes(code[6:]), "afterGetBytes": len(code) - 6, "originalPoolSha256": pool_sha,
            "supplier": supplier + descriptor, "supplierCodeSha256": hash_bytes(producer),
            "schemaClassSha256": hash_bytes(original), "projectedClassSha256": hash_bytes(projected)}


def challenge_qualification(original, projected, supplier, descriptor, field):
    _, methods, _ = runtime_jar._declarations(projected, with_code=True)
    _, code, _ = methods["validateName", EXPLICIT]
    if projected.count(code) != 1:
        raise ValueError("ambiguous projected method for the instruction control")
    changed_code = projected.replace(code, code[:6] + bytes((0,)) + code[7:])
    changed_pool = projected.replace(b"java/lang/ThreadLocal", b"java/lang/ThreadLocaX", 1)
    challenged = {"field": (projected, "VALIDATE_DEFAULTS"), "instruction": (changed_code, field), "pool": (changed_pool, field)}
    for label, (body, selected_field) in challenged.items():
        try:
            qualify(original, body, supplier, descriptor, selected_field)
        except ValueError:
            continue
        raise ValueError(f"accepted the changed {label}")
    return list(challenged)


def policy_sites(lines, number, side, cut, policy):
    entries = ("renamed", "preserved") if number == "364" else ("union", "direct")
    expected = {(entry, code): int(entry != entries[0] or side == "fix") for entry in entries for code in range(4)}
    returns, seen, binding = {}, {key: [] for key in expected}, []
    for line in lines:
        tag, *parts = line.split("\t")
        if tag == "SITE":
            binding.append(parts)
        elif tag == "CALL":
            entry, code, value = parts
            key = (entry, int(code))
            if key in returns:
                raise ValueError("duplicate public input")
            returns[key] = int(value)
        elif tag == "GET":
            entry, code, name, observed = parts
            if observed != policy:
                raise ValueError("public reader received a different name policy")
            seen[entry, int(code)].append(name)
        else:
            raise ValueError("unexpected debugger observation")
    if binding != [[cut["originalCodeSha256"], cut["originalPoolSha256"]]] or returns != expected:
        raise ValueError("debugger changed the public behavior or reached a different lookup")
    rows = []
    for (entry, code), names in seen.items():
        needed = {"MyRecord", "E", "field"} if number == "364" else {"RecordA", "Element", "fieldA", "value"}
        if number == "364" and entry == "preserved":
            needed.add("Other")
        if number == "367" and code:
            needed.add("marker")
        if not needed.issubset(names):
            raise ValueError(f"{number}/{side}/{entry}/{code}: missing original name-policy lookups {needed.difference(names)}")
        rows.append({"entry": entry, "code": code, "value": returns[entry, code], "names": names})
    return rows


def prepare(number, side, out, work, jdk):
    folder, = (ROOT / "examples").glob(number + "-*")
    jars, binding = materialize(folder, side, work)
    classes = work / "classes"
    (classes / "campaign").mkdir(parents=True)
    cp = os.pathsep.join(map(str, [classes, *jars]))
    env = dict(os.environ, JAVA_HOME=str(jdk), JVMCONTRACT_JAR_RELEASE="21", PATH=str(jdk / "bin") + os.pathsep + os.defpath)
    index, entry, original = selected_class(jars, SCHEMA + ".class")
    original_path = work / "Schema.class"
    original_path.write_bytes(original)
    projected = classes / "campaign/NameSuffix.class"
    tool = HERE / "ProjectNameValidation.java"
    args = [jdk / "bin/java", *EXPORTS, "-cp", cp, tool, original_path, projected, FIELDS[number]]
    supplier, descriptor = subprocess.check_output(args, cwd=work, env=env, text=True).split()
    projected_bytes = projected.read_bytes()
    cut = qualify(original, projected_bytes, supplier, descriptor, FIELDS[number])
    cut["rejectedChanges"] = challenge_qualification(original, projected_bytes, supplier, descriptor, FIELDS[number])
    src = [HERE / "NameChecks.java", HERE / "NamePolicySites.java", HERE / "AvroSites.java", *sorted((folder / "adapter").rglob("*.java"))]
    if number == "367":
        src.append(HERE / "UtfNameChecks.java")
    subprocess.run([jdk / "bin/javac", "-parameters", "-g", "-cp", cp, "-d", classes, *src], env=env, cwd=work, check=True)
    physical = invocation([jdk / "bin/java", "-Xverify:all", "-cp", cp, "campaign.NameChecks", number, side],
                          "original-jvm", out, work, env)
    policy = "java.lang.Boolean" if number == "364" else "org.apache.avro.NameValidator$2"
    expected = f"publicCalls=8 names=18 accepted=14 rejected=4 asciiPairs=16384 overrides=4 publicUtf={18 if number == '367' else 0} policy={policy}"
    if physical["exit"] or (out / physical["stdout"]).read_text().strip() != expected:
        raise ValueError(f"{number}/{side}: original and explicit-policy observations differ, see {out}")
    traced = invocation([jdk / "bin/java", "-cp", cp, "campaign.NamePolicySites", number, side, cp, work],
                        "policy-sites", out, work, env)
    if traced["exit"]:
        raise ValueError(f"{number}/{side}: debugger failed, see {out / traced['stderr']}")
    sites = policy_sites((out / traced["stdout"]).read_text().splitlines(), number, side, cut, policy)
    report = {"example": number, "side": side, "binding": binding, "jdkModules": SHA(jdk / "lib/modules"),
              "schemaProvider": {"jar": binding["orderedJars"][index], "entry": entry}, "qualification": cut,
              "threadLocalFactory": qualify_factory(jars, binding),
              "physical": physical, "trace": traced, "callSites": sites, "defaultPolicyClass": policy,
              "checksClassSha256": SHA(classes / "campaign/NameChecks.class"),
              "extractorSha256": SHA(tool), "checksSourceSha256": SHA(src[0]), "proofs": {}}
    if number == "367":
        report["publicUtfClassSha256"] = SHA(classes / "campaign/UtfNameChecks.class")
    return classes, jars, env, report


def run(out, numbers, sides, queries, physical_only, compare):
    jdk = Path(runtime_jdk.home("21"))
    for number in numbers:
        for side in sides:
            dest = out / number / side
            dest.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="avro-name-validation-") as tmp:
                work = Path(tmp)
                classes, jars, env, report = prepare(number, side, dest, work, jdk)
                if not physical_only:
                    checker = Path(os.environ["JVMCONTRACT"]).resolve()
                    report.update(checker=SHA(checker), source=os.environ["VERIFY_SOURCE_COMMIT"])
                    routes = [(checker, report["proofs"], "")]
                    if compare:
                        folder, = (ROOT / "examples").glob(number + "-*")
                        prior = read(folder / "records/final/run.json")
                        previous = checker.parent.parent / prior["libTree"] / "jvmcontract"
                        if SHA(previous) != prior["checkerSha256"]:
                            raise ValueError("different campaign baseline executable")
                        report["baseline"] = {"checker": prior["checkerSha256"], "source": prior["sourceCommit"], "proofs": {}}
                        routes.insert(0, (previous, report["baseline"]["proofs"], "baseline-"))
                    for binary, outcomes, prefix in routes:
                        for method in queries:
                            if method == "publicUtf" and number != "367":
                                continue
                            entry, guard, bounds = QUERIES[method]
                            outcomes[method] = proof(binary, classes, jars, work, env, dest, entry,
                                                     prefix + method, guard, bounds=bounds)
                            document(dest / "measurement.json", report)
                document(dest / "measurement.json", report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--example", choices=FIELDS)
    parser.add_argument("--side", choices=("parent", "fix"))
    parser.add_argument("--query", choices=QUERIES)
    parser.add_argument("--physical-only", action="store_true")
    parser.add_argument("--compare-campaign", action="store_true", help="also run the original campaign checker on the same compiled inputs")
    args = parser.parse_args()
    run(args.output.resolve(), [args.example] if args.example else FIELDS, [args.side] if args.side else ("parent", "fix"),
        [args.query] if args.query else QUERIES, args.physical_only, args.compare_campaign)
