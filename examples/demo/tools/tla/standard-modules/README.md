# TLA+ standard modules

The four standard modules the models extend: `Naturals`, `Sequences` and `FiniteSets` ([`BoxOffice.tla`](../../../apps/boxoffice/spec/BoxOffice.tla) and the others), and `TLC`, for the `Permutations` of the symmetry set in [`RaftElection.tla`](../../../apps/quorum/spec/RaftElection.tla).
They are not part of this project. They are unmodified copies from `tla2sany/StandardModules/` in `tla2tools.jar`, TLC 2.19 (rev 5a47802), under the MIT licence in [`License.txt`](License.txt).

TLC normally unpacks these from its jar into a temporary directory and deletes them on exit, so its output names files such as `/tmp/Naturals.tla` that do not exist afterwards.
[`build.py`](../../build.py) passes this directory as `-DTLA-Library`, so TLC parses these copies instead, and the paths in the `verifier-output.txt` of the D1 examples point at files you can open.

TLC implements many of these operators natively, in Java, and selects those implementations by module name, so the definitions here say what the operators mean but are not always the code TLC runs.
