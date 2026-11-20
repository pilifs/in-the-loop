# Rocker and ANTLR

Upgrade Rocker · ANTLR 4.5.3 → 4.7.2  
Caller-visible behavior A template author sees whether a with-declaration is accepted and where the compiler reports an error.  
Result Both compilers reject the trailing comma at line 1, column 18. The message changes from `missing ARGUMENT at '<EOF>'` to `extraneous input '<EOF>' expecting {ARGUMENT_COMMA, ARGUMENT}`. [Both JVM observations](records/observations.json)  
Scope One invalid declaration and one valid declaration, with the actual compiler and generated parser on each side.  
Review action Update an exact-message assertion if the diagnostic wording is contractual. The valid declaration retains the type `String`, name `s` and expression `"test"` on both sides.

The original `WithStatementTest.endsWithComma` passed on the old build and failed its message assertion on the new build. Each fresh Surefire report contains exactly that test. The tracked diff is confined to the POM. The version controls both the ANTLR generator and runtime, and all eight generated Java sources changed. That puts the pair outside the scored cohort's unchanged-generated-source rule. [Old testcase](records/testcase-old.xml) · [New testcase](records/testcase-new.xml) · [Published tags](records/tags.txt)

Holding the old generated compiler fixed and changing the runtime alone produced the new diagnostic. The new generated compiler with the old runtime failed during initialization of the parser automaton. The public verification task `diagnostic` covers the runtime-only substitution using the released Rocker compiler. The independent reproduction compiles 103 compiler classes on each revision from the original Java and grammars. The historical old build matched 101 released class files byte for byte. [Four controlled substitutions](records/controlled-substitution.json) · [Ordered binary and source locks](materials.json)

The offline Maven lifecycle stopped at Maven Enforcer 1.4.1 before a testcase ran. The selected developer test ran separately using the original source and the Surefire JUnit provider. [Effective models and lifecycle attempts](records/effective-and-ci.json)
