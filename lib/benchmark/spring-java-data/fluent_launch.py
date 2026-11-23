"""Discharge the separator premise of the existing native proofs for two exact JVM launches."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

import fluent_lines as lines
from historical_companion import prepare_graph
from measure import ROOT, digest, read, write
from targets import runtime_jar

SOURCE = lines.FOLDER / "companions/FluentLaunch.java"
DEST = lines.FOLDER / "records/fluent-launches"
PRODUCER = "20261123-030518-measure-four-spring-startup-boundaries-o"
CHECKS = "springwork/RoleChecks"
ENTRY = "springwork.FluentLaunch"
VM_FILES = ("bin/java", "lib/server/libjvm.so", "lib/modules", "release")
ENV = {"LC_ALL": "C", "TZ": "UTC"}


def require(ok, detail):
    if not ok:
        raise ValueError(detail)


def ref(pool, code, at):
    index = int.from_bytes(code[at + 1:at + 3], "big")
    tag, (owner, pair) = pool[index]
    names, (name, desc) = pool[pair]
    require(tag == 10 and names == 12, "expected a class method reference")
    return runtime_jar._class_name(pool, owner), runtime_jar._utf8(pool, name), runtime_jar._utf8(pool, desc)


def guard(caller):
    pool, methods, _ = runtime_jar._declarations(caller, with_code=True)
    flags, code, handlers = methods["check", "(I)I"]
    require(runtime_jar.this_class(caller) == "springwork/FluentLines" and ("<clinit>", "()V") not in methods
            and flags == 9 and not handlers and len(code) == 34, "different fluent guard entry")
    expected = bytearray.fromhex("b8 0000 4c 12 00 2b b6 0000 9a 000e 12 00 2b b6 0000 9a 0005 04 ac 1a b8 0000 1a b8 0000 7e ac")
    for pos, call in [(0, ("java/lang/System", "lineSeparator", "()Ljava/lang/String;")),
                      (7, ("java/lang/String", "equals", "(Ljava/lang/Object;)Z")),
                      (16, ("java/lang/String", "equals", "(Ljava/lang/Object;)Z")),
                      (25, (CHECKS, "fluentNames", "(I)I")), (29, (CHECKS, "fluentDecision", "(I)I"))]:
        require(ref(pool, code, pos) == call, "different fluent guard or public call")
        expected[pos + 1:pos + 3] = code[pos + 1:pos + 3]
    for pos, literal in [(4, "\n"), (13, "\r\n")]:
        tag, index = pool[code[pos + 1]]
        require(tag == 8 and runtime_jar._utf8(pool, index) == literal, "different fluent separator literal")
        expected[pos + 1] = code[pos + 1]
    require(code == expected, "different fluent branches, invocation arguments or conjunction")


def boolean_returns(code):
    """Every incoming edge at every int return must push 0/1, possibly through gotos."""
    # Instruction widths of the two original observers. Reject every unrecognized opcode.
    single = {0x02, 0x03, 0x04, 0x05, 0x07, 0x1a, 0x1b, 0x1c, 0x1d, 0x2b, 0x2c, 0x2d,
              0x3b, 0x3c, 0x3d, 0x3e, 0x4c, 0x4d, 0x4e, 0x78, 0x7e, 0x80, 0xac}
    two = {0x10, 0x15, 0x19, 0x36, 0x3a}
    branch = {0x99, 0x9a, 0xa0, 0xa2, 0xa7}
    three = {0x84, 0xb6, 0xb8, 0xc0} | branch
    preds, ops = {}, {}
    pc = 0
    while pc < len(code):
        op = ops[pc] = code[pc]
        width = 1 if op in single else 2 if op in two else 3 if op in three else 5 if op == 0xb9 else 0
        require(width and pc + width <= len(code), f"unexpected result observer instruction at {pc}")
        targets = [] if op in (0xa7, 0xac) else [pc + width]
        if op in branch:
            targets.append(pc + int.from_bytes(code[pc + 1:pc + 3], "big", signed=True))
        for target in targets:
            preds.setdefault(target, set()).add(pc)
        pc += width
    returns = [pc for pc, op in ops.items() if op == 0xac]
    require(returns and set(preds) <= set(ops), "invalid result observer control flow")
    for end in returns:
        todo = [end]
        seen = set()
        while todo:
            at = todo.pop()
            require(at not in seen and at in preds and at != 0, "unqualified route to an observer return")
            seen.add(at)
            for prev in preds[at]:
                if ops[prev] == 0xa7:
                    todo.append(prev)
                else:
                    require(ops[prev] in (0x03, 0x04), "a fluent observer may return an int outside zero and one")


def observers(data):
    pool, methods, _ = runtime_jar._declarations(data, with_code=True)
    require(runtime_jar.this_class(data) == CHECKS and ("<clinit>", "()V") not in methods, "different role observer class")
    for name, desc in [("names", "(IZ)I"), ("fluentDecision", "(I)I")]:
        flags, code, handlers = methods[name, desc]
        require(flags == (8 if name == "names" else 9) and not handlers, "different fluent observer entry")
        boolean_returns(code)
    flags, code, handlers = methods["fluentNames", "(I)I"]
    require(flags == 9 and not handlers and len(code) == 6 and code[:3] == bytes.fromhex("1a 04 b8") and code[-1] == 0xac
            and ref(pool, code, 2) == (CHECKS, "names", "(IZ)I"), "different public fluent name observer")


def rows(separator):
    units = "".join(f" {ord(c)}" for c in separator)
    active = separator in ("\n", "\r\n")
    return ["startup" + units, "property" + units, f"active {int(active)}",
            *lines.expected(separator)[1:]]


def measure(replay=False):
    with tempfile.TemporaryDirectory(prefix="fluent-launch-") as scratch:
        work = Path(scratch)
        jdk, graph, paths, bound = prepare_graph(lines.FOLDER, "landed", "fluent-names-landed", work)
        producer = read(lines.DEST / "measurement.json")
        caller = (lines.DEST / "FluentLines.jvm-bytecode").read_bytes()
        require(producer["job"] == PRODUCER and digest(lines.DEST / "FluentLines.jvm-bytecode") == producer["callerSha256"]
                and bound[1:] == producer["classpath"] and graph["jdk"] == producer["jdk"], "different proof producer or classpath")
        from scorecard import managed
        from startup_results import fluent_lines
        case = read(ROOT / "verification/spring-java-data/spring.json")["examples"]["370"]
        checked = fluent_lines(managed(PRODUCER), case, graph)
        require(checked["checked"] == 32 and checked["checkerSha256"] == producer["checkerSha256"],
                "the deployment premise has no complete guarded native proof")
        guard(caller)
        classes = work / "classes"
        package = classes / "springwork"
        package.mkdir(parents=True)
        (package / "FluentLines.class").write_bytes(caller)
        binding, = [b for b in producer["bindings"] if b["class"] == CHECKS.replace("/", ".") and b["method"] == "fluentNames"]
        with zipfile.ZipFile(next(p for p in paths[1:] if p.name == binding["provider"])) as jar:
            original = jar.read(CHECKS + ".class")
        require(hashlib.sha256(original).hexdigest() == binding["sha256"], "different original role observer")
        observers(original)
        cp = os.pathsep.join(map(str, [classes, *paths[1:]]))
        subprocess.run([jdk / "bin/javac", "--release", "21", "-proc:none", "-cp", cp, "-d", classes, SOURCE], env=ENV, check=True)
        compiled = package / "FluentLaunch.class"
        report = {"producer": PRODUCER, "checkerSha256": checked["checkerSha256"], "guardSha256": producer["callerSha256"], "observersSha256": binding["sha256"],
                  "casesSha256": digest(lines.DEST / "cases.tar.gz"), "classpath": bound[1:], "jdk": graph["jdk"],
                  "runtimeSha256": {name: digest(jdk / name) for name in VM_FILES}, "environment": ENV,
                  "sourceSha256": digest(SOURCE), "launchClassSha256": digest(compiled), "profiles": {}}
        if not replay:
            DEST.mkdir(parents=True, exist_ok=True)
            (DEST / "FluentLaunch.jvm-bytecode").write_bytes(compiled.read_bytes())
            (DEST / "RoleChecks.jvm-bytecode").write_bytes(original)
        for profile, sep in lines.PROFILES.items():
            options = [] if profile == "default" else ["-Dline.separator=" + sep]
            raw = subprocess.check_output([jdk / "bin/java", *options, "-cp", cp, ENTRY], env=ENV)
            require(raw.decode("ascii").splitlines() == rows(sep), f"startup condition or public outcomes differ on {profile}")
            active = sep in ("\n", "\r\n")
            report["profiles"][profile] = {"vmOptions": options, "initialUnits": list(map(ord, sep)), "guardActive": active,
                                           "nativeCoverage": 32 if active else 0, "stdoutSha256": hashlib.sha256(raw).hexdigest()}
            if not replay:
                (DEST / (profile + ".stdout")).write_bytes(raw)
        if not replay:
            write(DEST / "measurement.json", {**report, "job": os.environ["VERIFY_JOB_ID"], "source": os.environ["VERIFY_SOURCE_COMMIT"]})
        print("Two launches satisfy the native guard on all 32 original calls. The custom separator misses it.")


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--replay", action="store_true")
    measure(cli.parse_args().replay)
