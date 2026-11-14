"""What a preparation checks in the bytes it is given (llm-dlc/loops/example-targets.md, runtime's R1-R3): the classes
each JAR on a classpath holds, which one the JVM loads for a name (the first on the classpath), every class held twice
(shadowing), whether the original target method is in the original artifact, and whether an adapter calls it. A small
class-file reader, offline; nothing here runs Java. Runtime stream's.

    classes(jar)                      {internal class name: sha256 of its bytes}
    resolve(classpath, root)          {class: [jar, ...]} in classpath order: the first loads, the rest are shadowed
    duplicates(classpath, root)       the classes held by more than one entry, with each holder
    parse_target(target)              ("fixture.Gate", "allowed", "(I)Z" or None) from <class>#<method>(<descriptor>)
    methods(class_bytes)              {(name, descriptor)} a class declares
    references(class_bytes)           {(owner, name, descriptor)} the method references in its constant pool
"""

import hashlib
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
    with zipfile.ZipFile(jar) as z:
        try:
            return z.read(name + ".class")
        except KeyError:
            return None


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


# Constant pool tags and the number of bytes after the tag of each fixed-size one.
_FIXED = {3: 4, 4: 4, 5: 8, 6: 8, 7: 2, 8: 2, 9: 4, 10: 4, 11: 4, 12: 4, 15: 3, 16: 2, 17: 4, 18: 4, 19: 2, 20: 2}


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
            pool[i] = (1, data[offset + 2: offset + 2 + length].decode("utf-8", "surrogatepass"))
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


def methods(data):
    """{(name, descriptor)} of the methods the class declares."""
    pool, offset = _pool(data)
    offset += 6  # access, this, super
    interfaces = struct.unpack_from(">H", data, offset)[0]
    offset += 2 + 2 * interfaces
    for _ in range(2):  # fields, then methods
        count = struct.unpack_from(">H", data, offset)[0]
        offset += 2
        found = set()
        for _ in range(count):
            _, name, desc, attributes = struct.unpack_from(">HHHH", data, offset)
            offset += 8
            for _ in range(attributes):
                length = struct.unpack_from(">I", data, offset + 2)[0]
                offset += 6 + length
            found.add((_utf8(pool, name), _utf8(pool, desc)))
    return found


def references(data):
    """{(owner, name, descriptor)} of every Methodref and InterfaceMethodref in the class's constant pool."""
    pool, _ = _pool(data)
    out = set()
    for tag, value in pool.values():
        if tag in (10, 11):
            owner, nat = value
            name, desc = pool[nat][1]
            out.add((_class_name(pool, owner), _utf8(pool, name), _utf8(pool, desc)))
    return out
