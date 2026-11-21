#!/usr/bin/env python3
"""Tests for case_pack.py: a folder of per-case output kept as one file, read as if it were still a folder.
Run: python3 -m unittest targets.test_case_pack   (from examples/tools)"""
from __future__ import annotations

import hashlib
import io
import os
import tarfile
import tempfile
import unittest
from pathlib import Path

from targets import case_pack, workflow

CASES = {"p0/native.json": b'[{"made-up": 0}]\n', "p0/stderr": b"", "p1/native.json": b'[{"made-up": 1}]\n',
         "p1/stderr": b"a made-up warning\n", "m1/native.json": b'[{"made-up": -1}]\n', "m1/stderr": b"\x00\xff"}


class Pack(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.records = Path(self.tmp.name) / "901-made-up" / "records"
        self.call = self.records / "native-selectors" / "fix" / "run-1" / "calls" / "abc"
        self.write(self.call / "cases", CASES)
        (self.call / "Calls.java").write_text("class Calls {}\n")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, folder, files):
        for name, data in files.items():
            (folder / name).parent.mkdir(parents=True, exist_ok=True)
            (folder / name).write_bytes(data)

    def name(self, case):
        return f"native-selectors/fix/run-1/calls/abc/cases/{case}"

    def test_a_packed_folder_reads_as_the_folder_did_and_the_same_files_give_the_same_pack(self):
        before = {name: case_pack.read(self.records, self.name(name)) for name in CASES}
        self.assertEqual(before, CASES)
        unpacked = case_pack.unpacked(self.records)
        self.assertEqual(case_pack.pack(self.records), (1, 6, (self.call / "cases.tar.gz").stat().st_size))
        self.assertFalse((self.call / "cases").exists())
        self.assertEqual(sorted(p.name for p in self.call.iterdir()), ["Calls.java", "cases.tar.gz"])
        self.assertEqual({name: case_pack.read(self.records, self.name(name)) for name in CASES}, CASES)
        self.assertEqual(case_pack.unpacked(self.records), unpacked)  # the same names and digests, the pack opened
        first = (self.call / "cases.tar.gz").read_bytes()
        other = Path(self.tmp.name) / "elsewhere" / "cases"
        self.write(other, dict(reversed(list(CASES.items()))))  # written in another order, at another time
        os.utime(other / "p0/native.json", (1, 1))
        self.assertEqual(case_pack.write(other).read_bytes(), first)
        self.assertEqual(case_pack.pack(self.records), (0, 0, 0))  # nothing loose is left to pack

    def test_what_neither_the_folder_nor_the_pack_holds_is_refused_as_a_missing_file_is(self):
        with self.assertRaisesRegex(workflow.ClaimError, "p7/native.json does not exist"):
            case_pack.read(self.records, self.name("p7/native.json"))
        case_pack.pack(self.records)
        with self.assertRaisesRegex(workflow.ClaimError, "p7/native.json does not exist"):
            case_pack.read(self.records, self.name("p7/native.json"))
        with self.assertRaisesRegex(workflow.ClaimError, "resolves outside"):
            case_pack.read(self.records, "../../etc/made-up")
        with self.assertRaisesRegex(workflow.ClaimError, "does not exist"):
            case_pack.read(self.records, self.name("p0"))  # a folder in the pack is not a file
        pack = self.call / "cases.tar.gz"
        pack.write_bytes(pack.read_bytes()[:40])  # a pack cut short is said to be unreadable, not taken for an empty one
        with self.assertRaisesRegex(workflow.ClaimError, "cases.tar.gz cannot be read"):
            case_pack.read(self.records, self.name("p0/native.json"))

    def test_a_file_that_is_present_is_read_before_the_packs_member(self):
        case_pack.pack(self.records)
        self.write(self.call / "cases", {"p1/native.json": b"restored or rewritten\n"})
        self.assertEqual(case_pack.read(self.records, self.name("p1/native.json")), b"restored or rewritten\n")
        self.assertEqual(case_pack.read(self.records, self.name("p0/native.json")), CASES["p0/native.json"])
        with self.assertRaisesRegex(SystemExit, "differs from"):  # and a folder that disagrees with its pack is not removed
            case_pack.pack(self.records)
        self.assertTrue((self.call / "cases/p1/native.json").is_file())
        self.write(self.call / "cases", CASES)                    # the restored original, whole: it agrees, and goes
        self.assertEqual(case_pack.pack(self.records)[:2], (1, 6))
        self.assertFalse((self.call / "cases").exists())

    def test_a_pack_holds_plain_files_only(self):
        (self.call / "cases" / "link").symlink_to(self.call / "Calls.java")
        with self.assertRaisesRegex(ValueError, "not a plain file"):
            case_pack.write(self.call / "cases")
        self.assertTrue((self.call / "cases" / "p0/native.json").is_file())
        self.assertFalse((self.call / "cases.tar.gz").exists())
        (self.call / "cases" / "link").unlink()
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as tar:  # a pack made elsewhere, with a link in it
            info = tarfile.TarInfo("p0/native.json")
            info.type, info.linkname = tarfile.SYMTYPE, "/etc/made-up"
            tar.addfile(info)
        case_pack.pack(self.records)
        (self.call / "cases.tar.gz").write_bytes(buffer.getvalue())
        with self.assertRaisesRegex(workflow.ClaimError, "cannot be read"):
            case_pack.read(self.records, self.name("p0/native.json"))

    def test_the_packed_records_are_compared_with_an_unpacked_tree_file_for_file(self):
        original = Path(self.tmp.name) / "restored" / "records"
        for path in sorted(self.records.rglob("*")):
            if path.is_file():
                self.write(original, {path.relative_to(self.records).as_posix(): path.read_bytes()})
        case_pack.pack(self.records)
        self.assertEqual(case_pack.differences(self.records, original), [])
        (original / self.name("p1/stderr")).write_bytes(b"another made-up warning\n")
        (original / self.name("p2/native.json")).parent.mkdir()
        (original / self.name("p2/native.json")).write_bytes(b"[]")
        (self.records / "run.json").write_text("{}")
        self.assertEqual(case_pack.differences(self.records, original),
                         [f"missing here: {self.name('p2/native.json')}", "only here: run.json", f"differs: {self.name('p1/stderr')}"])
        self.assertEqual(case_pack.unpacked(self.records)[self.name("p0/native.json")],
                         hashlib.sha256(CASES["p0/native.json"]).hexdigest())

    def test_the_budget_names_a_loose_folder_of_cases_as_an_error_and_a_large_record_as_a_warning(self):
        self.assertEqual(case_pack.budget(self.records), ([], []))  # six loose files are a run in progress, not a pile
        many = {f"p{i}/native.json": b"[]" for i in range(case_pack.LOOSE_CASES + 1)}
        self.write(self.call / "cases", many)
        errors, warnings = case_pack.budget(self.records)
        self.assertEqual(warnings, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("901-made-up: records/native-selectors/fix/run-1/calls/abc/cases holds 55 loose per-case files; "
                      "run python3 examples/tools/targets/case_pack.py pack 901", errors[0])
        case_pack.pack(self.records)
        self.assertEqual(case_pack.budget(self.records), ([], []))
        self.write(self.records / "bulk", {f"{i}.json": b"{}" for i in range(case_pack.ENTRIES + 1)})
        self.write(self.records / "more", {f"{i // 500}/{i}.json": b"{}" for i in range(case_pack.FILES - case_pack.ENTRIES)})
        errors, warnings = case_pack.over_budget(self.records.parent.parent)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [f"901-made-up: records/bulk has {case_pack.ENTRIES + 1} entries (over 1000, what a forge lists)",
                                    f"901-made-up: records/ holds {case_pack.FILES + 3} files (over 2000)"])


if __name__ == "__main__":
    unittest.main()
