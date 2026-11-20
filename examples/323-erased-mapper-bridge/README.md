# An erased Mapper bridge rejects the wrong runtime type

The compiler-generated bridge casts its input before the typed method increments the entry counter.

The independent JVM oracle covered 5 inputs on each revision. original mismatches were 0 for value, 0 for exception, 0 for entries, 0 for typedAgreement. changed mismatches were 1 for value, 0 for exception, 0 for entries, 0 for typedAgreement.

The table records the direct observations, and each selected adapter field is checked on the full table. The public proof tasks have their own artifact-bound statements and execution histories.

[Frozen inputs and oracle](controls/table.json) · [JVM counts, witnesses and bindings](records/finite-grid.json) · [Required claims](milestones.json) · [Public tasks](target.json)

The emitted erased method has the bridge and synthetic flags. Its checkcast precedes its call to the typed Integer method. The wrong-type input never entered that body. The four admissible inputs also ran through the typed descriptor. See [both class files and their disassembly](records/bytecode.json).
