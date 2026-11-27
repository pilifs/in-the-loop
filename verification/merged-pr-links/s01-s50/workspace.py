"""Temporary build space for the Spring Boot campaign, including standalone runner jobs."""
import os
from pathlib import Path
import tempfile


def scratch_root():
    cache = (Path.home()/".cache/in-the-loop").resolve()
    requested = Path(os.environ.get("TMPDIR") or cache/"spring-boot-pr-links-s01-s50/tmp").resolve()
    directory = requested if requested.is_relative_to(cache) else cache/"spring-boot-pr-links-s01-s50/tmp"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def scratch(prefix):
    return tempfile.TemporaryDirectory(prefix=prefix,dir=scratch_root())
