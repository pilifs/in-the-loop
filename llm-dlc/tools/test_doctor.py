#!/usr/bin/env python3
"""Tests for doctor.py, the quantitative assessment of a machine: which findings block, which only limit, and the
budget it proposes. Run: python3 llm-dlc/tools/test_doctor.py
The machines here are made up; nothing is read from this one."""
import unittest
from unittest import mock

import doctor

GIB = doctor.GIB


def machine(memory=16, cpus=8, disk=100, system="Linux", architecture="x86_64"):
    return {"system": system, "architecture": architecture, "cpus": cpus, "os": "Made-up Linux 1", "wsl": False,
            "memory": int(memory * GIB), "memoryAvailable": int(memory * GIB), "swap": 0,
            "diskFree": int(disk * GIB), "diskAt": "/made/up"}


def levels(m):
    return {c["id"]: c["level"] for c in doctor.hardware(m)}


class HardwareTest(unittest.TestCase):
    def test_a_machine_at_or_above_the_comfortable_sizes_passes(self):
        self.assertEqual(set(levels(machine()).values()), {"ok"})

    def test_a_hardware_limit_below_the_minimum_blocks(self):
        self.assertEqual(levels(machine(memory=6))["memory"], "blocking")
        self.assertEqual(levels(machine(cpus=1))["cpus"], "blocking")
        self.assertEqual(levels(machine(disk=5))["disk"], "blocking")

    def test_between_the_minimum_and_the_comfortable_size_only_limits(self):
        found = levels(machine(memory=9, cpus=2, disk=12))  # the laptop the repository began on had 9 GB
        self.assertEqual((found["memory"], found["cpus"], found["disk"]), ("limits", "limits", "limits"))

    def test_a_limit_says_what_is_lost(self):
        memory = next(c for c in doctor.hardware(machine(memory=9)) if c["id"] == "memory")
        self.assertIn("deferred", memory["why"])
        self.assertNotIn("deferred", next(c for c in doctor.hardware(machine()) if c["id"] == "memory")["why"])

    def test_another_operating_system_blocks_and_another_architecture_limits(self):
        self.assertEqual(levels(machine(system="Darwin"))["os"], "blocking")
        self.assertEqual(levels(machine(architecture="riscv64"))["architecture"], "limits")


class BudgetTest(unittest.TestCase):
    def test_the_three_shares_fit_in_the_machine(self):
        for memory, cpus in ((8, 2), (9, 8), (16, 4), (32, 8), (64, 16), (105, 30), (512, 96)):
            b = doctor.budget(machine(memory=memory, cpus=cpus))
            total = float(b["reserve"][:-1]) + float(b["loopMemory"][:-1]) + float(b["runner"]["memory"][:-1])
            self.assertLessEqual(total, memory, (memory, b))
            self.assertGreaterEqual(b["runner"]["workers"], 1)
            self.assertLessEqual(float(b["runner"]["job_memory_max"][:-1]), max(1, float(b["runner"]["memory"][:-1])))
            self.assertLess(b["runner"]["cpus"], max(cpus, 2))

    def test_the_development_vm_gets_the_budget_it_was_given_by_hand(self):
        # 30 vCPUs and 105 GiB: a 13G reserve, 12G for a loop, and 80G and 26 CPUs for the runner with one loop.
        b = doctor.budget(machine(memory=105, cpus=30))
        self.assertEqual((b["reserve"], b["loopMemory"], b["runner"]["memory"], b["runner"]["cpus"]), ("13G", "12G", "80G", 26))

    def test_a_small_machine_keeps_the_default_loop_cap(self):
        self.assertEqual(doctor.budget(machine(memory=9, cpus=8))["loopMemory"], "3.5G")


class AssessTest(unittest.TestCase):
    def assess(self, tools):
        with mock.patch.object(doctor, "machine", lambda: machine()), mock.patch.object(doctor, "tools", lambda: tools):
            return doctor.assess()

    def test_a_missing_required_tool_blocks_and_an_optional_one_limits(self):
        report = self.assess([doctor.check("jj", "tools", "not found", "any", "blocking", "why", "fix"),
                              doctor.check("jbmc", "tools", "not found", "6.x", "limits", "why", "fix"),
                              doctor.check("git", "tools", "git 2", "any", "ok", "why", "fix")])
        self.assertEqual((report["blocking"], report["limits"]), (["jj"], ["jbmc"]))
        self.assertNotIn("fix", next(c for c in report["checks"] if c["id"] == "git"))

    def test_the_exit_status_says_whether_anything_blocks(self):
        with mock.patch.object(doctor, "assess", lambda: {"checks": [], "budget": doctor.budget(machine()),
                                                           "blocking": ["memory"], "limits": []}), \
                mock.patch("builtins.print"):
            self.assertEqual(doctor.main(["--json"]), 1)
        with mock.patch.object(doctor, "assess", lambda: {"checks": [], "budget": doctor.budget(machine()),
                                                           "blocking": [], "limits": ["jbmc"]}), \
                mock.patch("builtins.print"):
            self.assertEqual(doctor.main([]), 0)

    def test_version_numbers_are_read_out_of_a_tool_s_first_line(self):
        self.assertEqual(doctor.numbers("cargo 1.99.1 (5f94df478 2026-08-27)"), (1, 99, 1))
        self.assertEqual(doctor.numbers('openjdk version "25.0.5" 2026-10-20 LTS')[:1], (25,))
        self.assertEqual(doctor.numbers(None), ())


if __name__ == "__main__":
    unittest.main()
