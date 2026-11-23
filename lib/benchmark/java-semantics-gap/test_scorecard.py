"""A verdict or an assertion ID alone cannot bind a claim to its declared scope."""
import copy
from dataclasses import asdict
import json
import unittest

from scorecard import native_scope, state
from standalone import decode
from subjects import CLAIMS
from direct_arrays import BASE, unchanged_inputs


class ScorecardTest(unittest.TestCase):
    def test_frozen_subjects_compare_the_in_memory_scope_to_its_json_receipt(self):
        for key in ("arrays", "gson-parent"):
            saved = json.loads((BASE / "qualified" / key / "measurement.json").read_bytes())
            in_memory = dict(saved, scope=asdict(CLAIMS[key]))
            self.assertEqual(unchanged_inputs(key, in_memory), saved)
            in_memory["scope"]["bound"] += 1
            with self.assertRaisesRegex(ValueError, "frozen scope changed"):
                unchanged_inputs(key, in_memory)

    def test_a_violation_requires_its_original_jvm_replay(self):
        self.assertEqual(state("violation","violation","correct",None),"open")
        self.assertEqual(state("violation","violation","correct","refuted"),"refuted")
        self.assertEqual(state("violation","verified","unconfirmed witness","held"),"JVM-contradicted violation")
        self.assertEqual(state("verified","violation","false-success",None),"JVM-contradicted proof")
        self.assertEqual(state("verified","violation","incomplete bound or vacuous",None),"open")

    def test_narrower_strings_extra_assumptions_and_contracts_are_rejected(self):
        claim=next(c for c in CLAIMS["prefix"].claims if c.method=="wide")
        parameters=[{"name":name,"type":"java.lang.String","kind":"value","null":False,"max_length":4}
                    for name in ("text","prefix")]
        parameters.append({"name":"off","type":"int","kind":"primitive","null":False})
        row={"stated":{"domain":{"parameters":parameters,"shared_arrays":False},
             "assumptions":[{"kind":"initialization","basis":"engine","text":
             "every JDK class is initialized already, its static initializer having run and thrown nothing"}]},
             "search":{"gaps":[]},"throws":[]}
        native_scope(row,claim,4,"prefix/wide")
        def shorter(r): r["stated"]["domain"]["parameters"][0]["max_length"]=2
        def nullable(r): r["stated"]["domain"]["parameters"][1]["null"]=True
        def guard(r): r["stated"]["assumptions"].append({"kind":"precondition","text":"off == 0"})
        def assumed(r): r["search"]["gaps"].append({"treatment":"assumed"})
        def allowed_throw(r): r["throws"].append("NullPointerException")
        for change in (shorter,nullable,guard,assumed,allowed_throw):
            with self.subTest(change=change.__name__):
                altered=copy.deepcopy(row);change(altered)
                with self.assertRaises(ValueError): native_scope(altered,claim,4,"prefix/wide")

    def test_standalone_records_an_unwinding_failure_next_to_a_successful_target(self):
        target={"property":"java::GapAssertions.target:()V.assertion.1","status":"SUCCESS",
                "sourceLocation":{"propertyClass":"assertion"}}
        loop={"property":"java::Library.work:()V.unwind.1","status":"FAILURE"}
        data=json.dumps([{"result":[target,loop]},{"cProverStatus":"failure"}]).encode()
        result=decode(data,b"",10,"target")
        self.assertEqual(result["status"],"SUCCESS")
        self.assertEqual([p["property"] for p in result["otherFailures"]],[loop["property"]])
        self.assertEqual(decode(data,b"",0,"target")["status"],"incomplete property report")
        self.assertEqual(decode(data,b"",10,"reached")["status"],"incomplete property report")


if __name__=="__main__":
    unittest.main()
