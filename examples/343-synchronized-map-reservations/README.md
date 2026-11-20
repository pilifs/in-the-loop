# Two reservations on a synchronized map

Each worker calls once on the same JDK wrapper. The subjects differ in whether the application holds that wrapper's monitor across both calls. The JVM control gates the split client after containsKey and before put.

[Verification tasks](target.json) · [Sequential history oracle](controls/oracle.py)
