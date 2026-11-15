#!/usr/bin/env python3
"""Tests of examples/tools/targets/sidecar.py and examples/schema/target.schema.json: a strict, versioned sidecar,
and the refusals Phase 0 of llm-dlc/loops/example-targets.md requires (an unknown field, a mutable revision, a path
escape, a dependency cycle), and a constructed mutant kept constructed, offline and in milliseconds.

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

    def test_only_a_control_is_built_from_fixtures(self):
        fixture = edited(x=lambda t: t["history"]["revisions"].update(fixed={"fixture": "gate/after"}))
        self.refused(fixture, "only a control may name a fixture")
        sidecar.check(edited(x=lambda t: t["history"]["revisions"].update(fixed={"fixture": "gate/after"}),
                             y=lambda t: t["identity"].update(role="control")), self.folder)
        self.refused(edited(x=lambda t: t["history"]["revisions"].update(fixed={"commit": B, "fixture": "gate/after"})),
                     "is valid under each of")
        self.refused(edited(x=lambda t: t.update(preparation={"route": "fixture"})), "only a control is built from fixtures")

    def with_mutant(self, **mutant):
        """MINIMAL with a constructed mutant of `fixed` and its mutation pair, `mutant` overriding its fields."""
        m = {"base": "fixed", "patch": "controls/mutant.patch", "sha256": "0" * 64,
             "description": "drop the fix's second condition", **mutant}
        return edited(r=lambda t: t["history"]["revisions"].update(mutant={"mutant": m}),
                      p=lambda t: t["history"]["pairs"].append(
                          {"name": "mutation", "kind": "mutation", "before": "fixed", "after": "mutant"}))

    def test_a_constructed_mutant_is_one_patch_from_an_upstream_revision(self):
        sidecar.check(self.with_mutant(), self.folder)
        self.assertIn(("history/revisions/mutant/mutant/patch", "controls/mutant.patch"),
                      sidecar.files(self.with_mutant()))
        self.refused(self.with_mutant(base="released"), "its base released is not defined")
        self.refused(self.with_mutant(base="mutant"), "not its own base")
        for missing in ("base", "patch", "sha256", "description"):
            t = self.with_mutant()
            del t["history"]["revisions"]["mutant"]["mutant"][missing]
            self.refused(t, f"'{missing}' is a required property")
        self.refused(self.with_mutant(sha256="abc"), "does not match")
        self.refused(self.with_mutant(patch="../x.patch"), "does not match")
        self.refused(self.with_mutant(operator="drop"), "Additional properties")
        twice = self.with_mutant()
        twice["history"]["revisions"]["again"] = {"mutant": {**twice["history"]["revisions"]["mutant"]["mutant"],
                                                             "base": "mutant"}}
        self.refused(twice, "is a mutant itself")

    def test_a_constructed_mutant_has_no_upstream_identity(self):
        t = self.with_mutant()
        t["history"]["revisions"]["mutant"]["commit"] = B
        self.refused(t, "is valid under each of")
        for key, value in (("parent", A), ("tag", "v1"), ("release", "1.0")):
            t = self.with_mutant()
            t["history"]["revisions"]["mutant"][key] = value
            self.refused(t, f"a constructed mutant has no upstream {key}")
        published = self.with_mutant()
        published["preparation"] = {"route": "published-artifact", "artifacts": [
            {"revision": "mutant", "coordinates": "a:b:1.0"}]}
        self.refused(published, "is a constructed mutant, which nothing publishes")

    def test_a_constructed_mutant_is_compared_only_with_its_base_in_a_mutation_pair(self):
        t = self.with_mutant()
        t["history"]["pairs"][1].update(before="vulnerable")
        self.refused(t, "built from fixed, and the pair compares it with vulnerable")
        t = self.with_mutant()
        t["history"]["pairs"][1].update(before="mutant", after="fixed")
        self.refused(t, "before mutant is a mutant")
        t = self.with_mutant()
        t["history"]["pairs"].append({"name": "fake-fix", "kind": "exact-fix", "before": "fixed", "after": "mutant"})
        self.refused(t, "never in a pair of kind exact-fix")
        t = self.with_mutant()
        t["history"]["pairs"][1].update(after="vulnerable")
        self.refused(t, "after vulnerable is an upstream commit")
        control = edited(r=lambda t: t["history"]["revisions"].update(mutant={"fixture": "gate/mutant"}),
                         p=lambda t: t["history"]["pairs"].append(
                             {"name": "mutation", "kind": "mutation", "before": "fixed", "after": "mutant"}),
                         c=lambda t: t["identity"].update(role="control"))
        sidecar.check(control, self.folder)

    def with_slice(self, **recipe):
        t = edited(p=lambda t: t.update(preparation={
            "route": "source-slice",
            "slice": {"files": {"vulnerable": ["src/fixture/Gate.java"], "fixed": ["src/fixture/Gate.java"]},
                      "jdk": "8", "flags": ["-g", "-parameters", "-source", "1.8", "-target", "1.8"], **recipe},
            "artifacts": [{"revision": "fixed", "coordinates": "org.springframework:spring-web:5.2.0.RC2",
                           "url": "https://repo.spring.io/milestone/org/springframework/spring-web/5.2.0.RC2/"
                                  "spring-web-5.2.0.RC2.jar", "sha256": "e" * 64}]}))
        return t

    def with_reference(self, t):
        t["history"]["revisions"]["release"] = {"commit": "c" * 40, "route": "published-artifact", "release": "1.0"}
        t["history"]["pairs"].append({"name": "check", "kind": "correspondence", "before": "fixed", "after": "release"})
        t["preparation"]["artifacts"].append({"revision": "release", "coordinates": "g.x:gate:1.0",
                                              "url": "https://repo.maven.apache.org/maven2/g/x/gate/1.0/gate-1.0.jar"})
        return t

    def test_a_source_slice_names_its_files_and_flags_and_a_reference_is_compared_only_in_a_correspondence(self):
        sidecar.check(self.with_slice(), self.folder)
        sidecar.check(self.with_reference(self.with_slice()), self.folder)
        self.refused(self.with_slice(files={"vulnerable": ["src/fixture/Gate.java"]}),
                     "revision fixed is compiled by the slice, and slice.files names no files for it")
        self.refused(self.with_slice(files={"vulnerable": ["a/G.java"], "fixed": ["a/G.java"], "other": ["a/G.java"]}),
                     "slice.files names revision other, which is not defined")
        self.refused(self.with_slice(files={"vulnerable": ["../G.java"], "fixed": ["a/G.java"]}), "does not match")
        self.refused(self.with_slice(flags=["-processorpath", "x"]), "is not one a slice may set")
        self.refused(self.with_slice(flags=["-source", "eight"]), "needs a value it accepts")
        no_recipe = self.with_slice()
        del no_recipe["preparation"]["slice"]
        self.refused(no_recipe, "names no slice")
        stray = self.with_slice()
        stray["preparation"]["route"] = "upstream-build"
        self.refused(stray, "preparation.slice is the source-slice route's recipe")
        own = self.with_reference(self.with_slice())
        own["history"]["pairs"][-1]["kind"] = "release"
        self.refused(own, "is compared only in a correspondence pair")
        two = self.with_reference(self.with_slice())
        two["history"]["pairs"][-1]["after"] = "vulnerable"
        self.refused(two, "a correspondence compares one slice revision with one published reference")
        unlisted = self.with_reference(self.with_slice())
        unlisted["preparation"]["artifacts"].pop()
        self.refused(unlisted, "lists no JAR for it")
        match = {"class": "fixture/Gate.class", "sha256": "a" * 64,
                 "jar": {"coordinates": "g.x:gate:1.0", "url": "https://repo.spring.io/milestone/g/x/gate/1.0/gate-1.0.jar",
                         "sha256": "b" * 64}}
        sidecar.check(self.with_slice(matches={"vulnerable": [match]}), self.folder)
        self.refused(self.with_reference(self.with_slice(matches={"release": [match]})),
                     "slice.matches names revision release, whose slice.files it doesn't compile")
        self.refused(self.with_slice(matches={"vulnerable": [{**match, "class": "Gate.java"}]}), "does not match")
        self.refused(self.with_slice(matches={"vulnerable": [{**match, "jar": {**match["jar"],
                                                                               "url": "https://example.org/g.jar"}}]}),
                     "does not match")
        elsewhere = self.with_reference(edited(p=lambda t: t.update(preparation={"route": "published-artifact",
                                                                                 "artifacts": []})))
        self.refused(elsewhere, "a revision's own route is only for the source-slice route's published references")

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
