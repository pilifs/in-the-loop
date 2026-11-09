"""The external-target seam of llm-dlc/loops/example-targets.md: a real-world example with a target.json sidecar.

- sidecar.py: loads and checks a sidecar (examples/schema/target.schema.json). Owned by the workflow stream with the
  schema, after Phase 0.
- interfaces.py: the three shared interfaces, frozen in Phase 0 (TaskPlan, PreparedTarget, attempt ingestion), with
  the raw ExecutionRecord between them and the named Unsupported result. Coordinator-owned.
- workflow.py: task planning, attempt ingestion and the index projection (the workflow stream).
- runtime.py: preparation, separate-JVM controls and the verifier on prepared artifacts (the runtime stream).

Tests: test_sidecar.py and test_interfaces.py (coordinator), test_workflow.py and test_runtime.py (their streams).
Nothing here touches the network, and planning never does.
"""
