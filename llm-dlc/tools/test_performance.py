#!/usr/bin/env python3
"""Tests for the speed-ups in sync.py and redaction_rules.py: each must give the results of the
code it replaced. Run: python3 llm-dlc/tools/test_performance.py
Every value here is made up, and those that look like secrets are assembled at run time, so that
this file's own transcript raises no finding."""
import gzip
import io
import json
import random
import re
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import redaction_rules
import sync
from redaction_rules import EMAIL_RE, WIN_USER_RE, email_spans

USER = "qzuser"
SECRET = "made" + "up" + "-local-" + "value-0001"
PAIRS = [("/ho" + "me/" + USER, "~", 0, "home"), ("zorbhost", "host", re.I, "hostname"),
         (USER + "@corp" + ".test", "user@example.com", re.I, "email"), (SECRET, "[REDACTED:local-secret]", 0, "local-secret")]


class Reference(redaction_rules.Rules):
    """The rules as they ran before the speed-ups: every pattern over every string, EMAIL_RE itself."""

    def string(self, text):
        for _kind, rx, rep in self.literals:
            text = rx.sub(lambda _m, r=rep: r, text)
        for _kind, rx, rep in self.secret_res:
            text = rx.sub(rep, text)
        text = EMAIL_RE.sub(lambda m: m.group(0) if self._public_email(m.group(0)) else "[REDACTED:email]", text)
        text = WIN_USER_RE.sub(self._win_user, text)
        if self.user_re:
            text = self.user_re.sub("user", text)
        return text

    def _leaks_in(self, s, out):
        for kind, rx, _ in self.literals + self.secret_res:
            out += [(kind, m.group(0)) for m in rx.finditer(s)]
        out += [("email", m.group(0)) for m in EMAIL_RE.finditer(s) if not self._public_email(m.group(0))]
        out += [("windows-user", m.group(0)) for m in WIN_USER_RE.finditer(s) if self._win_user(m) != m.group(0)]
        if self.user_re:
            out += [("username", m.group(0)) for m in self.user_re.finditer(s)]


# Pieces that the rules care about, Unicode case variants among them (ſ folds to s, the Kelvin
# sign to k, İ to i under re.I), glued at random into strings.
PIECES = ["pass" + "word=", "PASS" + "WORD: ", "pa\u017f\u017fword=", "api_\u212aey=", "secret", "SECRET_KEY=",
          "TO" + "KEN=", "credentials:", "_AUTH=", "authorization: basic ", "Bearer ", "aut\u0130", "s" + "k-ant-",
          "gh" + "p_", "AK" + "IA", "x-api-key: ", "-u ", "--user=", "https://", "://", "@", "a@b.co", "x@y.example.com",
          "z@users.noreply.github.com", ".", "_", "-", "+", "%", ":", "=", "/", "\\", "\\n", "\\t", " ", "\"", "'", "\n",
          "[", "]", "{", "${", "<", USER, USER.upper(), "/mnt/c/Users/", "C:\\Users\\", "Public", "zorbhost", "ZORBHOST",
          SECRET, "/ho" + "me/zed", "/Us" + "ers/zed", "203.0." + "113.9", "fe80::1", "0a:1b:2c" + ":3d:4e:5f", "\x1b[31m",
          "accountUuid\": \"", "-----BEGIN RSA PRIVATE KEY-----", "-----END RSA PRIVATE KEY-----", "eyJ", "ya29.", "hf_"]


def random_text(rng: random.Random) -> str:
    parts = []
    for _ in range(rng.randint(1, 14)):
        if rng.random() < 0.6:
            parts.append(rng.choice(PIECES))
        else:
            alphabet = rng.choice(["abcxyz", "ABC" + "def0123456789", "abc.-_+%", "0123456789abcdef", "aZ09+/="])
            parts.append("".join(rng.choice(alphabet) for _ in range(rng.choice([1, 2, 5, 12, 25, 45]))))
    return "".join(parts)


class Emails(unittest.TestCase):
    def test_the_same_matches_as_the_pattern(self):
        rng = random.Random(7)
        alphabet = "ab1.-_+%@ :/x"
        for _ in range(30000):
            s = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 30)))
            if rng.random() < 0.3:
                s = s.replace("x", "co")
            self.assertEqual(list(email_spans(s)), [m.span() for m in EMAIL_RE.finditer(s)], s)

    def test_a_match_right_after_another_starts_where_it_ended(self):
        for s in ("a@b.cc.x@d.ee", "a@b.cc%x@d.ee", "a@b.cc@d.ee", "a@b.cc+@d.ee", ".a@b.cc", "@a@b.cc", "a@b.c-d.ee-"):
            self.assertEqual(list(email_spans(s)), [m.span() for m in EMAIL_RE.finditer(s)], s)

    def test_a_long_run_is_linear(self):
        rules = redaction_rules.Rules([], "nobody")
        for s in ("a" * 32000, "a" * 32000 + "@", "a" * 32000 + "@x", ("a" * 50 + "@") * 600):
            started = time.perf_counter()
            self.assertEqual(rules.string(s), s)
            rules.hits_of_line(s)
            self.assertLess(time.perf_counter() - started, 0.5, len(s))


class Rules(unittest.TestCase):
    """The rules with their hints and email_spans against the reference, on made-up text."""

    def setUp(self):
        self.new, self.old = redaction_rules.Rules(PAIRS, USER), Reference(PAIRS, USER)

    def test_redaction_is_unchanged(self):
        rng = random.Random(11)
        for _ in range(20000):
            s = random_text(rng)
            self.assertEqual(self.new.string(s), self.old.string(s), repr(s))

    def test_findings_are_unchanged(self):
        rng = random.Random(13)
        for _ in range(20000):
            s = random_text(rng)
            line = json.dumps({"text": s, s[:8]: [s[::-1]]}, ensure_ascii=False)
            self.assertEqual(self.new.hits_of_line(line), self.old.hits_of_line(line), repr(s))
            self.assertEqual(self.new.hits_of_line(s), self.old.hits_of_line(s), repr(s))

    def test_a_hint_never_hides_a_match(self):
        rng = random.Random(17)
        env = next(rx for kind, rx, _ in self.new.secret_res if kind == "env-secret")
        for _ in range(20000):
            s = random_text(rng)
            if env.search(s):
                self.assertTrue(self.new._may_match("env-secret", s), repr(s))

    def test_a_replaced_username_pattern_is_not_hinted(self):
        self.new.user_re = re.compile("other")
        self.assertIn(("username", "other"), self.new.hits_of_line("an other one")[0])


class Snapshots(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.patches = [mock.patch.object(sync, "REPO", root), mock.patch.object(sync, "TRACES", root / "traces")]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def test_sizes_come_from_the_bytes_in_hand(self):
        data = b'{"a":1}\n{"b":2}\n'
        with mock.patch.object(sync.gzip, "decompress", side_effect=AssertionError("read back")):
            first = sync.store_log("s1", data)
            again = sync.store_log("s1", data)
        self.assertEqual(first, again)
        self.assertEqual({k: first[k] for k in ("bytes", "lines", "gzip_bytes")}, sync.log_info("s1", first["sha256"]))
        self.assertEqual(gzip.decompress(sync.log_path("s1", first["sha256"]).read_bytes()), data)

    def test_an_unchanged_file_is_not_written(self):
        path = Path(self.tmp.name) / "f.txt"
        self.assertTrue(sync.write_if_changed(path, "x\n"))
        stamp = path.stat().st_mtime_ns
        time.sleep(0.01)
        self.assertFalse(sync.write_if_changed(path, "x\n"))
        self.assertEqual(path.stat().st_mtime_ns, stamp)
        self.assertTrue(sync.write_if_changed(path, "y\n"))
        self.assertEqual(path.read_text(), "y\n")

    def test_prefix_digests_agree_with_startswith(self):
        rng = random.Random(3)
        data = bytes(rng.randrange(256) for _ in range(500))
        lengths = {0, 1, 17, 250, 499, 500, 501, 900}
        digests = sync.prefix_digests(data, lengths)
        self.assertEqual(set(digests), {n for n in lengths if n <= len(data)})
        for n, digest in digests.items():
            self.assertEqual(digest, sync.hashlib.sha256(data[:n]).hexdigest())

    def test_check_reads_each_log_once_and_still_finds_a_rewritten_one(self):
        current, prefix, other = b'{"n":1}\n{"n":2}\n{"n":3}\n', b'{"n":1}\n', b'{"n":9}\n'
        shas = [sync.store_log("s1", d)["sha256"] for d in (current, prefix, other)]
        m = {"schema": sync.SCHEMA, "log": {"sha256": shas[0]}, "subagents": [], "stats": {"usage": {}},
             "commits": [{"change_id": "c1", "log_sha256": shas[1]}, {"change_id": "c2", "log_sha256": shas[2]},
                         {"change_id": "c3", "log_sha256": shas[0]}],
             "logs": {sha: {} for sha in shas}}
        loads = mock.Mock(wraps=sync.load_log)
        with mock.patch.object(sync, "load_log", loads), mock.patch.object(sync, "metrics_problems", return_value=([], [])):
            errors, _, notes, _ = sync.check_sessions({"s1": m}, sync.Redactor(), remote=False)
        self.assertEqual(sorted(c.args[1] for c in loads.call_args_list), sorted(shas))
        self.assertIn("s1: 1 older log(s) are not a prefix of the current log, as after a redaction policy change", notes)
        self.assertEqual([e for e in errors if "log" in e and "summary" not in e], [])

    def test_a_log_not_matching_its_name_is_reported_and_compared_by_its_bytes(self):
        current, prefix = b'{"n":1}\n{"n":2}\n', b'{"n":1}\n'
        sha_current, sha_prefix = (sync.store_log("s1", d)["sha256"] for d in (current, prefix))
        sync.log_path("s1", sha_prefix).write_bytes(gzip.compress(b'{"n":7}\n'))
        m = {"schema": sync.SCHEMA, "log": {"sha256": sha_current}, "subagents": [], "stats": {"usage": {}},
             "commits": [{"change_id": "c1", "log_sha256": sha_prefix}], "logs": {sha_current: {}, sha_prefix: {}}}
        with mock.patch.object(sync, "metrics_problems", return_value=([], [])):
            errors, _, notes, _ = sync.check_sessions({"s1": m}, sync.Redactor(), remote=False)
        self.assertIn(f"s1: log {sha_prefix[:12]} content does not match its name", errors)
        self.assertTrue(any("not a prefix" in n for n in notes))


class Sync(unittest.TestCase):
    def test_global_files_are_rebuilt_once_and_langfuse_is_not_contacted(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ("a", "b", "c"):
                (Path(d) / f"{name}.jsonl").write_text("")
            fake = lambda p, *a, **k: {"session_id": p.stem, "stats": {"turns": 0, "tool_calls": 0},
                                       "log": {"sha256": "0" * 64, "bytes": 0}, "commits": []}
            with mock.patch.object(sync, "claude_project_dir", return_value=Path(d)), \
                    mock.patch.object(sync, "process", side_effect=fake), \
                    mock.patch.object(sync, "write_index") as index, \
                    mock.patch.object(sync, "Redactor"), \
                    mock.patch.object(sync.subprocess, "Popen", side_effect=AssertionError("started a process")), \
                    mock.patch.object(sync.urllib.request, "urlopen", side_effect=AssertionError("network")), \
                    mock.patch.object(sync, "export_langfuse", side_effect=AssertionError("waited on Langfuse")), \
                    mock.patch("sys.stdout", io.StringIO()):
                sync.cmd_sync([])
        index.assert_called_once_with()

    def test_the_exporter_stops_at_the_first_failure(self):
        with mock.patch.object(sync, "load_manifest", return_value={"log": {"sha256": "0" * 64}}), \
                mock.patch.object(sync, "load_log", return_value=b'{"type":"user"}\n'), \
                mock.patch.object(sync, "export_langfuse", side_effect=OSError("down")) as export, \
                mock.patch.object(sync, "log"):
            self.assertEqual(sync.cmd_langfuse(["s1", "s2:live"]), 1)
        export.assert_called_once()

    def test_the_stop_hook_reads_nothing_without_langfuse(self):
        with mock.patch.object(sync, "langfuse_config", return_value=None), \
                mock.patch.object(sync, "Redactor", side_effect=AssertionError("redacted")), \
                mock.patch("sys.stdin", io.StringIO(json.dumps({"transcript_path": "/nonexistent.jsonl"}))), \
                mock.patch.object(sync, "log") as log:
            sync.cmd_hook()
        log.assert_not_called()


class Stamp(unittest.TestCase):
    """A stamp is refused by open errors only; open warnings become allow-list proposals."""
    IP = "203.0." + "113.8"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        self.patches = [mock.patch.object(sync, "ALLOWLIST", tmp / "allowlist.json"),
                        mock.patch.object(sync, "REVIEWED", tmp / "reviewed.json"),
                        mock.patch.object(redaction_rules, "write_stamp"),
                        mock.patch("sys.stdout", io.StringIO()), mock.patch("sys.stderr", io.StringIO())]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def finding(self, level, kind, value):
        return {sync.finding_id(kind, value): {"level": level, "kind": kind, "value": value, "count": 1, "where": {"s"}}}

    def test_an_open_warning_is_proposed_and_the_stamp_goes_ahead(self):
        with mock.patch.object(sync, "open_findings", return_value=self.finding("warn", "public-ip", self.IP)):
            self.assertEqual(sync.cmd_stamp([]), 0)
        redaction_rules.write_stamp.assert_called_once_with()
        (entry,) = sync.load_allowlist().values()
        self.assertEqual(entry["status"], "proposed")
        self.assertNotIn(self.IP, sync.ALLOWLIST.read_text())
        self.assertEqual(sync.allowlist_problems(sync.Redactor())[0], [])
        self.assertEqual(len(sync.allowlist_problems(sync.Redactor())[1]), 1)  # check warns about it

    def test_an_open_error_refuses_it(self):
        found = self.finding("ERROR", "email", "someone" + "@" + "corp.test")
        with mock.patch.object(sync, "open_findings", return_value=found):
            self.assertEqual(sync.cmd_stamp([]), 1)
        redaction_rules.write_stamp.assert_not_called()

    def test_rules_that_differ_are_counted(self):
        old = redaction_rules.Rules(PAIRS, USER)
        new = redaction_rules.Rules(PAIRS + [("plainword", "[REDACTED:x]", 0, "redact.txt literal")], USER)
        lines = [json.dumps({"a": "a plainword here"}), json.dumps({"a": "nothing"}), "plainword raw"]
        self.assertEqual(sync.rules_differences(old, redaction_rules.Rules(PAIRS, USER), lines), 0)
        self.assertEqual(sync.rules_differences(old, new, lines), 2)

    def test_a_kept_date_is_written_back(self):
        with tempfile.TemporaryDirectory() as d:
            copy = Path(d) / "rules.py"
            copy.write_text(Path(redaction_rules.__file__).read_text())
            with mock.patch.object(redaction_rules, "__file__", str(copy)):
                self.patches[2].stop()
                try:
                    redaction_rules.write_stamp("2026-01-02T03:04:05+00:00")
                finally:
                    self.patches[2].start()
            self.assertIn('RULES_GENERATED = "2026-01-02T03:04:05+00:00"', copy.read_text())


class Perf(unittest.TestCase):
    def test_phases_nest_and_records_are_kept(self):
        perf = sync.Perf()
        with perf.phase("outer"):
            with perf.phase("inner"):
                perf.count("things", 2)
            with perf.phase("inner"):
                pass
        record = perf.record("demo")
        self.assertEqual(record["phases"]["outer/inner"]["calls"], 2)
        self.assertEqual(record["counters"], {"things": 2})
        with tempfile.TemporaryDirectory() as d, mock.patch.object(sync, "STATE", Path(d)), \
                mock.patch.object(sync, "PERF_LOG", Path(d) / "perf.jsonl"), mock.patch.object(sync, "perf", perf):
            sync.save_perf("demo")
            out = io.StringIO()
            with mock.patch("sys.stdout", out):
                sync.cmd_perf(["1", "demo"])
        self.assertIn("outer/inner", out.getvalue())


if __name__ == "__main__":
    unittest.main()
