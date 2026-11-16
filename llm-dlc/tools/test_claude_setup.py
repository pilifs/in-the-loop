#!/usr/bin/env python3
"""Tests for claude_setup.py: what it finds a session has loaded besides the plugin, the flags of a clean launch,
and what `check` concludes. Run: python3 llm-dlc/tools/test_claude_setup.py
No model is called and nothing of this machine's Claude Code setup is read: the directories are made up,
CLAUDE_CONFIG_DIR points at one of them, and `check` runs against a stand-in `claude` on PATH that answers a probe
with a start-up report chosen by its flags."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import claude_setup

REPO = Path(__file__).resolve().parents[2]
sys.path.append(str(REPO / "lib/tools"))
from cost_tier import cost  # noqa: E402
sys.path.append(str(Path(__file__).resolve().parents[2] / "lib/tools"))
from cost_tier import cost  # noqa: E402

BUILTIN = [{"name": "cc-plugin-made-up", "path": "builtin"}]


def init(mcp=(), plugins=(), skills=("simplify",), agents=("Explore",), commands=(), style="default"):
    return {"type": "system", "subtype": "init", "mcp_servers": [{"name": m, "status": "connected"} for m in mcp],
            "plugins": BUILTIN + [{"name": p, "path": f"/made/up/{p}"} for p in plugins], "skills": list(skills),
            "agents": list(agents), "slash_commands": [*skills, "clear", *commands], "output_style": style}


class Made(unittest.TestCase):
    """A made-up machine: a home checkout, the user's project beside it, and their Claude Code configuration."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()
        self.home, self.project, self.config = self.tmp / "work/home", self.tmp / "work/project", self.tmp / "config"
        for d in (self.home / ".claude", self.project / ".claude", self.config):
            d.mkdir(parents=True)
        (self.home / "CLAUDE.md").write_text("# the checkout's own procedure\n")
        patch = mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.config)})
        patch.start()
        self.addCleanup(patch.stop)

    def names(self, found, kind):
        return [x["name"] for x in found if x["kind"] == kind]


class CleanFlagsTest(Made):
    def test_a_clean_launch_leaves_out_the_users_settings_and_every_mcp_server(self):
        flags = claude_setup.clean_flags(self.home)
        self.assertEqual(claude_setup.flag_value(flags, "--setting-sources"), "project,local")
        self.assertIn("--strict-mcp-config", flags)
        self.assertNotIn("--mcp-config", flags)
        self.assertEqual(claude_setup.sources(flags), {"project", "local"})

    def test_it_excludes_the_users_memory_and_the_memory_of_the_directories_above_by_path(self):
        (self.tmp / "work/CLAUDE.md").write_text("# a made-up note above the checkout\n")
        (self.tmp / "work/.claude/rules").mkdir(parents=True)
        (self.tmp / "work/.claude/rules/style.md").write_text("made up\n")
        excluded = claude_setup.excluded_by(claude_setup.clean_flags(self.home))
        self.assertIn(str(self.config / "CLAUDE.md"), excluded)
        self.assertIn(str(self.config / "rules/**"), excluded)
        self.assertIn(str(self.tmp / "work/CLAUDE.md"), excluded)
        self.assertIn(str(self.tmp / "work/.claude/rules/style.md"), excluded)
        self.assertFalse(any(e.startswith(str(self.home)) for e in excluded), "the checkout's own memory stays")

    def test_each_flag_is_one_line_for_a_shell_to_read(self):
        self.assertFalse(any("\n" in flag for flag in claude_setup.clean_flags(self.home)))


class LaunchFlagsTest(unittest.TestCase):
    def test_only_the_flags_that_decide_what_loads_are_kept_as_given(self):
        argv = ["claude", "--model", "opus", "--setting-sources", "project,local", "--strict-mcp-config",
                "--mcp-config", "a.json", "b.json", "--plugin-dir=/made/up", "-p", "a prompt", "--settings", "{}",
                "--resume", "0f0f"]
        self.assertEqual(claude_setup.loading_flags(argv),
                         ["--setting-sources", "project,local", "--strict-mcp-config", "--mcp-config", "a.json",
                          "b.json", "--plugin-dir=/made/up", "--settings", "{}"])

    def test_a_plain_launch_reads_every_source_and_safe_mode_none(self):
        self.assertEqual(claude_setup.sources([]), {"user", "project", "local"})
        self.assertEqual(claude_setup.sources(["--safe-mode"]), set())
        self.assertEqual(claude_setup.sources(["--setting-sources=user"]), {"user"})


class BeyondTest(unittest.TestCase):
    def test_what_a_clean_session_also_has_is_not_extra(self):
        self.assertEqual(claude_setup.beyond(init(), init()), [])

    def test_everything_else_is_listed_by_kind(self):
        theirs = init(mcp=["claude.ai Made Up"], plugins=["other"], skills=("simplify", "other:lint", "notes"),
                      agents=("Explore", "reviewer"), commands=("deploy",), style="terse")
        found = claude_setup.beyond(theirs, init())
        self.assertEqual({(x["kind"], x["name"]) for x in found},
                         {("mcp server", "claude.ai Made Up"), ("plugin", "other"), ("skill", "other:lint"),
                          ("skill", "notes"), ("agent", "reviewer"), ("command", "deploy"), ("output style", "terse")})

    def test_the_plugin_itself_and_its_skill_are_not_extra(self):
        theirs = init(plugins=["in-the-loop"], skills=("simplify", "in-the-loop:prove-java-change"))
        self.assertEqual(claude_setup.beyond(theirs, init()), [])

    def test_a_built_in_plugin_is_never_listed(self):
        self.assertEqual(claude_setup.loaded(init())["plugin"], set())


class OnDiskTest(Made):
    def test_the_users_and_the_projects_memory_and_hooks_are_found(self):
        (self.config / "CLAUDE.md").write_text("# made-up preferences\n")
        (self.project / "CLAUDE.md").write_text("# a made-up project\n")
        (self.project / "CLAUDE.local.md").write_text("made up\n")
        (self.config / "settings.json").write_text(json.dumps({"hooks": {"Stop": [], "PreToolUse": []}, "env": {"MADE_UP": "v"}}))
        found = claude_setup.on_disk(self.project, [], self.home)
        self.assertEqual(self.names(found, "memory file"),
                         [str(self.config / "CLAUDE.md"), str(self.project / "CLAUDE.md"), str(self.project / "CLAUDE.local.md")])
        self.assertEqual(self.names(found, "hooks"), ["PreToolUse, Stop"])
        self.assertNotIn("MADE_UP", json.dumps(found), "a setting's value is never reported")

    def test_a_launch_without_a_source_does_not_read_its_files(self):
        (self.config / "CLAUDE.md").write_text("# made-up preferences\n")
        (self.config / "settings.json").write_text(json.dumps({"hooks": {"Stop": []}}))
        (self.project / "CLAUDE.md").write_text("# a made-up project\n")
        found = claude_setup.on_disk(self.project, ["--setting-sources", "project,local"], self.home)
        self.assertEqual(self.names(found, "memory file"), [str(self.project / "CLAUDE.md")])
        self.assertEqual(self.names(found, "hooks"), [])
        self.assertEqual(claude_setup.on_disk(self.project, ["--safe-mode"], self.home), [])

    def test_a_clean_session_in_the_checkout_has_nothing_extra_on_disk(self):
        (self.config / "CLAUDE.md").write_text("# made-up preferences\n")
        (self.tmp / "work/CLAUDE.md").write_text("# a made-up note above the checkout\n")
        (self.home / ".claude/settings.json").write_text(json.dumps({"hooks": {"Stop": []}}))
        self.assertEqual(claude_setup.on_disk(self.home, claude_setup.clean_flags(self.home), self.home), [])
        plain = claude_setup.on_disk(self.home, [], self.home)  # the same directory, started as a plain `claude`
        self.assertEqual(self.names(plain, "memory file"), [str(self.config / "CLAUDE.md"), str(self.tmp / "work/CLAUDE.md")])

    def test_managed_settings_are_listed_where_they_exist(self):
        self.assertEqual(claude_setup.managed(self.tmp / "nothing-here"), [])
        (self.tmp / "etc").mkdir()
        (self.tmp / "etc/managed-settings.json").write_text("{}")
        self.assertEqual(self.names(claude_setup.managed(self.tmp / "etc"), "managed settings"),
                         [str(self.tmp / "etc/managed-settings.json")])


# The stand-in: a probe gets a start-up report by its flags, `plugin list` a made-up listing. $STANDIN_FAIL names
# the launches that don't answer: clean, plain or haiku.
STANDIN = r'''#!/usr/bin/env python3
import json, os, sys
args, fail = sys.argv[1:], os.environ.get("STANDIN_FAIL", "").split(",")
with open(os.environ["STANDIN_LOG"], "a") as f:
    f.write(json.dumps({"args": args, "cwd": os.getcwd(), "connectors": os.environ.get("ENABLE_CLAUDEAI_MCP_SERVERS")}) + "\n")
if args[:2] == ["plugin", "list"]:
    print(os.environ.get("STANDIN_PLUGINS", "[]"))
    sys.exit(0)
clean = "--strict-mcp-config" in args
if ("clean" if clean else "plain") in fail or ("haiku" in fail and "haiku" in args):
    sys.exit(1)
report = {"type": "system", "subtype": "init", "plugins": [{"name": "cc-plugin-made-up", "path": "builtin"}],
          "skills": ["simplify"], "agents": ["Explore"], "slash_commands": ["simplify", "clear"],
          "output_style": "default", "mcp_servers": []}
if not clean:
    report.update(json.loads(os.environ.get("STANDIN_PLAIN", "{}")))
print(json.dumps(report))
print(json.dumps({"type": "result", "subtype": "success", "result": "ok"}))
'''


@cost("tool")
class CheckTest(Made):
    def setUp(self):
        super().setUp()
        bin = self.tmp / "bin"
        bin.mkdir()
        (bin / "claude").write_text(STANDIN)
        (bin / "claude").chmod(0o755)
        self.log = self.tmp / "standin.jsonl"
        self.env = {"PATH": f"{bin}:{os.environ['PATH']}", "STANDIN_LOG": str(self.log)}

    def check(self, flags=(), cwd=None, **env):
        here = {"argv": ["claude", *flags], "cwd": str(cwd or self.project)}
        with mock.patch.dict(os.environ, {**self.env, **env}), mock.patch.object(claude_setup, "session", lambda: here), \
                mock.patch.object(claude_setup, "MANAGED", self.tmp / "nothing-here"):
            return claude_setup.check(self.home)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_a_session_with_a_connector_a_plugin_and_a_memory_file_is_not_clean(self):
        (self.project / "CLAUDE.md").write_text("# a made-up project\n")
        plain = {"mcp_servers": [{"name": "claude.ai Made Up", "status": "connected"}],
                 "plugins": [{"name": "other", "path": "/made/up/other"}, {"name": "in-the-loop", "path": "/made/up/itl"}]}
        found = self.check(STANDIN_PLAIN=json.dumps(plain))
        self.assertFalse(found["clean"])
        self.assertEqual([(x["kind"], x["name"]) for x in found["loaded"]],
                         [("mcp server", "claude.ai Made Up"), ("plugin", "other"), ("memory file", str(self.project / "CLAUDE.md"))])
        self.assertEqual((found["loop"]["isolated"], found["loop"]["remaining"]), (True, []))
        self.assertTrue(found["relaunch"].endswith("claude_setup.py launch"))
        report = claude_setup.report(found)
        self.assertTrue(report.startswith(claude_setup.WARNING))
        self.assertIn("not recommended", report)

    def test_the_two_probes_are_the_sessions_own_launch_and_a_clean_one_in_the_checkout(self):
        self.check(flags=["--plugin-dir", "/made/up", "--model", "opus"])
        probes = [c for c in self.calls() if "-p" in c["args"]]
        theirs = next(c for c in probes if c["cwd"] == str(self.project))
        ours = next(c for c in probes if c["cwd"] == str(self.home))
        self.assertIn("--plugin-dir", theirs["args"])
        self.assertNotIn("opus", theirs["args"])
        self.assertNotIn("--strict-mcp-config", theirs["args"])
        self.assertEqual((theirs["connectors"], ours["connectors"]), (None, "false"))
        for flag in claude_setup.clean_flags(self.home):
            self.assertIn(flag, ours["args"])
        for call in probes:  # one word, no tools, no transcript
            self.assertEqual(call["args"][call["args"].index("--tools") + 1], "")
            self.assertIn("--no-session-persistence", call["args"])

    def test_a_session_started_clean_in_the_checkout_is_clean(self):
        (self.config / "CLAUDE.md").write_text("# made-up preferences\n")
        found = self.check(flags=claude_setup.clean_flags(self.home), cwd=self.home,
                           STANDIN_PLUGINS=json.dumps([{"id": "other@made-up", "enabled": True, "scope": "user"}]))
        self.assertEqual((found["loaded"], found["clean"]), ([], True))
        self.assertNotIn("not recommended", claude_setup.report(found))

    def test_a_plugin_the_listing_calls_enabled_is_added_when_the_probe_missed_it(self):
        listing = [{"id": "other@made-up", "enabled": True, "scope": "user"},
                   {"id": "off@made-up", "enabled": False, "scope": "user"},
                   {"id": "in-the-loop@in-the-loop", "enabled": True, "scope": "user"}]
        found = self.check(STANDIN_PLUGINS=json.dumps(listing))
        self.assertEqual([(x["kind"], x["name"]) for x in found["loaded"]], [("plugin", "other")])

    def test_when_a_clean_launch_does_not_answer_the_loop_is_not_isolated_and_nothing_is_called_clean(self):
        found = self.check(STANDIN_FAIL="clean")
        self.assertEqual((found["loop"]["isolated"], found["loaded"], found["clean"]), (False, None, False))
        self.assertIn("--no-isolation", claude_setup.report(found))

    def test_a_probe_falls_back_to_the_accounts_default_model(self):
        found = self.check(STANDIN_FAIL="haiku")
        self.assertTrue(found["clean"], found)
        self.assertTrue(any("-p" in c["args"] and "--model" not in c["args"] for c in self.calls()))


@cost("tool")
class CommandTest(unittest.TestCase):
    @cost("tool")
    def test_check_refuses_in_a_development_checkout_and_flags_prints_one_per_line(self):
        tool = [sys.executable, str(REPO / "llm-dlc/tools/claude_setup.py")]
        env = {**os.environ, "IN_THE_LOOP_MODE": "development"}
        refused = subprocess.run([*tool, "check"], capture_output=True, text=True, env=env)
        self.assertEqual(refused.returncode, 2)
        self.assertIn("development checkout", refused.stderr)
        flags = subprocess.run([*tool, "flags"], capture_output=True, text=True, env=env)
        self.assertEqual(flags.stdout.splitlines()[:3], ["--setting-sources", "project,local", "--strict-mcp-config"])

    @cost("tool")
    def test_launch_starts_claude_clean_in_the_checkout_on_the_skills_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin, log = Path(tmp) / "bin", Path(tmp) / "log.jsonl"
            bin.mkdir()
            (bin / "claude").write_text(STANDIN)
            (bin / "claude").chmod(0o755)
            env = {**os.environ, "PATH": f"{bin}:{os.environ['PATH']}", "STANDIN_LOG": str(log), "STANDIN_FAIL": "clean"}
            subprocess.run([sys.executable, str(REPO / "llm-dlc/tools/claude_setup.py"), "launch", "--effort", "max", "hello"],
                           capture_output=True, text=True, env=env, cwd=tmp)
            call = json.loads(log.read_text().splitlines()[0])
        self.assertEqual((call["cwd"], call["connectors"]), (str(REPO), "false"))
        self.assertEqual(call["args"][:3], ["--setting-sources", "project,local", "--strict-mcp-config"])
        self.assertEqual(call["args"][-5:], ["--model", "claude-fable-5-2", "--effort", "max", "hello"])


if __name__ == "__main__":
    unittest.main()
