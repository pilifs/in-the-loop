# Frozen requests and controls

Reference `d717edd200ec3a781b7c7e179200e4a7dc549740`. Execution starts on
`4e72ad45bfca14260e5086aa08e5a7ff1970622c`. Of the linked local inputs only
`lib/tests/integration.rs` changed (80 additions and three deletions). Its scalar expressions
remain available. The release JAR and both historical induction records are unchanged.

An external request has six whitespace-delimited lines, in order: version, theorem, environment,
class (internal name and SHA-256), entry (name and descriptor), and companion (name and descriptor
or a dash). An optional final support line binds a superclass by name and digest. An evidence file
independently repeats the request digest and supplies hints. Acceptance returns the external request.
The request owner selects the bytes and resolution. A control uses a fresh request for its own class.

* `scalar-equality-v1` asks whether the two public static methods on the same int return the same
  Java int normally for every 32-bit input, with no heap change. Java arithmetic wraps modulo 2^32.
  The requests select multiply/add and multiply/shifted in the actual compiled Scalar class.
* `least-index-frame-total-v1` asks for normal termination of the public call on **all**
  non-null, already allocated arrays of length 0 through 2^31−1, all signed cells and targets at
  their descriptor's width. The heap must equal the entry heap. The return is the least matching
  index if one exists, and −1 if and only if none exists. Both indices and the result are Java ints.
  The named companion is a private static method of the same class.
* `initialized-verified-jvm-v1` assumes verified, well-formed classes, successful initialization
  of the selected class and its ancestors before entry, pinned defining classes and ordinary JVM
  linkage, single-threaded execution, and sufficient VM resources. VM resource failures and
  asynchronous termination are excluded. No assumption constrains cell values, match position,
  or array length beyond JVM representability. Initialization is a precondition.

Freeze these observations before implementing either route:

| Control | Expected observation |
|---|---|
| Fresh last match | [7,7], 7 returns 1 and preserves the heap |
| Wrong wrapper start / wrong helper miss | [7], 7 returns −1 / [], 7 returns 0 |
| Damaged heap after correct result | [7], 7 returns 0 and changes cell zero |
| No progress | A nonmatching singleton stays in the loop |
| Truncated long comparison | [0,4294967296], 4294967296 returns 0 |
| Unfamiliar positive, held until 336 freezes | An extra local or equivalent layout preserves all outputs |
| Evidence substitution | Wrong bytes, descriptor, theorem, certificate or missing exit/frame cannot certify the request |
| Producer fault at the consumer boundary | A producer asserting a discharged frame for a heap-writing method cannot supply the consumer's frame rule |

Record dispositions, witnesses, edge keys, dependencies, effort by stage and actual source changes.
Measure construction separately from three fresh consumer processes using child peak RSS, wall
time, and evidence bytes. Keep the first frozen 346 attempt, even if transfer succeeds later.
Only 336 and 346 are required to make the investment decision. The optional 337 extension begins
after their controls. All consumers are opt-in.
