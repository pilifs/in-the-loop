#!/usr/bin/env python3
"""Tests of examples/tools/economics.py: what it reads off the tool's notes, which claims the cache serves, and its
runs and expectations end to end against a fake jvmcontract, with no javac and no proof.

Run: python3 examples/tools/test_economics.py
"""

import contextlib
import hashlib
import json
import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import economics  # noqa: E402

KEY = "sha256:" + "ab" * 32
HELPER = "sha256:" + "cd" * 32
TIMED = "note: the proof cache took 0.120 s to compute this claim's key (both versions' closures, the harness's digest and the tools') and 0.003 s to look it up\n"


def outcome(verdict="verified", output="", search=0.5, reuse=None, proof="jvmcontract's own checker (CaDiCaL): proved", replay=None):
    return {"verdict": verdict, "output": output, "search": {"seconds": search} if search is not None else None,
            "reuse": reuse, "proof": proof, "replay": replay}


class Measure(unittest.TestCase):
    def test_a_miss_with_a_helper_proved_in_the_run_and_one_found(self):
        output = ("note: Split.share's own check took 0.200 s\n"
                  f"note: Split.share, changed: its two versions have the same outcome, result or exception, on every input, proved now and stored in the proof cache (claim {HELPER}); one function in both versions\n"
                  "note: Split.rate's own check took 0.050 s\n"
                  f"note: Split.rate, changed: its two versions have the same outcome, result or exception, on every input, found in the proof cache (claim {HELPER}); one function in both versions\n"
                  f"note: the proof cache has no result for this claim ({KEY}); proving\n" + TIMED +
                  f"✓ verified\nnote: stored in the proof cache as claim {KEY}\n")
        r = economics.measure(outcome(output=output), output, 2.0)
        self.assertEqual((r["served"], r["key"], r["stored"]), ("helper evidence found", KEY, True))
        self.assertEqual((r["checker"], r["hashing"], r["helperSeconds"], r["other"]), (0.5, 0.123, 0.25, 1.127))
        self.assertEqual([(h["callee"], h["found"]) for h in r["helpers"]], [("Split.share", False), ("Split.rate", True)])

    def test_a_helper_proved_only_now_and_one_left_as_written(self):
        output = (f"note: A.f, changed: its two versions have the same outcome, result or exception, on every input, proved now and stored in the proof cache (claim {HELPER}); one function in both versions\n"
                  "note: A.g's own check took 0.100 s\nnote: A.g, changed, stays as written in both versions: its two versions differ, at g(1)\n" + TIMED)
        r = economics.measure(outcome(output=output), output, 1.0)
        self.assertEqual(r["served"], "helper proved in the run")
        self.assertEqual(r["helpers"][1], {"callee": "A.g", "shared": False, "why": "its two versions differ, at g(1)", "seconds": 0.1})

    def test_an_exact_hit_s_helper_notes_are_the_stored_run_s_and_are_not_counted(self):
        output = (f"note: A.f, changed: its two versions have the same outcome, result or exception, on every input, proved now and stored in the proof cache (claim {HELPER}); one function in both versions\n"
                  f"note: reused from the proof cache: an exact hit of claim {KEY}, the result of x; nothing was proved again\n" + TIMED)
        r = economics.measure(outcome(output=output, search=None, reuse={"kind": "exact", "key": KEY, "from": "x"}), output, 0.4)
        self.assertEqual((r["served"], r["checker"], r["hashing"], r["helpers"], r["key"]), ("exact hit", 0.0, 0.123, [], KEY))

    def test_nothing_to_prove_refuted_unresolved_and_no_outcome(self):
        same = outcome(search=None, proof="its bytecode is identical in both versions and it reaches no other method; nothing to prove")
        self.assertEqual(economics.measure(same, "", 0.1)["served"], "nothing to prove")
        refuted = economics.measure(outcome("violation", replay={"by": "interpreter", "reproduced": True}), TIMED, 1.0)
        self.assertEqual((refuted["served"], refuted["replayed"]), ("refuted", True))
        self.assertEqual(economics.measure(outcome("unverifiable"), "", 1.0)["served"], "unresolved")
        self.assertEqual(economics.measure(None, "", 1.0)["served"], "error")
        not_used = economics.measure(outcome(), "note: the proof cache is not used: JBMC may decide it\n", 1.0)
        self.assertEqual((not_used["cacheNotUsed"], not_used["hashing"]), ("JBMC may decide it", 0.0))


def example(id, approach="B9", engine="native", **change):
    return {"id": id, "origin": "constructed", "approach": {"id": approach, **({"engine": engine} if engine else {})},
            "subject": {"file": "examples/apps/mica/src/main/java/X.java", "symbol": "p.X#m"},
            "change": {"patch": "change.patch", **change}}


class Claims(unittest.TestCase):
    def test_the_cache_serves_native_regression_proofs_only(self):
        self.assertIsNone(economics.served(example("140")))
        self.assertIn("JBMC's identity is not part of the claim's key", economics.served(example("013", engine=None)))
        self.assertIn("--engine jbmc", economics.served(example("013", engine=None)))
        self.assertIn("(`prove`), which has no proof cache", economics.served(example("147", approach="B11")))

    def test_every_recorded_b9_and_b11_example_is_counted_once(self):
        included, excluded = economics.recorded()
        ids = [x["id"] for x in included] + [x["id"] for x in excluded]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("160", [x["id"] for x in included if x["unserved"] is None])
        self.assertTrue(all(x["app"] in economics.build.TOOL_APPS for x in included))

    def test_the_recorded_claim_keeps_its_mappings_and_the_own_claim_only_its_domain(self):
        x = {"example": example("135", intendedInputs="n > 0", previousArguments="a, b", resultsAgreeWhen="r == p", previousSymbol="p.X#old")}
        x["example"]["approach"]["cache"] = True
        recorded = economics.recorded_claim(x)
        self.assertEqual(recorded["flags"], ["--unchanged-unless", "n > 0", "--before-target", "p.X#old", "--before-arguments", "a, b",
                                             "--results-agree-when", "r == p", "--engine", "native", "--gaps", "strict"])
        self.assertEqual(economics.own_claim(x)["flags"], ["--unchanged-unless", "n > 0", "--engine", "native", "--gaps", "strict"])

    def test_each_app_with_a_served_claim_has_a_change_of_each_kind(self):
        for app in ("crosscut", "mica"):
            for kind in economics.KINDS:
                patch = economics.change_patch(app, kind).read_text()
                self.assertTrue(patch.startswith(f"diff --git a/examples/apps/{app}/"), (app, kind))


# A jvmcontract that keeps a claim per target, flags and the two trees' code in its cache directory, the trees named
# by their patches: an unrelated edit is code no claim reaches, so it is in no claim. A stored claim is an exact hit;
# otherwise the patches on one side only decide (none, or the unrelated edit alone: nothing to prove; a regression:
# refuted; a helper rewrite: proved with its helper, proved now or found; anything else: proved).
FAKE = textwrap.dedent(r'''
    import hashlib, json, sys
    from pathlib import Path
    a = sys.argv[1:]
    opt = lambda name: a[a.index(name) + 1]
    before, after, cache = opt("--before"), opt("--after"), Path(opt("--cache"))
    code = lambda tree: sorted(set(Path(tree).name.split("+")) - {"unrelated"})
    key = "sha256:" + hashlib.sha256(json.dumps(a[a.index("--target"):a.index("--cache")] + [code(before), code(after)]).encode()).hexdigest()
    cache.mkdir(parents=True, exist_ok=True)
    timed = "note: the proof cache took 0.010 s to compute this claim's key (both versions' closures, the harness's digest and the tools') and 0.001 s to look it up\n"
    entry = cache / key[7:]
    b, f = set(Path(before).name.split("+")), set(Path(after).name.split("+"))
    changed = f - b
    if entry.exists():
        stored = json.loads(entry.read_text())
        print(json.dumps({**stored, "search": None, "reuse": {"kind": "exact", "key": key, "from": "an earlier run"},
                          "output": stored["output"] + f"note: reused from the proof cache: an exact hit of claim {key}, the result of an earlier run\n" + timed}))
        sys.exit(0)
    if changed <= {"unrelated"}:
        print(json.dumps({"verdict": "verified", "output": "✓ nothing to prove\n", "proof": "identical; nothing to prove", "search": None}))
        sys.exit(0)
    output, verdict, replay = "", "verified", None
    if "helper-rewrite" in changed:
        helper = cache / "helper"
        how = "found in the proof cache" if helper.exists() else "proved now and stored in the proof cache"
        helper.write_text("")
        output += f"note: H.h's own check took 0.100 s\nnote: H.h, changed: its two versions have the same outcome, result or exception, on every input, {how} (claim sha256:{'cd' * 32}); one function in both versions\n"
    if "regression" in changed:
        verdict, replay = "violation", {"by": "interpreter", "reproduced": True}
    output += f"note: the proof cache has no result for this claim ({key}); proving\n" + timed + f"{verdict}\nnote: stored in the proof cache as claim {key}\n"
    result = {"verdict": verdict, "output": output, "proof": "proved", "search": {"seconds": 0.5}, "replay": replay}
    entry.write_text(json.dumps({k: v for k, v in result.items() if k != "search"} | {"output": output.replace(timed, "")}))
    print(json.dumps(result))
''')


class Runs(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.exe = self.dir / "jvmcontract"
        self.exe.write_text(f"#!{sys.executable}\n{FAKE}")
        self.exe.chmod(0o755)
        names = {economics.change_patch(app, kind).read_text(): kind for app in ("crosscut", "mica") for kind in economics.KINDS}
        test = self

        def get(trees, app, patches, folder=None, example=None):
            labels = [names.get(p) or "p" + hashlib.sha256(p.encode()).hexdigest()[:8] for p in patches]
            if any(l.startswith("p") for l in labels) and set(labels) & set(test.conflicts):  # an example's patch on a change it conflicts with
                return None, "patch 2 of 2 does not apply: error: patch does not apply"
            root = test.dir / "trees" / "+".join([app, *labels])
            root.mkdir(parents=True, exist_ok=True)
            return root, root

        self.conflicts = ["helper-rewrite"]
        self.get = mock.patch.object(economics.Trees, "get", get)
        self.get.start()

    def tearDown(self):
        self.get.stop()

    def run_main(self):
        out = self.dir / "out"
        with open(os.devnull, "w") as quiet, contextlib.redirect_stdout(quiet):
            code = economics.main(["--jvmcontract", str(self.exe), "--out", str(out), "--app", "mica"])
        return code, json.loads((out / "report.json").read_text()), (out / "report.md").read_text()

    def test_the_runs_and_their_expectations(self):
        code, report, text = self.run_main()
        failed = [e for e in report["expectations"] if not e["passed"]]
        self.assertEqual((code, failed), (0, []))
        runs = {r["name"]: r for r in report["runs"]}
        self.assertEqual(runs["cold"]["totals"]["served"], {"proved": 6})
        self.assertEqual(runs["warm"]["totals"]["served"], {"exact hit": 6})
        self.assertEqual(runs["warm"]["differs"], [])
        self.assertEqual(runs["mica, an unrelated edit, rebased, warm"]["totals"]["served"], {"exact hit": 6})
        self.assertEqual(runs["mica, an unrelated edit, own, cold"]["totals"]["served"], {"nothing to prove": 4})
        helper = runs["mica, a behaviour-preserving helper rewrite, own, warm"]
        self.assertEqual(helper["totals"]["served"], {"helper evidence found": 3, "helper proved in the run": 1})
        self.assertEqual(runs["mica, a behaviour-preserving helper rewrite, rebased, cold"]["totals"]["served"], {"not run": 6})
        self.assertEqual(runs["mica, a real regression, own, warm"]["totals"]["served"], {"refuted": 4})
        self.assertEqual(report["counts"]["served"] + report["counts"]["unserved"] + len(report["excluded"]), report["counts"]["recorded"])
        self.assertIn("| warm | 6 | 6 exact hit |", text)
        self.assertIn("- ✓ every warm verdict is the cold run's", text)

    def test_a_warm_verdict_that_is_not_the_cold_one_fails(self):
        real = economics.check

        def lying(exe, claim, before, after, cwd, cache, work):
            record = real(exe, claim, before, after, cwd, cache, work)
            if record["served"] == "exact hit":
                record["verdict"] = "violation"
            return record

        with mock.patch.object(economics, "check", lying):
            code, report, text = self.run_main()
        self.assertEqual(code, 1)
        failed = {e["expectation"] for e in report["expectations"] if not e["passed"]}
        self.assertIn("every warm verdict is the cold run's", failed)
        self.assertIn("✗ every warm verdict is the cold run's: warm: 140: warm violation, cold verified", text)

    def test_a_warm_rerun_that_proves_again_fails(self):
        real = economics.check

        def forgetful(exe, claim, before, after, cwd, cache, work):
            return real(exe, claim, before, after, cwd, Path(tempfile.mkdtemp()), work)

        with mock.patch.object(economics, "check", forgetful):
            code, report, _ = self.run_main()
        self.assertEqual(code, 1)
        failed = {e["expectation"] for e in report["expectations"] if not e["passed"]}
        self.assertIn("the warm rerun is an exact hit wherever the cold run stored a result, with its verdict", failed)
        self.assertIn("mica, an unrelated edit: every rebased claim the cold run stored is an exact hit", failed)


if __name__ == "__main__":
    unittest.main()
