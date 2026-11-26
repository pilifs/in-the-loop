"""Resolve local manifest URLs on a captured deployment, retaining URL order, provenance and absences."""
import os
from pathlib import Path
import re
import hashlib
import shutil
import tempfile
import zipfile


def manifest(file, feature):
    if file.is_dir():
        return [], []
    with zipfile.ZipFile(file) as jar:
        names = jar.namelist()
        issues = []
        if feature < 21 and any(n.upper() == "META-INF/INDEX.LIST" for n in names):
            issues.append("JAR index can name additional providers")
        matches = [n for n in names if n.upper() == "META-INF/MANIFEST.MF"]
        if len(matches) > 1:
            return [], [*issues, "ambiguous manifest member"]
        if not matches:
            return [], issues
        data = jar.read(matches[0])
    main = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n").split(b"\n\n", 1)[0].replace(b"\n ", b"")
    values = [line.partition(b":")[2].strip(b" \t\f") for line in main.split(b"\n") if line.lower().startswith(b"class-path:")]
    if len(values) > 1 or any(not re.fullmatch(rb"[\x20-\x7e\t\f]*", value) for value in values):
        return [], [*issues, "ambiguous or unsupported manifest Class-Path"]
    return (values[0].decode().split() if values else []), issues


def local(token, parent):
    if not re.fullmatch(r"/?(?:[A-Za-z0-9_+.-]+/)*[A-Za-z0-9_+.-]+\.(?:jar|zip)", token, re.I):
        return None
    return Path(os.path.normpath(parent / token))


def resolve(document, base, feature, file_digest, *, layout_cache=None):
    # A signed or acquired root supplies paths. A basename or a matching digest alone cannot locate a URL.
    captured = (base / document["deploymentRoot"]).resolve() if document.get("deploymentRoot") else None
    roots, pins, sha_by_real = [], {}, {}
    issues, declarations, edges, absent = [], [], [], set()
    def physical(url):
        return captured / str(url).lstrip("/") if captured and url in mapped_urls else url

    mapped_urls = set()
    def load(item, declared):
        file = Path(os.path.abspath(base / item["file"]))
        actual = file_digest(file)
        if actual != item["sha256"]:
            raise ValueError(f"classpath differs at {file.name}")
        url = file
        if "deploymentPath" in item:
            url = Path(item["deploymentPath"])
            if not captured or not url.is_absolute() or ".." in url.parts:
                raise ValueError("a deploymentPath requires an absolute path inside a captured deploymentRoot")
            mapped_urls.add(url)
            placed = physical(url)
            if not placed.resolve().is_relative_to(captured) or file_digest(placed) != actual:
                raise ValueError(f"captured deployment bytes differ at {url}")
            file = placed
        if url in pins and pins[url] != (file, actual):
            raise ValueError(f"two pins for one deployment URL: {url}")
        pins[url] = file, actual
        sha_by_real[file.resolve()] = actual
        if declared:
            roots.append(url)
    for row in document["classpath"]:
        load(row, True)
    for row in document.get("manifestProviders", []):
        load(row, False)
    if not roots:
        raise ValueError("empty classpath")
    if document.get("ordered", True) is not True:
        issues.append({"reason": "provider order is unknown; supply the original ordered launch roots"})
    loader = document.get("loader", {"scope": "application", "delegation": "parent-first"})
    if not isinstance(loader, dict) or loader.get("delegation") != "parent-first" or loader.get("scope") != "application":
        issues.append({"reason": "loader search or delegation is not established for this launch", "loader": loader})
    order, positions, via = [], {}, []
    manifests = {}
    def tokens(file, sha):
        if sha not in manifests:
            manifests[sha] = manifest(file, feature)
        return manifests[sha]
    def visit(url, source):
        if url in positions:
            return
        file, sha = pins[url]
        i = positions[url] = len(order)
        order.append(url)
        via.append(source)
        items, faults = tokens(file, sha)
        issues.extend({"provider": i, "reason": reason} for reason in faults)
        if items:
            declarations.append({"provider": i, "entries": items})
        for token in items:
            edge = {"provider": i, "entry": token}
            edges.append(edge)
            target = local(token, url.parent)
            if target is None or document.get("layoutKnown", True) is not True:
                edge.update(state="unresolved", reason="unclassified manifest URL" if target is None else "original deployment location required")
                issues.append(dict(edge))
                continue
            if captured and url in mapped_urls:
                mapped_urls.add(target)
            path = physical(target)
            edge["url"] = str(target)
            if captured and target in mapped_urls and not path.resolve().is_relative_to(captured):
                edge.update(state="unresolved", reason="manifest edge resolves outside the captured layout")
            else:
                try:
                    path.stat()
                except (FileNotFoundError, NotADirectoryError):
                    absent.add(str(path))
                    edge.update(state="absent")
                except OSError:
                    edge.update(state="unresolved", reason="cannot establish file absence")
                else:
                    if target not in pins and path.resolve() in sha_by_real:
                        pins[target] = path, sha_by_real[path.resolve()]
                    if target not in pins:
                        edge.update(state="unresolved", reason="present implicit provider")
                    else:
                        edge.update(state="bound", revisited=target in positions)
                        visit(target, {"provider": i, "entry": token})
                        edge["classpathIndex"] = positions[target]
            if edge["state"] == "unresolved":
                issues.append(dict(edge))
    for n, url in enumerate(roots):
        visit(url, {"root": n})

    # A flattened path is usable by the ordinary launcher only if the VM's own manifest insertions produce
    # the same order. In particular, a host absolute URL must not sneak into a relocated captured layout.
    files = [pins[url][0] for url in order]
    if captured and not issues:
        observed_order = []
        by_file = {p: pins[u][1] for p, u in zip(files, order)}
        seen = set()
        def host(file):
            if file in seen:
                return
            seen.add(file)
            observed_order.append(file)
            for item in tokens(file, by_file[file])[0]:
                target = local(item, file.parent)
                if target in by_file:
                    host(target)
                elif target is not None:
                    if target.exists():
                        issues.append({"reason": "host manifest resolves outside the captured deployment", "file": str(target)})
                    else:
                        absent.add(str(target))
        for file in files:
            host(file)
        if observed_order != files or any(f != f.resolve() for f in files):
            if layout_cache is None:
                issues.append({"reason": "original URL layout requires a verified execution mapping"})
            elif not issues:
                # One physical directory per original URL preserves distinct code sources even for aliases.
                # Flatten only after verifying that the original manifests cannot insert another live host URL.
                mapped = []
                for url, file in zip(order, files):
                    sha = pins[url][1]
                    location = hashlib.sha256(str(url).encode()).hexdigest()
                    target = layout_cache.absolute() / location / sha / file.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if not target.exists():
                        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
                            temporary = Path(stream.name)
                            try:
                                with file.open("rb") as original:
                                    shutil.copyfileobj(original, stream)
                                stream.flush()
                                if file_digest(temporary) != sha:
                                    raise ValueError(f"deployment artifact changed while mapping {url}")
                                os.replace(temporary, target)
                            finally:
                                temporary.unlink(missing_ok=True)
                    if file_digest(target) != sha:
                        raise ValueError(f"mapped deployment artifact differs at {target}")
                    mapped.append(target)
                locations = set(mapped)
                for file, url in zip(mapped, order):
                    for token in tokens(file, pins[url][1])[0]:
                        actual = local(token, file.parent)
                        if actual not in locations:
                            if actual.exists():
                                issues.append({"reason": "mapped launch can insert an undeclared provider", "file": str(actual)})
                            else:
                                absent.add(str(actual))
                files = mapped
    providers = [{"name": file.name, "file": str(file), "originalFile": str(pins[url][0]), "deploymentPath": str(url), "sha256": pins[url][1],
                  "introducedBy": source} for url, file, source in zip(order, files, via)]
    info = {"declarations": declarations, "bound": [e for e in edges if e["state"] == "bound"],
            "absent": sorted(absent), "unresolved": issues, "edges": edges}
    return files, providers, {"orderedRoots": [str(u) for u in roots], "loader": loader,
                              "clientIndex": positions[roots[next((i for i,r in enumerate(document["classpath"]) if r.get("role") == "client"), 0)]],
                              "manifestClassPath": info}
