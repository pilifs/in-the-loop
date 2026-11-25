"""Supply a short-lived, loopback-only PostgreSQL instance to a public JDBC caller."""
from contextlib import contextmanager
import os
import secrets
import subprocess
import time


@contextmanager
def postgres(image):
    if not image.startswith("postgres@sha256:") or len(image.split(":")[-1]) != 64:
        raise ValueError("PostgreSQL fixture requires a pinned image")
    password = secrets.token_urlsafe(32)
    env = {**os.environ, "POSTGRES_PASSWORD": password}
    container = subprocess.check_output([
        "docker", "run", "--detach", "--rm", "--pull=never", "--memory=384m", "--cpus=1",
        "--tmpfs", "/var/lib/postgresql/data:rw,size=160m", "--publish", "127.0.0.1::5432",
        "--env", "POSTGRES_PASSWORD", "--env", "PGDATA=/var/lib/postgresql/data/cluster", image], env=env, text=True, timeout=30).strip()
    try:
        published = subprocess.check_output(["docker", "port", container, "5432/tcp"], text=True, timeout=5).strip()
        host, port = published.rsplit(":", 1)
        if host != "127.0.0.1" or not 0 < int(port) < 65536:
            raise ValueError("unexpected PostgreSQL port binding")
        deadline = time.monotonic() + 25
        while subprocess.run(["docker", "exec", container, "pg_isready", "-q", "-h", "127.0.0.1"],
                             timeout=5).returncode:
            if time.monotonic() > deadline:
                raise TimeoutError("disposable PostgreSQL did not start")
            time.sleep(0.25)
        version = subprocess.check_output(["docker", "exec", container, "psql", "-U", "postgres", "-Atc",
                                           "SHOW server_version_num"], text=True, timeout=5).strip()
        if not version.isdecimal():
            raise ValueError("PostgreSQL did not report its server version")
        yield {"PUBLIC_COMPARISON_PG_PORT": port, "PUBLIC_COMPARISON_PG_PASSWORD": password,
               "PUBLIC_COMPARISON_PG_VERSION": version}
    finally:
        subprocess.run(["docker", "stop", "--time", "1", container], check=True, stdout=subprocess.DEVNULL, timeout=12)
