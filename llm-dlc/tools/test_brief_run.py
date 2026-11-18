#!/usr/bin/env python3
"""Tests for brief_run.py, the watcher's tools for a brief's run, and for what run-streams.sh does for it: the
streams a brief names, the questions it asks about a loop that ended blocked and a stream to merge, and a run with
no fork.
Run: python3 llm-dlc/tools/test_brief_run.py
Everything is made up: a real jj repository in a temporary directory with copies of the scripts, a stand-in
`claude` on PATH, a stand-in feature-loop.sh that sets a brief's status and commits, and a stand-in sync.py. No
model is called."""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import brief_run
import conductor
import decisions
import doctor
import watch

TOOLS = Path(__file__).resolve().parent
sys.path.append(str(TOOLS.parents[1] / "lib/tools"))
from cost_tier import cost  # noqa: E402
sys.path.append(str(Path(__file__).resolve().parents[2] / "lib/tools"))
from cost_tier import cost  # noqa: E402

COPIED = ("run-streams.sh", "loop-common.sh", "streams_status.py", "run_records.py", "conductor.py", "decisions.py",
          "mode.py")

# sync.py's stand-in: llm-dlc/index.json (one of the files it generates) lists the session files, as the trace files
# list sessions; `commit` commits.
FAKE_SYNC = textwrap.dedent('''\
    import os, subprocess, sys
    from pathlib import Path
    if sys.argv[1] == "adopt-logs":
        open(os.environ["STATUSES"] + "/adopted", "a").write(os.getcwd() + "\\n")
        sys.exit(0)
    Path("llm-dlc/index.json").write_text("".join(sorted(p.name + "\\n" for p in Path("sessions").glob("*"))))
    if os.environ.get("STANDIN_LATE") == "1":  # another session writes into the working copy meanwhile
        Path("verification").mkdir(exist_ok=True)
        Path("verification/late.txt").write_text("a result collected during the merge\\n")
    if sys.argv[1] == "commit":
        args = sys.argv[2:]
        paths = args[1:args.index("-m")] if args[0] == "--only" else []
        message = args[args.index("-m") + 1]
        sys.exit(subprocess.run(["jj", "commit", "-m", message, *paths]).returncode)
''')

# verification/pipeline.py's stand-in: the runner's state is STATUSES/pipeline, a finished job a folder of results/
# with its result.json, and the jobs waiting the lines of pending; `run` only says it ran.
FAKE_PIPELINE = textwrap.dedent('''\
    import json, os, shutil, sys
    from pathlib import Path
    state = Path(os.environ["STATUSES"]) / "pipeline"
    results = state / "results"
    done = sorted(p.name for p in results.iterdir()) if results.exists() else []
    cmd = sys.argv[1]
    if cmd == "status":
        pending = (state / "pending").read_text().splitlines() if (state / "pending").exists() else []
        print(json.dumps({"pending": pending, "running": [], "finished, not collected": [f"{d} made up" for d in done]}))
    elif cmd == "collect":
        for name in done:
            r = json.loads((results / name / "result.json").read_text())
            dest = Path("verification/results") / name
            dest.mkdir(parents=True, exist_ok=True)
            (dest / "result.json").write_text(json.dumps({**r, "collected": {"conflicts": []}}))
            shutil.rmtree(results / name)
            print(f"{name}: {r['status']}: applied 0, conflicts 0, kept 0")
        print("\\nFor the commit message (python3 llm-dlc/tools/sync.py commit -m ... -m ...):")
        print(f"  Record verification results for {len(done)} job(s)")
        print(f"  Outputs applied for 0 of the {len(done)} job(s).")
    elif cmd == "commit-paths":
        print("verification")
    elif cmd == "wait":
        print("no runner is at work, and nothing waits to be collected")
    elif cmd == "run":
        (state / "ran").write_text("ran\\n")
    elif cmd == "nudge":
        print("nudged")
''')

# feature-loop.sh's stand-in: each run of a brief takes the next status of the list in STATUSES/BRIEF-NAME (the
# last one again when the list is used up), writes it into the brief and commits, and notes that it ran.
FAKE_LOOP = textwrap.dedent('''\
    #!/usr/bin/env bash
    cd "$(dirname "$0")/../.." || exit 1
    name=$(basename "$1" .md)
    echo "$name $PWD" >>"$STATUSES/runs"
    n=$(grep -c "^$name " "$STATUSES/runs")
    status=$(sed -n "${n}p" "$STATUSES/$name"); [[ -n "$status" ]] || status=$(tail -n 1 "$STATUSES/$name")
    sed -i "s/^- Status: .*/- Status: $status/" "$1"
    echo "cycle 1"
    jj commit -m "$name: $status" >/dev/null 2>&1
''')

CLAUDE = textwrap.dedent('''\
    #!/usr/bin/env python3
    import json, os, subprocess, sys
    with open(os.environ["STANDIN_LOG"], "a") as f:
        f.write(json.dumps({"args": sys.argv[1:], "cwd": os.getcwd()}) + "\\n")
    if os.environ.get("STANDIN_COMMITS") == "1":
        open("lib-foundation.txt", "w").write("shared\\n")
        open("sessions/foundation", "w").write("")
        open("llm-dlc/index.json", "w").write("base\\nfoundation\\n")
        subprocess.run(["jj", "commit", "-m", "the foundation: a shared piece"], check=True, capture_output=True)
    print(json.dumps({"type": "result", "subtype": "success", "total_cost_usd": 1.5, "result": "Built the shared piece."}))
''')


def brief(streams: list[str] = (), workspace: str | None = None, status: str | None = "working", extra: list[str] = (),
          session: int | None = None, separate: bool = True) -> str:
    session = session if session is not None else sum(map(ord, workspace or "main"))
    return "\n".join(["# Brief: made up", "", "## Progress", "", "- made up: started.",
                      *([f"- Status: {status}"] if status else []), "", "## Loop settings", "",
                      *([f"- session: 00000000-0000-4000-8000-{session:012d}"] if session else []), *(["- verification: separate"] if separate else []),
                      *([f"- streams: {', '.join(streams)}"] if streams else []),
                      *([f"- workspace: {workspace}"] if workspace else []), *extra, ""])


class Fixture(unittest.TestCase):
    STREAMS = ("a", "b")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.root = base / "root"
        self.statuses = base / "statuses"
        self.statuses.mkdir()
        (base / "bin").mkdir()
        (base / "bin" / "claude").write_text(CLAUDE)
        (base / "bin" / "claude").chmod(0o755)
        (base / "jj-config.toml").write_text("")
        self.log = base / "claude.jsonl"
        env = {"JJ_USER": "Made Up", "JJ_EMAIL": "made-up@example.com", "JJ_CONFIG": str(base / "jj-config.toml"),
               "PATH": f"{base / 'bin'}:{os.environ['PATH']}", "STANDIN_LOG": str(self.log), "STATUSES": str(self.statuses),
               "CLAUDE_CONFIG_DIR": str(base / "claude"), "XDG_STATE_HOME": str(base / "state"),
               "VERIFY_MACHINE_CONFIG": ""}
        self.env = mock.patch.dict(os.environ, env)
        self.env.start()
        # Run inside a stream's loop, the tests would otherwise inherit its run: a made-up run-streams.sh "without a
        # watcher" would ask the real one (RUN_STREAMS_WATCHER) about its made-up streams.
        for key in [k for k in os.environ if k.startswith(("RUN_STREAMS_", "FEATURE_LOOP_"))] + ["LOOP_CONDUCTOR", "TMUX", "TMUX_PANE"]:
            os.environ.pop(key, None)
        files = {".gitignore": "llm-dlc/loop-summaries/\nverification/pipeline.local.toml\n", "llm-dlc/tools/sync.py": FAKE_SYNC, "verification/pipeline.py": FAKE_PIPELINE, "sessions/base": "",
                 "llm-dlc/index.json": "base\n", "lib.txt": "one\n",
                 "llm-dlc/loops/made-up.md": brief(self.STREAMS)}
        for s in self.STREAMS:
            files[f"llm-dlc/loops/made-up-{s}.md"] = brief(workspace=f"made-up-{s}")
        for path, text in files.items():
            (self.root / path).parent.mkdir(parents=True, exist_ok=True)
            (self.root / path).write_text(text)
        for name in COPIED:
            shutil.copy(TOOLS / name, self.root / "llm-dlc" / "tools" / name)
        loop = self.root / "llm-dlc" / "tools" / "feature-loop.sh"
        loop.write_text(FAKE_LOOP)
        loop.chmod(0o755)
        self.jj(self.root, "git", "init", "--colocate")
        self.jj(self.root, "commit", "-m", "base: a made-up brief and its streams")
        self.dir = self.root / "llm-dlc" / "loop-summaries" / "run-streams-made-up"

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def jj(self, where: Path, *args: str) -> str:
        r = subprocess.run(["jj", *args], cwd=where, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def write(self, path: str, text: str, where: Path | None = None, message: str | None = None) -> None:
        where = where or self.root
        (where / path).parent.mkdir(parents=True, exist_ok=True)
        (where / path).write_text(text)
        if message:
            self.jj(where, "commit", "-m", message)

    def run_tool(self, *args: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = brief_run.main(list(args), root=self.root)
        return code, out.getvalue(), err.getvalue()

    def run_of(self) -> brief_run.Run:
        return brief_run.Run(self.root, "made-up")

    def plan(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([str(self.root / "llm-dlc/tools/run-streams.sh"), "--plan", *args], capture_output=True, text=True)

    def streams(self, *statuses_by_loop: tuple[str, list[str]], **env) -> subprocess.Popen:
        for name, statuses in statuses_by_loop:
            (self.statuses / name).write_text("".join(s + "\n" for s in statuses))
        return subprocess.Popen([str(self.root / "llm-dlc/tools/run-streams.sh"), "made-up"], cwd=self.root,
                                env={**os.environ, "RUN_STREAMS_POLL": "1", "RUN_STREAMS_STATUS_EVERY": "1", **env},
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    def runs(self) -> list[str]:
        return [line.split()[0] for line in (self.statuses / "runs").read_text().splitlines()]


class TheStreamsABriefNames(Fixture):
    @cost("tool")
    def test_a_brief_names_its_streams_and_each_has_its_brief_beside_it(self):
        r = self.plan("made-up")
        self.assertEqual(r.stdout.splitlines(), ["name: made-up", "brief: llm-dlc/loops/made-up.md",
                                                 "stream: a llm-dlc/loops/made-up-a.md", "stream: b llm-dlc/loops/made-up-b.md"])
        self.assertEqual(self.plan("llm-dlc/loops/made-up.md").stdout, r.stdout)  # by file as by name

    @cost("tool")
    def test_a_brief_that_names_none_has_no_streams(self):
        self.write("llm-dlc/loops/alone.md", brief())
        self.assertEqual(self.plan("alone").stdout.splitlines(), ["name: alone", "brief: llm-dlc/loops/alone.md"])

    @cost("tool")
    def test_the_briefs_older_than_the_setting_keep_their_streams(self):
        self.write("llm-dlc/loops/engine-priorities.md", "# Brief: older\n")
        self.write("llm-dlc/loops/cleanup.md", "# Brief: older\n")
        self.assertIn("stream: jbmc llm-dlc/loops/engine-priorities-jbmc.md", self.plan("engines").stdout)
        self.assertEqual(self.plan("llm-dlc/loops/engine-priorities.md").stdout.splitlines()[0], "name: engines")
        self.assertEqual([line.split()[1] for line in self.plan("cleanup").stdout.splitlines()[2:]], ["native", "jbmc", "examples"])

    @cost("tool")
    def test_a_brief_that_is_not_there_and_a_stream_named_as_the_runs_own_parts_are_refused(self):
        self.assertEqual(self.plan("absent").returncode, 2)
        self.write("llm-dlc/loops/bad.md", brief(["a", "brief"]))
        r = self.plan("bad")
        self.assertEqual(r.returncode, 2)
        self.assertIn("'brief'", r.stderr)


class BeforeTheRun(Fixture):
    @cost("tool")
    def test_a_brief_ready_to_run_has_nothing_in_its_way_and_says_where_each_stream_will_work(self):
        code, out, _ = self.run_tool("preflight", "made-up")
        check = json.loads(out)
        self.assertEqual((code, check["blocking"]), (0, []))
        self.assertEqual([(s["label"], s["workspace"], s["exists"], s["status"]) for s in check["streams"]],
                         [("a", "made-up-a", False, "working"), ("b", "made-up-b", False, "working")])
        self.assertEqual(check["streams"][0]["folder"], str(self.root.parent / "root-made-up-a"))

    @cost("tool")
    def test_what_run_streams_would_stop_at_is_found_before_anything_starts(self):
        self.write("llm-dlc/loops/made-up-a.md", brief(workspace="made-up-b"))  # the other stream's workspace
        (self.root / "llm-dlc/loops/made-up-b.md").write_text(brief(workspace="made-up-b", status=None))
        code, out, _ = self.run_tool("preflight", "made-up")
        blocking = " | ".join(json.loads(out)["blocking"])
        self.assertEqual(code, 1)
        self.assertIn("made-up-b.md names workspace made-up-b, which a has", blocking)
        self.write("llm-dlc/loops/made-up-a.md", brief(workspace="made-up-a"))
        (self.root.parent / "root-made-up-a").mkdir()  # a forgotten workspace's folder
        blocking = " | ".join(json.loads(self.run_tool("preflight", "made-up")[1])["blocking"])
        self.assertIn("root-made-up-a already exists, but no jj workspace is at it", blocking)
        self.assertIn("made-up-b.md has no `- Status:` line", blocking)

    @cost("tool")
    def test_each_loop_needs_a_session_of_its_own(self):
        self.write("llm-dlc/loops/made-up-a.md", brief(workspace="made-up-a", session=0))
        self.write("llm-dlc/loops/made-up-b.md", brief(workspace="made-up-b", session=sum(map(ord, "main"))))
        blocking = " | ".join(json.loads(self.run_tool("preflight", "made-up")[1])["blocking"])
        self.assertIn("made-up-a.md has no `- session: UUID`", blocking)
        self.assertIn("made-up-b.md names the session of llm-dlc/loops/made-up.md", blocking)

    @cost("tool")
    def test_a_loop_at_work_in_the_default_workspace_blocks_and_one_elsewhere_does_not(self):
        copy = Path(self.tmp.name) / "feature-loop.AbC123"  # as feature-loop.sh runs: from a private copy of itself
        copy.write_text("#!/usr/bin/env bash\nsleep 30\n")
        copy.chmod(0o755)
        for cwd, blocks in ((self.root, True), (Path(self.tmp.name), False)):
            p = subprocess.Popen(["bash", str(copy), "prove-change"], cwd=cwd)
            try:
                time.sleep(0.3)
                blocking = " | ".join(json.loads(self.run_tool("preflight", "made-up")[1])["blocking"])
                self.assertEqual("a loop is at work in the default workspace" in blocking, blocks, blocking)
            finally:
                p.kill()
                p.wait()

    @cost("tool")
    def test_a_stream_without_its_brief_blocks(self):
        (self.root / "llm-dlc/loops/made-up-b.md").unlink()
        self.assertIn("the stream b has no brief", " ".join(json.loads(self.run_tool("preflight", "made-up")[1])["blocking"]))

    @cost("tool")
    def test_the_runner_is_left_what_the_loops_do_not_take(self):
        machine = {"memory": 105 * doctor.GIB, "cpus": 30}
        with mock.patch.object(doctor, "machine", lambda: machine):
            self.assertEqual({k: brief_run.runner_budget(4, True)[k] for k in ("memory", "cpus", "workers")},
                             {"memory": "38G", "cpus": 18, "workers": 9})  # verification/README.md's streams row
            self.assertEqual(brief_run.runner_budget(0, False)["memory"], "80G")  # a brief with no streams is one loop
            self.assertEqual(brief_run.runner_budget(2, False)["cpus"], 24)

    @cost("tool")
    def test_a_budget_over_what_is_left_is_lowered_for_the_run_and_put_back_after_it(self):
        local = self.root / brief_run.LOCAL
        local.parent.mkdir(exist_ok=True)
        local.write_text('# a comment\n[runner]\nmachine_name = "vm"\nworkers = 13\ncpus = 26  # of 30\nmemory = "80G"\n[other]\nmemory = "1G"\n')
        with mock.patch.object(doctor, "machine", lambda: {"memory": 105 * doctor.GIB, "cpus": 30}):
            self.assertIn("memory 80G > 68G", " ".join(json.loads(self.run_tool("preflight", "made-up")[1])["notes"]))
            self.run_tool("budget", "made-up", "--apply")
            self.assertEqual(local.read_text(), '# a comment\n[runner]\nmachine_name = "vm"\nworkers = 12\ncpus = 24  # of 30\n'
                                                'memory = "68G"\n[other]\nmemory = "1G"\n')
            self.assertEqual(json.loads(self.run_tool("preflight", "made-up")[1])["notes"], [])
            self.run_tool("budget", "made-up", "--apply")  # a second time keeps the values of before the run
            self.run_tool("budget", "made-up", "--restore")
        self.assertIn('workers = 13\ncpus = 26  # of 30\nmemory = "80G"\n[other]', local.read_text())

    @cost("tool")
    def test_without_a_budget_of_its_own_the_checkout_is_given_the_machines_and_that_is_the_file_lowered(self):
        machine = self.root.parent / "machine.toml"
        machine.write_text('[runner]\nworkers = 13\ncpus = 26\nmemory = "80G"\njob_memory_max = "24G"\n')
        (self.root / brief_run.LOCAL).parent.mkdir(exist_ok=True)
        (self.root / brief_run.LOCAL).write_text('[runner]\nmachine_name = "vm"\n')  # sets no budget
        with mock.patch.dict(os.environ, {"VERIFY_MACHINE_CONFIG": str(machine)}), \
                mock.patch.object(doctor, "machine", lambda: {"memory": 105 * doctor.GIB, "cpus": 30}):
            self.assertEqual(brief_run.budget_file(self.root), machine)
            self.assertIn(f"{machine} gives the runner more", " ".join(json.loads(self.run_tool("preflight", "made-up")[1])["notes"]))
            self.run_tool("budget", "made-up", "--apply")
            self.assertIn('workers = 12\ncpus = 24\nmemory = "68G"\n', machine.read_text())
            self.run_tool("budget", "made-up", "--restore")
        self.assertEqual(machine.read_text(), '[runner]\nworkers = 13\ncpus = 26\nmemory = "80G"\njob_memory_max = "24G"\n')
        self.assertEqual((self.root / brief_run.LOCAL).read_text(), '[runner]\nmachine_name = "vm"\n')


class TheFoundation(Fixture):
    def foundation(self, *args: str, commits: bool = True) -> tuple[int, dict]:
        with mock.patch.dict(os.environ, {"STANDIN_COMMITS": "1" if commits else "0"}):
            code, out, err = self.run_tool("foundation", "made-up", "--memory", "none", *args)
        self.assertTrue(out, err)
        return code, json.loads(out)

    @cost("tool")
    def test_it_is_one_fable_session_in_a_workspace_of_its_own_given_the_users_words(self):
        code, out = self.foundation()
        call = json.loads(self.log.read_text().splitlines()[0])
        folder = self.root.parent / "root-made-up-foundation"
        self.assertEqual((code, call["cwd"]), (0, str(folder)))
        args = call["args"]
        self.assertEqual((args[args.index("--model") + 1], args[args.index("--effort") + 1]), ("claude-fable-5-2", "high"))
        self.assertIn(brief_run.FOUNDATION_PROMPT, args[1])
        self.assertTrue(args[1].startswith("The brief is `llm-dlc/loops/made-up.md`, with its streams' briefs beside it "
                                           "(`llm-dlc/loops/made-up-a.md`, `llm-dlc/loops/made-up-b.md`)."))
        self.assertEqual(args[args.index("--session-id") + 1], out["session"])
        self.assertEqual((out["ok"], out["committed"], out["uncommitted"], out["cost"]), (True, True, [], 1.5))
        self.assertIn("the foundation: a shared piece", out["commit"])
        self.assertIn("brief_run.py land made-up", out["next"])
        self.assertFalse((self.root / "lib-foundation.txt").exists())  # nothing of it is in the default workspace yet
        self.assertEqual((self.statuses / "adopted").read_text(), f"{folder}\n")  # the new workspace took the logs it lacked

    @cost("tool")
    def test_a_session_that_committed_nothing_is_said_so_and_a_second_run_keeps_the_session(self):
        _, first = self.foundation(commits=False)
        self.assertEqual((first["committed"], first["attempt"]), (False, 1))
        self.assertIn("committed nothing", first["next"])
        _, second = self.foundation(commits=False)
        self.assertEqual((second["session"], second["attempt"]), (first["session"], 2))

    @cost("tool")
    def test_its_commits_move_the_line_forward_when_the_line_has_not_moved(self):
        self.foundation()
        (self.root / "theirs.txt").write_text("another session's, uncommitted\n")
        code, out, err = self.run_tool("land", "made-up")
        self.assertEqual(code, 0, err)
        self.assertIn("moved forward", json.loads(out)["landed"])
        self.assertEqual((self.root / "lib-foundation.txt").read_text(), "shared\n")
        self.assertIn("the foundation: a shared piece", self.jj(self.root, "log", "--no-graph", "-r", "@-", "-T", "description"))
        self.assertIn("theirs.txt", self.jj(self.root, "diff", "-r", "@", "--name-only"))  # still uncommitted, on top
        self.assertEqual(json.loads(out)["handedOff"], ["made-up-a", "made-up-b"])  # each stream is told what it left
        item = (self.root / "llm-dlc/loop-summaries/made-up-a-inbox.md").read_text()
        self.assertIn("made-up-a-I001: what the run's foundation stage built before you started", item)
        self.assertIn("Built the shared piece.", item)
        again = json.loads(self.run_tool("land", "made-up")[1])
        self.assertIn("nothing to land", again["landed"])
        self.assertEqual(again["handedOff"], [])  # once
        self.assertTrue(json.loads(self.run_tool("preflight", "made-up")[1])["foundation"]["landed"])

    @cost("tool")
    def test_a_line_that_moved_takes_them_by_a_merge_with_the_generated_files_regenerated(self):
        self.foundation()
        self.write("sessions/collector", "")
        self.write("llm-dlc/index.json", "base\ncollector\n", message="the line moves: a result is collected")
        code, out, err = self.run_tool("land", "made-up")
        self.assertEqual(code, 0, err)
        self.assertIn("merged", json.loads(out)["landed"])
        self.assertEqual((self.root / "llm-dlc/index.json").read_text(), "base\ncollector\nfoundation\n")
        self.assertIn("Merge the foundation of the made-up run", self.jj(self.root, "log", "--no-graph", "-r", "@-", "-T", "description"))
        self.assertEqual(self.jj(self.root, "diff", "-r", "@", "--name-only"), "")

    @cost("tool")
    def test_what_another_session_wrote_during_the_merge_stays_uncommitted(self):
        self.foundation()
        self.write("lib.txt", "two\n", message="the line moves")
        with mock.patch.dict(os.environ, {"STANDIN_LATE": "1"}):
            code, out, err = self.run_tool("land", "made-up")
        self.assertEqual((code, json.loads(out)["leftUncommitted"]), (0, ["verification/late.txt"]), err)
        self.assertNotIn("verification/late.txt", self.jj(self.root, "diff", "-r", "@-", "--name-only"))
        self.assertEqual(self.jj(self.root, "diff", "-r", "@", "--name-only").split(), ["verification/late.txt"])
        self.assertTrue((self.root / "verification/late.txt").exists())

    @cost("tool")
    def test_a_merge_that_conflicts_in_real_work_is_taken_back(self):
        self.foundation()
        self.write("lib-foundation.txt", "the line's own\n", message="the line adds the same file")
        before = self.jj(self.root, "log", "--no-graph", "-r", "@-", "-T", "commit_id")
        code, _, err = self.run_tool("land", "made-up")
        self.assertEqual(code, 1)
        self.assertIn("conflicts in lib-foundation.txt: taken back", err)
        self.assertEqual(self.jj(self.root, "log", "--no-graph", "-r", "@-", "-T", "commit_id"), before)
        self.assertEqual((self.root / "lib-foundation.txt").read_text(), "the line's own\n")
        self.assertEqual(self.jj(self.root, "log", "--no-graph", "-r", "heads(all()) & conflicts()", "-T", "commit_id"), "")

    @cost("tool")
    def test_a_merge_waits_for_another_sessions_uncommitted_files(self):
        self.foundation()
        self.write("lib.txt", "two\n", message="the line moves")
        (self.root / "theirs.txt").write_text("uncommitted\n")
        code, _, err = self.run_tool("land", "made-up")
        self.assertEqual(code, 1)
        self.assertIn("uncommitted changes (theirs.txt)", err)

    @cost("tool")
    def test_trace_output_left_uncommitted_neither_holds_a_merge_back_nor_comes_along(self):
        self.foundation()
        self.write("lib.txt", "two\n", message="the line moves")
        self.write("llm-dlc/index.json", "stale\n")  # what a sync.py run left here, nobody's work
        self.write("llm-dlc/traces/sessions/made-up/summary.md", "a summary\n")
        self.jj(self.root, "describe", "-m", "Record session traces")
        code, out, err = self.run_tool("land", "made-up")
        self.assertEqual(code, 0, err)
        out = json.loads(out)
        self.assertIn("merged", out["landed"])
        self.assertEqual(sorted(out["dropped"]), ["llm-dlc/index.json", "llm-dlc/traces/sessions/made-up/summary.md"])
        self.assertEqual((self.root / "llm-dlc/index.json").read_text(), "base\nfoundation\n")  # written again
        self.assertEqual(self.jj(self.root, "diff", "-r", "@", "--name-only"), "")
        self.assertEqual(self.jj(self.root, "log", "--no-graph", "-r", 'heads(all()) & description("Record session traces")',
                                 "-T", "change_id"), "")  # the working copy it emptied is not left behind

    @cost("tool")
    def test_a_move_forward_drops_trace_output_and_is_taken_back_when_anothers_files_conflict(self):
        self.foundation()
        before = self.jj(self.root, "log", "--no-graph", "-r", "@-", "-T", "commit_id")
        self.write("llm-dlc/traces/loops.md", "stale\n")
        self.write("lib-foundation.txt", "another session's, uncommitted\n")  # the foundation added it too
        code, _, err = self.run_tool("land", "made-up")
        self.assertEqual(code, 1)
        self.assertIn("conflict with made-up-foundation's line in lib-foundation.txt: the line is left where it was", err)
        self.assertEqual(self.jj(self.root, "log", "--no-graph", "-r", "@-", "-T", "commit_id"), before)
        self.assertEqual((self.root / "lib-foundation.txt").read_text(), "another session's, uncommitted\n")
        (self.root / "lib-foundation.txt").unlink()
        code, out, err = self.run_tool("land", "made-up")
        self.assertEqual(code, 0, err)
        self.assertIn("moved forward", json.loads(out)["landed"])
        self.assertNotIn("dropped", json.loads(out))  # dropped the first time
        self.assertFalse((self.root / "llm-dlc/traces/loops.md").exists())
        self.assertEqual((self.root / "lib-foundation.txt").read_text(), "shared\n")

    @cost("tool")
    def test_of_llm_dlc_readme_only_a_change_to_its_session_table_is_trace_output(self):
        table = f"# Changes\n\n{brief_run.INDEX_BEGIN}\n| a session |\n{brief_run.INDEX_END}\n\nWritten by people.\n"
        self.write("llm-dlc/README.md", table, message="the page with its table")
        self.write("llm-dlc/README.md", table.replace("| a session |", "| a session |\n| another |"))
        self.assertTrue(brief_run.regenerable(self.root, "llm-dlc/README.md"))
        self.write("llm-dlc/README.md", table.replace("Written by people.", "Edited by a session."))
        self.assertFalse(brief_run.regenerable(self.root, "llm-dlc/README.md"))
        self.assertTrue(brief_run.regenerable(self.root, "llm-dlc/decisions/made-up.md"))
        self.assertFalse(brief_run.regenerable(self.root, "llm-dlc/decisions/made-up.jsonl"))
        self.assertFalse(brief_run.regenerable(self.root, "llm-dlc/loops/made-up.md"))


class KeepingTheQueue(Fixture):
    JOB = "20260101-000000-made-up"

    def back(self, job: str, status: str, attention: list[str] = ()) -> None:
        folder = self.statuses / "pipeline" / "results" / job
        folder.mkdir(parents=True)
        (folder / "result.json").write_text(json.dumps({"status": status, "summary": f"{job} {status}",
                                                        "attention": list(attention)}))

    @cost("tool")
    def test_the_watcher_collects_what_is_back_commits_it_alone_and_names_what_needs_triage(self):
        self.back(self.JOB, "passed")
        self.back("20260101-000001-made-up", "failed", ["out of memory at 2G"])
        (self.root / "theirs.txt").write_text("another session's, uncommitted\n")
        code, out, err = self.run_tool("collect", "made-up")
        self.assertEqual(code, 0, err)
        out = json.loads(out)
        self.assertEqual([r["id"] for r in out["collected"]], [self.JOB, "20260101-000001-made-up"])
        self.assertEqual([(r["id"], r["attention"]) for r in out["attention"]], [("20260101-000001-made-up", ["out of memory at 2G"])])
        committed = self.jj(self.root, "diff", "-r", "@-", "--name-only").split()
        self.assertEqual(committed, [f"verification/results/{self.JOB}/result.json",
                                     "verification/results/20260101-000001-made-up/result.json"])
        self.assertIn("Record verification results for 2 job(s)", self.jj(self.root, "log", "--no-graph", "-r", "@-", "-T", "description"))
        self.assertEqual(self.jj(self.root, "diff", "-r", "@", "--name-only").split(), ["theirs.txt"])  # left where it was
        self.assertEqual(self.run_tool("collect", "made-up")[1].strip(), "nothing to collect")

    @cost("tool")
    def test_jobs_waiting_with_no_runner_start_one_and_a_verification_loop_keeps_the_queue_while_it_runs(self):
        (self.statuses / "pipeline").mkdir()
        (self.statuses / "pipeline" / "pending").write_text(f"{self.JOB} made up, est. 1 min\n")
        run = self.run_of()
        with mock.patch.object(watch, "verification_running", return_value=None):
            thing = brief_run.tend(run)
        self.assertEqual((thing["kind"], thing["jobs"]), ("verification", [self.JOB]))
        end = time.time() + 20
        while not (self.statuses / "pipeline" / "ran").exists():
            self.assertLess(time.time(), end, "the runner was not started")
            time.sleep(0.1)
        self.back(self.JOB, "passed")
        with mock.patch.object(watch, "verification_running", return_value=4242), \
                mock.patch.object(watch, "tend_queue", return_value=None) as tend_queue:
            self.assertIsNone(brief_run.tend(run))
        tend_queue.assert_called_once()
        self.assertTrue((self.statuses / "pipeline" / "results" / self.JOB).exists())  # left to that loop

    @cost("tool")
    def test_each_look_at_the_queue_takes_the_streams_acknowledgements_and_tends_the_queue(self):
        self.write("llm-dlc/loops/made-up.md", brief(self.STREAMS, separate=False), message="the brief runs with the pipeline")
        run = self.run_of()
        run.update(run={"pid": None, "started": "2026-01-01T00:00:00Z"})
        with mock.patch.object(brief_run, "next_thing", return_value=None), \
                mock.patch.object(brief_run.inbox, "collect", return_value=[]) as collect, \
                mock.patch.object(brief_run, "tend", return_value=None) as tend:
            self.assertEqual(self.run_tool("wait", "made-up", "--timeout", "0")[0], 3)
        self.assertEqual([c.args[0] for c in collect.call_args_list], ["made-up-a", "made-up-b"])
        tend.assert_called_once()


class TheSyncLock(unittest.TestCase):
    def test_it_is_the_lock_sync_py_takes_on_the_repository(self):
        sys.path.insert(0, str(TOOLS))
        import sync
        with mock.patch.dict(os.environ, {"XDG_STATE_HOME": str(sync.STATE.parent)}):
            self.assertEqual(brief_run.sync_lock_path(sync.REPO), sync.Operation("check").lock_path)


class Watching(Fixture):
    def started(self, pid: int | None = None, ago: float = 0) -> brief_run.Run:
        run = self.run_of()
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - ago))
        run.update(run={"pid": pid or os.getpid(), "started": stamp})
        return run

    def wait(self, *args: str) -> tuple[int, str]:
        code, out, _ = self.run_tool("wait", "made-up", "--timeout", "0", *args)
        return code, out

    @cost("tool")
    def test_nothing_is_returned_before_there_is_a_run_and_while_it_is_quiet(self):
        self.assertEqual(self.wait()[0], 3)
        self.started()
        self.assertEqual(json.loads(self.wait()[1])["kind"], "nothing")

    @cost("tool")
    def test_a_loop_that_ended_blocked_is_a_question_with_how_to_answer_and_its_inbox(self):
        self.started()
        conductor.append_event(self.dir, type="blocked", needsVerdict=True, answers=["rerun", "leave"],
                               deadline=time.time() + 60, loop="a", brief="llm-dlc/loops/made-up-a.md", status="blocked: an answer")
        thing = json.loads(self.wait()[1])
        self.assertEqual((thing["kind"], thing["event"]["loop"]), ("question", "a"))
        self.assertIn("decide llm-dlc/loop-summaries/run-streams-made-up 1 rerun|leave", thing["answer"])
        self.assertIn("inbox.py list made-up-a --open", thing["inbox"])
        self.assertEqual(conductor.cmd_decide(self.dir, 1, "rerun", "its answer is in its inbox"), 0)
        recorded = decisions.fold(decisions.read("run-streams-made-up", self.root / "llm-dlc" / "decisions"))
        self.assertEqual([(d["decision"]["option"], d["decision"]["recovery"]["class"]) for d in recorded.values()], [("rerun", "cheap")])
        self.assertEqual(json.loads(self.wait()[1])["kind"], "nothing")

    @cost("tool")
    def test_while_the_foundation_runs_the_watcher_is_told_where_it_stands_at_the_interval(self):
        run = self.run_of()
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 4000))
        log = self.dir / "foundation.jsonl"
        self.dir.mkdir(parents=True)
        log.write_text(json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t1", "name": "Bash",
                                                                               "input": {"description": "Build the fixture"}}]}}) + "\n")
        run.update(foundation={"pid": os.getpid(), "started": stamp, "log": str(log), "folder": str(self.root)})
        thing = json.loads(self.wait()[1])
        self.assertEqual((thing["kind"], thing["toolCalls"], thing["command"]), ("foundation", 1, "Bash: Build the fixture"))
        self.assertRegex(thing["running"], r"^1 h 0\d min$")
        self.assertIn("base: a made-up brief", thing["lastCommit"])
        self.assertEqual(json.loads(self.wait()[1])["kind"], "nothing")  # the next one is an interval away

    @cost("tool")
    def test_a_summary_comes_at_the_interval_and_says_what_moved_since_the_last(self):
        self.started(ago=4000).update(foundation={"ended": "2026-01-01T00:00:00Z", "ok": True, "cost": 3.0, "landed": "abc"})
        (self.dir / "a.phase").write_text("running\n")
        (self.dir / "a.cycle").write_text("3\n")
        (self.dir / "a.cost").write_text("2.50\n")
        code, out = self.wait()
        self.assertEqual(code, 0)
        self.assertRegex(out.splitlines()[0], r"^### .* UTC · 1 h 0\d min into the run of llm-dlc/loops/made-up.md · \$5.50$")
        self.assertIn("- **foundation**: ended, $3.00; landed", out)
        self.assertIn("- **a**: working; cycle 3, 0 commits, $2.50; at ", out)
        self.assertIn("- **b**: working; cycle -, 0 commits, $0.00", out)
        self.assertNotIn("**merge**", out)  # there is no merge loop
        self.assertEqual(json.loads(self.wait()[1])["kind"], "nothing")  # the next one is an interval away
        self.run_tool("interval", "made-up", "0")
        self.assertNotIn("; at ", self.wait()[1].split("**b**")[0].split("**a**")[1])  # a's head has not moved

    @cost("tool")
    def test_a_summary_says_where_each_loops_time_went(self):
        run = self.started(ago=7200)
        t0 = time.time() - 7200
        def phases(label, *marks):
            (self.dir / f"{label}.phases").write_text("".join(f"{t0 + at}\t{phase}\n" for at, phase in marks))
        # a: an hour's work, twenty minutes for jobs, ten more of work, blocked ten, then done at 1 h 40
        phases("a", (0, "running"), (3600, "waiting for jobs"), (4800, "running"), (5400, "blocked: put to the watcher"),
               (6000, "finished: done"))
        phases("b", (0, "running"), (1800, "finished: done"), (1801, "finished: done; merged"))  # merged at once, while a ran on to 1 h 40
        out = self.wait()[1]
        a, b = (out.split(f"**{name}**")[1].split("- **")[0] for name in ("a", "b"))
        self.assertIn("time: 1 h 10 min working, 20 min waiting on jobs, 10 min blocked\n", a)
        self.assertIn("time: 30 min working, 1 h 10 min finished, others still running\n", b)
        self.assertEqual(brief_run.state(run)["loops"][1]["time"]["finished, others still running"], 4200)

    @cost("tool")
    def test_an_integration_check_that_stopped_passing_and_an_open_decision_are_each_told_once(self):
        run = self.started()
        run.report.parent.mkdir(parents=True, exist_ok=True)
        run.report.write_text("# Integration check\n\n- Result: failed (the script)\n")
        thing = json.loads(self.wait()[1])
        self.assertEqual((thing["kind"], thing["read"]), ("attention", "llm-dlc/loop-summaries/made-up-integration.md"))
        self.assertEqual(json.loads(self.wait()[1])["kind"], "nothing")
        with mock.patch.object(brief_run, "open_decisions", lambda run: ["made-up-D001"]):
            self.assertIn("made-up-D001 is open", json.loads(self.wait()[1])["what"])
            self.assertEqual(json.loads(self.wait()[1])["kind"], "nothing")

    @cost("tool")
    def test_a_run_that_ended_is_told_once_with_where_every_loop_stands(self):
        p = subprocess.Popen(["true"])
        p.wait()
        self.started(pid=p.pid)
        thing = json.loads(self.wait()[1])
        self.assertEqual((thing["kind"], [r["loop"] for r in thing["state"]["loops"]]), ("ended", ["a", "b"]))
        self.assertEqual(json.loads(self.wait()[1])["kind"], "nothing")


class ARunOfStreams(Fixture):
    """run-streams.sh itself, over stand-in loops: the streams it reads from the brief, none of them forked."""

    def answer(self, p: subprocess.Popen, seconds: float = 90) -> list[dict]:
        """Answer every question the run asks until it ends: `rerun` a blocked stream, and merge a finished one
        with brief_run.py merge, as the watcher does. Returns the questions, in order."""
        asked, until = [], time.time() + seconds
        while p.poll() is None and time.time() < until:
            event = conductor.pending(self.dir)
            if event is None:
                time.sleep(0.2)
                continue
            asked.append(event)
            if event["type"] == "merge":
                code, _, err = self.run_tool("merge", "made-up", event["loop"])
                self.assertEqual(code, 0, err)
            else:
                conductor.cmd_decide(self.dir, event["n"], "rerun", "b answered: the item is in a's inbox")
        return asked

    @cost("tool")
    def test_each_stream_is_merged_by_the_watcher_the_moment_it_is_finished_and_no_merge_loop_runs(self):
        p = self.streams(("made-up-a", ["blocked: an answer from b", "done"]), ("made-up-b", ["done"]),
                         RUN_STREAMS_WATCHER=str(self.dir), RUN_STREAMS_BLOCKED_WAIT="60")
        asked = self.answer(p)
        out, _ = p.communicate(timeout=60)
        self.assertEqual(p.returncode, 0, out)
        self.assertEqual(sorted((e["type"], e["loop"]) for e in asked), [("blocked", "a"), ("merge", "a"), ("merge", "b")])
        self.assertEqual(next(e for e in asked if e["type"] == "merge")["workspace"][:8], "made-up-")
        self.assertLess(asked.index(next(e for e in asked if e["type"] == "blocked")),
                        asked.index(next(e for e in asked if e == {**e, "type": "merge", "loop": "a"})))
        self.assertEqual(sorted(self.runs()), ["made-up-a", "made-up-a", "made-up-b"])  # the brief's own loop never ran
        self.assertIn("every stream is finished: merged a b; not merged none", out)
        self.assertIn("the streams fork no session", out)
        self.assertNotIn("compacting", out)
        # both streams' commits are on the default line, and the brief says so
        line = self.jj(self.root, "log", "--no-graph", "-r", "::@-", "-T", "description.first_line() ++ \"\\n\"")
        self.assertIn("made-up-a: done", line)
        self.assertIn("made-up-b: done", line)
        text = (self.root / "llm-dlc/loops/made-up.md").read_text()
        self.assertRegex(text, r"the watcher: merged stream \w \(\w+\), which says done\.\n.*merged stream \w \(\w+\), which says done\.\n- Status: done\n")
        self.assertEqual(self.jj(self.root, "diff", "-r", "@", "--name-only"), "")  # nothing is left uncommitted
        recorded = decisions.fold(decisions.read("run-streams-made-up", self.root / "llm-dlc" / "decisions"))
        self.assertEqual(sorted(d["decision"]["option"] for d in recorded.values()), ["merged", "merged", "rerun"])
        # again: nothing to merge, and nothing recorded twice
        code, again, _ = self.run_tool("merge", "made-up", "a")
        self.assertEqual((code, json.loads(again)["landed"]), (0, "nothing to land: the line already has it"))
        self.assertEqual((self.root / "llm-dlc/loops/made-up.md").read_text().count("merged stream a"), 1)
        rows = {r["loop"]: r for r in json.loads(self.run_tool("status", "made-up")[1])["loops"]}
        self.assertEqual({k: (r["status"], r["merged"]) for k, r in rows.items()}, {"a": ("done", True), "b": ("done", True)})

    @cost("tool")
    def test_a_stream_is_run_again_twice_at_most_and_then_left_without_asking(self):
        p = self.streams(("made-up-a", ["blocked: an answer"]), ("made-up-b", ["done"]),
                         RUN_STREAMS_WATCHER=str(self.dir), RUN_STREAMS_BLOCKED_WAIT="60")
        asked = self.answer(p)
        out, _ = p.communicate(timeout=60)
        self.assertEqual(p.returncode, 1, out)  # the brief is not done: a is blocked
        self.assertEqual([e["loop"] for e in asked if e["type"] == "blocked"], ["a", "a"])
        self.assertEqual(self.runs().count("made-up-a"), 3)
        self.assertIn("[a] blocked again after 2 rerun(s): left blocked", out)
        # a blocked stream is merged too, and the brief says what it left
        self.assertEqual(sorted(e["loop"] for e in asked if e["type"] == "merge"), ["a", "b"])
        self.assertIn("- Status: blocked: stream a: blocked: an answer\n", (self.root / "llm-dlc/loops/made-up.md").read_text())
        self.assertIn("finished: the brief llm-dlc/loops/made-up.md says blocked: stream a", out)

    @cost("tool")
    def test_without_an_answer_or_a_watcher_nothing_is_merged_and_the_end_says_how_to(self):
        p = self.streams(("made-up-a", ["blocked: an answer"]), ("made-up-b", ["done"]),
                         RUN_STREAMS_WATCHER=str(self.dir), RUN_STREAMS_BLOCKED_WAIT="1", RUN_STREAMS_MERGE_WAIT="1")
        out, _ = p.communicate(timeout=120)
        self.assertEqual(p.returncode, 1, out)  # the brief is not done: nothing was merged
        self.assertEqual(sorted(self.runs()), ["made-up-a", "made-up-b"])
        self.assertIn("every stream is finished: merged none; not merged a b", out)
        self.assertIn("[b] not merged: `python3 llm-dlc/tools/brief_run.py merge made-up b` merges it", out)
        (self.statuses / "runs").unlink()
        p = self.streams()  # no watcher: nothing is asked, and finished streams are not run again
        out, _ = p.communicate(timeout=120)
        self.assertEqual((p.returncode, (self.statuses / "runs").exists()), (1, False), out)
        self.assertNotIn("asking the watcher", out)
        self.assertIn("not merged a b", out)

    @cost("tool")
    def test_a_run_stopped_at_a_boundary_runs_nothing_again_starts_no_merge_and_is_continued_by_start(self):
        loop = self.root / "llm-dlc" / "tools" / "verification-loop.sh"  # the pipeline's stand-in: it collects nothing
        loop.write_text("#!/usr/bin/env bash\ntrap 'exit 0' USR1 INT TERM\nwhile :; do sleep 0.2; done\n")
        loop.chmod(0o755)
        self.write("llm-dlc/loops/made-up.md", brief(self.STREAMS, separate=False), message="the brief runs with the pipeline")
        job = "20260101-000000-made-up"
        for name, statuses in (("made-up-a", [f"waiting on jobs {job}", "done"]), ("made-up-b", ["done"]), ("made-up", ["done"])):
            (self.statuses / name).write_text("".join(x + "\n" for x in statuses))
        with mock.patch.dict(os.environ, {"RUN_STREAMS_POLL": "1", "RUN_STREAMS_STATUS_EVERY": "1", "RUN_STREAMS_MERGE_WAIT": "1"}):
            self.assertEqual(self.run_tool("start", "made-up")[0], 0)
            log = self.dir / "streams.log"
            self.until(lambda: f"[a] waiting for {job}" in log.read_text() and "[b] finished: done" in log.read_text(), log)
            self.assertIn("stops at a boundary", self.run_tool("stop", "made-up")[1])
            self.assertTrue(json.loads(self.run_tool("status", "made-up")[1])["stopping"])
            self.until(lambda: not self.alive(), log)
            self.assertIn("stopped at a boundary, every loop after its cycle under way", log.read_text())
            self.assertIn("the watcher keeps the queue", log.read_text())  # no verification loop of its own
            self.assertEqual(sorted(self.runs()), ["made-up-a", "made-up-b"])  # a was not run again
            self.assertNotIn("[a] asking the watcher to merge", log.read_text())  # nor put to the watcher to merge
            thing = json.loads(self.run_tool("wait", "made-up", "--timeout", "0")[1])
            self.assertEqual((thing["kind"], {r["loop"]: r["phase"] for r in thing["state"]["loops"]}["a"]), ("ended", "stopped at a boundary"))
            self.write(f"verification/results/{job}/result.json", "{}\n")  # the job is back
            self.assertEqual(self.run_tool("start", "made-up")[0], 0)  # continues: a's last cycle, then its merge
            self.until(lambda: not self.alive(), log)
        self.assertEqual((sorted(self.runs()[:2]), self.runs()[2:]), (["made-up-a", "made-up-b"], ["made-up-a"]))
        self.assertIn("[a] asking the watcher to merge", log.read_text())
        self.assertFalse(json.loads(self.run_tool("status", "made-up")[1])["stopping"])

    def alive(self) -> bool:
        pid = self.run_of().read()["run"]["pid"]
        try:
            os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            pass
        return watch.alive(pid)

    def until(self, done, log: Path, seconds: float = 90) -> None:
        end = time.time() + seconds
        while not done():
            self.assertLess(time.time(), end, log.read_text() if log.exists() else "no output")
            time.sleep(0.2)

    @cost("tool")
    def test_a_brief_with_no_streams_is_run_as_its_own_loop(self):
        self.write("llm-dlc/loops/made-up.md", brief(), message="the brief names no streams")
        p = self.streams(("made-up", ["done"]))
        out, _ = p.communicate(timeout=120)
        self.assertEqual((p.returncode, self.runs()), (0, ["made-up"]), out)
        self.assertIn("the brief names no streams: its own loop is the run", out)
        self.assertIn("[brief] ", out)

    @cost("tool")
    def test_the_watcher_starts_the_run_detached_and_is_told_when_it_ends(self):
        for name, statuses in (("made-up-a", ["done"]), ("made-up-b", ["done"])):
            (self.statuses / name).write_text("".join(s + "\n" for s in statuses))
        with mock.patch.dict(os.environ, {"RUN_STREAMS_POLL": "1", "RUN_STREAMS_STATUS_EVERY": "1", "RUN_STREAMS_MERGE_WAIT": "1"}):
            code, out, err = self.run_tool("start", "made-up")
        self.assertEqual(code, 0, err)
        run = self.run_of()
        pid = run.read()["run"]["pid"]
        self.assertIn("already under way", self.run_tool("start", "made-up")[1])
        until = time.time() + 120
        while watch.alive(pid) and time.time() < until:
            try:
                os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                pass
            time.sleep(0.2)
        code, out, _ = self.run_tool("wait", "made-up", "--timeout", "0")
        thing = json.loads(out)
        self.assertEqual(thing["kind"], "ended", (self.dir / "streams.log").read_text())
        self.assertEqual({r["loop"]: (r["status"], r["merged"]) for r in thing["state"]["loops"]},
                         {"a": ("done", False), "b": ("done", False)})  # nobody answered the merge questions
        self.assertEqual(sorted(self.runs()), ["made-up-a", "made-up-b"])


class TheOrderOfMerges(Fixture):
    """A trial merge finds where two streams' lines meet, an order holds the later one back, and a stream ahead in
    the order is merged while it is still at work."""

    def workspace(self, label: str) -> Path:
        folder = self.root.parent / f"root-made-up-{label}"
        self.jj(self.root, "workspace", "add", "--name", f"made-up-{label}", "-r", "@-", str(folder))
        return folder

    def set_status(self, folder: Path, label: str, status: str) -> None:
        self.write(f"llm-dlc/loops/made-up-{label}.md", brief(workspace=f"made-up-{label}", status=status), folder,
                   f"made-up-{label}: {status}")

    @cost("tool")
    def test_a_trial_merge_names_the_files_two_lines_meet_in_and_changes_nothing(self):
        a, b = self.workspace("a"), self.workspace("b")
        self.write("llm-dlc/index.json", "base\na\n", a)
        self.write("lib.txt", "a's\n", a, "a: the shared file")
        self.write("llm-dlc/index.json", "base\nb\n", b)
        self.write("lib.txt", "b's\n", b, "b: the shared file")
        self.write("left.txt", "not committed\n", b)
        before = self.jj(self.root, "log", "--no-graph", "-r", "all()", "-T", "commit_id ++ \"\\n\"")
        code, out, err = self.run_tool("trial", "made-up")
        self.assertEqual(code, 0, err)
        got = json.loads(out)
        pairs = {(p["a"], p["b"]): p for p in got["pairs"]}
        self.assertEqual(pairs[("a", "b")]["conflicts"], ["lib.txt"])
        self.assertEqual(pairs[("a", "b")]["regenerated"], ["llm-dlc/index.json"])  # generated: never a reason for an order
        self.assertEqual(pairs[("the default line", "a")]["conflicts"], [])
        self.assertIn("propose a merge order to the user", got["note"])
        self.assertEqual(self.jj(self.root, "log", "--no-graph", "-r", "all()", "-T", "commit_id ++ \"\\n\""), before)
        self.assertEqual((b / "left.txt").read_text(), "not committed\n")

    @cost("tool")
    def test_lines_that_do_not_meet_need_no_order(self):
        a, b = self.workspace("a"), self.workspace("b")
        self.write("a.txt", "a\n", a, "a: its own file")
        self.write("b.txt", "b\n", b, "b: its own file")
        got = json.loads(self.run_tool("trial", "made-up")[1])
        self.assertEqual([p["conflicts"] for p in got["pairs"]], [[], [], []])
        self.assertIn("in any order", got["note"])

    @cost("tool")
    def test_an_order_holds_a_stream_back_and_the_one_before_it_is_merged_while_it_still_works(self):
        a, b = self.workspace("a"), self.workspace("b")
        self.write("a.txt", "a\n", a, "a: the first half")
        self.write("a-later.txt", "not committed yet\n", a)
        self.write("b.txt", "b\n", b)
        self.set_status(b, "b", "done")
        self.assertEqual(self.run_tool("order", "made-up", "a", "a")[0], 1)
        self.assertEqual(self.run_tool("order", "made-up", "a", "c")[0], 1)
        code, out, _ = self.run_tool("order", "made-up", "a", "b")
        self.assertEqual((code, json.loads(out)["order"]), (0, ["a", "b"]))
        code, _, err = self.run_tool("merge", "made-up", "b")
        self.assertEqual(code, 1)
        self.assertIn("first `python3 llm-dlc/tools/brief_run.py merge made-up a --early`", err)
        # the watcher's question for b says the same
        run = self.run_of()
        run.update(run={"pid": os.getpid(), "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
        conductor.append_event(self.dir, type="merge", needsVerdict=True, answers=["merged", "leave"], deadline=time.time() + 60,
                               loop="b", workspace="made-up-b", brief="llm-dlc/loops/made-up-b.md", status="done")
        thing = json.loads(self.run_tool("wait", "made-up", "--timeout", "0")[1])
        self.assertEqual([f["stream"] for f in thing["order"]["first"]], ["a"])
        # a's line so far comes in; what it has not committed stays with it, and the brief is still working
        code, out, err = self.run_tool("merge", "made-up", "a", "--early")
        self.assertEqual(code, 0, err)
        self.assertTrue(json.loads(out)["early"])
        self.assertTrue((self.root / "a.txt").exists())
        self.assertFalse((self.root / "a-later.txt").exists())
        self.assertEqual((a / "a-later.txt").read_text(), "not committed yet\n")
        text = (self.root / "llm-dlc/loops/made-up.md").read_text()
        self.assertRegex(text, r"the watcher: merged stream a's line so far \(\w+\), while it is still at work\.\n- Status: working\n")
        # now b, and the brief stays working: a is merged so far, and not finished
        code, out, err = self.run_tool("merge", "made-up", "b")
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out).get("briefStatus", "working"), "working")
        self.assertIn("- Status: working\n", (self.root / "llm-dlc/loops/made-up.md").read_text())
        # a's later commits come in by its own merge, when it is finished
        self.jj(a, "commit", "-m", "a: the second half")
        self.set_status(a, "a", "done")
        code, out, err = self.run_tool("merge", "made-up", "a")
        self.assertEqual(code, 0, err)
        self.assertTrue((self.root / "a-later.txt").exists())
        self.assertIn("- Status: done\n", (self.root / "llm-dlc/loops/made-up.md").read_text())

    @cost("tool")
    def test_an_order_can_be_overridden_and_cleared(self):
        a, b = self.workspace("a"), self.workspace("b")
        self.write("a.txt", "a\n", a, "a: its file")
        self.write("b.txt", "b\n", b)
        self.set_status(b, "b", "done")
        self.run_tool("order", "made-up", "a", "b")
        self.assertEqual(self.run_tool("merge", "made-up", "b", "--out-of-order")[0], 0)
        self.assertTrue((self.root / "b.txt").exists())
        self.assertIsNone(json.loads(self.run_tool("order", "made-up", "--clear")[1])["order"])


TMUX = textwrap.dedent("""\
    #!/usr/bin/env python3
    # tmux's stand-in: one pane, %7, in window 3; what it is running is the file pane-command (claude without one).
    import os, sys
    from pathlib import Path
    state = Path(os.environ["STATUSES"])
    args = sys.argv[1:]
    command = (state / "pane-command").read_text().strip() if (state / "pane-command").exists() else "claude"
    if args[0] == "display-message":
        if args[args.index("-t") + 1] not in ("3", "%7"):
            sys.exit("can't find pane")
        print(args[-1].replace("#{pane_id}", "%7").replace("#{session_name}:#{window_index}.#{pane_index}", "main:3.0")
              .replace("#{pane_current_command}", command))
    elif args[0] == "send-keys":
        with open(state / "typed", "a") as f:
            f.write(args[-1] + "\\n")
""")


class Helpers(Fixture):
    """Sessions the user has open take work the run has no owner for: a narrow brief, a workspace of their own, and
    the watcher's merge."""

    def setUp(self):
        super().setUp()
        tmux = Path(self.tmp.name) / "bin" / "tmux"
        tmux.write_text(TMUX)
        tmux.chmod(0o755)
        self.task = Path(self.tmp.name) / "task.md"
        self.task.write_text("Make `helped.txt` say what the run needs.\n")
        self.folder = self.root.parent / "root-made-up-helper"

    @cost("tool")
    def test_a_helper_is_a_pane_the_user_names_and_never_a_shell_prompt(self):
        self.assertEqual(self.run_tool("helper", "made-up", "add", "helper", "--at", "window 3")[0], 1)
        code, _, err = self.run_tool("helper", "made-up", "add", "helper", "--at", "tmux 9")
        self.assertEqual(code, 1)
        self.assertIn("no tmux pane at 9", err)
        (self.statuses / "pane-command").write_text("bash\n")
        code, _, err = self.run_tool("helper", "made-up", "add", "helper", "--at", "tmux 3")
        self.assertEqual(code, 1)
        self.assertIn("at a shell prompt", err)
        (self.statuses / "pane-command").unlink()
        code, out, err = self.run_tool("helper", "made-up", "add", "helper", "--at", "tmux 3")
        self.assertEqual(code, 0, err)
        got = json.loads(out)
        self.assertEqual((got["where"], got["workspace"]), ("main:3.0", "made-up-helper"))
        self.assertIn("low-hanging work", got["role"])
        code, _, err = self.run_tool("helper", "made-up", "add", "specialist", "--at", "tmux 3")
        self.assertEqual(code, 1)
        self.assertIn("is the helper helper's", err)
        self.assertEqual(self.run_tool("helper", "made-up", "task", "nobody", "--title", "x", "--file", str(self.task))[0], 1)
        self.assertNotIn("made-up-helper", self.jj(self.root, "workspace", "list"))  # a workspace is made for a task only

    @cost("tool")
    def test_a_task_is_a_narrow_brief_typed_into_the_pane_and_its_work_is_merged_by_the_watcher(self):
        self.run_tool("helper", "made-up", "add", "helper", "--at", "tmux 3")
        code, out, err = self.run_tool("helper", "made-up", "task", "helper", "--title", "The orphaned file", "--file", str(self.task))
        self.assertEqual(code, 0, err)
        got = json.loads(out)
        self.assertEqual((got["task"], got["folder"]), ("helper-T001", str(self.folder)))
        text = Path(got["file"]).read_text()
        self.assertIn("# Helper task helper-T001 for the run of `llm-dlc/loops/made-up.md`: The orphaned file", text)
        self.assertIn(f"Work only in the jj workspace `made-up-helper`, at `{self.folder}`", text)
        self.assertIn("Don't merge, push, or land anything", text)
        self.assertIn("helper made-up done helper-T001 --report-file FILE", text)
        self.assertTrue(text.rstrip().endswith("Make `helped.txt` say what the run needs."))
        typed = (self.statuses / "typed").read_text().splitlines()
        self.assertEqual((typed[0], typed[1]), (got["line"], "Enter"))
        self.assertIn(got["file"], typed[0])
        self.assertIn(str(self.folder), (self.statuses / "adopted").read_text())  # the session logs it lacked
        # one at a time
        code, _, err = self.run_tool("helper", "made-up", "task", "helper", "--title", "Another", "--file", str(self.task))
        self.assertEqual(code, 1)
        self.assertIn("not merged yet (helper-T001)", err)
        # the helper works there, commits, and says it is done; the line moves meanwhile
        self.write("helped.txt", "what the run needs\n", self.folder, "helper: the orphaned file")
        self.write("lib.txt", "two\n", self.root, "the line moves on")
        run = self.run_of()
        run.update(run={"pid": os.getpid(), "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
        code, out, err = self.run_tool("wait", "made-up", "--timeout", "0")
        self.assertEqual(json.loads(out or "{}").get("kind"), "nothing", err)
        self.assertEqual(self.run_tool("helper", "made-up", "done", "helper-T001")[0], 1)  # a report is asked for
        code, out, err = self.run_tool("helper", "made-up", "done", "helper-T001", "--report", "Wrote helped.txt; nothing is left.")
        self.assertEqual(code, 0, err)
        thing = json.loads(self.run_tool("wait", "made-up", "--timeout", "0")[1])
        self.assertEqual((thing["kind"], thing["task"], thing["report"]), ("helper", "helper-T001", "Wrote helped.txt; nothing is left."))
        self.assertEqual(len(thing["commits"]), 1, thing)
        self.assertIn("the orphaned file", thing["commits"][0])
        self.assertEqual(json.loads(self.run_tool("wait", "made-up", "--timeout", "0")[1])["kind"], "nothing")  # told once
        code, out, err = self.run_tool("helper", "made-up", "merge", "helper-T001")
        self.assertEqual(code, 0, err)
        self.assertEqual((self.root / "helped.txt").read_text(), "what the run needs\n")
        self.assertEqual((self.root / "lib.txt").read_text(), "two\n")
        # its next task starts from the line as it is now, in the same workspace
        code, out, err = self.run_tool("helper", "made-up", "task", "helper", "--title", "A second", "--file", str(self.task), "--no-send")
        self.assertEqual(code, 0, err)
        self.assertEqual((json.loads(out)["task"], json.loads(out)["sent"]), ("helper-T002", "not typed into its pane"))
        self.assertEqual((self.folder / "lib.txt").read_text(), "two\n")
        self.assertEqual(len((self.statuses / "typed").read_text().splitlines()), 2)
        listed = json.loads(self.run_tool("helper", "made-up", "list")[1])
        self.assertEqual([(t["id"], bool(t["merged"])) for t in listed["helper"]["tasks"]], [("helper-T001", True), ("helper-T002", False)])

    @cost("tool")
    def test_a_pane_back_at_a_shell_prompt_is_typed_nothing(self):
        self.run_tool("helper", "made-up", "add", "helper", "--at", "tmux 3")
        (self.statuses / "pane-command").write_text("zsh\n")
        code, _, err = self.run_tool("helper", "made-up", "task", "helper", "--title", "The orphaned file", "--file", str(self.task))
        self.assertEqual(code, 1)
        self.assertIn("nothing was typed there", err)
        self.assertFalse((self.statuses / "typed").exists())
        self.assertNotIn("made-up-helper", self.jj(self.root, "workspace", "list"))  # and nothing was made for it


class AStreamRunAgain(Fixture):
    """A stream whose loop ended is run again inside the run, at the watcher's word, and a scope that holds only what
    an ended loop left is cleared before a loop starts."""

    def until_ended(self, seconds: float = 90) -> list[dict]:
        """Answer what the run asks until it ends: a blocked stream is asked to be run again (`rerun`) and its
        question answered `leave`, a finished one is merged. Returns the questions, in order."""
        asked, until = [], time.time() + seconds
        pid = self.run_of().read()["run"]["pid"]
        while watch.alive(pid) and time.time() < until:
            try:
                os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                pass
            event = conductor.pending(self.dir)
            if event is None or event.get("type") == "ended":
                time.sleep(0.2)
                continue
            asked.append(event)
            if event["type"] == "merge":
                code, _, err = self.run_tool("merge", "made-up", event["loop"])
                self.assertEqual(code, 0, err)
            else:
                code, out, err = self.run_tool("rerun", "made-up", event["loop"])
                self.assertEqual(code, 0, err)
                self.assertIn("question (event", json.loads(out)["next"])
                conductor.cmd_decide(self.dir, event["n"], "leave", "it is run again by a request, not by this answer")
        return asked

    @cost("tool")
    def test_a_stream_that_ended_is_run_again_inside_the_run_and_merged_when_it_is_finished(self):
        for name, statuses in (("made-up-a", ["blocked: its session was killed", "done"]), ("made-up-b", ["done"])):
            (self.statuses / name).write_text("".join(s + "\n" for s in statuses))
        with mock.patch.dict(os.environ, {"RUN_STREAMS_POLL": "1", "RUN_STREAMS_STATUS_EVERY": "1", "RUN_STREAMS_RERUN_POLL": "0.2"}):
            self.assertEqual(self.run_tool("start", "made-up")[0], 0)
            asked = self.until_ended()
        log = (self.dir / "streams.log").read_text()
        self.assertEqual(sorted((e["type"], e["loop"]) for e in asked), [("blocked", "a"), ("merge", "a"), ("merge", "b")], log)
        self.assertIn("[a] run again inside the run, as the watcher asked", log)
        self.assertEqual(self.runs().count("made-up-a"), 2)
        self.assertIn("every stream is finished: merged a b; not merged none", log)
        self.assertFalse((self.dir / "rerun" / "a").exists())
        self.assertIn("- Status: done\n", (self.root / "llm-dlc/loops/made-up.md").read_text())

    @cost("tool")
    def test_after_the_run_has_ended_a_rerun_starts_it_again_for_that_stream(self):
        p = self.streams(("made-up-a", ["blocked: its session was killed", "done"]), ("made-up-b", ["done"]))
        out, _ = p.communicate(timeout=120)
        self.assertEqual((p.returncode, self.runs().count("made-up-a")), (1, 1), out)
        with mock.patch.dict(os.environ, {"RUN_STREAMS_POLL": "1", "RUN_STREAMS_STATUS_EVERY": "1", "RUN_STREAMS_RERUN_POLL": "0.2"}):
            code, out, err = self.run_tool("rerun", "made-up", "a")
            self.assertEqual(code, 0, err)
            self.assertIn("the run itself had ended: started again, for this stream", out)
            asked = self.until_ended()
        log = (self.dir / "streams.log").read_text()
        self.assertIn("[a] its brief says blocked: its session was killed, and the watcher asked for it to be run again", log)
        self.assertEqual(sorted((e["type"], e["loop"]) for e in asked), [("merge", "a"), ("merge", "b")], log)
        self.assertEqual((self.runs().count("made-up-a"), self.runs().count("made-up-b")), (2, 1))
        self.assertEqual(self.run_tool("rerun", "made-up", "c")[0], 1)

    @cost("tool")
    def test_a_scope_that_holds_only_what_an_ended_loop_left_is_stopped_before_the_loop_starts(self):
        base = Path(self.tmp.name)
        systemctl = base / "bin" / "systemctl"
        # systemd's stand-in: the scope of stream a is active until it is stopped, and holds one process
        systemctl.write_text(textwrap.dedent("""\
            #!/usr/bin/env bash
            echo "$*" >>"$STATUSES/systemctl"
            case "$2" in
              is-active) [[ "$4" == feature-loop-made-up-a.scope && ! -e "$STATUSES/stopped" ]] ;;
              show) echo /left ;;
              stop) touch "$STATUSES/stopped" ;;
            esac
        """))
        systemctl.chmod(0o755)
        left = subprocess.Popen(["sleep", "60"], cwd=base)  # a test the ended loop left running, in a folder of its own
        self.addCleanup(left.kill)
        (base / "cgroup" / "left").mkdir(parents=True)
        (base / "cgroup" / "left" / "cgroup.procs").write_text(f"{left.pid}\n")
        p = self.streams(("made-up-a", ["done"]), ("made-up-b", ["done"]), RUN_STREAMS_CGROUP_ROOT=str(base / "cgroup"))
        out, _ = p.communicate(timeout=120)
        self.assertIn("[a] feature-loop-made-up-a.scope holds only what an ended loop left (1 process(es)): stopping it", out)
        self.assertNotIn("[b] feature-loop-made-up-b.scope holds", out)
        self.assertIn("--user stop feature-loop-made-up-a.scope", (self.statuses / "systemctl").read_text())
        self.assertEqual(sorted(self.runs()), ["made-up-a", "made-up-b"])


class TheWatchersOwnShell(Fixture):
    @cost("tool")
    def test_a_session_that_carries_a_runs_variables_does_not_start_one(self):
        self.assertEqual(json.loads(self.run_tool("preflight", "made-up")[1])["blocking"], [])
        with mock.patch.dict(os.environ, {"RUN_STREAMS_WATCHER": "/somewhere/else", "LOOP_CONDUCTOR": "/another"}):
            blocking = json.loads(self.run_tool("preflight", "made-up")[1])["blocking"]
        self.assertEqual(len(blocking), 1)
        self.assertIn("LOOP_CONDUCTOR, RUN_STREAMS_WATCHER", blocking[0])


if __name__ == "__main__":
    unittest.main()
