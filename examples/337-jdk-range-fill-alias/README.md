# A JDK range fill observed through two array roots

The direct JVM grid includes empty ranges, whole arrays, shared roots and distinct roots of unequal length. The changed control writes one extra cell when one exists.

[Bounded and length-independent tasks](target.json) · [Heap oracle](controls/oracle.py)
