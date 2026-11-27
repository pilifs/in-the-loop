"""Run a frozen native property, derive a first-use capture from its diagnostic, and retry.

    python3 examples/tools/targets/startup_facts.py --work DIR --locale C [--resume] -- \
        jvmcontract prove ENTRY --classes CLASSES --assert PREDICATE --engine native --gaps strict --json
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


def write_report(path, value):
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, encoding="utf-8", delete=False) as out:
        json.dump(value, out, indent=2, ensure_ascii=True)
        out.write("\n")
        name = out.name
    os.replace(name, path)


def run_step(command, extra, work, env):
    work.mkdir()
    proc = subprocess.run([*command, *extra, "--work", str(work)], env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)
    stdout = proc.stdout.decode("utf-8", errors="replace")
    stderr = proc.stderr.decode("utf-8", errors="replace")
    (work / "command.stdout").write_bytes(proc.stdout)
    (work / "command.stderr").write_bytes(proc.stderr)
    outcome = None
    if stdout.strip():
        data = json.loads(stdout)
        if len(data) != 1 or not isinstance(data[0], dict):
            raise ValueError("startup recovery requires one frozen property")
        outcome = data[0]
    return proc.returncode, outcome, stderr


def first_root(outcome):
    gaps = (outcome.get("search") or {}).get("gaps", [])
    if len(gaps) == 1 and gaps[0].get("treatment") == "refused":
        gap = gaps[0]
        id_ = gap.get("id", "")
        match = re.fullmatch(r"class-initializer:([\w.$]+)\.<clinit>\(\)V", id_)
        if match:
            return match[1]
        # Some initializers run in strict mode up to the actual unsupported JDK call.
        # Attribute it to startup only when every reported site is the same initializer.
        operation = id_.partition("@jdk-")[0].partition(":")[2]
        if operation in {
            "java.lang.System.getProperties()Ljava/util/Properties;",
            "java.nio.charset.Charset.defaultCharset()Ljava/nio/charset/Charset;",
            "java.lang.String.getBytes()[B",
            "java.lang.Class.getMethod(Ljava/lang/String;[Ljava/lang/Class;)Ljava/lang/reflect/Method;",
            "java.lang.Class.getDeclaredMethods()[Ljava/lang/reflect/Method;",
        }:
            sites = [re.fullmatch(r"([\w.$]+)\.<clinit>(?::\d+)?", s) for s in gap.get("sites", [])]
            if sites and all(sites):
                owners = {site[1] for site in sites}
                if len(owners) == 1:
                    return owners.pop()
    return None


def recover(command, work, locale=None, *, resume=False, receipts=None, env=None, properties=None, revision=None):
    """Return the original verdict and the separately scoped retry. Never reuse a verdict."""
    command = list(map(str, command))
    if len(command) < 3 or command[1] != "prove" or "--json" not in command:
        raise ValueError("provide one JSON jvmcontract prove command")
    for flag, expected in (("--engine", "native"), ("--gaps", "strict")):
        if not any(pair == [flag, expected] for pair in (command[i:i+2] for i in range(len(command)))):
            raise ValueError(f"startup recovery requires {flag} {expected}")
    managed = {"--observed-initializer", "--observed-runtime", "--work", "--cache"}
    if any(word.split("=", 1)[0] in managed for word in command):
        raise ValueError("startup recovery manages the recording, work directory and fresh proof invocations")
    if locale not in (None, "C", "C.UTF-8"):
        raise ValueError("unsupported startup locale")
    work = Path(work).resolve()
    work.mkdir(parents=True, exist_ok=True)
    receipts = (Path(receipts) if receipts else work / "receipts").resolve()
    previous = work / "startup-report.json"
    frozen = hashlib.sha256(json.dumps(command[1:], separators=(",", ":")).encode()).hexdigest()
    property_key = hashlib.sha256(json.dumps(properties or {}, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
    expected = None
    if resume:
        old = json.loads(previous.read_bytes())
        if (old["claimSha256"], old["locale"], old.get("revision"), old.get("propertyInputsSha256", property_key)) != (frozen, locale, revision, property_key) or not old.get("receiptId"):
            raise ValueError("saved startup report lacks a matching frozen claim, launch profile or successful recording")
        expected = old["receiptId"]
    attempt = Path(tempfile.mkdtemp(prefix="attempt-", dir=work))
    report = {"schema": "startup-claim-report/v1", "command": command[1:], "claimSha256": frozen, "locale": locale,
              "attempt": attempt.name, "route": "native strict", "original": None, "root": None, "receiptId": None,
              "consumed": [], "recording": "none", "resume": resume, "retry": None, "remaining": None}
    report["propertyInputsSha256"] = property_key
    report["revision"] = revision
    revision_option = {"startupRevision": revision} if revision else {}
    _, original, diagnostic = run_step(command, [], attempt / "original", env)
    if original:
        report["original"] = {"verdict": original["verdict"], "reason": original.get("problem"), "target": original["target"]}
        report["root"] = first_root(original)
    root = report["root"]
    if not root:
        report["remaining"] = (original or {}).get("problem") or diagnostic.strip() or None
    else:
        observed = ["--observed-initializer", root]
        _, initial, stop = run_step(command, observed, attempt / "initializer", env)
        report["initializerStop"] = (initial or {}).get("problem") or stop.strip()
        if initial is None and "holds an object of java.lang.reflect.Method" in stop and "neither holds nor describes" in stop:
            _, outcome, diagnostic = run_step(command, [*observed, "--observed-runtime", json.dumps({"reflectiveMembers":True,**revision_option})], attempt / "retry", env)
            captures = list((attempt / "retry" / "startup-receipts").glob("*.json"))
            if len(captures) == 1 and outcome:
                record = json.loads(captures[0].read_bytes())
                if record.get("schema") != "jvm-startup-member/v1" or record.get("root") != root:
                    raise ValueError("reflective recording does not bind the requested startup root")
                if expected and record["id"] != expected:
                    raise ValueError("fresh reflective capture differs from the saved binding")
                receipts.mkdir(parents=True, exist_ok=True)
                write_report(receipts / (record["id"] + ".json"), record)
                report.update(receiptId=record["id"], recording="fresh reflective lookup and effect comparisons",
                              executed=record["capture"]["events"], reflectiveFields=record["capture"]["fields"], retry=outcome["verdict"],
                              consumed=[a["id"] for a in outcome["stated"]["assumptions"] if a.get("id")],
                              remaining=outcome.get("problem"))
            else:
                report["remaining"] = diagnostic.strip()
        elif initial is None and "read the system properties as a whole" in stop:
            runtime = {"liveProperties": True, "emptyEnvironment": True, "rootWorkingDirectory": True,
                       "processors": 2, "startupProperties": properties or {}, **revision_option}
            _, outcome, diagnostic = run_step(command, [*observed, "--observed-runtime", json.dumps(runtime)], attempt / "retry", env)
            retry_dir = attempt / "retry"
            full = list((retry_dir / "startup-receipts").glob("*.json"))
            partial = [p for p in (retry_dir / "startup-diagnostics").glob("*.json") if json.loads(p.read_bytes()).get("schema") == "jvm-startup-table/v1"]
            found = full or partial
            if len(found) == 1:
                capture = json.loads(found[0].read_bytes())
                if capture.get("schema") != "jvm-startup-table/v1" or capture["root"] != root:
                    raise ValueError("live table recording does not bind the requested root")
                receipts.mkdir(parents=True, exist_ok=True)
                write_report(receipts / found[0].name, capture)
                report.update(table=capture["table"], executed=capture["events"], ordinaryInitializerParity=capture["ordinaryInitializerParity"])
                if full and outcome:
                    if expected and expected != capture["id"]:
                        raise ValueError("fresh live table differs from the named recording")
                    report.update(receiptId=capture["id"], recording="fresh live table and plain comparison", retry=outcome["verdict"],
                                  consumed=[a["id"] for a in outcome["stated"]["assumptions"] if a.get("id")])
                else:
                    report.update(diagnosticId=capture["id"], recording="table observation only")
            report["remaining"] = outcome.get("problem") if outcome else diagnostic.strip()
        elif locale and initial is None and re.search(r"reads the default charset \(.+\), which the observation cannot bind", stop):
            runtime = {"charsetLocale": locale, "charsetReceiptDirectory": str(receipts), **revision_option}
            if expected:
                runtime["expectedCharsetReceipt"] = expected
            _, outcome, diagnostic = run_step(command, [*observed, "--observed-runtime", json.dumps(runtime)], attempt / "retry", env)
            published = re.search(r"^startup receipt ([a-f0-9]{64}): (fresh JVM trace|reused trace, freshly checked subject) \(", diagnostic, re.M)
            if published and outcome:
                id_, report["recording"] = published.groups()
                receipt = json.loads((receipts / (id_ + ".json")).read_bytes())
                if receipt["id"] != id_ or receipt["root"] != root:
                    raise ValueError("recording does not identify the selected root")
                for key in ("target", "assert", "assume", "domain", "throws"):
                    if original.get(key) != outcome.get(key):
                        raise ValueError("startup retry changed the frozen " + key)
                report.update(receiptId=id_, profile=receipt["profile"], executed=receipt["executed"],
                              potentialReferences=receipt["potentialReferences"], retry=outcome["verdict"],
                              consumed=[a["id"] for a in outcome["stated"]["assumptions"] if a.get("id")],
                              remaining=outcome.get("problem"), counterexample=outcome.get("counterexample"))
            else:
                report["remaining"] = diagnostic.strip()
        else:
            report["remaining"] = report["initializerStop"]
    for path in (attempt / "retry" / "startup-diagnostics").glob("*.json"):
        failure = json.loads(path.read_bytes())
        if failure.get("schema") == "jvm-startup-failure/v1":
            roots = [name.replace("/",".") for name in (failure.get("binding") or {}).get("orderedRoots",[])]
            if root not in roots or failure.get("usableAsPremise") is not False or failure.get("normalReturn") is not False:
                raise ValueError("failed startup recording has the wrong scope")
            report.update(failure={"id":failure["id"],"root":failure["root"],"exceptions":failure["exceptions"],"partialEvents":failure["partialEvents"]},
                          recording="failed startup observation")
    write_report(attempt / "startup-report.json", report)
    # Keep the last resumable observation when a later attempt rejects a changed binding.
    if report["receiptId"] or not previous.exists():
        write_report(previous, report)
    return report


def summary(report):
    first = (report.get("original") or {}).get("verdict", "open")
    profile = report.get("profile") or {}
    facts = ", ".join(report["consumed"]) or "none"
    recording = report.get("receiptId") or report.get("diagnosticId") or (report.get("failure") or {}).get("id") or ""
    return "\n".join((f"Original property  {first}  {(report.get('original') or {}).get('target', '')}",
                      f"Startup  {report['root'] or 'no unique root'}  {report['locale'] or 'original launch'}  {profile.get('canonical', '')}".rstrip(),
                      f"Recording  {report['recording']}  {recording}",
                      f"Conditional retry  {report['retry'] or 'open'}", f"Consumed assumptions  {facts}",
                      f"Remaining  {report['remaining'] or 'none'}"))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--locale", choices=("C", "C.UTF-8"), help="requested COMPAT charset profile when the diagnostic needs one")
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--revision", help="revision identity from the original deployment registration")
    ap.add_argument("--property", action="append", default=[], metavar="KEY=VALUE",
                    help="controlled system property supplied to a live-table startup retry")
    ap.add_argument("--receipts", type=Path)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("command", nargs=argparse.REMAINDER)
    args = ap.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    settings = {}
    for item in args.property:
        key, separator, value = item.partition("=")
        if not separator or not key or key in settings: ap.error("--property requires a unique KEY=VALUE")
        settings[key] = value
    result = recover(command, args.work, args.locale, resume=args.resume, receipts=args.receipts, properties=settings, revision=args.revision)
    print(summary(result))
    return 0 if result["receiptId"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
