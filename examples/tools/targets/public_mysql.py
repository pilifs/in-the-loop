"""Run a private InnoDB fixture for a public JDBC comparison."""
from contextlib import contextmanager
import os
import re
import secrets
import subprocess
import time


@contextmanager
def mysql(image):
    if not re.fullmatch(r"mysql@sha256:[0-9a-f]{64}", image):
        raise ValueError("MySQL fixture requires a pinned image")
    password = secrets.token_urlsafe(32)
    env = {**os.environ, "MYSQL_ROOT_PASSWORD": secrets.token_urlsafe(32), "MYSQL_PASSWORD": password}
    container = subprocess.check_output([
        "docker", "run", "--detach", "--rm", "--pull=never", "--memory=768m", "--cpus=1",
        "--tmpfs", "/var/lib/mysql:rw,size=384m", "--publish", "127.0.0.1::3306",
        "--env", "MYSQL_ROOT_PASSWORD", "--env", "MYSQL_DATABASE=comparison", "--env", "MYSQL_USER=caller",
        "--env", "MYSQL_PASSWORD", image, "--innodb-buffer-pool-size=32M", "--innodb-redo-log-capacity=32M",
        "--skip-log-bin", "--performance-schema=OFF"], env=env, text=True, timeout=30).strip()
    try:
        published = subprocess.check_output(["docker", "port", container, "3306/tcp"], text=True, timeout=5).strip()
        host, port = published.rsplit(":", 1)
        if host != "127.0.0.1" or not 0 < int(port) < 65536:
            raise ValueError("unexpected MySQL port binding")
        # The image initializes on a socket, then restarts. A successful TCP query as
        # the restricted fixture user establishes readiness of the final server.
        deadline = time.monotonic() + 40
        while True:
            ready = subprocess.run(["docker", "exec", "--env", "MYSQL_PWD", container, "mysql",
                                    "--protocol=TCP", "-h", "127.0.0.1", "-u", "caller", "-Nse",
                                    "SELECT VERSION()", "comparison"], env={**os.environ, "MYSQL_PWD": password},
                                   capture_output=True, text=True, timeout=5)
            if ready.returncode == 0:
                version = ready.stdout.strip()
                if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
                    raise ValueError("unexpected MySQL server version")
                break
            if time.monotonic() >= deadline:
                raise TimeoutError("disposable MySQL did not accept its TCP fixture connection")
            time.sleep(0.4)
        yield {"PUBLIC_COMPARISON_MYSQL_PORT": port, "PUBLIC_COMPARISON_MYSQL_PASSWORD": password,
               "PUBLIC_COMPARISON_MYSQL_VERSION": version}
    finally:
        subprocess.run(["docker", "stop", "--time", "1", container], check=True, stdout=subprocess.DEVNULL, timeout=15)
