# Lazy Optional fallback has observable calls

Calling the supplier eagerly preserves all returned integers and invokes the supplier on present values.

The independent JVM oracle covered 4 inputs on each revision. lazy mismatches were 0 for value, 0 for callbacks. branch mismatches were 0 for value, 0 for callbacks. eager mismatches were 0 for value, 3 for callbacks.

The table records the direct observations, and each selected adapter field is checked on the full table. The public proof tasks have their own artifact-bound statements and execution histories.

[Frozen inputs and oracle](controls/table.json) · [JVM counts, witnesses and bindings](records/finite-grid.json) · [Required claims](milestones.json) · [Public tasks](target.json)

The concrete Fallback class implements Supplier<Integer>. The lazy and explicit-branch subjects each call it once for empty. The eager subject makes one extra call for each of the three present inputs. The prepared class disassembly identifies the Optional entry and supplier. [Bytecode evidence](records/bytecode.json)
