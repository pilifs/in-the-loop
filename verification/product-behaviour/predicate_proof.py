"""Check the original predicate or visitor bytecode used by the three live continuations."""
import hashlib
import itertools
import json
from pathlib import Path

from targets import change_inventory, runtime_jar, upgrade_replay


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def method(jar, owner, name, desc):
    data = runtime_jar.read_class(jar, owner.replace(".", "/"))
    pool, declarations, _ = runtime_jar._declarations(data, with_code=True)
    flags, code, handlers = declarations[name, desc]
    require(code and not handlers and not flags & (0x20 | 0x100), "unexpected handler, monitor or native body")
    instructions = dict(change_inventory.instructions(code))
    references = {}
    for pc, op in instructions.items():
        if 0xb2 <= op <= 0xb9:
            index = int.from_bytes(code[pc+1:pc+3], "big")
            references[pc] = runtime_jar._member_ref(pool, pool[index][1])
    return {"owner": owner, "method": name, "descriptor": desc, "code": digest(code),
            "pool": digest(data[10:runtime_jar._pool(data)[1]]), "class": digest(data)}, code, instructions, references, pool


def getter(jar, owner, name, desc, field, field_type):
    identity, code, ops, refs, _ = method(jar, owner, name, desc)
    require(list(ops.values()) == [0x2a,0xb4,0xb0] and refs[1] == (owner.replace(".", "/"),field,field_type),
            "unexpected getter for " + field)
    return identity


def tag(jar, side):
    owner = "org.jsoup.parser.Tag"
    record, code, ops, refs, _ = method(jar,owner,"isEmpty","()Z")
    require(list(ops.values()) == [0x2a,0xb4,0xb2,0x7e,0x99,0x04,0xa7,0x03,0xac]
            and refs == {1: ("org/jsoup/parser/Tag","options","I"), 4: ("org/jsoup/parser/Tag","Void","I")}
            and code[9:11] == bytes([0,7]) and code[13:15] == bytes([0,4]), "changed tag predicate")
    caller, code, ops, refs, _ = method(jar,"org.jsoup.parser.HtmlTreeBuilder","insertElementFor",
                                        "(Lorg/jsoup/parser/Token$StartTag;)Lorg/jsoup/nodes/Element;")
    call = max(pc for pc, ref in refs.items() if ref == ("org/jsoup/parser/Tag","isEmpty","()Z"))
    require(ops[call+3] == 0x99 and ops[call+6] == 0x2a and refs[call+7][1] == "pop", "original pop no longer consumes predicate")
    return record | {"consumer": caller, "consumerOffset": call,
                     "partitions": ["(options & Void) == 0 returns false", "(options & Void) != 0 returns true"],
                     "frame": "Non-null exact Tag, initialized class, arbitrary signed options and Void. No writes or calls."}


def visitor(jar, side):
    alt = "org.commonmark.renderer.html.CoreHtmlNodeRenderer$AltTextVisitor"
    base = "org.commonmark.node.AbstractVisitor"
    node = "org.commonmark.node.Node"
    leaf = "org.commonmark.node.Code"
    sig = "(Lorg/commonmark/node/Code;)V"
    data = runtime_jar.read_class(jar, alt.replace(".", "/"))
    require(runtime_jar.super_class(data) == base.replace(".", "/"), "wrong visitor superclass")
    if side == "new":
        h, code, ops, refs, _ = method(jar,alt,"visit",sig)
        require(list(ops.values()) == [0x2a,0xb4,0x2b,0xb6,0xb6,0x57,0xb1] and refs == {
            1:(alt.replace(".","/"),"sb","Ljava/lang/StringBuilder;"),
            5:(leaf.replace(".","/"),"getLiteral","()Ljava/lang/String;"),
            8:("java/lang/StringBuilder","append","(Ljava/lang/String;)Ljava/lang/StringBuilder;")}, "different visitor effect")
        dependencies = [getter(jar,leaf,"getLiteral","()Ljava/lang/String;","literal","Ljava/lang/String;")]
    else:
        require(("visit",sig) not in runtime_jar.methods(data) and not any(n == "visitChildren" for n, d in runtime_jar.methods(data)),
                "different inherited dispatch")
        h, code, ops, refs, _ = method(jar,base,"visit",sig)
        require(list(ops.values()) == [0x2a,0x2b,0xb6,0xb1] and refs[2] == (base.replace(".","/"),"visitChildren","(Lorg/commonmark/node/Node;)V"),
                "different inherited visit")
        traversal, body, ops2, calls, _ = method(jar,base,"visitChildren","(Lorg/commonmark/node/Node;)V")
        require(list(ops2.values())[:5] == [0x2b,0xb6,0x4d,0x2c,0xc6] and calls[1] == (node.replace(".","/"),"getFirstChild","()Lorg/commonmark/node/Node;")
                and ops2[6+int.from_bytes(body[7:9],"big",signed=True)] == 0xb1, "leaf has another effect")
        require(("getFirstChild","()Lorg/commonmark/node/Node;") not in runtime_jar.methods(runtime_jar.read_class(jar,leaf.replace(".","/"))),
                "different Code child dispatch")
        dependencies = [traversal,getter(jar,node,"getFirstChild","()Lorg/commonmark/node/Node;","firstChild","Lorg/commonmark/node/Node;")]
    return h | {"exit": max(ops), "visitorClass": digest(data), "dependencies": dependencies,
                "frame": "Exact image visitor and leaf Code. Parent preserves the builder. Fix appends the current String using the same original JDK append and receiver."}


def rename(jar, side):
    task = "net.lingala.zip4j.tasks.RenameFilesTask"
    sig = "(Lnet/lingala/zip4j/model/FileHeader;Ljava/util/Map;)Ljava/util/Map$Entry;"
    h, code, ops, refs, pool = method(jar,task,"getCorrespondingEntryFromMap",sig)
    require(list(ops)[11] == 32 and list(ops.values())[:11] == [0x2c,0xb9,0xb9,0x4e,0x2d,0xb9,0x99,0x2d,0xb9,0xc0,0x3a]
            and refs[1] == ("java/util/Map","entrySet","()Ljava/util/Set;")
            and refs[6] == ("java/util/Set","iterator","()Ljava/util/Iterator;")
            and refs[13] == ("java/util/Iterator","hasNext","()Z")
            and refs[22] == ("java/util/Iterator","next","()Ljava/lang/Object;")
            and code[31] == 4 and runtime_jar._class_name(pool,int.from_bytes(code[28:30],"big")) == "java/util/Map$Entry",
            "different original map iteration")
    after = dict(zip(ops,[*list(ops)[1:],len(code)]))
    coverage = set()
    partitions = []
    for prefix, directory, equal in itertools.product((False,True), repeat=3):
        # The iteration prologue has already executed. The sole node and exhausted iterator are bound live.
        stack, pc, path = [], 32, []
        while True:
            require(pc in ops and pc not in path, "unexpected back edge or branch")
            op, next_pc = ops[pc], after[pc]
            path.append(pc)
            if op == 0x2b: stack.append("header")
            elif op == 0x2d: stack.append("iterator")
            elif op == 0x19 and code[pc+1] == 4: stack.append("entry")
            elif op == 0x12:
                kind,index = pool[code[pc+1]]
                require(kind == 8 and runtime_jar._utf8(pool,index) == "/", "different directory boundary")
                stack.append("slash")
            elif op == 0xc0:
                require(runtime_jar._class_name(pool,int.from_bytes(code[pc+1:next_pc],"big")) == "java/lang/String" and stack[-1] == "key",
                        "different cast")
            elif op in (0xb9,0xb6):
                ref = refs[pc]
                calls = {
                    ("java/util/Map$Entry","getKey","()Ljava/lang/Object;"): (["entry"],"key"),
                    ("net/lingala/zip4j/model/FileHeader","getFileName","()Ljava/lang/String;"): (["header"],"name"),
                    ("java/lang/String","endsWith","(Ljava/lang/String;)Z"): (["key","slash"],directory),
                    ("java/lang/String","startsWith","(Ljava/lang/String;)Z"): (["name","key"],prefix),
                    ("java/lang/String","equals","(Ljava/lang/Object;)Z"): (["name","key"],equal),
                    ("java/util/Iterator","hasNext","()Z"): (["iterator"],False)}
                require(ref in calls, "unqualified invocation " + str(ref))
                args,value = calls[ref]
                require(stack[-len(args):] == args, "different predicate operands")
                del stack[-len(args):]
                stack.append(value)
            elif op in (0x99,0xa7):
                if op == 0xa7 or not stack.pop():
                    next_pc = pc + int.from_bytes(code[pc+1:pc+3],"big",signed=True)
            elif op == 0x01: stack.append(None)
            elif op == 0xb0:
                expected = prefix if side == "old" else (directory and prefix) or equal
                require(stack == ["entry" if expected else None], "wrong singleton selection")
                break
            else: raise ValueError(f"unqualified operation at {pc}: {op:#x}")
            pc = next_pc
        coverage.update(path)
        partitions.append({"prefix":prefix,"directory":directory,"equal":equal,"matched":expected,"path":path})
    require(set(pc for pc in ops if pc >= 32) <= coverage, "incomplete selection branches")
    getter_id = getter(jar,"net.lingala.zip4j.model.AbstractFileHeader","getFileName","()Ljava/lang/String;","fileName","Ljava/lang/String;")
    header = runtime_jar.read_class(jar,"net/lingala/zip4j/model/FileHeader")
    require(runtime_jar.super_class(header) == "net/lingala/zip4j/model/AbstractFileHeader" and
            ("getFileName","()Ljava/lang/String;") not in runtime_jar.methods(header), "file name getter dispatch differs")
    returns = [pc for pc,op in ops.items() if op == 0xb0]
    return h | {"returns": returns,"rejectReturn":max(returns),"getter":getter_id,"partitions":partitions,
                "frame":"After the sole original HashMap node has been selected. Its non-null compact ASCII key, value and file name are bound. The suffix reads the header and key and selects the identical node or null."}


def prove(case, jar, side):
    record = {"J01":visitor,"J02":tag,"J06":rename}[case](jar,side)
    record.update(jar=upgrade_replay.sha(jar), side=side, qualifier=upgrade_replay.sha(Path(__file__)))
    record["key"] = digest(json.dumps(record,sort_keys=True).encode())
    return record
