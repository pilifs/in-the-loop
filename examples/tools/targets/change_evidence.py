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


def outcome(trial, entry, client, required_helper=None, require_projection=False):
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
    if require_projection:
        projections = trial.get("publicProjections", [])
        if len(projections) != 2 or projections[0] != projections[1] or set(value) != {"return"}:
            return None
        try:
            measured = digest(json.loads(value["return"]))
        except (ValueError, TypeError):
            return None
        if projections[0].get("observationSha256") != measured or not projections[0].get("entryCalls"):
            return None
    if set(value) == {"throws"}:
        escapes = trial.get("escapingExceptions", [])
        if len(escapes) != 2 or any(e.get("entry") != entry or e.get("jarSha256") != client
                                    or e.get("throws") != value["throws"] for e in escapes):
            return None
    elif set(value) != {"return"}:
        return None
    return value


def entry_artifact(binding):
    return binding.get("dispatchArtifactSha256") or binding.get("entryArtifactSha256") or binding["classpath"][0]


class SideCache:
    """Only deterministic, qualified, positive sides can bypass new original-entry replays."""

    def __init__(self, directory, basis, images, *, defer_writes=False, new_expected=None):
        self.directory = directory
        self.basis = basis
        self.images = images
        self.new_expected = new_expected or {}
        self.actions = {}
        self.pending = {} if defer_writes else None

    def key(self, side, files, binding, report):
        return digest({"context": self.basis, "jdk": self.images[side], "files": list(map(str, files)),
                       "binding": {k: v for k, v in binding.items() if k not in ("commit", "trials", "loadedDependencyClasses")},
                       "observerClasses": report["probeClasses"], "call": report["observerInvocation"]})

    @staticmethod
    def valid(payload, domain, entry, client, required_helper=None, require_projection=False):
        trials = payload["trials"]
        if (len(trials) != len(domain) or not payload["loadedDependencyClasses"]
                or set(payload["loadedPerInput"]) != {str(i) for i in range(len(domain))}):
            return False
        return all(t["input"] == i and outcome(t, entry, client, required_helper, require_projection) == case["expected"]
                   and "return" in case["expected"] for i, (case, t) in enumerate(zip(domain, trials)))

    def domain(self, side, report):
        if side == "new" and self.new_expected:
            return [{**case, "expected": self.new_expected.get(i, case["expected"])} for i,case in enumerate(report["cases"])]
        return report["cases"]

    def lookup(self, side, files, binding, report):
        key = self.key(side, files, binding, report)
        self.actions[side] = {"action": "executed", "key": key}
        path = self.directory / (key + ".json")
        if path.is_file():
            try:
                record = json.loads(path.read_text())
                payload = record["evidence"]
                if (record["key"] == key and digest(payload) == record["evidenceSha256"]
                        and self.valid(payload, self.domain(side, report), binding.get("resolvedEntry", report["entry"]), entry_artifact(binding), binding.get("requiredHelperProof"), "generatedObserver" in report)):
                    self.actions[side]["action"] = "exact reuse"
                    return payload
            except (KeyError, TypeError, ValueError):
                pass
        return None

    def remember(self, side, binding, report, loaded_per_input):
        payload = {"trials": binding["trials"], "loadedDependencyClasses": binding["loadedDependencyClasses"],
                   "loadedPerInput": {str(i): sorted(v) for i, v in loaded_per_input.items()}}
        if self.valid(payload, self.domain(side, report), binding.get("resolvedEntry", report["entry"]), entry_artifact(binding), binding.get("requiredHelperProof"), "generatedObserver" in report):
            key = self.actions[side]["key"]
            path = self.directory / (key + ".json")
            record = {"key": key, "evidenceSha256": digest(payload), "evidence": payload}
            if self.pending is None:
                write_json(path, record)
            else:
                self.pending[path] = record

    def publish_pending(self):
        for path, record in self.pending.items():
            write_json(path, record)
        self.pending.clear()


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
    asserted = spec.get("assertedSides", ["old", "new"])
    if asserted not in (["old"], ["new"], ["old", "new"]):
        raise ValueError("invalid registered side scope")
    children = []
    changes = {c["input"]: c["expectedNew"] for c in intent["allowedChanges"]} if isinstance(intent, dict) else {}
    for i, case in enumerate(cases):
        values, startup = {}, {}
        for side in ("old", "new"):
            trial = indexed[side].get(i, {})
            cp = sides.get(side, {}).get("classpath", [])
            values[side] = outcome(trial, sides[side].get("resolvedEntry", spec["entry"]), entry_artifact(sides[side]), sides[side].get("requiredHelperProof"), "generatedObserver" in spec) if cp else None
            if trial.get("beforeEntry"):
                startup[side] = trial["beforeEntry"]
        old, new = values["old"], values["new"]
        target = changes.get(i, case["expected"])
        def agrees(actual, expected):
            if spec.get("predictionEncoding") == "typed-public-fields/v1":
                from targets.observer_generation import matches
                return matches(actual, expected)
            return actual == expected
        if len(asserted) == 1:
            measured = values[asserted[0]]
            status = ("open" if measured is None or intent == "undecided" else
                      "established" if agrees(measured, case["expected"]) else "refuted")
        elif old is None or new is None or not agrees(old, case["expected"]) or intent == "undecided":
            status = "open"
        else:
            status = "established" if agrees(new, target) else "refuted"
        children.append({"input": i, "arguments": case["args"], "expected": case["expected"], **values,
                         **({"intendedChange": target} if i in changes else {}),
                         "status": status, **({"beforeEntry": startup} if startup else {})})
    witness = next((c for c in children if c["status"] == "refuted"), None)
    missing = [c["input"] for c in children if c["status"] == "open"]
    rule = ("check both intended observations on the union of all enumerated singleton inputs" if len(asserted) == 2
            else f"check only the registered {asserted[0]} prediction over the enumerated inputs")
    return {"rule": rule,
            "status": "refuted" if witness else "open" if missing else "established",
            "inputs": len(cases), "covered": len(cases) - len(missing), "children": children,
            "firstOpenDependency": missing[0] if missing else None,
            "witness": None if witness is None else witness["input"]}
