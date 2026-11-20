# One label method compiled to two bytecode targets

The same source lowers to StringBuilder or invokedynamic. A control drops the slash only before a null argument.

The independent JVM oracle covered 9 inputs on each revision. legacy mismatches were 0 for label. modern mismatches were 0 for label. changed mismatches were 3 for label.

The table records the direct observations, and each selected adapter field is checked on the full table. The public proof tasks have their own artifact-bound statements and execution histories.

[Frozen inputs and oracle](controls/table.json) · [JVM counts, witnesses and bindings](records/finite-grid.json) · [Required claims](milestones.json) · [Public tasks](target.json)

The same Label.java produced class-file major 52 with javac 21 -source 8 -target 8 and major 65 with default JDK 21 targeting. Disassembly shows StringBuilder.append in the former and invokedynamic in the latter. Both ran on the same JDK 21 JVM. [Compiler flags, bytes and disassembly](records/bytecode.json)
