# Array copy leaves a prefix before an incompatible element

The JVM copied 40 typed Object[] sources into fresh String[] destinations. Both implementations threw ArrayStoreException on 25 inputs. Twelve destinations differed. For the source containing A and boxed 1, the reference left [A, x] and the precheck left [x, x].

The complete table freezes the runtime component types, nulls, source values, exception class and final destination. The selected adapter fields are checked independently against direct calls.

[Declared claims and revisions](target.json) · [Required claim bindings](milestones.json) · [Independent check](controls/table.json) · [JVM evidence](receipts/replay)
