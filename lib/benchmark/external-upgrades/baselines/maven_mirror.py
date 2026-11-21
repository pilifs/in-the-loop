"""Serve public Maven Central release files to an isolated disclosed CI build over a Unix socket."""

from collections import Counter
from contextlib import contextmanager
import fcntl
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import socket
from socketserver import UnixStreamServer
import tempfile
from threading import Thread
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from xml.etree import ElementTree


CENTRAL = "https://repo.maven.apache.org/maven2/"


# These release repositories are used by the original clients in this comparison.
# Map legacy URLs to the current HTTPS endpoints for the same public repository.
PUBLIC_RELEASES = {
    "https://repository.jboss.org/nexus/content/groups/public-jboss": "https://repository.jboss.org/nexus/repository/public-jboss/",
    "https://repository.jboss.org/nexus/content/groups/public": "https://repository.jboss.org/nexus/repository/public/",
    "https://jcenter.bintray.com": "https://repo1.maven.org/maven2/",
}


def declared_releases(project, pom_paths):
    releases = []
    for name in pom_paths:
        file = (project / name).resolve()
        if not file.is_relative_to(project.resolve()):
            raise ValueError("repository POM is outside the original checkout")
        document = ElementTree.parse(file)
        for entry in document.findall(".//{*}repositories/{*}repository/{*}url"):
            endpoint = PUBLIC_RELEASES.get((entry.text or "").strip().rstrip("/"))
            if endpoint and endpoint not in releases:
                releases.append(endpoint)
    return releases


def open_release(name, releases):
    for base in (CENTRAL, *releases):
        try:
            response = urlopen(base + name.as_posix(), timeout=45)
        except HTTPError as error:
            if error.code != 404 or base == (releases[-1] if releases else CENTRAL):
                raise
            error.close()
            continue
        if response.geturl() != base + name.as_posix():
            response.close()
            raise ValueError("unexpected remote release location")
        return response


def artifact_path(request):
    name = request.removeprefix("/")
    if not re.fullmatch(r"[A-Za-z0-9_./+-]+", name) or any(
        not part or part in {".", ".."} for part in name.split("/")
    ):
        return None
    path = PurePosixPath(name)
    base = re.sub(r"\.(?:sha1|sha256|sha512|md5)$", "", path.name)
    if base == "maven-metadata.xml":
        return path if len(path.parts) >= 2 else None
    if len(path.parts) < 4 or not base.startswith(path.parts[-3] + "-"):
        return None
    return path if base.endswith((".pom", ".jar", ".xml", ".zip", ".war", ".module", ".tar.gz", ".signature")) else None


class QuietHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_HEAD(self):
        self.serve(False)

    def do_GET(self):
        self.serve(True)


class Repository(QuietHandler):
    def serve(self, body):
        name = artifact_path(self.path)
        if name is None:
            self.send_error(404)
            return
        server = self.server
        local = server.repository / name
        try:
            with server.lock_file.open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                if not local.resolve().is_relative_to(server.repository):
                    raise ValueError("path leaves the repository")
                if local.is_file():
                    server.counts["cachedRequests"] += 1
                else:
                    if name in server.missing:
                        self.send_error(404)
                        return
                    local.parent.mkdir(parents=True, exist_ok=True)
                    with open_release(name, server.releases) as upstream:
                        server.counts["from " + upstream.geturl().removesuffix(name.as_posix())] += 1
                        with tempfile.NamedTemporaryFile(dir=local.parent) as pending:
                            while chunk := upstream.read(256 * 1024):
                                server.counts["downloadedBytes"] += len(chunk)
                                if server.counts["downloadedBytes"] > server.byte_limit:
                                    raise ValueError("disclosed case download budget exhausted")
                                pending.write(chunk)
                            pending.flush()
                            os.link(pending.name, local)
                    server.counts["downloadedFiles"] += 1
            self.send_response(200)
            self.send_header("Content-Length", str(local.stat().st_size))
            self.end_headers()
            if body:
                with local.open("rb") as source:
                    shutil.copyfileobj(source, self.wfile)
        except HTTPError as exc:
            server.counts[f"upstreamHttp{exc.code}"] += 1
            if exc.code == 404:
                server.missing.add(name)
            exc.close()
            self.send_error(exc.code)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except (OSError, ValueError, URLError):
            server.counts["resolutionErrors"] += 1
            self.send_error(502)


@contextmanager
def serve(repository, socket_directory, byte_limit, releases=()):
    repository = repository.resolve(strict=True)
    # Unix socket names have a small length limit. The directory FD names the same socket inside the guest mount.
    fd = os.open(socket_directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with UnixStreamServer(f"/proc/self/fd/{fd}/central.sock", Repository) as server:
            server.repository = repository
            server.releases = tuple(releases)
            server.lock_file = repository.parent / "resolution.lock"
            server.byte_limit = byte_limit
            server.counts = Counter()
            server.missing = set()
            worker = Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                yield server.counts
            finally:
                server.shutdown()
                worker.join()
    finally:
        os.close(fd)


class LocalConnection(HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect("/mirror/central.sock")


class LocalMirror(QuietHandler):
    def serve(self, body):
        remote = LocalConnection("localhost")
        try:
            remote.request("GET" if body else "HEAD", self.path)
            answer = remote.getresponse()
            self.send_response(answer.status)
            if length := answer.getheader("Content-Length"):
                self.send_header("Content-Length", length)
            self.end_headers()
            if body:
                shutil.copyfileobj(answer, self.wfile)
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            remote.close()


def guest_server():
    server = HTTPServer(("127.0.0.1", 0), LocalMirror)
    Thread(target=server.serve_forever, daemon=True).start()
    return server.server_port
