"""Check the fixed private weekday conversion on its original bytecode over all signed Java ints."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from register import CASE, PARSER, sha
from plan_run import ROOT
sys.path.insert(0, str(ROOT / "examples/tools"))
from targets import change_inventory, runtime_jar

VALID = ("isValidDayOfWeek", "(I)Z")
CONVERT = ("toCalendarDayOfWeek", "(I)I")
BRIDGE = ("access$800", "(I)I")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def hash_bytes(data):
    return hashlib.sha256(data).hexdigest()


def identity(value):
    return hash_bytes(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def bv(value):
    return f"#x{value & 0xffffffff:08x}"


def translate(data):
    pool, declarations, _ = runtime_jar._declarations(data, with_code=True)
    methods = {}
    calls = {}
    for sig, access in [(VALID, 10), (CONVERT, 10), (BRIDGE, 0x1008)]:
        flags, code, handlers = declarations[sig]
        require(flags == access and handlers == 0, "wrong flags or exception handlers on " + sig[0])
        ops = dict(change_inventory.instructions(code))
        visited = set()
        targets = {}
        def evaluate(pc, stack):
            visited.add(pc)
            op = ops[pc]
            if op == 0xac:
                require(len(stack) == 1, "unexpected stack at return")
                return stack[0]
            n = next(i for i in ops if i > pc)
            if op == 0x1a:
                return evaluate(n, stack + ["x"])
            if 0x03 <= op <= 0x08 or op == 0x10:
                value = op - 3 if op != 0x10 else int.from_bytes(code[pc+1:pc+2], "big", signed=True)
                return evaluate(n, stack + [bv(value)])
            if op == 0x60:
                return evaluate(n, stack[:-2] + [f"(bvadd {stack[-2]} {stack[-1]})"])
            if op == 0xb8:
                idx = int.from_bytes(code[pc+1:pc+3], "big")
                tag, value = pool[idx]
                owner, name, desc = runtime_jar._member_ref(pool, value)
                require(tag == 10 and owner == PARSER.replace(".", "/") and (name, desc) in methods,
                        "call escapes the proved acyclic private methods")
                targets[pc] = name + desc
                return evaluate(n, stack[:-1] + [f"({name} {stack[-1]})"])
            require(op in (0xa7, 0x9a, 0xa0, 0xa1, 0xa3), "unexpected instruction or effect at " + str(pc))
            target = pc + int.from_bytes(code[pc+1:pc+3], "big", signed=True)
            require(target in ops and target > pc, "unproved loop or invalid branch")
            if op == 0xa7:
                return evaluate(target, stack)
            if op == 0x9a:
                condition, rest = f"(distinct {stack[-1]} {bv(0)})", stack[:-1]
            else:
                compare = {0xa0: "distinct", 0xa1: "bvslt", 0xa3: "bvsgt"}[op]
                condition, rest = f"({compare} {stack[-2]} {stack[-1]})", stack[:-2]
            return f"(ite {condition} {evaluate(target, rest)} {evaluate(n, rest)})"
        expression = evaluate(0, [])
        require(visited == set(ops), "unchecked instructions in " + sig[0])
        methods[sig] = {"access": flags, "code": code.hex(), "codeSha256": hash_bytes(code),
                        "expression": expression, "calls": {str(k): v for k, v in targets.items()}}
        calls[sig] = list(targets.values())
    require(calls[CONVERT] == [VALID[0] + VALID[1]] and calls[BRIDGE] == [CONVERT[0] + CONVERT[1]],
            "different converter or synthetic bridge")
    return methods


def prove(manifest, spec):
    artifact, = manifest["classpath"]
    jar = Path(artifact["file"])
    require(sha(jar) == artifact["sha256"], "private deployment differs")
    data = runtime_jar.read_class(jar, PARSER.replace(".", "/"))
    methods = runtime_jar.methods(data)
    require(CONVERT in methods and VALID in methods and BRIDGE in methods, "private weekday conversion absent")
    require(spec["entry"] == PARSER + "#" + "".join(CONVERT) and spec["callFrom"] == PARSER + "#" + "".join(BRIDGE),
            "different private helper or consumer")
    bodies = translate(data)
    definitions = [f"(define-fun {sig[0]} ((x (_ BitVec 32))) (_ BitVec 32) {body['expression']})"
                   for sig, body in bodies.items()]
    valid = f"(and (bvsge x {bv(1)}) (bvsle x {bv(7)}))"
    expected = f"(ite {valid} (ite (= x {bv(7)}) {bv(1)} (bvadd x {bv(1)})) x)"
    rows = spec["rows"]
    require(rows and all(isinstance(r.get("args"), list) and len(r["args"]) == 1 for r in rows),
            "empty or malformed weekday table")
    args = [r["args"][0] for r in rows]
    require(len(set(args)) == len(args) and all(len(r["args"]) == 1 and
            all(type(v) is int and -(2**31) <= v < 2**31 for v in [*r["args"], r["result"]]) for r in rows),
            "invalid substitution domain")
    claims = [f"(= (isValidDayOfWeek x) (ite {valid} {bv(1)} {bv(0)}))",
              f"(= (toCalendarDayOfWeek x) {expected})", "(= (access$800 x) (toCalendarDayOfWeek x))",
              *(f"(= (toCalendarDayOfWeek {bv(r['args'][0])}) {bv(r['result'])})" for r in rows)]
    query = "\n".join(["(set-logic QF_BV)", *definitions, "(declare-const x (_ BitVec 32))",
                       "(assert (not (and " + " ".join(claims) + ")))", "(check-sat)"]) + "\n"
    solver = subprocess.run(["z3", "-in"], input=query, text=True, check=True, capture_output=True, timeout=10)
    require(solver.stdout.strip() in ("sat", "unsat"), "solver did not decide the original conversion")
    require(solver.stdout.strip() == "unsat", "private bytecode contradicts the declared weekday result")
    freeze = json.loads((CASE.parent / "freeze.json").read_bytes())
    proof = {"entry": spec["entry"], "rows": rows, "commit": manifest["commit"], "orderedClasspath": manifest["classpath"],
             "provider": str(jar), "jdk": freeze["jdk"], "classSha256": hash_bytes(data),
             "poolSha256": hash_bytes(data[10:runtime_jar._pool(data)[1]]), "codeSha256": bodies[CONVERT]["codeSha256"],
             "bodies": {name + desc: body for (name, desc), body in bodies.items()},
             "scope": "Every signed int after successful initialization. All control paths terminate normally, read only the argument and constants, and have no heap or static writes.",
             "qualificationSha256": sha(Path(__file__)), "declaredSpec": spec, "query": query,
             "solver": subprocess.check_output(["z3", "--version"], text=True).strip(), "counterexample": "unsat"}
    return proof | {"key": identity(proof)}


def number_strategy(manifest, repaired):
    artifact, = manifest["classpath"]
    jar = Path(artifact["file"])
    require(sha(jar) == artifact["sha256"], "different strategy deployment")
    owner = PARSER.replace(".", "/")
    data = runtime_jar.read_class(jar, owner)
    pool, declarations, _ = runtime_jar._declarations(data, with_code=True)
    code = declarations["<clinit>", "()V"][1]
    ops = list(change_inventory.instructions(code))

    def member(pc):
        return runtime_jar._member_ref(pool, pool[int.from_bytes(code[pc+1:pc+3], "big")][1])

    index, = [i for i, (pc, op) in enumerate(ops) if op == 0xb3 and member(pc) ==
              (owner, "DAY_OF_WEEK_STRATEGY", "L" + owner + "$Strategy;")]
    init = ops[index-4:index+1]
    require([op for _, op in init] == [0xbb, 0x59, 0x10, 0xb7, 0xb3]
            and code[init[2][0]+1] == 7, "weekday field is not the argument of the selected strategy")
    start = init[0][0]
    selected = runtime_jar._class_name(pool, int.from_bytes(code[start+1:start+3], "big"))
    require(member(init[3][0]) == (selected, "<init>", "(I)V"), "different constructed strategy")
    strategy = runtime_jar.read_class(jar, selected)
    subpool, methods, _ = runtime_jar._declarations(strategy, with_code=True)
    flags, body, handlers = methods["modify", "(L" + owner + ";I)I"]
    require(flags == 0 and not handlers and runtime_jar.super_class(strategy) == owner + "$NumberStrategy",
            "changed strategy superclass, dispatch or exception table")
    if repaired:
        require(len(body) == 5 and body[:2] == bytes.fromhex("1cb8") and body[-1] == 0xac
                and runtime_jar._member_ref(subpool, subpool[int.from_bytes(body[2:4], "big")][1]) == (owner, *BRIDGE),
                "fixed strategy did not pass its original day directly to the bridge")
    else:
        # iload_2, bipush 7, if_icmpne 10, iconst_1, goto 13, iload_2, iconst_1, iadd, ireturn.
        require(body.hex() == "1c1007a0000704a700061c0460ac", "parent weekday expression or branch destinations differ")
    return {"commit": manifest["commit"], "jar": artifact["sha256"], "selected": selected, "strategyClass": hash_bytes(strategy),
            "parserClass": hash_bytes(data), "initializerCode": hash_bytes(code), "putstatic": init[-1][0], "body": body.hex()}


def compare_strategies(old, new, proof):
    bindings = {"old": number_strategy(old, False), "new": number_strategy(new, True)}
    definitions = [line for line in proof["query"].splitlines() if line.startswith("(define-fun ")]
    domain = f"(and (bvsge x {bv(1)}) (bvsle x {bv(7)}))"
    parent = f"(ite (= x {bv(7)}) {bv(1)} (bvadd x {bv(1)}))"
    query = "\n".join(["(set-logic QF_BV)", *definitions, "(declare-const x (_ BitVec 32))",
                       f"(assert (xor (= {parent} (access$800 x)) {domain}))", "(check-sat)"]) + "\n"
    answer = subprocess.run(["z3", "-in"], input=query, text=True, capture_output=True, check=True, timeout=10).stdout.strip()
    require(answer == "unsat", "weekday strategies have a different agreement domain")
    return {"bindings": bindings, "query": query, "counterexample": answer, "equalSignedInputs": 7,
            "differentSignedInputs": 2**32 - 7, "scope": "The installed weekday number strategies agree precisely on ISO days 1 through 7. The public parsing claims cover only their registered histories."}


def calendar_consumers(jar):
    parser = PARSER.replace(".", "/")
    number, recorder = parser + "$NumberStrategy", parser + "$WeekDateRecorder"
    calendar = "java/util/Calendar"
    # Exact normal continuations of the substituted int. Each pattern selects exactly one instruction
    # sequence in the original method; calls and fields include their resolved constant-pool identity.
    patterns = [
        (number, "parse", "(L" + parser + ";Ljava/util/Calendar;Ljava/lang/String;Ljava/text/ParsePosition;I)Z",
         [(0xb6, (number, "modify", "(L" + parser + ";I)I")), (0xb6, (calendar, "set", "(II)V")), 0x04, 0xac]),
        (recorder, "set", "(II)V", [0x2a, (0xb4, (recorder, "target", "Ljava/util/Calendar;")), 0x1b, 0x1c,
                                    (0xb6, (calendar, "set", "(II)V")), 0xb1]),
        (recorder, "applyWeekDate", "()V", [(0xb8, (parser, *BRIDGE)), 0x3d, 0x2a,
             (0xb4, (recorder, "target", "Ljava/util/Calendar;")), 0x2a, (0xb4, (recorder, "weekYearValue", "I")),
             0x1b, 0x1c, (0xb6, (calendar, "setWeekDate", "(III)V")), 0xb1])]
    result = {}
    for owner, name, desc, wanted in patterns:
        data = runtime_jar.read_class(jar, owner)
        pool, methods, _ = runtime_jar._declarations(data, with_code=True)
        body = methods[name, desc][1]
        positions, instructions = [], []
        for pc, op in change_inventory.instructions(body):
            positions.append(pc)
            if 0xb2 <= op <= 0xb9:
                instructions.append((op, runtime_jar._member_ref(pool, pool[int.from_bytes(body[pc+1:pc+3], "big")][1])))
            else:
                instructions.append(op)
        i, = [i for i in range(len(instructions)) if instructions[i:i+len(wanted)] == wanted]
        result[owner + "#" + name + desc] = {"class": hash_bytes(data), "code": hash_bytes(body),
            "sites": positions[i:i+len(wanted)], "instructions": [list(x) if isinstance(x, tuple) else x for x in wanted]}
    return result
