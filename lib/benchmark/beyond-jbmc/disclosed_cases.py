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
RANGE_SEEDS = (("807","false","1"), ("808","false","2"), ("808","true","0"), ("809","true","2"))
CASES["N04-N05"] = ("text", Subject(0, "JacksonRanges", "jackson-core-2.19.0", (
    Claim("arrayRange", "int suffix, boolean negative, int offset", holds=RANGE_SEEDS),
    Claim("stringRange", "int suffix, boolean negative", holds=tuple(s[:2] for s in RANGE_SEEDS)),
    Claim("accepted", "int suffix, boolean negative, int offset",
          holds=(("807","false","1"), ("808","true","2"), ("0","true","0"))),
    Claim("allDigits", "char[] text, int offset, boolean negative", holds=(
        ('"x9223372036854775808y".toCharArray()', "1", "true"),
        ('"x9223372036854775808y".toCharArray()', "1", "false"),
        ('"9999999999999999999".toCharArray()', "0", "true"),
        ('"0000000000000000001".toCharArray()', "0", "false")))), 24, 32))
for phase, graph in (("old", SPRING_OLD), ("new", SPRING_NEW)):
    closed = Claim("resolved") if phase == "new" else Claim("resolved", holds=(), fails=((),))
    opened = Claim("unresolved") if phase == "old" else Claim("unresolved", holds=(), fails=((),))
    CASES["S02-S09-" + phase] = ("reflection", Subject(0, "SpringTypes", graph, (
        closed, opened, Claim("methodReturn"), Claim("releasedSignature"), Claim("afterClear"),
        Claim("publicMethod"), Claim("genericReturn"))))
