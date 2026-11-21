"""The external-target seam of llm-dlc/loops/example-targets.md: a real-world example with a target.json sidecar.

- sidecar.py: loads and checks a sidecar (examples/schema/target.schema.json). Owned by the workflow stream with the
  schema, after Phase 0.
- interfaces.py: the three shared interfaces, frozen in Phase 0 (TaskPlan, PreparedTarget, attempt ingestion), with
  the raw ExecutionRecord between them and the named Unsupported result. Coordinator-owned.
- workflow.py: task planning, attempt ingestion, handoffs and the index projection (the workflow stream).
- runtime.py: preparation, separate-JVM controls and the verifier on prepared artifacts (the runtime stream).
- route.py: what build.py (--plan ID --task T, ID --task T) and pipeline.py (submit --example ID --task T) call; it
  chains the interfaces and stops at the first Unsupported. Coordinator-owned.

- fixtures/: Phase 0's local, deterministic fixtures (fixtures/README.md): a two-revision adapter fixture with a
  mutant, recorded concrete controls, a recorded capability refusal, and constructed bad runs and receipts.

Tests: test_fixtures.py, test_sidecar.py, test_interfaces.py and test_route.py (coordinator), test_workflow.py and test_runtime.py (their streams).
Nothing here touches the network, and planning never does.
"""

import sys
from pathlib import Path

# What the library shares with its Python consumers (lib/python: the proof output reader, the disassembly reader,
# array induction) is imported by name from every module of this package.
LIB_PYTHON = str(Path(__file__).resolve().parents[3] / "lib/python")
if LIB_PYTHON not in sys.path:
    sys.path.insert(0, LIB_PYTHON)
