#!/usr/bin/env python3
"""Tests of examples/tools/targets/sidecar.py and examples/schema/target.schema.json: a strict, versioned sidecar,
and the refusals Phase 0 of llm-dlc/loops/example-targets.md requires (an unknown field, a mutable revision, a path
escape, a dependency cycle), offline and in milliseconds.

  python3 examples/tools/targets/test_sidecar.py
"""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from targets import sidecar  # noqa: E402

A = "a" * 40
B = "b" * 40

MINIMAL = {
    "schema": "example-target/v1",
    "identity": {"case": "fixture-gate", "family": "fixture", "role": "negative"},
    "history": {
        "repository": "https://github.com/example/fixture",
        "revisions": {"vulnerable": {"commit": A}, "fixed": {"commit": B, "parent": A}},
        "pairs": [{"name": "exact-fix", "kind": "exact-fix", "before": "vulnerable", "after": "fixed"}],
    },
    "tasks": [
        {"id": "vulnerable-security", "kind": "prove", "relation": "security", "revision": "vulnerable",
         "target": "fixture.Gate#allowed(Ljava/lang/String;)Z", "expected": "refuted", "engine": "native", "gaps": "strict"},
        {"id": "fixed-security", "kind": "prove", "relation": "security", "revision": "fixed",
         "target": "fixture.Gate#allowed", "expected": "established", "requires": ["vulnerable-security"]},
        {"id": "preservation", "kind": "equivalence", "relation": "preservation", "pair": "exact-fix",
         "target": "fixture.Gate#allowed", "expected": "established", "bounds": {"maxStringLength": 4}},
    ],
    "controls": [{"id": "oracle", "kind": "oracle", "path": "controls/oracle.py", "task": "fixed-security"}],
}


def edited(**changes):
    """MINIMAL with changes, each a function of a deep copy."""
    t = copy.deepcopy(MINIMAL)
    for change in changes.values():
        change(t)
    return t


class SidecarTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.folder = Path(self.dir.name)

    def tearDown(self):
        self.dir.cleanup()

    def refused(self, target, fragment):
        with self.assertRaises(sidecar.SidecarError) as caught:
            sidecar.check(target, self.folder)
        self.assertIn(fragment, str(caught.exception))

    def test_a_minimal_sidecar_is_accepted(self):
        sidecar.check(MINIMAL, self.folder)

    def test_a_catalog_entry_has_no_tasks(self):
        t = edited(role=lambda t: t["identity"].update(role="catalog"), tasks=lambda t: t.update(tasks=[]),
                   controls=lambda t: t.pop("controls"))
        sidecar.check(t, self.folder)

    def test_another_version_is_refused(self):
        self.refused(edited(v=lambda t: t.update(schema="example-target/v2")), "example-target/v1")

    def test_an_unknown_field_is_refused_at_every_level(self):
        self.refused(edited(x=lambda t: t.update(extra=1)), "Additional properties")
        self.refused(edited(x=lambda t: t["identity"].update(extra=1)), "Additional properties")
        self.refused(edited(x=lambda t: t["history"]["revisions"]["fixed"].update(branch="main")), "Additional properties")
        self.refused(edited(x=lambda t: t["tasks"][0].update(predicate="x")), "Additional properties")

    def test_a_mutable_revision_is_refused(self):
        for ref in ("main", "v5.3.18", A[:12], A.upper()):
            self.refused(edited(x=lambda t: t["history"]["revisions"]["fixed"].update(commit=ref)), "does not match")

    def test_a_mutable_artifact_version_is_refused(self):
        for version in ("5.3.+", "LATEST", "[5.3,6)", "6.3.8-SNAPSHOT", "RELEASE"):
            t = edited(p=lambda t: t.update(preparation={"route": "published-artifact", "artifacts": [
                {"revision": "fixed", "coordinates": f"org.springframework:spring-core:{version}"}]}))
            with self.assertRaises(sidecar.SidecarError, msg=version):
                sidecar.check(t, self.folder)
        ok = edited(p=lambda t: t.update(preparation={"route": "published-artifact", "artifacts": [
            {"revision": "fixed", "coordinates": "org.springframework:spring-core:5.3.19",
             "url": "https://repo.maven.apache.org/maven2/org/springframework/spring-core/5.3.19/spring-core-5.3.19.jar",
             "sha256": "0" * 64}]}))
        sidecar.check(ok, self.folder)

    def test_a_download_from_elsewhere_is_refused(self):
        t = edited(p=lambda t: t.update(preparation={"route": "published-artifact", "artifacts": [
            {"revision": "fixed", "coordinates": "a:b:1.0", "url": "https://mirror.example.com/a/b/1.0/b-1.0.jar"}]}))
        self.refused(t, "does not match")

    def test_a_path_escape_is_refused(self):
        for path in ("../other/oracle.py", "/etc/passwd", "controls/../../x", "..", "a\\..\\b"):
            self.refused(edited(x=lambda t: t["controls"][0].update(path=path)), "does not match")

    def test_a_path_through_a_link_out_of_the_folder_is_refused(self):
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        (self.folder / "controls").symlink_to(outside.name)
        self.refused(MINIMAL, "resolves outside the example's folder")

    def test_a_dependency_cycle_is_refused(self):
        t = edited(x=lambda t: t["tasks"][0].update(requires=["preservation"]),
                   y=lambda t: t["tasks"][2].update(requires=["fixed-security"]))
        self.refused(t, "cycle")
        self.refused(edited(x=lambda t: t["tasks"][0].update(requires=["vulnerable-security"])), "cycle")

    def test_undefined_names_are_refused(self):
        self.refused(edited(x=lambda t: t["tasks"][0].update(revision="introduced")), "revision introduced is not defined")
        self.refused(edited(x=lambda t: t["tasks"][2].update(pair="release")), "pair release is not defined")
        self.refused(edited(x=lambda t: t["tasks"][1].update(requires=["nothing"])), "requires nothing")
        self.refused(edited(x=lambda t: t["history"]["pairs"][0].update(after="released")), "after names revision released")
        self.refused(edited(x=lambda t: t["tasks"].append(dict(t["tasks"][0]))), "defined twice")

    def test_a_task_names_a_revision_or_a_pair_by_its_kind(self):
        self.refused(edited(x=lambda t: t["tasks"][0].update(pair="exact-fix")), "should not be valid")
        self.refused(edited(x=lambda t: t["tasks"][2].pop("pair")), "'pair' is a required property")

    def test_load_reads_the_file_example_json_names(self):
        example = {"origin": "real-world", "target": "target.json"}
        self.assertIsNone(sidecar.load(self.folder, {"origin": "real-world"}))
        with self.assertRaises(sidecar.SidecarError):
            sidecar.load(self.folder, example)  # named and missing
        (self.folder / "target.json").write_text(json.dumps(MINIMAL))
        self.assertEqual(sidecar.load(self.folder, example)["identity"]["case"], "fixture-gate")
        with self.assertRaises(sidecar.SidecarError):
            sidecar.load(self.folder, {"origin": "constructed", "target": "target.json"})
        (self.folder / "target.json").write_text("{")
        with self.assertRaises(sidecar.SidecarError):
            sidecar.load(self.folder, example)


class ExampleSchemaTest(unittest.TestCase):
    """The one optional reference from example.json, allowed for a real-world example only."""

    def test_only_a_real_world_example_may_name_a_sidecar(self):
        import jsonschema
        schema = json.loads((HERE.parents[1] / "schema/example.schema.json").read_text())
        real = json.loads(next((HERE.parents[1]).glob("105-*/example.json")).read_text())
        jsonschema.validate({**real, "target": "target.json"}, schema)
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate({**real, "target": "elsewhere/target.json"}, schema)
        constructed = json.loads(next((HERE.parents[1]).glob("001-*/example.json")).read_text())
        jsonschema.validate(constructed, schema)
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate({**constructed, "target": "target.json"}, schema)


if __name__ == "__main__":
    unittest.main()
