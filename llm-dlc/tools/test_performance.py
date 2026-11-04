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
import shutil
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


STATE = tempfile.TemporaryDirectory()  # the caches and measurements of these tests, not this machine's


def setUpModule():
    state = Path(STATE.name)
    for name, path in (("STATE", state), ("TRANSCRIPT_CACHE", state / "transcript-cache.json"),
                       ("SCAN_CACHE", state / "scan-cache.json"), ("PERF_LOG", state / "perf.jsonl")):
        mock.patch.object(sync, name, path).start()
    mock.patch.object(sync, "CHECK_CACHE", state / "check-cache.json").start()
    mock.patch.object(sync, "SYNC_CACHE", state / "sync-cache.json").start()


def tearDownModule():
    mock.patch.stopall()
    STATE.cleanup()


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
        loads = mock.Mock(wraps=sync.decompress)
        with mock.patch.object(sync, "decompress", loads), mock.patch.object(sync, "load_log", side_effect=AssertionError), \
                mock.patch.object(sync, "metrics_problems", return_value=([], [])):
            errors, _, notes, _ = sync.check_sessions({"s1": m}, sync.Redactor(), remote=False)
        self.assertEqual(sorted(sync.sha256(c.args[0]) for c in loads.call_args_list),
                         sorted(sync.sha256(sync.log_path("s1", sha).read_bytes()) for sha in shas))
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
                    mock.patch.object(sync, "commit_index", return_value=None), \
                    mock.patch.object(sync, "repo_web_url", return_value=None), \
                    mock.patch.object(sync, "Redactor", return_value=mock.Mock(fingerprint=lambda: "f")), \
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
        return {sync.finding_id(kind, value): {"level": level, "kind": kind, "masked": sync._mask(value), "value": value,
                                               "count": 1, "where": {"s"}}}

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


class MadeUpRedactor(sync.Redactor):
    """sync's Redactor with the made-up literals of these tests instead of this machine's."""

    def __init__(self, reviewed=None):
        self.inputs = (PAIRS, USER)
        redaction_rules.Rules.__init__(self, PAIRS, USER)
        self.reviewed, self.skipped, self._latest = reviewed or {}, sync.Counter(), None


def made_up_transcript(rng: random.Random, lines: int) -> bytes:
    """JSON lines and broken ones, with every line break the decoder or splitlines knows, invalid
    UTF-8, and line separators both raw and escaped."""
    out = []
    for _ in range(lines):
        text = random_text(rng) + rng.choice(["", " x", "\\u2028", "é", "\x85", "\x0b"])
        line = (json.dumps({"type": "user", "text": text}, ensure_ascii=rng.random() < 0.5) if rng.random() < 0.7
                else text).encode()
        out.append(line + rng.choice([b"\n", b"\n", b"\r\n", b"\r", b"\xe2\x80\xa8", b"\xff\n", b"\xe2\x82\n"]))
    return b"".join(out)


class Caches(unittest.TestCase):
    """The transcript and scan caches give what redacting and scanning everything gives."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.patches = [mock.patch.object(sync, "REPO", root), mock.patch.object(sync, "TRACES", root / "traces")]
        for p in self.patches:
            p.start()
        self.r = MadeUpRedactor()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def test_decoding_is_that_of_read_text(self):
        rng = random.Random(5)
        path = Path(self.tmp.name) / "t.jsonl"
        for _ in range(300):
            raw = bytes(rng.choice(b"ab\n\r\xe2\x82\xac\xff\xc3\xa9 ") for _ in range(rng.randint(0, 40)))
            path.write_bytes(raw)
            self.assertEqual(sync.decoded(raw), path.read_text(errors="replace"), raw)

    def grow(self, full: bytes, rng: random.Random, cache: sync.LocalCache, steps: int = 25) -> int:
        """Sync ever longer prefixes of full, cut anywhere; each log must be the full redaction."""
        reused = 0
        for cut in sorted(rng.sample(range(1, len(full) + 1), steps)) + [len(full)]:
            raw = full[:cut]
            before = cache.entries.get("s1", {}).get("source_bytes", 0)
            data = sync.redacted_incrementally(raw, "s1", "s1", self.r, cache)
            self.assertEqual(data, self.r(sync.decoded(raw)), cut)
            reused += before > 0 and len(raw) >= before
            sync.store_log("s1", data)
        return reused

    def test_a_growing_transcript_is_redacted_as_a_whole(self):
        for seed in range(12):
            rng = random.Random(seed)
            cache = sync.LocalCache(None, "f")
            self.assertGreater(self.grow(made_up_transcript(rng, 60), rng, cache), 0)

    def test_nothing_is_reused_from_a_rewritten_transcript_or_a_damaged_log(self):
        rng = random.Random(21)
        cache = sync.LocalCache(None, "f")
        full = made_up_transcript(rng, 40)
        first = sync.redacted_incrementally(full, "s1", "s1", self.r, cache)
        sync.store_log("s1", first)
        rewritten = (USER + "@corp" + ".test").encode() + full[len(USER) + 10:] + made_up_transcript(rng, 3)
        self.assertEqual(sync.redacted_incrementally(rewritten, "s1", "s1", self.r, cache), self.r(sync.decoded(rewritten)))
        sync.store_log("s1", self.r(sync.decoded(rewritten)))
        entry = cache.entries["s1"]
        sync.log_path("s1", entry["log_sha256"]).write_bytes(gzip.compress(b'{"other":1}\n' * 9999))
        longer = rewritten + made_up_transcript(rng, 3)
        loads = mock.Mock(wraps=sync.load_log)
        with mock.patch.object(sync, "load_log", loads):
            self.assertEqual(sync.redacted_incrementally(longer, "s1", "s1", self.r, cache), self.r(sync.decoded(longer)))
        loads.assert_called_once()

    def test_entries_under_another_fingerprint_or_a_full_audit_are_not_used(self):
        path = Path(self.tmp.name) / "cache.json"
        cache = sync.LocalCache(path, "f1")
        cache.entries["k"] = {"x": 1}
        cache.save()
        self.assertEqual(sync.LocalCache(path, "f1").entries, {"k": {"x": 1}})
        self.assertEqual(sync.LocalCache(path, "f2").entries, {})
        self.assertEqual(sync.LocalCache(path, "f1", trusted=False).entries, {})
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        other = MadeUpRedactor()
        other.inputs = (PAIRS[:-1], USER)
        self.assertNotEqual(self.r.fingerprint(), other.fingerprint())

    def test_a_growing_log_is_scanned_as_a_whole(self):
        listed = {}
        reviewed = MadeUpRedactor()
        for seed in range(8):
            rng = random.Random(100 + seed)
            full = self.r(sync.decoded(made_up_transcript(rng, 80)))
            scans = sync.ScanCache(self.r, path=None)
            for cut in sorted({full.rfind(b"\n", 0, rng.randrange(len(full))) + 1 for _ in range(10)} | {len(full)}):
                data = full[:cut]
                found = scans.hits("s1", sync.sha256(data), data)
                text = data.decode(errors="replace")
                self.assertEqual(found["leaks"], sync._counted(self.r.hits_of_text(text)[0]))
                self.assertEqual(found["review"], sync._counted(self.r.hits_of_text(text)[1]))
                # judged the same way as the text: a reviewed false positive is left out and counted
                for kind, rows in found["review"].items():
                    listed.setdefault(next(iter(rows)), {})
                reviewed.reviewed = listed
                reviewed.skipped = sync.Counter()
                expected = reviewed.leaks(text), reviewed.review(text)
                skipped, reviewed.skipped = reviewed.skipped, sync.Counter()
                self.assertEqual((reviewed.cached_leaks(found), reviewed.cached_review(found)), expected)
                self.assertEqual(reviewed.skipped, skipped)
            self.assertTrue(scans.entries)

    def check(self, m, scans):
        with mock.patch.object(sync, "metrics_problems", return_value=([], [])):
            return sync.check_sessions({"s1": m}, self.r, remote=False, scans=scans)

    def test_check_scans_a_log_once_by_its_content(self):
        texts = ['{"ip":"203.0.' + '113.%d"}\n' % n for n in range(1, 4)]
        current = "".join(texts).encode()
        prefix, other = current[:len(texts[0])], texts[2].encode()
        shas = [sync.store_log("s1", d)["sha256"] for d in (current, prefix, other)]
        m = {"schema": sync.SCHEMA, "log": {"sha256": shas[0]}, "subagents": [], "stats": {"usage": {}},
             "commits": [{"change_id": "c1", "log_sha256": shas[1]}], "logs": {sha: {} for sha in shas}}
        path = Path(self.tmp.name) / "scan.json"
        scans = sync.ScanCache(self.r, path)
        first = self.check(m, scans)
        scans.save()
        self.assertEqual(len([w for w in first[1] if "public-ip" in w]), 3)
        self.assertEqual(first, self.check(m, None))  # what scanning everything says
        scans = sync.ScanCache(self.r, path)
        self.assertEqual(set(scans.entries), set(shas))
        with mock.patch.object(self.r, "raw_hits", side_effect=AssertionError("scanned again")):
            self.assertEqual(self.check(m, scans), first)
        # the session's published files go through the cache too, by their content
        sync.summary_path("s1").write_text("written by zed" + "@corp" + ".test\n")
        found = self.check(m, scans)
        self.assertIn("s1: unredacted ['email'] in traces/s1/summary.md", found[0])
        self.assertEqual(found, self.check(m, None))
        with mock.patch.object(self.r, "raw_hits", side_effect=AssertionError("scanned again")):
            self.assertEqual(self.check(m, scans), found)
        sync.summary_path("s1").unlink()
        # a stored file that no longer holds its name's content is scanned for what it holds
        sync.log_path("s1", shas[2]).write_bytes(gzip.compress(b'{"ip":"198.51.' + b'100.4"}\n'))
        third = self.check(m, sync.ScanCache(self.r, path))
        self.assertIn(f"s1: log {shas[2][:12]} content does not match its name", third[0])
        self.assertEqual([w for w in third[1] if shas[2][:12] in w], 
                         [f"s1: log {shas[2][:12]}: public-ip ×1: " + sync._mask("198.51." + "100.4")])


class Previews(unittest.TestCase):
    """scan, review and stamp read the caches sync and check fill, and say what reading nothing says."""
    IPS = ["203.0." + "113.%d" % n for n in range(1, 6)]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.src = root / "project"
        (self.src / "s1" / "subagents").mkdir(parents=True)
        self.patches = [mock.patch.object(sync, "REPO", root), mock.patch.object(sync, "TRACES", root / "traces"),
                        mock.patch.object(sync, "claude_project_dir", return_value=self.src),
                        mock.patch.object(sync, "FINDINGS_CACHE", root / "values.json"),
                        mock.patch.object(sync, "older_than_stamp", return_value=False)]
        for p in self.patches:
            p.start()
        for f in (sync.TRANSCRIPT_CACHE, sync.SCAN_CACHE, sync.CHECK_CACHE):
            f.unlink(missing_ok=True)
        self.r = MadeUpRedactor()
        # a session synced once, then grown; a subagent; a log not uploaded; one that is; a summary
        line = lambda n, text: json.dumps({"type": "user", "n": n, "text": text}) + "\n"
        self.transcript = self.src / "s1.jsonl"
        self.transcript.write_text(line(1, "at " + self.IPS[0]) + line(2, "mail " + USER + "@corp" + ".test"))
        cache = sync.transcript_cache(self.r)
        stored = sync.redacted_now(self.transcript, "s1", "s1", self.r, cache)[1]
        cache.save()
        with self.transcript.open("a") as f:
            f.write(line(3, "then " + self.IPS[1]) + line(4, "and " + self.IPS[0]))
        (self.src / "s1" / "subagents" / "agent-a.jsonl").write_text(line(1, "sub " + self.IPS[2]))
        pending = sync.store_log("s1", line(1, "pending " + self.IPS[3]).encode())["sha256"]
        public = sync.store_log("s1", line(1, "public " + self.IPS[4]).encode())["sha256"]
        sync.save_manifest("s1", {"logs": {sync.sha256(stored): {}, pending: {}, public: {"url": "u"}}})
        sync.summary_path("s1").write_text("written by zed" + "@corp" + ".test\n")

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    @staticmethod
    def rows(found):
        return {fid: (f["level"], f["kind"], f["masked"], f["count"], sorted(f["where"])) for fid, f in found.items()}

    def test_findings_from_the_caches_are_those_of_reading_everything(self):
        expected = sync.scanned_findings(MadeUpRedactor())
        self.assertEqual({f["kind"] for f in expected.values()}, {"public-ip", "email"})
        self.assertNotIn(sync.finding_id("public-ip", self.IPS[4]), expected)  # published: check's business
        self.assertEqual(self.rows(sync.open_findings(self.r, full=True)), self.rows(expected))
        transcripts = sync.TRANSCRIPT_CACHE.read_bytes()
        first = sync.open_findings(self.r)
        self.assertEqual(self.rows(first), self.rows(expected))
        self.assertEqual(sync.TRANSCRIPT_CACHE.read_bytes(), transcripts)  # names no stored log: not saved
        r = MadeUpRedactor()
        with mock.patch.object(r, "raw_hits", side_effect=AssertionError("scanned again")):
            self.assertEqual(self.rows(sync.open_findings(r)), self.rows(expected))
        # a finding a person reviewed is left out and counted, as reading everything does
        fid = sync.finding_id("public-ip", self.IPS[0])
        reviewed, plain = MadeUpRedactor({fid: {}}), MadeUpRedactor({fid: {}})
        self.assertEqual(self.rows(sync.open_findings(reviewed)), self.rows(sync.scanned_findings(plain)))
        self.assertNotIn(fid, sync.open_findings(MadeUpRedactor({fid: {}})))
        self.assertEqual(reviewed.skipped, plain.skipped)

    def test_a_full_preview_adds_to_the_caches_and_drops_nothing(self):
        other = MadeUpRedactor()
        stored = sync.ScanCache(other)
        stored.hits("s9", sync.sha256(b"x\n"), b"x\n")  # an entry of check's that no preview reads
        stored.save()
        sync.open_findings(self.r, full=True)
        kept = sync.ScanCache(MadeUpRedactor()).entries
        self.assertIn(sync.sha256(b"x\n"), kept)
        r = MadeUpRedactor()
        with mock.patch.object(r, "raw_hits", side_effect=AssertionError("scanned again")):
            sync.open_findings(r)

    def test_values_come_from_a_scan_or_reading_everything_again(self):
        found = sync.open_findings(self.r, values=True)  # scanned now: every value known
        self.assertTrue(all(f["value"] for f in found.values()))
        sync.FINDINGS_CACHE.unlink()
        rescan = mock.Mock(wraps=sync.scanned_findings)
        with mock.patch.object(sync, "scanned_findings", rescan):
            listed = sync.open_findings(MadeUpRedactor())  # listing needs no value
            rescan.assert_not_called()
            self.assertTrue(all("value" not in f for f in listed.values()))
            again = sync.open_findings(MadeUpRedactor(), values=True)
            rescan.assert_called_once()
        self.assertEqual({fid: f["value"] for fid, f in again.items()}, {fid: f["value"] for fid, f in found.items()})
        r = MadeUpRedactor()
        with mock.patch.object(r, "raw_hits", side_effect=AssertionError("scanned again")):
            self.assertEqual(sync.open_findings(r, values=True).keys(), found.keys())
        # a remembered value is used only when the id names it
        values = json.loads(sync.FINDINGS_CACHE.read_text())
        fid = next(iter(values))
        values[fid]["value"] += "x"
        sync.FINDINGS_CACHE.write_text(json.dumps(values))
        self.assertNotIn("value", sync.open_findings(MadeUpRedactor())[fid])

    def test_scan_prints_what_reading_everything_prints(self):
        def scan(*args):
            with mock.patch.object(sync, "Redactor", MadeUpRedactor), mock.patch("sys.stdout", io.StringIO()) as out:
                code = sync.cmd_scan(list(args))
            return code, out.getvalue()

        full = scan("--full")
        self.assertIn("public-ip ×3: " + sync._mask(self.IPS[0]) + ", " + sync._mask(self.IPS[1]), full[1])
        self.assertIn("s1 agent agent-a: ", full[1])
        self.assertEqual(scan(), full)
        with mock.patch.object(MadeUpRedactor, "raw_hits", side_effect=AssertionError("scanned again")):
            self.assertEqual(scan(), full)
        self.assertEqual(scan("s1"), full)

    def test_stamp_proposes_from_the_caches(self):
        with mock.patch.object(sync, "Redactor", MadeUpRedactor), mock.patch.object(sync, "ALLOWLIST", Path(self.tmp.name) / "a.json"), \
                mock.patch.object(redaction_rules, "write_stamp") as write, mock.patch("sys.stdout", io.StringIO()), \
                mock.patch("sys.stderr", io.StringIO()):
            sync.summary_path("s1").unlink()  # its email is an error, which refuses a stamp
            self.assertEqual(sync.cmd_stamp([]), 0)
            write.assert_called_once_with()
            proposed = sync.load_allowlist()
        self.assertEqual({e["masked"] for e in proposed.values()}, {sync._mask(ip) for ip in self.IPS[:4]})
        self.assertFalse(any(ip in json.dumps(proposed) for ip in self.IPS))


class Checks(unittest.TestCase):
    """CheckCache: what check works out from content is looked up by that content, and gives what
    working it out again gives."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.patches = [mock.patch.object(sync, "REPO", root), mock.patch.object(sync, "TRACES", root / "traces"),
                        mock.patch.object(sync, "PRICING", root / "pricing.json")]
        for p in self.patches:
            p.start()
        (root / "pricing.json").write_text(json.dumps({"models": {}}))
        self.r = MadeUpRedactor()
        self.path = root / "check.json"
        self.scans = sync.ScanCache(self.r, path=None)

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def session(self):
        """A session of three logs, each a prefix of the next, and one that is not."""
        lines = [json.dumps({"type": "user", "n": n, "text": "made-up line %d" % n}) + "\n" for n in range(6)]
        logs = ["".join(lines[:2]).encode(), "".join(lines[:4]).encode(), "".join(lines).encode(), lines[5].encode()]
        shas = [sync.store_log("s1", d)["sha256"] for d in logs]
        m = {"schema": sync.SCHEMA, "log": {"sha256": shas[2]}, "subagents": [], "stats": {"usage": {}},
             "commits": [{"change_id": f"c{i}", "log_sha256": sha} for i, sha in enumerate(shas)],
             "logs": {sha: {} for sha in shas}}
        return m, shas

    def check(self, m, checks):
        problems = mock.Mock(return_value=([], []))
        with mock.patch.object(sync, "metrics_problems", problems):
            found = sync.check_sessions({"s1": m}, self.r, remote=False,
                                        scans=self.scans if checks else sync.ScanCache(self.r, path=None), checks=checks)
        return found

    def test_verified_snapshots_are_not_decompressed_again(self):
        m, shas = self.session()
        checks = sync.CheckCache(self.r, self.path)
        first = self.check(m, checks)
        checks.save()
        self.assertEqual(first, self.check(m, None))
        self.assertIn("s1: 1 older log(s) are not a prefix of the current log, as after a redaction policy change", first[2])
        checks = sync.CheckCache(self.r, self.path)
        self.assertEqual(len([k for k in checks.entries if k.startswith("gz:")]), 4)
        with mock.patch.object(sync, "decompress", side_effect=AssertionError("decompressed again")), \
                mock.patch.object(sync, "prefix_digests", side_effect=AssertionError("hashed again")):
            self.assertEqual(self.check(m, checks), first)
        self.assertEqual(sync.CheckCache(self.r, self.path, trusted=False).entries, {})
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_changed_bytes_are_verified_by_what_they_hold(self):
        m, shas = self.session()
        checks = sync.CheckCache(self.r, self.path)
        self.check(m, checks)
        # the same content compressed differently: its name still holds
        data = gzip.decompress(sync.log_path("s1", shas[0]).read_bytes())
        sync.log_path("s1", shas[0]).write_bytes(gzip.compress(data, compresslevel=1, mtime=7))
        self.assertEqual(self.check(m, checks), self.check(m, None))
        # other content under the name: an error, and the prefix check compares its bytes
        sync.log_path("s1", shas[1]).write_bytes(gzip.compress(b'{"other":1}\n'))
        found = self.check(m, checks)
        self.assertEqual(found, self.check(m, None))
        self.assertIn(f"s1: log {shas[1][:12]} content does not match its name", found[0])
        self.assertIn("s1: 2 older log(s) are not a prefix of the current log, as after a redaction policy change", found[2])
        # a current log rewritten under its name: its prefixes are worked out for what it holds
        sync.log_path("s1", shas[2]).write_bytes(gzip.compress(data + b'{"more":1}\n'))
        found = self.check(m, checks)
        self.assertEqual(found, self.check(m, None))
        self.assertIn(f"s1: log {shas[2][:12]} content does not match its name", found[0])

    def test_metrics_are_compared_again_when_an_input_changes(self):
        m, shas = self.session()
        m["stats"]["usage"] = dict.fromkeys(("input_tokens", "output_tokens", "cache_read_input_tokens",
                                             "cache_creation_input_tokens"), 0)
        sync.metrics_path("s1").write_text("{}")
        checks = sync.CheckCache(self.r, self.path)
        rendered = mock.Mock(return_value="{}")
        content = lambda: gzip.decompress(sync.log_path("s1", shas[2]).read_bytes())
        def problems(logs, text=None):
            if text is not None:
                sync.metrics_path("s1").write_text(text)
            with mock.patch.object(sync, "session_metrics", rendered):
                return sync.metrics_problems("s1", m, content, self.r, checks, logs)
        self.assertEqual(problems([shas[2]]), problems([shas[2]]))
        self.assertEqual(rendered.call_count, 1)
        for changed in ([shas[1]], [shas[2], None]):
            problems(changed)
        self.assertEqual(rendered.call_count, 3)
        found = problems([shas[2]], '{"a": 1}')
        self.assertEqual(rendered.call_count, 4)
        self.assertIn("s1: metrics.json does not match the log and manifest (run sync)", found[0])
        sync.PRICING.write_text(json.dumps({"models": {"x": {}}}))
        problems([shas[2]])
        m["stats"]["usage"]["input_tokens"] = 1
        problems([shas[2]])
        self.assertEqual(rendered.call_count, 6)
        problems([shas[2]], "{}")
        self.assertEqual(rendered.call_count, 7)
        problems([shas[2]])
        self.assertEqual(rendered.call_count, 7)

    def test_tree_files_are_what_jj_file_show_prints(self):
        with mock.patch.object(sync, "REPO", Path(sync.__file__).resolve().parents[2]):
            if not sync.has_jj():
                self.skipTest("no jj")
            commits = [c["commit_id"] for c in sync.jj_commits("::@- & ~root()")[:40:8]]
            wanted = [(c, p) for c in commits for p in ("llm-dlc/README.md", "no/such/file", "llm-dlc")]
            wanted.append(("0" * 40, "llm-dlc/README.md"))
            found = sync.tree_files(wanted)
            for c, p in wanted:
                r = sync.jj("file", "show", "-r", c, p)
                expected = r.stdout.encode() if r.returncode == 0 and p != "llm-dlc" else None
                self.assertEqual(found[c, p], expected, (c, p))


class Incremental(unittest.TestCase):
    """sync (and so commit) skips a session whose state is the one recorded after its last sync, and
    a skipped session is one that syncing again would leave as it is."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.src = root / "projects"
        self.src.mkdir()
        self.patches = [mock.patch.object(sync, "REPO", root / "repo"),
                        mock.patch.object(sync, "TRACES", root / "repo" / "traces"),
                        mock.patch.object(sync, "SESSION_NOTES", root / "notes"),
                        mock.patch.object(sync, "claude_project_dir", return_value=self.src),
                        mock.patch.object(sync, "Redactor", MadeUpRedactor),
                        mock.patch.object(sync, "write_index"),
                        mock.patch.dict(sync.os.environ, {"CLAUDE_CODE_SESSION_ID": ""}),
                        mock.patch("sys.stdout", io.StringIO())]
        for p in self.patches:
            p.start()
        sync.SYNC_CACHE.unlink(missing_ok=True)
        for sid in ("s1", "s2"):
            self.grow(sid, 3)
            old = time.time() - 2 * sync.LIVE_SECONDS
            sync.os.utime(self.src / f"{sid}.jsonl", (old, old))

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def grow(self, sid, n):
        with open(self.src / f"{sid}.jsonl", "a") as f:
            for i in range(n):
                f.write(json.dumps({"type": "user", "timestamp": f"2026-11-0{1 + i % 3}T10:00:0{i % 10}Z",
                                    "message": {"role": "user", "content": f"made-up prompt {i}"}}) + "\n")

    def synced(self, *args):
        """The sessions a sync processes, and every file it leaves under the traces directory."""
        with mock.patch.object(sync, "process", wraps=sync.process) as process:
            sync.cmd_sync(list(args))
        files = {p.relative_to(sync.TRACES): p.read_bytes() for p in sorted(sync.TRACES.rglob("*")) if p.is_file()}
        return sorted(c.args[0].stem for c in process.call_args_list), files

    def test_only_a_session_whose_inputs_or_outputs_changed_is_synced(self):
        self.assertEqual(self.synced()[0], ["s1", "s2"])
        names, files = self.synced()
        self.assertEqual(names, [])
        self.assertEqual(self.synced("--all"), (["s1", "s2"], files))  # skipping changed nothing
        self.grow("s1", 2)
        self.assertEqual(self.synced()[0], ["s1"])
        sync.summary_path("s2").write_text("edited by hand\n")
        self.assertEqual(self.synced()[0], ["s2"])
        sync.SESSION_NOTES.mkdir()
        sync.notes_path("s1").write_text("A made-up note.\n")
        names, files = self.synced()
        self.assertEqual(names, ["s1"])
        self.assertIn(b"A made-up note.", files[Path("s1/summary.md")])
        sync.os.utime(self.src / "s2.jsonl")  # touched: now open, so its status changes
        self.assertEqual(self.synced()[0], ["s2"])
        self.assertEqual(self.synced("s2")[0], ["s2"])  # a session named is synced whatever its state
        with mock.patch.dict(sync.os.environ, {"LLM_TRACES_FULL": "1"}):
            self.assertEqual(self.synced()[0], ["s1", "s2"])
        self.assertEqual(self.synced()[0], [])

    def test_a_changed_tool_or_publish_means_syncing_again(self):
        self.synced()
        with mock.patch.object(sync, "repo_web_url", return_value="https://example.com/x/y"):
            self.assertEqual(self.synced()[0], ["s1", "s2"])
        with mock.patch.object(sync, "process", wraps=sync.process) as process:
            sync.cmd_sync([], publishing=True)
        self.assertEqual(process.call_count, 2)
        self.assertEqual(self.synced()[0], ["s1", "s2"])  # what a publish wrote is not taken as a sync's

    def test_the_commits_that_count_are_those_a_sync_would_stamp_or_list(self):
        self.synced()
        t, path = sync.datetime.fromisoformat("2026-11-02T10:00:00+00:00").timestamp(), self.src / "s1.jsonl"
        c = lambda cid, desc, author=t, immutable=False, commit="a" * 40, at=False: {
            "change_id": cid, "commit_id": commit, "immutable": immutable, "empty": False, "at": at,
            "author": author, "description": desc}
        index = [c("k1", "Done\n\nLLM-Trace: s1 sha256:" + "0" * 64, author=0), c("k2", "In the span"),
                 c("k3", "Long after", author=t + 3 * 86400), c("k4", "Old, pushed", immutable=True, commit="b" * 40),
                 c("k5", "@", author=t + 3 * 86400, at=True)]
        state = lambda index, current=False: sync.session_state(path, "ended", current, index)
        base = state(index)
        self.assertEqual([x[0] for x in base["commits"]], ["k1", "k2"])
        self.assertEqual([x[0] for x in state(index, current=True)["commits"]], ["k1", "k2", "k5"])
        for i, change in ((0, {"description": "Done"}), (0, {"immutable": True}), (1, {"description": "Edited"}),
                          (1, {"empty": True}), (1, {"author": t + 3 * 86400})):
            self.assertNotEqual(state([{**x, **change} if j == i else x for j, x in enumerate(index)]), base, (i, change))
        for i, change in ((0, {"commit_id": "c" * 40}), (2, {"description": "Edited"}), (3, {"description": "x"}),
                          (4, {"description": "y"})):
            self.assertEqual(state([{**x, **change} if j == i else x for j, x in enumerate(index)]), base, (i, change))

    def test_the_span_covers_what_jj_counts_as_made(self):
        with mock.patch.object(sync, "REPO", Path(sync.__file__).resolve().parents[2]), \
                mock.patch.object(sync, "TRACES", Path(sync.__file__).resolve().parents[1] / "traces"):
            if not sync.has_jj():
                self.skipTest("no jj")
            index = sync.commit_index()
            for sid, m in sync.all_manifests().items():
                if not (m.get("started") and m.get("ended")):
                    continue
                made = (f'mutable() & ::@ & author_date(after:"{m["started"]}") & author_date(before:"{m["ended"]}")'
                        f' & ~(empty() & description(exact:""))')
                wanted = {x["change_id"] for x in sync.jj_commits(made)}
                wanted |= {x["change_id"] for x in sync.jj_commits(f'description(substring:"LLM-Trace: {sid}")')}
                state = sync.session_state(self.src / f"{sid}.jsonl", "ended", False, index)
                self.assertLessEqual(wanted, {x[0] for x in state["commits"]}, sid)


class CommitChecks(unittest.TestCase):
    """commit runs the check after it has committed, with the redactor its sync used, so agents need
    no separate `check`; its notes are counted rather than listed."""

    def test_commit_checks_what_it_committed_and_fails_on_an_error(self):
        for found, expected in ((0, 0), (1, 1)):
            calls, redact = [], object()
            ok = lambda *a, **k: sync.subprocess.CompletedProcess(a, 0, "", "")
            with mock.patch.object(sync, "jj", side_effect=lambda *a: calls.append(("jj",) + a[:1]) or ok()), \
                 mock.patch.object(sync, "jj_commits", return_value=[{"change_id": "k" * 32}]), \
                 mock.patch.object(sync, "cmd_sync", side_effect=lambda a: calls.append(("sync",)) or redact), \
                 mock.patch.object(sync, "cmd_check", side_effect=lambda a, **k: calls.append(("check", k)) or found), \
                 mock.patch("sys.stdout", io.StringIO()), mock.patch("sys.stderr", io.StringIO()) as err:
                self.assertEqual(sync.cmd_commit(["-m", "Made-up summary", "-m", "Made-up body"]), expected)
            self.assertEqual(calls, [("jj", "describe"), ("sync",), ("jj", "new"),
                                     ("check", {"redact": redact, "notes_listed": False})])
            self.assertEqual("found errors" in err.getvalue(), bool(found))

    def test_notes_are_counted_when_not_listed(self):
        def report(listed):
            with mock.patch.object(sync, "reviewed_problems", return_value=[]), \
                 mock.patch.object(sync, "allowlist_problems", return_value=([], [])), \
                 mock.patch.object(sync, "all_manifests", return_value={}), \
                 mock.patch.object(sync, "check_sessions", return_value=([], ["made-up warning"], ["n1", "n2"], 0)), \
                 mock.patch.object(sync, "check_trailers", return_value=([], [])), \
                 mock.patch.object(sync, "check_global_files", return_value=[]), \
                 mock.patch.object(sync, "Redactor", MadeUpRedactor), mock.patch("sys.stdout", io.StringIO()) as out:
                self.assertEqual(sync.cmd_check([], notes_listed=listed), 0)
            return out.getvalue()
        listed, counted = report(True), report(False)
        self.assertIn("note  n1", listed)
        self.assertNotIn("note ", counted)
        self.assertIn("warn  made-up warning", counted)
        self.assertIn("2 note(s) needing no action (sync.py check lists them)", counted)


class PublicationGate(unittest.TestCase):
    """push's last step before `jj git push`: the revision it publishes holds, byte for byte, the
    trace files that `check` read on disk, and every log its new commits point at is uploaded."""

    SID = "made-up-session"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = root = Path(self.tmp.name)
        llm = root / "llm-dlc"
        self.patches = [mock.patch.object(sync, name, value) for name, value in (
            ("REPO", root), ("TRACES", llm / "traces"), ("SESSION_NOTES", llm / "session-notes"),
            ("INDEX", llm / "index.json"), ("TRACES_README", llm / "traces" / "README.md"),
            ("METRICS_ROLLUP", llm / "traces" / "metrics.json"), ("REVIEWED", llm / "reviewed.json"),
            ("ALLOWLIST", llm / "allowlist.json"))]
        for p in self.patches:
            p.start()
        self.git("init", "-q")
        self.sha = "ab" * 32
        self.write_session(url=True)
        for path, text in ((sync.INDEX, "{}\n"), (sync.TRACES_README, "# made-up\n"), (sync.METRICS_ROLLUP, "{}\n"),
                           (llm / "unrelated.md", "not a trace file\n")):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def git(self, *args: str) -> str:
        env = {**sync.os.environ, "GIT_AUTHOR_NAME": "Made Up", "GIT_AUTHOR_EMAIL": "made-up@example.com",
               "GIT_COMMITTER_NAME": "Made Up", "GIT_COMMITTER_EMAIL": "made-up@example.com"}
        return sync.subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True,
                                   text=True, env=env).stdout.strip()

    def write_session(self, url: bool, withdrawn: bool = False):
        info = {"url": sync.log_url(self.SID, self.sha)} if url else {}
        if withdrawn:
            info = {"withdrawn": "made-up reason"}
        d = sync.session_dir(self.SID)
        d.mkdir(parents=True, exist_ok=True)
        sync.manifest_path(self.SID).write_text(json.dumps({"schema": sync.SCHEMA, "log": {"sha256": self.sha},
                                                            "logs": {self.sha: info}}) + "\n")
        sync.summary_path(self.SID).write_text("# made-up summary\n")
        sync.metrics_path(self.SID).write_text("{}\n")

    def snapshot(self) -> str:
        """A commit of the working files, made with plumbing (no `git commit` in this repo)."""
        self.git("add", "-A")
        return self.git("commit-tree", "-m", "made-up", self.git("write-tree"))

    def gate(self, commit: str, pushed_desc: str | None = None) -> list[str]:
        desc = pushed_desc if pushed_desc is not None else f"Made-up change\n\n{sync.TRAILER}: {self.SID} sha256:{self.sha}\n"
        listed = sync.subprocess.CompletedProcess([], 0, commit + "\n", "")
        with mock.patch.object(sync, "jj", return_value=listed) as jj, \
             mock.patch.object(sync, "jj_commits", return_value=[{"change_id": "k" * 32, "description": desc}]) as pushed:
            errors = sync.publication_gate("bookmarks(exact:\"main\")")
        self.assertEqual(jj.call_args.args[:4], ("log", "--no-graph", "-r", "bookmarks(exact:\"main\")"))
        self.assertEqual(pushed.call_args.args, ("::(bookmarks(exact:\"main\")) ~ ::remote_bookmarks()",))
        return errors

    def test_the_checked_revision_passes(self):
        self.assertEqual(self.gate(self.snapshot()), [])

    def test_a_file_changed_since_the_commit_is_caught(self):
        commit = self.snapshot()
        sync.summary_path(self.SID).write_text("# made-up summary, edited after the commit\n")
        errors = self.gate(commit)
        self.assertEqual(len(errors), 1)
        self.assertIn("summary.md differs from the copy that was checked", errors[0])

    def test_files_check_did_not_read_are_caught(self):
        log = sync.log_path(self.SID, self.sha)  # gitignored in the real repo; committed here by mistake
        log.parent.mkdir(parents=True)
        log.write_bytes(gzip.compress(b"made-up\n"))
        stray = sync.SESSION_NOTES / "no-such-session.md"
        stray.parent.mkdir(parents=True)
        stray.write_text("made-up note\n")
        errors = self.gate(self.snapshot())
        self.assertEqual(len(errors), 2)
        self.assertTrue(all("is in the revision but was not checked" in e for e in errors))

    def test_a_checked_file_missing_from_the_revision_is_caught(self):
        commit = self.snapshot()
        sync.notes_path(self.SID).parent.mkdir(parents=True)
        sync.notes_path(self.SID).write_text("made-up note\n")
        errors = self.gate(commit)
        self.assertEqual(len(errors), 1)
        self.assertIn("was checked but is not in the revision", errors[0])

    def test_a_pushed_commit_must_point_at_an_uploaded_log(self):
        self.write_session(url=False)
        errors = self.gate(self.snapshot())
        self.assertEqual(len(errors), 1)
        self.assertIn("which is not uploaded", errors[0])
        self.write_session(url=False, withdrawn=True)
        self.assertEqual(self.gate(self.snapshot()), [])
        legacy = f"Made-up change\n\n{sync.TRAILER}: {self.SID}\n"  # no sha256: nothing to fetch
        self.assertEqual(self.gate(self.snapshot(), legacy), [])

    def test_a_revset_jj_cannot_resolve_fails(self):
        failed = sync.subprocess.CompletedProcess([], 1, "", "made-up revset error")
        with mock.patch.object(sync, "jj", return_value=failed):
            errors = sync.publication_gate("nope(")
        self.assertEqual(len(errors), 1)
        self.assertIn("made-up revset error", errors[0])

    def test_what_a_push_publishes(self):
        self.assertEqual(sync.push_revisions(["--bookmark", "main"]), 'bookmarks(exact:"main")')
        self.assertEqual(sync.push_revisions(["-b=glob:feat*", "--remote", "origin"]), 'bookmarks(glob:"feat*")')
        self.assertEqual(sync.push_revisions(["-b", "main", "-r", "@-", "--change=xyz"]),
                         'bookmarks(exact:"main") | (@-) | (xyz)')
        self.assertEqual(sync.push_revisions(["--all"]), "bookmarks()")
        self.assertEqual(sync.push_revisions([]), "bookmarks() ~ ::remote_bookmarks()")

    def test_push_stops_before_git_when_the_gate_fails(self):
        for problems, pushed in ((["made-up problem"], False), ([], True)):
            ok = sync.subprocess.CompletedProcess([], 0, "", "")
            with mock.patch.object(sync, "uncommitted_work", return_value=[]), \
                 mock.patch.object(sync, "jj_commits", return_value=[{"change_id": "k" * 32, "description": "Made-up\n"}]), \
                 mock.patch.object(sync, "jj", return_value=ok), mock.patch.object(sync, "cmd_sync"), \
                 mock.patch.object(sync, "cmd_check", return_value=0), mock.patch.object(sync, "cmd_upload", return_value=0), \
                 mock.patch.object(sync, "write_index"), mock.patch.object(sync, "all_manifests", return_value={}), \
                 mock.patch.object(sync, "publication_gate", return_value=problems) as gate, \
                 mock.patch.object(sync.subprocess, "run", return_value=ok) as run, \
                 mock.patch("sys.stdout", io.StringIO()), mock.patch("sys.stderr", io.StringIO()):
                self.assertEqual(sync.cmd_push(["--bookmark", "main"]), 0 if pushed else 1)
            gate.assert_called_once_with('bookmarks(exact:"main")')
            self.assertEqual(run.called, pushed)


class HookCursor(unittest.TestCase):
    """The Stop hook reads a transcript from its cursor and sends what reading it whole sends."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.state_new, self.state_old = root / "state-new", root / "state-old"
        self.sent = []
        self.down = False

        def urlopen(req, timeout=None):
            if self.down:
                raise OSError("down")
            self.sent.append(json.loads(gzip.decompress(req.data)))
            return mock.MagicMock()
        self.patches = [mock.patch.object(sync, "REPO", root), mock.patch.object(sync, "TRACES", root / "traces"),
                        mock.patch.object(sync, "langfuse_config", return_value=("http://stub.invalid", "pk", "sk")),
                        mock.patch.object(sync.urllib.request, "urlopen", side_effect=urlopen)]
        for p in self.patches:
            p.start()
        sync.TRANSCRIPT_CACHE.unlink(missing_ok=True)
        sync.save_manifest("s1", {"session_id": "s1", "log": {"sha256": "0" * 64}})
        self.transcript = root / "project" / "s1.jsonl"
        self.transcript.parent.mkdir()
        self.transcript.write_bytes(b"")
        self.r = MadeUpRedactor()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def reference(self):
        """The hook as it was: redact and parse the whole transcript."""
        entries = sync.read_jsonl(self.r(self.transcript.read_text(errors="replace")))
        m = {**sync.load_manifest("s1"), **sync.summarize(entries, self.r.string(str(sync.REPO)))}
        return sync.export_langfuse("s1", entries, m, live=False)

    def both(self):
        """What the reference and the hook send, each with its own state."""
        out = []
        for state, run in ((self.state_old, self.reference), (self.state_new, lambda: sync.hook_export(self.transcript, self.r))):
            with mock.patch.object(sync, "STATE", state):
                try:
                    run()
                except OSError:
                    pass
            out.append(self.sent[:])
            self.sent.clear()
        return out

    @staticmethod
    def turn(rng, n):
        ts = lambda k: "2026-11-03T10:%02d:%02dZ" % (n % 60, k)
        text = lambda: random_text(rng)
        lines = [{"type": "user", "uuid": f"p{n}-{rng.random()}", "timestamp": ts(0), "message": {"role": "user", "content": text()}}]
        for k in range(rng.randint(0, 3)):
            tid = f"t{n}.{k}"
            lines.append({"type": "assistant", "timestamp": ts(2 * k + 1), "message": {
                "id": f"m{n}.{k}", "model": "made-up-model", "usage": {"input_tokens": k, "output_tokens": 1},
                "content": [{"type": "text", "text": text()}, {"type": "tool_use", "id": tid, "name": "Bash", "input": {"command": text()}}]}})
            lines.append({"type": "user", "timestamp": ts(2 * k + 2), "message": {"content": [
                {"type": "tool_result", "tool_use_id": tid, "content": text(), "is_error": rng.random() < 0.2}]}})
        if rng.random() < 0.3:
            lines.append({"type": "ai-title", "aiTitle": "title " + text()})
        out = []
        for e in lines:
            line = json.dumps(e, ensure_ascii=rng.random() < 0.5).encode()
            out.append(line + rng.choice([b"\n", b"\n", b"\n", b"\r\n", b"\r", b"\xe2\x80\xa8"]))
            if rng.random() < 0.15:  # noise: a broken line, a raw line separator, invalid UTF-8
                out.append(rng.choice([b"{broken", b'{"type":"progress","t":"a\xe2\x80\xa8b"}', b"\xff\xfe", b""]) + b"\n")
        return b"".join(out)

    def test_it_sends_what_reading_everything_sends(self):
        turns = 0
        for seed in range(12):
            rng = random.Random(seed)
            for d in (self.state_new, self.state_old):
                shutil.rmtree(d, ignore_errors=True)
            data, n, unfinished = b"", 0, b""
            self.transcript.write_bytes(b"")
            for step in range(10):
                if step == 6 and seed % 3 == 0:  # replaced: another transcript under the same name
                    data, n = b"", 100
                for _ in range(rng.randint(0, 3)):
                    data += unfinished
                    unfinished = b""
                    data += self.turn(rng, n)
                    n += 1
                if rng.random() < 0.3:  # cut mid-line, finished at the next step
                    cut = rng.randint(1, len(data)) if data else 0
                    data, unfinished = data[:cut], data[cut:]
                self.transcript.write_bytes(data)
                self.down = rng.random() < 0.2
                old, new = self.both()
                self.assertEqual(new, old, f"seed {seed}, step {step}")
                turns += sum(1 for b in new for s in b["resourceSpans"][0]["scopeSpans"][0]["spans"] if "parentSpanId" not in s)
        self.assertGreater(turns, 100)

    def lengths(self):
        """The length of each text the hook redacts."""
        seen = []
        real = MadeUpRedactor.__call__
        return seen, mock.patch.object(MadeUpRedactor, "__call__", lambda r, text: seen.append(len(text)) or real(r, text))

    def test_it_reads_only_what_follows_the_cursor(self):
        rng = random.Random(1)
        first, second = self.turn(rng, 0) + self.turn(rng, 1), self.turn(rng, 2)
        unix = lambda b: b.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        first, second = unix(first), unix(second)
        self.transcript.write_bytes(first)
        seen, patch = self.lengths()
        with mock.patch.object(sync, "STATE", self.state_new), patch:
            self.assertEqual(sync.hook_export(self.transcript, self.r), 2)
            self.transcript.write_bytes(first + second)
            self.assertEqual(sync.hook_export(self.transcript, self.r), 1)
            self.assertEqual(sync.hook_export(self.transcript, self.r), 0)
        self.assertEqual(seen[2:], [len(second.decode(errors="replace")), 0])  # the first read is in two calls
        names = [s["name"] for b in self.sent for s in b["resourceSpans"][0]["scopeSpans"][0]["spans"] if "parentSpanId" not in s]
        self.assertEqual(names, ["turn 1", "turn 2", "turn 3"])

    def test_it_reads_everything_when_the_cursor_cannot_be_trusted(self):
        rng = random.Random(2)
        data = self.turn(rng, 0).replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        self.transcript.write_bytes(data)
        with mock.patch.object(sync, "STATE", self.state_new):
            sync.hook_export(self.transcript, self.r)
            changed = data.replace(b"10:00:00", b"10:00:01", 1)  # same length, other bytes
            for label, content, patch in (
                    ("replaced", changed, mock.patch.dict("os.environ", {})),
                    ("--full", changed, mock.patch.dict("os.environ", {"LLM_TRACES_FULL": "1"})),
                    ("other rules", changed, mock.patch.object(MadeUpRedactor, "fingerprint", return_value="other"))):
                self.transcript.write_bytes(content)
                seen, counting = self.lengths()
                with patch, counting:
                    sync.hook_export(self.transcript, self.r)
                self.assertEqual(sum(seen), len(content.decode(errors="replace")), label)

    def test_the_state_keeps_what_else_it_records(self):
        self.state_new.mkdir()
        (self.state_new / "s1.json").write_text(json.dumps({"exported": ["x"], "complete": "c" * 64}))
        self.transcript.write_bytes(self.turn(random.Random(3), 0))
        with mock.patch.object(sync, "STATE", self.state_new):
            sync.hook_export(self.transcript, self.r)
            state = sync.langfuse_state("s1")
        self.assertEqual(state["complete"], "c" * 64)
        self.assertIn("x", state["exported"])
        self.assertEqual(len(state["exported"]), 2)
        self.assertEqual(state["hook_cursor"]["turns"], 1)

    def test_lines_in_counts_what_the_redactor_reads(self):
        rng = random.Random(4)
        for _ in range(300):
            raw = made_up_transcript(rng, rng.randint(0, 3))
            for piece in raw.split(b"\n"):
                for line in (piece, piece + b"\n"):
                    self.assertEqual(sync.lines_in(line), len(sync.decoded(line).splitlines()), line)
                    self.assertEqual(sync.lines_in(line), self.r(sync.decoded(line)).count(b"\n"), line)


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
