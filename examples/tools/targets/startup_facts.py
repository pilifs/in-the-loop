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
        match = re.fullmatch(r"class-initializer:([\w.$]+)\.<clinit>\(\)V", gaps[0].get("id", ""))
        if match:
            return match[1]
    return None


def recover(command, work, locale, *, resume=False, receipts=None, env=None):
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
    if locale not in ("C", "C.UTF-8"):
        raise ValueError("unsupported startup locale")
    work = Path(work).resolve()
    work.mkdir(parents=True, exist_ok=True)
    receipts = (Path(receipts) if receipts else work / "receipts").resolve()
    previous = work / "startup-report.json"
    frozen = hashlib.sha256(json.dumps(command[1:], separators=(",", ":")).encode()).hexdigest()
    expected = None
    if resume:
        old = json.loads(previous.read_bytes())
        if (old["claimSha256"], old["locale"]) != (frozen, locale) or not old.get("receiptId"):
            raise ValueError("saved startup report lacks a matching frozen claim, launch profile or successful recording")
        expected = old["receiptId"]
    attempt = Path(tempfile.mkdtemp(prefix="attempt-", dir=work))
    report = {"schema": "startup-claim-report/v1", "command": command[1:], "claimSha256": frozen, "locale": locale,
              "attempt": attempt.name, "route": "native strict", "original": None, "root": None, "receiptId": None,
              "consumed": [], "recording": "none", "resume": resume, "retry": None, "remaining": None}
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
        if initial is None and re.search(r"reads the default charset \(.+\), which the observation cannot bind", stop):
            runtime = {"charsetLocale": locale, "charsetReceiptDirectory": str(receipts)}
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
    write_report(attempt / "startup-report.json", report)
    # Keep the last resumable observation when a later attempt rejects a changed binding.
    if report["receiptId"] or not previous.exists():
        write_report(previous, report)
    return report


def summary(report):
    first = (report.get("original") or {}).get("verdict", "open")
    profile = report.get("profile") or {}
    facts = ", ".join(report["consumed"]) or "none"
    return "\n".join((f"Original property  {first}  {(report.get('original') or {}).get('target', '')}",
                      f"Startup  {report['root'] or 'no unique root'}  {report['locale']}  {profile.get('canonical', 'unavailable')}",
                      f"Recording  {report['recording']}  {report['receiptId'] or ''}",
                      f"Conditional retry  {report['retry'] or 'open'}", f"Consumed assumptions  {facts}",
                      f"Remaining  {report['remaining'] or 'none'}"))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--locale", required=True, choices=("C", "C.UTF-8"))
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--receipts", type=Path)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("command", nargs=argparse.REMAINDER)
    args = ap.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    result = recover(command, args.work, args.locale, resume=args.resume, receipts=args.receipts)
    print(summary(result))
    return 0 if result["receiptId"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
