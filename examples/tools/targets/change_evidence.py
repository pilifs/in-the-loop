"""Compose qualified finite caller observations and resume exact successful JVM trials."""

import json
import os
from pathlib import Path
import tempfile

from targets.change_inventory import digest


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, mode="w", delete=False) as out:
        try:
            json.dump(value, out, indent=2, ensure_ascii=True, allow_nan=False)
            out.write("\n")
            out.close()
            os.replace(out.name, path)
        finally:
            Path(out.name).unlink(missing_ok=True)


def outcome(trial, entry, client, required_helper=None):
    """A returned value or an exception actually escaping the selected original invocation."""
    if required_helper:
        applications = trial.get("checkedApplications", [])
        if (len(applications) != 2 or any(a.get("proofKey") != required_helper or not a.get("applications")
                                          or not a.get("startupArguments") for a in applications)):
            return None
    observations = trial.get("observations", [])
    invocations = trial.get("entryInvocations", [])
    if (trial.get("qualifiedMethodEntries") != 2 or len(observations) != 2
            or observations[0] != observations[1] or len(invocations) != 2
            or any(not isinstance(inv, dict) or type(inv.get("observerCodeIndex")) is not int
                   or "#" not in str(inv.get("dispatchedTo", "")) for inv in invocations)
            or not trial.get("loadedUpgradeOnEachReplay") or trial.get("beforeEntry")):
        return None
    value = observations[0]
    if set(value) == {"throws"}:
        escapes = trial.get("escapingExceptions", [])
        if len(escapes) != 2 or any(e.get("entry") != entry or e.get("jarSha256") != client
                                    or e.get("throws") != value["throws"] for e in escapes):
            return None
    elif set(value) != {"return"}:
        return None
    return value


class SideCache:
    """Only deterministic, qualified, positive sides can bypass new original-entry replays."""

    def __init__(self, directory, basis, images):
        self.directory = directory
        self.basis = basis
        self.images = images
        self.actions = {}

    def key(self, side, files, binding, report):
        return digest({"context": self.basis, "jdk": self.images[side], "files": list(map(str, files)),
                       "binding": {k: v for k, v in binding.items() if k not in ("commit", "trials", "loadedDependencyClasses")},
                       "observerClasses": report["probeClasses"], "call": report["observerInvocation"]})

    @staticmethod
    def valid(payload, domain, entry, client, required_helper=None):
        trials = payload["trials"]
        if (len(trials) != len(domain) or not payload["loadedDependencyClasses"]
                or set(payload["loadedPerInput"]) != {str(i) for i in range(len(domain))}):
            return False
        return all(t["input"] == i and outcome(t, entry, client, required_helper) == case["expected"]
                   and "return" in case["expected"] for i, (case, t) in enumerate(zip(domain, trials)))

    def lookup(self, side, files, binding, report):
        key = self.key(side, files, binding, report)
        self.actions[side] = {"action": "executed", "key": key}
        path = self.directory / (key + ".json")
        if path.is_file():
            try:
                record = json.loads(path.read_text())
                payload = record["evidence"]
                if (record["key"] == key and digest(payload) == record["evidenceSha256"]
                        and self.valid(payload, report["cases"], report["entry"], binding["classpath"][0], binding.get("requiredHelperProof"))):
                    self.actions[side]["action"] = "exact reuse"
                    return payload
            except (KeyError, TypeError, ValueError):
                pass
        return None

    def remember(self, side, binding, report, loaded_per_input):
        payload = {"trials": binding["trials"], "loadedDependencyClasses": binding["loadedDependencyClasses"],
                   "loadedPerInput": {str(i): sorted(v) for i, v in loaded_per_input.items()}}
        if self.valid(payload, report["cases"], report["entry"], binding["classpath"][0], binding.get("requiredHelperProof")):
            key = self.actions[side]["key"]
            write_json(self.directory / (key + ".json"),
                       {"key": key, "evidenceSha256": digest(payload), "evidence": payload})


def compose(spec, report, intent="preserve"):
    """The finite parent requires every registered input. One admitted original witness suffices."""
    cases = spec["cases"]
    if (not cases or len({tuple(c["args"]) for c in cases}) != len(cases)
            or report.get("entry") != spec["entry"] or report.get("cases") != cases):
        raise ValueError("the execution differs from the frozen caller or domain")
    sides = report.get("sides", {})
    indexed = {}
    for side in ("old", "new"):
        rows = sides.get(side, {}).get("trials", [])
        if any(type(r.get("input")) is not int or not 0 <= r["input"] < len(cases) for r in rows):
            raise ValueError("trial outside the frozen domain")
        indexed[side] = {r["input"]: r for r in rows}
        if len(indexed[side]) != len(rows):
            raise ValueError("duplicate trial in finite coverage")
    children = []
    changes = {c["input"]: c["expectedNew"] for c in intent["allowedChanges"]} if isinstance(intent, dict) else {}
    for i, case in enumerate(cases):
        values, startup = {}, {}
        for side in ("old", "new"):
            trial = indexed[side].get(i, {})
            cp = sides.get(side, {}).get("classpath", [])
            values[side] = outcome(trial, spec["entry"], cp[0], sides[side].get("requiredHelperProof")) if cp else None
            if trial.get("beforeEntry"):
                startup[side] = trial["beforeEntry"]
        old, new = values["old"], values["new"]
        target = changes.get(i, case["expected"])
        if old is None or new is None or old != case["expected"] or intent == "undecided":
            status = "open"
        else:
            status = "established" if target == new else "refuted"
        children.append({"input": i, "arguments": case["args"], "expected": case["expected"], **values,
                         **({"intendedChange": target} if i in changes else {}),
                         "status": status, **({"beforeEntry": startup} if startup else {})})
    witness = next((c for c in children if c["status"] == "refuted"), None)
    missing = [c["input"] for c in children if c["status"] == "open"]
    return {"rule": "check both intended observations on the union of all enumerated singleton inputs",
            "status": "refuted" if witness else "open" if missing else "established",
            "inputs": len(cases), "covered": len(cases) - len(missing), "children": children,
            "firstOpenDependency": missing[0] if missing else None,
            "witness": None if witness is None else witness["input"]}
