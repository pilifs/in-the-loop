"""What a preparation checks in the bytes it is given (llm-dlc/loops/example-targets.md, runtime's R1-R3): the classes
each JAR on a classpath holds, which one the JVM loads for a name (the first on the classpath), every class held twice
(shadowing), whether the original target method is in the original artifact, and whether an adapter calls it. A small
class-file reader, offline; nothing here runs Java. Runtime stream's.

    classes(jar)                      {internal class name: sha256 of its bytes}
    resolve(classpath, root)          {class: [jar, ...]} in classpath order: the first loads, the rest are shadowed
    duplicates(classpath, root)       the classes held by more than one entry, with each holder
    parse_target(target)              ("fixture.Gate", "allowed", "(I)Z" or None) from <class>#<method>(<descriptor>)
    feature_needed(jar)               the oldest Java feature release that loads every class in it (major - 44)
    methods(class_bytes)              {(name, descriptor)} a class declares
    super_class(class_bytes)          its superclass's internal name (None for java/lang/Object)
    references(class_bytes)           {(owner, name, descriptor)} the method references in its constant pool
    resolve_method(owner, n, d, look) the class whose declaration a method reference resolves to, up the superclass
                                      chain as the JVM resolves it, among the classes `look` has bytes for
    debug_attributes(class_bytes)     the debugging attributes it records: which javac flags made it
"""

import hashlib
import re
import struct
import zipfile
from pathlib import Path


def classes(jar):
    """{internal name (fixture/Gate): sha256} of every class file in `jar`; module-info and multi-release copies
    (META-INF/versions/N/...) are kept under their own entry names, never merged into the base names."""
    out = {}
    with zipfile.ZipFile(jar) as z:
        for info in z.infolist():
            if info.filename.endswith(".class") and not info.is_dir():
                out[info.filename[:-6]] = hashlib.sha256(z.read(info)).hexdigest()
    return out


def read_class(jar, name):
    """The bytes of class `name` (internal form) in `jar`, or None."""
    if Path(jar).is_dir():
        file = Path(jar) / (name + ".class")
        return file.read_bytes() if file.is_file() else None
    with zipfile.ZipFile(jar) as z:
        try:
            return z.read(name + ".class")
        except KeyError:
            return None


def multi_release(manifest):
    """How a manifest's bytes enable multi-release lookup: "enabled", "disabled" or "ambiguous". The rule is the
    checker's (lib/src/classpath.rs, `multi_release`), held to the same fifteen spellings measured on JDK 17, 21 and
    25: enabled when the bytes hold `Multi-Release: true` literally (either case, one space) and the main section's
    attribute, with continuation lines joined and the last value taken, is `true` on a line that is ended. Ambiguous
    when the joined attribute reads true and the literal is absent (a value folded over two lines): the runtimes
    measured load the base entries of such a JAR, and a reader that joins lines first the versioned ones."""
    literal = b"multi-release: true" in manifest.lower()
    text = manifest.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    main, blank, _ = text.partition(b"\n\n")
    if not blank:  # no empty line ends the main section: a last line without a line break is not read
        main = main.rpartition(b"\n")[0]
    pairs = [(k.lower(), v) for line in main.replace(b"\n ", b"").splitlines() for k, sep, v in [line.partition(b": ")] if sep]
    values = [v for k, v in pairs if k == b"multi-release"]
    if not values or values[-1].lower() != b"true":
        return "disabled"
    return "enabled" if literal else "ambiguous"


def effective_entries(archive, feature):
    """The logical entries a JVM of the specified feature sees in its original JAR: an inventory view, for the tools
    that list a whole JAR. Which class file stands for a class a proof is about is not decided here but bound
    (class_binding.py): by the checker's resolver and by what a JVM was seen to load. A JAR whose manifest readers
    differ on is listed as the runtimes measured read it, by its base entries."""
    entries = {item.filename: item for item in archive.infolist() if not item.is_dir()}
    manifest = entries.get("META-INF/MANIFEST.MF")
    if not manifest or multi_release(archive.read(manifest)) != "enabled":
        return entries
    ranks = {}
    for name, item in list(entries.items()):
        if not name.startswith("META-INF/versions/"):
            continue
        del entries[name]
        version, _, logical = name[len("META-INF/versions/"):].partition("/")
        if (not logical or logical.startswith("META-INF/") or not re.fullmatch(r"[1-9][0-9]{0,8}", version)):
            continue
        release = int(version)
        if 9 <= release <= feature and release > ranks.get(logical, 0):
            ranks[logical] = release
            entries[logical] = item
    return entries


def effective_class(jar, name, feature):
    with zipfile.ZipFile(jar) as archive:
        selected = effective_entries(archive, feature).get(name + ".class")
        return archive.read(selected) if selected is not None else None


def resolve(classpath, root="."):
    """{class: [classpath entry, ...]} in classpath order, for JAR entries (a directory entry is listed by its class
    files): the first holder is the one the JVM loads."""
    holders = {}
    for entry in classpath:
        path = Path(root) / entry
        names = classes(path) if path.is_file() else {
            p.relative_to(path).as_posix()[:-6]: None for p in sorted(path.rglob("*.class"))} if path.is_dir() else {}
        for name in names:
            holders.setdefault(name, []).append(entry)
    return holders


def duplicates(classpath, root="."):
    """[(class, [holders])] for each class more than one classpath entry holds (module-info excepted): on such a
    classpath the class actually loaded depends on order, so a preparation refuses it unless the bytes are proved
    equal (they aren't checked equal here: a duplicate is reported either way)."""
    return [(name, entries) for name, entries in sorted(resolve(classpath, root).items())
            if len(entries) > 1 and not name.endswith("module-info")]


def parse_target(target):
    """(dotted class, method, descriptor or None) from `pkg.Class#method(desc)ret` or `pkg.Class#method`."""
    cls, sep, rest = target.partition("#")
    if not sep or not cls or not rest:
        raise ValueError(f"not a <class>#<method> target: {target!r}")
    name, paren, desc = rest.partition("(")
    return cls, name, ("(" + desc) if paren else None


def internal(dotted):
    return dotted.replace(".", "/")


def feature_needed(jar):
    """The lowest Java feature release that can load every class file in `jar` (class file major version - 44), or
    None for a JAR with no classes. A JDK older than that refuses the bytes before any of them runs."""
    majors = []
    with zipfile.ZipFile(jar) as z:
        for info in z.infolist():
            if info.filename.endswith(".class") and not info.filename.startswith("META-INF/versions/"):
                head = z.read(info)[:8]
                if head[:4] == b"\xca\xfe\xba\xbe":
                    majors.append(struct.unpack(">H", head[6:8])[0])
    return max(majors) - 44 if majors else None


# Constant pool tags and the number of bytes after the tag of each fixed-size one.
_FIXED = {3: 4, 4: 4, 5: 8, 6: 8, 7: 2, 8: 2, 9: 4, 10: 4, 11: 4, 12: 4, 15: 3, 16: 2, 17: 4, 18: 4, 19: 2, 20: 2}


def modified_utf8(data):
    """Read a CONSTANT_Utf8 (JVMS 4.4.7), retaining isolated Java UTF-16 surrogates."""
    if re.search(rb"[\x00\xf0-\xff]", data):
        raise ValueError("literal NUL or four-byte sequence in class-file modified UTF-8")
    text = data.replace(b"\xc0\x80", b"\0").decode("utf-8", "surrogatepass")
    if b"\xed" in data:
        # A supplementary character is stored as two encoded UTF-16 code units.
        return text.encode("utf-16-be", "surrogatepass").decode("utf-16-be", "surrogatepass")
    return text


def _pool(data):
    """The constant pool as {index: (tag, value)} and the offset just after it."""
    if data[:4] != b"\xca\xfe\xba\xbe":
        raise ValueError("not a class file")
    count = struct.unpack_from(">H", data, 8)[0]
    pool, i, offset = {}, 1, 10
    while i < count:
        tag = data[offset]
        offset += 1
        if tag == 1:
            length = struct.unpack_from(">H", data, offset)[0]
            if offset + 2 + length > len(data):
                raise ValueError(f"truncated modified UTF-8 at constant pool entry {i}")
            pool[i] = (1, modified_utf8(data[offset + 2: offset + 2 + length]))
            offset += 2 + length
        elif tag in _FIXED:
            size = _FIXED[tag]
            raw = data[offset: offset + size]
            pool[i] = (tag, struct.unpack(">HH", raw) if size == 4 and tag in (9, 10, 11, 12, 17, 18)
                       else struct.unpack(">H", raw)[0] if size == 2 else raw)
            offset += size
        else:
            raise ValueError(f"unknown constant pool tag {tag} at entry {i}")
        i += 2 if tag in (5, 6) else 1
    return pool, offset


def _utf8(pool, index):
    return pool[index][1]


def _class_name(pool, index):
    return _utf8(pool, pool[index][1])


def this_class(data):
    pool, offset = _pool(data)
    return _class_name(pool, struct.unpack_from(">H", data, offset + 2)[0])


def super_class(data):
    """The internal name of the class's superclass, or None for java/lang/Object (super_class 0)."""
    pool, offset = _pool(data)
    index = struct.unpack_from(">H", data, offset + 4)[0]
    return _class_name(pool, index) if index else None


def _declarations(data, with_code=False, *, field_declarations=None):
    """The constant pool, declared method access flags, and offset of the class attributes."""
    pool, offset = _pool(data)
    offset += 6  # access, this, super
    interfaces = struct.unpack_from(">H", data, offset)[0]
    offset += 2 + 2 * interfaces
    for table in range(2):  # fields, then methods
        count = struct.unpack_from(">H", data, offset)[0]
        offset += 2
        found = {}
        for _ in range(count):
            access, name, desc, attributes = struct.unpack_from(">HHHH", data, offset)
            offset += 8
            body, handlers = None, None
            for _ in range(attributes):
                attribute, length = struct.unpack_from(">HI", data, offset)
                if with_code and table == 1 and _utf8(pool, attribute) == "Code":
                    size = struct.unpack_from(">I", data, offset + 10)[0]
                    if size + 12 > length:
                        raise ValueError("truncated method Code attribute")
                    body = data[offset + 14:offset + 14 + size]
                    handlers = struct.unpack_from(">H", data, offset + 14 + size)[0]
                offset += 6 + length
            found[_utf8(pool, name), _utf8(pool, desc)] = (access, body, handlers) if with_code else access
        if table == 0 and field_declarations is not None:
            field_declarations.update(found)
    return pool, found, offset


def methods(data):
    """{(name, descriptor)} of the methods the class declares."""
    return set(_declarations(data)[1])


def method_flags(data, method, descriptor):
    return _declarations(data)[1].get((method, descriptor))


def class_flags(data):
    _, offset = _pool(data)
    return struct.unpack_from(">H", data, offset)[0]


def interfaces(data):
    pool, offset = _pool(data)
    count = struct.unpack_from(">H", data, offset + 6)[0]
    return [_class_name(pool, struct.unpack_from(">H", data, offset + 8 + 2 * i)[0]) for i in range(count)]


def source_file(data):
    pool, _, offset = _declarations(data)
    count = struct.unpack_from(">H", data, offset)[0]
    offset += 2
    for _ in range(count):
        name, length = struct.unpack_from(">HI", data, offset)
        if _utf8(pool, name) == "SourceFile" and length == 2:
            return _utf8(pool, struct.unpack_from(">H", data, offset + 6)[0])
        offset += 6 + length
    return None


def _parameter_types(desc):
    """The parameter descriptors of a method descriptor, in order."""
    out, i, inner = [], 0, desc[1:desc.index(")")]
    while i < len(inner):
        start = i
        while inner[i] == "[":
            i += 1
        i = inner.index(";", i) + 1 if inner[i] == "L" else i + 1
        out.append(inner[start:i])
    return out


def parameter_names(data, method, descriptor):
    """(names, where) of the declared method's parameters as the class records them: from `MethodParameters` (javac
    -parameters), else the `LocalVariableTable` (javac -g), as jvmcontract reads them; ([arg0, ...], None) when the
    class records none, which is what the verifier then calls them. None when the class doesn't declare the method."""
    pool, offset = _pool(data)
    offset += 6
    offset += 2 + 2 * struct.unpack_from(">H", data, offset)[0]
    for kind in ("field", "method"):
        count = struct.unpack_from(">H", data, offset)[0]
        offset += 2
        for _ in range(count):
            access, name, desc, attributes = struct.unpack_from(">HHHH", data, offset)
            offset += 8
            mine = kind == "method" and (_utf8(pool, name), _utf8(pool, desc)) == (method, descriptor)
            found = {}
            for _ in range(attributes):
                attr, length = struct.unpack_from(">HI", data, offset)
                body = data[offset + 6: offset + 6 + length]
                offset += 6 + length
                if mine:
                    found[_utf8(pool, attr)] = body
            if mine:
                return _names(pool, access, descriptor, found)
    return None


def _names(pool, access, descriptor, attributes):
    types = _parameter_types(descriptor)
    fallback = [f"arg{i}" for i in range(len(types))]
    body = attributes.get("MethodParameters")
    if body is not None:
        names = [struct.unpack_from(">H", body, 1 + 4 * i)[0] for i in range(body[0])]
        if len(names) == len(types) and all(names):
            return [_utf8(pool, n) for n in names], "MethodParameters"
    code = attributes.get("Code")
    if code is None:
        return fallback, None
    at = 8 + struct.unpack_from(">I", code, 4)[0]
    at += 2 + 8 * struct.unpack_from(">H", code, at)[0]
    table = {}
    for _ in range(struct.unpack_from(">H", code, at)[0]):
        attr, length = struct.unpack_from(">HI", code, at + 2)
        if _utf8(pool, attr) == "LocalVariableTable":
            for k in range(struct.unpack_from(">H", code, at + 8)[0]):
                start, _, name, _, slot = struct.unpack_from(">HHHHH", code, at + 10 + 10 * k)
                if start == 0:
                    table[slot] = _utf8(pool, name)
        at += 6 + length
    slot, names = (0 if access & 0x0008 else 1), []
    for t in types:
        names.append(table.get(slot))
        slot += 2 if t in ("J", "D") else 1
    return (names, "LocalVariableTable") if all(names) else (fallback, None)


DEBUG_ATTRIBUTES = ("SourceFile", "LineNumberTable", "LocalVariableTable", "MethodParameters")


def debug_attributes(data):
    """The debugging attributes a class records anywhere (on the class, a method, or a method's Code), of
    DEBUG_ATTRIBUTES: which javac flags made it (`-g` for the LocalVariableTable, `-parameters` for MethodParameters;
    javac's default gives SourceFile and LineNumberTable)."""
    pool, offset = _pool(data)
    found = set()
    offset += 6
    offset += 2 + 2 * struct.unpack_from(">H", data, offset)[0]

    def attributes(at, inside_code=False):
        count = struct.unpack_from(">H", data, at)[0]
        at += 2
        for _ in range(count):
            attr, length = struct.unpack_from(">HI", data, at)
            name = _utf8(pool, attr)
            if name in DEBUG_ATTRIBUTES:
                found.add(name)
            if name == "Code" and not inside_code:
                code = at + 6
                code += 8 + struct.unpack_from(">I", data, code + 4)[0]
                code += 2 + 8 * struct.unpack_from(">H", data, code)[0]
                attributes(code, True)
            at += 6 + length
        return at

    for _ in ("field", "method"):
        count = struct.unpack_from(">H", data, offset)[0]
        offset += 2
        for _ in range(count):
            offset = attributes(offset + 6)
    attributes(offset)
    return found


def _member_ref(pool, value):
    owner, nat = value
    name, desc = pool[nat][1]
    return _class_name(pool, owner), _utf8(pool, name), _utf8(pool, desc)


def references(data):
    """{(owner, name, descriptor)} of every Methodref and InterfaceMethodref in the class's constant pool."""
    pool, _ = _pool(data)
    return {_member_ref(pool, value) for tag, value in pool.values() if tag in (10, 11)}


def member_reference_kinds(data, operand):
    pool, _ = _pool(data)
    kinds = {9: "field", 10: "method", 11: "interface method"}
    return sorted({kinds[tag] for tag, value in pool.values() if tag in kinds and _member_ref(pool, value) == operand})


def member_at_code_index(data, name, descriptor, index, *, code_sha256, pool_sha256):
    """Resolve the field or method instruction at a bytecode index reported by a live JVM."""
    pool, declarations, _ = _declarations(data, with_code=True)
    _, code, _ = declarations.get((name, descriptor), (None, None, None))
    if (not code or not 0 <= index <= len(code) - 3 or hashlib.sha256(code).hexdigest() != code_sha256
            or hashlib.sha256(data[10:_pool(data)[1]]).hexdigest() != pool_sha256):
        return None
    opcodes = ("getstatic", "putstatic", "getfield", "putfield", "invokevirtual", "invokespecial",
               "invokestatic", "invokeinterface")
    opcode = code[index]
    if not 0xb2 <= opcode <= 0xb9:
        return None
    tag, value = pool[struct.unpack_from(">H", code, index + 1)[0]]
    allowed = (9,) if opcode <= 0xb5 else (11,) if opcode == 0xb9 else (10,) if opcode == 0xb6 else (10, 11)
    if tag not in allowed:
        return None
    owner, member, desc = _member_ref(pool, value)
    return {"opcode": opcodes[opcode - 0xb2], "owner": owner.replace("/", "."), "name": member,
            "descriptor": desc, "referenceKind": {9: "field", 10: "method", 11: "interface method"}[tag]}


def type_references(data, target):
    """Symbolic class constants and JVM descriptors naming an exact internal type."""
    fields = set()
    pool, declarations, _ = _declarations(data, field_declarations=fields)
    def mentions(descriptor):
        return target in re.findall(r"L([^;]+);", descriptor)
    kinds = set()
    for tag, value in pool.values():
        if tag == 7:
            name = _utf8(pool, value)
            if name == target or (name.startswith("[") and mentions(name)):
                kinds.add("class constant")
        elif tag == 12 and mentions(_utf8(pool, value[1])):
            kinds.add("member reference descriptor")
        elif tag == 16 and mentions(_utf8(pool, value)):
            kinds.add("method type descriptor")
    methods = sorted(name + desc for name, desc in declarations if mentions(desc))
    field_names = sorted(name + ":" + desc for name, desc in fields if mentions(desc))
    if methods:
        kinds.add("method declaration")
    if field_names:
        kinds.add("field declaration")
    return {"kinds": sorted(kinds), "methods": methods, "fields": field_names}


def resolve_method(owner, name, descriptor, look):
    """The class whose declaration of name+descriptor a Methodref owned by `owner` resolves to: the owner if it
    declares it, else the nearest superclass that does (JVMS 5.4.3.3's class step). `look(internal name)` gives a
    class's bytes or None. So javac's `isAllowed(field)` in a subclass of DataBinder, a reference owned by the
    subclass, resolves to DataBinder. None when the chain reaches a class `look` has no bytes for (a JDK class) before
    a declaration: never a guess. Superinterfaces' default methods aren't followed."""
    seen = set()
    while owner and owner not in seen:
        seen.add(owner)
        data = look(owner)
        if data is None:
            return None
        if (name, descriptor) in methods(data):
            return owner
        owner = super_class(data)
    return None
