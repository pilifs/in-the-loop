#!/usr/bin/env python3
"""Tests for accept.py, the acceptance check of an answer given beside the route, and its controls: an answer the
evidence does not give, a result that is not there, an artifact that changed, a trial bound.
Run: python3 examples/tools/test_accept.py

The examples are copies of the made-up target fixture (examples/tools/targets/fixtures) in a temporary checkout, with
a job, its result and its outcome written by hand in the shape the pipeline and the drivers leave (`beside`, which
llm-dlc/tools/test_changes.py uses too). Nothing is run. One test reads this checkout's own example 289."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import accept

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "examples/tools/targets/fixtures"
sys.path.append(str(REPO / "lib/tools"))
from cost_tier import cost  # noqa: E402
sys.path.append(str(Path(__file__).resolve().parents[2] / "lib/tools"))
from cost_tier import cost  # noqa: E402

COMMIT = "c" * 40
VERDICT = {"established": "verified", "refuted": "violation"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def outcome_of(task: dict, claim: dict, answer: str, bound: int | None) -> dict | list:
    """An outcome as `jvmcontract prove --json` (a list of one) or `equivalence --json` prints it, of the answer."""
    entry = task["target"].split("(", 1)[0]
    refuted = answer == "refuted"
    checked = {
        "verdict": VERDICT.get(answer, "unverifiable"), "target": entry, "problem": None if answer in VERDICT else "made up",
        "assume": claim.get("assume"), "assert": claim.get("assert") if task["kind"] == "prove" else "result",
        "throws": list(claim.get("throws") or []),
        "counterexample": {"input": "allowed(field=\"ab\")", "inputs": [{"name": "field", "type": "java.lang.String",
                                                                         "value": {"kind": "string", "units": [97, 98]}}]} if refuted else None,
        "search": {"engine": task.get("engine"), "gap_mode": task.get("gaps"), "max_array_length": bound, "unwind": 16},
        "stated": {"bounds": {"unwind": 16, "complete": not refuted},
                   "vacuity": {} if refuted else {"status": "non-vacuous", "basis": "probe", "witness": "allowed(field=\"\")",
                                                  **({"outside": task["allowedChange"]} if "allowedChange" in task else {})},
                   "domain": {"parameters": [{"name": n, "null": True} for n in claim.get("nullable") or []]},
                   "assumptions": [{"kind": "precondition", "text": claim.get("assume") or "true", "basis": "stated"},
                                   {"kind": "library", "text": "made up: what the checker assumed", "basis": "engine"}],
                   "models": {"digest": "sha256:made-up", "jdk": "25"}, "checker": {"name": "made up", "solver": "made up"}},
    }
    if refuted:
        checked["replay"] = {"by": "jvm", "reproduced": True}
    if task["kind"] == "prove":
        return [checked]
    said = f"outside the inputs the change is meant to affect (`{task['allowedChange']}`, read on the new version)" if task.get("allowedChange") else ""
    return {"verdict": checked["verdict"], "target": entry, "problem": checked["problem"], "counterexample": checked["counterexample"],
            "output": f"made up: the two versions agree {said}", "search": checked["search"], "stated": checked["stated"],
            "pair": {**checked, "target": "RegressionPair#agree"}, **({"replay": checked["replay"]} if refuted else {})}


def beside(root: Path, folder: Path, task_id: str, answer: str, job: str, status: str | None = "passed", names=None,
           trial: int | None = None, outcome: str | None = None, mutant: str | None = None, harness: str | None = None,
           harness_under: str | None = None) -> dict:
    """An answer given beside the route, as a sidecar records it, with what the pipeline and a driver leave: the job
    (naming the examples in NAMES, by default this one), its result (none when STATUS is None), the step's log and the
    collected outcome, of the answer or of OUTCOME where the two are to differ, run at the claim's bound or at TRIAL;
    and the claim file frozen in a ledger. MUTANT is the hash the step's log says the mutant's JAR had. HARNESS is the
    assumption the collected harness source returns first without (`work/harness/PropertyHarness.java`, as the checker
    writes it, or `work/pair-work/harness/` for a pair task, unless HARNESS_UNDER names the folder), where there is to
    be one. Returns the paths, relative to ROOT."""
    number, rel = folder.name[:3], folder.relative_to(root).as_posix()
    target = json.loads((folder / "target.json").read_text())
    task = next(t for t in target["tasks"] if t["id"] == task_id)
    task["besideRoute"] = {"answer": answer, "job": job, "by": "proofs/prove.py: made up", "recorded": "2026-01-02"}
    (folder / "target.json").write_text(json.dumps(target))
    claim_rel = f"{rel}/{task['claim']}"
    claim = json.loads((root / claim_rel).read_text())
    work = f"verification/.work-{number}"
    run = f"python3 {rel}/proofs/prove.py {task_id}" + (f" --max-array-length {trial}" if trial else "") + f" --timeout 60 --work {work}"
    spec = {"id": job, "links": {"examples": [number] if names is None else names}, "steps": [{"name": "the claim", "run": run}]}
    jobs = root / "verification/jobs"
    jobs.mkdir(parents=True, exist_ok=True)
    (jobs / f"{job}.json").write_text(json.dumps(spec))
    ledger = root / "llm-dlc/decisions/made-up-claims.json"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    frozen = json.loads(ledger.read_text()) if ledger.is_file() else {}
    frozen.setdefault(number, {"files": {}})["files"][claim_rel] = sha(root / claim_rel)
    ledger.write_text(json.dumps(frozen))
    paths = {"outcome": f"{work}/{task_id}/outcome.json", "result": f"verification/results/{job}/result.json",
             "log": f"verification/results/{job}/logs/1.log", "job": f"verification/jobs/{job}.json", "claim": claim_rel, "ledger": "llm-dlc/decisions/made-up-claims.json"}
    if not status:
        return paths
    (root / paths["outcome"]).parent.mkdir(parents=True, exist_ok=True)
    bound = trial or {**(claim.get("bounds") or {}), **(task.get("bounds") or {})}.get("maxArrayLength")
    (root / paths["outcome"]).write_text(json.dumps(outcome_of(task, claim, outcome or answer, bound)))
    outputs = [{"path": paths["outcome"], "change": "added", "sha256": sha(root / paths["outcome"])}]
    if harness is not None:
        under = harness_under if harness_under is not None else "pair-work/harness" if task["kind"] == "equivalence" else "harness"
        paths["harness"] = f"{work}/{task_id}/work/{under}/PropertyHarness.java"
        (root / paths["harness"]).parent.mkdir(parents=True, exist_ok=True)
        (root / paths["harness"]).write_text("public final class PropertyHarness {\n    public static void check(java.lang.String field) {\n"
                                             f"        if (!({harness})) {{ return; }} // the inputs the property is about\n"
                                             "        assert false; // made up\n    }\n}\n")
        outputs.append({"path": paths["harness"], "change": "added", "sha256": sha(root / paths["harness"])})
    (root / paths["log"]).parent.mkdir(parents=True, exist_ok=True)
    (root / paths["log"]).write_text((f"mutant: gate.jar with Gate recompiled, sha256 {mutant}: made up\n" if mutant else "") + "verdict: made up\n")
    (root / paths["result"]).write_text(json.dumps({
        "id": job, "status": status, "job": {"sha256": hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()},
        "sourceCommit": COMMIT, "jvmcontract": {"libTree": "t" * 40},
        "steps": [{"index": 1, "status": "passed", "run": run, "log": {"path": "logs/1.log", "sha256": sha(root / paths["log"])}}],
        "outputs": outputs}))
    return paths


def rewrite(root: Path, paths: dict, change, as_the_job_wrote_it: bool = True) -> None:
    """Change the outcome with CHANGE(outcome), which gets the checked property's own dict (the pair's, of an
    equivalence): as the job would have written it (the result's hash follows), or behind the job's back."""
    file = root / paths["outcome"]
    outcome = json.loads(file.read_text())
    change(outcome[0] if isinstance(outcome, list) else outcome["pair"])
    if isinstance(outcome, dict):
        outcome.update({k: outcome["pair"][k] for k in ("verdict", "search", "stated") if k in outcome["pair"]})
    file.write_text(json.dumps(outcome))
    if as_the_job_wrote_it:
        result = json.loads((root / paths["result"]).read_text())
        for o in result["outputs"]:
            if o["path"] == paths["outcome"]:
                o["sha256"] = sha(file)
        (root / paths["result"]).write_text(json.dumps(result))


class AsCommitted:
    """A source that has the job's commit: every file as it was when this was made."""

    def __init__(self, root: Path):
        self.files = {p.relative_to(root).as_posix(): p.read_bytes() for p in (root / "examples").rglob("*") if p.is_file()}

    def has(self, commit: str) -> bool:
        return commit == COMMIT

    def __call__(self, commit: str, path: str) -> bytes | None:
        return self.files.get(path)


class Checkout(unittest.TestCase):
    JOB = "20260102-000001-example-900-made-up"

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)
        self.folder = self.root / "examples/900-made-up-change"
        shutil.copytree(FIXTURES, self.folder, ignore=shutil.ignore_patterns("__pycache__"))

    def edit(self, rel: str, change) -> None:
        """Change a JSON file of the example with CHANGE(data)."""
        file = self.folder / rel
        data = json.loads(file.read_text())
        change(data)
        file.write_text(json.dumps(data))

    def bound(self, task: str, n: int) -> None:
        claim = next(t["claim"] for t in json.loads((self.folder / "target.json").read_text())["tasks"] if t["id"] == task)
        self.edit(claim, lambda c: c.update(bounds={"maxArrayLength": n}))

    def beside(self, task, answer, **how) -> dict:
        return beside(self.root, self.folder, task, answer, self.JOB, **how)

    def check(self, task, source=None) -> dict:
        return accept.check(self.root, "900", task, source)

    def refused(self, task, check, words, source=None) -> dict:
        r = self.check(task, source)
        self.assertFalse(r["accepted"], r)
        self.assertTrue(r["why"].startswith(f"{check}: "), r["why"])
        self.assertIn(words, r["why"])
        return r


class Accepted(Checkout):
    def test_an_answer_its_evidence_gives_is_accepted_and_says_what_it_rests_on(self):
        for task, answer in (("regex-probe", "refuted"), ("fixed-security", "established"), ("preservation", "established")):
            with self.subTest(task=task):
                self.beside(task, answer)
                r = self.check(task)
                self.assertTrue(r["accepted"], r.get("why"))
                self.assertEqual((r["claimed"], r["actual"]), (answer, answer))
                self.assertNotIn("why", r)
                self.assertEqual({c["status"] for c in r["checks"]}, {accept.OK})
                self.assertIn("replay" if answer == "refuted" else "non-vacuous", [c["check"] for c in r["checks"]])
                self.assertEqual(r["restsOn"], ["made up: what the checker assumed"], "the checker's own assumptions, not the claim's")
                self.assertTrue(any("recorded no artifact identities" in limit for limit in r["limits"]), r["limits"])
                self.assertEqual(r["identity"]["sourceCommit"], COMMIT)

    def test_a_task_with_no_answer_beside_the_route_has_nothing_to_accept(self):
        r = self.check("regex-probe")
        self.assertFalse(r["accepted"])
        self.assertIn("no answer beside the route", r["why"])
        self.assertEqual(accept.tasks_beside(self.root, "900"), [])
        self.beside("regex-probe", "refuted")
        self.assertEqual(accept.tasks_beside(self.root, "900"), ["regex-probe"])

    def test_the_command_lists_each_answer_and_fails_when_one_is_refused(self):
        import contextlib
        import io
        self.beside("regex-probe", "refuted")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = accept.main(["900"], self.root)
        self.assertEqual(code, 0, out.getvalue())
        self.assertIn("✓ 900 regex-probe: refuted, accepted", out.getvalue())
        self.assertEqual(out.getvalue().count("limit: the driver recorded no artifact identities"), 1, "a limit is said once")
        self.edit("target.json", lambda t: next(x for x in t["tasks"] if x["id"] == "regex-probe")["besideRoute"].update(answer="established"))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = accept.main(["900", "--json"], self.root)
        self.assertEqual(code, 1)
        self.assertEqual([(r["task"], r["accepted"], r["actual"]) for r in json.loads(out.getvalue())], [("regex-probe", False, "refuted")])


class WrongConclusion(Checkout):
    """The control the old rule failed: a passed job that names the example supported either answer."""

    def test_the_other_answer_is_refused_on_the_same_passed_job(self):
        self.beside("regex-probe", "refuted")
        self.assertTrue(self.check("regex-probe")["accepted"])
        self.edit("target.json", lambda t: next(x for x in t["tasks"] if x["id"] == "regex-probe")["besideRoute"].update(answer="established"))
        r = self.refused("regex-probe", "conclusion", "the outcome's verdict is violation (refuted), and the answer recorded is established")
        self.assertEqual(r["actual"], "refuted")

    def test_an_outcome_with_no_verdict_supports_no_answer(self):
        for answer in ("established", "refuted"):
            self.beside("regex-probe", answer, outcome="unknown")
            self.assertEqual(self.refused("regex-probe", "conclusion", "unverifiable (unknown)")["actual"], "unknown")

    def test_one_job_of_several_tasks_gives_each_task_its_own_steps_outcome(self):
        a = self.beside("regex-probe", "refuted")
        self.beside("fixed-security", "established")
        # One job ran both: its result has both steps and both outcomes.
        spec = json.loads((self.root / a["job"]).read_text())
        both = json.loads((self.root / a["result"]).read_text())
        first_run = f"python3 examples/900-made-up-change/proofs/prove.py regex-probe --timeout 60 --work verification/.work-900"
        spec["steps"].insert(0, {"name": "the probe", "run": first_run})
        (self.root / a["job"]).write_text(json.dumps(spec))
        both["job"]["sha256"] = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()
        both["steps"].insert(0, {"index": 0, "status": "passed", "run": first_run, "log": {"path": "logs/1.log", "sha256": sha(self.root / a["log"])}})
        both["outputs"].append({"path": a["outcome"], "change": "added", "sha256": sha(self.root / a["outcome"])})
        (self.root / a["result"]).write_text(json.dumps(both))
        self.assertTrue(self.check("regex-probe")["accepted"], self.check("regex-probe").get("why"))
        self.assertTrue(self.check("fixed-security")["accepted"], self.check("fixed-security").get("why"))
        # And an answer flipped on one of them is refused, the other's passing step notwithstanding.
        self.edit("target.json", lambda t: next(x for x in t["tasks"] if x["id"] == "fixed-security")["besideRoute"].update(answer="refuted"))
        self.refused("fixed-security", "conclusion", "verified (established)")


class MissingResult(Checkout):
    def test_no_result_a_failed_job_or_a_job_of_another_example_is_refused(self):
        for how, check, words in (({"status": None}, "job", "no result of job"), ({"status": "failed"}, "job", "ended failed, not passed"),
                                  ({"names": ["950"]}, "job", "does not name example 900")):
            with self.subTest(how=how):
                shutil.rmtree(self.root / "verification", ignore_errors=True)
                self.beside("regex-probe", "refuted", **how)
                self.refused("regex-probe", check, words)

    def test_a_job_that_never_ran_this_task_is_refused(self):
        paths = self.beside("regex-probe", "refuted")
        self.edit("target.json", lambda t: next(x for x in t["tasks"] if x["id"] == "fixed-security").update(
            besideRoute={"answer": "established", "job": self.JOB, "by": "made up", "recorded": "2026-01-02"}))
        self.refused("fixed-security", "step", "no passed step of job")
        self.assertTrue((self.root / paths["outcome"]).is_file())

    def test_an_outcome_that_is_gone_or_was_never_collected_is_refused(self):
        paths = self.beside("regex-probe", "refuted")
        (self.root / paths["outcome"]).unlink()
        self.refused("regex-probe", "outcome", "is not in this checkout")
        paths = self.beside("regex-probe", "refuted")
        result = json.loads((self.root / paths["result"]).read_text())
        result["outputs"] = []
        (self.root / paths["result"]).write_text(json.dumps(result))
        self.refused("regex-probe", "outcome", "is not among job")

    def test_a_refutation_whose_witness_did_not_reproduce_or_is_missing_is_refused(self):
        paths = self.beside("regex-probe", "refuted")
        rewrite(self.root, paths, lambda o: o.update(replay={"by": "jvm", "reproduced": False}))
        self.refused("regex-probe", "replay", "was not reproduced on a JVM")
        rewrite(self.root, paths, lambda o: o.pop("replay"))
        self.refused("regex-probe", "replay", "not recorded")
        rewrite(self.root, paths, lambda o: o.update(counterexample=None))
        self.refused("regex-probe", "replay", "no witness")

    def test_an_establishment_that_is_vacuous_incomplete_or_under_another_mode_is_refused(self):
        for change, check, words in (
                (lambda o: o["stated"].update(vacuity={"status": "vacuous"}), "non-vacuous", "names no input that reaches the property"),
                (lambda o: o["stated"].update(vacuity={}), "non-vacuous", "not recorded"),
                (lambda o: o["stated"]["bounds"].update(complete=False), "complete", "does not say the bounds are complete"),
                (lambda o: o["search"].update(gap_mode="assume"), "mode", "gap mode assume where the task says strict"),
                (lambda o: o["search"].update(engine="jbmc"), "mode", "engine jbmc where the task says native")):
            with self.subTest(words=words):
                paths = self.beside("fixed-security", "established")
                rewrite(self.root, paths, change)
                self.refused("fixed-security", check, words)


class ChangedArtifact(Checkout):
    def test_a_preservation_whose_witness_is_not_said_to_lie_outside_the_allowed_change_is_refused(self):
        """A pair's versions are compared only outside the allowed change: a witness inside it reaches no comparison, so
        an establishment is accepted only when its outcome says its witness lies outside the task's change."""
        for change, check, words in (
                (lambda o: o["stated"]["vacuity"].pop("outside"), "non-vacuous", "does not say whether its witness"),
                (lambda o: o["stated"]["vacuity"].update(outside="true"), "non-vacuous", "which is not the task's allowed change"),
                (lambda o: o["stated"].update(vacuity={"status": "vacuous", "text": "inside the allowed change"}), "non-vacuous", "names no input that reaches the property")):
            with self.subTest(words=words):
                paths = self.beside("preservation", "established")
                self.assertTrue(self.check("preservation")["accepted"])
                rewrite(self.root, paths, change)
                self.refused("preservation", check, words)

    def test_an_outcome_changed_after_the_job_is_refused(self):
        paths = self.beside("regex-probe", "refuted")
        rewrite(self.root, paths, lambda o: o.update(verdict="verified"), as_the_job_wrote_it=False)
        self.refused("regex-probe", "outcome", "is not the file the job wrote")

    def test_a_job_file_changed_after_its_result_is_refused(self):
        paths = self.beside("regex-probe", "refuted")
        spec = json.loads((self.root / paths["job"]).read_text())
        spec["steps"][0]["run"] += " --max-array-length 2"
        (self.root / paths["job"]).write_text(json.dumps(spec))
        self.refused("regex-probe", "job", "is not the one its result is of")

    def test_a_claim_file_changed_after_it_was_frozen_or_run_is_refused(self):
        self.beside("regex-probe", "refuted")
        committed = AsCommitted(self.root)
        self.assertTrue(self.check("regex-probe", committed)["accepted"])
        self.edit("claims/regex-probe.json", lambda c: c.update(statement="made weaker afterwards"))
        self.refused("regex-probe", "claim", "is not the claim frozen")
        # With no ledger, the bytes the job ran at its commit are what the file is held to.
        (self.root / "llm-dlc/decisions/made-up-claims.json").unlink()
        self.refused("regex-probe", "claim", f"is not the file the job ran at {COMMIT[:12]}", committed)
        # With neither, nothing says which claim the job was about.
        self.refused("regex-probe", "claim", "is in no ledger of frozen claims")

    def test_an_expression_or_an_allowed_change_that_is_not_the_claims_is_refused(self):
        paths = self.beside("regex-probe", "refuted")
        rewrite(self.root, paths, lambda o: o.update({"assert": "true"}))
        self.refused("regex-probe", "expressions", "the outcome's assert is not the claim file's")
        paths = self.beside("preservation", "established")
        self.assertTrue(self.check("preservation")["accepted"])
        self.edit("target.json", lambda t: next(x for x in t["tasks"] if x["id"] == "preservation").update(allowedChange="true"))
        self.refused("preservation", "expressions", "the allowed change the outcome says it ran is not the task's")

    def test_the_generated_pair_is_what_says_the_allowed_change_where_the_job_collected_it(self):
        paths = self.beside("preservation", "established")
        pair = self.root / "verification/.work-900/preservation/work/pair/RegressionPair.java"
        pair.parent.mkdir(parents=True)
        pair.write_text("static boolean meantToChange(int code) { return code == 97; }")
        result = json.loads((self.root / paths["result"]).read_text())
        result["outputs"].append({"path": pair.relative_to(self.root).as_posix(), "change": "added", "sha256": sha(pair)})
        (self.root / paths["result"]).write_text(json.dumps(result))
        r = self.check("preservation")
        self.assertTrue(r["accepted"], r.get("why"))
        self.assertIn("in the generated pair", next(c["detail"] for c in r["checks"] if c["check"] == "expressions"))
        self.edit("target.json", lambda t: next(x for x in t["tasks"] if x["id"] == "preservation").update(allowedChange="code >= 0"))
        self.refused("preservation", "expressions", "the allowed change in the generated pair")

    def test_an_outcome_about_another_entry_is_refused(self):
        paths = self.beside("regex-probe", "refuted")
        rewrite(self.root, paths, lambda o: o.update(target="fixture.Other#allowed"))
        self.refused("regex-probe", "entry", "fixture.Other#allowed")
        # An adapter entry counts when the task's invocation names it.
        self.edit("target.json", lambda t: next(x for x in t["tasks"] if x["id"] == "regex-probe").update(
            invocation={"how": "adapter", "checked": "2026-01-02", "evidence": "made up", "entry": "fixture.Other#allowed(Ljava/lang/String;)Z, made up"}))
        self.assertTrue(self.check("regex-probe")["accepted"])

    def test_an_outcome_naming_an_overload_by_the_descriptors_types_is_about_the_tasks_target(self):
        """The checker names one of several overloads with its parameter types (example 307's
        `BCrypt#hashpw(java.lang.String, java.lang.String)`): that is the task's target when the types are its
        descriptor's, and another method when they are not."""
        paths = self.beside("regex-probe", "refuted")  # target fixture.RegexGate#allowed(Ljava/lang/String;)Z
        for same in ("fixture.RegexGate#allowed", "fixture.RegexGate#allowed(java.lang.String)",
                     "fixture.RegexGate#allowed( java.lang.String )"):
            with self.subTest(same=same):
                rewrite(self.root, paths, lambda o: o.update(target=same))
                r = self.check("regex-probe")
                self.assertTrue(r["accepted"], r.get("why"))
        for other in ("fixture.RegexGate#allowed(int)", "fixture.RegexGate#allowed(String)",
                      "fixture.RegexGate#allowed(java.lang.String, int)", "fixture.RegexGate#allowed()",
                      "fixture.RegexGate#allowed(java.lang.String[])", "fixture.RegexGate#allowedTwice(java.lang.String)",
                      "fixture.Other#allowed(java.lang.String)", "fixture.RegexGate#allowed(java.lang.String"):
            with self.subTest(other=other):
                rewrite(self.root, paths, lambda o: o.update(target=other))
                self.refused("regex-probe", "entry", other)

    def test_a_task_or_an_adapter_that_is_not_what_the_job_ran_is_refused(self):
        (self.folder / "replay").mkdir(exist_ok=True)
        (self.folder / "replay/Adapter.java").write_text("class Adapter {}\n")
        self.edit("target.json", lambda t: t["preparation"].update(adapters=["replay/Adapter.java"]))
        self.beside("fixed-security", "established")
        committed = AsCommitted(self.root)
        r = self.check("fixed-security", committed)
        self.assertTrue(r["accepted"], r.get("why"))
        self.assertFalse(any("is not in this checkout" in limit for limit in r["limits"]), "the commit is there: nothing left uncompared")
        # An adapter source listed since, for another claim's entry, is not one the job compiled: the answer stands, and
        # the check says so. The sources it did compile are still compared.
        (self.folder / "replay/Other.java").write_text("class Other {}\n")
        self.edit("target.json", lambda t: t["preparation"].update(adapters=["replay/Adapter.java", "replay/Other.java"]))
        r = self.check("fixed-security", committed)
        self.assertTrue(r["accepted"], r.get("why"))
        self.assertIn("1 listed since, which the job did not compile: replay/Other.java", next(c["detail"] for c in r["checks"] if c["check"] == "task"))
        (self.folder / "replay/Adapter.java").write_text("class Adapter { /* changed */ }\n")
        self.refused("fixed-security", "task", "the adapter is not the one the job compiled", committed)
        committed = AsCommitted(self.root)
        self.edit("target.json", lambda t: next(x for x in t["tasks"] if x["id"] == "fixed-security").update(gaps="assume", expected="refuted"))
        self.refused("fixed-security", "task", "expected, gaps", committed)

    def test_a_mutant_whose_jar_is_not_the_replays_or_is_in_no_record_is_refused(self):
        replayed, other = "a" * 64, "b" * 64
        self.edit("target.json", lambda t: t["history"]["revisions"].update(mutant={"mutant": {"base": "after", "patch": "p", "sha256": "0" * 64, "description": "made up"}}))
        receipt = self.folder / "receipts/mutant-replay/1/result.json"
        receipt.parent.mkdir(parents=True)
        receipt.write_text(json.dumps({"claim": {"target": {"dependencies": [{"revision": "mutant", "role": "original", "sha256": replayed}]}}}))
        self.beside("mutant-security", "refuted", mutant=replayed)
        r = self.check("mutant-security")
        self.assertTrue(r["accepted"], r.get("why"))
        self.beside("mutant-security", "refuted", mutant=other)
        self.refused("mutant-security", "mutant", "is not the one the mutant replay ran")
        self.beside("mutant-security", "refuted")
        self.refused("mutant-security", "mutant", "its hash is in no record")
        # A task of a revision that is not constructed has no such check.
        self.beside("fixed-security", "established")
        self.assertNotIn("mutant", [c["check"] for c in self.check("fixed-security")["checks"]])


class TrialBound(Checkout):
    def test_a_proof_at_a_smaller_bound_does_not_establish_the_claim(self):
        self.bound("fixed-security", 8)
        self.beside("fixed-security", "established")
        r = self.check("fixed-security")
        self.assertTrue(r["accepted"], r.get("why"))
        self.assertEqual((r["bound"]["claim"], r["bound"]["ran"], r["bound"]["trialFlags"]), (8, 8, []))
        self.beside("fixed-security", "established", trial=6)
        r = self.refused("fixed-security", "domain", "a proof at bound 6 establishes nothing about the claim's bound 8: a trial run")
        self.assertEqual(r["bound"]["trialFlags"], ["--max-array-length"])

    def test_the_frozen_step_is_taken_where_a_job_ran_a_trial_first(self):
        self.bound("fixed-security", 8)
        paths = self.beside("fixed-security", "established")
        spec, result = json.loads((self.root / paths["job"]).read_text()), json.loads((self.root / paths["result"]).read_text())
        trial = spec["steps"][0]["run"].replace(" --timeout", " --max-array-length 6 --timeout").replace(".work-900", ".work-900/trial")
        spec["steps"].insert(0, {"name": "a trial", "run": trial})
        (self.root / paths["job"]).write_text(json.dumps(spec))
        result["job"]["sha256"] = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()
        result["steps"].insert(0, {"index": 0, "status": "passed", "run": trial, "log": result["steps"][0]["log"]})
        (self.root / paths["result"]).write_text(json.dumps(result))
        r = self.check("fixed-security")
        self.assertTrue(r["accepted"], r.get("why"))
        self.assertEqual(r["bound"]["ran"], 8)

    def test_a_witness_found_at_a_smaller_bound_refutes_the_claim_and_one_outside_its_domain_does_not(self):
        self.bound("regex-probe", 8)
        self.beside("regex-probe", "refuted", trial=3)
        r = self.check("regex-probe")
        self.assertTrue(r["accepted"], r.get("why"))
        self.assertIn("the witness lies in the claim's domain", next(c["detail"] for c in r["checks"] if c["check"] == "domain"))
        paths = self.beside("regex-probe", "refuted", trial=12)
        rewrite(self.root, paths, lambda o: o["counterexample"]["inputs"][0]["value"].update(units=list(range(10))))
        self.refused("regex-probe", "domain", "the witness holds a value of length 10, outside the claim's bound 8")

    def test_a_claim_with_no_bound_is_held_to_a_step_that_overrides_none(self):
        self.beside("fixed-security", "established")
        self.assertTrue(self.check("fixed-security")["accepted"])
        self.beside("fixed-security", "established", trial=4)
        self.refused("fixed-security", "domain", "the step overrides one (--max-array-length)")

    def test_the_parameters_that_may_be_null_are_the_claims(self):
        paths = self.beside("regex-probe", "refuted")
        rewrite(self.root, paths, lambda o: o["stated"]["domain"].update(parameters=[{"name": "field", "null": True}]))
        self.refused("regex-probe", "domain", "the parameters that may be null (field) are not the claim's (none)")


class DriverRecord(Checkout):
    """evidence.json, which a driver writes beside the outcome with `accept.record`."""

    def recorded(self, task="fixed-security", answer="established", trial=False, jar=b"the pinned JAR"):
        jars = self.root / "jars"
        jars.mkdir(exist_ok=True)
        (jars / "gate-1.0.jar").write_bytes(jar)
        self.edit("target.json", lambda t: t["preparation"].update(
            artifacts=[{"revision": "after", "coordinates": "made:gate:1.0", "url": "https://repo.example/gate-1.0.jar",
                        "sha256": hashlib.sha256(b"the pinned JAR").hexdigest()}], adapters=["replay/Adapter.java"]))
        (self.folder / "replay").mkdir(exist_ok=True)
        (self.folder / "replay/Adapter.java").write_text("class Adapter {}\n")
        (self.folder / "proofs").mkdir(exist_ok=True)
        (self.folder / "proofs/prove.py").write_text("# made up\n")
        paths = self.beside(task, answer)
        work = (self.root / paths["outcome"]).parent
        classes = work / "adapter-after"
        classes.mkdir(exist_ok=True)
        (classes / "Adapter.class").write_bytes(b"\xca\xfe\xba\xbe")
        written = accept.record(work, example="900", task=task, claim_file=self.root / paths["claim"],
                                bound={"maxArrayLength": None, "unwind": 16, "trial": trial},
                                artifacts=[{"revision": "after", "name": "gate-1.0.jar", "sha256": sha(jars / "gate-1.0.jar")}],
                                adapter_sources=[self.folder / "replay/Adapter.java"], adapter_classes=[classes],
                                jvmcontract=str(jars / "gate-1.0.jar"), driver=self.folder / "proofs/prove.py", root=self.root)
        result = json.loads((self.root / paths["result"]).read_text())
        result["outputs"].append({"path": written.relative_to(self.root).as_posix(), "change": "added", "sha256": sha(written)})
        (self.root / paths["result"]).write_text(json.dumps(result))
        return paths

    def test_recorded_identities_that_are_the_pinned_ones_leave_no_limit(self):
        self.recorded()
        r = self.check("fixed-security")
        self.assertTrue(r["accepted"], r.get("why"))
        self.assertIn("artifacts", [c["check"] for c in r["checks"]])
        self.assertFalse(any("recorded no artifact identities" in limit for limit in r["limits"]), r["limits"])
        self.assertEqual(r["identity"]["jvmcontract"]["sha256"], hashlib.sha256(b"the pinned JAR").hexdigest())
        evidence = json.loads((self.root / "verification/.work-900/fixed-security/evidence.json").read_text())
        self.assertEqual(evidence["claim"]["file"], "examples/900-made-up-change/claims/gate-security.json")
        self.assertEqual(list(evidence["adapter"]["sources"]), ["examples/900-made-up-change/replay/Adapter.java"])

    def test_a_jar_that_is_not_the_pinned_one_a_trial_or_a_changed_adapter_is_refused(self):
        self.recorded(jar=b"another JAR")
        self.refused("fixed-security", "artifacts", "gate-1.0.jar of after is not the JAR target.json pins")
        self.recorded(trial=True)
        self.refused("fixed-security", "artifacts", "it marks the run a trial")
        self.recorded()
        (self.folder / "replay/Adapter.java").write_text("class Adapter { /* changed */ }\n")
        self.refused("fixed-security", "artifacts", "the adapter source examples/900-made-up-change/replay/Adapter.java is not the one it compiled")

    def test_a_constructed_mutants_closure_is_held_to_its_bases_pins(self):
        """A mutant's class path is its base's with its own JAR built: the driver records the rest under the mutant's
        revision, and they are the JARs the base pins."""
        self.edit("target.json", lambda t: t["history"]["revisions"].update(
            mutant={"mutant": {"base": "after", "patch": "p", "sha256": "0" * 64, "description": "made up"}}))
        for jar, status in ((b"the pinned JAR", "ok"), (b"another JAR", "fail")):
            paths = self.recorded("mutant-security", "refuted", jar=jar)
            file = self.root / "verification/.work-900/mutant-security/evidence.json"
            data = json.loads(file.read_text())
            data["artifacts"] = [{"revision": "mutant", "name": "built.jar", "sha256": "1" * 64, "constructed": True},
                                 *({**a, "revision": "mutant"} for a in data["artifacts"])]
            file.write_text(json.dumps(data))
            result = json.loads((self.root / paths["result"]).read_text())
            next(o for o in result["outputs"] if o["path"].endswith("/evidence.json"))["sha256"] = sha(file)
            (self.root / paths["result"]).write_text(json.dumps(result))
            [artifacts] = [c for c in self.check("mutant-security")["checks"] if c["check"] == "artifacts"]
            self.assertEqual(artifacts["status"], status, artifacts["detail"])
        self.assertIn("gate-1.0.jar of mutant is not the JAR target.json pins", artifacts["detail"])

    def test_a_driver_that_is_not_the_one_at_the_jobs_commit_is_refused(self):
        """The record names the driver that ran; at the job's source commit the driver at that path is another."""
        self.recorded()
        committed = AsCommitted(self.root)
        self.assertTrue(self.check("fixed-security", committed)["accepted"], self.check("fixed-security", committed).get("why"))
        committed.files["examples/900-made-up-change/proofs/prove.py"] = b"# another driver\n"
        self.refused("fixed-security", "artifacts", "is not examples/900-made-up-change/proofs/prove.py at the source commit", committed)

    def test_a_record_changed_after_the_job_or_of_another_task_is_refused(self):
        self.recorded()
        file = self.root / "verification/.work-900/fixed-security/evidence.json"
        data = json.loads(file.read_text())
        file.write_text(json.dumps({**data, "task": "regex-probe"}))
        self.refused("fixed-security", "artifacts", "is not the file the job wrote")


def task_of(t: dict, task_id: str) -> dict:
    return next(x for x in t["tasks"] if x["id"] == task_id)


class Countermodels(Checkout):
    """The challenge stream's controls of this check (lib/tests/fixtures/accept-countermodels/README.md, `zwrpkwnl`):
    evidence the check once accepted for an answer the evidence does not give. Each failed before the check was
    tightened; beside each, the evidence of the same kind that is still accepted."""

    def test_an_outcome_about_another_method_whose_name_the_entry_contains_is_refused(self):
        """The entry was matched as a substring of the invocation's entry, so an outcome about `GateAdapter#allowed`
        stood in for one about `GateAdapter#allowedTwice`: the same expressions over other code."""
        paths = self.beside("regex-probe", "refuted")
        self.edit("target.json", lambda t: task_of(t, "regex-probe").update(invocation={
            "how": "adapter", "checked": "2026-01-02", "evidence": "made up",
            "entry": "fixture.adapter.GateAdapter#allowedTwice(Ljava/lang/String;)Z, made up"}))
        rewrite(self.root, paths, lambda o: o.update(target="fixture.adapter.GateAdapter#allowedTwice"))
        self.assertTrue(self.check("regex-probe")["accepted"], "the entry the task names")
        for other in ("fixture.adapter.GateAdapter#allowed", "adapter.GateAdapter#allowedTwice", "GateAdapter#allowed"):
            with self.subTest(other=other):
                rewrite(self.root, paths, lambda o: o.update(target=other))
                self.refused("regex-probe", "entry", other)

    def test_an_outcome_about_a_method_an_assumption_mentions_is_refused_and_the_adapter_entry_it_names_is_not(self):
        """A method the claim's assumptions name in passing (how the input is read) is not the entry. One an assumption
        names as the adapter entry is: 286's and 287's tasks have no invocation entry and name theirs so."""
        paths = self.beside("regex-probe", "refuted")
        self.edit("claims/regex-probe.json", lambda c: c.update(assumptions=[
            {"text": "the field is read by fixture.RegexGate#field from the request, made up"},
            {"text": "the parameters are those of the adapter entry fixture.adapter.GateAdapter#allowed(Ljava/lang/String;)Z: made up"}]))
        self.beside("regex-probe", "refuted")  # the ledger freezes the edited claim
        rewrite(self.root, paths, lambda o: o.update(target="fixture.RegexGate#field"))
        self.refused("regex-probe", "entry", "fixture.RegexGate#field")
        rewrite(self.root, paths, lambda o: o.update(target="fixture.adapter.GateAdapter#allowed"))
        self.assertTrue(self.check("regex-probe")["accepted"], self.check("regex-probe").get("why"))

    def test_a_step_that_ran_a_driver_at_another_path_is_refused(self):
        """Any word that ended in proofs/prove.py and contained the example's folder was taken: a driver of another
        checkout, which the identity then named as this commit's, or no driver run at all. `python3 -I` is a run."""
        for run, taken in (("python3 /elsewhere/examples/900-made-up-change/proofs/prove.py fixed-security --timeout 60 --work verification/.work-900", False),
                           ("echo examples/900-made-up-change/proofs/prove.py fixed-security --work verification/.work-900", False),
                           ("python3 -I examples/900-made-up-change/proofs/prove.py fixed-security --timeout 60 --work verification/.work-900", True)):
            with self.subTest(run=run):
                paths = self.beside("fixed-security", "established")
                spec = json.loads((self.root / paths["job"]).read_text())
                result = json.loads((self.root / paths["result"]).read_text())
                spec["steps"][0]["run"] = result["steps"][0]["run"] = run
                (self.root / paths["job"]).write_text(json.dumps(spec))
                result["job"]["sha256"] = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()
                (self.root / paths["result"]).write_text(json.dumps(result))
                if taken:
                    self.assertTrue(self.check("fixed-security")["accepted"], self.check("fixed-security").get("why"))
                else:
                    self.refused("fixed-security", "step", "prove.py")

    def test_a_refutation_whose_witness_is_null_where_the_claim_says_not_null_is_refused(self):
        """The domain check compared the outcome's stated nullable parameters with the claim's, never the witness's
        values: a witness with field null refuted a claim over non-null fields only, which it lies outside."""
        paths = self.beside("regex-probe", "refuted")
        rewrite(self.root, paths, lambda o: o.update(counterexample={"input": "allowed(field=null)", "inputs": [
            {"name": "field", "type": "java.lang.String", "value": None}]}))
        self.refused("regex-probe", "domain", "null")
        self.edit("claims/regex-probe.json", lambda c: c.update(nullable=["field"]))
        self.beside("regex-probe", "refuted")
        rewrite(self.root, paths, lambda o: o.update(counterexample={"input": "allowed(field=null)", "inputs": [
            {"name": "field", "type": "java.lang.String", "value": None}]}))
        self.assertTrue(self.check("regex-probe")["accepted"], self.check("regex-probe").get("why"))

    def test_a_refutation_whose_witness_the_claims_assumption_excludes_is_left_unbound(self):
        """A replay that reproduced the assertion's failure said nothing of whether the input was assumed: a witness of
        length 2 refuted a claim about length 3 only. What says it is the harness the JVM ran, which returns first
        where the assumption does not hold; with no such source collected, or one that does not return first, nothing
        does."""
        self.edit("claims/regex-probe.json", lambda c: c.update(assume="field.length() == 3"))
        self.beside("regex-probe", "refuted")
        r = self.check("regex-probe")
        self.assertFalse(r["accepted"], "witness allowed(field=\"ab\") is outside `field.length() == 3`, and no record says it is inside")
        self.assertIn(("replay", accept.UNBOUND), [(c["check"], c["status"]) for c in r["checks"]])
        self.assertIn("collected no harness source", r["why"])
        self.beside("regex-probe", "refuted", harness="field != null")
        self.refused("regex-probe", "replay", "does not return first where `field.length() == 3` does not hold")
        self.beside("regex-probe", "refuted", harness="field.length() == 3")
        r = self.check("regex-probe")
        self.assertTrue(r["accepted"], r.get("why"))
        self.assertIn("returns before the call where the assumption does not hold", next(c["detail"] for c in r["checks"] if c["check"] == "replay"))

    def test_a_pair_tasks_harness_is_the_one_under_pair_work(self):
        """A pair task's job collects the harness the JVM ran under `work/pair-work/harness/` (example 307's
        mutant-preservation), not `work/harness/`: the check reads it there, with the same hash and predicate checks,
        and a pair's outcome with a harness only where a prove run's would be has no record of the assumption."""
        self.edit("claims/gate-preservation.json", lambda c: c.update(assume="field.length() == 2"))
        self.edit("target.json", lambda t: task_of(t, "preservation").update(expected="refuted"))
        self.beside("preservation", "refuted")
        self.refused("preservation", "replay", "collected no harness source (verification/.work-900/preservation/work/pair-work/harness/")
        self.beside("preservation", "refuted", harness="field.length() == 2", harness_under="harness")
        self.refused("preservation", "replay", "collected no harness source")
        self.beside("preservation", "refuted", harness="field != null")
        self.refused("preservation", "replay", "does not return first where `field.length() == 2` does not hold")
        paths = self.beside("preservation", "refuted", harness="field.length() == 2")
        r = self.check("preservation")
        self.assertTrue(r["accepted"], r.get("why"))
        self.assertIn("pair-work/harness/PropertyHarness.java", next(c["detail"] for c in r["checks"] if c["check"] == "replay"))
        (self.root / paths["harness"]).write_text("changed after the job\n")
        self.refused("preservation", "replay", "collected no harness source")
        # A prove task still reads its own: work/harness/, not a pair's folder.
        self.edit("claims/regex-probe.json", lambda c: c.update(assume="field.length() == 2"))
        self.beside("regex-probe", "refuted", harness="field.length() == 2", harness_under="pair-work/harness")
        self.refused("regex-probe", "replay", "collected no harness source (verification/.work-900/regex-probe/work/harness/")
        self.beside("regex-probe", "refuted", harness="field.length() == 2")
        self.assertTrue(self.check("regex-probe")["accepted"])

    def test_a_pair_run_with_an_allowed_change_the_task_does_not_allow_is_refused(self):
        """The expressions check asked nothing of the pair when the task allows no change, so a pair that ran with
        `code == 97` established `preservation` everywhere, where the versions differ at 97. The generated pair, where
        the job collected it, says so as well."""
        paths = self.beside("preservation", "established")
        self.edit("target.json", lambda t: task_of(t, "preservation").pop("allowedChange"))
        self.assertIn("meant to affect (`code == 97`", json.loads((self.root / paths["outcome"]).read_text())["output"])
        self.refused("preservation", "expressions", "code == 97")
        pair = self.root / "verification/.work-900/preservation/work/pair/RegressionPair.java"
        pair.parent.mkdir(parents=True)
        pair.write_text("static boolean meantToChange(int code) { return code == 97; }")
        result = json.loads((self.root / paths["result"]).read_text())
        result["outputs"].append({"path": pair.relative_to(self.root).as_posix(), "change": "added", "sha256": sha(pair)})
        (self.root / paths["result"]).write_text(json.dumps(result))
        self.refused("preservation", "expressions", "skips the inputs of an allowed change")

    def test_a_task_bound_below_the_claims_does_not_establish_the_claim(self):
        """`want` was the claim's bound overridden by the task's, so a task that lowered it to 2 made a proof at 2 the
        claim's bound of 8: the trial-bound control by another route."""
        self.bound("fixed-security", 8)
        self.edit("target.json", lambda t: task_of(t, "fixed-security").update(bounds={"maxArrayLength": 2}))
        self.beside("fixed-security", "established")
        self.refused("fixed-security", "domain", "8")


class StepsPastTheFix(Checkout):
    """The challenge stream's controls of the step check past `kqxwrwrx` (lib/tests/fixtures/accept-countermodels/
    README.md, 'Past the fix', `xnqlyxnw`): a job whose step ran the example's driver and did something else besides,
    or ran it on something else. The pipeline runs a step with `bash -c`, and evidence.json does not hash the outcome,
    so only a job every step of which is a plain driver run leaves an outcome the driver alone wrote. Each failed while
    the check read a step's words only up to the task's name and the first `--work`; beside them, the honest jobs'
    shapes that are still accepted."""

    DRIVER = "examples/900-made-up-change/proofs/prove.py"
    WORK = "verification/.work-900"
    recorded = DriverRecord.recorded  # with evidence.json, so that an accepted answer has no limit

    def steps(self, runs: list[str], build: bool = False, **job) -> None:
        """The job's steps are RUNS, each passed, the last one's log the step's log, and the result records the job
        as the runner read it; BUILD puts the pipeline's own build of the checker first, as step 0."""
        spec = json.loads((self.root / self.paths["job"]).read_text())
        result = json.loads((self.root / self.paths["result"]).read_text())
        log = result["steps"][0]["log"]
        spec.pop("env", None)
        spec.update(job)
        spec["steps"] = [{"name": f"step {i}", "run": run} for i, run in enumerate(runs, 1)]
        result["steps"] = [{"index": i, "status": "passed", "run": run, "log": log} for i, run in enumerate(runs, 1)]
        if build:
            result["steps"].insert(0, {"index": 0, "status": "passed", "log": log,
                                       "run": "/opt/rust/bin/cargo build --release --manifest-path lib/Cargo.toml"})
        (self.root / self.paths["job"]).write_text(json.dumps(spec))
        result["job"]["sha256"] = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()
        (self.root / self.paths["result"]).write_text(json.dumps(result))

    def setUp(self):
        super().setUp()
        self.paths = self.recorded()
        self.driver = f"python3 {self.DRIVER} fixed-security --timeout 60 --work {self.WORK}"
        self.committed = AsCommitted(self.root)  # the job's source commit is this checkout as it is

    def accepted(self, runs: list[str], **how) -> None:
        self.steps(runs, **how)
        r = self.check("fixed-security", self.committed)
        self.assertTrue(r["accepted"], r.get("why"))
        self.assertEqual(r["limits"], [], "the evidence an honest job leaves")

    def refused_for(self, runs: list[str], words: str, **how) -> None:
        self.steps(runs, **how)
        self.refused("fixed-security", "step", words, self.committed)

    def test_the_honest_jobs_shapes_are_accepted(self):
        """The 13 accepted answers' jobs: the pipeline's build first, driver runs of the example's tasks with
        --timeout and one --work, `python3 -I`, a trial in a folder of its own before the frozen run, and in one job
        the drivers of two examples."""
        other = "python3 examples/901-another-change/proofs/prove.py fixed-security --timeout 60 --work verification/.work-901"
        for runs, how in (([self.driver], {"build": True}),
                          ([f"python3 {self.DRIVER} regex-probe --timeout 60 --work {self.WORK}", self.driver.replace("python3", "python3 -I")], {}),
                          ([f"python3 {self.DRIVER} fixed-security --max-array-length 2 --timeout 60 --work {self.WORK}/trial", self.driver], {}),
                          ([other, self.driver, other], {"build": True})):
            with self.subTest(runs=runs):
                self.accepted(runs, **how)

    def test_a_step_that_goes_on_past_the_driver_in_the_shell_is_refused(self):
        """What follows a `;` or a `&&` runs after the driver and can write the outcome it collected."""
        for after in (f" ; cp verification/forged.json {self.WORK}/fixed-security/outcome.json",
                      f" && sed -i s/violation/verified/ {self.WORK}/fixed-security/outcome.json",
                      f";cp verification/forged.json {self.WORK}/fixed-security/outcome.json",
                      " $(cp verification/forged.json x)", "\ncp verification/forged.json x"):
            with self.subTest(after=after):
                self.refused_for([self.driver + after], "not a plain driver run")

    def test_a_step_before_or_after_the_driver_that_is_not_a_driver_run_is_refused(self):
        """A job's earlier step can replace the driver in the job's checkout, which then writes evidence.json naming
        the source commit's driver hash, or write the outcome folder itself; a later one can rewrite it."""
        for runs in ([f"cp /elsewhere/prove.py {self.DRIVER}", self.driver],
                     [f"cp -r verification/forged/. {self.WORK}", self.driver],
                     [self.driver, f"cp verification/forged.json {self.WORK}/fixed-security/outcome.json"]):
            with self.subTest(runs=runs):
                self.refused_for(runs, "is not a plain driver run")

    def test_a_later_driver_run_into_the_same_outcome_folder_is_refused(self):
        """The outcome collected is the last one written there: a trial after the frozen run, or another example's
        driver on a task of the same name, leaves its own."""
        for later in (f"python3 {self.DRIVER} fixed-security --max-array-length 2 --timeout 60 --work {self.WORK}",
                      f"python3 examples/901-another-change/proofs/prove.py fixed-security --timeout 60 --work {self.WORK}/"):
            with self.subTest(later=later):
                self.refused_for([self.driver, later], "writes the same outcome folder")

    def test_a_later_run_into_the_same_folder_under_another_spelling_is_refused(self):
        """The evidence stream's I015 (lib/tests/fixtures/accept-countermodels/README.md, 'Past the step check's fix'):
        the pipeline runs every step in <state>/work/<job id>, known when the job is written, so an absolute --work, or
        one that leaves that folder by `..`, can name the chosen step's outcome folder under another spelling; and a
        task word with a `/` can reach it from the folder above."""
        for later, words in ((f"python3 {self.DRIVER} fixed-security --timeout 60 --work /state/work/{self.paths['job'].rsplit('/', 1)[1][:-5]}/{self.WORK}",
                              "is not a folder inside the step's own"),
                             (f"python3 {self.DRIVER} fixed-security --timeout 60 --work ../{self.paths['job'].rsplit('/', 1)[1][:-5]}/{self.WORK}",
                              "is not a folder inside the step's own"),
                             (f"python3 {self.DRIVER} fixed-security --max-array-length 2 --timeout 60 --work {self.WORK}/x/..", "writes the same outcome folder"),
                             (f"python3 {self.DRIVER} .work-900/fixed-security --timeout 60 --work verification", "writes the same outcome folder")):
            with self.subTest(later=later):
                self.refused_for([self.driver, later], words)
        # The chosen step itself is held to the same: its outcome is collected under the job's folder.
        self.refused_for([f"python3 {self.DRIVER} fixed-security --timeout 60 --work /tmp/{self.WORK}"], "is not a folder inside the step's own")
        # A folder of its own inside the step's, before or after, is still a trial's or another task's.
        self.accepted([f"python3 {self.DRIVER} fixed-security --max-array-length 2 --timeout 60 --work {self.WORK}/trial/../trial2", self.driver])

    def test_the_outcome_read_is_the_one_the_driver_wrote_where_work_is_given_twice(self):
        """The step check took the first `--work`; the driver's argparse keeps the last (and `--work=DIR` was not
        read as one at all)."""
        for twice, words in ((f"--work {self.WORK} --work verification/.work-elsewhere", "given twice"),
                             (f"--work {self.WORK} --work=verification/.work-elsewhere", "--work=")):
            with self.subTest(twice=twice):
                self.refused_for([f"python3 {self.DRIVER} fixed-security --timeout 60 {twice}"], words)

    def test_a_step_that_runs_the_driver_on_another_checker_binary_or_environment_is_refused(self):
        """`--jvmcontract PATH` runs another binary than the pipeline's build of the job's lib/, which the identity
        still names; a job's `env` can do the same through PATH or JVMCONTRACT, and a step's `cwd` moves what its
        paths mean."""
        self.refused_for([f"python3 {self.DRIVER} fixed-security --jvmcontract /elsewhere/lib/target/release/jvmcontract "
                          f"--timeout 60 --work {self.WORK}"], "--jvmcontract")
        self.refused_for([self.driver], "environment", env={"PATH": "/elsewhere/bin:/usr/bin"})
        self.steps([self.driver])
        spec = json.loads((self.root / self.paths["job"]).read_text())
        spec["steps"][0]["cwd"] = "examples"
        (self.root / self.paths["job"]).write_text(json.dumps(spec))
        result = json.loads((self.root / self.paths["result"]).read_text())
        result["job"]["sha256"] = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()
        (self.root / self.paths["result"]).write_text(json.dumps(result))
        self.refused("fixed-security", "step", "runs in 'examples'", self.committed)

    def test_a_result_whose_steps_are_not_the_job_files_is_refused(self):
        """The job file is the one its result is of (its hash); the steps the result records ran are its steps."""
        self.steps([self.driver])
        result = json.loads((self.root / self.paths["result"]).read_text())
        result["steps"].insert(0, {**result["steps"][0], "index": 0, "run": f"cp -r verification/forged/. {self.WORK}"})
        (self.root / self.paths["result"]).write_text(json.dumps(result))
        self.refused("fixed-security", "step", "not the job file's", self.committed)


class Targets(unittest.TestCase):
    def test_a_descriptors_parameters_are_spelled_as_the_checker_names_an_overloads(self):
        self.assertEqual(accept.descriptor_parameters("(Ljava/lang/String;[I[[Lpkg/A$B;JZ)V"),
                         ["java.lang.String", "int[]", "pkg.A$B[][]", "long", "boolean"])
        self.assertEqual(accept.descriptor_parameters("()V"), [])
        for bad in ("Ljava/lang/String;", "(Ljava/lang/String)V", "(Q)V"):
            with self.subTest(bad=bad):
                self.assertIsNone(accept.descriptor_parameters(bad))

    def test_a_target_with_types_is_the_tasks_only_with_its_descriptors_types(self):
        task = "pkg.C#m(Lpkg/A$B;[B)V"
        for same in ("pkg.C#m", "pkg.C#m(pkg.A$B, byte[])", "pkg.C#m(pkg.A.B, byte[])"):
            with self.subTest(same=same):
                self.assertTrue(accept.same_target(same, task))
        for other in ("pkg.C#m(A.B, byte[])", "pkg.C#m(pkg.A$B, byte)", "pkg.C#m(pkg.A$B)", "pkg.C#n(pkg.A$B, byte[])", "pkg.D#m"):
            with self.subTest(other=other):
                self.assertFalse(accept.same_target(other, task))
        # A task target with no descriptor says no types to hold a list of them to.
        self.assertTrue(accept.same_target("pkg.C#m", "pkg.C#m"))
        self.assertFalse(accept.same_target("pkg.C#m(int)", "pkg.C#m"))
        self.assertFalse(accept.same_target("pkg.C#m", ""))


class ThisCheckout(unittest.TestCase):
    @cost("tool")
    def test_example_289s_four_answers_are_accepted_from_their_saved_results(self):
        """The four results an outside review checked by hand (llm-dlc/loop-summaries/prove-change/expert-review.md,
        c2), run again by the job that recorded what it ran (evidence.json): the claim files and the allowed change
        unchanged, the outputs at their recorded hashes, bound 8, strict gaps, both refutations reproduced on a JVM,
        the mutant's JAR the replay's, and every JAR, the adapter and the verifier recorded, so no limit is left.
        Preservation's first rerun is refused: its outcome is from before the checker said whether its witness lies
        outside the allowed change. The run that says so (job 20261117-213024, on another checker) answers it."""
        source = accept.Source(REPO)
        git = source.git_dir()
        if not git or subprocess.run([*git, "cat-file", "-e", "150c4a2557ebd284bbb73f1084e5ac7d6e1d7523^{commit}"], capture_output=True).returncode:
            self.skipTest("the jobs' source commit is not in this checkout (a released copy)")
        tasks = accept.tasks_beside(REPO, "289")
        self.assertEqual(sorted(tasks), ["fixed-security", "mutant-security", "preservation", "vulnerable-security"])
        for task in tasks:
            r = accept.check(REPO, "289", task, source)
            if task == "preservation" and r["job"] == "20261117-122454-example-289-the-four-proof-tasks-again-w":
                self.assertFalse(r["accepted"])
                self.assertIn(("non-vacuous", "unbound"), [(c["check"], c["status"]) for c in r["checks"]])
                continue
            self.assertTrue(r["accepted"], f"{task}: {r.get('why')}")
            self.assertEqual(r["limits"], [], task)
            self.assertIn(("artifacts", "ok"), [(c["check"], c["status"]) for c in r["checks"]], task)
            self.assertEqual(r["bound"]["ran"], 8)
            trees = {"20261117-213024-examples-289-and-290-preservation-again": "937c791fb373e9b206b0ac0cdec704cab66d3e70"}
            self.assertEqual(r["identity"]["libTree"], trees.get(r["job"], "09d2f5bfc7dd3385b28ab233aa4ae671db5d7bea"))


if __name__ == "__main__":
    unittest.main()
