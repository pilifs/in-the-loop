#!/usr/bin/env python3
"""The case packets' constructed mutants, planned by the merged code (Phase 5 step 1's request 3 of
llm-dlc/loops/example-targets.md): each of the six deep packets declares its mutation control as workflow's W1
`mutant` revision, the `after` of a `mutation` pair over its base, with a replay task and a claim task of its own, and
runtime's simplematch slice keeps its mutant in its target.json. Request 9: the runner gives each packet's driver the
arguments its oracle documents, and ingestion reads each revision's lines with the oracle's problems(lines).
Offline: nothing is prepared, and no JVM runs."""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE.parent.parent
sys.path.insert(0, str(HERE.parent))
from targets import interfaces, runtime, runtime_maven, sidecar, workflow, workflow_ingest  # noqa: E402
sys.path.append(str(Path(__file__).resolve().parents[3] / "lib/tools"))
from cost_tier import cost  # noqa: E402

# Each packet: the mutant's base, its patch, the task whose claim the mutant is meant to fail, and the mutant's own
# claim task. A CVE packet's mutant fails the fixed release's security property; a positive's fails its preservation
# (gate A4: "its nearby constructed mutation fails the same claim and control").
PACKETS = {
    "285": ("fixed-release", "controls/raw-method-fallback.patch", "fixed-security", "mutant-security"),
    "286": ("fixed-release", "controls/pattern-side-unnormalized.patch", "fixed-security", "mutant-security"),
    "287": ("fixed-release", "controls/char-count-guard.patch", "fixed-security", "mutant-security"),
    "288": ("fixed-release", "controls/field-side-default-locale.patch", "fixed-security", "mutant-security"),
    "289": ("fixed-release", "controls/case-insensitive-without-dotall.patch", "fixed-security", "mutant-security"),
    "305": ("after", "controls/status-200.patch", "preservation", "mutant-preservation"),
    "306": ("release-after", "controls/drop-prefix.patch", "preservation", "mutant-preservation"),
    "307": ("after", "controls/us-ascii.patch", "preservation", "mutant-preservation"),
}


def packet(number):
    folder = next(EXAMPLES.glob(f"{number}-*"))
    example = json.loads((folder / "example.json").read_text())
    return folder, example, sidecar.load(folder, example)


class PacketMutantTest(unittest.TestCase):
    def test_each_packet_declares_its_mutant_as_a_revision_in_a_mutation_pair(self):
        for number, (base, patch, _, _) in PACKETS.items():
            with self.subTest(number):
                folder, _, target = packet(number)
                m = target["history"]["revisions"]["mutant"]["mutant"]
                self.assertEqual((m["base"], m["patch"]), (base, patch))
                self.assertEqual(m["sha256"], workflow.file_sha256(folder / patch))
                self.assertIn({"name": "mutation", "kind": "mutation", "before": base, "after": "mutant"},
                              target["history"]["pairs"])
                mutations = [c for c in target["controls"] if c["kind"] == "mutation"]
                self.assertEqual([(c["path"], c.get("revision")) for c in mutations], [(patch, "mutant")])

    def test_each_packet_plans_its_mutant_replay(self):
        for number, (base, patch, _, _) in PACKETS.items():
            with self.subTest(number):
                folder, example, target = packet(number)
                p = workflow.plan_task(folder, example, target, "mutant-replay")
                self.assertIsInstance(p, interfaces.TaskPlan, p)
                self.assertEqual(p.revisions, (base, "mutant"))
                entry = p.artifacts[1]
                self.assertEqual(entry["mutant"]["base"]["revision"], base)
                self.assertEqual(entry["mutant"]["patch"]["path"], patch)
                self.assertNotIn("commit", entry)
                self.assertIn(patch, [c["path"] for c in p.claim["controls"]])
                replay = workflow.plan_task(folder, example, target, "replay")
                self.assertNotEqual(p.claim["key"], replay.claim["key"])

    def test_each_mutant_claim_task_states_its_reference_claim_on_the_mutants_artifact(self):
        for number, (_, _, reference, task) in PACKETS.items():
            with self.subTest(number):
                folder, example, target = packet(number)
                p = workflow.plan_task(folder, example, target, task)
                self.assertIsInstance(p, interfaces.TaskPlan, p)
                ref = workflow.plan_task(folder, example, target, reference)
                self.assertEqual(p.expected, "refuted")
                self.assertEqual(p.claim["file"], ref.claim["file"])
                self.assertEqual((p.kind, p.relation, p.target, p.engine, p.gaps),
                                 (ref.kind, ref.relation, ref.target, ref.engine, ref.gaps))
                self.assertIn("mutant", p.revisions)
                self.assertTrue(all("mutant" in a for a in p.artifacts if a["revision"] == "mutant"))
                # one property, so one source-level key; the claim is the mutant's own once bound to its artifact,
                # and an attempt's inputs already differ
                self.assertEqual(p.claim["key"], ref.claim["key"])
                self.assertNotEqual(workflow.inputs_key(p), workflow.inputs_key(ref))
                self.assertIn("mutant-replay", p.prerequisites)

    def test_287s_missing_sensitivity_control_is_recorded_while_no_mutant_claim_covers_the_byte_entry(self):
        # The user's review item 10 (2026-11-15): the char-count-guard mutant drops the byte guard, but its only claim
        # task goes through matches, where ASCII characters are bytes. No task states fixed-guard's claim on the
        # mutant, so that gap is recorded in the handoff, the notes and the README. A task that closes it makes this
        # test fail: then update those records.
        folder, example, target = packet("287")
        guard = next(t for t in target["tasks"] if t["id"] == "fixed-guard")
        on_mutant = [t for t in target["tasks"] if t.get("revision") == "mutant"
                     or t.get("pair") == "mutation" and t["kind"] != "replay"]
        self.assertEqual([t["id"] for t in on_mutant], ["mutant-security"])
        self.assertNotEqual(on_mutant[0]["target"], guard["target"])
        self.assertNotEqual(on_mutant[0]["claim"], guard["claim"])
        # The note is the one that names the review item, wherever later notes put it (it was read as the last one
        # until example 287's proof attempt added a note after it).
        note = next((n for n in example["notes"] if n.startswith("Review item 10 ")), "")
        for where, text in (("handoff.next", target["handoff"]["next"]), ("notes", note),
                            ("README", (folder / "README.md").read_text())):
            with self.subTest(where):
                self.assertIn("missing sensitivity control", text.lower())
                self.assertIn("ASCII passwords", text)
                self.assertIn("overlong-bytes-rejected.json", text)


class SimpleMatchMutantTest(unittest.TestCase):
    def test_the_simplematch_slice_keeps_its_mutant_in_its_sidecar(self):
        folder = HERE / "runtime_simplematch"
        self.assertFalse((folder / "mutation.json").exists())
        target = json.loads((folder / "target.json").read_text())
        sidecar.check(target, folder)
        p = workflow.plan_task(folder, {"id": "315"}, target, "mutant-replay")
        self.assertIsInstance(p, interfaces.TaskPlan, p)
        self.assertEqual(p.revisions, ("r5-3-19", "mutant"))
        self.assertEqual(p.artifacts[1]["mutant"]["patch"]["path"], "mutant/suffix-anywhere.patch")


class RouterTest(unittest.TestCase):
    """Request 4: the committed router (examples/index.json and examples/README.md's table) lists every numbered
    folder, the catalog 285-300 and the positives 305-307 included, each sidecar example with its target projection,
    so find.py can reach them."""

    def test_the_router_lists_every_numbered_folder(self):
        folders = sorted(p.name for p in EXAMPLES.iterdir() if p.is_dir() and p.name[:3].isdigit())
        index = {e["id"]: e for e in json.loads((EXAMPLES / "index.json").read_text())["examples"]}
        readme = (EXAMPLES / "README.md").read_text()
        for name in folders:
            with self.subTest(name):
                self.assertTrue(name[:3] in index, f"{name} is not in examples/index.json")
                self.assertEqual(index[name[:3]]["path"], f"examples/{name}")
                self.assertIn(f"]({name}/README.md) |", readme)
                if (EXAMPLES / name / "target.json").exists():
                    self.assertIsNotNone(index[name[:3]]["target"])
        for number in PACKETS:
            self.assertIn(index[number]["target"]["role"], ("negative", "positive"))

    def test_every_target_projection_carries_its_readiness(self):
        """Request 5: the index projects each sidecar example's derived readiness, so find.py --readiness reaches
        them; it was None for all until workflow_discovery.READINESS_IN_INDEX was turned on."""
        index = json.loads((EXAMPLES / "index.json").read_text())["examples"]
        targets = {e["id"]: e["target"] for e in index if e["target"] is not None}
        self.assertTrue(set(PACKETS) <= set(targets))
        for number, t in targets.items():
            with self.subTest(number):
                self.assertIn(t["readiness"], ("catalogued", "partial", "scaffolded", "executable", "blocked"))
                self.assertNotIn("unsupported", t)


class CompanionTest(unittest.TestCase):
    """Request 6: each family's negative and positive name each other as companions, every sidecar example carries
    the external-target tag (and only those), and a positive carries its family's domain tag."""

    FAMILIES = {"285": ("305", "metrics"), "286": ("306", "data-binding"), "287": ("307", "password-hashing")}

    def test_negative_and_positive_name_each_other(self):
        for negative, (positive, _) in self.FAMILIES.items():
            with self.subTest(negative):
                _, _, n = packet(negative)
                _, _, p = packet(positive)
                self.assertEqual(n["identity"]["family"], p["identity"]["family"])
                self.assertIn(positive, n["identity"].get("companions", []))
                self.assertIn(negative, p["identity"].get("companions", []))
                self.assertIn(negative, p["identity"]["matching"])

    def test_external_target_tags_exactly_the_sidecar_examples(self):
        for folder in sorted(p for p in EXAMPLES.iterdir() if p.is_dir() and p.name[:3].isdigit()):
            with self.subTest(folder.name):
                tags = json.loads((folder / "example.json").read_text())["tags"]
                self.assertEqual("external-target" in tags, (folder / "target.json").exists())

    def test_a_positive_carries_its_familys_domain_tag(self):
        vocabulary = json.loads((EXAMPLES / "tags.json").read_text())
        for negative, (positive, domain) in self.FAMILIES.items():
            with self.subTest(positive):
                self.assertIn(domain, vocabulary["domain"])
                for number in (negative, positive):
                    _, example, _ = packet(number)
                    self.assertIn(domain, example["tags"])
                    for tag in example["tags"]:
                        self.assertTrue(tag in vocabulary["domain"] or tag in vocabulary["defect"]
                                        or tag in vocabulary.get("technique", {}), tag)
                    # request-binding is a defect of handler parameters, not of a matching helper
                    self.assertNotIn("request-binding", example["tags"])



class ReplayExpectationTest(unittest.TestCase):
    """What ingestion expects each revision's controls to show in every replay task of the seven packets, as each
    packet's README states it. A pair's kind gives it, but a `release` pair is only a release comparison: it brackets a
    negative case's fix (the vulnerable release violates the oracle, the fixed one holds) or a positive case's
    preserving change (both hold), so its sides follow the case's role. 306's `replay` runs its release pair, and its
    README and hand replay say both 5.3.6 and 5.3.7 hold."""

    def sides(self, number, task):
        folder, example, target = packet(number)
        p = workflow.plan_task(folder, example, target, task)
        self.assertIsInstance(p, interfaces.TaskPlan, p)
        t = next(t for t in target["tasks"] if t["id"] == task)
        return workflow_ingest.expected_sides(target, t, list(p.revisions))

    def test_each_replay_expects_what_its_packet_states(self):
        wanted = {
            ("285", "replay"): {"vulnerable-release": "violates", "fixed-release": "holds"},
            ("286", "replay"): {"vulnerable-release": "violates", "fixed-release": "holds"},
            ("287", "replay"): {"vulnerable-release": "violates", "fixed-release": "holds"},
            ("288", "replay"): {"vulnerable-release": "violates", "fixed-release": "holds"},
            ("289", "replay"): {"vulnerable-release": "violates", "fixed-release": "holds"},
            ("305", "replay"): {"before": "holds", "after": "holds"},
            ("306", "replay"): {"release-before": "holds", "release-after": "holds"},
            ("307", "replay"): {"before": "holds", "after": "holds"},
            ("105", "replay"): {"before": "violates", "after": "holds"},
            **{(n, "mutant-replay"): {base: "holds", "mutant": "violates"} for n, (base, _, _, _) in PACKETS.items()},
        }
        for (number, task), sides in wanted.items():
            with self.subTest(number=number, task=task):
                self.assertEqual(self.sides(number, task), sides)

    def test_a_release_pair_of_another_role_says_nothing(self):
        # The fixture's role is control and runtime's slices' calibration: no direction follows from the role, so a
        # release pair there gives no expectation ("no pair says what these controls should show"), never a guess.
        target = {"identity": {"role": "calibration"},
                  "history": {"pairs": [{"name": "release", "kind": "release", "before": "a", "after": "b"}]}}
        self.assertEqual(workflow_ingest.expected_sides(target, {"pair": "release"}, ["a", "b"]), {})
        for role, sides in (("negative", {"a": "violates", "b": "holds"}), ("positive", {"a": "holds", "b": "holds"})):
            target["identity"]["role"] = role
            self.assertEqual(workflow_ingest.expected_sides(target, {"pair": "release"}, ["a", "b"]), sides)



class SliceRouteTest(unittest.TestCase):
    """305 on the source-slice route (the user's decision of 2026-11-14): each commit's WebMvcTags (and after's Outcome)
    compiled alone against Framework 5.2.0.RC2, micrometer-core 1.2.0 and javax.servlet-api 4.0.1, and the after slice
    checked against Boot 2.2.0.M6's published JAR in a correspondence pair, which ingestion reads as alike or not."""

    def test_305s_tasks_plan_slices_a_published_reference_and_a_slice_mutant(self):
        folder, example, target = packet("305")
        replay = workflow.plan_task(folder, example, target, "replay")
        self.assertEqual([(a["route"], len(a["slice"]["files"]), len(a["published"])) for a in replay.artifacts],
                         [("source-slice", 1, 6), ("source-slice", 2, 6)])
        self.assertEqual(replay.artifacts[0]["slice"]["flags"][:2], ["-g", "-parameters"])
        self.assertTrue(replay.network)
        self.assertIn("git", replay.tools["required"])
        m6 = workflow.plan_task(folder, example, target, "m6-replay")
        self.assertEqual([(a["revision"], a["route"]) for a in m6.artifacts],
                         [("after", "source-slice"), ("release-m6", "published-artifact")])
        self.assertEqual(m6.artifacts[1]["published"][0]["coordinates"],
                         "org.springframework.boot:spring-boot-actuator:2.2.0.M6")
        mutant = workflow.plan_task(folder, example, target, "mutant-replay").artifacts[1]
        self.assertEqual(set(mutant["mutant"]["base"]), {"revision", "commit", "published", "slice"})
        for r in ("before", "after", "release-m6"):
            self.assertEqual(runtime.lock(m6 if r != "before" else replay, r).stage, "source-locked", r)
        self.assertEqual(runtime.lock(workflow.plan_task(folder, example, target, "mutant-replay"), "mutant").stage,
                         "source-locked")

    def test_307s_slices_need_only_the_jdk_and_before_must_match_5_2_0_m4s_published_class(self):
        """307 on the source slice (the user's choice of 2026-11-15): each commit's BCrypt.java alone, by JDK 8 with
        -g -source 1.8 -target 1.8 -encoding UTF-8, and before's BCrypt.class compared byte for byte with Spring
        Security 5.2.0.M4's published one in every preparation of before. The mutant inherits no match."""
        folder, example, target = packet("307")
        self.assertNotIn("build", target["preparation"])
        replay = workflow.plan_task(folder, example, target, "replay")
        self.assertEqual([(a["revision"], a["route"], a["published"]) for a in replay.artifacts],
                         [("before", "source-slice", []), ("after", "source-slice", [])])
        self.assertEqual(replay.artifacts[0]["slice"]["flags"], ["-g", "-source", "1.8", "-target", "1.8",
                                                                 "-encoding", "UTF-8"])
        match, = replay.artifacts[0]["slice"]["matches"]
        lock = json.loads((Path(folder) / "sources.lock.json").read_text())
        m4 = next(c for c in lock["correspondence"] if c["release"] == "5.2.0.M4")["published"]
        self.assertEqual((match["class"], match["sha256"], match["jar"]["sha256"], match["jar"]["url"]),
                         ("org/springframework/security/crypto/bcrypt/BCrypt.class",
                          m4["entries"]["org/springframework/security/crypto/bcrypt/BCrypt.class"], m4["sha256"],
                          m4["url"]))
        self.assertNotIn("matches", replay.artifacts[1]["slice"], "after has no published counterpart")
        mutant_plan = workflow.plan_task(folder, example, target, "mutant-replay")
        self.assertNotIn("matches", mutant_plan.artifacts[1]["mutant"]["base"]["slice"])
        with mock.patch.object(runtime_maven, "FETCH", side_effect=AssertionError("a lock fetched")):
            for p, r in ((replay, "before"), (replay, "after"), (mutant_plan, "mutant")):
                self.assertEqual(runtime.lock(p, r).stage, "source-locked", r)
            self.assertEqual(runtime.lock(replay, "before").source["slice"]["matches"][0]["jar"]["role"], "reference")
        for task in ("preservation", "mutant-preservation"):
            self.assertTrue(workflow.plan_task(folder, example, target, task).network, task)

    def test_a_slice_receipts_claim_names_each_revisions_scope_and_other_routes_are_unchanged(self):
        def scopes(number, task):
            folder, example, target = packet(number)
            p = workflow.plan_task(folder, example, target, task)
            return workflow_ingest.artifact_scopes({a["revision"]: (a, None, None) for a in p.artifacts})
        self.assertEqual(scopes("305", "m6-replay"), {"after": "extracted-source-slice", "release-m6": "original-bytecode"})
        self.assertEqual(scopes("305", "mutant-replay"), {"after": "extracted-source-slice",
                                                          "mutant": "constructed-mutation-of-a-slice"})
        self.assertIsNone(scopes("306", "mutant-replay"), "no slice, no new field: other routes' claims stay as they were")
        self.assertIsNone(scopes("285", "replay"))

    def test_the_m6_correspondence_expects_both_sides_alike(self):
        folder, example, target = packet("305")
        p = workflow.plan_task(folder, example, target, "m6-replay")
        good, bad = replays("305", oracle_module(folder))
        good = tuple(json.loads(line) for line in good)
        other_calls = tuple(dict(o, getStatusCalls=7) for o in good)  # the oracle doesn't read it, the comparison does
        bad = tuple(json.loads(line) for line in bad)
        bound = {r: ({"jdks": ["21", "25"]}, SimpleNamespace(artifacts=()), None) for r in p.revisions}

        def outcome(after, m6):
            records = [interfaces.ExecutionRecord(kind="jvm-control", revision=r, argv=("java",), status="exited",
                                                  exitCode=0, seconds=0.1, stdout="o", stderr="e",
                                                  identities={"jdk": f'openjdk version "{j}.0.1"'}, observations=obs)
                       for r, obs in (("after", after), ("release-m6", m6)) for j in ("21", "25")]
            fields, _, _ = workflow_ingest.replay_outcome(p, target, bound, records, {"path": "controls/oracle.py"})
            return fields["expectation"], fields["verdictLabel"]

        self.assertEqual(outcome(good, good)[0], "yes")
        self.assertIn("as the m6-correspondence correspondence expects", outcome(good, good)[1])
        self.assertEqual(outcome(bad, bad)[0], "yes", "alike is what a correspondence asks, holding or not")
        self.assertEqual(outcome(good, bad), ("no", outcome(good, bad)[1]))
        self.assertIn("problems differ", outcome(good, bad)[1])
        self.assertEqual(outcome(good, other_calls)[0], "no")
        self.assertIn("observations differ", outcome(good, other_calls)[1])


def oracle_module(folder):
    spec = importlib.util.spec_from_file_location(f"oracle_{folder.name[:3]}", folder / "controls/oracle.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def replays(number, m):
    """(lines the statement accepts, lines it doesn't) for one packet, constructed from its oracle, no JVM."""
    if number == "285":
        probes = m.load_probes()
        return (m.constructed(probes, lambda t: t if t in m.KNOWN else m.SENTINEL),
                m.constructed(probes, lambda t: m.SENTINEL if t is None else t))
    if number == "286":
        probes = m.load_probes()
        return m.constructed(probes, "ascii"), m.constructed(probes, "exact")
    if number == "287":
        data = m.load_probes()
        return m.constructed(data, "byte-guard"), m.constructed(data, "plain")
    if number == "305":
        good = [{"probe": m.token(p), "outcome": "returned", "key": m.expected(p)[0], "value": m.expected(p)[1]}
                for p in m.load_probes()]
    elif number == "306":
        good = [{"pattern": m.token(p), "str": m.token(q), "outcome": "returned", "value": m.expected(p, q)}
                for p, q in m.load_probes()]
    elif number == "307":
        probes, _ = m.load()
        bad = [{"password": m.key(p)[0], "salt": m.key(p)[1], "outcome": "threw", "exception": "java.lang.Error"}
               for p in probes]
        return None, [json.dumps(r) for r in bad]
    else:  # 105: the contract everywhere is the after revision; before overflows at (-2)^31
        probes = m.load()[0]
        good = [{"k": k, "e": e, "outcome": c[0], ("value" if c[0] == "returned" else "exception"): c[1]}
                for (k, e), c in ((p, m.contract(*p)) for p in probes)]
    bad = [dict(r, outcome="threw", exception="java.lang.IllegalStateException") for r in good]
    if number == "105":
        bad = [dict(r) if (r["k"], r["e"]) != (-2, 31) else {"k": -2, "e": 31, "outcome": "threw",
                                                               "exception": m.AE} for r in good]
    return [json.dumps(r) for r in good], [json.dumps(r) for r in bad]


class OracleConventionTest(unittest.TestCase):
    """Request 9: one convention for every packet's controls (runtime.py's docstring). The runner gives the driver
    the oracle's driver_args() and keeps every line it prints; the preparation copies the probes the oracle reads;
    ingestion reads each revision's lines with problems(lines), and refuses a result of any other shape."""
    NUMBERS = ("105", "285", "286", "287", "305", "306", "307")

    def prepare_oracle(self, folder, workdir):
        """The oracle part of a preparation, as runtime._add_controls makes it (no adapter or driver here)."""
        source = runtime._controls_source(folder.resolve(), {})
        build = SimpleNamespace(artifacts=[])
        runtime._add_controls(build, {"oracle": source["oracle"]}, folder.resolve(), workdir, "r", [])
        return SimpleNamespace(revision="r", source=source, artifacts=build.artifacts)

    @cost("tool")
    def test_the_runner_gives_each_driver_the_arguments_its_oracle_documents(self):
        for number in self.NUMBERS:
            with self.subTest(number), tempfile.TemporaryDirectory() as tmp:
                folder = next(EXAMPLES.glob(f"{number}-*"))
                prepared = self.prepare_oracle(folder, Path(tmp))
                data = [c["path"] for c in json.loads((folder / "target.json").read_text())["controls"]
                        if c["kind"] in ("probe", "trigger")]
                self.assertTrue(data)
                self.assertEqual({a.origin for a in prepared.artifacts}, {"controls/oracle.py", *data})
                args, oracle, convention = runtime._oracle_inputs(Path(tmp), prepared)
                documented = subprocess.run([sys.executable, "-I", str(folder / "controls/oracle.py"), "argv"],
                                            capture_output=True, text=True, check=True).stdout.splitlines()
                self.assertEqual((args, convention, oracle.path), (documented, "driver_args", "controls/oracle.py"))

    def test_ingestion_reads_each_revisions_lines_with_the_oracles_problems(self):
        for number in self.NUMBERS:
            with self.subTest(number):
                folder = next(EXAMPLES.glob(f"{number}-*"))
                good, bad = replays(number, oracle_module(folder))
                runs = ([good] if good else []) + [bad, bad[:-1]]
                read = workflow_ingest.read_with_oracle(
                    SimpleNamespace(folder=str(folder)), {"path": "controls/oracle.py"},
                    [SimpleNamespace(observations=tuple(json.loads(line) for line in lines)) for lines in runs])
                if good:
                    self.assertEqual(read[0], {"problems": []})
                self.assertTrue(read[-2].get("problems"), read[-2])
                self.assertTrue(all(isinstance(p, list) and len(p) == 2 for p in read[-2]["problems"]))
                self.assertIn("error", read[-1], "an incomplete replay is no verdict")
                if number == "105":
                    self.assertEqual([p[0] for p in read[-2]["problems"]], [[-2, 31]])
                if number == "285":
                    triggers = sorted(p["id"] for p in oracle_module(folder).load_probes() if p["role"] == "trigger")
                    self.assertEqual(sorted(p[0] for p in read[-2]["problems"]), triggers)

    def test_an_oracle_result_of_another_shape_is_no_verdict(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "dict.py").write_text("def check(lines):\n    return {'property': 'holds', 'security': []}\n")
            (folder / "exits.py").write_text("import sys\ndef problems(lines):\n    sys.exit('incomplete')\n")
            (folder / "both.py").write_text("def check(lines):\n    return {}\n"
                                            "def problems(lines):\n    return [('a', 'b')]\n")
            records = [SimpleNamespace(observations=({"input": 1},))]
            plan = SimpleNamespace(folder=str(folder))
            dict_read = workflow_ingest.read_with_oracle(plan, {"path": "dict.py"}, records)
            self.assertIn("not a list of (input, problem)", dict_read[0].get("error", ""), dict_read)
            self.assertIn("SystemExit", workflow_ingest.read_with_oracle(plan, {"path": "exits.py"}, records)[0]["error"])
            self.assertEqual(workflow_ingest.read_with_oracle(plan, {"path": "both.py"}, records),
                             [{"problems": [["a", "b"]]}])

    def test_the_runner_refuses_an_oracle_that_gives_no_arguments_or_leads_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            where = Path(tmp)
            (where / "controls").mkdir()
            (where / "controls/oracle.py").write_text("from pathlib import Path\nPROBES = Path('probes.json')\n")
            prepared = SimpleNamespace(revision="r", source={"oracle": {"path": "o/oracle.py"}},
                                       artifacts=[interfaces.Artifact("controls/oracle.py", "0" * 64, "oracle",
                                                                      origin="o/oracle.py")])
            with self.assertRaisesRegex(runtime.Refused, "neither driver_args"):
                runtime._oracle_inputs(where, prepared)
            (where / "controls/oracle.py").write_text("def driver_args():\n    raise SystemExit('no probes')\n")
            with self.assertRaisesRegex(runtime.Refused, "could not give the driver's arguments"):
                runtime._oracle_inputs(where, prepared)
        with self.assertRaisesRegex(runtime.Refused, "outside the work directory"):
            runtime._oracle_files({"path": "a/b/oracle.py", "sha256": "0" * 64,
                                   "data": [{"path": "probes.json", "sha256": "1" * 64}]})

    def test_under_driver_args_every_line_is_kept_and_an_unreadable_one_is_no_observation(self):
        lines = '{"jvm": {"version": "25"}}\n{"probe": "a", "outcome": "returned"}\n'
        observed, problem = runtime._observations(lines, ["a=GET"], "driver_args")
        self.assertEqual((len(observed), problem), (2, None))
        self.assertIsNone(runtime._observations(lines, ["a=GET"], "PROBES")[0], "PROBES still matches inputs")
        self.assertIsNone(runtime._observations(lines + "not json\n", ["a=GET"], "driver_args")[0])
        self.assertEqual(runtime._observations("", ["a=GET"], "driver_args"), (None, "the driver printed nothing"))

if __name__ == "__main__":
    unittest.main()
