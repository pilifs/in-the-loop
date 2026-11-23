"""The public method, full parameter scope, JVM controls and expected answer of each opening claim."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Claim:
    method: str
    parameters: str = ""
    guard: str = ""
    # Each original JVM invocation is a tuple of arguments, written as Java expressions.
    holds: tuple = ((),)
    fails: tuple = ()
    nullable: str = ""


@dataclass(frozen=True)
class Subject:
    example: int
    owner: str
    graph: str
    claims: tuple
    bound: int = 8
    unwind: int = 16


def unary(*values):
    return tuple((str(value),) for value in values)


NUM = "n >= 16777216 && n < 33554432"
HEX = "n >= 16 && n <= 255"
NIBBLE = "m >= 0 && m < 16"
CHOICE = "choice >= 0 && choice < 4"
OFFSETS = "off >= -1 && off <= 6"
SMALL = unary(16777216, 16777217, 16777219, 33554431)
WORDS = unary("0L", "1L", "0xfffffffffffffL", "-1L")
BOOL = unary("false", "true")
UTF = (('"abab"', '""', "4"), ('"abab"', '"ba"', "1"), ('"a"', '"a"', "Integer.MIN_VALUE"),
       ('"a"', '""', "Integer.MAX_VALUE"), ('"a"', 'new String("a")', "0"),
       ('"\\uD800"', '"\\uD800"', "0"), ('"\\uDBFF\\uDFFF"', '"\\uDFFF"', "1"))
CELLS = unary("null", "new ReferenceCells.Item[0]", "new ReferenceCells.Item[1]",
              "new ReferenceCells.Item[]{new ReferenceCells.Item()}")
SIGNED = unary(0, 1, -1, "Integer.MIN_VALUE", "Integer.MAX_VALUE")
LONGS = unary("0L", "1L", "-1L", "Long.MIN_VALUE", "Long.MAX_VALUE")
CLAIMS = {
    "lists": Subject(376, "ListHistory", "jdk", (
        Claim("fromArray", "int value", holds=SIGNED),
        Claim("fromCollection", "int value", holds=SIGNED),
        Claim("followsSlot", "int value", holds=(), fails=SIGNED))),
    "numbers": Subject(377, "WideNumbers", "lang-historical", (
        Claim("fraction", "int n", NUM, SMALL), Claim("fractionOpcode", "int n", NUM, SMALL),
        Claim("floorOnly", "int n", NUM, unary(16777216), unary(16777219, 33554431)),
        Claim("narrow", "long fraction", holds=WORDS), Claim("narrowOpcode", "long fraction", holds=WORDS),
        Claim("wraps", "long fraction", holds=(), fails=WORDS))),
    "prefix": Subject(378, "OffsetPrefix", "jdk", (
        Claim("small", "int off, boolean empty", OFFSETS,
              tuple((str(i), b) for i in range(-1, 7) for b in ("true", "false"))),
        Claim("beforeEnd", "int off", OFFSETS, unary(-1, 0, 4, 6), unary(5)),
        Claim("wide", "String text, String prefix, int off", holds=UTF),
        Claim("nullPrefix", "int off", "off >= 0 && off <= 5", unary(0, 5))), 4),
    "arrays": Subject(379, "ReferenceCells", "jdk", (
        Claim("categories", "ReferenceCells.Item[] values", holds=CELLS, nullable="values"),
        Claim("noNullCell", "ReferenceCells.Item[] values", holds=CELLS[:2], fails=(CELLS[2],), nullable="values"),
        Claim("noItemCell", "ReferenceCells.Item[] values", holds=CELLS[:3], fails=(CELLS[3],), nullable="values"),
        Claim("followsAlias", "boolean shared, int initial", holds=(("true", "3"), ("false", "3"), ("true", "Integer.MAX_VALUE"))),
        Claim("alwaysShares", "boolean shared", holds=(("true",),), fails=(("false",),))), 2),
    "receiver": Subject(379, "ReceiverScope", "jdk", (
        Claim("exact", "boolean absent", holds=BOOL),
        Claim("parentOrChild", "int choice", holds=unary(0, 1), fails=unary(2)))),
    "stores": Subject(380, "ArrayStores", "jdk", (
        Claim("history", "int index, int kind, boolean absent", holds=tuple(
            (str(i), str(k), a) for i in (-1,0,1) for k in (0,1,2) for a in ("false","true"))),
        Claim("alwaysSucceeds", holds=(), fails=((),)))),
    "store-iterator": Subject(380, "IteratorStores", "collections", (
        Claim("history", "boolean integerArray, boolean advance, int kind", "kind >= 0 && kind <= 2",
              tuple((a,b,str(k)) for a in ("false","true") for b in ("false","true") for k in range(3))),)),
    "dispatch": Subject(382, "DefaultDispatch", "jdk", (
        Claim("dispatch", "int kind, int x", holds=tuple((str(k), x[0]) for k in range(3) for x in SIGNED)),
        Claim("firstDeclared", "int x", holds=(), fails=SIGNED))),
    "endian": Subject(383, "ByteReversal", "io", (
        Claim("reverseInt", "int x", holds=SIGNED), Claim("reverseLong", "long x", holds=LONGS),
        Claim("rotateInt", "int x", holds=unary(0, -1), fails=unary(1)),
        Claim("rotateLong", "long x", holds=unary("0L", "-1L"), fails=unary("1L")))),
    "surrogates": Subject(384, "SurrogateUnits", "text", (
        Claim("translate", "char a, char b, boolean second", holds=tuple((a,b,f) for a,b in
              (("'A'","'B'"),("(char)0xDBFF","(char)0xDFFF"),("(char)0xD800","'A'"),("'A'","(char)0xDC00"))
              for f in ("true","false"))),
        Claim("removeEvery", "char a, char b", holds=(("'A'","'B'"),), fails=(("(char)0xDBFF","(char)0xDFFF"),)))),
    "deque": Subject(385, "DequeRemoval", "collections", (
        Claim("history", "boolean ownerRemoves", holds=BOOL), Claim("stillReturns", holds=(), fails=((),)),
        Claim("singleton", "boolean removable", holds=BOOL), Claim("filtered", "boolean prefetch", holds=BOOL))),
    "construction": Subject(386, "ConstructorPhase", "lang-release", (
        Claim("history", "String source", holds=unary("null", '""', '"A"', '"\\uD800"', '"\\uDC00"', '"\\uDBFF\\uDFFF"'), nullable="source"),
        Claim("emptySkips", holds=(), fails=((),)), Claim("alreadyInitialized", holds=(), fails=((),))), 2),
    "radix": Subject(387, "RadixDigits", "jdk", (
        Claim("hex", "int n", HEX, unary(16, 190, 255)), Claim("lowFirst", "int n", HEX, unary(17), unary(190)))),
    "nibble": Subject(388, "UnsignedNibble", "lang-nibble", (
        Claim("nibble", "int m, int offset", NIBBLE, tuple((str(m),off) for m in (0,10,15) for off in ("0","1","-1","3","4","Integer.MIN_VALUE","Integer.MAX_VALUE"))),
        Claim("left", "int m", NIBBLE, unary(0), unary(10)), Claim("acceptsNegative", holds=(), fails=((),)))),
    "enum": Subject(389, "EnumNames", "jdk", (
        Claim("lookup", "int kind", "kind >= 0 && kind < 5", unary(*range(5))),
        Claim("ordinal", "boolean closed", holds=BOOL), Claim("alwaysZero", "boolean closed", holds=(("false",),), fails=(("true",),)))),
    "locals": Subject(390, "ThreadLocalHistory", "spring", (
        Claim("kernel", "int choice", CHOICE, unary(*range(4))), Claim("spring", "int choice", CHOICE, unary(*range(4))),
        Claim("nullInitializes", "boolean spring", holds=(), fails=BOOL))),
    # A worker-first schedule is an existential witness. A single ordinary JVM launch of mixed() may return either.
    "monitors": Subject(391, "MonitorIdentity", "jdk", (
        Claim("matched"), Claim("mixed", holds=(), fails=()), Claim("synchronizedMethod"))),
}
for side in ("parent", "fix"):
    CLAIMS["gson-" + side] = Subject(379, "GsonRequestedClass", "gson-" + side, (
        Claim("compatible", "int selection", "selection >= 0 && selection < 5", unary(*range(5))),
        Claim("syntax", "int selection", "selection >= 0 && selection < 4",
              unary(*range(4)) if side == "fix" else (), unary(*range(4)) if side == "parent" else ())))
    CLAIMS["guava-" + side] = Subject(381, "FormatHistory", "guava-" + side, (
        Claim("retained", "boolean typed", holds=BOOL if side == "fix" else (), fails=BOOL if side == "parent" else ()),
        Claim("parentBehavior", "boolean typed", holds=BOOL if side == "parent" else (), fails=BOOL if side == "fix" else ())))
