"""Executable observations from the beyond-JBMC casebook on their released classpaths."""
from subjects import Claim, Subject

SPRING_OLD = "spring-6.1.14"
SPRING_NEW = "spring-6.2.0"
COMPANIONS = {"InterfaceClaims": ["InterfaceShape"], "ViewChecks": ["FarmFrame"]}
COMPILE_GRAPH = {("SpringTypes", SPRING_NEW): SPRING_OLD}
CASES = {
    "S01": ("reflection", Subject(0, "InterfaceClaims", "jdk", (
        Claim("intact"), Claim("inverse", holds=(), fails=((),)), Claim("defensiveCopies")))),
}
for phase, graph in (("old", SPRING_OLD), ("new", SPRING_NEW)):
    closed = Claim("resolved") if phase == "new" else Claim("resolved", holds=(), fails=((),))
    opened = Claim("unresolved") if phase == "old" else Claim("unresolved", holds=(), fails=((),))
    CASES["S02-S09-" + phase] = ("reflection", Subject(0, "SpringTypes", graph, (
        closed, opened, Claim("methodReturn"), Claim("releasedSignature"), Claim("afterClear"),
        Claim("publicMethod"), Claim("genericReturn"))))
