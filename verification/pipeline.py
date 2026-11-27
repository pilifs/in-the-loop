#!/usr/bin/env python3
"""The compatibility entry point of the jobs pipeline.

The pipeline is jobs/pipeline.py since 2026-11-27 (jobs/README.md). This path is what every job specification,
hook, note and commit until then names, so it stays: run as a command it is that file's command line, option for
option, and imported as a module (`import pipeline`, with this folder on the path) it *is* that module. Nothing is
implemented here.
"""
import importlib.util
import sys
from pathlib import Path

_path = Path(__file__).resolve().parents[1] / "jobs" / "pipeline.py"
_module = sys.modules.get("jobs_pipeline")
if _module is None:
    _spec = importlib.util.spec_from_file_location("jobs_pipeline", _path)
    _module = importlib.util.module_from_spec(_spec)
    sys.modules["jobs_pipeline"] = _module
    _spec.loader.exec_module(_module)

if __name__ == "__main__":
    sys.exit(_module.main())
sys.modules[__name__] = _module
