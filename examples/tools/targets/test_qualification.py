"""Changing one semantic field of the plan or of the replay must retire its evidence."""

from copy import deepcopy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from targets import qualification


class QualificationTest(unittest.TestCase):
    def setUp(self):
        self.task = {"target": "example.Pair#apply([I[I)I"}
        selected = [{"kind": "array-parameter", "parameter": "right"}]
        self.claim = {"observations": selected, "nullable": ["left", "right"], "mayAlias": ["left,right"],
                      "bounds": {"maxArrayLength": 4, "unwind": 8}, "assume": "valid(left, right)"}
        params = [{"name": name, "type": "int[]", "kind": "array", "null": True, "max_length": 4}
                  for name in ("left", "right")]
        self.outcome = {"verdict": "verified", "stated": {
            "bounds": {"max_array_length": 4, "unwind": 8, "complete": True}, "vacuity": {"status": "non-vacuous"},
            "models": {"jdk": "21.0.13", "digest": "model A"},
            "domain": {"parameters": params, "shared_arrays": True, "may_alias": [["left", "right"]]},
            "assumptions": [{"kind": "precondition", "basis": "stated", "text": self.claim["assume"]}],
            "spec": {"observations": deepcopy(selected), "contract": {
                "subject": "example.Pair#apply", "required": ["array:right"],
                "inputs": [{"name": p["name"], "type": "int[]", "derivation": {"kind": "identity"}} for p in params]}}}}

    def problem(self):
        return qualification.check(self.claim, self.task, self.outcome, 4)

    def test_narrow_proof_and_in_domain_replayed_refutation(self):
        self.assertIsNone(self.problem())
        s = self.outcome["stated"]
        s["bounds"]["max_array_length"] = 2
        for param in s["domain"]["parameters"]:
            param["max_length"] = 2
        self.assertIn("does not cover", self.problem())
        s["bounds"]["complete"] = False
        self.outcome.update(verdict="violation", replay={"by": "jvm", "reproduced": True},
                            counterexample={"inputs": [{"name": "left", "type": "int[]", "value": [0]},
                                                       {"name": "right", "type": "int[]", "value": {"same": 0}}],
                                            "differs": ["array:right"], "replay_observations": deepcopy(self.claim["observations"])})
        self.assertIsNone(self.problem())
        self.outcome["counterexample"]["replay_observations"][0]["parameter"] = "left"
        self.assertIn("JVM replay", self.problem())
        self.outcome["counterexample"]["replay_observations"] = deepcopy(self.claim["observations"])
        self.outcome["counterexample"]["inputs"][0]["value"] = [0] * 5
        self.assertIn("outside", self.problem())

    def test_comparing_complete_descriptors_environment_and_alias_policy(self):
        for original, altered in [
            ({"kind": "field-path", "path": "p.a"}, {"kind": "field-path", "path": "p.b"}),
            ({"kind": "effect", "call": "save", "payload": ["a", "b"]}, {"kind": "effect", "call": "save", "payload": ["b", "a"]}),
            ({"kind": "exception"}, {"kind": "result"}),
        ]:
            self.claim["observations"] = [original]
            self.outcome["stated"]["spec"]["observations"] = [altered]
            self.assertIn("descriptors", self.problem())
        self.claim["observations"] = [{"kind": "array-parameter", "parameter": "right"}]
        self.outcome["stated"]["spec"]["observations"] = deepcopy(self.claim["observations"])
        self.claim["mayAlias"] = []
        self.assertIn("alias", self.problem())
        self.claim["mayAlias"] = ["left,right"]
        self.claim["boundEnvironment"] = {"jdk": "21.0.13", "modelDigest": "model A"}
        self.assertIsNone(self.problem())
        self.outcome["stated"]["models"]["digest"] = "model B"
        self.assertIn("environment", self.problem())

    def test_an_incomplete_or_vacuous_proof_stays_open(self):
        self.outcome["stated"]["bounds"]["complete"] = False
        self.assertIn("incomplete", self.problem())
        self.outcome["stated"]["bounds"]["complete"] = True
        self.outcome["stated"]["vacuity"]["status"] = "vacuous"
        self.assertIn("non-vacuity", self.problem())
        self.outcome["stated"]["spec"]["observations"] = []
        self.assertIn("descriptors", self.problem())


if __name__ == "__main__":
    unittest.main()
