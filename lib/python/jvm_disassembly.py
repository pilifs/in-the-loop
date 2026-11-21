"""A compiled class as the JDK's own disassembler prints it: each method's instructions, by name and descriptor.

The reading several proof techniques start from (array induction, lib/python/jvm_array_induction.py; the schedule and
monitor experiments under examples/tools/targets). It is the pinned `javap` run on the exact class file given, never
a class resolved through javap's search path, so what is read is the bytes that were bound. Standard library only.

    methods(javap, class_file)    ({(name, descriptor): {"header", "code": [Instruction], "handlers"}}, the disassembly text)
    member_call(instruction)      (owner or None, name, descriptor) of an instruction's constant-pool method reference
"""

from dataclasses import dataclass
import re
import subprocess


@dataclass(frozen=True)
class Instruction:
    pc: int
    op: str
    arg: str
    member: str


def methods(javap, class_file):
    """Use the pinned JDK disassembler on the exact class file, never a class resolved by javap's search path."""
    dis = subprocess.check_output([javap, "-p", "-c", "-s", class_file], text=True)
    parsed = {}
    header = None
    key = None
    for line in dis.splitlines():
        if re.match(r"^  \S", line):
            header, key = line.strip(), None
        elif header and line.startswith("    descriptor:"):
            if "(" in header or header == "static {};":
                name = (
                    "<clinit>" if header == "static {};" else header.split("(")[0].split()[-1].split(".")[-1]
                )
                key = (name, line.split()[-1])
                parsed[key] = {"header": header, "code": [], "handlers": False}
        elif key and "Exception table:" in line:
            parsed[key]["handlers"] = True
        elif key and (match := re.fullmatch(r"\s*(\d+):\s+(\w+)(?:\s+(.*?))?\s*", line)):
            arg, _, member = (match[3] or "").partition("//")
            parsed[key]["code"].append(Instruction(int(match[1]), match[2], arg.strip(), member.strip()))
    return parsed, dis


def member_call(ins):
    """(owner in internal form, or None for the instruction's own class; name; descriptor) of a method reference."""
    match = re.fullmatch(r"Method (?:(.+)\.)?([\w$]+):(\([^)]*\).+)", ins.member)
    if not match:
        raise ValueError(f"unresolved constant-pool call at {ins.pc}: {ins.member}")
    return match.groups()
