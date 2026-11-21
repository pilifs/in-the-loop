"""The selected class binding of a prepared revision: which exact class file stands for a class name, said once and
taken by every reader (llm-dlc/loops/lib-architecture-fast-follow.md, part 2).

Three parties can each say which bytes a class name means: the checker, a JVM, and these tools. They are kept to one
answer this way:

- **The checker's selection is lib/src/classpath.rs's** (`ClassPath::bind`), asked through one process for a whole
  verifier launch: `ask(exe, env, cwd, sides)` runs `jvmcontract class-bindings` once, whatever the number of sides,
  classes or selectors. It returns, for each class, the provider, the JAR entry and the SHA-256, or a typed refusal.
- **A JVM's selection is observed**, never computed: `java/LoadedClasses.java` on the JDKs the artifact runs on
  (runtime.py's `_loaded_classes`). `observed(...)` turns what it printed into a binding or a typed refusal.
- **These tools select nothing by rule.** `candidates(jar, name)` is the physical inventory: every class file a JAR
  holds for a name, the base one and each `META-INF/versions/N/` one, whatever its manifest says. A class with one
  class file needs no selection. A class with more is bound only by an observation, and `read(jar, name)` refuses
  to hand out bytes for it otherwise. Nothing here reads a manifest.

A prepared target then records the bytes actually loaded (`classSha256`, with `jarEntry` and `classObservation`
when a JVM chose among several), the launch guard compares the checker's binding with it, and a disagreement is a
refusal that names both digests and where each is from. Planning and reading old receipts use none of this and need
no built checker.
"""

import hashlib
import json
import re
import subprocess
import zipfile
from pathlib import Path

VERSIONED = re.compile(r"META-INF/versions/([1-9][0-9]{0,8})/(.+)")
SCHEMA = "jvmcontract-class-bindings/v1"


class Unbound(ValueError):
    """No one class file stands for a class name here. `refusal` is the typed account: a code, the class, and the
    candidates with their digests and origins."""

    def __init__(self, refusal):
        super().__init__(refusal["reason"])
        self.refusal = refusal


def candidates(jar, name):
    """Every class file `jar` holds for the class `name` (internal form), the base entry first and then the
    versioned ones by release: [{"entry", "sha256", "release"}]. The physical inventory, whatever the manifest says;
    which of them a JVM loads is not decided here. A directory holds at most its one file."""
    jar = Path(jar)
    if jar.is_dir():
        file = jar / (name + ".class")
        return [{"entry": name + ".class", "sha256": hashlib.sha256(file.read_bytes()).hexdigest(), "release": None}] if file.is_file() else []
    found = []
    with zipfile.ZipFile(jar) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            versioned = VERSIONED.fullmatch(info.filename)
            if info.filename == name + ".class" or (versioned and versioned[2] == name + ".class"):
                found.append({"entry": info.filename, "sha256": hashlib.sha256(archive.read(info)).hexdigest(),
                              "release": int(versioned[1]) if versioned else None})
    return sorted(found, key=lambda c: (c["release"] is not None, c["release"] or 0))


def entry_bytes(jar, entry):
    """The bytes of one named entry of a JAR (or file of a directory)."""
    jar = Path(jar)
    if jar.is_dir():
        return (jar / entry).read_bytes()
    with zipfile.ZipFile(jar) as archive:
        return archive.read(entry)


def refusal(code, cls, reason, *, held=(), provider=None, observed=None, selected=None):
    """A typed refusal, in the shape the checker's has (lib/src/classpath.rs, BindingRefusal)."""
    return {"code": code, "class": cls, "reason": reason,
            **({"selected": selected} if selected else {}), **({"observed": observed} if observed else {}),
            "candidates": [{"provider": provider, **c} for c in held]}


def listed(held, provider):
    return ", ".join(f"{provider}!{c['entry']} (sha256 {c['sha256']})" for c in held)


def read(jar, name, entry=None, *, provider=None):
    """The bytes that stand for class `name` in `jar`: the entry a prepared binding names, or the class's one class
    file. None when the JAR holds none. A class with several class files and no bound entry raises Unbound: handing
    out the base entry there is how a reader ends up with other bytes than a JVM loads."""
    if entry is not None:
        return entry_bytes(jar, entry)
    held = candidates(jar, name)
    if not held:
        return None
    if len(held) > 1 or held[0]["release"] is not None:
        where = provider or Path(jar).name
        raise Unbound(refusal("unbound-class", name.replace("/", "."),
                              f"{name.replace('/', '.')} has more than one class file in {where}, and nothing here says which a "
                              f"JVM loads: {listed(held, where)}", held=held, provider=where))
    return entry_bytes(jar, held[0]["entry"])


def observed(cls, provider, held, seen):
    """The binding of a class with several class files, from what JVMs were seen to load: `seen` is
    {JDK feature: (code source relative to the preparation, sha256)}, as `LoadedClasses` printed it on each JDK the
    artifact runs on. Unbound when the JDKs loaded different bytes, loaded the class from another entry of the class
    path, or loaded bytes that no class file of the provider has. Both digests and their origins are in the refusal."""
    digests = {digest for _, digest in seen.values()}
    sources = {source for source, _ in seen.values()}
    by_jdk = "; ".join(f"JDK {feature} loaded sha256 {digest} from {source}" for feature, (source, digest) in sorted(seen.items(), key=lambda kv: int(kv[0])))
    if not seen:
        raise Unbound(refusal("unobserved-class", cls, f"{cls} has more than one class file in {provider} ({listed(held, provider)}), "
                              "and no JVM was run to see which it loads", held=held, provider=provider))
    if len(digests) != 1:
        raise Unbound(refusal("observation-differs-by-jdk", cls,
                              f"{cls} is not one class on the JDKs this artifact runs on: {by_jdk}. {provider} holds "
                              f"{listed(held, provider)}. A claim over these JDKs has no single subject", held=held, provider=provider))
    (digest,) = digests
    if sources != {provider}:
        raise Unbound(refusal("observation-differs", cls, f"{cls} was loaded from {', '.join(sorted(sources))} and not from {provider}: {by_jdk}",
                              held=held, provider=provider, observed=digest))
    match = [c for c in held if c["sha256"] == digest]
    if not match:
        raise Unbound(refusal("observation-unmatched", cls, f"{cls}: {by_jdk}, and no class file of {provider} has those bytes: "
                              f"{listed(held, provider)}", held=held, provider=provider, observed=digest))
    return {"entry": match[0]["entry"], "sha256": digest, "release": match[0]["release"], "jdks": sorted(seen, key=int),
            "candidates": held}


def ask(exe, env, cwd, sides, timeout=120):
    """The checker's bindings for every side of one launch, in one process: `sides` is {name: {"classpath": [...],
    "classes": [{"class", "method", "descriptor"}], "listEntries": [...]}} with paths relative to `cwd` or absolute.
    Returns the answer's `sides` and its bound release. The environment is the verifier's own (JAVA_HOME,
    JVMCONTRACT_JAR_RELEASE, JVMCONTRACT_CLASS_OBSERVATIONS), so the binding is the one the check will read by."""
    proc = subprocess.run([str(exe), "class-bindings"], input=json.dumps({"sides": sides}), capture_output=True, text=True,
                          cwd=cwd, env=env, timeout=timeout)
    if proc.returncode != 0:
        raise ValueError(f"jvmcontract class-bindings failed (exit {proc.returncode}): {(proc.stderr or proc.stdout).strip()[-300:]}")
    try:
        answer = json.loads(proc.stdout)
    except ValueError as error:
        raise ValueError(f"jvmcontract class-bindings printed no JSON: {error}") from None
    if answer.get("schema") != SCHEMA or not isinstance(answer.get("sides"), dict):
        raise ValueError(f"jvmcontract class-bindings answered in another format: {answer.get('schema')!r}")
    return answer["sides"], answer.get("bound_release")


def disagreement(cls, binding, expected_provider, expected_sha256):
    """Why the checker's binding of `cls` is not the prepared one, or None: its refusal, another provider, or other
    bytes. The text names both digests and where each is from."""
    prepared = f"the preparation bound {expected_provider} (sha256 {expected_sha256})"
    if "refused" in binding:
        r = binding["refused"]
        held = "; ".join(f"{c['entry']} sha256 {c['sha256']}" for c in r.get("candidates") or [])
        return f"{cls}: the checker binds no class file ({r['code']}): {r['reason']}" + (f" [{held}]" if held else "") + f"; {prepared}"
    if binding["sha256"] != expected_sha256 or Path(binding["provider"]) != Path(expected_provider):
        return (f"{cls}: the checker would inspect {binding['provider']}!{binding['entry']} (sha256 {binding['sha256']}, selected by "
                f"{binding['selected_by']}), and {prepared}")
    return None
