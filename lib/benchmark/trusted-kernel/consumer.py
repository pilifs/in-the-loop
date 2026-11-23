"""Recheck the supplied external request and certificate against the supplied class in a fresh process."""

import argparse
from pathlib import Path
import tempfile

from replay import build_kernel, fresh_rust, lean_check


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("route", choices=["rust", "lean"])
    ap.add_argument("request", type=Path)
    ap.add_argument("certificate", type=Path)
    ap.add_argument("artifact", type=Path)
    ap.add_argument("support", nargs="*", type=Path)
    args = ap.parse_args()
    if args.route == "lean":
        if args.support:
            ap.error("the scalar theorem has no supporting application class")
        result = lean_check(args.request, args.certificate, args.artifact)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            binary, _ = build_kernel(Path(tmp))
            result = fresh_rust(binary, args.request, args.certificate, args.artifact, args.support)
    print(result["stdout"])
    return result["exit"]


if __name__ == "__main__":
    raise SystemExit(main())
