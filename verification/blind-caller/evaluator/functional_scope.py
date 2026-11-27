"""Affirmatively admit ordinary, closed product behavior; keep all other draws as scoped abstentions."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

from eligibility_inventory import BATCHES, CACHE, HERE, RESERVED, digest, example, read, upstream_pr, worktree, write
from packet_view import HAZARD, SOURCE_EXTENSIONS, UNSAFE_MATERIAL, clean_description, is_production, is_test, raw_git, related_tests, source_names


DENIED = re.compile(r"\b(?:auth(?:entication|orization|orize|enticated)?|authz|oauth\w*|security|privileg\w*|escalat\w*|permission\w*|credential\w*|password\w*|crypto\w*|cipher\w*|encrypt\w*|decrypt\w*|keystore|certificate\w*|tls|ssl|csrf|xss|xxe|attack\w*|exploit\w*|intrusion|untrusted|malicious|adversarial|bypass\w*|spoof\w*|sandbox\w*|inject\w*|firewall|request.smuggl\w*|overflow|underflow|out.of.bounds|memory.exhaustion|infinite.loop|path.traversal|zip.slip|denial.of.service|red[oe]s|cve\b|ghsa\b)\b", re.I)
BOUNDARY = re.compile(r"\b(?:http\w*|https|servlet\w*|multipart\w*|websocket\w*|socket\w*|network\w*|proxy|proxies|jdbc|r2dbc|sql\w*|database|docker|shell\w*|processbuilder|runtime\.getruntime|classloader|reflection|reflective|deserializ\w*|serializ\w*|marshalling|unmarshall\w*|yaml|xml|html|json|toml|url|uri|file.?system|fileinputstream|fileoutputstream|zipinputstream|zipoutputstream|symlink\w*|symbolic.link|tempfile|regexp|regex|base64|binary.decoder|bytecode|native.code|process.boundary)\b", re.I)
ORDINARY = {
    "numeric value or formatting": r"\b(?:number\w*|numeric\w*|integer\w*|bigdecimal|decimal\w*|numeral\w*|round(?:ing|ed)?|fraction\w*|arithmetic|precision|floating|bigint\w*|digits?|percent(?:age)?)\b",
    "plain text formatting": r"\b(?:strings?|text|format\w*|locale\w*|language|upper\s?case|lower\s?case|whitespace|trim\w*|indent\w*|truncate\w*|truncation|character\w*|surrogate\w*|unicode|emoji|spelling|substrings?|delimit\w*|join\w*)\b",
    "collection order, lookup or equality": r"\b(?:collections?|maps?|lists?|sorted set|hash set|linked set|ordering|sort\w*|comparators?|iterator\w*|queues?|stacks?|arrays?|intersection)\b",
    "calendar or time arithmetic": r"\b(?:dates?|times?|months?|years?|days?|hours?|minutes?|weeks?|calendar\w*|duration|period|chronolog\w*|temporal\w*|instant\w*|epoch|leap|timezone)\b",
    "ordinary public value object": r"\b(?:equals|equality|hashcode|copy|copied|copies|clone\w*|getter|setter|immutable|geometry|polygon\w*|vertices|vertex|coordinates?|histogram\w*)\b",
}
CATEGORIES = {name: re.compile(pattern, re.I) for name, pattern in ORDINARY.items()}
TEST_RISK = re.compile(r"\b(?:Files\.|Paths\.|java\.net\.|java\.security\.|java\.lang\.reflect\.|ProcessBuilder|System\.(?:setSecurityManager|load|loadLibrary|setProperty|getenv)|Runtime\.getRuntime|Class\.forName|Shell|Unsafe|@SpringBootTest|@Sql|MockMvc|Testcontainers|fuzz\w*|stress\w*|bomb|payload|harnessProcess)\b", re.I)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def decision_hash(decision):
    return sha(json.dumps(decision, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode())


def identity(row):
    return sha("\0".join([row["url"], row["pins"]["parent"], row["pins"]["fix"]]).encode())


def words(value):
    value = re.sub(r"https?://[^ \n)>]+", " ", value)
    value = re.sub(r"([a-z\d])([A-Z])", r"\1 \2", value)
    return re.sub(r"[-_/]", " ", value)


def risk(value):
    return bool(HAZARD.search(value) or DENIED.search(words(value)) or BOUNDARY.search(words(value))
                or UNSAFE_MATERIAL.search(value))


def categories(value):
    return {k for k, pattern in CATEGORIES.items() if pattern.search(words(value))}


def safe_test(content, category):
    # All accepted files are immutable original source. No test runner is launched by
    # this evaluator. Only an ordinary fixture in the reviewed domain can enter a view.
    source = content.decode("utf-8", "replace")
    return (len(content) <= 80_000 and not risk(source) and not TEST_RISK.search(source)
            and category in categories(source) and ("@Test" in source or "assert" in source))


def decide(index, row):
    if row["number"] in RESERVED or not row["eligible"]:
        raise ValueError("the functional review can only examine an eligible drawn row")
    metadata = upstream_pr(row)
    title, body = metadata["title"], metadata["body"] or ""
    declaration = title + "\n" + clean_description(body)
    base = {"index": index, "identitySha256": identity(row), "policySha256": digest(Path(__file__)),
            "permitted": False, "classification": "scoped abstention", "reason": "insufficient affirmative ordinary-functionality evidence",
            "sourceDigests": {"publicPR": sha((title + "\n" + body).encode())}, "approvedTests": {"old": [], "new": []}}
    public_labels = " ".join(label["name"] for label in metadata["labels"])
    if risk(title + "\n" + body + "\n" + public_labels):
        base["reason"] = "possible security-sensitive behavior or deployment boundary"
        return base
    spec = read(example(row["number"]) / "comparison.json")
    purposes = [q["history"] for q in spec["questions"]]
    primary = next(q for q in spec["questions"] if q["role"] == "Intent")["history"]
    base["sourceDigests"]["registeredPurposes"] = sha("\n".join(purposes).encode())
    if (any(risk(purpose) for purpose in purposes)
            or any(risk(q["prediction"]) or risk(q["refutation"]) for q in spec["questions"])):
        base["reason"] = "registered purpose requires a sensitive or ambiguous boundary"
        return base
    tree = worktree(CACHE / BATCHES[row["batch"]][3], row["slot"], "fix")
    old, new = row["pins"]["parent"], row["pins"]["fix"]
    paths = [p.decode() for p in raw_git(tree, "diff", "--name-only", "--no-renames", "-z", old, new).split(b"\0") if p]
    production = [p for p in paths if is_production(p)]
    if not production or len(production) > 30:
        return base
    # Review exactly the changed production material, independently of the producer.
    # The public decision records only its digest, the broad functional class and counts.
    patch = raw_git(tree, "diff", "--no-renames", "--no-ext-diff", "--unified=0", old, new, "--", *production)
    base["sourceDigests"]["productionChange"] = sha(patch)
    if len(patch) > 512_000:
        return base
    lines = patch.decode("utf-8", "replace").splitlines()
    # A zero-context diff can repeat an unchanged class declaration in its hunk
    # header. Inspect changed lines and physical production paths, not that label.
    change = "\n".join([*production, *(line[1:] for line in lines if line.startswith(("+", "-"))
                                         and not line.startswith(("+++", "---")))])
    if risk(change):
        base["reason"] = "changed production behavior crosses a sensitive or ambiguous boundary"
        return base
    agreed = categories(declaration) & categories(change) & categories(primary)
    if not agreed:
        return base
    # Ambiguous non-production changes must not supply a different execution target.
    unusual = [p for p in paths if not is_test(p) and not is_production(p)
               and PurePosixPath(p).suffix.lower() in {".c", ".cc", ".cpp", ".sh", ".ps1", ".class", ".so", ".exe"}]
    if unusual:
        return base
    category = next(c for c in CATEGORIES if c in agreed)
    base.update(permitted=True, classification="ordinary product behavior", functionalClass=category,
                reason="public prose, changed production code and registered public purpose independently describe this ordinary operation")
    stems = [PurePosixPath(p).stem for p in production]
    packages = {p.rsplit("/", 1)[0].split(marker)[-1] for p in production
                for marker in ("/java/", "/kotlin/", "/groovy/", "/scala/") if marker in p}
    considered = 0
    for side, revision in (("old", old), ("new", new)):
        for path in source_names(tree, revision):
            if not is_test(path) or PurePosixPath(path).suffix not in SOURCE_EXTENSIONS:
                continue
            if path not in paths and not related_tests(path, stems, packages):
                continue
            considered += 1
            if risk(path):
                continue
            content = raw_git(tree, "show", f"{revision}:{path}")
            if safe_test(content, category):
                base["approvedTests"][side].append(sha(content))
        base["approvedTests"][side] = sorted(set(base["approvedTests"][side]))
    base["originalTestSourcesConsidered"] = considered
    return base


def require_decision(row, decision):
    if (decision.get("identitySha256") != identity(row) or decision.get("classification") != "ordinary product behavior"
            or decision.get("permitted") is not True or decision.get("functionalClass") not in CATEGORIES
            or set(decision.get("sourceDigests", {})) != {"publicPR", "registeredPurposes", "productionChange"}):
        raise ValueError("missing affirmative review of ordinary functionality for this original PR")
    return {"classification": "ordinary product behavior", "decisionSha256": decision_hash(decision)}


def assess(draw, destination):
    rows = {r["number"]: r for r in read(HERE / "eligibility.json")["rows"]}
    decisions = [decide(i, rows[c["number"]]) for i, c in enumerate(draw["cases"], 1)]
    result = {"schema": "blind-caller-functional-scope/v1", "producerRevision": draw["producerRevision"],
              "preregistration": draw["preregistration"], "cases": decisions}
    if destination.exists() and read(destination) != result:
        raise ValueError("a different per-slot functional scope is already recorded")
    write(destination, result)
    print(dict(Counter(r["classification"] for r in decisions)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draw", type=Path, default=HERE / "draw.json")
    parser.add_argument("--output", type=Path, default=HERE / "functional-scope.json")
    args = parser.parse_args()
    assess(read(args.draw), args.output)
