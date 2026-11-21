"""Check driver selection and the actual JDBC service provider bytes on an original JVM classpath."""

import hashlib
from pathlib import Path
import re
import subprocess
import zipfile

from targets import runtime_jar, upgrade_linkage


SERVICE = "META-INF/services/java.sql.Driver"


def inspect_driver(url, prepared, feature, jdk, helpers, temp, env, deadline):
    files, operand, binding = prepared
    output = upgrade_linkage.lookup(["--jdbc-driver"], "UPGRADE-DRIVER ", files, jdk, helpers, temp, env,
                                    deadline, stdin=url)
    state, _, value = output.partition(" ")
    selection = {"outcome": state}
    if state == "selected":
        name, uri = value.split(" ", 1)
        selection.update(name=name, **upgrade_linkage.file_binding(uri, files, binding))
    else:
        selection["sqlState"] = value
    evidence = {"selection": selection, "maxClassMajor": feature + 44, "declaringJarSha256": binding["dependency"],
                "providers": []}
    with zipfile.ZipFile(operand) as archive:
        if SERVICE not in archive.namelist():
            return evidence
        if archive.namelist().count(SERVICE) != 1:
            raise ValueError("multiple JDBC service files in one operand")
        descriptor = archive.read(SERVICE)
    evidence["serviceFileSha256"] = hashlib.sha256(descriptor).hexdigest()
    names = [line.partition("#")[0].strip() for line in descriptor.decode("utf-8").splitlines()]
    for name in dict.fromkeys(n for n in names if n):
        if not re.fullmatch(r"(?:[A-Za-z_$][\w$]*\.)*[A-Za-z_$][\w$]*", name, re.ASCII):
            raise ValueError("unsupported JDBC provider name")
        state, _, value = upgrade_linkage.lookup([name], "UPGRADE-LOOKUP ", files, jdk, helpers, temp, env, deadline).partition(" ")
        provider = {"name": name, "link": state}
        if state == "linkage":
            provider["error"] = value
        elif state == "found":
            provider["loadedFrom"] = upgrade_linkage.file_binding(value, files, binding)
        internal = runtime_jar.internal(name)
        for pos, jar in enumerate(files):
            data = runtime_jar.effective_class(jar, internal, feature)
            if data is not None:
                if runtime_jar.this_class(data) != internal:
                    raise ValueError("JDBC provider entry declares another class")
                provider.update(classpathIndex=pos, jarSha256=binding["classpath"][pos],
                                classSha256=hashlib.sha256(data).hexdigest(), classMajor=int.from_bytes(data[6:8], "big"))
                break
        evidence["providers"].append(provider)
    return evidence


def diagnose(report, prepared, old_loaded, feature, jdk, helpers, temp, env, deadline):
    checked = {}
    for comparison in report["beforeEntryComparison"]:
        i = comparison["input"]
        old, new = (report["sides"][side]["trials"][i] for side in ("old", "new"))
        if (not new.get("repeatableBeforeEntry") or old["qualifiedMethodEntries"] != 2
                or old["observations"] != [report["cases"][i]["expected"]] * 2 or not old["loadedUpgradeOnEachReplay"]):
            continue
        failure = new["beforeEntry"][0]
        if failure["causes"][-1:] != ["java.sql.SQLException"]:
            continue
        event = failure.get("rootThrow", {}) if len(failure["causes"]) > 1 else failure
        site = event.get("runtimeThrowLocation", {}).get("entry", "")
        if not site.startswith(("java.sql.DriverManager#getConnection(", "java.sql.DriverManager#getDriver(")):
            continue
        match = re.fullmatch(r"No suitable driver found for (jdbc:[A-Za-z][\w+.-]*:[^\r\n]+)", failure.get("lastCauseMessage", ""))
        if not match:
            continue
        url = match[1]
        key = hashlib.sha256(url.encode()).hexdigest()
        if key not in checked:
            try:
                checked[key] = {s: inspect_driver(url, side, feature, jdk, helpers, temp, env, deadline)
                                for s, side in prepared.items()}
            except (ValueError, OSError, subprocess.SubprocessError, zipfile.BadZipFile) as exc:
                checked[key] = {"open": str(exc)}
        paired = checked[key]
        if "open" in paired:
            continue
        before, after = paired["old"], paired["new"]
        selected = before["selection"]
        blocked = [p["name"] for p in after["providers"] if p.get("error") == "java.lang.UnsupportedClassVersionError"
                   and p.get("jarSha256") == after["declaringJarSha256"] and p["classMajor"] > after["maxClassMajor"]]
        if (selected.get("jarSha256") == before["declaringJarSha256"] and selected.get("name") in old_loaded.get(i, set())
                and after["selection"] == {"outcome": "none", "sqlState": "08001"} and blocked):
            comparison["jdbcDriver"] = {"urlSha256": key, "selectedBefore": selected["name"],
                                        "incompatibleProviders": blocked, "throwLocation": event["runtimeThrowLocation"]}
    if checked:
        report["jdbcDriverEvidence"] = checked


def main(argv=None):
    import argparse
    import json
    import tempfile
    import time
    from targets import runtime_jdk, upgrade_replay

    parser = argparse.ArgumentParser(description="Check which driver accepts a JDBC URL on a locked original classpath.")
    parser.add_argument("--prepared", type=Path, required=True, help="ordered file and sha256 rows from the original build")
    parser.add_argument("--dependency", required=True, help="SHA-256 of the driver artifact on this classpath")
    parser.add_argument("--jdk", type=Path, required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if not args.url.startswith("jdbc:") or any(char in args.url for char in "\r\n"):
        parser.error("expected a single JDBC URL")
    started = time.monotonic()
    result = {"status": "open", "scope": "DriverManager.getDriver URL selection without opening a connection",
              "urlSha256": hashlib.sha256(args.url.encode()).hexdigest(), "dependency": args.dependency}
    try:
        document = json.loads(args.prepared.read_text())
        files, operand, hashes = upgrade_replay.checked_classpath(args.prepared, document, args.dependency)
        jdk = args.jdk.resolve()
        identity = runtime_jdk.identity(jdk)
        result.update(jdk=identity["release"], classpath=hashes, lookupSha256=upgrade_replay.sha(upgrade_replay.LOOKUP))
        with tempfile.TemporaryDirectory(prefix="upgrade-driver-") as directory:
            temp = Path(directory)
            env = {"PATH": str(jdk/"bin") + ":/usr/bin:/bin", "HOME": directory, "TMPDIR": directory,
                   "TZ": "UTC", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
            subprocess.run([str(jdk/"bin/javac"), "-J-Djava.io.tmpdir="+directory, "-proc:none", "-d", directory,
                            str(upgrade_replay.LOOKUP)], cwd=temp, env=env, check=True, capture_output=True, timeout=30)
            binding = {"classpath": hashes, "dependency": args.dependency}
            result["driver"] = inspect_driver(args.url, (files, operand, binding), int(identity["feature"]), jdk,
                                              temp, temp, env, started+60)
            selection = result["driver"]["selection"]
            if selection.get("jarSha256") or selection == {"outcome": "none", "sqlState": "08001"}:
                result["status"] = "checked"
            else:
                result["reason"] = "driver selection did not bind to a supplied artifact or the no-driver SQL state"
    except (OSError, ValueError, KeyError, subprocess.SubprocessError, zipfile.BadZipFile) as exc:
        result["reason"] = str(exc)
    result["elapsedSeconds"] = round(time.monotonic() - started, 3)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(result["status"], result.get("driver", {}).get("selection", {}).get("outcome", result.get("reason", "")))
    return 0 if result["status"] == "checked" else 1
