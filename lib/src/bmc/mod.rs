//! Bounded model checking of a harness in the tool itself, without JBMC: the harness bytecode is executed
//! symbolically over bit-vectors ([`bits`]), one path at a time, and a bundled SAT solver (CaDiCaL) decides at
//! every branch which sides are feasible and, when a path reaches the harness's `AssertionError`, what input takes
//! it there. Each path carries a model of its condition (the solver's answer when it was split off), so the side
//! of a branch that model takes is known feasible and the solver is asked once per branch, about the other side,
//! and not at all about a condition the path has taken before. That one question is given as much work as the
//! solver's calls so far did together, in conflicts and not seconds so that it is the same on every machine, and a
//! side undecided by then waits until the decided paths are done, so a violation is not held up by an infeasible side
//! that is hard to refute. A division or multiplication is left to the solver
//! under what holds of every one and built as a circuit only where a model got it wrong
//! ([`bits::Blaster::sdivrem_lazy`], [`bits::Blaster::mul_lazy`]); a quotient times its divisor is the dividend
//! less the remainder, with no product.
//! Loops are unwound up to a bound, as JBMC's are, and a path that needs more is no verdict. Once more paths have
//! been explored than a small search has ([`Options::merge_after`]), paths are merged where they meet: one that
//! reaches an instruction with more than one way in (after an `if`, a loop header, a handler) waits there, and the
//! paths waiting at the earliest such point are made one path when nothing else can run, every value they differ
//! in a choice by the condition of each and its models all of theirs ([`Engine::merge`]), so that independent
//! branches add paths rather than multiply them and a branch each of whose sides some model takes costs no solver
//! call. A reference they differ in becomes a symbolic one, one of their objects or null under the condition of
//! each ([`Choice`]); a reference every path agrees on stays a known object, the fast path. A small search stays unmerged, each solver call being about one concrete path, which is cheaper.
//! Two paths whose heaps are not of one shape (one made objects the other did not) stay two while the paths are few,
//! and once they are many ([`Options::merge_heaps_after`]) are merged into one heap of both's objects ([`align`]). A path waits where a loop is left as at any join, and the group resumed is the
//! earliest in the program, a path that has gone round a loop less before one that has gone round it more
//! ([`JoinKey`]).
//!
//! The fragment this engine handles is the one the proofs are mostly about: static methods over `int`, `long`,
//! `short`, `byte`, `char` and `boolean`, straight-line and branching arithmetic, calls into the application's own
//! static methods (inlined), the `Math`/`StrictMath` exact and floor operations with their overflow exceptions,
//! `Integer`/`Long` comparisons, exceptions thrown and caught by class, and bounded Strings: a String is an object
//! with its content, UTF-16 code units of a symbolic length (any units at all, a surrogate alone or a NUL), whose
//! `length`, `isEmpty`, `charAt`, `equals` and `startsWith` are modelled; a String parameter has every content up to
//! [`Parameters::max_string_length`], and its witness is its code units. A String whose content the engine doesn't
//! compute (a number's digits) is an opaque object, which a message built for an exception may still be. An array of those primitives is an object with a symbolic length and a cell
//! per index it may have ([`Array`]): an array parameter has every length up to [`Options::max_array_length`],
//! as JBMC's nondeterministic arrays do (and is never null nor another parameter's array, unless
//! [`Options::parameters`] lets it be, a symbolic reference then), a read is a choice among the cells by the index and a write a
//! conditional update of each, and an index out of bounds or a negative size is a branch to the exception, as a
//! division by zero is. An array of references holds an object or null per cell, and an index into one that is not
//! a constant splits the path per cell. An application class's static fields are path state, and its initializer
//! runs where the JVM runs it (JVMS §5.5); an enum's is one, its constants made through `java.lang.Enum`'s model
//! and its `$VALUES` an array of references. Floating point, the JDK's static state and the rest of the
//! JDK are refused with a reason, so that a caller can fall back to JBMC. A verdict it gives is on the same statement JBMC would
//! check, the generated harness class, so a counterexample is replayed and shrunk like JBMC's.
//!
//! Every instruction, and every call it can make, is implemented as the JVM does it, modelled (by a model whose
//! contract is written down), a named gap ([`gaps`]), or refused:
//!
//! | Instructions | Treatment |
//! |---|---|
//! | `nop`, `aconst_null`, `iconst`, `lconst`, `bipush`/`sipush`, `ldc` of an int or a long, `iload`/`lload`/`aload`, `istore`/`lstore`/`astore`, `pop`, `pop2`, `dup`, `dup_x1`, `dup_x2`, `dup2`, `dup2_x1`, `dup2_x2`, `swap`, `iinc` | implemented |
//! | `iadd` … `lxor` (arithmetic, shifts, bitwise), `i2l`, `l2i`, `i2b`, `i2c`, `i2s`, `lcmp` | implemented bit for bit; `idiv`, `irem`, `ldiv`, `lrem` throw `ArithmeticException` on zero |
//! | `ifeq` …, `if_icmpeq` …, `if_acmpeq`/`if_acmpne`, `ifnull`, `ifnonnull`, `goto`, `tableswitch`, `lookupswitch`, `ireturn` … `return` | implemented; a loop's back edge counts against the unwinding bound, per entry of the loop (an outer loop's back edge or a new call starts an inner loop's count again), and a path that needs another iteration goes on from an invariant of the loop where the engine finds one ([`loops`], [`Options::invariants`]); `if_acmp`, `ifnull` and `ifnonnull` on a symbolic reference are formulas over its guards |
//! | `newarray`, `arraylength`, `iaload` … `saload`, `iastore` … `sastore` on arrays of primitives | implemented, up to [`Options::max_array_length`] cells; `ArrayIndexOutOfBoundsException`, `NegativeArraySizeException`, and `NullPointerException` on null |
//! | `anewarray`, `aaload`/`aastore` on arrays of references, and an array's `clone()` | implemented as for primitives, a cell holding an object or null; an `aaload` at an index that is not a constant gives a symbolic reference, the reference of each cell under `index == i` ([`Choice`]), and splits no path; an `aastore` at such an index splits the path per cell ([`Engine::concrete_index`]); a cell may hold a symbolic reference, which an `aastore` stores as it is when every object it may be is of the element type (as `List.of`'s varargs array holds a harness's picks), and splits per object otherwise; `clone()` a new array of the same class and elements; an `aastore` of an object not of the element type (`ArrayStoreException`) is refused |
//! | `new`, `getfield`, `putfield`, `invokestatic`, `invokespecial`, `invokevirtual`, `invokeinterface` of the application's own methods | implemented: objects with fields, calls inlined, a virtual call dispatched on its receiver's class, `NullPointerException` on a null receiver; a field resolved as the JVM resolves it (JVMS §5.4.3.2), so a field a subclass declares again is a second one. Through a symbolic reference, `getfield` chooses among its objects' fields by the guards and `putfield` writes each under its guard, `NullPointerException` where it is null; a call on one, or any other instruction that needs its object (`checkcast`, `athrow`, a monitor, an array instruction, a JDK call's argument), splits the path per object first ([`Engine::concrete_ref`]) |
//! | `athrow`, exception handlers, `checkcast`, `instanceof` | implemented, a handler matched by subclass; `instanceof` on a symbolic reference a formula over its guards |
//! | `monitorenter`, `monitorexit` | implemented: `NullPointerException` on null, and otherwise nothing, which is all a monitor does in a run of one thread |
//! | `getstatic`, `putstatic` of an application class's field; `getstatic` of a JDK compile-time constant (`Integer`/`Long` `MAX_VALUE`/`MIN_VALUE`, or a field with a `ConstantValue`) | implemented: a field is resolved as the JVM resolves it, and holds what the path wrote, else its `ConstantValue`, else zero or null |
//! | class initialization (JVMS §5.5), at the first `new`, `getstatic`, `putstatic` or `invokestatic` of an application class | implemented ([`Engine::initialise`]): the class's superclass, then the superinterfaces that declare a default method ([`gaps::initialization_supers`]), then its `<clinit>`, run as bytecode; a use from inside its own initialization goes on; an exception that leaves a `<clinit>` is thrown as an `ExceptionInInitializerError` (an `Error` as it is), and a later use of the class, or of one that waited on it, throws `NoClassDefFoundError`. A JDK class is taken to be initialized already |
//! | a `<clinit>` outside the fragment ([`gaps::runs_initializer`]: one that reaches what the engine refuses, or reads or writes a static of a class whose `<clinit>` is outside; a gap inside one it runs is met there) | gap: `class-initializer`, met where the JVM would run it; under assume, or closed by a contract that it throws nothing, taken to have run, its static fields then known only as constants |
//! | the `<clinit>` of a class named by `--observed-initializer` ([`Options::observed`], [`crate::observed`]) | not run and no gap: the path takes the static state the initializer left on a JVM, as far as the observation holds it (a field it holds no value of is refused where it is read), and the run states what that rests on ([`Outcome::assumed`]) |
//! | `invokestatic` of `Math`/`StrictMath`/`Integer`/`Long`/`Boolean` operations ([`models_jdk_static`]) | modelled in [`Engine::call_jdk_static`], each as its Javadoc specifies, exceptions included |
//! | `invokestatic` of `Objects.requireNonNull(Object)` and `(Object, String)`, and of `Pattern.compile(String)` ([`models_jdk_reference_static`]) | modelled in [`Engine::call_jdk_static`]: `requireNonNull` returns its argument or throws `NullPointerException`; `compile` throws it for null, returns a new `Pattern` with no content (its methods the JDK calls they name) for a constant regular expression of the plain form ([`crate::jdk_facts::plain_regex`]), which the JDK compiles whatever it is, and is the gap `jdk-static-method` for any other |
//! | `invokestatic` of any other JDK method over integers, booleans, arrays and objects ([`gaps::jdk_static_call`]) | gap: `jdk-static-method`, with no assume form |
//! | `invokestatic` of a class the tool's models (`lib/models`) provide | modelled: the model's bytecode runs, as in the interpreter |
//! | `invokespecial`/`invokevirtual` of `java.lang.Enum`'s constructor, `name()`, `ordinal()`, `toString()` and `equals` ([`ClassPath::checker_runs`]) | modelled: the model's bytecode (`lib/models/java/lang/Enum.java`, which JBMC runs too) sets and reads the enum's `name` and `ordinal` fields; the interpreter's natives do the same. `Enum`'s other methods (`compareTo`, `hashCode`, `valueOf` …) stay JDK gaps |
//! | `invokestatic` of `List.of` (its fixed forms, up to ten elements) and `List.copyOf`, and `invokevirtual`/`invokeinterface` of the immutable lists' methods an evidence record of `values::OPERATIONS` samples (`size`, `isEmpty`, `get`, `iterator`, the iterator's `hasNext` and `next`, and the changes `add`, `set`, `remove(int)`, `clear` and the iterator's `remove`) ([`ClassPath::checker_runs`]); a call from outside the models of any other method they implement (`contains`, `indexOf`, `equals`, `hashCode`, `toArray`, `addAll`, `sort` …, and `List.of(E...)`) is the JDK call it names, a gap or a refusal as any JDK call is ([`gaps::outside_the_list_records`]) | modelled: the models' bytecode (`lib/models/java/util/`, which JBMC runs too: `List12` for one or two elements, `ListN` over an array of its own otherwise, one empty list), `ImmutableCollections`' initializer run as an application class's ([`ClassPath::checker_class`]); order, duplicates and aliases between elements are the elements' references, null rejected, every change `UnsupportedOperationException`, `get` out of range an `IndexOutOfBoundsException` from a `List12` and an `ArrayIndexOutOfBoundsException` from a `ListN`. The interpreter's natives do the same. `copyOf` of another implementation meets its methods as JDK calls |
//! | `new HashMap()` and `new HashMap(int)`, and `invokevirtual`/`invokeinterface` of `put`, `get`, `containsKey`, `size` and `isEmpty` on the map ([`ClassPath::checker_runs`]) | modelled: the model's bytecode (`lib/models/java/util/HashMap.java`, which JBMC runs too), a map's entries one chain of objects, a key found by its `hashCode` and `equals` as the JDK finds one; each call has an evidence record of `values::OPERATIONS`. The model has no other method: any other (`remove`, `keySet`, `Map`'s default methods) is the JDK call it names |
//! | `invokespecial` of `Object.<init>()`, `Record.<init>()`, and a JDK exception's `()`, `(String)` or `(String, Throwable)` constructor ([`gaps::exact_jdk_call`]) | modelled exactly: they change nothing a proof observes |
//! | `invokespecial` of any other JDK constructor, `invokevirtual`/`invokeinterface` of a JDK method returning `void` or an object | gap: `jdk-constructor`, `jdk-void-method`, `jdk-reference-method` |
//! | `invokevirtual`/`invokeinterface` of `String.length()`, `isEmpty()`, `charAt(int)`, `equals(Object)`, `startsWith(String)` and `hashCode()` on a String whose content the engine holds, whatever class the call names (`Object.equals`, `CharSequence.length`: the receiver's class picks the method) ([`Engine::string_method`]) | modelled, as their Javadoc specifies: `StringIndexOutOfBoundsException` from `charAt` out of range, `NullPointerException` from `startsWith(null)`, `equals` true of the same object, false of null and of another class, else the lengths and every code unit compared, `hashCode` the sum `s[0]*31^(n-1) + … + s[n-1]` in `int` arithmetic; on an opaque String they are the JDK calls below; on one past the content cap, a named limit with no verdict |
//! | `invokevirtual`/`invokeinterface` of a JDK method returning an integer, a `char` or a `boolean` | gap: `jdk-primitive-method`, with no assume form |
//! | `invokedynamic` string concatenation | implemented over strings and primitives: Strings (`null` as "null"), `char`s, `int`s, `short`s and `byte`s (their decimal digits) and the recipe's constants give a String of their content in order, up to [`MAX_STRING_CONTENT`] code units, past which its content is a named limit; a `long`, a floating-point number or a boolean converted gives an opaque String (their formatting is outside the model); an object argument it would convert is a gap, `string-conversion` |
//! | `invokevirtual` of the String methods of [`strings`], of `split(String, int)` and `matches(String)` ([`regex`]) and of `getBytes(Charset)` ([`bytes`]) on a String whose content the engine holds, and a `StringBuilder`'s constructors and methods of [`strings`] | modelled as formulas over the content, each exception thrown where the JDK throws it; `toLowerCase()` and `toLowerCase(Locale)` lower an ASCII String under the default locale the path set or the Locale given, Turkish and Azeri among them ([`locale`]); either of a String with a unit outside ASCII or under a Locale the engine knows nothing of, and `split` at anything but one constant character with a negative limit, stay the JDK call (a gap, or refused) |
//! | `invokedynamic` of `LambdaMetafactory.metafactory` | an object of the interface that holds what the site captured ([`Lambda`]); a call of the interface's method on it runs the lambda's method or the method a method reference names, its arguments cast as the JVM casts them ([`Engine::lambda_call`]); a call that would box or unbox is refused |
//! | `invokespecial`, `invokevirtual` and `invokeinterface` of `java.util.ArrayList`'s constructors and methods, in a check that asks for the model (`--model java.util.ArrayList`, [`crate::models::ON_REQUEST`]) | enter the model ([`ClassPath::runs_model`]) for what it keeps, and the run states it ([`Outcome::assumed`]); a method it does not keep, and every call in a check that did not ask, is the JDK call it was |
//! | `invokestatic` of `Arrays.stream(Object[])`, `Arrays.stream(int[])` and `IntStream.range(int, int)`, and `invokevirtual` of `String.chars()` | enter the stream models only the checker runs ([`crate::models::entry`]) |
//! | `invokestatic` of `Arrays.asList(T...)`, and the list's `size()`, `get(int)` and `toArray()` | modelled, for the checker alone: the model's bytecode (`lib/models/java/util/lists/ArrayAsList.java`), a view of the array. Any other method is the JDK's `AbstractList`'s, the JDK call it names |
//! | `new LinkedHashMap()`, and `values()` on the map with the collection's `size()` and `iterator()` and the iterator's `hasNext()` and `next()` | modelled, for the checker alone: the model's bytecode (`lib/models/java/util/LinkedHashMap.java`) over the `HashMap` model's chain of entries, which is in insertion order; the iterator fails fast as the JDK's. Any other method is the JDK call it names |
//! | `Pattern.quote`, `String.join`, `Pattern.compile(String, int)`, `Pattern.matcher`, `Matcher.matches()` as far as [`regex`] says; `Character.isLetter(char)` of an ASCII unit ([`strings`]); `Integer.parseInt(String)`, `MessageDigest.isEqual`, `Arrays.copyOf` of an array of numbers or of references and `getstatic` of `StandardCharsets.UTF_8` as far as [`bytes`] says; `getstatic` of `Locale`'s constants, `Locale.forLanguageTag(String)` and `Locale.setDefault(Locale)` as far as [`locale`] says; `Class.getName()`, `Class.getClassLoader()`, `Class.forName(String, boolean, ClassLoader)`, `Class.forName(String)` with its initialization, `Class.isAssignableFrom(Class)`, `Thread.currentThread()` and its `getContextClassLoader()`, `Collections.emptyMap()`, `Logger.getLogger(String)`, `getstatic` of a `java.util.logging.Level` below `INFO`, `Logger.isLoggable(Level)`, `new ArrayList()`, `new ConcurrentHashMap()` and `new ConcurrentHashMap(int)` as far as [`runtime`] says | modelled where their arguments let them be, under the assumptions the run states ([`Outcome::assumed`]); the JDK call (a gap) elsewhere |
//! | `ldc` of a string or a class | implemented: one object per distinct literal on a path, as the JVM interns strings and has one `Class` object per class, a String with its content, its code units as the class file holds them, an isolated surrogate included (`BootstrapArg::Units`) |
//! | floating point (`fconst`, `dconst`, `fadd` …, `fcmpl` …, `f2i` …), `jsr`/`ret`, `putstatic` of a JDK field, any other `getstatic` of one, a static field of a class taken to be initialized other than a constant, `multianewarray`, any other `invokedynamic`, a JDK method with a floating-point parameter or result or an array result, a native method | refused: no verdict, so that `--engine auto` can ask JBMC |
//! | under JBMC, not this engine ([`crate::jbmc_gaps`]): a method with no bytecode on JBMC's class path, or an `invokedynamic` JBMC does not link, or a monitor instruction, which JBMC drops | JBMC's gaps: its stub of a JDK method is one of the JDK kinds above, any other is `missing-body`, an unlinked call site is `invokedynamic`, and a method that synchronizes is `monitor`; this engine refuses the first two and implements monitors |
//!
//! A gap is refused by name under [`gaps::GapMode::Strict`], the default: the path ends there, and a run that met
//! one has no verdict unless another path is a violation, which stands. Under [`gaps::GapMode::Assume`] the engine
//! goes on with the approximation [`gaps::GapKind::approximation`] states, and the outcome names every gap it
//! assumed ([`Outcome::gaps`]); a gap with no assume form ([`gaps::GapKind::assumable`]) is refused there too. Under [`gaps::GapMode::Advised`] it refuses a gap as under strict: the proof
//! drivers stop before the engine runs when the gap scan finds one with no contract ([`crate::advice`]), so the
//! engine meets one only where the scan did not see it. A gap a contract closes (`--contracts`,
//! [`crate::gap_contracts`], [`Options::contracts`]) is no gap: at a JDK call the engine runs the contract's method
//! of the generated class [`crate::gap_contracts::CLASS`] in place of the call, whose intrinsics open the gap again
//! on an input outside the contract's `assume:` (met at the call), give an array it modifies fresh elements, give
//! a primitive result a fresh value, and end a path the contract's assertion excludes; an initializer whose contract throws nothing is taken to have run.
//! The outcome names every gap a contract closed, with the contract (treatment `contract`).

pub mod bitwuzla;
pub mod bits;
pub mod gaps;
pub mod bytes;
pub mod locale;
mod loops;
mod observed;
mod regex;
pub mod runtime;
pub mod sat;
pub mod strings;
pub mod transcript;

use std::collections::{BTreeMap, HashMap};
use std::rc::Rc;
use std::time::{Duration, Instant};

use crate::classfile::{ArithOp, ArrayKind, BootstrapArg, ClassFile, Cond, ExceptionHandler, Insn, Kind, MethodDescriptor, Narrow, Type};
use crate::classpath::ClassPath;
use crate::{Error, Verdict};
use bits::{Bits, Blaster, Lit, Model, FALSE, TRUE};
use gaps::{Closing, Closure, Gap, GapKind, GapMode, GapRecord, GapSetting, GapTreatment, JdkCall, Site};

/// What the engine is allowed.
#[derive(Debug, Clone)]
pub struct Options {
    /// How many times a loop's back edge may be taken on one path.
    pub unwind: u32,
    pub timeout: Duration,
    /// How many paths may be explored before the engine gives up.
    pub max_paths: u64,
    /// The longest an array parameter may be, as JBMC's `--max-nondet-array-length`.
    pub max_array_length: u32,
    /// How many paths are explored each on its own before the paths that meet are merged ([`Engine::merge`]): a
    /// small search is cheaper unmerged, every solver call being about one concrete path, and merging pays once
    /// the paths multiply. 0 merges from the start.
    pub merge_after: u64,
    /// How many paths are explored before they are merged eagerly ([`Engine::eager`]): paths whose heaps are not of
    /// one shape made one ([`align`]), each first rid of the locals nothing reads again and of the objects it no
    /// longer reaches, and a loop's exit a join. While the paths are few, two that made different objects stay two:
    /// a reference is then a known object on each, and what both compute of it is one formula by the gate hashing,
    /// which a merged heap's choices among objects would hide from it. Where a method makes objects in a loop (the
    /// parts of a String, a builder per element) such paths multiply without end, and past this count they are
    /// made one. The count is a measured compromise, twice [`Options::merge_after`]'s. The values sweep's totals
    /// over lists of up to 10 lines (908 paths merged from the start, `lib/tests/values.rs`) stay under it, and
    /// take what they took before: with heaps merged from the first path their two sums are no longer one formula
    /// and 6 lines take over a minute, and with 512 here 10 lines do. Example 286's decision, whose paths multiply
    /// by the Strings it makes, takes 1.7 times as long at 5 code units as with 512 (51 s for 30 s, unoptimized).
    pub merge_heaps_after: u64,
    /// Whether a loop that goes round more often than `unwind` is covered by an invariant the engine looks for
    /// ([`loops`]). Off, a path that needs another iteration ends the run with no verdict, whatever the loop.
    pub invariants: bool,
    /// What a gap does to the path that reaches it ([`gaps::GapMode`]): ends it (strict) or is assumed.
    pub gaps: GapMode,
    /// Under advised, the contracts that close gaps (`--contracts`, [`crate::gap_contracts`]): the engine applies
    /// each at its gap in place of refusing it.
    pub contracts: std::sync::Arc<BTreeMap<Gap, Closure>>,
    /// The file to write the run's solver calls to ([`transcript`]); when `None`, the directory the environment
    /// variable [`transcript::ENV`] names, if it is set.
    pub transcript: Option<std::path::PathBuf>,
    /// Makes the SAT solver the check is run on, empty ([`sat`]): by default the one the environment variable
    /// [`sat::ENV`] chooses, CaDiCaL unless it names another, and otherwise what a test puts behind the same
    /// interface. Results name the solver by [`solver_signature`], the default's.
    pub solver: fn() -> Box<dyn sat::Sat>,
    /// Which array parameters may be null and which may be one array ([`Parameters`]); by default each is an
    /// array of its own, never null.
    pub parameters: Parameters,
    /// The calls a checked summary stands in for ([`Summary`]).
    pub summaries: std::sync::Arc<Vec<Summary>>,
    /// The method the check proves a summary of (its class, name and descriptor): the run then also shows that it
    /// leaves the state as it was, and refuses one it can't show it of ([`Engine::in_summary`]).
    pub pure: Option<(String, String, String)>,
    /// Whether the method of [`Options::pure`] is proved by induction alone (`prove --decreases`), with no summary
    /// made of it: its calls of itself are then the only calls a statement of its result stands in for, and they
    /// are made in the state of the call under proof, which nothing it runs may write. So what it reads is not
    /// refused, where a summary's method may read nothing a caller can change ([`Engine::reads`]).
    pub own_induction: bool,
    /// The classes whose initializer the engine does not run, by internal name, each with the static state the
    /// initializer left on a JVM ([`crate::observed`], `--observed-initializer`): a use that initializes one gives
    /// the path that state, and the run states what that rests on ([`Outcome::assumed`]).
    pub observed: std::sync::Arc<crate::observed::Observations>,
    /// The models on request the engine runs for their classes ([`crate::models::ON_REQUEST`], `--model`), by
    /// internal name; the run states each as what it rests on ([`Outcome::assumed`]).
    pub models: std::sync::Arc<std::collections::BTreeSet<String>>,
    /// The previous version of a pair of versions the check holds in one program ([`crate::pairing`]): what its
    /// code asks by a name it computes is answered as on its own class path ([`runtime`]).
    pub previous: Option<std::sync::Arc<crate::relocate::Previous>>,
}

/// A static method whose calls run a method of the claim's class ([`crate::harness::expr::CLAIM_CLASS`]) of the same
/// descriptor instead: a checked summary of it, or the induction hypothesis of the proof of one ([`crate::summary`]).
/// The calls the harness and the claim's class make themselves run the method as it is.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Summary {
    pub owner: String,
    pub name: String,
    pub descriptor: String,
    pub stub: String,
}

impl Default for Options {
    fn default() -> Self {
        Options { unwind: 16, timeout: Duration::from_secs(600), max_paths: 200_000, max_array_length: 8, merge_after: 512, merge_heaps_after: 1024, invariants: true, gaps: GapMode::Strict, contracts: Default::default(), transcript: None, solver: sat::configured, parameters: Parameters::default(), summaries: Default::default(), pure: None, own_induction: false, observed: Default::default(), models: Default::default(), previous: None }
    }
}

/// The harness's array parameters beyond the default domain, by local-variable slot. Each array parameter has an
/// array of its own, of a fresh length up to the bound with fresh cells; a parameter that may be null, or may be
/// one array with another, is a symbolic reference ([`Choice`]) among null and the arrays it may be: its own, and
/// the own array of each parameter before it in its group. Any partition of a group into arrays is so reachable,
/// each array named by the first parameter holding it, and a witness says which parameters hold one array
/// ([`Outcome::raw_same`]).
///
/// A `String` parameter is taken only under an explicit bound, [`Parameters::max_string_length`]: it is then a
/// String of its own of every content up to the bound, any code units at all ([`Obj::content`]), and is nullable or
/// one String with another as an array parameter is (`==` then tells them apart, `equals` doesn't).
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Parameters {
    pub nullable: Vec<u32>,
    /// Groups of parameters any two of which may be one array, each group in slot order.
    pub may_alias: Vec<Vec<u32>>,
    /// The most code units a `String` parameter has: an input-domain bound, part of the claim. `None` refuses a
    /// `String` parameter, so that no check takes one under a bound it didn't state.
    pub max_string_length: Option<u32>,
}

impl Parameters {
    pub fn is_default(&self) -> bool {
        self.nullable.is_empty() && self.may_alias.is_empty() && self.max_string_length.is_none()
    }
}

/// The ranges a violating input is looked for in, smallest first, so that a counterexample is small enough to
/// read: the same stages as JBMC is run through (`[0:20]`, then `[-100000:100000]`, then everything). The engine
/// explores every path once; on a path that violates the property it asks the solver for an input in the first
/// stage that has one, and goes on to the next path only while no path has given one in the first stage.
pub const STAGES: &[(i64, i64)] = &[(0, 20), (-100_000, 100_000)];

/// The most questions to the solver in making a witness the least input ([`Engine::least`]).
const LEAST_QUESTIONS: usize = 2048;

/// The engine's answer about one harness.
#[derive(Debug, Clone)]
pub struct Outcome {
    pub verdict: Verdict,
    /// The violating input by parameter slot, as decimal numbers (a boolean as 0 or 1, a char by its code).
    pub raw_inputs: BTreeMap<u32, String>,
    /// The violating input's array parameters by slot, their elements as `raw_inputs` spells values, or `None`
    /// for a null one ([`Parameters::nullable`]).
    pub raw_arrays: BTreeMap<u32, Option<Vec<String>>>,
    /// The violating input's array parameters that are the same array as an earlier one, by slot: the slot of the
    /// first parameter holding it ([`Parameters::may_alias`]).
    pub raw_same: BTreeMap<u32, u32>,
    /// The stage the violating input was found in, as JBMC's `--java-assume-inputs-interval` would spell it;
    /// `None` when only the whole range has one.
    pub stage: Option<String>,
    /// Why there is no verdict: something outside the fragment, a loop beyond the bound, or the budget.
    pub problem: Option<String>,
    pub paths: u64,
    /// How many paths were absorbed into another at a join point ([`Engine::merge`]).
    pub merges: u64,
    pub solves: u64,
    pub solving: f64,
    pub evaluated: u64,
    pub evaluating: f64,
    pub clauses: u64,
    pub variables: i32,
    /// How many divisions and multiplications were left to the solver under the cheap facts, and how many of each
    /// had their circuit built because the solver got one wrong ([`bits::Blaster::sdivrem_lazy`],
    /// [`bits::Blaster::mul_lazy`]).
    pub divisions: u64,
    pub refined: u64,
    pub multiplications: u64,
    pub refined_multiplications: u64,
    /// How many word-level operations the solver was given as terms, when it takes terms ([`sat::Terms`]); zero
    /// when it is given clauses.
    pub word_operations: u64,
    pub seconds: f64,
    /// The phases the solving and evaluating above are not: reading and parsing class files, decoding methods,
    /// building circuits (the encoding, as the paths are explored), and reading a witness out of a model; the
    /// rest of `seconds` is the symbolic execution ([`Outcome::profile`]).
    pub loading: f64,
    pub decoding: f64,
    pub encoding: f64,
    pub witness: f64,
    /// The solver, for the report.
    pub solver: String,
    /// The gaps the run met, each refused (strict: a path ended there) or assumed, with where.
    pub gaps: Vec<GapRecord>,
    pub gap_mode: GapMode,
    /// What the models the run used take for granted about the JVM it stands for ([`strings::LOCALE_ASSUMPTION`],
    /// [`runtime::CLASS_PATH_ASSUMPTION`]): a verdict holds under them, and a statement lists them.
    pub assumed: Vec<String>,
    /// The loops that go round more often than the bound and that an invariant covers ([`loops`]), each as
    /// `p.C.m at pc N`: a proof holds of all their iterations, and a witness past one is run before it is believed.
    pub loops: Vec<String>,
    /// Where the run's solver calls were written, when they were ([`Options::transcript`]).
    pub transcript: Option<std::path::PathBuf>,
}

impl Outcome {
    /// The outcome in the shape of a JBMC result, so that the proof drivers treat it as one.
    pub fn into_jbmc_result(self, log: std::path::PathBuf) -> crate::jbmc::JbmcResult {
        let stats = self.stats();
        let profile = self.profile();
        let ending = crate::jbmc::Ending::of_native(self.verdict, self.problem.as_deref());
        crate::jbmc::JbmcResult {
            verdict: self.verdict,
            version: format!("jvmcontract's own checker ({})", self.solver),
            properties: 1,
            raw_inputs: self.raw_inputs,
            raw_arrays: self.raw_arrays,
            raw_same: self.raw_same,
            stage: self.stage,
            problem: self.problem,
            log,
            seconds: self.seconds,
            native: Some(stats),
            gaps: self.gaps,
            gap_mode: Some(self.gap_mode),
            ending,
            profile,
            congruence: None,
        }
    }

    /// The run's phases as [`crate::phases`] names them for both checkers: the symbolic execution is what the
    /// other phases leave of the run, gates evaluated in path models included, and nothing is `other`.
    pub fn profile(&self) -> crate::phases::Profile {
        let symbolic = (self.seconds - self.loading - self.decoding - self.encoding - self.solving - self.witness).max(0.0);
        let phases = crate::phases::Phases { loading: self.loading, lowering: self.decoding, symbolic, encoding: self.encoding, solving: self.solving, trace: self.witness, other: 0.0 }.completed(self.seconds);
        crate::phases::Profile { phases: Some(phases), formula: crate::phases::Formula { steps: None, conditions: None, variables: Some(self.variables.max(0) as u64), clauses: Some(self.clauses) } }
    }

    /// The numbers of [`Outcome::summary`], for a structured report.
    pub fn stats(&self) -> Stats {
        Stats {
            paths: self.paths,
            merges: self.merges,
            solver_calls: self.solves,
            solving_seconds: self.solving,
            gates_evaluated: self.evaluated,
            evaluating_seconds: self.evaluating,
            divisions: self.divisions,
            divisions_built: self.refined,
            multiplications: self.multiplications,
            multiplications_built: self.refined_multiplications,
            word_operations: self.word_operations,
            variables: self.variables,
            clauses: self.clauses,
            seconds: self.seconds,
            loading_seconds: self.loading,
            decoding_seconds: self.decoding,
            encoding_seconds: self.encoding,
            witness_seconds: self.witness,
            assumed: self.assumed.clone(),
            loops: self.loops.clone(),
        }
    }

    /// One line on what the run did, for the log.
    pub fn summary(&self) -> String {
        let gaps = match self.gaps.len() {
            0 => String::new(),
            n => {
                let refused = self.gaps.iter().filter(|g| g.treatment == Some(GapTreatment::Refused)).count();
                let what = match (refused, n - refused) {
                    (_, 0) => "refused".to_string(),
                    (0, _) => "assumed".to_string(),
                    (r, a) => format!("({r} refused, {a} assumed)"),
                };
                format!(", {n} gap{} {what} (--gaps {})", if n == 1 { "" } else { "s" }, self.gap_mode.name())
            }
        };
        format!("{:?}: {} paths, {} merged at joins, {} solver calls ({:.2} s), {} gates evaluated in path models ({:.2} s), {} of {} divisions and {} of {} multiplications built in full, {}{} variables, {} clauses, {:.2} s{gaps}{}", self.verdict, self.paths, self.merges, self.solves, self.solving, self.evaluated, self.evaluating, self.refined, self.divisions, self.refined_multiplications, self.multiplications, if self.word_operations > 0 { format!("{} word-level operations given as terms, ", self.word_operations) } else { String::new() }, self.variables, self.clauses, self.seconds, self.problem.as_deref().map(|p| format!("; {p}")).unwrap_or_default())
            + &self.transcript.as_ref().map(|t| format!("; solver calls written to {}", t.display())).unwrap_or_default()
    }
}

/// What the engine's search took, as [`Outcome::summary`] prints it: the paths it explored and merged, the solver's
/// calls and time, the gates evaluated in path models instead, the divisions and multiplications left to the solver
/// and those whose circuit had to be built, and the size of the last formula.
fn is_zero(n: &u64) -> bool {
    *n == 0
}

#[derive(Debug, Clone, PartialEq, serde::Serialize)]
pub struct Stats {
    pub paths: u64,
    pub merges: u64,
    pub solver_calls: u64,
    pub solving_seconds: f64,
    pub gates_evaluated: u64,
    pub evaluating_seconds: f64,
    pub divisions: u64,
    pub divisions_built: u64,
    pub multiplications: u64,
    pub multiplications_built: u64,
    /// Absent for a solver given clauses.
    #[serde(skip_serializing_if = "is_zero")]
    pub word_operations: u64,
    pub variables: i32,
    pub clauses: u64,
    pub seconds: f64,
    /// Reading and parsing class files, decoding methods, building circuits, and reading a witness out of a
    /// model: with the solving and evaluating above, the phases of [`crate::phases`].
    pub loading_seconds: f64,
    pub decoding_seconds: f64,
    pub encoding_seconds: f64,
    pub witness_seconds: f64,
    /// What the models the run used take for granted ([`Outcome::assumed`]); absent when they take nothing.
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub assumed: Vec<String>,
    /// The loops beyond the bound that an invariant covers ([`Outcome::loops`]); absent when there is none.
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub loops: Vec<String>,
}

impl Stats {
    /// The words of a verdict for the loops an invariant covers: `; 2 loops beyond the bound covered by invariants
    /// the checker found and proved (p.C.m at pc 4, p.C.n at pc 9)`, or nothing.
    pub fn covered_loops(&self) -> String {
        match self.loops.len() {
            0 => String::new(),
            1 => format!("; 1 loop beyond the bound covered by an invariant the checker found and proved ({})", self.loops[0]),
            n => format!("; {n} loops beyond the bound covered by invariants the checker found and proved ({})", self.loops.join(", ")),
        }
    }
}

/// Why a parameter type is outside the fragment, if it is. A `String` is in it under a bound
/// ([`Parameters::max_string_length`]).
pub fn unsupported_parameter(t: &Type) -> Option<String> {
    match t {
        Type::Boolean | Type::Byte | Type::Char | Type::Short | Type::Int | Type::Long => None,
        Type::Array(element) if matches!(**element, Type::Boolean | Type::Byte | Type::Char | Type::Short | Type::Int | Type::Long) => None,
        Type::Array(element) if is_string(element) => None,
        t if is_string(t) => None,
        other => Some(format!("a {} parameter", other.java_name())),
    }
}

const STRING: &str = "java/lang/String";

fn is_string(t: &Type) -> bool {
    matches!(t, Type::Object(name) if name == STRING)
}

/// The most code units the engine computes a String's content to: a concatenation that could make more gives a
/// String whose content is a named limit ([`Obj::limit`]), never a truncated one. An input's length is its own
/// bound ([`Parameters::max_string_length`]), and a literal has the units it has.
pub const MAX_STRING_CONTENT: usize = 64;

/// A cell of a `String[]` parameter in a witness ([`Outcome::raw_arrays`]): `null`, or `s:` and the String's code
/// units in decimal, comma-separated (`s:65,71,69`; `s:` for the empty String).
pub fn string_element(units: Option<&[u16]>) -> String {
    match units {
        None => "null".to_string(),
        Some(units) => format!("s:{}", units.iter().map(u16::to_string).collect::<Vec<_>>().join(",")),
    }
}

/// [`string_element`] read back: `Err` for a cell that is neither.
pub fn read_string_element(raw: &str) -> Result<Option<Vec<u16>>, String> {
    if raw == "null" {
        return Ok(None);
    }
    let units = raw.strip_prefix("s:").ok_or_else(|| format!("{raw:?} is not a String[] cell"))?;
    if units.is_empty() {
        return Ok(Some(Vec::new()));
    }
    units.split(',').map(|u| u.parse::<u16>().map_err(|_| format!("{u:?} is not a code unit"))).collect::<Result<Vec<u16>, String>>().map(Some)
}

/// The width of a cell of an array of `element`s: what a store keeps of the value, which a load extends to an
/// int (a boolean and a char without sign, a byte and a short with it) or leaves a long.
fn cell_width(element: &Type) -> usize {
    match element {
        Type::Boolean => 1,
        Type::Byte => 8,
        Type::Char | Type::Short => 16,
        Type::Long => 64,
        _ => 32,
    }
}

/// A value on the operand stack or in a local: an int (32 bits, which boolean, byte, char and short are too), a
/// long, a reference to an object of the path's (one this run made, an exception, a string) or `null`, or a
/// symbolic reference ([`Choice`]).
///
/// A reference whose target is known is `R`, the fast path every reference took before symbolic ones: nothing
/// about it is a formula. A `C` is made only where paths that differ in a reference merge ([`Engine::absorb`]),
/// where a read through a `C` gives references ([`Engine::get_field`]), or where an `aaload` reads a cell at a
/// computed index; a field or an array's cell may then hold one.
#[derive(Debug, Clone)]
enum Val {
    I(Bits),
    J(Bits),
    R(Option<usize>),
    C(Rc<Choice>),
}

impl Val {
    fn category(&self) -> usize {
        match self {
            Val::J(_) => 2,
            _ => 1,
        }
    }

    /// The reference as a choice: a known one is the only option, under `TRUE`. `None` for a primitive.
    fn options(&self) -> Option<Vec<(Lit, Option<usize>)>> {
        match self {
            Val::R(r) => Some(vec![(TRUE, *r)]),
            Val::C(c) => Some(c.0.clone()),
            _ => None,
        }
    }
}

/// A symbolic reference: one of a finite set of the path's objects, or null, each under a guard. The guards are
/// pairwise exclusive, and under the path's condition one of them holds, so the reference is the target of the
/// guard that holds. Options are sorted by target, each target once, at least two of them ([`choice`]), so that two
/// choices of the same guards and targets are equal.
///
/// `if_acmp`, `ifnull`, `ifnonnull` and `instanceof` on one are formulas over the guards (but for two Locales,
/// whose identity the JDK's cache decides: [`locale`]), `getfield` reads each
/// candidate's field and chooses among the values by the guards, and `putfield` writes each candidate's field
/// under its guard ([`Engine::put_field`]); an `aastore` stores one into a cell as it is when every candidate is of
/// the element type, and an `aaload` gives the one a cell holds. Every other instruction that needs to know the
/// object (a call on it, an array instruction on it, `checkcast`, `athrow`, a monitor) splits the path per option
/// first ([`Engine::concrete_ref`]), the reference then known on each.
#[derive(Debug, Clone, PartialEq, Eq)]
struct Choice(Vec<(Lit, Option<usize>)>);

/// The reference that is each target under its guard: options under `FALSE` dropped, the guards of one target
/// joined, sorted by target; a known reference when one target is left.
fn choice(b: &mut Blaster, options: Vec<(Lit, Option<usize>)>) -> Val {
    let mut by_target: BTreeMap<Option<usize>, Lit> = BTreeMap::new();
    for (g, t) in options {
        if g == FALSE {
            continue;
        }
        let joined = match by_target.get(&t) {
            Some(&h) => b.or(h, g),
            None => g,
        };
        by_target.insert(t, joined);
    }
    if let Some((&t, _)) = by_target.iter().find(|(_, &g)| g == TRUE) {
        return Val::R(t);
    }
    if by_target.len() <= 1 {
        return Val::R(by_target.into_keys().next().flatten());
    }
    Val::C(Rc::new(Choice(by_target.into_iter().map(|(t, g)| (g, t)).collect())))
}

/// An object made during the run: its class, and the fields written so far (an application exception's, say), or
/// the array it is.
///
/// A `java.lang.String` whose content the engine knows holds it in `array`: an [`Array`] of `char` cells, its
/// length the String's (symbolic, for an input), each cell a UTF-16 code unit, any of the 65,536, so that a
/// surrogate alone or a NUL is a content like any other ([`Obj::content`]). A String with no `array` is opaque:
/// what a conversion the engine doesn't model made (a number's digits), or a concatenation beyond
/// [`MAX_STRING_CONTENT`], whose `limit` says so. Its identity is its index, apart from its content: two Strings of
/// one content are two objects, as on the JVM.
#[derive(Debug, Clone)]
struct Obj {
    class: String,
    fields: BTreeMap<String, Val>,
    array: Option<Array>,
    /// Why an opaque String has no content, where that is a named limit rather than a gap.
    limit: Option<String>,
    /// The objects this one is, each under its guard, the guards exclusive: a String a JDK method returned that is
    /// the very String it was called on where nothing changed (`substring` of the whole range, `toLowerCase` of a
    /// String with no upper case), or the literal `""` where the result is empty. The content is this object's
    /// either way; only a comparison of references ([`Engine::same_lit`]) reads it.
    same: Vec<(Lit, usize)>,
    /// What a lambda or a method reference's object stands for ([`Lambda`]); the values it captured are its fields.
    lambda: Option<Rc<Lambda>>,
    /// What the object means as a regular expression, where the engine holds it as one ([`regex`]).
    regex: Option<Rc<regex::Regex>>,
    /// Which allocation made the object: the copies of it on the paths that split after it was made share the
    /// number, and no other object has it. Only [`align`] reads it, to pair an object with itself.
    made: u64,
    /// Whether the object was there when the method a summary is proved of was entered ([`Engine::in_summary`]).
    given: bool,
    /// Of an array of numbers past a summarized loop ([`loops`]): its cells hold any values, and `array.cells` is
    /// what they were once, which nothing reads. A read of a cell is then any value, a write changes nothing, and
    /// what would read the cells in bulk does not take it for an array ([`Obj::as_array`]) and is refused. A table
    /// of a thousand words a loop writes at an index it computes is this and no fresh word for each cell.
    unknown: bool,
}

/// An object `invokedynamic` made through `LambdaMetafactory.metafactory`: the interface it implements, the name
/// of that interface's one abstract method, and the method the call of it runs (a lambda's body, which javac
/// compiled to a method of the class it is written in, or the method a method reference names), with as many
/// captured values before the call's own arguments as the site passed. The values are the object's fields, by
/// position ([`captured_key`]).
#[derive(Debug, Clone, PartialEq)]
struct Lambda {
    interface: String,
    name: String,
    handle: crate::classfile::MethodHandle,
    captured: usize,
}

/// The field of a lambda's object that holds its `i`th captured value.
fn captured_key(i: usize) -> String {
    format!("\u{3bb}{i:03}")
}

/// The number of the next object made ([`Obj::made`]).
static MADE: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);

impl Obj {
    fn new(class: &str) -> Obj {
        Obj { class: class.to_string(), fields: BTreeMap::new(), array: None, limit: None, same: Vec::new(), lambda: None, regex: None, made: MADE.fetch_add(1, std::sync::atomic::Ordering::Relaxed), given: false, unknown: false }
    }

    /// The array the object is, where its cells are known: not a String's content.
    fn as_array(&self) -> Option<&Array> {
        self.array.as_ref().filter(|_| self.class.starts_with('[') && !self.unknown)
    }

    /// Whether the object is an array, its cells known or not ([`Obj::unknown`]).
    fn is_array(&self) -> bool {
        self.array.is_some() && self.class.starts_with('[')
    }

    /// A String's content: its length and code units.
    fn content(&self) -> Option<&Array> {
        self.array.as_ref().filter(|_| self.class == STRING)
    }
}

/// An array: its length, and a cell for every index it may have (as many as its length can be). An array of
/// primitives has `cells`, each as wide as [`cell_width`] says: a read at a symbolic index is a choice among them,
/// and a write updates each under the condition that the index is its own. An array of references has `refs`,
/// a reference in each cell (an object or null, or a symbolic reference, [`Choice`], as a field may hold), and no
/// `cells`: a reference is not a choice among bits, so an index into one is made a constant first, the path split
/// per cell ([`Engine::concrete_index`]). An index at or beyond the length is out of bounds whatever its cell
/// holds.
#[derive(Debug, Clone)]
struct Array {
    element: Type,
    length: Bits,
    cells: Vec<Bits>,
    refs: Vec<Val>,
}

/// Whether an array of `element`s holds references.
fn holds_references(element: &Type) -> bool {
    matches!(element, Type::Object(_) | Type::Array(_))
}

/// The class an object of type `t` has, as [`ClassPath::is_subtype`] names classes: an internal name, or an
/// array's descriptor (`[I`, `[Lcom/example/Color;`).
fn class_of(t: &Type) -> String {
    match t {
        Type::Object(name) => name.clone(),
        other => other.descriptor(),
    }
}

/// A violating input: the scalar parameters' values and the array parameters' elements, by slot.
#[derive(Debug, Clone, Default)]
struct Input {
    scalars: BTreeMap<u32, String>,
    arrays: BTreeMap<u32, Option<Vec<String>>>,
    same: BTreeMap<u32, u32>,
}

/// A method's decoded code, shared by every frame that runs it.
struct Decoded {
    insns: Vec<Insn>,
    pcs: Vec<u32>,
    index: HashMap<u32, usize>,
    handlers: Vec<ExceptionHandler>,
    max_locals: usize,
    /// Per instruction, its source line, when the class has line numbers: where a gap is met.
    lines: Vec<Option<u16>>,
    /// Per instruction, whether control can reach it from more than one place (the instruction after an `if`'s
    /// scope, a loop header, a handler): where the paths that reach it are merged ([`Engine::merge`]).
    joins: Vec<bool>,
    /// Whether an instruction is where a loop is left: a join once paths are merged eagerly ([`Engine::eager`]).
    exits: Vec<bool>,
    /// By instruction, the locals that are live before it: read on some way from there before they are written
    /// (an exception's handler is a way from every instruction its range covers). A local that is not live holds
    /// nothing the method will read, so a path waiting at a join forgets it ([`Frame::forget_dead`]), and two
    /// paths that differ only in such a local are of one shape.
    live: Vec<Vec<bool>>,
    /// The loops: each head a branch goes back to (its pc), with the pc of the last instruction that does.
    loops: Vec<(u32, u32)>,
}

#[derive(Clone)]
struct Frame {
    class: Rc<ClassFile>,
    method: String,
    code: Rc<Decoded>,
    /// The index (into `code.insns`) of the instruction being executed.
    at: usize,
    locals: Vec<Option<Val>>,
    stack: Vec<Val>,
    /// The class whose `<clinit>` the frame runs: when it returns the class is initialized, and when an exception
    /// leaves it the class is erroneous (JVMS §5.5, steps 10 and 11).
    initializes: Option<String>,
    /// The classes the instruction being executed began to initialize and that wait for their superclasses' and
    /// superinterfaces' initializers to finish (JVMS §5.5, step 7), outermost first: the instruction runs again
    /// each time one of those returns, and an exception that leaves it makes them erroneous.
    entered: Vec<String>,
    /// How often the back edges to each loop head (by its pc) were taken since the loop was last entered afresh:
    /// a new frame enters every loop afresh, and a back edge enters afresh each loop whose head is in its body
    /// (see [`Engine::jump`]).
    back_edges: BTreeMap<u32, u32>,
    /// The loops, by head, that the frame is in past the bound, in the state an invariant gives ([`loops`]): a
    /// back edge to one ends the path, and they are forgotten as the counts are.
    summarized: std::collections::BTreeSet<u32>,
}

impl Frame {
    fn new(class: Rc<ClassFile>, method: String, code: Rc<Decoded>, locals: Vec<Option<Val>>) -> Frame {
        Frame { class, method, code, at: 0, locals, stack: Vec::new(), initializes: None, entered: Vec::new(), back_edges: BTreeMap::new(), summarized: Default::default() }
    }

    fn pc(&self) -> u32 {
        self.code.pcs[self.at]
    }

    /// Forgets the locals that are not live before the frame's instruction ([`Decoded::live`]), and holds a slot
    /// for every local the method has.
    fn forget_dead(&mut self) {
        let live = &self.code.live[self.at];
        self.locals.resize(self.locals.len().max(live.len()), None);
        for (s, local) in self.locals.iter_mut().enumerate() {
            if !live.get(s).copied().unwrap_or(true) {
                *local = None;
            }
        }
        // A slot past the method's locals that holds nothing (the second half of a wide store's last slot) is no
        // part of the frame.
        while self.locals.len() > live.len() && self.locals.last().is_some_and(Option::is_none) {
            self.locals.pop();
        }
    }
}

/// One path through the harness: its frames (each with how often its loops' back edges were taken), the condition
/// that selects it (a conjunction of literals), models of that condition, and its objects.
#[derive(Clone)]
struct Path {
    frames: Vec<Frame>,
    cond: Vec<Lit>,
    /// Inputs that take the path, at least one: the solver's answer when the path was split off, or every input
    /// zero for the first, and after a merge the models of every path merged into it (up to [`MOST_MODELS`]). A
    /// side of a branch one of them takes is feasible without asking the solver, so a branch whose two sides are
    /// each taken by a model costs no solver call, and each side keeps the models that take it.
    models: Vec<Model>,
    /// Whether the path is known feasible: a twin split off at a branch the solver did not decide within its
    /// probe's budget keeps its parent's model, which takes the other side, and waits in `Engine::deferred`
    /// until every decided path is done, when the solver is asked about it with all the time left.
    undecided: bool,
    /// Whether the path was just taken from a join point, where it waited for the other paths to arrive, and is
    /// to run the join's instruction rather than wait there again.
    resumed: bool,
    objects: Vec<Obj>,
    /// The object each string or class literal loaded so far is, so that every load of one literal is the same
    /// reference, as the JVM's interned strings and `Class` objects are.
    literals: BTreeMap<Literal, usize>,
    /// The state of initialization of each application class the path has used (JVMS §5.5); a class absent is not
    /// initialized yet.
    classes: BTreeMap<String, ClassState>,
    /// The static fields of application classes the path has written, by declaring class and name; one it has not
    /// is its `ConstantValue`, or zero or null.
    statics: BTreeMap<(String, String), Val>,
    /// The loop an iteration of which the path runs to find the loop's invariant ([`loops`]).
    probing: Option<loops::Probe>,
    /// Whether the path is past a loop an invariant covers: its state then stands for more than the states a run
    /// reaches, and a computed index into a large array is not followed ([`loops`]).
    loose: bool,
}

/// Where a class is in its initialization (JVMS §5.5).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum ClassState {
    /// Begun and not finished: a use of the class from its own initialization goes on as if it were initialized.
    InProgress,
    /// Its `<clinit>` ran and returned, or it has none.
    Done,
    /// Taken to be initialized, its `<clinit>` not run: a `class-initializer` gap assumed, or closed by a contract.
    /// Only its constants are known.
    Assumed,
    /// Its initialization threw: a later use throws `NoClassDefFoundError`.
    Erroneous,
}

/// A string or class literal, the identity of what an `ldc` of it loads: a string by its code units, an isolated
/// surrogate included, so that two literals are one object exactly when the JVM interns them as one.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
enum Literal {
    Str(Vec<u16>),
    Class(String),
    /// The loader of the classes of the check's class path ([`runtime`]).
    Loader,
    /// The `java.util.logging.Logger` of a name ([`runtime`]).
    Logger(Vec<u16>),
    /// A charset of `java.nio.charset.StandardCharsets`, by its field's name ([`bytes`]).
    Charset(&'static str),
    /// A constant of `java.util.Locale`, by its field's name ([`locale`]).
    Locale(String),
    /// A level of `java.util.logging.Level` below `INFO`, by its field's name ([`runtime`]).
    Level(&'static str),
    /// The one thread of the run ([`runtime`]).
    Thread,
    /// The one map `Collections.emptyMap()` returns ([`runtime`]).
    EmptyMap,
}

/// Where a path waits at a join point: for each frame, outermost first, where it is in the method, then the class
/// and the method. Where it is: each loop around its instruction, outermost first, as the loop's head and how
/// often the frame has gone round it, then the instruction itself (its pc). The paths of one group are at the same
/// instruction of the same calls in the same iteration of every loop around it, and the group earliest in the
/// harness (the smallest key) is resumed first, since what is still running can only arrive at a later one: of two
/// frames in one loop, the one that has gone round it less is the earlier, whichever instruction of the loop each
/// is at, and a frame in a loop is later than one before the loop's head and earlier than one past its end.
type JoinKey = Vec<(Vec<(u32, u32)>, String, String)>;

fn join_key(path: &Path, loops: bool) -> JoinKey {
    path.frames
        .iter()
        .map(|f| {
            let pc = f.pc();
            // The loops the frame has left say nothing of where it is; the ones around it do, gone round or not.
            let mut place: Vec<(u32, u32)> = if loops { f.code.loops.iter().filter(|(head, last)| *head <= pc && pc <= *last).map(|(head, _)| (*head, f.back_edges.get(head).copied().unwrap_or(0))).collect() } else { Vec::new() };
            place.push((pc, 0));
            (place, f.class.name.clone(), f.method.clone())
        })
        .collect()
}

/// The value that is `x` where `g` holds and `y` where it doesn't: bits chosen bit by bit, references a
/// [`Choice`] of both's options. `None` when the two are not of one kind ([`mergeable`]).
fn choose(b: &mut Blaster, g: Lit, x: &Val, y: &Val) -> Option<Val> {
    match (x, y) {
        (Val::I(p), Val::I(q)) => Some(Val::I(if p == q { p.clone() } else { b.ite_bits(g, p, q) })),
        (Val::J(p), Val::J(q)) => Some(Val::J(if p == q { p.clone() } else { b.ite_bits(g, p, q) })),
        (Val::R(p), Val::R(q)) if p == q => Some(x.clone()),
        (Val::C(p), Val::C(q)) if p == q => Some(x.clone()),
        _ => {
            let (xs, ys) = (x.options()?, y.options()?);
            let mut options = Vec::with_capacity(xs.len() + ys.len());
            for (h, t) in xs {
                options.push((b.and(g, h), t));
            }
            for (h, t) in ys {
                options.push((b.and(-g, h), t));
            }
            Some(choice(b, options))
        }
    }
}

/// Makes every copy of `choice` in the path's state (locals, stacks, static fields, objects' fields) the known
/// reference `target`, once the path has taken the option of `target`.
fn substitute(path: &mut Path, choice: &Rc<Choice>, target: Option<usize>) {
    let fix = |v: &mut Val| {
        if matches!(v, Val::C(c) if Rc::ptr_eq(c, choice) || **c == **choice) {
            *v = Val::R(target);
        }
    };
    for frame in &mut path.frames {
        frame.locals.iter_mut().flatten().for_each(fix);
        frame.stack.iter_mut().for_each(fix);
    }
    path.statics.values_mut().for_each(fix);
    for o in &mut path.objects {
        o.fields.values_mut().for_each(fix);
        if let Some(array) = &mut o.array {
            array.refs.iter_mut().for_each(fix);
        }
    }
}

/// Whether two values can be one value under a condition: both ints, both longs, or both references, which
/// are a [`Choice`] by the condition where they differ.
fn mergeable(a: &Val, b: &Val) -> bool {
    matches!((a, b), (Val::I(_), Val::I(_)) | (Val::J(_), Val::J(_)) | (Val::R(_) | Val::C(_), Val::R(_) | Val::C(_)))
}

/// Whether two paths at the same join point have states of one shape, so that they can be merged slot by slot and
/// object by object: the same slots and objects, each object of the same class with the same fields (the paths
/// differ only in bits and in which objects references denote), an array's cells of references among them.
fn same_shape(a: &Path, b: &Path) -> bool {
    frames_alike(a, b) && a.objects.len() == b.objects.len() && a.literals == b.literals && a.objects.iter().zip(&b.objects).all(|(o, q)| alike(o, q))
}

/// Whether two paths at the same join point have frames, static fields and initialized classes that can be made
/// one: all of [`same_shape`] but the objects.
fn frames_alike(a: &Path, b: &Path) -> bool {
    let slots = |x: &Option<Val>, y: &Option<Val>| match (x, y) {
        (None, None) => true,
        (Some(x), Some(y)) => mergeable(x, y),
        _ => false,
    };
    a.frames.len() == b.frames.len()
        && a.frames.iter().zip(&b.frames).all(|(f, g)| f.locals.len() == g.locals.len() && f.locals.iter().zip(&g.locals).all(|(x, y)| slots(x, y)) && f.stack.len() == g.stack.len() && f.stack.iter().zip(&g.stack).all(|(x, y)| mergeable(x, y)))
        && a.frames.iter().zip(&b.frames).all(|(f, g)| f.initializes == g.initializes && f.entered == g.entered && f.summarized == g.summarized)
        && a.classes == b.classes
        && a.statics.len() == b.statics.len()
        && a.statics.iter().zip(&b.statics).all(|((k, x), (l, y))| k == l && mergeable(x, y))
}

/// Whether two objects, one of each of two paths, can be one object that is the first on its path and the second
/// on the other: the same class, the same fields of the same kinds, the same kind of content.
fn alike(o: &Obj, q: &Obj) -> bool {
    o.class == q.class
        && o.limit == q.limit
        && o.lambda == q.lambda
        && o.regex == q.regex
        && o.given == q.given
        && o.fields.len() == q.fields.len()
        && o.fields.iter().zip(&q.fields).all(|((k, x), (l, y))| k == l && mergeable(x, y))
        && match (&o.array, &q.array) {
            (None, None) => true,
            // A String's or a builder's content of fewer cells is padded when the two are made one: a cell
            // at or past the length is never read.
            (Some(x), Some(y)) => x.element == y.element && (x.cells.len() == y.cells.len() || holds_text(&o.class)) && x.refs.len() == y.refs.len(),
            _ => false,
        }
}

/// Where each object of `other` is in the heap that holds both paths' objects, for two paths at a join point whose
/// heaps are not of one shape (one made objects the other did not: a loop that makes one per element, left after
/// different counts): an object of `into` it is made one with, or a place after `into`'s objects. `None` when the
/// frames cannot be made one.
///
/// Any pairing is sound that pairs an object with at most one other, since an object of the merged heap is
/// `into`'s where `into`'s path is taken and `other`'s elsewhere, and a reference is renumbered with its object. The
/// one chosen keeps the merged heap small: a literal with the same literal; an object with its own copy on the
/// other path ([`Obj::made`]); then the objects the two paths hold in the same place (a local, a field of two
/// paired objects, a cell of two paired arrays).
fn align(into: &Path, other: &Path) -> Option<Vec<usize>> {
    if !frames_alike(into, other) || !into.literals.keys().eq(other.literals.keys()) {
        return None;
    }
    let mut map: Vec<Option<usize>> = vec![None; other.objects.len()];
    let mut taken = vec![false; into.objects.len()];
    let mut paired: std::collections::VecDeque<(usize, usize)> = std::collections::VecDeque::new();
    for (literal, &j) in &other.literals {
        let i = into.literals[literal];
        if taken[i] || map[j].is_some() || !alike(&into.objects[i], &other.objects[j]) {
            return None;
        }
        (map[j], taken[i]) = (Some(i), true);
        paired.push_back((i, j));
    }
    // More than one object may have a number: a merged heap keeps both of two copies that were not alike.
    let mut made: HashMap<u64, Vec<usize>> = HashMap::new();
    for (i, o) in into.objects.iter().enumerate() {
        made.entry(o.made).or_default().push(i);
    }
    for (j, q) in other.objects.iter().enumerate() {
        if map[j].is_some() {
            continue;
        }
        if let Some(&i) = made.get(&q.made).and_then(|copies| copies.iter().find(|&&i| !taken[i] && alike(&into.objects[i], q))) {
            (map[j], taken[i]) = (Some(i), true);
            paired.push_back((i, j));
        }
    }
    // The objects two values hold in the same place, to try as a pair.
    fn held(x: &Val, y: &Val, out: &mut std::collections::VecDeque<(usize, usize)>) {
        if let (Val::R(Some(i)), Val::R(Some(j))) = (x, y) {
            out.push_back((*i, *j));
        }
    }
    let mut candidates = std::collections::VecDeque::new();
    for (f, g) in into.frames.iter().zip(&other.frames) {
        f.locals.iter().zip(&g.locals).for_each(|(x, y)| {
            if let (Some(x), Some(y)) = (x, y) {
                held(x, y, &mut candidates);
            }
        });
        f.stack.iter().zip(&g.stack).for_each(|(x, y)| held(x, y, &mut candidates));
    }
    into.statics.values().zip(other.statics.values()).for_each(|(x, y)| held(x, y, &mut candidates));
    loop {
        // What two paired objects hold in the same place comes before the next candidate.
        while let Some((i, j)) = paired.pop_front() {
            let (o, q) = (&into.objects[i], &other.objects[j]);
            o.fields.values().zip(q.fields.values()).for_each(|(x, y)| held(x, y, &mut candidates));
            if let (Some(x), Some(y)) = (&o.array, &q.array) {
                x.refs.iter().zip(&y.refs).for_each(|(x, y)| held(x, y, &mut candidates));
            }
            o.same.iter().zip(&q.same).for_each(|((_, t), (_, u))| candidates.push_back((*t, *u)));
        }
        let Some((i, j)) = candidates.pop_front() else { break };
        if map[j].is_none() && !taken[i] && alike(&into.objects[i], &other.objects[j]) {
            (map[j], taken[i]) = (Some(i), true);
            paired.push_back((i, j));
        }
    }
    let mut next = into.objects.len();
    Some(
        map.into_iter()
            .map(|place| {
                place.unwrap_or_else(|| {
                    next += 1;
                    next - 1
                })
            })
            .collect(),
    )
}

/// Renumbers every reference the path's state holds (its frames, static fields, literals, and its objects' fields,
/// cells and identities): the object `o` becomes `number(o)`. The objects themselves stay where they are.
fn renumber(path: &mut Path, number: &dyn Fn(usize) -> usize) {
    let value = |v: &mut Val| match v {
        Val::R(Some(o)) => *o = number(*o),
        Val::C(c) => {
            let mut options: Vec<(Lit, Option<usize>)> = c.0.iter().map(|(g, t)| (*g, t.map(number))).collect();
            options.sort_by_key(|(_, t)| *t);
            *v = Val::C(Rc::new(Choice(options)));
        }
        _ => {}
    };
    for obj in &mut path.objects {
        obj.fields.values_mut().for_each(value);
        if let Some(array) = &mut obj.array {
            array.refs.iter_mut().for_each(value);
        }
        for (_, t) in &mut obj.same {
            *t = number(*t);
        }
    }
    for frame in &mut path.frames {
        frame.locals.iter_mut().flatten().for_each(value);
        frame.stack.iter_mut().for_each(value);
    }
    path.statics.values_mut().for_each(value);
    for o in path.literals.values_mut() {
        *o = number(*o);
    }
}

/// Whether an object of `class` holds text in its array: a String's content or a StringBuilder's, whose cells at
/// or past the length nothing reads.
fn holds_text(class: &str) -> bool {
    class == STRING || class == strings::BUILDER
}

/// Drops the objects the path's state no longer reaches and numbers the rest in the order it reaches them: the
/// literals in their order, then each frame's locals and stack from the outermost, then the static fields, each
/// object followed through its fields, its array's references and the objects it is ([`Obj::same`]). What a
/// path computed and let go of (the Strings a call made on the way to its result) is then no part of its shape,
/// and two paths that reach the same join by different work are one shape again ([`same_shape`]).
fn collect(path: &mut Path) {
    fn targets(v: &Val, out: &mut Vec<usize>) {
        match v {
            Val::R(Some(o)) => out.push(*o),
            Val::C(c) => out.extend(c.0.iter().filter_map(|(_, t)| *t)),
            _ => {}
        }
    }
    let mut roots = Vec::new();
    roots.extend(path.literals.values().copied());
    for frame in &path.frames {
        frame.locals.iter().flatten().for_each(|v| targets(v, &mut roots));
        frame.stack.iter().for_each(|v| targets(v, &mut roots));
    }
    path.statics.values().for_each(|v| targets(v, &mut roots));
    // Depth first, each object numbered when first reached.
    let mut number: Vec<Option<usize>> = vec![None; path.objects.len()];
    let mut order = Vec::new();
    let mut stack: Vec<usize> = roots.into_iter().rev().collect();
    while let Some(o) = stack.pop() {
        if number[o].is_some() {
            continue;
        }
        number[o] = Some(order.len());
        order.push(o);
        let obj = &path.objects[o];
        let mut next = Vec::new();
        obj.fields.values().for_each(|v| targets(v, &mut next));
        if let Some(array) = &obj.array {
            array.refs.iter().for_each(|v| targets(v, &mut next));
        }
        next.extend(obj.same.iter().map(|(_, t)| *t));
        stack.extend(next.into_iter().rev());
    }
    if order.len() == path.objects.len() && order.iter().enumerate().all(|(i, o)| i == *o) {
        return;
    }
    path.objects = order.iter().map(|&o| path.objects[o].clone()).collect();
    renumber(path, &|o| number[o].expect("a reached object"));
}

/// How a path ended.
enum End {
    /// The harness returned: the property holds on this path.
    Returned,
    /// The path condition cannot be satisfied.
    Infeasible,
    /// The harness's assertion failed on a path of this condition, which the solver found satisfiable.
    Violation(Vec<Lit>),
    /// A loop needed more iterations than the bound.
    Unwound(String),
    /// The path reached a gap under `--gaps strict`, which refuses it: what lies beyond it is not known.
    Gap,
    /// The path reached a join point and waits there for the paths that arrive after it.
    Parked,
    /// The path is back at the head (a pc) of a loop an invariant covers ([`loops`]), in a state the head's state
    /// stands for: with the path, where it is that loop's invariant that is still being found.
    Back(u32, Option<Box<Path>>),
    /// The path left the loop an iteration of which is run to find its invariant ([`loops::Probe`]).
    Left,
}

/// Why the engine stops without a verdict.
enum Stop {
    Unsupported(String),
    Budget(String),
}

type Step = Result<Option<End>, Stop>;

/// Where a use of a class leaves its initialization ([`Engine::initialise_class`]).
enum Initialising {
    /// Initialized, or being initialized by an enclosing use: the instruction goes on.
    Ready,
    /// A `<clinit>` was pushed to run first.
    Running,
    /// The class, or one it needs first, is erroneous: `NoClassDefFoundError`.
    Erroneous,
    /// A gap ended the path.
    End(End),
}

/// Which sides of a branch are feasible under the path condition.
enum Sides {
    /// Both, with the path's models that take each side (the solver's answer where none of its own did).
    Both { then_models: Vec<Model>, else_models: Vec<Model> },
    Then,
    Else,
    /// The side the path's models take, the other undecided: the solver did not answer within the probe's budget.
    Undecided { model_takes_then: bool },
}

/// How many models a path keeps after a merge: the first ones, since every path has at least one.
const MOST_MODELS: usize = 16;

/// The least work a branch probe is given, in the solver's conflicts ([`Engine::probe`]): about two seconds of
/// CaDiCaL on a formula of a few hundred thousand clauses, and less on a smaller one. `Pricing#total`'s regression
/// proof (VF-010) has a feasible side that takes 5,167, about a second, which the old floor of a second of time
/// decided on some runs and not others.
const PROBE_CONFLICTS: u64 = 10_000;

/// The fewest paths the search for a smaller witness runs past the first violation, when fewer ran before it
/// ([`Engine::witness_budget`]).
const WITNESS_PATHS: u64 = 64;

struct Engine<'a> {
    cp: &'a ClassPath,
    summaries: std::sync::Arc<Vec<Summary>>,
    pure: Option<(String, String, String)>,
    own_induction: bool,
    b: Blaster,
    codes: HashMap<(String, String, String), Rc<Decoded>>,
    pending: Vec<Path>,
    /// The paths the solver did not decide in time, taken up when `pending` is empty.
    deferred: Vec<Path>,
    /// The paths waiting at join points, by where they wait; a group is merged and resumed when `pending` is
    /// empty, the earliest first.
    waiting: BTreeMap<JoinKey, Vec<Path>>,
    merges: u64,
    merge_after: u64,
    merge_heaps_after: u64,
    /// Whether a loop beyond the bound is given an invariant ([`Options::invariants`]).
    invariants: bool,
    unwind: u32,
    deadline: Instant,
    /// Set at the first violation: the paths and the solver's work (conflicts, [`Blaster::work`]) at which the search
    /// for a smaller witness stops, as many again as the first violation took, at least [`WITNESS_PATHS`] paths and
    /// [`PROBE_CONFLICTS`] conflicts. Counted in work, not time, so that the witness reported is the same on every
    /// machine and every run, as the probes are (VF-010).
    witness_budget: Option<(u64, u64)>,
    max_paths: u64,
    paths: u64,
    /// The harness's scalar parameters: slot, type and bits, for reading the input off a model.
    params: Vec<(u32, Type, Bits)>,
    /// The harness's array parameters: slot, element type, length and cells, for reading the input off a model
    /// (the cells as made; a path writes into its own copy of the object).
    arrays: Vec<(u32, Type, Bits, Vec<Bits>)>,
    /// What the models the run used take for granted beyond the bytecode (the default locale, under
    /// [`strings::LOCALE_ASSUMPTION`]), for the statement.
    assumed: std::collections::BTreeSet<String>,
    /// The loops an invariant covered past the bound ([`loops`]), for the outcome.
    loops: std::collections::BTreeSet<String>,
    /// While an iteration is run to find a loop's invariant: the arrays read or written at an index that is no
    /// constant, by allocation, each with the index ([`loops`]).
    indexed: Option<Vec<(u64, Bits)>>,
    /// The same loops by class, method and head, for [`Engine::summarize_at_entry`].
    known_loops: HashMap<(String, String, u32), loops::Known>,
    /// Each `String[]` parameter's own array, by slot: its length, and for each cell whether it is null, and the
    /// length and code units of the String it holds otherwise.
    string_arrays: Vec<(u32, Bits, Vec<(Lit, Bits, Vec<Bits>)>)>,
    /// The array parameters that are a choice ([`Parameters`]): slot, and each option's guard with the slot whose
    /// own array it is, or null.
    choices: Vec<(u32, Vec<(Lit, Option<u32>)>)>,
    max_array_length: u32,
    /// One literal per entry of [`STAGES`], true when every parameter is in the range; built at the first
    /// violation, so that a proof pays nothing for them.
    stage_lits: Vec<Option<Lit>>,
    gap_mode: GapMode,
    /// The gaps met so far, with where.
    met: BTreeMap<Gap, std::collections::BTreeSet<Site>>,
    /// The contracts that close gaps, and the gaps they closed so far, with where.
    contracts: std::sync::Arc<BTreeMap<Gap, Closure>>,
    applied: BTreeMap<Gap, std::collections::BTreeSet<Site>>,
    /// Whether an object of a class has a field that a subclass along its chain declares again, by class: only
    /// then does an access need the field's resolution to find its key ([`ClassPath::field_key`]).
    hides: HashMap<String, bool>,
    /// What the JVM initializes before a class, by class ([`gaps::initialization_supers`]).
    supers: HashMap<String, Rc<Vec<String>>>,
    /// Whether the engine runs a class's `<clinit>`, by class ([`gaps::runs_initializer`]).
    runs: HashMap<String, bool>,
    /// The observed initializers ([`Options::observed`]), and the static fields an observation taken so far holds
    /// no value of, each with what it was ([`Engine::unheld_static`]).
    observed: std::sync::Arc<crate::observed::Observations>,
    previous: Option<std::sync::Arc<crate::relocate::Previous>>,
    unheld: HashMap<(String, String), String>,
    /// The time spent decoding methods, and reading witnesses out of models (their solving and encoding apart).
    decoding: Duration,
    witness: Duration,
}

fn unsupported<T>(what: impl Into<String>) -> Result<T, Stop> {
    Err(Stop::Unsupported(what.into()))
}

/// Whether a load or store instruction of `kind` fits an array of `element`s, as the verifier requires.
fn check_kind(kind: ArrayKind, element: &Type) -> Result<(), Stop> {
    let fits = match kind {
        ArrayKind::Int => *element == Type::Int,
        ArrayKind::Long => *element == Type::Long,
        ArrayKind::Byte => matches!(element, Type::Byte | Type::Boolean),
        ArrayKind::Char => *element == Type::Char,
        ArrayKind::Short => *element == Type::Short,
        ArrayKind::Float | ArrayKind::Double => return unsupported("floating point"),
        ArrayKind::Ref => return unsupported("arrays of references"),
    };
    if fits {
        Ok(())
    } else {
        unsupported(format!("a {kind:?} array instruction on a {}[]", element.java_name()))
    }
}

/// Checks `class.method` of the harness: every path either returns or is infeasible (verified), or one throws the
/// `AssertionError` on an input the solver names (violation).
pub fn check(cp: &ClassPath, class: &str, method: &str, options: &Options) -> Result<Outcome, Error> {
    let started = Instant::now();
    let Some(harness) = cp.bytecode(class)? else {
        return Err(Error::new(format!("harness class {class} not found")));
    };
    let m = harness.method_by_name(method).ok_or_else(|| Error::new(format!("no method {method} in {class}")))?.clone();
    let descriptor = MethodDescriptor::parse(&m.descriptor)?;
    sat::configuration()?;
    let mut solver = (options.solver)();
    let transcript = match transcript::destination(options.transcript.as_deref()) {
        None => None,
        Some(path) if solver.terms().is_some() => {
            return Err(Error::new(format!("cannot write the transcript {}: it records clauses, and {} is given the engine's terms", path.display(), solver.signature())));
        }
        Some(path) => {
            let header = [
                format!("jvmcontract {}: the own checker's solver calls, in order ({})", env!("CARGO_PKG_VERSION"), "lib/src/bmc/transcript.rs"),
                format!("solver: {}", solver.signature()),
                format!("check: {class}.{method}{}", m.descriptor),
                format!("options: unwind {}, max array length {}, max paths {}, merge after {}, timeout {:.3} s, gaps {}", options.unwind, options.max_array_length, options.max_paths, options.merge_after, options.timeout.as_secs_f64(), options.gaps.name()),
            ];
            Some(transcript::Transcript::create(&path, &header).map_err(|e| Error::new(format!("cannot write the transcript {}: {e}", path.display())))?)
        }
    };
    let mut engine = Engine {
        cp,
        b: Blaster::over(solver, transcript),
        codes: HashMap::new(),
        pending: Vec::new(),
        deferred: Vec::new(),
        waiting: BTreeMap::new(),
        merges: 0,
        merge_after: options.merge_after,
        merge_heaps_after: options.merge_heaps_after,
        invariants: options.invariants,
        unwind: options.unwind,
        deadline: started + options.timeout,
        witness_budget: None,
        max_paths: options.max_paths,
        paths: 0,
        params: Vec::new(),
        arrays: Vec::new(),
        string_arrays: Vec::new(),
        assumed: Default::default(),
        loops: Default::default(),
        known_loops: Default::default(),
        indexed: None,
        choices: Vec::new(),
        max_array_length: options.max_array_length,
        stage_lits: vec![None; STAGES.len()],
        gap_mode: options.gaps,
        met: BTreeMap::new(),
        contracts: options.contracts.clone(),
        summaries: options.summaries.clone(),
        pure: options.pure.clone(),
        own_induction: options.own_induction,
        applied: BTreeMap::new(),
        hides: HashMap::new(),
        supers: HashMap::new(),
        runs: HashMap::new(),
        observed: options.observed.clone(),
        previous: options.previous.clone(),
        unheld: HashMap::new(),
        decoding: Duration::ZERO,
        witness: Duration::ZERO,
    };
    // An observed initializer is one the engine has the result of: an initializer that uses the class's static
    // fields is no further outside the fragment for it ([`gaps::runs_initializer`]), which is decided anew.
    if *cp.requested_models.borrow() != *options.models {
        *cp.requested_models.borrow_mut() = (*options.models).clone();
        cp.initializer_runs.borrow_mut().clear();
    }
    if *cp.observed_initializers.borrow() != options.observed.keys().cloned().collect() {
        *cp.observed_initializers.borrow_mut() = options.observed.keys().cloned().collect();
        cp.initializer_runs.borrow_mut().clear();
    }
    let loading_before = cp.loading();
    let solver = engine.b.signature();
    let jdk = gaps::jdk_release();
    let outcome = |engine: &Engine, verdict: Verdict, input: Input, stage: Option<String>, problem: Option<String>| Outcome {
        verdict,
        raw_inputs: input.scalars,
        raw_arrays: input.arrays,
        raw_same: input.same,
        stage,
        problem,
        paths: engine.paths,
        merges: engine.merges,
        solves: engine.b.solves,
        solving: engine.b.solving.as_secs_f64(),
        evaluated: engine.b.evaluated,
        evaluating: engine.b.evaluating.as_secs_f64(),
        clauses: engine.b.clauses,
        variables: engine.b.variables(),
        divisions: engine.b.divisions().0,
        refined: engine.b.divisions().1,
        multiplications: engine.b.multiplications().0,
        refined_multiplications: engine.b.multiplications().1,
        word_operations: engine.b.word_operations() as u64,
        seconds: started.elapsed().as_secs_f64(),
        loading: (cp.loading() - loading_before).as_secs_f64(),
        decoding: engine.decoding.as_secs_f64(),
        encoding: engine.b.encoding.as_secs_f64(),
        witness: engine.witness.as_secs_f64(),
        solver: solver.clone(),
        gaps: gaps::records(&engine.met, jdk.as_deref(), Some(if engine.gap_mode.refuses() { GapTreatment::Refused } else { GapTreatment::Assumed })).into_iter().chain(gaps::contract_records(&engine.applied, &engine.contracts, jdk.as_deref())).collect(),
        gap_mode: engine.gap_mode,
        assumed: engine.assumed.iter().map(|a| a.to_string()).collect(),
        loops: engine.loops.iter().cloned().collect(),
        transcript: engine.b.transcript_path().map(std::path::Path::to_path_buf),
    };

    let result = 'search: {
        // The inputs: fresh bits per parameter, in its range; an array parameter is an object of a fresh length up to
        // the bound (the first path's condition) with fresh cells.
        let mut locals: Vec<Option<Val>> = Vec::new();
        let mut objects: Vec<Obj> = Vec::new();
        let mut cond: Vec<Lit> = Vec::new();
        let mut slot = 0u32;
        // Each array parameter's own array: slot, type and object.
        let mut own: Vec<(u32, Type, usize)> = Vec::new();
        let options_in = &options.parameters;
        for t in &descriptor.params {
            if let Some(why) = unsupported_parameter(t) {
                break 'search Ok(outcome(&engine, Verdict::Unverifiable, Input::default(), None, Some(format!("outside the fragment: {why}"))));
            }
            // An array, or a String (its code units, as an array of chars is): its own object, of every length up
            // to its bound.
            let held = match t {
                Type::Array(element) => Some(((**element).clone(), options.max_array_length, t.descriptor())),
                t if is_string(t) => match options_in.max_string_length {
                    Some(bound) => Some((Type::Char, bound, STRING.to_string())),
                    None => break 'search Ok(outcome(&engine, Verdict::Unverifiable, Input::default(), None, Some("outside the fragment: a java.lang.String parameter with no bound on its length (bmc::Parameters::max_string_length)".into()))),
                },
                _ => None,
            };
            if let Some((element, bound, class)) = held {
                let length = engine.b.fresh(32);
                let zero = engine.b.constant(0, 32);
                let most = engine.b.constant(i64::from(bound), 32);
                cond.push(engine.b.sle(&zero, &length));
                cond.push(engine.b.sle(&length, &most));
                if is_string(&element) {
                    // An array of Strings: each cell null or a String of its own, of every content up to the
                    // Strings' bound; no two cells one object.
                    let Some(units) = options_in.max_string_length else {
                        break 'search Ok(outcome(&engine, Verdict::Unverifiable, Input::default(), None, Some("outside the fragment: a java.lang.String[] parameter with no bound on its Strings' length (bmc::Parameters::max_string_length)".into())));
                    };
                    let most_units = engine.b.constant(i64::from(units), 32);
                    let mut refs = Vec::new();
                    let mut elements = Vec::new();
                    for _ in 0..bound {
                        let n = engine.b.fresh(32);
                        cond.push(engine.b.sle(&zero, &n));
                        cond.push(engine.b.sle(&n, &most_units));
                        let cells: Vec<Bits> = (0..units).map(|_| engine.b.fresh(16)).collect();
                        objects.push(Obj { array: Some(Array { element: Type::Char, length: n.clone(), cells: cells.clone(), refs: Vec::new() }), ..Obj::new(STRING) });
                        let null = engine.b.var();
                        refs.push(choice(&mut engine.b, vec![(null, None), (-null, Some(objects.len() - 1))]));
                        elements.push((null, n, cells));
                    }
                    engine.string_arrays.push((slot, length.clone(), elements));
                    objects.push(Obj { array: Some(Array { element, length, cells: Vec::new(), refs }), ..Obj::new(&class) });
                } else {
                    let cells: Vec<Bits> = (0..bound).map(|_| engine.b.fresh(cell_width(&element))).collect();
                    engine.arrays.push((slot, element.clone(), length.clone(), cells.clone()));
                    objects.push(Obj { array: Some(Array { element, length, cells, refs: Vec::new() }), ..Obj::new(&class) });
                }
                own.push((slot, t.clone(), objects.len() - 1));
                // Null, the own arrays of the parameters before it in its group of the same type, and its own,
                // one of them under exclusive guards that cover every input.
                let mut options: Vec<Option<u32>> = Vec::new();
                if options_in.nullable.contains(&slot) {
                    options.push(None);
                }
                if let Some(group) = options_in.may_alias.iter().find(|g| g.contains(&slot)) {
                    options.extend(own.iter().filter(|(s, ty, _)| *s != slot && ty == t && group.contains(s)).map(|(s, _, _)| Some(*s)));
                }
                options.push(Some(slot));
                let mut guarded = Vec::new();
                let mut none_before = TRUE;
                for (i, option) in options.iter().enumerate() {
                    let g = if i + 1 == options.len() {
                        none_before
                    } else {
                        let pick = engine.b.var();
                        let g = engine.b.and(none_before, pick);
                        none_before = engine.b.and(none_before, -pick);
                        g
                    };
                    guarded.push((g, *option));
                }
                let object_of = |s: Option<u32>| s.map(|s| own.iter().find(|(o, _, _)| *o == s).expect("an own array").2);
                let value = choice(&mut engine.b, guarded.iter().map(|(g, s)| (*g, object_of(*s))).collect());
                if guarded.len() > 1 {
                    engine.choices.push((slot, guarded));
                }
                locals.push(Some(value));
                slot += 1;
                continue;
            }
            let bits = match t {
                Type::Boolean => {
                    let mut v = vec![FALSE; 32];
                    v[0] = engine.b.var();
                    v
                }
                Type::Byte => {
                    let small = engine.b.fresh(8);
                    engine.b.sext(&small, 32)
                }
                Type::Char => {
                    let small = engine.b.fresh(16);
                    engine.b.zext(&small, 32)
                }
                Type::Short => {
                    let small = engine.b.fresh(16);
                    engine.b.sext(&small, 32)
                }
                Type::Int => engine.b.fresh(32),
                Type::Long => engine.b.fresh(64),
                _ => unreachable!(),
            };
            engine.params.push((slot, t.clone(), bits.clone()));
            locals.push(Some(if *t == Type::Long { Val::J(bits) } else { Val::I(bits) }));
            if *t == Type::Long {
                locals.push(None);
            }
            slot += u32::from(t.slots());
        }
        let code = engine.code(&harness, &m.name, &m.descriptor).map_err(|e| Error::new(stop_text(&e)))?;
        locals.resize(code.max_locals.max(locals.len()), None);
        let first = Path { frames: vec![Frame::new(harness.clone(), m.name.clone(), code, locals)], cond, models: vec![Model::default()], undecided: false, resumed: false, objects, literals: BTreeMap::new(), classes: BTreeMap::new(), statics: BTreeMap::new(), probing: None, loose: false };
        engine.pending.push(first);

        // The smallest violating input so far, by stage: a path that only has one outside the stages does not end the
        // search, since another path may have one in the first stage, as it does when the first path to fail is an
        // overflow and the second a rounding. The search for a better one is given as much work again as the first
        // took (`witness_budget`), within the deadline; the violation stands whatever the remaining paths do.
        let mut best: Option<(usize, Input)> = None;
        let violation = |engine: &Engine, best: Option<(usize, Input)>| {
            let (stage, input) = best.expect("a violation");
            let stage = STAGES.get(stage).map(|(lo, hi)| format!("[{lo}:{hi}]"));
            outcome(engine, Verdict::Violation, input, stage, None)
        };
        loop {
            if let Some((paths, work)) = engine.witness_budget {
                if engine.paths >= paths || engine.b.work() >= work {
                    break 'search Ok(violation(&engine, best));
                }
            }
            let path = match engine.next_path() {
                Ok(Some(path)) => path,
                Ok(None) => break,
                Err(stop) => break 'search Ok(if best.is_some() { violation(&engine, best) } else { outcome(&engine, Verdict::Unverifiable, Input::default(), None, Some(stop_text(&stop))) }),
            };
            if engine.paths > engine.max_paths {
                break 'search Ok(if best.is_some() { violation(&engine, best) } else { outcome(&engine, Verdict::Unverifiable, Input::default(), None, Some(format!("more than {} paths; the budget is spent", engine.max_paths))) });
            }
            match engine.run(path) {
                Ok(End::Returned) | Ok(End::Infeasible) | Ok(End::Parked) | Ok(End::Gap) | Ok(End::Back(..)) | Ok(End::Left) => {}
                Ok(End::Violation(cond)) => {
                    let (stage, input) = match engine.staged_input(&cond) {
                        Ok(found) => found,
                        Err(stop) if best.is_some() => {
                            let _ = stop;
                            break 'search Ok(violation(&engine, best));
                        }
                        Err(stop) => break 'search Ok(outcome(&engine, Verdict::Unverifiable, Input::default(), None, Some(stop_text(&stop)))),
                    };
                    if best.as_ref().is_none_or(|(s, _)| stage < *s) {
                        if best.is_none() {
                            if engine.b.set_work_limit(None) {
                                let (paths, work) = (engine.paths, engine.b.work());
                                engine.witness_budget = Some((paths + paths.max(WITNESS_PATHS), work + work.max(PROBE_CONFLICTS)));
                            } else {
                                // A solver with no conflict limit is given as long again as the first took, at least a second.
                                let elapsed = started.elapsed();
                                engine.deadline = engine.deadline.min(Instant::now() + elapsed.max(Duration::from_secs(1)));
                            }
                        }
                        best = Some((stage, input));
                    }
                    if stage == 0 {
                        break 'search Ok(violation(&engine, best));
                    }
                }
                Ok(End::Unwound(what)) => {
                    break 'search Ok(if best.is_some() { violation(&engine, best) } else { outcome(&engine, Verdict::Unverifiable, Input::default(), None, Some(format!("a loop was not fully unwound with --unwind {} ({what})", options.unwind))) })
                }
                Err(Stop::Unsupported(what)) => {
                    break 'search Ok(if best.is_some() { violation(&engine, best) } else { outcome(&engine, Verdict::Unverifiable, Input::default(), None, Some(format!("outside the fragment: {what}"))) })
                }
                Err(Stop::Budget(what)) => break 'search Ok(if best.is_some() { violation(&engine, best) } else { outcome(&engine, Verdict::Unverifiable, Input::default(), None, Some(what)) }),
            }
        }
        if best.is_some() {
            break 'search Ok(violation(&engine, best));
        }
        if !engine.met.is_empty() && (engine.gap_mode.refuses() || engine.met.keys().any(|g| !g.kind.assumable())) {
            let refused: BTreeMap<Gap, std::collections::BTreeSet<Site>> = engine.met.iter().filter(|(g, _)| engine.gap_mode.refuses() || !g.kind.assumable()).map(|(g, s)| (g.clone(), s.clone())).collect();
            let problem = refused_gaps(&gaps::records(&refused, jdk.as_deref(), None), engine.gap_mode);
            break 'search Ok(outcome(&engine, Verdict::Unverifiable, Input::default(), None, Some(problem)));
        }
        Ok(outcome(&engine, Verdict::Verified, Input::default(), None, None))
    };
    // The transcript ends with how the run ended; one that could not be written fails the run, which was asked for it.
    let mut result = result;
    if let Ok(out) = &mut result {
        let last = format!("{:?}{}", out.verdict, out.problem.as_deref().map(|p| format!(": {p}")).unwrap_or_default());
        if let Some(written) = engine.b.finish_transcript(&last.replace('\n', " ")) {
            let path = out.transcript.clone().unwrap_or_default();
            written.map_err(|e| Error::new(format!("cannot write the transcript {}: {e}", path.display())))?;
        }
    }
    result
}

/// Why a run that refused gaps has no verdict: each gap by its id, with the call and where.
pub fn refused_gaps(gaps: &[GapRecord], mode: GapMode) -> String {
    let n = gaps.len();
    let list = gaps.iter().map(|g| format!("{} ({} at {})", g.id, g.call, g.sites.join(", "))).collect::<Vec<_>>().join("; ");
    let assumable: Vec<&GapRecord> = gaps.iter().filter(|g| g.kind.assumable()).collect();
    let after = if assumable.is_empty() {
        if n == 1 { "It has no approximation under --gaps assume, since its value could only be made up: only a contract closes it (--gaps advised)".to_string() } else { "They have no approximation under --gaps assume, since their values could only be made up: only contracts close them (--gaps advised)".to_string() }
    } else {
        let instead = match (gaps, assumable.as_slice()) {
            ([_], [g]) => format!("that {} {}", g.call, g.approximation),
            _ => "what each gap's approximation states".to_string(),
        };
        let rest = if assumable.len() < n { ", except where a gap has no approximation" } else { "" };
        format!("With --gaps assume it assumes instead {instead}, and the verdict names the assumption{rest}")
    };
    format!("the tool's own checker met {n} gap{s}, a construct it does not implement as the JVM does, and refused {it} (--gaps {mode}): {list}. {after}", s = if n == 1 { "" } else { "s" }, it = if n == 1 { "it" } else { "them" }, mode = mode.name())
}

/// The SAT solver checks run on by default, by name and version: `CaDiCaL 1.9.5 (bundled)`, unless the environment
/// variable [`sat::ENV`] chooses another.
pub fn solver_signature() -> String {
    match sat::configuration() {
        Ok(make) => make().signature(),
        Err(e) => format!("none: {}", e.0),
    }
}

/// Runs the engine on a harness for the proof drivers: the class path is the harness, the application classes
/// and their class path (not the JDK classes extracted for JBMC: a JDK method is modelled here, never run), with
/// the tool's models; the result is in JBMC's shape, and a line goes to `work/bmc.log`.
#[allow(clippy::too_many_arguments)] // the settings a proof driver passes on
#[allow(clippy::too_many_arguments)]
pub fn run_for_proof(entries: &[std::path::PathBuf], models: bool, class: &str, method: &str, unwind: u32, max_array_length: u32, timeout: Duration, gaps: &GapSetting, parameters: &Parameters, work: &std::path::Path) -> Result<crate::jbmc::JbmcResult, Error> {
    run_for_proof_with(entries, models, class, method, unwind, max_array_length, timeout, gaps, parameters, &[], None, false, work)
}

/// [`run_for_proof`] with the calls checked summaries stand in for (`summaries`), and the method the check proves a
/// summary of, or proves by induction (`pure`; `own_induction` says which, [`Options::own_induction`]).
#[allow(clippy::too_many_arguments)]
pub fn run_for_proof_with(entries: &[std::path::PathBuf], models: bool, class: &str, method: &str, unwind: u32, max_array_length: u32, timeout: Duration, gaps: &GapSetting, parameters: &Parameters, summaries: &[Summary], pure: Option<(String, String, String)>, own_induction: bool, work: &std::path::Path) -> Result<crate::jbmc::JbmcResult, Error> {
    let cp = crate::witness::classpath(entries.iter().chain(&gaps.class_dir).map(std::path::PathBuf::as_path))?.with_models(models);
    let outcome = check(&cp, class, method, &Options { unwind, timeout, max_array_length, gaps: gaps.mode, contracts: gaps.contracts.clone(), observed: gaps.observed.clone(), models: gaps.models.clone(), previous: gaps.previous.clone(), parameters: parameters.clone(), summaries: std::sync::Arc::new(summaries.to_vec()), pure, own_induction, ..Options::default() })?;
    let log = work.join("bmc.log");
    let _ = std::fs::write(&log, format!("jvmcontract's own checker on {class}.{method}\n{}\n", outcome.summary()));
    Ok(outcome.into_jbmc_result(log))
}

/// Where a frame is: its method and the source line of its instruction.
fn site(frame: &Frame) -> Site {
    Site { class: frame.class.name.clone(), method: frame.method.clone(), line: frame.code.lines[frame.at] }
}

fn stop_text(stop: &Stop) -> String {
    match stop {
        Stop::Unsupported(s) | Stop::Budget(s) => s.clone(),
    }
}

impl ClassFile {
    /// The one method of this name (the harness has one `check`).
    fn method_by_name(&self, name: &str) -> Option<&crate::classfile::Method> {
        self.methods.iter().find(|m| m.name == name)
    }
}

impl<'a> Engine<'a> {
    fn code(&mut self, class: &Rc<ClassFile>, name: &str, descriptor: &str) -> Result<Rc<Decoded>, Stop> {
        let key = (class.name.clone(), name.to_string(), descriptor.to_string());
        if let Some(c) = self.codes.get(&key) {
            return Ok(c.clone());
        }
        let started = Instant::now();
        let compiled = self.decode(class, name, descriptor);
        self.decoding += started.elapsed();
        let compiled = compiled?;
        self.codes.insert(key, compiled.clone());
        Ok(compiled)
    }

    /// [`Engine::code`] for a method not decoded yet.
    fn decode(&mut self, class: &Rc<ClassFile>, name: &str, descriptor: &str) -> Result<Rc<Decoded>, Stop> {
        let method = class.method(name, descriptor).ok_or_else(|| Stop::Unsupported(format!("no method {}.{name}{descriptor}", class.name)))?;
        if method.is_native() {
            return unsupported(format!("{}.{name} is native", class.name.replace('/', ".")));
        }
        let code = method.code.as_ref().ok_or_else(|| Stop::Unsupported(format!("{}.{name} has no code", class.name.replace('/', "."))))?;
        let decoded = code.instructions().map_err(|e| Stop::Unsupported(e.to_string()))?;
        let mut index = HashMap::with_capacity(decoded.len());
        let mut insns = Vec::with_capacity(decoded.len());
        let mut pcs = Vec::with_capacity(decoded.len());
        for (i, (pc, insn)) in decoded.into_iter().enumerate() {
            index.insert(pc, i);
            insns.push(insn);
            pcs.push(pc);
        }
        // A join is an instruction with more than one way in: the fall-through from the one before it, a branch
        // to it, or, for a handler, any instruction its range covers.
        let mut ways_in = vec![0u32; insns.len()];
        ways_in[0] += 1;
        for (i, insn) in insns.iter().enumerate() {
            let falls_through = !matches!(insn, Insn::Goto(_) | Insn::Jsr(_) | Insn::Ret(_) | Insn::TableSwitch { .. } | Insn::LookupSwitch { .. } | Insn::Return(_) | Insn::AThrow);
            if falls_through && i + 1 < insns.len() {
                ways_in[i + 1] += 1;
            }
            for target in insn.targets() {
                if let Some(&j) = index.get(&target) {
                    ways_in[j] += 1;
                }
            }
        }
        for h in &code.exception_table {
            if let Some(&j) = index.get(&u32::from(h.handler_pc)) {
                ways_in[j] += 2;
            }
        }
        let joins: Vec<bool> = ways_in.iter().map(|&n| n >= 2).collect();
        let mut loops: BTreeMap<u32, u32> = BTreeMap::new();
        for (i, insn) in insns.iter().enumerate() {
            for target in insn.targets().into_iter().filter(|t| *t <= pcs[i]) {
                let last = loops.entry(target).or_insert(pcs[i]);
                *last = (*last).max(pcs[i]);
            }
        }
        let loops: Vec<(u32, u32)> = loops.into_iter().collect();
        // Where a loop is left is a join too once the paths are many ([`Options::merge_heaps_after`]): one way in,
        // but a path arrives from each iteration that leaves.
        let mut exits = vec![false; insns.len()];
        for (i, insn) in insns.iter().enumerate() {
            let falls_through = !matches!(insn, Insn::Goto(_) | Insn::Jsr(_) | Insn::Ret(_) | Insn::TableSwitch { .. } | Insn::LookupSwitch { .. } | Insn::Return(_) | Insn::AThrow);
            let mut after: Vec<usize> = insn.targets().into_iter().filter_map(|t| index.get(&t).copied()).collect();
            if falls_through && i + 1 < insns.len() {
                after.push(i + 1);
            }
            for j in after {
                if loops.iter().any(|(head, last)| (*head..=*last).contains(&pcs[i]) && !(*head..=*last).contains(&pcs[j])) {
                    exits[j] = true;
                }
            }
        }
        // Liveness, backwards to a fixed point: live before = read here, or live after and not written here.
        let slots = code.max_locals as usize;
        let handlers: Vec<(usize, usize, usize)> = code.exception_table.iter().filter_map(|h| Some((*index.get(&u32::from(h.start_pc))?, index.get(&u32::from(h.end_pc)).copied().unwrap_or(insns.len()), *index.get(&u32::from(h.handler_pc))?))).collect();
        let mut live = vec![vec![false; slots]; insns.len()];
        let mut changed = true;
        while changed {
            changed = false;
            for i in (0..insns.len()).rev() {
                let insn = &insns[i];
                let mut now = vec![false; slots];
                let falls_through = !matches!(insn, Insn::Goto(_) | Insn::Jsr(_) | Insn::Ret(_) | Insn::TableSwitch { .. } | Insn::LookupSwitch { .. } | Insn::Return(_) | Insn::AThrow);
                let mut after: Vec<usize> = insn.targets().into_iter().filter_map(|t| index.get(&t).copied()).collect();
                if falls_through && i + 1 < insns.len() {
                    after.push(i + 1);
                }
                for j in after {
                    for (s, l) in live[j].iter().enumerate() {
                        now[s] |= *l;
                    }
                }
                match insn {
                    Insn::Store(_, s) => {
                        if let Some(l) = now.get_mut(usize::from(*s)) {
                            *l = false;
                        }
                    }
                    Insn::Load(_, s) | Insn::IInc(s, _) | Insn::Ret(s) => {
                        if let Some(l) = now.get_mut(usize::from(*s)) {
                            *l = true;
                        }
                    }
                    // jsr/ret are refused where they run; until then every local is taken to be live.
                    Insn::Jsr(_) => now.iter_mut().for_each(|l| *l = true),
                    _ => {}
                }
                // What a handler reads is live at every instruction it covers, whatever that one writes.
                for (start, end, handler) in &handlers {
                    if (*start..*end).contains(&i) {
                        for (s, l) in live[*handler].clone().iter().enumerate() {
                            now[s] |= *l;
                        }
                    }
                }
                if now != live[i] {
                    live[i] = now;
                    changed = true;
                }
            }
        }
        let lines = pcs.iter().map(|&pc| code.line_at(pc)).collect();
        Ok(Rc::new(Decoded { insns, pcs, index, handlers: code.exception_table.clone(), max_locals: code.max_locals as usize, lines, joins, exits, live, loops }))
    }

    /// Whether the paths are many enough to be merged eagerly ([`Options::merge_heaps_after`]): heaps of two shapes
    /// made one, a path rid of the locals no instruction reads again and of the objects it no longer reaches, and a
    /// loop's exit a join, the paths resumed in the order of the loops they are in. Before that the engine merges
    /// what is of one shape where two ways in meet, and nothing else.
    fn eager(&self) -> bool {
        self.paths > self.merge_heaps_after
    }

    /// Runs one path to its end, or, once `Options::merge_after` paths have been explored, to a join point, where
    /// it waits (`End::Parked`) for the paths that arrive after it to be merged with it; twins of it go to `pending`.
    fn run(&mut self, mut path: Path) -> Result<End, Stop> {
        let mut steps: u64 = 0;
        loop {
            if path.probing.as_ref().is_some_and(|probe| probe.left(&path)) {
                return Ok(End::Left);
            }
            if !path.resumed && self.paths > self.merge_after {
                let frame = path.frames.last().expect("a frame");
                let eager = self.eager();
                if frame.code.joins[frame.at] || (eager && frame.code.exits[frame.at]) {
                    if eager {
                        path.frames.iter_mut().for_each(Frame::forget_dead);
                    }
                    self.waiting.entry(join_key(&path, eager)).or_default().push(path);
                    return Ok(End::Parked);
                }
            }
            path.resumed = false;
            if self.summarize_at_entry(&mut path)? {
                continue;
            }
            steps += 1;
            if steps % 256 == 0 && Instant::now() > self.deadline {
                return Err(Stop::Budget("the engine did not finish within the time limit".into()));
            }
            match self.step(&mut path)? {
                Some(End::Back(head, _)) if path.probing.as_ref().is_some_and(|probe| probe.is(path.frames.len(), head)) => return Ok(End::Back(head, Some(Box::new(path)))),
                Some(end) => return Ok(end),
                None => {}
            }
        }
    }

    /// Which sides of a branch on `c` are feasible on the path. A condition the path has already taken (the
    /// same comparison of the same values, which the gate hashing makes the same literal: a loop bound both
    /// versions test) is decided without the solver; otherwise a side one of the path's models takes is feasible,
    /// and the solver is asked once, about a side no model takes.
    fn sides(&mut self, path: &mut Path, c: Lit) -> Result<Sides, Stop> {
        if c == TRUE || path.cond.contains(&c) {
            return Ok(Sides::Then);
        }
        if c == FALSE || path.cond.contains(&-c) {
            return Ok(Sides::Else);
        }
        let (mut then_models, mut else_models): (Vec<Model>, Vec<Model>) = (Vec::new(), Vec::new());
        for mut model in path.models.drain(..) {
            if self.b.holds(&mut model, c) {
                then_models.push(model);
            } else {
                else_models.push(model);
            }
        }
        if !then_models.is_empty() && !else_models.is_empty() {
            return Ok(Sides::Both { then_models, else_models });
        }
        let model_takes_then = !then_models.is_empty();
        let mut assumptions = path.cond.clone();
        assumptions.push(if model_takes_then { -c } else { c });
        let answer = self.probe(&assumptions);
        if let Ok(Some(true)) = answer {
            if model_takes_then {
                else_models.push(self.b.snapshot());
            } else {
                then_models.push(self.b.snapshot());
            }
            return Ok(Sides::Both { then_models, else_models });
        }
        // The path keeps its models, which all take one side.
        path.models = if model_takes_then { then_models } else { else_models };
        match answer? {
            None => Ok(Sides::Undecided { model_takes_then }),
            Some(false) if model_takes_then => Ok(Sides::Then),
            _ => Ok(Sides::Else),
        }
    }

    /// Splits the path on `c` when both sides are feasible: the twin returned takes the then side when
    /// `twin_takes_then`, else the else side, and the path the other; each keeps the models of its side.
    fn split(&self, path: &mut Path, c: Lit, then_models: Vec<Model>, else_models: Vec<Model>, twin_takes_then: bool) -> Path {
        let mut twin = path.clone();
        twin.resumed = false;
        if twin_takes_then {
            twin.models = then_models;
            path.models = else_models;
        } else {
            twin.models = else_models;
            path.models = then_models;
        }
        twin.cond.push(if twin_takes_then { c } else { -c });
        path.cond.push(if twin_takes_then { -c } else { c });
        twin
    }

    /// Splits the path on `c` when the side its models do not take is undecided: the path goes on with its
    /// side, and the twin returned takes the other, undecided, with the path's models (see `Path::undecided`).
    fn split_undecided(&self, path: &mut Path, c: Lit, model_takes_then: bool) -> Path {
        let mut twin = path.clone();
        twin.resumed = false;
        twin.undecided = true;
        twin.cond.push(if model_takes_then { -c } else { c });
        path.cond.push(if model_takes_then { c } else { -c });
        twin
    }

    /// Decides an undecided twin now, with all the time left, where it cannot wait: `None` when it is infeasible.
    fn settle(&mut self, mut twin: Path) -> Result<Option<Path>, Stop> {
        if !self.solve(&twin.cond)? {
            return Ok(None);
        }
        twin.models = vec![self.b.snapshot()];
        twin.undecided = false;
        Ok(Some(twin))
    }

    /// The literal of stage `i`: every parameter within its range (a boolean is in every range).
    fn stage_literal(&mut self, i: usize) -> Lit {
        if let Some(l) = self.stage_lits[i] {
            return l;
        }
        let (lo, hi) = STAGES[i];
        let mut lits = Vec::new();
        let mut values: Vec<(Type, Bits)> = self.params.iter().map(|(_, t, bits)| (t.clone(), bits.clone())).collect();
        for (_, element, _, cells) in &self.arrays {
            values.extend(cells.iter().map(|c| (element.clone(), self.b.extend_cell(element, c))));
        }
        for (_, _, elements) in &self.string_arrays {
            for (_, _, cells) in elements {
                values.extend(cells.iter().map(|c| (Type::Char, self.b.extend_cell(&Type::Char, c))));
            }
        }
        for (t, bits) in values {
            if t == Type::Boolean {
                continue;
            }
            let width = bits.len();
            let low = self.b.constant(lo, width);
            let high = self.b.constant(hi, width);
            let above = self.b.sle(&low, &bits);
            let below = self.b.sle(&bits, &high);
            lits.push(self.b.and(above, below));
        }
        let l = self.b.all(&lits);
        self.stage_lits[i] = Some(l);
        l
    }

    /// An input that takes the violating path of condition `cond`, from the first stage of [`STAGES`] that has
    /// one, or from the whole range (stage `STAGES.len()`) when none does.
    fn staged_input(&mut self, cond: &[Lit]) -> Result<(usize, Input), Stop> {
        // Its solving and encoding are counted as such; the rest is reading the witness.
        let (started, solving, encoding) = (Instant::now(), self.b.solving, self.b.encoding);
        let found = self.staged_input_solved(cond);
        let elsewhere = (self.b.solving - solving) + (self.b.encoding - encoding);
        self.witness += started.elapsed().saturating_sub(elsewhere);
        found
    }

    fn staged_input_solved(&mut self, cond: &[Lit]) -> Result<(usize, Input), Stop> {
        let mut assumptions = cond.to_vec();
        for i in 0..STAGES.len() {
            let l = self.stage_literal(i);
            assumptions.push(l);
            if self.solve(&assumptions)? {
                self.least(&mut assumptions)?;
                return Ok((i, self.input()));
            }
            assumptions.pop();
        }
        if !self.solve(cond)? {
            return Err(Stop::Budget("the solver changed its mind about a violating path".into()));
        }
        let mut assumptions = cond.to_vec();
        self.least(&mut assumptions)?;
        Ok((STAGES.len(), self.input()))
    }

    /// In a run that covered a loop by an invariant ([`loops`]), makes the solver's model of `assumptions` the
    /// least violating input there is under them: the scalar parameters, then each array's length and, of a
    /// String, its code units, each in turn the least it can be with the ones before it as they are (a number not
    /// negative where it can be, a String the first in dictionary order). A witness of such a run is run on the
    /// method before it is believed, every iteration of the loop with it, and what a program takes its counts
    /// from (a cost, a length, the digits of one) is fewest where its input is least. One question to the solver
    /// for each bit that is set, up to [`LEAST_QUESTIONS`] and for at most half the time the run has left when the
    /// violation is found: a descent that runs out of either leaves the bits it has not asked about as the model
    /// has them, and the violation stands (before, the time limit passing in the descent lost it: example 287's
    /// byte guard on 6.3.7, whose violating path is found after four minutes and asks some 300 questions of a
    /// formula of millions of variables, 0.2 s each). The model the solver is left with is the input.
    fn least(&mut self, assumptions: &mut Vec<Lit>) -> Result<(), Stop> {
        if self.loops.is_empty() {
            return Ok(());
        }
        let mut numbers: Vec<Bits> = self.params.iter().map(|(_, _, bits)| bits.clone()).collect();
        let arrays: Vec<(Type, Bits, Vec<Bits>)> = self.arrays.iter().map(|(_, element, length, cells)| (element.clone(), length.clone(), cells.clone())).collect();
        let (mut asked, mut holds) = (0, true);
        let mut next = arrays.into_iter();
        // Half the time the run has left is the descent's: the violation is found already, and stands without it.
        let until = {
            let now = Instant::now();
            now + self.deadline.saturating_duration_since(now) / 2
        };
        loop {
            for bits in std::mem::take(&mut numbers) {
                // From the sign or the highest bit down; a bit the model has clear stays clear.
                let mut model: Vec<bool> = bits.iter().map(|&bit| self.b.value(bit)).collect();
                for k in (0..bits.len()).rev() {
                    let bit = bits[k];
                    if bit == TRUE || bit == FALSE {
                        continue;
                    }
                    if !model[k] {
                        assumptions.push(-bit);
                        continue;
                    }
                    if asked == LEAST_QUESTIONS {
                        assumptions.push(bit);
                        continue;
                    }
                    asked += 1;
                    assumptions.push(-bit);
                    let answer = if self.witness_budget.is_some() { Some(self.solve(assumptions)?) } else { self.solve_until(assumptions, until, None)? };
                    holds = answer == Some(true);
                    if holds {
                        model = bits.iter().map(|&bit| self.b.value(bit)).collect();
                    } else {
                        assumptions.pop();
                        assumptions.push(bit);
                    }
                    if answer.is_none() {
                        // Out of its time: every bit left stays as the last model has it.
                        asked = LEAST_QUESTIONS;
                    }
                }
                if !holds {
                    // The model the bits before were read from is the solver's again.
                    holds = self.solve(assumptions)?;
                    if !holds {
                        return Err(Stop::Budget("the solver changed its mind about a violating path".into()));
                    }
                }
            }
            let Some((element, length, cells)) = next.next() else { return Ok(()) };
            numbers.push(length.clone());
            if element == Type::Char {
                // Its units up to the length the model gives it, which is the least by now.
                let n = usize::try_from(self.b.eval(&length)).unwrap_or(0).min(cells.len());
                numbers.extend(cells[..n].iter().cloned());
            }
        }
    }

    /// The parameters' values in the solver's last model: an array's elements are its cells up to its length.
    fn input(&self) -> Input {
        let unsigned = |t: &Type, v: i64| match t {
            Type::Char => v & 0xFFFF,
            Type::Boolean => v & 1,
            _ => v,
        };
        let mut input = Input::default();
        for (slot, t, bits) in &self.params {
            input.scalars.insert(*slot, unsigned(t, self.b.eval(bits)).to_string());
        }
        let contents = |own: u32| -> Option<Vec<String>> {
            // A String[]'s cells, each as [`string_element`] spells it.
            if let Some((_, length, elements)) = self.string_arrays.iter().find(|(s, ..)| *s == own) {
                let n = usize::try_from(self.b.eval(length)).unwrap_or(0).min(elements.len());
                return Some(elements[..n].iter().map(|(null, units, cells)| {
                    let m = usize::try_from(self.b.eval(units)).unwrap_or(0).min(cells.len());
                    string_element((!self.b.value(*null)).then(|| cells[..m].iter().map(|c| (self.b.eval(c) & 0xFFFF) as u16).collect::<Vec<u16>>()).as_deref())
                }).collect());
            }
            let (_, element, length, cells) = self.arrays.iter().find(|(s, ..)| *s == own)?;
            let n = usize::try_from(self.b.eval(length)).unwrap_or(0).min(cells.len());
            Some(cells[..n].iter().map(|c| unsigned(element, self.b.eval(c)).to_string()).collect())
        };
        // Which array each parameter holds (its own, unless it is a choice), and the first parameter to hold each.
        let mut first: BTreeMap<u32, u32> = BTreeMap::new();
        let mut slots: Vec<u32> = self.arrays.iter().map(|(s, ..)| *s).chain(self.string_arrays.iter().map(|(s, ..)| *s)).collect();
        slots.sort_unstable();
        for slot in &slots {
            let held = match self.choices.iter().find(|(s, _)| s == slot) {
                Some((_, options)) => options.iter().find(|(g, _)| self.b.value(*g)).and_then(|(_, s)| *s),
                None => Some(*slot),
            };
            match held {
                None => {
                    input.arrays.insert(*slot, None);
                }
                Some(own) => {
                    input.arrays.insert(*slot, contents(own));
                    match first.get(&own) {
                        Some(&earlier) => {
                            input.same.insert(*slot, earlier);
                        }
                        None => {
                            first.insert(own, *slot);
                        }
                    }
                }
            }
        }
        input
    }

    /// Asks the solver, which is given the time left until the deadline, and during the search for a smaller witness
    /// after a violation the work left in [`Engine::witness_budget`]. A model is only taken when it is a real one:
    /// while the solver's choice for a division left to it is not the real division of the operands it chose, the
    /// circuit of that division is built and the solver asked again, so a `true` means an execution exists and
    /// its model (the parameters' values, the sides of later branches) is one.
    fn solve(&mut self, assumptions: &[Lit]) -> Result<bool, Stop> {
        let deadline = self.deadline;
        let Some((_, work)) = self.witness_budget else {
            return self.solve_until(assumptions, deadline, None)?.ok_or_else(|| Stop::Budget("the solver did not finish within the time limit".into()));
        };
        let spent = || Stop::Budget("the search for a smaller witness spent its work".into());
        let left = work.checked_sub(self.b.work()).filter(|&w| w > 0).ok_or_else(spent)?;
        let answer = self.solve_until(assumptions, deadline, Some(left));
        self.b.set_work_limit(None);
        answer?.ok_or_else(spent)
    }

    /// Asks the solver about the other side of a branch, for as much work as all the solver calls so far did
    /// together, at least [`PROBE_CONFLICTS`] conflicts: `None` when it did not answer, and the side is left
    /// undecided rather than waited for, since an infeasible side can be as hard to refute as the whole proof (that
    /// a value is not a multiple of another, say) while the violation on the feasible side is found at once, as JBMC
    /// finds it without ever deciding the side. What is undecided is decided once the decided paths are done, with
    /// all the time left, so a proof loses at most the probes' work.
    ///
    /// The budget is the solver's conflicts, not its time, so that which side is left undecided, and with it the
    /// order of the paths, is the same on every machine and every run (VF-010). Only the run's deadline is the
    /// clock's. A solver with no conflict limit ([`sat::Sat::set_work_limit`]) is given the time the calls so far
    /// took instead, at least a second.
    fn probe(&mut self, assumptions: &[Lit]) -> Result<Option<bool>, Stop> {
        let budget = self.b.work().max(PROBE_CONFLICTS);
        if self.b.set_work_limit(Some(budget)) {
            let answer = self.solve_until(assumptions, self.deadline, Some(budget));
            self.b.set_work_limit(None);
            return answer;
        }
        let budget = self.b.solving.max(Duration::from_secs(1));
        let until = self.deadline.min(Instant::now() + budget);
        self.solve_until(assumptions, until, None)
    }

    /// Asks the solver until it answers with a real model or no model, refining the operations a model gets wrong:
    /// `None` when it did not answer by `until`, or within `conflicts` conflicts over all its calls here (a call
    /// goes some way past its limit, as far on every run, before the solver looks at it).
    fn solve_until(&mut self, assumptions: &[Lit], until: Instant, conflicts: Option<u64>) -> Result<Option<bool>, Stop> {
        let started = self.b.work();
        loop {
            let now = Instant::now();
            if now > self.deadline {
                return Err(Stop::Budget("the engine did not finish within the time limit".into()));
            }
            if now > until {
                return Ok(None);
            }
            if let Some(conflicts) = conflicts {
                let spent = self.b.work() - started;
                if spent >= conflicts {
                    return Ok(None);
                }
                self.b.set_work_limit(Some(conflicts - spent));
            }
            self.b.set_timeout((until - now).as_secs_f32());
            let answered = self.b.solve_with(assumptions);
            match answered {
                None => return Ok(None),
                Some(false) => return Ok(false).map(Some),
                // A model that gives one function of equal operands two values is ruled out by a lemma first, so a
                // proof that two versions compute one remainder differently builds no divider.
                // Only of the operations the assumptions depend on: any other decides nothing of them.
                Some(true) => {
                    let among = self.b.operations_under(assumptions);
                    match (self.b.inconsistent_pair(&among), self.b.wrong_operation(&among)) {
                        (Some((i, j, swapped)), _) => self.b.add_congruence(i, j, swapped),
                        (None, None) => return Ok(Some(true)),
                        (None, Some(i)) => self.b.refine_operation(i),
                    }
                }
            }
        }
    }

    /// The next path to run: a decided one from `pending`; when there is none, the group waiting at the earliest
    /// join point, merged; when nothing waits, a deferred one the solver now decides with all the time left (an
    /// infeasible one is dropped). `None` when every path is done.
    fn next_path(&mut self) -> Result<Option<Path>, Stop> {
        loop {
            if let Some(path) = self.pending.pop() {
                if path.undecided {
                    self.deferred.push(path);
                    continue;
                }
                if !path.resumed {
                    self.paths += 1;
                }
                return Ok(Some(path));
            }
            if let Some(key) = self.waiting.keys().next().cloned() {
                let group = self.waiting.remove(&key).expect("a group");
                let mut merged = self.merge(group);
                let first = merged.pop().expect("a path");
                self.pending.extend(merged);
                return Ok(Some(first));
            }
            let Some(mut path) = self.deferred.pop() else {
                return Ok(None);
            };
            if self.solve(&path.cond)? {
                path.models = vec![self.b.snapshot()];
                path.undecided = false;
                self.paths += 1;
                return Ok(Some(path));
            }
        }
    }

    /// Merges the paths waiting at one join point into as few as have one shape ([`same_shape`]): each path
    /// absorbed into another makes every value they differ in a choice by the absorbed path's condition, and the
    /// condition of the merged path the disjunction of theirs. The paths through an `if` are one path after it,
    /// and the paths through a loop body one path at the header, so that a method of `n` independent branches is
    /// explored in `n` paths and not `2^n`. The merged path keeps the models of both, which take it; its
    /// condition is the common prefix of the two, then the literals both took after it, then one literal for
    /// either rest.
    fn merge(&mut self, mut group: Vec<Path>) -> Vec<Path> {
        // Paths that differ only in what they left behind are of one shape once that is gone: each loads the
        // literals any of them loaded (a literal's object is the same whenever it is first loaded), and keeps only
        // the objects its state still reaches, numbered in the order the state reaches them ([`collect`]).
        // Heaps of two shapes are merged only once the paths are many ([`Engine::eager`]).
        let heaps = self.eager();
        if group.len() > 1 {
            let literals: std::collections::BTreeSet<Literal> = group.iter().flat_map(|p| p.literals.keys().cloned()).collect();
            for path in &mut group {
                for literal in &literals {
                    let class = match literal {
                        Literal::Str(_) => STRING,
                        Literal::Class(_) => "java/lang/Class",
                        Literal::Loader => "java/lang/ClassLoader",
                        Literal::Logger(_) => "java/util/logging/Logger",
                        Literal::Charset(_) => bytes::CHARSET,
                        Literal::Locale(_) => locale::LOCALE,
                        Literal::Level(_) => runtime::LEVEL,
                        Literal::Thread => "java/lang/Thread",
                        Literal::EmptyMap => runtime::EMPTY_MAP,
                    };
                    self.literal(path, literal.clone(), class);
                }
                if heaps {
                    collect(path);
                }
            }
            self.initialise_alike(&mut group);
        }
        let mut merged: Vec<Path> = Vec::new();
        for mut path in group {
            path.resumed = true;
            if let Some(into) = merged.iter_mut().find(|m| same_shape(m, &path)) {
                self.absorb(into, &path);
                self.merges += 1;
                continue;
            }
            // Heaps of two shapes: one heap of both's objects ([`align`]), each path's state in its numbering.
            let Some((into, places)) = merged.iter_mut().find_map(|m| if heaps { align(m, &path).map(|places| (m, places)) } else { None }) else {
                merged.push(path);
                continue;
            };
            renumber(&mut path, &|o| places[o]);
            let total = places.iter().map(|p| p + 1).max().unwrap_or(0).max(into.objects.len());
            let mut theirs: Vec<Option<Obj>> = vec![None; total];
            for (obj, &place) in std::mem::take(&mut path.objects).into_iter().zip(&places) {
                theirs[place] = Some(obj);
            }
            for obj in &theirs[into.objects.len()..] {
                into.objects.push(obj.clone().expect("an object of the other path at every new place"));
            }
            // An object only one path has is itself on both sides: nothing of it is chosen.
            path.objects = theirs.into_iter().zip(&into.objects).map(|(obj, own)| obj.unwrap_or_else(|| own.clone())).collect();
            self.absorb(into, &path);
            self.merges += 1;
        }
        merged
    }

    /// Makes the paths of a join point alike in the classes whose initialization does nothing: a class with no
    /// `<clinit>` that one path has initialized is initialized on each other path whose state already holds what
    /// initializing it there would do, which is to initialize its superclass and the superinterfaces JVMS §5.5
    /// names, each of them initialized there already. Nothing a path can observe differs: the class has no
    /// initializer to run later, and the classes above it are in the state they would be in.
    fn initialise_alike(&mut self, group: &mut [Path]) {
        let done: std::collections::BTreeSet<String> = group.iter().flat_map(|p| p.classes.iter().filter(|(_, s)| matches!(s, ClassState::Done)).map(|(c, _)| c.clone())).collect();
        let mut quiet: Vec<(String, Rc<Vec<String>>)> = Vec::new();
        for class in done {
            if group.iter().all(|p| p.classes.contains_key(&class)) || self.cp.checker_class(&class).is_some_and(|cf| cf.method("<clinit>", "()V").is_some()) {
                continue;
            }
            let supers = match self.supers.get(&class) {
                Some(s) => s.clone(),
                None => {
                    let s = Rc::new(gaps::initialization_supers(self.cp, &class));
                    self.supers.insert(class.clone(), s.clone());
                    s
                }
            };
            quiet.push((class, supers));
        }
        for path in group.iter_mut() {
            // A class whose supers are among these too follows them: to a fixed point.
            loop {
                let before = path.classes.len();
                for (class, supers) in &quiet {
                    if !path.classes.contains_key(class) && supers.iter().all(|s| !self.cp.checker_statics(s) || matches!(path.classes.get(s), Some(ClassState::Done | ClassState::Assumed))) {
                        path.classes.insert(class.clone(), ClassState::Done);
                    }
                }
                if path.classes.len() == before {
                    break;
                }
            }
        }
    }

    fn absorb(&mut self, into: &mut Path, other: &Path) {
        into.loose |= other.loose;
        let prefix = into.cond.iter().zip(&other.cond).take_while(|(x, y)| x == y).count();
        let common: Vec<Lit> = into.cond[prefix..].iter().copied().filter(|l| other.cond[prefix..].contains(l)).collect();
        let rest_into: Vec<Lit> = into.cond[prefix..].iter().copied().filter(|l| !common.contains(l)).collect();
        let rest_other: Vec<Lit> = other.cond[prefix..].iter().copied().filter(|l| !common.contains(l)).collect();
        let takes_into = self.b.all(&rest_into);
        let takes_other = self.b.all(&rest_other);
        let either = self.b.or(takes_into, takes_other);
        into.cond.truncate(prefix);
        into.cond.extend(common);
        if either != TRUE {
            into.cond.push(either);
        }
        let choose = |b: &mut Blaster, x: &mut Val, y: &Val| {
            if let Some(v) = choose(b, takes_into, x, y) {
                *x = v;
            }
        };
        for (f, g) in into.frames.iter_mut().zip(&other.frames) {
            for (x, y) in f.locals.iter_mut().zip(&g.locals) {
                if let (Some(x), Some(y)) = (x, y) {
                    choose(&mut self.b, x, y);
                }
            }
            for (x, y) in f.stack.iter_mut().zip(&g.stack) {
                choose(&mut self.b, x, y);
            }
        }
        for (x, y) in into.statics.values_mut().zip(other.statics.values()) {
            choose(&mut self.b, x, y);
        }
        for (o, q) in into.objects.iter_mut().zip(&other.objects) {
            // An object that was there before a summarized method was entered, on either path.
            o.given |= q.given;
            for (name, x) in o.fields.iter_mut() {
                choose(&mut self.b, x, &q.fields[name]);
            }
            if o.same != q.same {
                // One guard per object it may be: this path's where it is taken, the other's elsewhere.
                let targets: std::collections::BTreeSet<usize> = o.same.iter().chain(&q.same).map(|(_, t)| *t).collect();
                let guard = |same: &[(Lit, usize)], t: usize| same.iter().find(|(_, u)| *u == t).map(|(g, _)| *g).unwrap_or(FALSE);
                let mut same: Vec<(Lit, usize)> = Vec::new();
                for t in targets {
                    let (mine, theirs) = (guard(&o.same, t), guard(&q.same, t));
                    let g = if mine == theirs { mine } else { self.b.ite(takes_into, mine, theirs) };
                    if g != FALSE {
                        same.push((g, t));
                    }
                }
                o.same = same;
            }
            o.unknown |= q.unknown;
            let unknown = o.unknown;
            if let (Some(x), Some(y)) = (&mut o.array, &q.array) {
                if x.length != y.length {
                    x.length = self.b.ite_bits(takes_into, &x.length, &y.length);
                }
                // Cells that hold any values on either path hold any on both.
                if unknown {
                    continue;
                }
                // A text's cells past the other's are its own where it is taken, and nothing's elsewhere.
                let blank = self.b.constant(0, 16);
                while x.cells.len() < y.cells.len() {
                    x.cells.push(blank.clone());
                }
                for (i, c) in x.cells.iter_mut().enumerate() {
                    let d = y.cells.get(i).unwrap_or(&blank);
                    if c != d {
                        *c = self.b.ite_bits(takes_into, c, d);
                    }
                }
                for (c, d) in x.refs.iter_mut().zip(&y.refs) {
                    choose(&mut self.b, c, d);
                }
            }
        }
        // The paths may be at different iterations of a loop (one left an earlier loop sooner); the merged path
        // counts the fewer, so that the iterations the other has left are not counted twice, which would report
        // the loop as beyond the bound when no path is. A path needing more than the bound is still stopped, at
        // most as many iterations later as the counts differed: nothing is cut short, only reported later.
        for (f, g) in into.frames.iter_mut().zip(&other.frames) {
            f.back_edges.retain(|head, taken| {
                *taken = (*taken).min(g.back_edges.get(head).copied().unwrap_or(0));
                *taken > 0
            });
        }
        into.models.extend(other.models.iter().take(MOST_MODELS.saturating_sub(into.models.len())).cloned());
    }

    /// Takes the branch on `c`: the path goes on with `c` and jumps to `then`, or with `¬c` and jumps to `else_`,
    /// or both, the twin for the else side joining `pending`. `None` if neither side is feasible.
    fn branch(&mut self, path: &mut Path, c: Lit, then: usize, else_: usize) -> Result<Option<End>, Stop> {
        match self.sides(path, c)? {
            Sides::Both { then_models, else_models } => {
                let mut twin = self.split(path, c, then_models, else_models, false);
                twin.frames.last_mut().expect("a frame").at = else_;
                self.pending.push(twin);
                path.frames.last_mut().expect("a frame").at = then;
            }
            Sides::Then => {
                path.cond.push(c);
                path.frames.last_mut().expect("a frame").at = then;
            }
            Sides::Else => {
                path.cond.push(-c);
                path.frames.last_mut().expect("a frame").at = else_;
            }
            Sides::Undecided { model_takes_then } => {
                let mut twin = self.split_undecided(path, c, model_takes_then);
                twin.frames.last_mut().expect("a frame").at = if model_takes_then { else_ } else { then };
                self.pending.push(twin);
                path.frames.last_mut().expect("a frame").at = if model_takes_then { then } else { else_ };
            }
        }
        Ok(None)
    }

    /// Splits the path on `c` where the then side throws `exception` and the else side pushes `value` and goes
    /// on: a division by zero, an overflow.
    fn branch_throw(&mut self, path: &mut Path, c: Lit, exception: &str, value: Val) -> Step {
        self.branch_throw_or(path, c, exception, move |engine, path| {
            engine.push(path, value);
            engine.advance(path);
        })
    }

    /// Splits the path on `c` where the then side throws `exception` and the else side does `go_on` (which moves
    /// past the instruction): an index out of bounds, a negative array size.
    /// Splits the path on `c`: where it holds, the path meets the gap `gap` (a call a model takes only part of the
    /// inputs of, which stays the JDK call it was on the rest) and ends there under strict, an object of the
    /// call's result type its value otherwise; where it doesn't, `go_on` runs. A side no input takes is not run.
    fn branch_gap_or(&mut self, path: &mut Path, c: Lit, gap: (GapKind, &str, &str, &str), go_on: impl FnOnce(&mut Self, &mut Path)) -> Step {
        let (kind, owner, name, descriptor) = gap;
        let met = |engine: &mut Self, path: &mut Path| -> Step {
            if let Some(end) = engine.meet(path, kind, owner, name, descriptor) {
                return Ok(Some(end));
            }
            match MethodDescriptor::parse(descriptor).map(|d| d.ret) {
                Ok(Type::Object(class)) => {
                    let r = engine.alloc(path, &class);
                    engine.push(path, Val::R(Some(r)));
                }
                Ok(Type::Void) => {}
                // A primitive the JDK computed has no approximation, as on any JDK call ([`JdkCall::Refused`]).
                _ => return unsupported(format!("{}.{name}{descriptor} beyond what the engine models of it", owner.replace('/', "."))),
            }
            engine.advance(path);
            Ok(None)
        };
        match self.sides(path, c)? {
            Sides::Both { then_models, else_models } => {
                let mut twin = self.split(path, c, then_models, else_models, false);
                go_on(self, &mut twin);
                self.pending.push(twin);
                met(self, path)
            }
            Sides::Then => {
                path.cond.push(c);
                met(self, path)
            }
            Sides::Else => {
                path.cond.push(-c);
                go_on(self, path);
                Ok(None)
            }
            Sides::Undecided { model_takes_then: true } => {
                let mut twin = self.split_undecided(path, c, true);
                go_on(self, &mut twin);
                self.pending.push(twin);
                met(self, path)
            }
            Sides::Undecided { model_takes_then: false } => {
                let twin = self.split_undecided(path, c, false);
                if let Some(mut twin) = self.settle(twin)? {
                    if met(self, &mut twin)?.is_none() {
                        self.pending.push(twin);
                    }
                }
                go_on(self, path);
                Ok(None)
            }
        }
    }

    fn branch_throw_or(&mut self, path: &mut Path, c: Lit, exception: &str, go_on: impl FnOnce(&mut Self, &mut Path)) -> Step {
        match self.sides(path, c)? {
            Sides::Both { then_models, else_models } => {
                let mut twin = self.split(path, c, then_models, else_models, false);
                go_on(self, &mut twin);
                self.pending.push(twin);
                self.raise(path, exception)
            }
            Sides::Then => {
                path.cond.push(c);
                self.raise(path, exception)
            }
            Sides::Else => {
                path.cond.push(-c);
                go_on(self, path);
                Ok(None)
            }
            Sides::Undecided { model_takes_then: true } => {
                let mut twin = self.split_undecided(path, c, true);
                go_on(self, &mut twin);
                self.pending.push(twin);
                self.raise(path, exception)
            }
            Sides::Undecided { model_takes_then: false } => {
                // The throwing side cannot wait undecided: whether the exception leaves the harness is judged as
                // it is thrown.
                let twin = self.split_undecided(path, c, false);
                if let Some(mut twin) = self.settle(twin)? {
                    self.raise(&mut twin, exception)?;
                    self.pending.push(twin);
                }
                go_on(self, path);
                Ok(None)
            }
        }
    }

    /// `arraylength`, `newarray`, and a load or store at an index: the index must be below the length (an int
    /// compared unsigned, so that a negative one is out of bounds too), else `ArrayIndexOutOfBoundsException`;
    /// a new array's size must not be negative, and must be known to be within the bound, since a cell is made
    /// per index.
    fn array_insn(&mut self, path: &mut Path, insn: &Insn) -> Step {
        match insn {
            Insn::ArrayLength => {
                if let Some(step) = self.concrete_ref(path, 0) {
                    return step;
                }
                let o = match self.pop_array(path) {
                    Ok(o) => o,
                    Err(step) => return step,
                };
                let length = path.objects[o].array.as_ref().expect("an array").length.clone();
                self.push(path, Val::I(length));
                self.advance(path);
                Ok(None)
            }
            Insn::ArrayLoad(ArrayKind::Ref) => {
                if let Some(step) = self.concrete_ref(path, 1) {
                    return step;
                }
                let index = self.pop_int(path)?;
                let o = match self.pop_array(path) {
                    Ok(o) => o,
                    Err(step) => return step,
                };
                if path.objects[o].given {
                    self.reads(path, || "reads an array that was there before the call".into())?;
                }
                let array = path.objects[o].array.clone().expect("an array");
                if !holds_references(&array.element) {
                    return unsupported(format!("an aaload from a {}[]", array.element.java_name()));
                }
                let value = match self.b.constant_value(&index) {
                    Some(k) => {
                        let Some(value) = usize::try_from(k).ok().and_then(|k| array.refs.get(k).cloned()) else {
                            // No cell there: out of bounds whatever the length.
                            return self.raise(path, "java/lang/ArrayIndexOutOfBoundsException");
                        };
                        value
                    }
                    // At a computed index, the reference is the one of the cell the index names: a choice among the
                    // cells' references, each under `index == i` (and under its own guard, where the cell holds a
                    // choice). In bounds one of them holds, since the array's length is at most its cells.
                    None => {
                        let mut options = Vec::new();
                        for (i, cell) in array.refs.iter().enumerate() {
                            let k = self.b.constant(i as i64, 32);
                            let here = self.b.eq(&index, &k);
                            for (g, t) in cell.options().expect("a cell of references") {
                                options.push((self.b.and(here, g), t));
                            }
                        }
                        choice(&mut self.b, options)
                    }
                };
                let in_bounds = self.b.ult(&index, &array.length);
                self.branch_throw(path, -in_bounds, "java/lang/ArrayIndexOutOfBoundsException", value)
            }
            Insn::ArrayStore(ArrayKind::Ref) => {
                // A symbolic value is stored as it is, as `putfield` stores one, when every object it may be is of
                // the element type; otherwise the path is split per object, so that the one that isn't throws.
                if let Some(step) = self.concrete_ref(path, 2) {
                    return step;
                }
                if let Some(Val::R(Some(o))) = path.frames.last().and_then(|f| f.stack.len().checked_sub(3).map(|i| f.stack[i].clone())) {
                    self.keeps(path, Some(o), "stores into an array made before it was called")?;
                }
                if !self.stores_without_check(path) {
                    if let Some(step) = self.concrete_ref(path, 0) {
                        return step;
                    }
                }
                if let Some(step) = self.concrete_index(path, 1) {
                    return step;
                }
                let value = self.pop(path)?;
                if value.options().is_none() {
                    return unsupported(format!("an aastore of {value:?}, not a reference"));
                }
                let index = self.pop_int(path)?;
                let o = match self.pop_array(path) {
                    Ok(o) => o,
                    Err(step) => return step,
                };
                let array = path.objects[o].array.as_ref().expect("an array");
                if !holds_references(&array.element) {
                    return unsupported(format!("an aastore into a {}[]", array.element.java_name()));
                }
                let Some(cell) = self.b.constant_value(&index).and_then(|k| usize::try_from(k).ok()).filter(|&k| k < array.refs.len()) else {
                    return self.raise(path, "java/lang/ArrayIndexOutOfBoundsException");
                };
                if let Val::R(Some(v)) = value {
                    if !self.cp.is_subtype(&path.objects[v].class, &class_of(&array.element)) {
                        return unsupported(format!("an aastore of a {} into a {}[] (ArrayStoreException)", path.objects[v].class.replace('/', "."), array.element.java_name()));
                    }
                }
                let in_bounds = self.b.ult(&index, &array.length);
                self.branch_throw_or(path, -in_bounds, "java/lang/ArrayIndexOutOfBoundsException", move |engine, path| {
                    path.objects[o].array.as_mut().expect("an array").refs[cell] = value;
                    engine.advance(path);
                })
            }
            Insn::ArrayLoad(kind) => {
                if let Some(step) = self.concrete_ref(path, 1) {
                    return step;
                }
                let index = self.pop_int(path)?;
                let o = match self.pop_array(path) {
                    Ok(o) => o,
                    Err(step) => return step,
                };
                if path.objects[o].given {
                    self.reads(path, || "reads an array that was there before the call".into())?;
                }
                let array = path.objects[o].array.clone().expect("an array");
                check_kind(*kind, &array.element)?;
                let width = cell_width(&array.element);
                self.index_used(path, o, &index);
                // Past a summarized loop a computed index into a large array is not followed ([`loops`]).
                let loose = path.objects[o].unknown || (path.loose && array.cells.len() > loops::LOOSE_CELLS && self.b.constant_value(&index).is_none());
                let mut value = if loose { self.b.fresh(width) } else { array.cells.last().cloned().unwrap_or_else(|| self.b.constant(0, width)) };
                for (i, cell) in array.cells.iter().enumerate().rev().skip(1) {
                    if loose {
                        break;
                    }
                    let here = self.b.constant(i as i64, 32);
                    let is = self.b.eq(&index, &here);
                    value = self.b.ite_bits(is, cell, &value);
                }
                let value = self.b.extend_cell(&array.element, &value);
                let value = if array.element == Type::Long { Val::J(value) } else { Val::I(value) };
                let in_bounds = self.b.ult(&index, &array.length);
                self.branch_throw(path, -in_bounds, "java/lang/ArrayIndexOutOfBoundsException", value)
            }
            Insn::ArrayStore(kind) => {
                if let Some(step) = self.concrete_ref(path, 2) {
                    return step;
                }
                if let Some(Val::R(Some(o))) = path.frames.last().and_then(|f| f.stack.len().checked_sub(3).map(|i| f.stack[i].clone())) {
                    self.keeps(path, Some(o), "stores into an array made before it was called")?;
                }
                let value = match self.pop(path)? {
                    Val::I(b) | Val::J(b) => b,
                    Val::R(_) | Val::C(_) => return unsupported("arrays of references"),
                };
                let index = self.pop_int(path)?;
                let o = match self.pop_array(path) {
                    Ok(o) => o,
                    Err(step) => return step,
                };
                let array = path.objects[o].array.as_ref().expect("an array");
                check_kind(*kind, &array.element)?;
                let width = cell_width(&array.element);
                if value.len() < width {
                    return unsupported("a store of a narrower value into an array");
                }
                let stored = self.b.trunc(&value, width);
                let length = array.length.clone();
                self.index_used(path, o, &index);
                let in_bounds = self.b.ult(&index, &length);
                self.branch_throw_or(path, -in_bounds, "java/lang/ArrayIndexOutOfBoundsException", move |engine, path| {
                    // Past a summarized loop a write at a computed index into a large array may be any cell's:
                    // the cells hold any values from here on ([`loops`]).
                    let cells = path.objects[o].array.as_ref().expect("an array").cells.len();
                    if path.loose && cells > loops::LOOSE_CELLS && engine.b.constant_value(&index).is_none() {
                        path.objects[o].unknown = true;
                    }
                    if path.objects[o].unknown {
                        engine.advance(path);
                        return;
                    }
                    let cells = &mut path.objects[o].array.as_mut().expect("an array").cells;
                    for (i, cell) in cells.iter_mut().enumerate() {
                        let here = engine.b.constant(i as i64, 32);
                        let is = engine.b.eq(&index, &here);
                        *cell = engine.b.ite_bits(is, &stored, cell);
                    }
                    engine.advance(path);
                })
            }
            Insn::NewArray(kind) => {
                let element = match kind {
                    ArrayKind::Int => Type::Int,
                    ArrayKind::Long => Type::Long,
                    ArrayKind::Byte => Type::Byte,
                    ArrayKind::Char => Type::Char,
                    ArrayKind::Short => Type::Short,
                    ArrayKind::Float | ArrayKind::Double => return unsupported("floating point"),
                    ArrayKind::Ref => return unsupported("arrays of references"),
                };
                let count = self.pop_int(path)?;
                let cells = self.new_array_cells(path, &count)?;
                let negative = self.b.negative(&count);
                let width = cell_width(&element);
                self.branch_throw_or(path, negative, "java/lang/NegativeArraySizeException", move |engine, path| {
                    let zero = engine.b.constant(0, width);
                    let class = Type::Array(Box::new(element.clone())).descriptor();
                    path.objects.push(Obj { array: Some(Array { element, length: count, cells: vec![zero; cells], refs: Vec::new() }), ..Obj::new(&class) });
                    let o = path.objects.len() - 1;
                    engine.push(path, Val::R(Some(o)));
                    engine.advance(path);
                })
            }
            // Every cell null; the element class is not initialized (JVMS §6.5 anewarray).
            Insn::ANewArray(index) => {
                let frame = path.frames.last().expect("a frame");
                let name = frame.class.pool.class_name(*index).map_err(|e| Stop::Unsupported(e.to_string()))?.to_string();
                let element = if name.starts_with('[') { Type::parse(&name).map_err(|e| Stop::Unsupported(e.to_string()))? } else { Type::Object(name) };
                let count = self.pop_int(path)?;
                let cells = self.new_array_cells(path, &count)?;
                let negative = self.b.negative(&count);
                self.branch_throw_or(path, negative, "java/lang/NegativeArraySizeException", move |engine, path| {
                    let class = Type::Array(Box::new(element.clone())).descriptor();
                    path.objects.push(Obj { array: Some(Array { element, length: count, cells: Vec::new(), refs: vec![Val::R(None); cells] }), ..Obj::new(&class) });
                    let o = path.objects.len() - 1;
                    engine.push(path, Val::R(Some(o)));
                    engine.advance(path);
                })
            }
            _ => unsupported("a multi-dimensional array"),
        }
    }

    /// How many cells a new array of `count` elements has: its size when that is a constant (none when it is
    /// negative, which throws), and otherwise the bound, once the solver shows the size is within it on the path;
    /// or, where it is not, the cells of the largest array the path holds (a copy of an array the run made itself,
    /// as `String.split`'s of a String of as many units as the bound is one longer than the bound).
    fn new_array_cells(&mut self, path: &Path, count: &Bits) -> Result<usize, Stop> {
        Ok(match self.b.constant_value(count) {
            Some(n) if n < 0 => 0,
            Some(n) if n <= 1 << 16 => n as usize,
            Some(n) => return unsupported(format!("an array of {n} elements")),
            None => {
                // A computed size: within the bound, as a copy of a parameter is; within one more, as a table over
                // the positions of a bounded String is (`new boolean[s.length() + 1]`) and the parts a String splits
                // into are; within the path's largest array; or beyond the engine.
                let bound = self.max_array_length as usize;
                let largest = path.objects.iter().filter_map(|o| o.as_array()).map(|a| a.cells.len().max(a.refs.len())).max().unwrap_or(0);
                let mut within = None;
                for cells in [Some(bound), Some(bound + 1), Some(largest).filter(|l| *l > bound + 1)].into_iter().flatten() {
                    if within.is_some() {
                        break;
                    }
                    let most = self.b.constant(cells as i64, 32);
                    let beyond = self.b.slt(&most, count);
                    let mut assumptions = path.cond.clone();
                    assumptions.push(beyond);
                    if !self.solve(&assumptions)? {
                        within = Some(cells);
                    }
                }
                match within {
                    Some(cells) => cells,
                    None => {
                        let top = path.frames.last().expect("a frame");
                        return unsupported(format!("an array of computed size, not known to be within {} elements (in {}.{})", (bound + 1).max(largest), top.class.name.replace('/', "."), top.method));
                    }
                }
            }
        })
    }

    /// Makes the index of an `aastore` (`depth` 1, under the value) a constant, when it is not one and the array
    /// below it is an array: which cell is written is not a choice among bits, as an int is, so the path is split
    /// on `index == i` for each cell `i` in turn, as a switch is. (An `aaload` at such an index reads a choice
    /// among the cells and splits nothing.) Each side that takes a cell
    /// runs the instruction again with `i` in place of the index, and the path on which the index is none of
    /// them throws `ArrayIndexOutOfBoundsException`, since the array's length is at most its cells. `None` when
    /// there is nothing to split, and the instruction goes on (or throws, on a null array).
    fn concrete_index(&mut self, path: &mut Path, depth: usize) -> Option<Step> {
        let stack = &path.frames.last().expect("a frame").stack;
        let n = stack.len();
        if n < depth + 2 {
            return None;
        }
        let at = n - 1 - depth;
        let (Val::I(index), Val::R(Some(o))) = (&stack[at], &stack[at - 1]) else { return None };
        if self.b.constant_value(index).is_some() {
            return None;
        }
        let array = path.objects[*o].array.as_ref().filter(|a| holds_references(&a.element))?;
        let cells = array.refs.len();
        let index = index.clone();
        Some(self.split_index(path, index, at, cells))
    }

    /// [`Engine::concrete_index`]'s split. A path that runs the instruction again does so rather than wait at it,
    /// as one taken from a join point does (`Path::resumed`): merged with the others there, its constant would
    /// be a choice again.
    fn split_index(&mut self, path: &mut Path, index: Bits, at: usize, cells: usize) -> Step {
        let fix = |path: &mut Path, k: &Bits| {
            path.frames.last_mut().expect("a frame").stack[at] = Val::I(k.clone());
            path.resumed = true;
        };
        for i in 0..cells {
            let k = self.b.constant(i as i64, 32);
            let c = self.b.eq(&index, &k);
            match self.sides(path, c)? {
                Sides::Both { then_models, else_models } => {
                    let mut twin = self.split(path, c, then_models, else_models, true);
                    fix(&mut twin, &k);
                    // Counted here, since it does not come back from `next_path` as a new path.
                    self.paths += 1;
                    self.pending.push(twin);
                }
                Sides::Then => {
                    path.cond.push(c);
                    fix(path, &k);
                    return Ok(None);
                }
                Sides::Else => path.cond.push(-c),
                Sides::Undecided { model_takes_then: true } => {
                    // The twin takes the other cells: it runs the instruction again, this cell decided against.
                    let mut twin = self.split_undecided(path, c, true);
                    twin.resumed = true;
                    self.pending.push(twin);
                    fix(path, &k);
                    return Ok(None);
                }
                Sides::Undecided { model_takes_then: false } => {
                    let mut twin = self.split_undecided(path, c, false);
                    fix(&mut twin, &k);
                    self.pending.push(twin);
                }
            }
        }
        self.raise(path, "java/lang/ArrayIndexOutOfBoundsException")
    }

    /// Whether an `aastore`'s value, on top of the stack, is a symbolic reference every object of which is of the
    /// element type of the array below it (a known one): stored as it is, it can't throw `ArrayStoreException`.
    fn stores_without_check(&self, path: &Path) -> bool {
        let stack = &path.frames.last().expect("a frame").stack;
        let n = stack.len();
        let (Some(Val::C(choice)), Some(Val::R(Some(o)))) = (stack.last(), n.checked_sub(3).map(|i| &stack[i])) else { return false };
        let Some(array) = path.objects[*o].as_array().filter(|a| holds_references(&a.element)) else { return false };
        let element = class_of(&array.element);
        choice.0.iter().all(|(_, t)| t.is_none_or(|v| self.cp.is_subtype(&path.objects[v].class, &element)))
    }

    /// Splits the path per option of the symbolic reference `depth` values below the top of the stack, if it is one
    /// ([`Choice`]): the instruction, which needs to know the object, runs again on each part with the reference
    /// known, as [`Engine::concrete_index`] makes an index known. `None` when it is known already.
    fn concrete_ref(&mut self, path: &mut Path, depth: usize) -> Option<Step> {
        let stack = &path.frames.last().expect("a frame").stack;
        let at = stack.len().checked_sub(depth + 1)?;
        let Val::C(choice) = &stack[at] else { return None };
        let choice = choice.clone();
        Some(self.split_choice(path, &choice))
    }

    /// Splits the path per option of `choice`, every option but the last asked of the solver, the last taking what
    /// is left; on each part, every copy of the choice in the path's state is the option's target.
    fn split_choice(&mut self, path: &mut Path, choice: &Rc<Choice>) -> Step {
        let fix = |path: &mut Path, target: Option<usize>| {
            substitute(path, choice, target);
            path.resumed = true;
        };
        let (last, rest) = choice.0.split_last().expect("a choice has options");
        for &(c, target) in rest {
            match self.sides(path, c)? {
                Sides::Both { then_models, else_models } => {
                    let mut twin = self.split(path, c, then_models, else_models, true);
                    fix(&mut twin, target);
                    self.paths += 1;
                    self.pending.push(twin);
                }
                Sides::Then => {
                    path.cond.push(c);
                    fix(path, target);
                    return Ok(None);
                }
                Sides::Else => path.cond.push(-c),
                Sides::Undecided { model_takes_then: true } => {
                    // The twin takes the other options: it runs the instruction again, this one decided against.
                    let mut twin = self.split_undecided(path, c, true);
                    twin.resumed = true;
                    self.pending.push(twin);
                    fix(path, target);
                    return Ok(None);
                }
                Sides::Undecided { model_takes_then: false } => {
                    let mut twin = self.split_undecided(path, c, false);
                    fix(&mut twin, target);
                    self.pending.push(twin);
                }
            }
        }
        // Every other option excluded: the last one's guard holds under the path's condition.
        if !path.cond.contains(&last.0) {
            path.cond.push(last.0);
        }
        fix(path, last.1);
        Ok(None)
    }

    /// Whether the reference is null, as a literal: a formula over a [`Choice`]'s guards.
    fn null_lit(&mut self, v: &Val) -> Result<Lit, Stop> {
        let Some(options) = v.options() else { return unsupported(format!("expected a reference on the stack, found {v:?}")) };
        let guards: Vec<Lit> = options.iter().filter(|(_, t)| t.is_none()).map(|(g, _)| *g).collect();
        Ok(self.any(&guards))
    }

    /// A reference's options as the objects they are: an object that is another under a guard ([`Obj::same`]) is
    /// that one there, and itself elsewhere.
    fn identities(&mut self, path: &Path, options: &[(Lit, Option<usize>)]) -> Vec<(Lit, Option<usize>)> {
        let mut out = Vec::new();
        for &(g, t) in options {
            let same = match t {
                Some(o) if !path.objects[o].same.is_empty() => path.objects[o].same.clone(),
                _ => {
                    out.push((g, t));
                    continue;
                }
            };
            let mut itself = g;
            for (h, other) in same {
                let there = self.b.and(g, h);
                itself = self.b.and(itself, -h);
                out.extend(self.identities(path, &[(there, Some(other))]));
            }
            out.push((itself, t));
        }
        out
    }

    /// Whether two references are the same object (or both null), as a literal: some pair of their options with
    /// one target, both guards holding.
    fn same_lit(&mut self, path: &Path, x: &Val, y: &Val) -> Result<Lit, Stop> {
        let (Some(xs), Some(ys)) = (x.options(), y.options()) else { return unsupported(format!("expected two references on the stack, found {x:?} and {y:?}")) };
        // One reference is itself, whatever it may be: two options of one choice never hold together.
        let one = xs == ys;
        // Each option as the object it is ([`Obj::same`]): itself, or another under a guard.
        let xs = self.identities(path, &xs);
        let ys = self.identities(path, &ys);
        let mut pairs = Vec::new();
        for (g, t) in &xs {
            for (h, u) in &ys {
                if t == u {
                    pairs.push(self.b.and(*g, *h));
                } else if let (Some(t), Some(u)) = (t, u) {
                    // Whether two Locales are one object is the JDK's cache's to say ([`locale`]).
                    if !one && Self::is_known_locale(path, *t) && Self::is_known_locale(path, *u) && self.b.and(*g, *h) != FALSE {
                        return unsupported("a comparison of two Locale objects by reference: whether Locale.forLanguageTag returns one of Locale's constants, or the object an earlier call returned, is the JDK's cache's to say");
                    }
                }
            }
        }
        Ok(self.any(&pairs))
    }

    /// The disjunction of `lits`, `FALSE` when there are none.
    fn any(&mut self, lits: &[Lit]) -> Lit {
        let mut c = FALSE;
        for &l in lits {
            c = self.b.or(c, l);
        }
        c
    }

    /// `getfield` through a symbolic reference: the field of each object it may be, chosen among by the guards, and
    /// `NullPointerException` where it is null.
    fn get_field(&mut self, path: &mut Path, choice: &Choice, owner: &str, name: &str, descriptor: &str) -> Step {
        let mut values: Vec<(Lit, Val)> = Vec::new();
        let mut null = Vec::new();
        for &(g, t) in &choice.0 {
            match t {
                None => null.push(g),
                Some(o) => {
                    self.reads_field(path, o, owner, name, descriptor)?;
                    let key = self.field_key(path, o, owner, name, descriptor)?;
                    let v = match path.objects[o].fields.get(&key) {
                        Some(v) => v.clone(),
                        None => self.default_value(descriptor)?,
                    };
                    values.push((g, v));
                }
            }
        }
        // Where no object is the target the reference is null, which throws; there the value is any of them.
        let (_, mut value) = values.pop().expect("a choice has an object or two options");
        while let Some((g, v)) = values.pop() {
            value = choose(&mut self.b, g, &v, &value).ok_or_else(|| Stop::Unsupported(format!("fields {name} of different kinds")))?;
        }
        let null = self.any(&null);
        self.branch_throw(path, null, "java/lang/NullPointerException", value)
    }

    /// Refuses, inside a summarized method, a `getfield` of a field that is not final on an object that was there
    /// before the call ([`Engine::reads`]).
    fn reads_field(&self, path: &Path, o: usize, owner: &str, name: &str, descriptor: &str) -> Result<(), Stop> {
        if path.objects[o].given && self.in_lemma(path) && !self.final_field(owner, name, descriptor) {
            self.reads(path, || format!("reads the field {name} of an object that was there before the call"))?;
        }
        Ok(())
    }

    /// `putfield` through a symbolic reference: each object it may be gets the value where its guard holds and keeps
    /// its own elsewhere, and where it is null, `NullPointerException`.
    fn put_field(&mut self, path: &mut Path, choice: &Choice, value: Val, owner: &str, name: &str, descriptor: &str) -> Step {
        let mut writes: Vec<(usize, String, Val)> = Vec::new();
        let mut null = Vec::new();
        for &(g, t) in &choice.0 {
            match t {
                None => null.push(g),
                Some(o) => {
                    self.keeps(path, Some(o), "writes a field of an object made before it was called")?;
                    let key = self.field_key(path, o, owner, name, descriptor)?;
                    let old = match path.objects[o].fields.get(&key) {
                        Some(v) => v.clone(),
                        None => self.default_value(descriptor)?,
                    };
                    let new = choose(&mut self.b, g, &value, &old).ok_or_else(|| Stop::Unsupported(format!("a putfield of {value:?} into {name}")))?;
                    writes.push((o, key, new));
                }
            }
        }
        let null = self.any(&null);
        self.branch_throw_or(path, null, "java/lang/NullPointerException", move |engine, path| {
            for (o, key, v) in writes {
                path.objects[o].fields.insert(key, v);
            }
            engine.advance(path);
        })
    }

    /// A jump within the top frame, counting back edges against the bound per entry of a loop (VF-011).
    ///
    /// A back edge from `from` to `target` takes another iteration of the loop headed at `target`, and is counted
    /// for that head. It also leaves the iteration of every loop whose head is in its body, after `target` and up to
    /// `from` (an inner loop, run again from its entry in the next iteration), so their counts start again. Each
    /// count is kept while the path stays in its loop, and a new frame starts with none.
    ///
    /// It stays a bound: on a path that goes on forever in a frame, take the lowest head whose back edges it takes
    /// without end. Its count starts again only on a back edge to a lower head, which the path takes finitely
    /// often, so the count grows past `--unwind` and the path ends unwound (calls are at most 64 deep). An inner
    /// loop is thus run at most `--unwind` times per iteration of the loops around it, as JBMC's `--unwind` counts.
    fn jump(&mut self, path: &mut Path, target: u32) -> Step {
        let frame = path.frames.last_mut().expect("a frame");
        let to = *frame.code.index.get(&target).ok_or_else(|| Stop::Unsupported(format!("jump to no instruction at pc {target}")))?;
        if to <= frame.at {
            let from = frame.pc();
            frame.back_edges.retain(|&head, _| head <= target || head > from);
            frame.summarized.retain(|&head| head <= target || head > from);
            // Back at the head of a loop an invariant covers: the head's state stands for this one.
            if frame.summarized.contains(&target) {
                return Ok(Some(End::Back(target, None)));
            }
            let count = frame.back_edges.entry(target).or_insert(0);
            *count += 1;
            if *count > self.unwind {
                // Past the bound: an invariant of the further iterations, or the loop is left unwound ([`loops`]).
                return self.summarize(path, target, from);
            }
        }
        path.frames.last_mut().expect("a frame").at = to;
        Ok(None)
    }

    fn advance(&self, path: &mut Path) {
        path.frames.last_mut().expect("a frame").at += 1;
    }

    fn push(&self, path: &mut Path, v: Val) {
        path.frames.last_mut().expect("a frame").stack.push(v);
    }

    fn pop(&self, path: &mut Path) -> Result<Val, Stop> {
        path.frames.last_mut().expect("a frame").stack.pop().ok_or_else(|| Stop::Unsupported("operand stack underflow".into()))
    }

    fn pop_int(&self, path: &mut Path) -> Result<Bits, Stop> {
        match self.pop(path)? {
            Val::I(b) => Ok(b),
            other => unsupported(format!("expected an int on the stack, found {other:?}")),
        }
    }

    fn pop_long(&self, path: &mut Path) -> Result<Bits, Stop> {
        match self.pop(path)? {
            Val::J(b) => Ok(b),
            other => unsupported(format!("expected a long on the stack, found {other:?}")),
        }
    }

    fn pop_ref(&self, path: &mut Path) -> Result<Option<usize>, Stop> {
        match self.pop(path)? {
            Val::R(r) => Ok(r),
            other => unsupported(format!("expected a reference on the stack, found {other:?}")),
        }
    }

    fn alloc(&self, path: &mut Path, class: &str) -> usize {
        path.objects.push(Obj::new(class));
        path.objects.len() - 1
    }

    /// The array the reference on the stack is, after the null check.
    fn pop_array(&mut self, path: &mut Path) -> Result<usize, Step> {
        let r = self.pop_ref(path).map_err(Err)?;
        let o = self.null_check(path, r)?.expect("checked");
        if !path.objects[o].is_array() {
            return Err(unsupported("an array operation on an object that is not an array"));
        }
        Ok(o)
    }

    /// Throws a new exception of the class from the current instruction.
    fn raise(&mut self, path: &mut Path, class: &str) -> Step {
        let obj = self.alloc(path, class);
        self.throw(path, obj)
    }

    /// Unwinds to the nearest handler of the object's class; a path the harness's `AssertionError` leaves is a
    /// violation, and any other uncaught exception is outside what the engine can judge.
    ///
    /// An exception that leaves a `<clinit>` makes its class erroneous and, unless it is an `Error`, is replaced by
    /// an `ExceptionInInitializerError`; the classes the instruction that ran it was initializing are erroneous
    /// too (JVMS §5.5, steps 7 and 11).
    fn throw(&mut self, path: &mut Path, mut obj: usize) -> Step {
        let mut class = path.objects[obj].class.clone();
        while let Some(frame) = path.frames.last_mut() {
            for c in std::mem::take(&mut frame.entered) {
                path.classes.insert(c, ClassState::Erroneous);
            }
            let pc = frame.pc();
            let handler = frame.code.handlers.iter().find(|h| u32::from(h.start_pc) <= pc && pc < u32::from(h.end_pc) && h.catch_type.as_deref().is_none_or(|t| self.cp.is_subtype(&class, t))).cloned();
            if let Some(h) = handler {
                let to = *frame.code.index.get(&u32::from(h.handler_pc)).ok_or_else(|| Stop::Unsupported("handler at no instruction".into()))?;
                frame.stack.clear();
                frame.stack.push(Val::R(Some(obj)));
                frame.at = to;
                return Ok(None);
            }
            if let Some(c) = path.frames.pop().and_then(|f| f.initializes) {
                path.classes.insert(c, ClassState::Erroneous);
                if !self.cp.is_subtype(&class, "java/lang/Error") {
                    class = "java/lang/ExceptionInInitializerError".to_string();
                    obj = self.alloc(path, &class);
                }
            }
        }
        if self.cp.is_subtype(&class, "java/lang/AssertionError") {
            let feasible = self.solve(&path.cond.clone())?;
            return Ok(Some(if feasible { End::Violation(std::mem::take(&mut path.cond)) } else { End::Infeasible }));
        }
        unsupported(format!("an uncaught {} leaves the harness", class.replace('/', ".")))
    }

    fn null_check(&mut self, path: &mut Path, r: Option<usize>) -> Result<Option<usize>, Step> {
        match r {
            Some(o) => Ok(Some(o)),
            None => Err(self.raise(path, "java/lang/NullPointerException")),
        }
    }

    /// Executes the instruction at the top frame's `at`.
    fn step(&mut self, path: &mut Path) -> Step {
        let frame = path.frames.last().expect("a frame");
        let insn = frame.code.insns[frame.at].clone();
        let class = frame.class.clone();
        match insn {
            Insn::Nop => {}
            Insn::AConstNull => self.push(path, Val::R(None)),
            Insn::IConst(v) => {
                let c = self.b.constant(i64::from(v), 32);
                self.push(path, Val::I(c));
            }
            Insn::LConst(v) => {
                let c = self.b.constant(v, 64);
                self.push(path, Val::J(c));
            }
            Insn::FConst(_) | Insn::DConst(_) => return unsupported("floating point"),
            Insn::Ldc(index) => match class.pool.loadable(index).map_err(|e| Stop::Unsupported(e.to_string()))? {
                // One object per distinct content, as the JVM interns strings (JLS §3.10.5).
                loaded @ (BootstrapArg::Str(_) | BootstrapArg::Units(_)) => {
                    let units = loaded.string_units().expect("a String constant").into_owned();
                    let o = self.literal(path, Literal::Str(units), "java/lang/String");
                    self.push(path, Val::R(Some(o)));
                }
                BootstrapArg::Int(v) => {
                    let c = self.b.constant(i64::from(v), 32);
                    self.push(path, Val::I(c));
                }
                BootstrapArg::Long(v) => {
                    let c = self.b.constant(v, 64);
                    self.push(path, Val::J(c));
                }
                // One object per class literal, as the JVM has one `Class` object per class.
                BootstrapArg::Class(name) => {
                    let o = self.literal(path, Literal::Class(name), "java/lang/Class");
                    self.push(path, Val::R(Some(o)));
                }
                BootstrapArg::Float(_) | BootstrapArg::Double(_) => return unsupported("floating point"),
                other => return unsupported(format!("ldc of {other:?}")),
            },
            Insn::Load(_, slot) => {
                let frame = path.frames.last().expect("a frame");
                let v = frame.locals.get(slot as usize).cloned().flatten().ok_or_else(|| Stop::Unsupported(format!("load of an unset local {slot}")))?;
                self.push(path, v);
            }
            Insn::Store(_, slot) => {
                let v = self.pop(path)?;
                let frame = path.frames.last_mut().expect("a frame");
                let slot = slot as usize;
                if frame.locals.len() <= slot + 1 {
                    frame.locals.resize(slot + 2, None);
                }
                if v.category() == 2 {
                    frame.locals[slot + 1] = None;
                }
                frame.locals[slot] = Some(v);
            }
            Insn::ArrayLoad(_) | Insn::ArrayStore(_) | Insn::NewArray(_) | Insn::ANewArray(_) | Insn::ArrayLength | Insn::MultiANewArray(..) => return self.array_insn(path, &insn),
            Insn::Pop => {
                self.pop(path)?;
            }
            Insn::Pop2 => {
                if self.pop(path)?.category() == 1 {
                    self.pop(path)?;
                }
            }
            Insn::Dup => {
                let v = self.pop(path)?;
                self.push(path, v.clone());
                self.push(path, v);
            }
            Insn::DupX1 => {
                let v1 = self.pop(path)?;
                let v2 = self.pop(path)?;
                self.push(path, v1.clone());
                self.push(path, v2);
                self.push(path, v1);
            }
            Insn::DupX2 => {
                let v1 = self.pop(path)?;
                let v2 = self.pop(path)?;
                if v2.category() == 2 {
                    self.push(path, v1.clone());
                    self.push(path, v2);
                    self.push(path, v1);
                } else {
                    let v3 = self.pop(path)?;
                    self.push(path, v1.clone());
                    self.push(path, v3);
                    self.push(path, v2);
                    self.push(path, v1);
                }
            }
            Insn::Dup2 => {
                let v1 = self.pop(path)?;
                if v1.category() == 2 {
                    self.push(path, v1.clone());
                    self.push(path, v1);
                } else {
                    let v2 = self.pop(path)?;
                    self.push(path, v2.clone());
                    self.push(path, v1.clone());
                    self.push(path, v2);
                    self.push(path, v1);
                }
            }
            Insn::Dup2X1 => {
                let v1 = self.pop(path)?;
                if v1.category() == 2 {
                    let v2 = self.pop(path)?;
                    self.push(path, v1.clone());
                    self.push(path, v2);
                    self.push(path, v1);
                } else {
                    let v2 = self.pop(path)?;
                    let v3 = self.pop(path)?;
                    self.push(path, v2.clone());
                    self.push(path, v1.clone());
                    self.push(path, v3);
                    self.push(path, v2);
                    self.push(path, v1);
                }
            }
            Insn::Dup2X2 => {
                let v1 = self.pop(path)?;
                let v2 = self.pop(path)?;
                if v1.category() == 2 && v2.category() == 2 {
                    self.push(path, v1.clone());
                    self.push(path, v2);
                    self.push(path, v1);
                } else if v1.category() == 1 && v2.category() == 1 {
                    let v3 = self.pop(path)?;
                    if v3.category() == 2 {
                        self.push(path, v2.clone());
                        self.push(path, v1.clone());
                        self.push(path, v3);
                        self.push(path, v2);
                        self.push(path, v1);
                    } else {
                        let v4 = self.pop(path)?;
                        self.push(path, v2.clone());
                        self.push(path, v1.clone());
                        self.push(path, v4);
                        self.push(path, v3);
                        self.push(path, v2);
                        self.push(path, v1);
                    }
                } else {
                    // v1 wide over v2, v3 narrow.
                    let v3 = self.pop(path)?;
                    self.push(path, v1.clone());
                    self.push(path, v3);
                    self.push(path, v2);
                    self.push(path, v1);
                }
            }
            Insn::Swap => {
                let v1 = self.pop(path)?;
                let v2 = self.pop(path)?;
                self.push(path, v1);
                self.push(path, v2);
            }
            Insn::Arith(op, kind) => return self.arith(path, op, kind),
            Insn::IInc(slot, delta) => {
                let frame = path.frames.last_mut().expect("a frame");
                let Some(Some(Val::I(v))) = frame.locals.get(slot as usize).cloned() else { return unsupported(format!("iinc of an unset local {slot}")) };
                let d = self.b.constant(i64::from(delta), 32);
                let sum = self.b.add(&v, &d);
                path.frames.last_mut().expect("a frame").locals[slot as usize] = Some(Val::I(sum));
            }
            Insn::Convert(from, to) => {
                let v = match (from, to) {
                    (Kind::Int, Narrow::To(Kind::Long)) => {
                        let x = self.pop_int(path)?;
                        Val::J(self.b.sext(&x, 64))
                    }
                    (Kind::Long, Narrow::To(Kind::Int)) => {
                        let x = self.pop_long(path)?;
                        Val::I(self.b.trunc(&x, 32))
                    }
                    (Kind::Int, Narrow::Byte) => {
                        let x = self.pop_int(path)?;
                        let t = self.b.trunc(&x, 8);
                        Val::I(self.b.sext(&t, 32))
                    }
                    (Kind::Int, Narrow::Char) => {
                        let x = self.pop_int(path)?;
                        let t = self.b.trunc(&x, 16);
                        Val::I(self.b.zext(&t, 32))
                    }
                    (Kind::Int, Narrow::Short) => {
                        let x = self.pop_int(path)?;
                        let t = self.b.trunc(&x, 16);
                        Val::I(self.b.sext(&t, 32))
                    }
                    _ => return unsupported("floating point"),
                };
                self.push(path, v);
            }
            Insn::Cmp(op) => {
                if op.kind != Kind::Long {
                    return unsupported("floating point");
                }
                let y = self.pop_long(path)?;
                let x = self.pop_long(path)?;
                let lt = self.b.slt(&x, &y);
                let eq = self.b.eq(&x, &y);
                let minus_one = self.b.constant(-1, 32);
                let zero = self.b.constant(0, 32);
                let one = self.b.constant(1, 32);
                let tail = self.b.ite_bits(eq, &zero, &one);
                let r = self.b.ite_bits(lt, &minus_one, &tail);
                self.push(path, Val::I(r));
            }
            Insn::If(cond, target) => {
                let x = self.pop_int(path)?;
                let zero = self.b.constant(0, 32);
                let c = self.compare(cond, &x, &zero);
                return self.conditional(path, c, target);
            }
            Insn::IfICmp(cond, target) => {
                let y = self.pop_int(path)?;
                let x = self.pop_int(path)?;
                let c = self.compare(cond, &x, &y);
                return self.conditional(path, c, target);
            }
            // Over known references these are constants; over a symbolic one, formulas of its guards.
            Insn::IfACmp(equal, target) => {
                let y = self.pop(path)?;
                let x = self.pop(path)?;
                self.compares(path, &x)?;
                self.compares(path, &y)?;
                let same = self.same_lit(path, &x, &y)?;
                return self.conditional(path, if equal { same } else { -same }, target);
            }
            Insn::IfNull(target) => {
                let x = self.pop(path)?;
                let null = self.null_lit(&x)?;
                return self.conditional(path, null, target);
            }
            Insn::IfNonNull(target) => {
                let x = self.pop(path)?;
                let null = self.null_lit(&x)?;
                return self.conditional(path, -null, target);
            }
            Insn::Goto(target) => return self.jump(path, target),
            Insn::Jsr(_) | Insn::Ret(_) => return unsupported("jsr/ret"),
            Insn::TableSwitch { default, low, high, targets } => {
                let key = self.pop_int(path)?;
                let cases: Vec<(i32, u32)> = targets.iter().enumerate().map(|(i, &t)| (low + i as i32, t)).collect();
                debug_assert_eq!(cases.len() as i32, high - low + 1);
                return self.switch(path, key, &cases, default);
            }
            Insn::LookupSwitch { default, pairs } => {
                let key = self.pop_int(path)?;
                return self.switch(path, key, &pairs, default);
            }
            Insn::Return(kind) => {
                let value = match kind {
                    Some(_) => Some(self.pop(path)?),
                    None => None,
                };
                let returned = path.frames.pop().expect("a frame");
                if path.frames.is_empty() {
                    return Ok(Some(End::Returned));
                }
                // A `<clinit>` returned: its class is initialized, and the instruction that ran it runs again.
                if let Some(c) = returned.initializes {
                    // In a lemma's proof, what it made a caller may change before anything else reads it (an
                    // initializer that started before it and reads its array): it was there before ([`Engine::in_lemma`]).
                    if self.pure.is_some() && !self.own_induction {
                        path.objects.iter_mut().for_each(|o| o.given = true);
                    }
                    path.classes.insert(c, ClassState::Done);
                    return Ok(None);
                }
                if let Some(v) = value {
                    self.push(path, v);
                }
                self.advance(path);
                return Ok(None);
            }
            // The class that declares the resolved field is initialized first (JVMS §5.5).
            Insn::GetStatic(index) => {
                let member = class.pool.member(index).map_err(|e| Stop::Unsupported(e.to_string()))?;
                let declaring = self.cp.resolve_field(&member.owner, &member.name, &member.descriptor).unwrap_or_else(|| member.owner.clone());
                // The JDK's UTF-8 charset is one object ([`bytes`]).
                if (declaring.as_str(), member.name.as_str()) == (bytes::STANDARD_CHARSETS, "UTF_8") {
                    let charset = self.literal(path, Literal::Charset("UTF_8"), bytes::CHARSET);
                    self.push(path, Val::R(Some(charset)));
                    self.advance(path);
                    return Ok(None);
                }
                // Each of `Locale`'s constants is one object ([`locale`]).
                if locale::constant(&declaring, &member.name) {
                    let constant = self.locale_constant(path, &member.name);
                    self.push(path, Val::R(Some(constant)));
                    self.advance(path);
                    return Ok(None);
                }
                // Each level of `java.util.logging` below `INFO` is one object ([`runtime`]).
                if let Some(level) = runtime::level_constant(&declaring, &member.name) {
                    let constant = self.literal(path, Literal::Level(level), runtime::LEVEL);
                    self.push(path, Val::R(Some(constant)));
                    self.advance(path);
                    return Ok(None);
                }
                if let Some(step) = self.initialise(path, &declaring) {
                    return step;
                }
                // A lemma reads no static field a caller can write ([`Engine::reads`]): a final one is written
                // by its class's initializer alone, and the claim's class has only the tool's own (the measure
                // of the call under proof). Nor does an initializer the lemma's proof runs, but for the fields of
                // a class being initialized, which no caller can have written before its initializer began.
                if declaring != crate::harness::expr::CLAIM_CLASS && self.cp.checker_statics(&declaring) && !self.final_field(&declaring, &member.name, &member.descriptor) && path.classes.get(&declaring) != Some(&ClassState::InProgress) {
                    self.reads(path, || format!("reads the static field {}.{}", declaring.replace('/', "."), member.name))?;
                }
                let v = match self.application_static(path, &declaring, &member.name, &member.descriptor) {
                    Some(v) => v?,
                    None => self.get_static(&member.owner, &member.name, &member.descriptor)?,
                };
                self.push(path, v);
            }
            Insn::PutStatic(index) => {
                self.keeps(path, None, "writes a static field")?;
                let member = class.pool.member(index).map_err(|e| Stop::Unsupported(e.to_string()))?;
                let declaring = self.cp.resolve_field(&member.owner, &member.name, &member.descriptor).unwrap_or_else(|| member.owner.clone());
                if !self.cp.checker_statics(&declaring) {
                    return unsupported(format!("writes static field {}.{} of the JDK", declaring.replace('/', "."), member.name));
                }
                if let Some(step) = self.initialise(path, &declaring) {
                    return step;
                }
                if path.classes.get(&declaring) == Some(&ClassState::Assumed) {
                    return unsupported(format!("writes static field {}.{} of a class whose initializer was not run", declaring.replace('/', "."), member.name));
                }
                let v = self.pop(path)?;
                path.statics.insert((declaring, member.name.clone()), v);
            }
            Insn::GetField(index) => {
                let member = class.pool.member(index).map_err(|e| Stop::Unsupported(e.to_string()))?;
                if let Some(Val::C(choice)) = path.frames.last().expect("a frame").stack.last().cloned() {
                    self.pop(path)?;
                    return self.get_field(path, &choice, &member.owner, &member.name, &member.descriptor);
                }
                let r = self.pop_ref(path)?;
                let o = match self.null_check(path, r) {
                    Ok(o) => o.expect("checked"),
                    Err(step) => return step,
                };
                self.reads_field(path, o, &member.owner, &member.name, &member.descriptor)?;
                let key = self.field_key(path, o, &member.owner, &member.name, &member.descriptor)?;
                let v = match path.objects[o].fields.get(&key) {
                    Some(v) => v.clone(),
                    None => self.default_value(&member.descriptor)?,
                };
                self.push(path, v);
            }
            Insn::PutField(index) => {
                let member = class.pool.member(index).map_err(|e| Stop::Unsupported(e.to_string()))?;
                let v = self.pop(path)?;
                if let Some(Val::C(choice)) = path.frames.last().expect("a frame").stack.last().cloned() {
                    self.pop(path)?;
                    return self.put_field(path, &choice, v, &member.owner, &member.name, &member.descriptor);
                }
                let r = self.pop_ref(path)?;
                let o = match self.null_check(path, r) {
                    Ok(o) => o.expect("checked"),
                    Err(step) => return step,
                };
                self.keeps(path, Some(o), "writes a field of an object made before it was called")?;
                let key = self.field_key(path, o, &member.owner, &member.name, &member.descriptor)?;
                path.objects[o].fields.insert(key, v);
            }
            Insn::InvokeStatic(index) => {
                let member = class.pool.member(index).map_err(|e| Stop::Unsupported(e.to_string()))?;
                return self.invoke_static(path, &class.name, &member);
            }
            Insn::InvokeSpecial(index) | Insn::InvokeVirtual(index) | Insn::InvokeInterface(index) => {
                let member = class.pool.member(index).map_err(|e| Stop::Unsupported(e.to_string()))?;
                return self.invoke_instance(path, &class.name, matches!(insn, Insn::InvokeSpecial(_)), &member);
            }
            Insn::InvokeDynamic(index) => {
                let (bootstrap, _, descriptor_text) = class.pool.invoke_dynamic(index).map_err(|e| Stop::Unsupported(e.to_string()))?;
                let descriptor = MethodDescriptor::parse(descriptor_text).map_err(|e| Stop::Unsupported(e.to_string()))?;
                // A lambda or a method reference: an object of the interface, which holds what the site captured.
                let site = class.bootstrap_methods().ok().and_then(|b| b.into_iter().nth(usize::from(bootstrap)));
                if let Some(b) = site.as_ref().filter(|b| b.method.member.owner == "java/lang/invoke/LambdaMetafactory" && b.method.member.name == "metafactory") {
                    let (_, sam, _) = class.pool.invoke_dynamic(index).map_err(|e| Stop::Unsupported(e.to_string()))?;
                    let (Type::Object(interface), Some(BootstrapArg::MethodHandle(handle))) = (&descriptor.ret, b.args.get(1)) else { return unsupported("a lambda site with no method to call") };
                    let lambda = Lambda { interface: interface.clone(), name: sam.to_string(), handle: handle.clone(), captured: descriptor.params.len() };
                    let captured = self.pop_args(path, descriptor.params.len())?;
                    let r = self.alloc(path, interface);
                    path.objects[r].lambda = Some(Rc::new(lambda));
                    for (i, v) in captured.into_iter().enumerate() {
                        path.objects[r].fields.insert(captured_key(i), v);
                    }
                    self.push(path, Val::R(Some(r)));
                    self.advance(path);
                    return Ok(None);
                }
                if !is_string(&descriptor.ret) {
                    return unsupported("invokedynamic other than a lambda and string concatenation");
                }
                // An object argument is converted by its toString, which the engine does not run.
                for class in gaps::converted_arguments(&descriptor) {
                    if let Some(end) = self.meet(path, GapKind::StringConversion, &class, "toString", "()Ljava/lang/String;") {
                        return Ok(Some(end));
                    }
                }
                // The Strings concatenated are known objects, each with its content or none.
                for (depth, t) in descriptor.params.iter().rev().enumerate() {
                    if is_string(t) {
                        if let Some(step) = self.concrete_ref(path, depth) {
                            return step;
                        }
                    }
                }
                let args = self.pop_args(path, descriptor.params.len())?;
                let recipe = class.bootstrap_methods().ok().and_then(|b| b.into_iter().nth(usize::from(bootstrap)));
                let r = self.concatenation(path, recipe.as_ref(), &descriptor, args)?;
                self.push(path, Val::R(Some(r)));
            }
            Insn::New(index) => {
                let name = class.pool.class_name(index).map_err(|e| Stop::Unsupported(e.to_string()))?.to_string();
                if let Some(step) = self.initialise(path, &name) {
                    return step;
                }
                let r = self.alloc(path, &name);
                self.push(path, Val::R(Some(r)));
            }
            Insn::AThrow => {
                if let Some(step) = self.concrete_ref(path, 0) {
                    return step;
                }
                let r = self.pop_ref(path)?;
                let o = match self.null_check(path, r) {
                    Ok(o) => o.expect("checked"),
                    Err(step) => return step,
                };
                return self.throw(path, o);
            }
            Insn::CheckCast(index) => {
                let target = class.pool.class_name(index).map_err(|e| Stop::Unsupported(e.to_string()))?.to_string();
                if let Some(step) = self.concrete_ref(path, 0) {
                    return step;
                }
                let r = self.pop_ref(path)?;
                if let Some(o) = r {
                    if !self.cp.is_subtype(&path.objects[o].class, &target) {
                        return self.raise(path, "java/lang/ClassCastException");
                    }
                }
                self.push(path, Val::R(r));
            }
            Insn::InstanceOf(index) => {
                let target = class.pool.class_name(index).map_err(|e| Stop::Unsupported(e.to_string()))?.to_string();
                let r = self.pop(path)?;
                let Some(options) = r.options() else { return unsupported(format!("expected a reference on the stack, found {r:?}")) };
                let guards: Vec<Lit> = options.iter().filter(|(_, t)| t.is_some_and(|o| self.cp.is_subtype(&path.objects[o].class, &target))).map(|(g, _)| *g).collect();
                let is = self.any(&guards);
                let (one, zero) = (self.b.constant(1, 32), self.b.constant(0, 32));
                let c = self.b.ite_bits(is, &one, &zero);
                self.push(path, Val::I(c));
            }
            // In a run of one thread a monitor is always free and always held by it: only a null one does anything.
            Insn::MonitorEnter | Insn::MonitorExit => {
                if let Some(step) = self.concrete_ref(path, 0) {
                    return step;
                }
                let r = self.pop_ref(path)?;
                if let Err(step) = self.null_check(path, r) {
                    return step;
                }
            }
        }
        self.advance(path);
        Ok(None)
    }

    /// `length()`, `isEmpty()`, `charAt(int)`, `equals(Object)` and `startsWith(String)` of a String whose content
    /// the engine holds ([`Obj::content`]), as the JDK's do, by its Javadoc: `charAt` out of range throws
    /// `StringIndexOutOfBoundsException`, `startsWith(null)` a `NullPointerException`, and `equals` is true of the
    /// very object, false of null and of any other class, and otherwise compares the lengths and every code unit.
    /// `None` for any other call, and for one whose String has no content, which stays the JDK call it was (a
    /// gap), unless what it lacks is a named limit ([`Obj::limit`]), which ends the path with no verdict.
    fn string_method(&mut self, path: &mut Path, o: usize, name: &str, descriptor: &str, args: &[Val]) -> Option<Step> {
        if !models_string_method(STRING, name, descriptor) {
            return None;
        }
        // `chars()` enters the model of its stream, which reads the String unit by unit as any caller does.
        if let Some((class, method, entry)) = crate::models::entry(STRING, name, descriptor) {
            return Some(self.call(path, class, method, entry, vec![Val::R(Some(o))]));
        }
        // `toString()` of a String is the String itself (its Javadoc), whatever the engine holds of its content.
        if name == "toString" {
            self.push(path, Val::R(Some(o)));
            self.advance(path);
            return Some(Ok(None));
        }
        let limited = |obj: &Obj| obj.limit.clone().map(|why| unsupported(why));
        let Some(s) = path.objects[o].content().cloned() else { return limited(&path.objects[o]) };
        if strings::models(name, descriptor) || locale::models_string(name, descriptor) {
            return Some(self.string_method_on_content(path, o, &s, name, descriptor, args));
        }
        if name == "matches" && regex::models_string(name, descriptor) {
            return self.string_matches(path, &s, args);
        }
        if bytes::models_string(name, descriptor) {
            return self.string_bytes(path, &s, args);
        }
        if regex::models_string(name, descriptor) {
            return Some(self.string_split(path, o, &s, args));
        }
        let zero = self.b.constant(0, 32);
        let truth = match (name, args) {
            ("length", _) => {
                self.push(path, Val::I(s.length));
                self.advance(path);
                return Some(Ok(None));
            }
            // s[0]*31^(n-1) + ... + s[n-1], in int arithmetic (String.hashCode's Javadoc): 0 for the empty String.
            ("hashCode", _) => {
                let mut hash = self.b.constant(0, 32);
                let five = self.b.constant(5, 32);
                for (i, cell) in s.cells.iter().enumerate() {
                    let here = self.b.constant(i as i64, 32);
                    let inside = self.b.ult(&here, &s.length);
                    let shifted = self.b.shl(&hash, &five);
                    let times31 = self.b.sub(&shifted, &hash);
                    let unit = self.b.extend_cell(&Type::Char, cell);
                    let next = self.b.add(&times31, &unit);
                    hash = self.b.ite_bits(inside, &next, &hash);
                }
                self.push(path, Val::I(hash));
                self.advance(path);
                return Some(Ok(None));
            }
            ("isEmpty", _) => self.b.eq(&s.length, &zero),
            ("charAt", [Val::I(index)]) => {
                let mut unit = s.cells.last().cloned().unwrap_or_else(|| self.b.constant(0, 16));
                for (i, cell) in s.cells.iter().enumerate().rev().skip(1) {
                    let here = self.b.constant(i as i64, 32);
                    let is = self.b.eq(index, &here);
                    unit = self.b.ite_bits(is, cell, &unit);
                }
                let unit = self.b.extend_cell(&Type::Char, &unit);
                let in_bounds = self.b.ult(index, &s.length);
                return Some(self.branch_throw(path, -in_bounds, "java/lang/StringIndexOutOfBoundsException", Val::I(unit)));
            }
            ("equals", [Val::R(other)]) => match *other {
                None => FALSE,
                Some(p) if p == o => TRUE,
                Some(p) if path.objects[p].class != STRING => FALSE,
                Some(p) => match path.objects[p].content().cloned() {
                    Some(t) => {
                        let lengths = self.b.eq(&s.length, &t.length);
                        let units = self.units_agree(&s, &t, &s.length);
                        self.b.and(lengths, units)
                    }
                    None => return limited(&path.objects[p]),
                },
            },
            ("startsWith", [Val::R(prefix)]) => match *prefix {
                None => return Some(self.raise(path, "java/lang/NullPointerException")),
                Some(p) => match path.objects[p].content().cloned() {
                    Some(t) => {
                        let fits = self.b.sle(&t.length, &s.length);
                        let units = self.units_agree(&s, &t, &t.length);
                        self.b.and(fits, units)
                    }
                    None => return limited(&path.objects[p]),
                },
            },
            _ => return Some(unsupported(format!("String.{name}{descriptor} with arguments {args:?}"))),
        };
        let (one, zero) = (self.b.constant(1, 32), self.b.constant(0, 32));
        let value = self.b.ite_bits(truth, &one, &zero);
        self.push(path, Val::I(value));
        self.advance(path);
        Some(Ok(None))
    }

    /// Whether two contents have the same code unit at every index below `upto` (the length of one of them, which
    /// the caller has made at most the other's): an index past either's cells is past `upto` too.
    fn units_agree(&mut self, s: &Array, t: &Array, upto: &Bits) -> Lit {
        let mut agree = Vec::new();
        for (i, (x, y)) in s.cells.iter().zip(&t.cells).enumerate() {
            let here = self.b.constant(i as i64, 32);
            let inside = self.b.ult(&here, upto);
            let same = self.b.eq(x, y);
            agree.push(self.b.or(-inside, same));
        }
        // Beyond the cells both have, `upto` must not reach.
        let common = self.b.constant(s.cells.len().min(t.cells.len()) as i64, 32);
        agree.push(self.b.sle(upto, &common));
        self.b.all(&agree)
    }

    /// The String a compiler-generated concatenation (`StringConcatFactory.makeConcatWithConstants`, or
    /// `makeConcat`) makes of its arguments: Strings (`null` as "null"), `char`s, `int`s, `short`s and `byte`s (their
    /// decimal digits, [`Engine::decimal`]), and the recipe's constants, with the content of each in order. A
    /// `long`, a floating-point number or a boolean converted, or a String with no content, makes one with no
    /// content (their formatting is outside the model), and one that could have more than
    /// [`MAX_STRING_CONTENT`] code units has none either, its limit named.
    fn concatenation(&mut self, path: &mut Path, bootstrap: Option<&crate::classfile::BootstrapMethod>, descriptor: &MethodDescriptor, args: Vec<Val>) -> Result<usize, Stop> {
        enum Piece {
            Units(Vec<u16>),
            Content(Array),
        }
        let opaque = |engine: &mut Self, path: &mut Path, limit: Option<String>| {
            let r = engine.alloc(path, STRING);
            path.objects[r].limit = limit;
            Ok(r)
        };
        let mut pieces = Vec::new();
        let mut args = args.into_iter().zip(&descriptor.params);
        let mut argument = |engine: &mut Self, path: &Path, pieces: &mut Vec<Piece>| -> Result<Option<Option<String>>, Stop> {
            let (v, t) = args.next().ok_or_else(|| Stop::Unsupported("a concatenation recipe with more arguments than its call site".into()))?;
            match (t, v) {
                (t, Val::R(None)) if is_string(t) => pieces.push(Piece::Units("null".encode_utf16().collect())),
                (t, Val::R(Some(p))) if is_string(t) => match path.objects[p].content() {
                    Some(content) => pieces.push(Piece::Content(content.clone())),
                    None => return Ok(Some(path.objects[p].limit.clone())),
                },
                (Type::Char, Val::I(bits)) => {
                    let length = engine.b.constant(1, 32);
                    pieces.push(Piece::Content(Array { element: Type::Char, length, cells: vec![engine.b.trunc(&bits, 16)], refs: Vec::new() }));
                }
                // An int, a short or a byte is converted as `Integer.toString` converts it (JLS §5.1.11).
                (Type::Int | Type::Short | Type::Byte, Val::I(bits)) => {
                    let (length, cells) = engine.decimal(&bits);
                    pieces.push(Piece::Content(Array { element: Type::Char, length, cells, refs: Vec::new() }));
                }
                _ => return Ok(Some(None)),
            }
            Ok(None)
        };
        // What leaves the content unknown, if anything: the first such piece's limit, if it has one.
        let mut unknown: Option<Option<String>> = None;
        let with_constants = bootstrap.filter(|b| b.method.member.owner == "java/lang/invoke/StringConcatFactory" && b.method.member.name == "makeConcatWithConstants");
        match with_constants {
            Some(b) => {
                let Some(recipe) = b.args.first().and_then(BootstrapArg::string_units) else { return unsupported("a concatenation with no recipe") };
                let mut constants = b.args[1..].iter();
                for &unit in recipe.iter() {
                    match unit {
                        1 => {
                            if let Some(why) = argument(self, path, &mut pieces)? {
                                unknown.get_or_insert(why);
                            }
                        }
                        2 => match constants.next() {
                            Some(c @ (BootstrapArg::Str(_) | BootstrapArg::Units(_))) => pieces.push(Piece::Units(c.string_units().expect("a String constant").into_owned())),
                            Some(BootstrapArg::Int(v)) => pieces.push(Piece::Units(v.to_string().encode_utf16().collect())),
                            Some(BootstrapArg::Long(v)) => pieces.push(Piece::Units(v.to_string().encode_utf16().collect())),
                            _ => {
                                unknown.get_or_insert(None);
                            }
                        },
                        unit => pieces.push(Piece::Units(vec![unit])),
                    }
                }
            }
            None => {
                for _ in 0..descriptor.params.len() {
                    if let Some(why) = argument(self, path, &mut pieces)? {
                        unknown.get_or_insert(why);
                    }
                }
            }
        }
        if let Some(limit) = unknown {
            return opaque(self, path, limit);
        }
        let most: usize = pieces.iter().map(|p| match p {
            Piece::Units(u) => u.len(),
            Piece::Content(c) => c.cells.len(),
        }).sum();
        if most > MAX_STRING_CONTENT {
            return opaque(self, path, Some(format!("a concatenation of up to {most} code units, beyond the own checker's content cap of {MAX_STRING_CONTENT}: a named limit, not a truncated String")));
        }
        // Each piece's units at its offset, the sum of the lengths before it; a cell no piece reaches is past the length.
        let mut length = self.b.constant(0, 32);
        let mut cells = vec![self.b.constant(0, 16); most];
        for piece in pieces {
            let content = match piece {
                Piece::Units(units) => {
                    let length = self.b.constant(units.len() as i64, 32);
                    Array { element: Type::Char, length, cells: units.iter().map(|&u| self.b.constant(i64::from(u), 16)).collect(), refs: Vec::new() }
                }
                Piece::Content(c) => c,
            };
            for (i, unit) in content.cells.iter().enumerate() {
                let here = self.b.constant(i as i64, 32);
                let present = self.b.ult(&here, &content.length);
                let at = self.b.add(&length, &here);
                for (j, cell) in cells.iter_mut().enumerate() {
                    let target = self.b.constant(j as i64, 32);
                    let is = self.b.eq(&at, &target);
                    let writes = self.b.and(present, is);
                    if writes != FALSE {
                        *cell = self.b.ite_bits(writes, unit, cell);
                    }
                }
            }
            length = self.b.add(&length, &content.length);
        }
        path.objects.push(Obj { array: Some(Array { element: Type::Char, length, cells, refs: Vec::new() }), ..Obj::new(STRING) });
        Ok(path.objects.len() - 1)
    }

    /// The path reaches a gap: it is recorded with where, and under strict the path ends there (`Some(End::Gap)`);
    /// under assume the caller goes on with the approximation (`None`).
    fn meet(&mut self, path: &Path, kind: GapKind, owner: &str, name: &str, descriptor: &str) -> Option<End> {
        let site = site(path.frames.last().expect("a frame"));
        self.met.entry(Gap { kind, owner: owner.to_string(), name: name.to_string(), descriptor: descriptor.to_string() }).or_default().insert(site);
        (self.gap_mode.refuses() || !kind.assumable()).then_some(End::Gap)
    }

    /// The path reaches a gap a contract closes: recorded with where, for the verdict to say what it rests on.
    fn apply(&mut self, path: &Path, gap: Gap) {
        let site = site(path.frames.last().expect("a frame"));
        self.applied.entry(gap).or_default().insert(site);
    }

    /// A call of [`crate::gap_contracts::INTRINSICS`] from a contract's method: what bytecode cannot say.
    fn intrinsic(&mut self, path: &mut Path, name: &str, args: Vec<Val>) -> Step {
        match (name, args.as_slice()) {
            // The input is outside the contract's `assume:`: the gap is open, and met at the call the contract is
            // for, in the frame below the contract's method.
            ("open", [Val::I(index)]) => {
                let index = self.b.constant_value(index).ok_or_else(|| Stop::Unsupported("a contract's number is not a constant".into()))? as usize;
                let gap = self.contracts.iter().find(|(_, c)| c.contract.index == index).map(|(g, _)| g.clone()).ok_or_else(|| Stop::Unsupported(format!("no contract {index}")))?;
                let caller = path.frames.len().checked_sub(2).map(|i| path.frames[i].clone()).ok_or_else(|| Stop::Unsupported("a contract's method called from nowhere".into()))?;
                let assumable = gap.kind.assumable();
                self.met.entry(gap).or_default().insert(site(&caller));
                if self.gap_mode.refuses() || !assumable {
                    return Ok(Some(End::Gap));
                }
            }
            // The array's elements become any values: what the call wrote, which the assertion that follows
            // narrows. Its length is the length it had.
            ("havoc", [Val::R(Some(o))]) => {
                let Some(array) = path.objects[*o].as_array() else { return unsupported("a contract modifies an object that is not an array") };
                let width = cell_width(&array.element);
                let cells: Vec<Bits> = (0..array.cells.len()).map(|_| self.b.fresh(width)).collect();
                path.objects[*o].array.as_mut().expect("an array").cells = cells;
            }
            ("havoc", [Val::R(None)]) => return self.raise(path, "java/lang/NullPointerException"),
            // A primitive result: any value of the width, which the contract's method narrows to its type and its
            // assertion to what the contract states.
            ("anyInt", []) => {
                let v = self.b.fresh(32);
                self.push(path, Val::I(v));
            }
            ("anyLong", []) => {
                let v = self.b.fresh(64);
                self.push(path, Val::J(v));
            }
            // Either truth value, as the int a boolean is: no branch decides which.
            ("anyBoolean", []) => {
                let bit = self.b.fresh(1);
                let v = self.b.zext(&bit, 32);
                self.push(path, Val::I(v));
            }
            // No run of the call takes the path: what it returned does not satisfy the contract's assertion.
            ("infeasible", []) => return Ok(Some(End::Infeasible)),
            // An induction hypothesis used where it says nothing ([`crate::summary`]): the proof does not go through.
            ("unproved", []) => {
                return unsupported("the induction does not go through: a recursive call is reached whose arguments the hypothesis does not cover (outside the property's assumption or its bounds, or the measure not below the call's own and at least zero)");
            }
            // Whether two objects are of one class, as `a.getClass() == b.getClass()` is on the JVM: a proof of a
            // contract against the JDK's bytecode ([`crate::contract_proving`]) checks the exception's exact class.
            ("sameClass", [Val::R(Some(a)), Val::R(Some(b))]) => {
                let same = path.objects[*a].class == path.objects[*b].class;
                let v = self.b.constant(i64::from(same), 32);
                self.push(path, Val::I(v));
            }
            ("sameClass", [_, _]) => return self.raise(path, "java/lang/NullPointerException"),
            _ => return unsupported(format!("unknown intrinsic {name} of a contract")),
        }
        self.advance(path);
        Ok(None)
    }

    /// The path uses `class` in a way that initializes it (JVMS §5.5: `new`, `getstatic`, `putstatic`,
    /// `invokestatic`), from the instruction at the top frame: `None` when the class is initialized, or being
    /// initialized by an enclosing use, and the instruction goes on; otherwise what the instruction does instead,
    /// having pushed a `<clinit>` to run first (the instruction runs again when it returns), thrown
    /// `NoClassDefFoundError` for an erroneous class, or ended at a gap. The engine runs an application class's
    /// `<clinit>` when it is in the fragment ([`gaps::runs_initializer`]); any other is a `class-initializer` gap,
    /// which under assume, or closed by a contract that it throws nothing, is taken to have run. A JDK class is
    /// taken to be initialized already.
    fn initialise(&mut self, path: &mut Path, class: &str) -> Option<Step> {
        if !self.cp.checker_statics(class) {
            return None;
        }
        match self.initialise_class(path, class) {
            Ok(Initialising::Ready) => {
                debug_assert!(path.frames.last().expect("a frame").entered.is_empty());
                None
            }
            Ok(Initialising::Running) => Some(Ok(None)),
            Ok(Initialising::Erroneous) => Some(self.raise(path, "java/lang/NoClassDefFoundError")),
            Ok(Initialising::End(end)) => Some(Ok(Some(end))),
            Err(stop) => Some(Err(stop)),
        }
    }

    /// The procedure of JVMS §5.5 for `class`, from the top frame's instruction, resumed where it stopped each
    /// time a `<clinit>` it pushed returns.
    fn initialise_class(&mut self, path: &mut Path, class: &str) -> Result<Initialising, Stop> {
        let top = path.frames.len() - 1;
        match path.classes.get(class) {
            Some(ClassState::Done | ClassState::Assumed) => return Ok(Initialising::Ready),
            Some(ClassState::Erroneous) => return Ok(Initialising::Erroneous),
            // Being initialized by this thread, from an enclosing use: go on (step 3).
            Some(ClassState::InProgress) if !path.frames[top].entered.iter().any(|c| c == class) => return Ok(Initialising::Ready),
            // Begun by this instruction, which runs again: resume.
            Some(ClassState::InProgress) => {}
            None => {
                if !self.cp.checker_statics(class) {
                    return Ok(Initialising::Ready);
                }
                path.classes.insert(class.to_string(), ClassState::InProgress);
                path.frames[top].entered.push(class.to_string());
            }
        }
        let supers = match self.supers.get(class) {
            Some(s) => s.clone(),
            None => {
                let s = Rc::new(gaps::initialization_supers(self.cp, class));
                self.supers.insert(class.to_string(), s.clone());
                s
            }
        };
        for s in supers.iter() {
            match self.initialise_class(path, s)? {
                Initialising::Ready => {}
                other => return Ok(other),
            }
        }
        path.frames[top].entered.retain(|c| c != class);
        let Some(cf) = self.cp.checker_class(class) else {
            path.classes.insert(class.to_string(), ClassState::Done);
            return Ok(Initialising::Ready);
        };
        if self.is_observed(class) {
            if self.in_summary(path) {
                return unsupported(format!("the method initializes the class {}, whose initializer is observed, {}", class.replace('/', "."), self.result_only()));
            }
            self.take_observed(path, class)?;
            path.classes.insert(class.to_string(), ClassState::Done);
            return Ok(Initialising::Ready);
        }
        if cf.method("<clinit>", "()V").is_none() {
            path.classes.insert(class.to_string(), ClassState::Done);
            return Ok(Initialising::Ready);
        }
        let runs = match self.runs.get(class) {
            Some(&r) => r,
            None => {
                let r = gaps::runs_initializer(self.cp, class);
                self.runs.insert(class.to_string(), r);
                r
            }
        };
        if self.in_summary(path) {
            let (owner, name, _) = self.pure.as_ref().expect("in a summary");
            return unsupported(format!("{}.{name} initializes the class {}, {}", owner.replace('/', "."), class.replace('/', "."), self.result_only()));
        }
        if runs {
            self.call(path, class, "<clinit>", "()V", Vec::new())?;
            path.frames.last_mut().expect("a frame").initializes = Some(class.to_string());
            return Ok(Initialising::Running);
        }
        let gap = Gap { kind: GapKind::ClassInitializer, owner: class.to_string(), name: "<clinit>".into(), descriptor: "()V".into() };
        if self.contracts.get(&gap).is_some_and(|k| k.how == Closing::Initialised) {
            self.apply(path, gap);
        } else if let Some(end) = self.meet(path, GapKind::ClassInitializer, class, "<clinit>", "()V") {
            return Ok(Initialising::End(end));
        }
        path.classes.insert(class.to_string(), ClassState::Assumed);
        Ok(Initialising::Ready)
    }

    /// The value of the static field `name` that `declaring`, an application class, declares, once the class is
    /// initialized: what the path wrote, else its `ConstantValue`, else zero or null. `None` for a JDK class, read
    /// by [`Engine::get_static`]. A class taken to be initialized has only its constants.
    fn application_static(&mut self, path: &mut Path, declaring: &str, name: &str, descriptor: &str) -> Option<Result<Val, Stop>> {
        if !self.cp.checker_statics(declaring) {
            return None;
        }
        if path.classes.get(declaring) == Some(&ClassState::Assumed) {
            return Some(self.get_static(declaring, name, descriptor));
        }
        if let Some(v) = path.statics.get(&(declaring.to_string(), name.to_string())) {
            return Some(Ok(v.clone()));
        }
        if let Some(refused) = self.unheld_static(path, declaring, name) {
            return Some(unsupported(refused));
        }
        let constant = self.cp.checker_class(declaring).and_then(|cf| {
            let field = cf.field(name).filter(|f| f.is_static())?;
            let attr = field.attributes.iter().find(|a| a.name == "ConstantValue").filter(|a| a.data.len() == 2)?;
            cf.pool.loadable(u16::from_be_bytes([attr.data[0], attr.data[1]])).ok()
        });
        Some(match constant {
            Some(BootstrapArg::Int(v)) => Ok(Val::I(self.b.constant(i64::from(v), 32))),
            Some(BootstrapArg::Long(v)) => Ok(Val::J(self.b.constant(v, 64))),
            Some(loaded @ (BootstrapArg::Str(_) | BootstrapArg::Units(_))) => {
                let units = loaded.string_units().expect("a String constant").into_owned();
                let o = self.literal(path, Literal::Str(units), "java/lang/String");
                Ok(Val::R(Some(o)))
            }
            Some(_) => unsupported("floating point"),
            None => self.default_value(descriptor),
        })
    }

    /// The object a string or class literal is on this path: made at its first load, a string with its content.
    fn literal(&mut self, path: &mut Path, literal: Literal, class: &str) -> usize {
        if let Some(&o) = path.literals.get(&literal) {
            return o;
        }
        let o = match &literal {
            Literal::Str(units) => {
                let units = units.clone();
                self.string(path, &units)
            }
            Literal::Class(_) | Literal::Loader | Literal::Logger(_) | Literal::Charset(_) | Literal::Locale(_) | Literal::Level(_) | Literal::Thread | Literal::EmptyMap => self.alloc(path, class),
        };
        path.literals.insert(literal, o);
        o
    }

    /// A new String of these code units.
    fn string(&mut self, path: &mut Path, units: &[u16]) -> usize {
        let length = self.b.constant(units.len() as i64, 32);
        let cells = units.iter().map(|&u| self.b.constant(i64::from(u), 16)).collect();
        path.objects.push(Obj { array: Some(Array { element: Type::Char, length, cells, refs: Vec::new() }), ..Obj::new(STRING) });
        path.objects.len() - 1
    }

    /// The key the instance field `owner.name:descriptor` has in object `o`: its name, unless a subclass along the
    /// object's class declares the name again ([`ClassPath::field_key`]), as the interpreter keys it.
    fn field_key(&mut self, path: &Path, o: usize, owner: &str, name: &str, descriptor: &str) -> Result<String, Stop> {
        let class = &path.objects[o].class;
        let hides = match self.hides.get(class) {
            Some(&h) => h,
            None => {
                let h = self.cp.hides_fields(class);
                self.hides.insert(class.clone(), h);
                h
            }
        };
        if !hides {
            return Ok(name.to_string());
        }
        let declaring = self.cp.resolve_field(owner, name, descriptor).ok_or_else(|| Stop::Unsupported(format!("no field {}.{name}", owner.replace('/', "."))))?;
        Ok(self.cp.field_key(class, &declaring, name))
    }

    fn default_value(&self, descriptor: &str) -> Result<Val, Stop> {
        Ok(match Type::parse(descriptor).map_err(|e| Stop::Unsupported(e.to_string()))? {
            Type::Long => Val::J(self.b.constant(0, 64)),
            Type::Float | Type::Double => return unsupported("floating point"),
            Type::Object(_) | Type::Array(_) => Val::R(None),
            _ => Val::I(self.b.constant(0, 32)),
        })
    }

    fn get_static(&mut self, owner: &str, name: &str, descriptor: &str) -> Result<Val, Stop> {
        // A JDK constant javac did not inline (none in practice: these are compile-time constants).
        let known: Option<Val> = match (owner, name) {
            ("java/lang/Integer", "MAX_VALUE") => Some(Val::I(self.b.constant(i64::from(i32::MAX), 32))),
            ("java/lang/Integer", "MIN_VALUE") => Some(Val::I(self.b.constant(i64::from(i32::MIN), 32))),
            ("java/lang/Long", "MAX_VALUE") => Some(Val::J(self.b.constant(i64::MAX, 64))),
            ("java/lang/Long", "MIN_VALUE") => Some(Val::J(self.b.constant(i64::MIN, 64))),
            _ => None,
        };
        if let Some(v) = known {
            return Ok(v);
        }
        // An application constant with a ConstantValue attribute (a static final primitive initialised by a
        // literal); any other static is state the engine does not model.
        let Ok(Some(class)) = self.cp.bytecode(owner) else { return unsupported(format!("reads static field {}.{name}", owner.replace('/', "."))) };
        let Some(field) = class.field(name).filter(|f| f.is_static()) else { return unsupported(format!("reads static field {}.{name}", owner.replace('/', "."))) };
        let Some(attr) = field.attributes.iter().find(|a| a.name == "ConstantValue").filter(|a| a.data.len() == 2) else {
            return unsupported(format!("reads static field {}.{name}, which is not a compile-time constant", owner.replace('/', ".")));
        };
        let index = u16::from_be_bytes([attr.data[0], attr.data[1]]);
        Ok(match (class.pool.loadable(index), Type::parse(descriptor)) {
            (Ok(BootstrapArg::Int(v)), _) => Val::I(self.b.constant(i64::from(v), 32)),
            (Ok(BootstrapArg::Long(v)), _) => Val::J(self.b.constant(v, 64)),
            _ => return unsupported(format!("reads static field {}.{name}", owner.replace('/', "."))),
        })
    }

    fn pop_args(&self, path: &mut Path, count: usize) -> Result<Vec<Val>, Stop> {
        let mut args = Vec::with_capacity(count);
        for _ in 0..count {
            args.push(self.pop(path)?);
        }
        args.reverse();
        Ok(args)
    }

    /// An `invokestatic` of `member` from the class `caller`, its arguments on the stack: an application method or
    /// a model's is called, a JDK method the engine models is computed, and any other is a gap or refused. A
    /// lambda's call of the method it stands for comes here too ([`Engine::lambda_call`]).
    fn invoke_static(&mut self, path: &mut Path, caller: &str, member: &crate::classfile::MemberRef) -> Step {
        let descriptor = MethodDescriptor::parse(&member.descriptor).map_err(|e| Stop::Unsupported(e.to_string()))?;
        // A model only for JBMC's class path that the checker runs all the same ([`ClassPath::checker_runs`]:
        // `List.of`, `List.copyOf` and the immutable lists' helpers) is called as an application method, unless
        // no evidence record samples the call (`List.of(E...)`), which is then the JDK call it names
        // ([`gaps::outside_the_list_records`]).
        let runs_model = !self.cp.is_application(&member.owner) && self.cp.checker_runs(&member.owner) && self.cp.checker_method(&member.owner, &member.name, &member.descriptor).is_some_and(|(cf, m)| self.cp.checker_runs(&cf.name) && m.code.is_some() && !gaps::outside_the_list_records(caller, &cf.name, &member.name, &member.descriptor));
        if runs_model || (self.cp.is_application(&member.owner) && member.owner != crate::gap_contracts::INTRINSICS) {
            // The class that declares the method is initialized first (JVMS §5.5), the arguments still on
            // the stack, so that the instruction can run again once its initializer returns.
            let declaring = if runs_model { self.cp.checker_method(&member.owner, &member.name, &member.descriptor).map(|(cf, _)| cf.name.clone()) } else { self.cp.bytecode_method(&member.owner, &member.name, &member.descriptor).map(|(cf, _)| cf.name.clone()) }.unwrap_or_else(|| member.owner.clone());
            if let Some(step) = self.initialise(path, &declaring) {
                return step;
            }
            // A summary of the method, or the hypothesis of its own proof, in place of a call that is neither the
            // harness's nor the claim's ([`Summary`]).
            let summary = self.summaries.iter().find(|s| s.owner == member.owner && s.name == member.name && s.descriptor == member.descriptor).map(|s| s.stub.clone());
            // Not while any class is still being initialized: the lemma was proved of classes initialized, and a
            // final field it reads, of its method's class or of any other (a superclass whose initializer calls
            // it, a class its assumption reads), may not be written yet. The call then runs as written.
            let initialized = !path.classes.values().any(|s| *s == ClassState::InProgress);
            if let Some(stub) = summary.filter(|_| initialized && caller != crate::harness::expr::CLAIM_CLASS && caller != path.frames[0].class.name) {
                if let Some(step) = self.initialise(path, crate::harness::expr::CLAIM_CLASS) {
                    return step;
                }
                let args = self.pop_args(path, descriptor.params.len())?;
                return self.call(path, crate::harness::expr::CLAIM_CLASS, &stub, &member.descriptor, args);
            }
            let args = self.pop_args(path, descriptor.params.len())?;
            return self.call(path, &member.owner, &member.name, &member.descriptor, args);
        }
        // The JDK's methods and the intrinsics take known references, but for a call that only stores the
        // reference ([`locale::takes_a_choice`]).
        if !locale::takes_a_choice(&member.owner, &member.name, &member.descriptor) {
            for depth in 0..descriptor.params.len() {
                if let Some(step) = self.concrete_ref(path, depth) {
                    return step;
                }
            }
        }
        let args = self.pop_args(path, descriptor.params.len())?;
        if member.owner == crate::gap_contracts::INTRINSICS {
            return self.intrinsic(path, &member.name, args);
        }
        // A JDK call that enters a model by the model's own method (`Arrays.stream`, [`crate::models::entry`]).
        if let Some((class, method, entry)) = crate::models::entry(&member.owner, &member.name, &member.descriptor) {
            return self.call(path, class, method, entry, args);
        }
        // A JDK class the tool models (Character.digit, say) runs as bytecode here too, so that the
        // engine and the interpreter that replays its witnesses agree on it.
        if self.cp.model(&member.owner).is_some() && self.cp.bytecode_method(&member.owner, &member.name, &member.descriptor).is_some_and(|(_, m)| m.code.is_some()) {
            return self.call(path, &member.owner, &member.name, &member.descriptor, args);
        }
        match gaps::jdk_static_call(&member.owner, &member.name, &member.descriptor) {
            JdkCall::Exact => return self.call_jdk_static(path, &member.owner, &member.name, &member.descriptor, &descriptor, args),
            JdkCall::Refused => return unsupported(format!("{}.{}{}", member.owner.replace('/', "."), member.name, member.descriptor)),
            JdkCall::Gap(kind) => {
                let gap = Gap { kind, owner: member.owner.clone(), name: member.name.clone(), descriptor: member.descriptor.clone() };
                if let Some(Closure { how: Closing::Stub { method, descriptor: stub, .. }, .. }) = self.contracts.get(&gap).cloned() {
                    self.apply(path, gap);
                    return self.call(path, crate::gap_contracts::CLASS, &method, &stub, args);
                }
                // No approximation: the path ends here in every mode.
                return Ok(self.meet(path, kind, &member.owner, &member.name, &member.descriptor));
            }
        }
    }

    /// The call of a lambda's object `o` (at `receiver_at` on the stack, the call's arguments above it) by its
    /// interface's method, of descriptor `called`: the object is replaced by the values it captured, and the
    /// method it stands for is invoked as the instruction for its kind would (JVMS §5.4.3.5), so that an
    /// application method runs, a JDK method is modelled, a gap or refused, as anywhere else. The class of a
    /// static method is initialized first, the stack still as the interface call left it, since the instruction
    /// runs again once an initializer returns. A call that would convert between a primitive and its box, or
    /// drop a result, is refused; the cast the JVM's own lambda class makes of a reference argument is made where
    /// the object is known.
    fn lambda_call(&mut self, path: &mut Path, caller: &str, o: usize, receiver_at: usize, lambda: &Lambda, called: &MethodDescriptor) -> Step {
        let target = &lambda.handle.member;
        let Ok(mut takes) = MethodDescriptor::parse(&target.descriptor) else { return unsupported("a lambda's method with no descriptor") };
        let kind = lambda.handle.kind;
        let returns = match kind {
            8 => Type::Object(target.owner.clone()),
            _ => takes.ret.clone(),
        };
        // An instance method takes its receiver first, among the captured values or the call's arguments.
        if matches!(kind, 5 | 7 | 9) {
            takes.params.insert(0, Type::Object(target.owner.clone()));
        }
        if !matches!(kind, 5..=9) || takes.params.len() != lambda.captured + called.params.len() {
            return unsupported(format!("a lambda that stands for {}.{} in a way the engine does not run (method handle kind {kind})", target.owner.replace('/', "."), target.name));
        }
        let fits = |from: &Type, to: &Type| match (from, to) {
            (Type::Object(_) | Type::Array(_), Type::Object(_) | Type::Array(_)) => true,
            (a, b) => a == b,
        };
        if !called.params.iter().zip(&takes.params[lambda.captured..]).all(|(a, b)| fits(a, b)) || !fits(&returns, &called.ret) {
            return unsupported(format!("a lambda whose call of {}.{} converts between a primitive and its box, or drops its result", target.owner.replace('/', "."), target.name));
        }
        if kind == 6 || kind == 8 {
            let declaring = self.cp.bytecode_method(&target.owner, &target.name, &target.descriptor).map(|(cf, _)| cf.name.clone()).unwrap_or_else(|| target.owner.clone());
            if let Some(step) = self.initialise(path, &declaring) {
                return step;
            }
        }
        // Each reference argument is known before the call is made of it: its cast below reads its class, and
        // the method called may need it known, which it could no longer ask of this instruction once the
        // receiver is gone from the stack (a split runs the instruction again).
        for depth in 0..called.params.len() {
            if let Some(step) = self.concrete_ref(path, depth) {
                return step;
            }
        }
        // The cast of each reference argument to the type the method takes.
        let stack = &path.frames.last().expect("a frame").stack;
        for (v, t) in stack[receiver_at + 1..].iter().zip(&takes.params[lambda.captured..]) {
            if let (Val::R(Some(a)), Type::Object(_) | Type::Array(_)) = (v, t) {
                if !self.cp.is_subtype(&path.objects[*a].class, &class_of(t)) {
                    let args = called.params.len();
                    self.pop_args(path, args)?;
                    self.pop(path)?;
                    return self.raise(path, "java/lang/ClassCastException");
                }
            }
        }
        let captured: Vec<Val> = (0..lambda.captured).map(|i| path.objects[o].fields.get(&captured_key(i)).cloned().ok_or_else(|| Stop::Unsupported("a lambda with a captured value missing".into()))).collect::<Result<_, _>>()?;
        // A captured reference that is not known could not be made known by the call either.
        if captured.iter().any(|v| matches!(v, Val::C(_))) && !(kind == 6 && self.cp.is_application(&target.owner)) {
            return unsupported(format!("a lambda that stands for {}.{} and captured a reference that is one of several objects", target.owner.replace('/', "."), target.name));
        }
        let made = (kind == 8).then(|| self.alloc(path, &target.owner));
        let stack = &mut path.frames.last_mut().expect("a frame").stack;
        let mut replaced: Vec<Val> = Vec::new();
        if let Some(r) = made {
            // `new`, `dup`: the object stays under the constructor's receiver and is the call's result.
            replaced.extend([Val::R(Some(r)), Val::R(Some(r))]);
        }
        replaced.extend(captured);
        stack.splice(receiver_at..=receiver_at, replaced);
        match kind {
            6 => self.invoke_static(path, caller, target),
            _ => self.invoke_instance(path, caller, matches!(kind, 7 | 8), target),
        }
    }

    /// An `invokespecial`, `invokevirtual` or `invokeinterface` of `member` from the class `caller`, the receiver
    /// and the arguments on the stack.
    fn invoke_instance(&mut self, path: &mut Path, caller: &str, special: bool, member: &crate::classfile::MemberRef) -> Step {
        let descriptor = MethodDescriptor::parse(&member.descriptor).map_err(|e| Stop::Unsupported(e.to_string()))?;
        // The receiver is dispatched on, so it is known first; so are the arguments of a call that is not
        // into the application, whose models and contracts take known references.
        if let Some(step) = self.concrete_ref(path, descriptor.params.len()) {
            return step;
        }
        let Some(receiver_at) = path.frames.last().expect("a frame").stack.len().checked_sub(1 + descriptor.params.len()) else {
            let top = path.frames.last().expect("a frame");
            return unsupported(format!("a call of {}.{} in {}.{} with fewer values on the stack than it takes", member.owner.replace('/', "."), member.name, top.class.name.replace('/', "."), top.method));
        };
        // A lambda's object, called by its interface's method: the method it stands for runs ([`Lambda`]).
        if let Val::R(Some(o)) = path.frames.last().expect("a frame").stack[receiver_at] {
            if let Some(lambda) = path.objects[o].lambda.clone().filter(|l| !special && l.name == member.name) {
                return self.lambda_call(path, caller, o, receiver_at, &lambda, &descriptor);
            }
        }
        if let Val::R(Some(o)) = path.frames.last().expect("a frame").stack[receiver_at] {
            let owner = if special { member.owner.clone() } else { path.objects[o].class.clone() };
            let application = self.cp.checker_method(&owner, &member.name, &member.descriptor).is_some_and(|(cf, m)| self.cp.checker_runs(&cf.name) && m.code.is_some() && !gaps::outside_the_list_records(caller, &cf.name, &member.name, &member.descriptor));
            if !application {
                for depth in 0..descriptor.params.len() {
                    if let Some(step) = self.concrete_ref(path, depth) {
                        return step;
                    }
                }
            }
        }
        let args = self.pop_args(path, descriptor.params.len())?;
        let receiver = self.pop_ref(path)?;
        let o = match self.null_check(path, receiver) {
            Ok(o) => o.expect("checked"),
            Err(step) => return step,
        };
        let special = special;
        // An array's `clone`: a new array of the same class, length and elements (JLS §10.7).
        if !special && member.name == "clone" && member.descriptor == "()Ljava/lang/Object;" && path.objects[o].is_array() {
            let copy = Obj { array: path.objects[o].array.clone(), unknown: path.objects[o].unknown, ..Obj::new(&path.objects[o].class) };
            path.objects.push(copy);
            let r = path.objects.len() - 1;
            self.push(path, Val::R(Some(r)));
            self.advance(path);
            return Ok(None);
        }
        // A String method the engine models on the content it holds, whichever type the call names: a
        // String's `equals` and `hashCode` are its own when a map calls them on a key it holds as an Object.
        if !special && path.objects[o].class == STRING {
            if let Some(step) = self.string_method(path, o, &member.name, &member.descriptor, &args) {
                return step;
            }
        }
        // A contract given for the call stands in place of the engine's own model of it ([`gaps::modelled_jdk_call`]):
        // the call is then the gap it is to a checker with no such model, closed as the contract says.
        let unmodelled = gaps::unmodelled_instance_call(self.cp, &member.owner, &member.name, &member.descriptor);
        let contracted = matches!(&unmodelled, JdkCall::Gap(kind) if self.contracts.contains_key(&Gap { kind: *kind, owner: member.owner.clone(), name: member.name.clone(), descriptor: member.descriptor.clone() }));
        if !contracted {
            // A StringBuilder's constructors and methods on the content it holds ([`strings`]).
            if let Some(step) = self.builder_method(path, o, &member.name, &member.descriptor, &args) {
                return step;
            }
            // A class literal's name and loader ([`runtime`]).
            if let Some(step) = self.class_method(path, o, &member.owner, &member.name, &member.descriptor) {
                return step;
            }
            // Whether a class is another's or below it, of two class literals ([`runtime`]).
            if let Some(step) = self.class_relation(path, o, &member.name, &member.descriptor, &args) {
                return step;
            }
            // Whether a Logger logs a level below `INFO` ([`runtime`]).
            if let Some(step) = self.logger_method(path, o, &member.owner, &member.name, &member.descriptor, &args) {
                return step;
            }
            // A constructor that takes a capacity alone ([`runtime::capacity_constructor`]).
            if let (true, [Val::I(capacity)]) = (special && member.name == "<init>" && runtime::capacity_constructor(&member.owner, &member.descriptor), args.as_slice()) {
                let negative = self.b.negative(capacity);
                return self.branch_throw_or(path, negative, "java/lang/IllegalArgumentException", |engine, path| engine.advance(path));
            }
        }
        // A Pattern's `matcher` and a Matcher's `matches`, of a Pattern the engine holds the pieces of ([`regex`]).
        if let Some(step) = self.regex_method(path, o, &member.name, &member.descriptor, &args) {
            return step;
        }
        // On any other Class object (a JDK class's loader, a class no literal names) it is the JDK call.
        if !contracted && runtime::models_instance(&member.owner, &member.name, &member.descriptor) {
            if let Some(end) = self.meet(path, GapKind::JdkReferenceMethod, &member.owner, &member.name, &member.descriptor) {
                return Ok(Some(end));
            }
            if let Type::Object(name) = &descriptor.ret {
                let r = self.alloc(path, name);
                self.push(path, Val::R(Some(r)));
            }
            self.advance(path);
            return Ok(None);
        }
        let owner = if special { member.owner.clone() } else { path.objects[o].class.clone() };
        // An application method, or one of `java.lang.Enum`'s or the immutable lists', which their models run
        // ([`ClassPath::checker_runs`]); a list model's method no evidence record samples is the JDK call it
        // names, called from outside the models ([`gaps::outside_the_list_records`]).
        if let Some((cf, m)) = self.cp.checker_method(&owner, &member.name, &member.descriptor).filter(|(cf, _)| self.cp.checker_runs(&cf.name) && !gaps::outside_the_list_records(caller, &cf.name, &member.name, &member.descriptor)) {
            if m.code.is_some() {
                let mut full = vec![Val::R(Some(o))];
                full.extend(args);
                return self.call(path, &cf.name, &member.name, &member.descriptor, full);
            }
        }
        // A JDK method on an opaque object: reproduced exactly (an exception's constructor), a gap, or, with
        // a floating-point or array result, refused. Under assume, a constructor does nothing, a void method
        // nothing, and a method that returns an object returns a new one; one that returns a primitive has
        // no approximation, and is refused there too.
        // A builder's call that its model did not take (the builder's content is not the engine's) is the call
        // it is to a checker with no such model.
        match if contracted || strings::models_builder(&member.owner, &member.name, &member.descriptor) { unmodelled } else { gaps::jdk_instance_call(self.cp, &member.owner, &member.name, &member.descriptor) } {
            JdkCall::Exact => {}
            JdkCall::Gap(kind) => {
                // What the call does to a builder is the contract's or the assumption's to say: the engine holds
                // its content no longer, and a later call it models on that content is refused by name.
                if path.objects[o].class == strings::BUILDER {
                    path.objects[o].array = None;
                }
                let gap = Gap { kind, owner: member.owner.clone(), name: member.name.clone(), descriptor: member.descriptor.clone() };
                if let Some(Closure { how: Closing::Stub { method, descriptor: stub, receiver }, .. }) = self.contracts.get(&gap).cloned() {
                    // A contract closes the gap: its method of the generated class runs in place of the call.
                    self.apply(path, gap);
                    let mut full = Vec::new();
                    if receiver {
                        full.push(Val::R(Some(o)));
                    }
                    full.extend(args);
                    return self.call(path, crate::gap_contracts::CLASS, &method, &stub, full);
                }
                if let Some(end) = self.meet(path, kind, &member.owner, &member.name, &member.descriptor) {
                    return Ok(Some(end));
                }
                if let Type::Object(name) = &descriptor.ret {
                    let r = self.alloc(path, name);
                    self.push(path, Val::R(Some(r)));
                }
            }
            JdkCall::Refused => return unsupported(format!("{}.{} on an object the engine does not model", member.owner.replace('/', "."), member.name)),
        }
        self.advance(path);
        Ok(None)
    }

    /// Calls an application method: a new frame with the arguments in its locals.
    fn call(&mut self, path: &mut Path, owner: &str, name: &str, descriptor: &str, args: Vec<Val>) -> Step {
        let (cf, m) = self.cp.checker_method(owner, name, descriptor).ok_or_else(|| Stop::Unsupported(format!("method not found: {}.{name}{descriptor}", owner.replace('/', "."))))?;
        if m.is_abstract() {
            return unsupported(format!("{}.{name} is abstract", cf.name.replace('/', ".")));
        }
        if path.frames.len() >= 64 {
            return unsupported("calls nested deeper than 64 (unbounded recursion?)");
        }
        let code = self.code(&cf, name, descriptor)?;
        let mut locals: Vec<Option<Val>> = Vec::with_capacity(code.max_locals);
        for a in args {
            let wide = a.category() == 2;
            locals.push(Some(a));
            if wide {
                locals.push(None);
            }
        }
        locals.resize(code.max_locals.max(locals.len()), None);
        // What is there when the harness calls the method was there before the call; and so was what is there
        // when it calls the lemma's assumption, before that.
        if path.frames.len() == 1 && (owner == crate::harness::expr::CLAIM_CLASS && self.pure.is_some() || self.pure.as_ref().is_some_and(|(o, n, d)| o == owner && n == name && d == descriptor)) {
            path.objects.iter_mut().for_each(|o| o.given = true);
        }
        // And, in a lemma's proof, what is there when a class initializer starts: a caller may initialize the
        // class later than the proof does, after changing what was there ([`Engine::in_lemma`]).
        if name == "<clinit>" && self.pure.is_some() && !self.own_induction {
            path.objects.iter_mut().for_each(|o| o.given = true);
        }
        // A model run on request is what the result then rests on.
        if let Some(model) = crate::models::on_request(&cf.name).filter(|_| !self.cp.is_application(&cf.name)) {
            self.assumed.insert(crate::models::requested_assumption(model));
        }
        path.frames.push(Frame::new(cf.clone(), name.to_string(), code, locals));
        Ok(None)
    }

    /// Whether the path is inside the method the check proves a summary of ([`Options::pure`]), called by the
    /// harness. A summary states the method's result and nothing else, so the proof of one also shows that the
    /// method changes nothing a caller could see, and that its result does not depend on which objects its
    /// arguments are: inside it, a write to a static field, to an object that was there before the call
    /// ([`Obj::given`]) or to its array, the initialization of a class that has an initializer, and a comparison by
    /// identity of such an object that is no literal, each end the run with no verdict ([`Engine::keeps`],
    /// [`Engine::compares`]).
    fn in_summary(&self, path: &Path) -> bool {
        self.pure.as_ref().is_some_and(|(owner, name, _)| path.frames.get(1).is_some_and(|f| f.class.name == *owner && f.method == *name))
    }

    /// Refuses, inside a summarized method, a write to the object `o` when it was there before the call (`None`:
    /// to a static field).
    fn keeps(&self, path: &Path, o: Option<usize>, what: &str) -> Result<(), Stop> {
        if self.in_summary(path) && o.map_or(true, |o| path.objects[o].given) {
            let (owner, name, _) = self.pure.as_ref().expect("in a summary");
            return unsupported(format!("{}.{name} {what}, {}", owner.replace('/', "."), self.result_only()));
        }
        Ok(())
    }

    /// Why a method that does more than return is refused: what would stand in for its calls states a result.
    fn result_only(&self) -> &'static str {
        if self.own_induction {
            "and the induction hypothesis states the result of its calls of itself only: it is not a method proved by induction on a measure (--decreases)"
        } else {
            "and a summary of it would state its result only: it is not a method a summary can stand in for"
        }
    }

    /// Whether the path is where a lemma must read nothing a caller can change: inside the method the check proves
    /// a summary of, or inside the lemma's own assumption or assertion, which the harness calls in the claim's
    /// class and the summary evaluates again at each call it stands in for, in the state that call is made in, or
    /// inside a class initializer the proof runs (the method's class and its superclasses, which the harness
    /// initializes, or a class the assumption uses): the lemma may read a final static field such an initializer
    /// writes, and a caller may initialize the class after changing what the initializer reads (a static field,
    /// an object, the default locale), so that the field is not what it was in the proof.
    /// Never in a proof by induction alone ([`Options::own_induction`]).
    fn in_lemma(&self, path: &Path) -> bool {
        self.pure.is_some() && !self.own_induction && (self.in_summary(path) || path.frames.get(1).is_some_and(|f| f.class.name == crate::harness::expr::CLAIM_CLASS) || self.initializer(path).is_some())
    }

    /// The class whose initializer the path is innermost in, if any.
    fn initializer<'p>(&self, path: &'p Path) -> Option<&'p str> {
        path.frames.iter().rev().find(|f| f.method == "<clinit>").map(|f| f.class.name.as_str())
    }

    /// Refuses, in a lemma's proof ([`Engine::in_lemma`]), a read of what a caller can change before it calls: a
    /// static field that is not final, a field that is not final or a cell of an object that was there before the
    /// call ([`Obj::given`]: with arguments that are primitives and Strings, one a static field leads to), the
    /// default locale. The lemma is proved from the state the harness starts in and its summary is used at every
    /// call, whatever was written before it, so a result or a statement that depends on such a read is no
    /// function of the arguments.
    fn reads(&self, path: &Path, what: impl FnOnce() -> String) -> Result<(), Stop> {
        if self.in_lemma(path) {
            let (owner, name, _) = self.pure.as_ref().expect("in a lemma");
            if !self.in_summary(path) {
                if let Some(class) = self.initializer(path) {
                    return unsupported(format!("the initializer of {}, which the proof of the lemma about {}.{name} runs, {}, which a caller can change before it initializes the class, and a summary would state the method's result as one of its arguments only, whatever the final static fields that initializer writes then hold: it is not a method a summary can stand in for", class.replace('/', "."), owner.replace('/', "."), what()));
                }
            }
            let reader = if self.in_summary(path) { format!("{}.{name}", owner.replace('/', ".")) } else { format!("the lemma about {}.{name}, in its assumption or its assertion,", owner.replace('/', ".")) };
            return unsupported(format!("{reader} {}, which a caller can change before it calls, and a summary would state the method's result as one of its arguments only: it is not a method a summary can stand in for", what()));
        }
        Ok(())
    }

    /// Whether the field `name` of `owner` (or of the class it inherits it from) is final; a field not found is
    /// taken not to be.
    fn final_field(&self, owner: &str, name: &str, descriptor: &str) -> bool {
        let declaring = self.cp.resolve_field(owner, name, descriptor).unwrap_or_else(|| owner.to_string());
        matches!(self.cp.load(&declaring), Ok(Some(loaded)) if loaded.class.field(name).is_some_and(|f| f.is_final()))
    }

    /// Refuses, inside a summarized method, a comparison by identity of a reference that may be an object that was
    /// there before the call, a literal aside (which is the same object whoever calls).
    fn compares(&self, path: &Path, v: &Val) -> Result<(), Stop> {
        if !self.in_summary(path) {
            return Ok(());
        }
        let given = |o: usize| path.objects[o].given && !path.literals.values().any(|&l| l == o);
        let may_be_given = v.options().is_some_and(|options| options.iter().filter_map(|(_, t)| *t).any(|o| given(o) || path.objects[o].same.iter().any(|(_, t)| given(*t))));
        if may_be_given {
            let (owner, name, _) = self.pure.as_ref().expect("in a summary");
            let stands_in = if self.own_induction { "it is not a method proved by induction on a measure (--decreases)" } else { "it is not a method a summary can stand in for" };
            return unsupported(format!("{}.{name} compares an object it was given by identity (==), so its result may depend on which objects its arguments are: {stands_in}", owner.replace('/', ".")));
        }
        Ok(())
    }

    fn compare(&mut self, cond: Cond, x: &Bits, y: &Bits) -> Lit {
        match cond {
            Cond::Eq => self.b.eq(x, y),
            Cond::Ne => -self.b.eq(x, y),
            Cond::Lt => self.b.slt(x, y),
            Cond::Ge => -self.b.slt(x, y),
            Cond::Gt => self.b.slt(y, x),
            Cond::Le => -self.b.slt(y, x),
        }
    }

    /// A conditional jump to `target`, else fall through.
    fn conditional(&mut self, path: &mut Path, c: Lit, target: u32) -> Step {
        let frame = path.frames.last().expect("a frame");
        let then = *frame.code.index.get(&target).ok_or_else(|| Stop::Unsupported(format!("jump to no instruction at pc {target}")))?;
        let fall = frame.at + 1;
        let backward = then <= frame.at;
        if backward {
            // Count the back edge on the side that takes it; `jump` does the counting once the side is chosen.
            match self.sides(path, c)? {
                Sides::Both { then_models, else_models } => {
                    let mut twin = self.split(path, c, then_models, else_models, false);
                    twin.frames.last_mut().expect("a frame").at = fall;
                    self.pending.push(twin);
                    return self.jump(path, target);
                }
                Sides::Then => {
                    path.cond.push(c);
                    return self.jump(path, target);
                }
                Sides::Else => {
                    path.cond.push(-c);
                    path.frames.last_mut().expect("a frame").at = fall;
                    return Ok(None);
                }
                Sides::Undecided { model_takes_then: true } => {
                    let mut twin = self.split_undecided(path, c, true);
                    twin.frames.last_mut().expect("a frame").at = fall;
                    self.pending.push(twin);
                    return self.jump(path, target);
                }
                Sides::Undecided { model_takes_then: false } => {
                    let mut twin = self.split_undecided(path, c, false);
                    if let Some(end) = self.jump(&mut twin, target)? {
                        // The twin hit the unwinding bound, which counts only if it is feasible.
                        if !matches!(end, End::Infeasible) {
                            if let Some(twin) = self.settle(twin)? {
                                *path = twin;
                                return Ok(Some(end));
                            }
                        }
                    } else {
                        self.pending.push(twin);
                    }
                    path.frames.last_mut().expect("a frame").at = fall;
                    return Ok(None);
                }
            }
        }
        self.branch(path, c, then, fall)
    }

    /// A switch: each case in turn is a branch on `key == case`, the matching twin jumping to its target and the
    /// path going on to the next case; the last falls to the default.
    fn switch(&mut self, path: &mut Path, key: Bits, cases: &[(i32, u32)], default: u32) -> Step {
        for &(value, target) in cases {
            let k = self.b.constant(i64::from(value), 32);
            let c = self.b.eq(&key, &k);
            match self.sides(path, c)? {
                Sides::Both { then_models, else_models } => {
                    let mut twin = self.split(path, c, then_models, else_models, true);
                    if let Some(end) = self.jump(&mut twin, target)? {
                        if !matches!(end, End::Infeasible) {
                            // The twin hit the unwinding bound: report it as the path's own end.
                            *path = twin;
                            return Ok(Some(end));
                        }
                    } else {
                        self.pending.push(twin);
                    }
                }
                Sides::Then => {
                    path.cond.push(c);
                    return self.jump(path, target);
                }
                Sides::Else => path.cond.push(-c),
                Sides::Undecided { model_takes_then: true } => {
                    // The twin takes the other cases: it runs the switch again, with this case decided against.
                    let mut twin = self.split_undecided(path, c, true);
                    twin.frames.last_mut().expect("a frame").stack.push(Val::I(key.clone()));
                    self.pending.push(twin);
                    return self.jump(path, target);
                }
                Sides::Undecided { model_takes_then: false } => {
                    let mut twin = self.split_undecided(path, c, false);
                    if let Some(end) = self.jump(&mut twin, target)? {
                        if !matches!(end, End::Infeasible) {
                            if let Some(twin) = self.settle(twin)? {
                                *path = twin;
                                return Ok(Some(end));
                            }
                        }
                    } else {
                        self.pending.push(twin);
                    }
                }
            }
        }
        self.jump(path, default)
    }

    fn arith(&mut self, path: &mut Path, op: ArithOp, kind: Kind) -> Step {
        let width = match kind {
            Kind::Int => 32,
            Kind::Long => 64,
            _ => return unsupported("floating point"),
        };
        let wrap = |b: Bits| if width == 64 { Val::J(b) } else { Val::I(b) };
        if op == ArithOp::Neg {
            let x = if width == 64 { self.pop_long(path)? } else { self.pop_int(path)? };
            let r = self.b.neg(&x);
            self.push(path, wrap(r));
            self.advance(path);
            return Ok(None);
        }
        // Shift amounts are ints whatever the shifted value's width.
        let y = if width == 64 && !matches!(op, ArithOp::Shl | ArithOp::Shr | ArithOp::Ushr) { self.pop_long(path)? } else { self.pop_int(path)? };
        let x = if width == 64 { self.pop_long(path)? } else { self.pop_int(path)? };
        let r = match op {
            ArithOp::Add => self.b.add(&x, &y),
            ArithOp::Sub => self.b.sub(&x, &y),
            ArithOp::Mul => self.b.mul_lazy(&x, &y),
            ArithOp::Div | ArithOp::Rem => {
                let zero = self.b.is_zero(&y);
                let (q, r) = self.b.sdivrem_lazy(&x, &y);
                let value = wrap(if op == ArithOp::Div { q } else { r });
                return self.branch_throw(path, zero, "java/lang/ArithmeticException", value);
            }
            ArithOp::Shl => self.b.shl(&x, &y),
            ArithOp::Shr => self.b.shr(&x, &y),
            ArithOp::Ushr => self.b.ushr(&x, &y),
            ArithOp::And => self.b.and_bits(&x, &y),
            ArithOp::Or => self.b.or_bits(&x, &y),
            ArithOp::Xor => self.b.xor_bits(&x, &y),
            ArithOp::Neg => unreachable!(),
        };
        self.push(path, wrap(r));
        self.advance(path);
        Ok(None)
    }

    /// The JDK's static methods the engine models: the exact and floor arithmetic of `Math`, the comparisons
    /// of the integer wrappers, and their `numberOfLeadingZeros`. [`models_jdk_static`] lists the same arms, for the gap scan.
    fn call_jdk_static(&mut self, path: &mut Path, owner: &str, name: &str, descriptor: &str, parsed: &MethodDescriptor, args: Vec<Val>) -> Step {
        // The JVM's own objects ([`runtime`]): a class by name, a logger. Where the arguments are not ones it
        // answers for, the call is the gap it was.
        // Whether a char is a letter, of an ASCII unit ([`strings`]): the JDK's call of any other.
        if strings::models_static(owner, name, descriptor) {
            return self.is_letter(path, &args);
        }
        if runtime::models_static(owner, name, descriptor) || regex::models_static(owner, name, descriptor) || bytes::models_static(owner, name, descriptor) || locale::models_static(owner, name, descriptor) {
            let modelled = if runtime::models_static(owner, name, descriptor) {
                self.runtime_static(path, owner, name, &args)
            } else if locale::models_static(owner, name, descriptor) {
                self.locale_static(path, name, &args)
            } else if bytes::models_static(owner, name, descriptor) {
                self.bytes_static(path, owner, name, descriptor, &args)
            } else {
                self.regex_static(path, owner, name, &args)
            };
            return match modelled {
                Some(step) => step,
                None => {
                    if let Some(end) = self.meet(path, GapKind::JdkStaticMethod, owner, name, descriptor) {
                        return Ok(Some(end));
                    }
                    if let Type::Object(class) = &parsed.ret {
                        let r = self.alloc(path, class);
                        self.push(path, Val::R(Some(r)));
                    }
                    self.advance(path);
                    Ok(None)
                }
            };
        }
        // The models over references ([`models_jdk_reference_static`]), whose arguments are known objects or null.
        match (owner, name, args.as_slice()) {
            // The object itself, or a NullPointerException; the message of the second form is one no proof observes.
            ("java/util/Objects", "requireNonNull", [Val::R(object), ..]) => {
                if object.is_none() {
                    return self.raise(path, "java/lang/NullPointerException");
                }
                self.push(path, Val::R(*object));
                self.advance(path);
                return Ok(None);
            }
            // A regex that is a constant of the plain form ([`crate::jdk_facts::plain_regex`]) compiles: a new
            // Pattern, an object with no content, whose methods are the JDK calls they were. Any other regex is the
            // gap the call was, since whether it compiles is the JDK's parser's to say.
            ("java/util/regex/Pattern", "compile", [Val::R(regex)]) => {
                let Some(o) = *regex else { return self.raise(path, "java/lang/NullPointerException") };
                // A String the engine holds as a regular expression ([`regex`]) compiles to its pieces.
                if let Some(step) = self.compile_source(path, o) {
                    return step;
                }
                let units = path.objects[o].content().and_then(|s| {
                    let length = usize::try_from(self.b.constant_value(&s.length)?).ok()?;
                    s.cells.get(..length)?.iter().map(|c| self.b.constant_value(c).map(|u| u as u16)).collect::<Option<Vec<u16>>>()
                });
                if !units.is_some_and(|u| crate::jdk_facts::plain_regex(&u)) {
                    return Ok(self.meet(path, GapKind::JdkStaticMethod, owner, name, descriptor));
                }
                let r = self.alloc(path, "java/util/regex/Pattern");
                self.push(path, Val::R(Some(r)));
                self.advance(path);
                return Ok(None);
            }
            _ => {}
        }
        let bits = |v: &Val| match v {
            Val::I(b) | Val::J(b) => Some(b.clone()),
            Val::R(_) | Val::C(_) => None,
        };
        let a: Vec<Bits> = match args.iter().map(bits).collect::<Option<Vec<_>>>() {
            Some(a) => a,
            None => return unsupported(format!("{}.{name}{descriptor}", owner.replace('/', "."))),
        };
        let wrap = |b: Bits| if b.len() == 64 { Val::J(b) } else { Val::I(b) };
        let result = match (owner, name) {
            ("java/lang/Math" | "java/lang/StrictMath", "addExact" | "subtractExact" | "multiplyExact" | "negateExact" | "incrementExact" | "decrementExact" | "toIntExact" | "absExact") => {
                let (value, overflow) = match name {
                    "addExact" => {
                        let r = self.b.add(&a[0], &a[1]);
                        // Overflow if the operands agree in sign and the result does not.
                        let same = -self.b.xor(self.b.negative(&a[0]), self.b.negative(&a[1]));
                        let differs = self.b.xor(self.b.negative(&a[0]), self.b.negative(&r));
                        let o = self.b.and(same, differs);
                        (r, o)
                    }
                    "subtractExact" => {
                        let r = self.b.sub(&a[0], &a[1]);
                        let differ = self.b.xor(self.b.negative(&a[0]), self.b.negative(&a[1]));
                        let changed = self.b.xor(self.b.negative(&a[0]), self.b.negative(&r));
                        let o = self.b.and(differ, changed);
                        (r, o)
                    }
                    "multiplyExact" => {
                        // (JI)J widens the int; the product is exact iff it fits in the width, checked on the
                        // double-width product.
                        let width = a[0].len();
                        let x = self.b.sext(&a[0], 2 * width);
                        let y = if a[1].len() == width { self.b.sext(&a[1], 2 * width) } else { self.b.sext(&a[1], 2 * width) };
                        let wide = self.b.mul(&x, &y);
                        let r = self.b.trunc(&wide, width);
                        let back = self.b.sext(&r, 2 * width);
                        let o = -self.b.eq(&wide, &back);
                        (r, o)
                    }
                    "negateExact" => {
                        let r = self.b.neg(&a[0]);
                        let min = self.b.constant(if a[0].len() == 64 { i64::MIN } else { i64::from(i32::MIN) }, a[0].len());
                        let o = self.b.eq(&a[0], &min);
                        (r, o)
                    }
                    "incrementExact" | "decrementExact" => {
                        let one = self.b.constant(1, a[0].len());
                        let r = if name == "incrementExact" { self.b.add(&a[0], &one) } else { self.b.sub(&a[0], &one) };
                        let limit = self.b.constant(if name == "incrementExact" { if a[0].len() == 64 { i64::MAX } else { i64::from(i32::MAX) } } else if a[0].len() == 64 { i64::MIN } else { i64::from(i32::MIN) }, a[0].len());
                        let o = self.b.eq(&a[0], &limit);
                        (r, o)
                    }
                    "toIntExact" => {
                        let r = self.b.trunc(&a[0], 32);
                        let back = self.b.sext(&r, 64);
                        let o = -self.b.eq(&a[0], &back);
                        (r, o)
                    }
                    "absExact" => {
                        let neg = self.b.neg(&a[0]);
                        let r = self.b.ite_bits(self.b.negative(&a[0]), &neg, &a[0]);
                        let min = self.b.constant(if a[0].len() == 64 { i64::MIN } else { i64::from(i32::MIN) }, a[0].len());
                        let o = self.b.eq(&a[0], &min);
                        (r, o)
                    }
                    _ => unreachable!(),
                };
                return self.branch_throw(path, overflow, "java/lang/ArithmeticException", wrap(value));
            }
            ("java/lang/Math" | "java/lang/StrictMath", "abs") => {
                let neg = self.b.neg(&a[0]);
                wrap(self.b.ite_bits(self.b.negative(&a[0]), &neg, &a[0]))
            }
            ("java/lang/Math" | "java/lang/StrictMath" | "java/lang/Integer" | "java/lang/Long", "max" | "min") => {
                let lt = self.b.slt(&a[0], &a[1]);
                let (x, y) = if name == "max" { (&a[1], &a[0]) } else { (&a[0], &a[1]) };
                wrap(self.b.ite_bits(lt, x, y))
            }
            ("java/lang/Integer" | "java/lang/Long", "sum") => wrap(self.b.add(&a[0], &a[1])),
            ("java/lang/Math" | "java/lang/StrictMath", "floorDiv" | "floorMod") => {
                // floorDiv(x, y) = x / y, less one when the signs differ and the division is inexact;
                // floorMod(x, y) = x - floorDiv(x, y) * y. A second operand narrower than the first is widened.
                let width = a[0].len();
                let y = if a[1].len() == width { a[1].clone() } else { self.b.sext(&a[1], width) };
                let zero = self.b.is_zero(&y);
                let (q, r) = self.b.sdivrem_lazy(&a[0], &y);
                let inexact = -self.b.is_zero(&r);
                let differ = self.b.xor(self.b.negative(&a[0]), self.b.negative(&y));
                let adjust = self.b.and(inexact, differ);
                let one = self.b.constant(1, width);
                let q_less = self.b.sub(&q, &one);
                let fq = self.b.ite_bits(adjust, &q_less, &q);
                let value = if name == "floorDiv" {
                    fq
                } else {
                    let r_plus = self.b.add(&r, &y);
                    let fm = self.b.ite_bits(adjust, &r_plus, &r);
                    if parsed.ret == Type::Int && width == 64 { self.b.trunc(&fm, 32) } else { fm }
                };
                return self.branch_throw(path, zero, "java/lang/ArithmeticException", wrap(value));
            }
            ("java/lang/Integer" | "java/lang/Long", "compare") => {
                let lt = self.b.slt(&a[0], &a[1]);
                let eq = self.b.eq(&a[0], &a[1]);
                let minus_one = self.b.constant(-1, 32);
                let zero = self.b.constant(0, 32);
                let one = self.b.constant(1, 32);
                let tail = self.b.ite_bits(eq, &zero, &one);
                Val::I(self.b.ite_bits(lt, &minus_one, &tail))
            }
            ("java/lang/Integer" | "java/lang/Long", "signum") => {
                let zero = self.b.constant(0, a[0].len());
                let lt = self.b.slt(&a[0], &zero);
                let eq = self.b.eq(&a[0], &zero);
                let minus_one = self.b.constant(-1, 32);
                let z = self.b.constant(0, 32);
                let one = self.b.constant(1, 32);
                let tail = self.b.ite_bits(eq, &z, &one);
                Val::I(self.b.ite_bits(lt, &minus_one, &tail))
            }
            ("java/lang/Integer", "toUnsignedLong") => Val::J(self.b.zext(&a[0], 64)),
            ("java/lang/Integer" | "java/lang/Long", "numberOfLeadingZeros") => {
                // A priority encoder: the zeros above the highest one bit, the width for zero. Each bit, from the
                // lowest up, overrides the count the bits below it gave.
                let width = a[0].len();
                let mut count = self.b.constant(width as i64, 32);
                for (i, &bit) in a[0].iter().enumerate() {
                    let here = self.b.constant((width - 1 - i) as i64, 32);
                    count = self.b.ite_bits(bit, &here, &count);
                }
                Val::I(count)
            }
            ("java/lang/Boolean", "logicalAnd") => Val::I(self.b.and_bits(&a[0], &a[1])),
            ("java/lang/Boolean", "logicalOr") => Val::I(self.b.or_bits(&a[0], &a[1])),
            ("java/lang/Boolean", "logicalXor") => Val::I(self.b.xor_bits(&a[0], &a[1])),
            _ => return unsupported(format!("{}.{name}{descriptor}", owner.replace('/', "."))),
        };
        self.push(path, result);
        self.advance(path);
        Ok(None)
    }
}

/// Whether the engine models the String method `owner.name(descriptor)` on a String whose content it holds
/// ([`Engine::string_method`]); the engine and the gap scan share it.
pub fn models_string_method(owner: &str, name: &str, descriptor: &str) -> bool {
    owner == STRING && (matches!((name, descriptor), ("length", "()I") | ("isEmpty", "()Z") | ("charAt", "(I)C") | ("equals", "(Ljava/lang/Object;)Z") | ("hashCode", "()I") | ("startsWith", "(Ljava/lang/String;)Z") | ("toString", "()Ljava/lang/String;")) || strings::models(name, descriptor) || locale::models_string(name, descriptor) || regex::models_string(name, descriptor) || bytes::models_string(name, descriptor) || crate::models::entry(STRING, name, descriptor).is_some())
}

/// Whether [`Engine::call_jdk_static`] models `owner.name`: the arms of its match, for [`gaps::scan`], which counts
/// such a call as reproduced exactly rather than a gap.
pub fn models_jdk_static(owner: &str, name: &str) -> bool {
    matches!(
        (owner, name),
        ("java/lang/Math" | "java/lang/StrictMath", "addExact" | "subtractExact" | "multiplyExact" | "negateExact" | "incrementExact" | "decrementExact" | "toIntExact" | "absExact" | "abs" | "max" | "min" | "floorDiv" | "floorMod")
            | ("java/lang/Integer" | "java/lang/Long", "max" | "min" | "sum" | "compare" | "signum")
            | ("java/lang/Integer", "toUnsignedLong")
            | ("java/lang/Integer" | "java/lang/Long", "numberOfLeadingZeros")
            | ("java/lang/Boolean", "logicalAnd" | "logicalOr" | "logicalXor")
    )
}

/// Whether [`Engine::call_jdk_static`] models the static call `owner.name(descriptor)` over references:
/// `Objects.requireNonNull` of an object, with or without a message, and `Pattern.compile` of a regex (where it is a
/// constant of the plain form, [`crate::jdk_facts::plain_regex`]; on any other the engine meets the call as the gap it
/// was, where it runs it); or where its arguments let it be, the gap it was elsewhere: the calls of [`runtime`],
/// [`regex`], [`bytes`] and [`locale`], and `Character.isLetter(char)` ([`strings`]).
pub fn models_jdk_reference_static(owner: &str, name: &str, descriptor: &str) -> bool {
    matches!(
        (owner, name, descriptor),
        ("java/util/Objects", "requireNonNull", "(Ljava/lang/Object;)Ljava/lang/Object;" | "(Ljava/lang/Object;Ljava/lang/String;)Ljava/lang/Object;") | ("java/util/regex/Pattern", "compile", "(Ljava/lang/String;)Ljava/util/regex/Pattern;")
    ) || runtime::models_static(owner, name, descriptor)
        || strings::models_static(owner, name, descriptor)
        || regex::models_static(owner, name, descriptor)
        || bytes::models_static(owner, name, descriptor)
        || locale::models_static(owner, name, descriptor)
        || crate::models::entry(owner, name, descriptor).is_some()
}

impl Blaster {
    /// The solver by name alone, as [`Outcome::solver`] gives it: the first word of its signature (`CaDiCaL`).
    fn signature(&self) -> String {
        self.solver_signature().split_whitespace().next().unwrap_or_default().to_string()
    }

    /// A cell of an array of `element`s as the value a load pushes: extended to an int, without sign for a
    /// boolean or a char and with it for a byte or a short, or left a long.
    fn extend_cell(&self, element: &Type, cell: &Bits) -> Bits {
        match element {
            Type::Boolean | Type::Char => self.zext(cell, 32),
            Type::Byte | Type::Short => self.sext(cell, 32),
            _ => cell.clone(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::classfile::flags;
    use crate::classfile::writer::{ClassWriter, CodeBuilder, MethodWriter};

    /// The module's table says what the engine does with every instruction the decoder gives (each opcode decoded
    /// on its own, its operands zero), and the gap table of [`gaps`] has a row for every kind of gap: a new
    /// instruction or kind fails here until the tables say how it is treated.
    #[test]
    fn the_module_docs_say_what_the_engine_does_with_every_instruction() {
        let docs = |source: &str| source.lines().take_while(|l| l.starts_with("//!")).collect::<Vec<_>>().join("\n");
        let engine = docs(include_str!("mod.rs"));
        let table = engine.split("| Instructions | Treatment |").nth(1).expect("the table of instructions");
        let row = |insn: &Insn| -> &'static str {
            let float = |k: &Kind| matches!(k, Kind::Float | Kind::Double);
            match insn {
                Insn::Nop => "`nop`",
                Insn::AConstNull => "`aconst_null`",
                Insn::IConst(_) => "`iconst`",
                Insn::LConst(_) => "`lconst`",
                Insn::FConst(_) => "`fconst`",
                Insn::DConst(_) => "`dconst`",
                Insn::Ldc(_) => "`ldc` of an int or a long",
                Insn::Load(k, _) | Insn::Store(k, _) | Insn::Return(Some(k)) | Insn::Arith(_, k) if float(k) => "floating point",
                Insn::Convert(k, n) if float(k) || matches!(n, Narrow::To(t) if float(t)) => "floating point",
                Insn::Load(..) => "`iload`",
                Insn::Store(..) => "`istore`",
                Insn::ArrayLoad(ArrayKind::Ref) | Insn::ArrayStore(ArrayKind::Ref) => "`aaload`/`aastore`",
                Insn::ArrayLoad(ArrayKind::Float | ArrayKind::Double) | Insn::ArrayStore(ArrayKind::Float | ArrayKind::Double) => "floating point",
                Insn::ArrayLoad(_) => "`iaload` … `saload`",
                Insn::ArrayStore(_) => "`iastore` … `sastore`",
                Insn::Pop => "`pop`",
                Insn::Pop2 => "`pop2`",
                Insn::Dup => "`dup`",
                Insn::DupX1 => "`dup_x1`",
                Insn::DupX2 => "`dup_x2`",
                Insn::Dup2 => "`dup2`",
                Insn::Dup2X1 => "`dup2_x1`",
                Insn::Dup2X2 => "`dup2_x2`",
                Insn::Swap => "`swap`",
                Insn::Arith(..) => "`iadd` … `lxor`",
                Insn::IInc(..) => "`iinc`",
                Insn::Convert(..) => "`i2l`",
                Insn::Cmp(c) if c.kind == Kind::Long => "`lcmp`",
                Insn::Cmp(_) => "`fcmpl`",
                Insn::If(..) => "`ifeq`",
                Insn::IfICmp(..) => "`if_icmpeq`",
                Insn::IfACmp(..) => "`if_acmpeq`/`if_acmpne`",
                Insn::IfNull(_) => "`ifnull`",
                Insn::IfNonNull(_) => "`ifnonnull`",
                Insn::Goto(_) => "`goto`",
                Insn::Jsr(_) | Insn::Ret(_) => "`jsr`/`ret`",
                Insn::TableSwitch { .. } => "`tableswitch`",
                Insn::LookupSwitch { .. } => "`lookupswitch`",
                Insn::Return(_) => "`ireturn` … `return`",
                Insn::GetStatic(_) => "`getstatic`",
                Insn::PutStatic(_) => "`putstatic`",
                Insn::GetField(_) => "`getfield`",
                Insn::PutField(_) => "`putfield`",
                Insn::InvokeVirtual(_) => "`invokevirtual`",
                Insn::InvokeSpecial(_) => "`invokespecial`",
                Insn::InvokeStatic(_) => "`invokestatic`",
                Insn::InvokeInterface(_) => "`invokeinterface`",
                Insn::InvokeDynamic(_) => "`invokedynamic` string concatenation",
                Insn::New(_) => "`new`",
                Insn::NewArray(_) => "`newarray`",
                Insn::ANewArray(_) => "`anewarray`",
                Insn::ArrayLength => "`arraylength`",
                Insn::AThrow => "`athrow`",
                Insn::CheckCast(_) => "`checkcast`",
                Insn::InstanceOf(_) => "`instanceof`",
                Insn::MonitorEnter => "`monitorenter`",
                Insn::MonitorExit => "`monitorexit`",
                Insn::MultiANewArray(..) => "`multianewarray`",
            }
        };
        let mut decoded = 0;
        for op in 0u8..=255 {
            let mut bytes = vec![op];
            bytes.resize(32, 0);
            let Ok(insns) = crate::classfile::bytecode::decode(&bytes) else { continue };
            let insn = &insns[0].1;
            decoded += 1;
            assert!(table.contains(row(insn)), "opcode {op:#04x} ({insn:?}): the module's table has no row with {}", row(insn));
        }
        assert!(decoded >= 200, "every opcode of the JVM decodes, {decoded} did");
        for row in ["implemented", "modelled", "gap", "refused"] {
            assert!(table.contains(&format!("| {row}")), "a row of what is {row}");
        }
        let kinds = docs(include_str!("gaps.rs"));
        for kind in GapKind::ALL {
            assert!(kinds.contains(&format!("| `{}` |", kind.name())), "the gap table has a row for {}", kind.name());
            assert!(table.contains(&format!("`{}`", kind.name())), "the instruction table says where a {} gap is met", kind.name());
        }
    }

    /// A harness-shaped class: `static void check(int a, int b)` whose body `build` writes, failing by throwing an
    /// `AssertionError` at the label `fail`.
    fn harness(descriptor: &str, build: impl FnOnce(&mut CodeBuilder, &mut ClassWriter, crate::classfile::writer::Label)) -> ClassPath {
        let mut writer = ClassWriter::new("Check");
        writer.default_constructor();
        let mut code = CodeBuilder::new();
        code.max_locals = 8;
        code.max_stack = 8;
        let fail = code.label();
        build(&mut code, &mut writer, fail);
        code.return_(None);
        code.bind(fail);
        let error = writer.pool.class("java/lang/AssertionError");
        let init = writer.pool.method_ref("java/lang/AssertionError", "<init>", "()V");
        code.op_u16(0xbb, error);
        code.op(0x59);
        code.op_u16(0xb7, init);
        code.op(0xbf);
        writer.methods.push(MethodWriter { access: flags::PUBLIC | flags::STATIC, name: "check".into(), descriptor: descriptor.into(), code: Some(code) });
        let dir = tempfile::tempdir().unwrap();
        std::fs::write(dir.path().join("Check.class"), writer.to_bytes()).unwrap();
        let mut cp = ClassPath::new();
        cp.add(dir.path()).unwrap();
        std::mem::forget(dir);
        cp
    }

    fn run(cp: &ClassPath) -> Outcome {
        check(cp, "Check", "check", &Options::default()).unwrap()
    }

    /// `a[0] = 1; b[0] = 2; a[0] == 1`, which holds unless `a` and `b` are one array, over arrays of length 1 at
    /// least: a parameter that may be the same array as another is a choice between its own and the other's.
    #[test]
    fn array_parameters_that_may_be_one_array_are_a_choice_and_the_witness_says_which() {
        let cp = harness("([I[I)V", |code, _, fail| {
            let skip = code.label();
            for a in [0, 1] {
                code.load(Kind::Ref, a);
                code.op(0xbe); // arraylength
                code.if_zero(Cond::Eq, skip);
            }
            for (a, v) in [(0, 1), (1, 2)] {
                code.load(Kind::Ref, a);
                code.iconst(0);
                code.iconst(v);
                code.op(0x4f); // iastore
            }
            code.load(Kind::Ref, 0);
            code.iconst(0);
            code.op(0x2e); // iaload
            code.iconst(1);
            code.if_icmp(Cond::Ne, fail);
            code.bind(skip);
        });
        let distinct = run(&cp);
        assert_eq!(distinct.verdict, Verdict::Verified, "{:?}", distinct.problem);
        for merge_after in [0, u64::MAX] {
            let parameters = Parameters { may_alias: vec![vec![0, 1]], ..Parameters::default() };
            let out = check(&cp, "Check", "check", &Options { parameters, merge_after, ..Options::default() }).unwrap();
            assert_eq!(out.verdict, Verdict::Violation, "{:?}", out.problem);
            assert_eq!(out.raw_same, BTreeMap::from([(1, 0)]), "b is a's array");
            assert_eq!(out.raw_arrays[&1], out.raw_arrays[&0], "and has its elements");
        }
    }

    /// `a.length >= 0`, which an array parameter that may be null refutes with a `NullPointerException` the
    /// harness doesn't catch: the engine says so, and with the null checked first, the claim holds.
    #[test]
    fn an_array_parameter_that_may_be_null_is_null_on_some_path() {
        let length = |guarded: bool| {
            harness("([I)V", move |code, _, fail| {
                let done = code.label();
                if guarded {
                    code.load(Kind::Ref, 0);
                    code.if_null(done);
                }
                code.load(Kind::Ref, 0);
                code.op(0xbe); // arraylength
                code.if_zero(Cond::Lt, fail);
                code.bind(done);
            })
        };
        let nullable = |cp: &ClassPath| check(cp, "Check", "check", &Options { parameters: Parameters { nullable: vec![0], ..Parameters::default() }, ..Options::default() }).unwrap();
        assert_eq!(run(&length(false)).verdict, Verdict::Verified, "never null by default");
        let unguarded = nullable(&length(false));
        assert_eq!(unguarded.verdict, Verdict::Unverifiable);
        assert!(unguarded.problem.as_deref().unwrap_or("").contains("NullPointerException"), "{:?}", unguarded.problem);
        assert_eq!(nullable(&length(true)).verdict, Verdict::Verified);
        // A null that fails the claim is the witness's.
        let fails_on_null = harness("([I)V", |code, _, fail| {
            code.load(Kind::Ref, 0);
            code.if_null(fail);
        });
        let out = nullable(&fails_on_null);
        assert_eq!(out.verdict, Verdict::Violation);
        assert_eq!(out.raw_arrays[&0], None);
        assert!(out.raw_same.is_empty());
    }

    #[test]
    fn a_tautology_is_verified_and_a_falsifiable_claim_refuted_with_its_input() {
        // a + b == b + a
        let cp = harness("(II)V", |code, _, fail| {
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.op(0x60); // iadd
            code.load(Kind::Int, 1);
            code.load(Kind::Int, 0);
            code.op(0x60);
            code.if_icmp(Cond::Ne, fail);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Verified, "{:?}", out.problem);
        assert_eq!(out.solves, 0, "both sides are the same gates, so the comparison folds to a constant and no solver call is needed");

        // a * 2 == a + a holds; a * a >= 0 does not (overflow), and the input that breaks it is reported.
        let cp = harness("(I)V", |code, _, fail| {
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 0);
            code.op(0x68); // imul
            code.if_zero(Cond::Lt, fail);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Violation, "{:?}", out.problem);
        let a: i32 = out.raw_inputs[&0].parse().unwrap();
        assert!(a.wrapping_mul(a) < 0, "{a}");
    }

    #[test]
    fn a_branch_costs_one_solver_call_and_a_condition_taken_before_none() {
        // `if (a >= b) return; if (a >= b) fail; return`: the first branch asks the solver about the one side
        // the path's model does not take, and the second is on the literal the path already took.
        let cp = harness("(II)V", |code, _, fail| {
            let done = code.label();
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.if_icmp(Cond::Ge, done);
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.if_icmp(Cond::Ge, fail);
            code.bind(done);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Verified, "{:?}", out.problem);
        assert_eq!((out.paths, out.solves), (2, 1));

        // Two independent branches: four paths, and three solver calls (one per branch point explored), where
        // asking about both sides of each would take six.
        let cp = harness("(II)V", |code, _, _| {
            let second = code.label();
            let done = code.label();
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.if_icmp(Cond::Lt, second);
            code.bind(second);
            code.load(Kind::Int, 0);
            code.iconst(5);
            code.if_icmp(Cond::Lt, done);
            code.bind(done);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Verified, "{:?}", out.problem);
        assert_eq!((out.paths, out.merges, out.solves), (4, 0, 3));

        // Merged from the start, the two paths through the first branch are one again at the join after it, so
        // the second is explored once, on the merged path, and its two paths are one at the end: three paths, two
        // merges and two solver calls.
        let out = check(&cp, "Check", "check", &Options { merge_after: 0, ..Options::default() }).unwrap();
        assert_eq!(out.verdict, Verdict::Verified, "{:?}", out.problem);
        assert_eq!((out.paths, out.merges, out.solves), (3, 2, 2));
    }

    #[test]
    fn paths_are_merged_at_a_join_and_a_violation_through_one_is_found_with_its_input() {
        // `x = a < b ? a : b; if (x != a) fail`: the two assignments meet at the comparison, which runs once on the
        // merged path; the violation on it needs the else side of the first branch, and the solver names an input
        // that takes it. The merged path goes to the failure itself, so its twin (the return) is never run.
        let cp = harness("(II)V", |code, _, fail| {
            let else_ = code.label();
            let join = code.label();
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.if_icmp(Cond::Ge, else_);
            code.load(Kind::Int, 0);
            code.store(Kind::Int, 2);
            code.goto(join);
            code.bind(else_);
            code.load(Kind::Int, 1);
            code.store(Kind::Int, 2);
            code.bind(join);
            code.load(Kind::Int, 2);
            code.load(Kind::Int, 0);
            code.if_icmp(Cond::Ne, fail);
        });
        let merged = Options { merge_after: 0, ..Options::default() };
        let out = check(&cp, "Check", "check", &merged).unwrap();
        assert_eq!(out.verdict, Verdict::Violation, "{:?}", out.problem);
        assert_eq!((out.paths, out.merges), (2, 1), "{}", out.summary());
        let (a, b): (i64, i64) = (out.raw_inputs[&0].parse().unwrap(), out.raw_inputs[&1].parse().unwrap());
        assert!(a > b, "{a} {b}");
        assert_eq!(out.stage.as_deref(), Some("[0:20]"));

        // Eight independent branches in a row (`if ((a >>> i & 1) != 0) b += 1` for each bit i): nine paths
        // merged, not 256, and the claim after them still holds.
        let cp = harness("(II)V", |code, _, fail| {
            for i in 0..8u8 {
                let join = code.label();
                code.load(Kind::Int, 0);
                code.iconst(i as i32);
                code.op(0x7c);
                code.iconst(1);
                code.op(0x7e);
                code.if_zero(Cond::Eq, join);
                code.load(Kind::Int, 1);
                code.iconst(1);
                code.op(0x60);
                code.store(Kind::Int, 1);
                code.bind(join);
            }
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 0);
            code.if_icmp(Cond::Ne, fail);
        });
        let out = check(&cp, "Check", "check", &merged).unwrap();
        assert_eq!(out.verdict, Verdict::Verified, "{:?}", out.problem);
        assert_eq!((out.paths, out.merges), (9, 8), "{}", out.summary());
        // Unmerged until the budget: every path on its own.
        let out = check(&cp, "Check", "check", &Options { merge_after: 1000, ..Options::default() }).unwrap();
        assert_eq!((out.verdict, out.paths, out.merges), (Verdict::Verified, 256, 0), "{}", out.summary());
        // With the budget inside the search, the paths explored after it are merged: fewer than 256, more than 9.
        let out = check(&cp, "Check", "check", &Options { merge_after: 16, ..Options::default() }).unwrap();
        assert_eq!(out.verdict, Verdict::Verified, "{:?}", out.problem);
        assert!(out.paths > 9 && out.paths < 256 && out.merges > 0, "{}", out.summary());
    }

    #[test]
    fn division_by_zero_is_an_exception_path_and_handlers_catch_by_class() {
        // a / b throws ArithmeticException exactly when b == 0 (the handler asserts b == 0, the normal path
        // b != 0), and on a concrete input the quotient is what it should be.
        let cp = harness("(II)V", |code, writer, fail| {
            let try_start = code.label();
            let try_end = code.label();
            let handler = code.label();
            let ok = code.label();
            let not_seven = code.label();
            code.bind(try_start);
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.op(0x6c); // idiv
            code.store(Kind::Int, 2);
            code.load(Kind::Int, 1);
            code.if_zero(Cond::Eq, fail); // returned although b == 0: impossible
            code.load(Kind::Int, 0);
            code.iconst(7);
            code.if_icmp(Cond::Ne, not_seven);
            code.load(Kind::Int, 1);
            code.iconst(2);
            code.if_icmp(Cond::Ne, not_seven);
            code.load(Kind::Int, 2);
            code.iconst(3);
            code.if_icmp(Cond::Ne, fail); // 7 / 2 != 3: impossible
            code.bind(not_seven);
            code.bind(try_end);
            code.goto(ok);
            code.bind(handler);
            code.op(0x57); // pop
            code.load(Kind::Int, 1);
            code.if_zero(Cond::Ne, fail); // thrown although b != 0: impossible
            code.bind(ok);
            let arithmetic = writer.pool.class("java/lang/ArithmeticException");
            code.handler(try_start, try_end, handler, Some(arithmetic));
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Verified, "{:?}", out.problem);

        // The quotient of 7 / 2 claimed to be 4: refuted, and the input named is 7 and 2.
        let cp = harness("(II)V", |code, _, fail| {
            let ok = code.label();
            code.load(Kind::Int, 0);
            code.iconst(7);
            code.if_icmp(Cond::Ne, ok);
            code.load(Kind::Int, 1);
            code.iconst(2);
            code.if_icmp(Cond::Ne, ok);
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.op(0x6c);
            code.iconst(4);
            code.if_icmp(Cond::Ne, fail);
            code.bind(ok);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Violation, "{:?}", out.problem);
        assert_eq!((out.raw_inputs[&0].as_str(), out.raw_inputs[&1].as_str()), ("7", "2"));

        // Without a handler the exception leaves the harness, which the engine does not judge.
        let cp = harness("(II)V", |code, _, fail| {
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.op(0x6c);
            code.op(0x57);
            code.iconst(1);
            code.if_zero(Cond::Eq, fail);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Unverifiable);
        assert!(out.problem.unwrap().contains("uncaught java.lang.ArithmeticException"));
    }

    #[test]
    fn a_violating_input_is_taken_from_the_first_stage_that_has_one() {
        // a * a >= 0 fails only from 46341 up: nothing in [0:20], the second stage has it.
        let cp = harness("(I)V", |code, _, fail| {
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 0);
            code.op(0x68); // imul
            code.if_zero(Cond::Lt, fail);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Violation, "{:?}", out.problem);
        assert_eq!(out.stage.as_deref(), Some("[-100000:100000]"));
        let a: i32 = out.raw_inputs[&0].parse().unwrap();
        assert!(a.wrapping_mul(a) < 0 && a.abs() <= 100_000, "{a}");

        // a != 5000000 fails on one input only, outside every stage.
        let cp = harness("(I)V", |code, writer, fail| {
            code.load(Kind::Int, 0);
            let big = writer.pool.integer(5_000_000);
            code.ldc(big);
            code.if_icmp(Cond::Eq, fail);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Violation, "{:?}", out.problem);
        assert_eq!(out.stage, None);
        assert_eq!(out.raw_inputs[&0], "5000000");

        // The path explored first (the jump, a < 0) fails only at -7000000; the other fails at 3. The search
        // goes on past the first violating path and reports the small input, from the first stage.
        let cp = harness("(I)V", |code, writer, fail| {
            let negative = code.label();
            let done = code.label();
            code.load(Kind::Int, 0);
            code.if_zero(Cond::Lt, negative);
            code.load(Kind::Int, 0);
            code.iconst(3);
            code.if_icmp(Cond::Eq, fail);
            code.goto(done);
            code.bind(negative);
            code.load(Kind::Int, 0);
            let big = writer.pool.integer(-7_000_000);
            code.ldc(big);
            code.if_icmp(Cond::Eq, fail);
            code.bind(done);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Violation, "{:?}", out.problem);
        assert_eq!(out.stage.as_deref(), Some("[0:20]"));
        assert_eq!(out.raw_inputs[&0], "3");
        assert!(out.paths >= 2, "{}", out.paths);

        // A long parameter is staged too, and a boolean is in every stage.
        let cp = harness("(JZ)V", |code, _, fail| {
            code.load(Kind::Int, 2);
            code.if_zero(Cond::Eq, fail);
            code.load(Kind::Long, 0);
            code.op(0x09); // lconst_0
            code.op(0x94); // lcmp
            code.if_zero(Cond::Le, fail);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Violation, "{:?}", out.problem);
        assert_eq!(out.stage.as_deref(), Some("[0:20]"));
        let a: i64 = out.raw_inputs[&0].parse().unwrap();
        assert!((0..=20).contains(&a), "{a}");
    }

    /// After the first violation the search for a smaller witness is bounded by the solver's work and the paths
    /// run, not by the clock: on a solver as slow as a loaded machine's, the witness is the one a fast solver gives.
    #[test]
    fn the_search_for_a_smaller_witness_does_not_depend_on_the_clock() {
        // The path explored first (a < 0) fails only at -7000000, outside every stage. The other runs past eight
        // branches, each a solver call, before it fails at 3, in the first stage.
        let cp = harness("(I)V", |code, writer, fail| {
            let negative = code.label();
            let done = code.label();
            code.load(Kind::Int, 0);
            code.if_zero(Cond::Lt, negative);
            for k in 1..=8 {
                code.load(Kind::Int, 0);
                let c = writer.pool.integer(1000 + k);
                code.ldc(c);
                code.if_icmp(Cond::Eq, done);
            }
            code.load(Kind::Int, 0);
            code.iconst(3);
            code.if_icmp(Cond::Eq, fail);
            code.goto(done);
            code.bind(negative);
            code.load(Kind::Int, 0);
            let big = writer.pool.integer(-7_000_000);
            code.ldc(big);
            code.if_icmp(Cond::Eq, fail);
            code.bind(done);
        });
        let fast = run(&cp);
        assert_eq!(fast.verdict, Verdict::Violation, "{:?}", fast.problem);
        assert_eq!((fast.stage.as_deref(), fast.raw_inputs[&0].as_str()), (Some("[0:20]"), "3"));
        let slow = check(&cp, "Check", "check", &Options { solver: sat::Slow::boxed, ..Options::default() }).unwrap();
        assert_eq!(slow.verdict, Verdict::Violation, "{:?}", slow.problem);
        assert_eq!((slow.stage.as_deref(), slow.raw_inputs[&0].as_str(), slow.paths), (Some("[0:20]"), "3", fast.paths));
    }

    #[test]
    fn the_stages_are_jbmcs() {
        let spelled: Vec<Option<String>> = STAGES.iter().map(|(lo, hi)| Some(format!("[{lo}:{hi}]"))).chain(std::iter::once(None)).collect();
        let jbmc: Vec<Option<String>> = crate::equivalence::STAGES.iter().map(|s| s.map(str::to_string)).collect();
        assert_eq!(spelled, jbmc);
    }

    #[test]
    fn loops_are_unwound_up_to_the_bound() {
        // for (i = 0; i < n; i++) {}  then assert i == n: fine within the bound, beyond it no verdict.
        let cp = harness("(I)V", |code, _, fail| {
            let top = code.label();
            let done = code.label();
            code.iconst(0);
            code.store(Kind::Int, 1);
            code.bind(top);
            code.load(Kind::Int, 1);
            code.load(Kind::Int, 0);
            code.if_icmp(Cond::Ge, done);
            code.iinc(1, 1);
            code.goto(top);
            code.bind(done);
            code.load(Kind::Int, 1);
            code.load(Kind::Int, 0);
            code.if_icmp(Cond::Lt, fail);
        });
        let out = check(&cp, "Check", "check", &Options { unwind: 4, invariants: false, ..Options::default() }).unwrap();
        assert_eq!(out.verdict, Verdict::Unverifiable, "{:?}", out.problem);
        assert!(out.problem.unwrap().contains("not fully unwound"));

        // With an invariant looked for, the loop's further iterations are covered: `i` is at least 4 from then
        // on, and where the loop is left it is not below `n`.
        let out = check(&cp, "Check", "check", &Options { unwind: 4, ..Options::default() }).unwrap();
        assert_eq!(out.verdict, Verdict::Verified, "{:?}", out.problem);
        assert_eq!(out.loops, ["Check.check at pc 3"]);
        assert!(out.assumed.is_empty(), "i grows: the loop ends: {:?}", out.assumed);
    }

    /// `for (i = 0; i < outer; i++) for (j = 0; j < inner(i); j++) s++;`, with `i` in slot 1, `j` in slot 2 and `s`
    /// in slot 3, each loop tested at its top and closed by a `goto` back to it.
    fn nested_loops(code: &mut CodeBuilder, outer: impl FnOnce(&mut CodeBuilder), inner: impl FnOnce(&mut CodeBuilder)) {
        let (top, done, inner_top, inner_done) = (code.label(), code.label(), code.label(), code.label());
        code.iconst(0);
        code.store(Kind::Int, 1);
        code.iconst(0);
        code.store(Kind::Int, 3);
        code.bind(top);
        code.load(Kind::Int, 1);
        outer(code);
        code.if_icmp(Cond::Ge, done);
        code.iconst(0);
        code.store(Kind::Int, 2);
        code.bind(inner_top);
        code.load(Kind::Int, 2);
        inner(code);
        code.if_icmp(Cond::Ge, inner_done);
        code.iinc(3, 1);
        code.iinc(2, 1);
        code.goto(inner_top);
        code.bind(inner_done);
        code.iinc(1, 1);
        code.goto(top);
        code.bind(done);
    }

    #[test]
    fn an_inner_loop_is_unwound_per_entry_of_it() {
        // VF-011: 4 iterations of an outer loop, each running an inner loop 3 times, are within --unwind 4, although
        // the inner back edge is taken 12 times on the path.
        let cp = harness("()V", |code, _, fail| {
            nested_loops(code, |code| code.iconst(4), |code| code.iconst(3));
            code.load(Kind::Int, 3);
            code.iconst(12);
            code.if_icmp(Cond::Ne, fail);
        });
        let out = check(&cp, "Check", "check", &Options { unwind: 4, ..Options::default() }).unwrap();
        assert_eq!(out.verdict, Verdict::Verified, "{:?}", out.problem);

        // Example 052's shape: a sum over i < k inside a loop over k < n, for every n up to 5, so 10 inner
        // iterations at most and fewer than 5 on each entry. 2 s == n (n - 1).
        let cp = harness("(I)V", |code, _, fail| {
            let ok = code.label();
            code.load(Kind::Int, 0);
            code.if_zero(Cond::Lt, ok);
            code.load(Kind::Int, 0);
            code.iconst(5);
            code.if_icmp(Cond::Gt, ok);
            nested_loops(code, |code| code.load(Kind::Int, 0), |code| code.load(Kind::Int, 1));
            code.load(Kind::Int, 3);
            code.iconst(1);
            code.op(0x78); // ishl
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 0);
            code.iconst(1);
            code.op(0x64); // isub
            code.op(0x68); // imul
            code.if_icmp(Cond::Ne, fail);
            code.bind(ok);
        });
        let out = check(&cp, "Check", "check", &Options { unwind: 5, ..Options::default() }).unwrap();
        assert_eq!(out.verdict, Verdict::Verified, "{:?}", out.problem);

        // The count still bounds each entry: an inner loop of 5 iterations is beyond --unwind 4.
        let cp = harness("()V", |code, _, _| nested_loops(code, |code| code.iconst(2), |code| code.iconst(5)));
        let out = check(&cp, "Check", "check", &Options { unwind: 4, invariants: false, ..Options::default() }).unwrap();
        assert_eq!(out.verdict, Verdict::Unverifiable, "{:?}", out.problem);
        assert!(out.problem.unwrap().contains("not fully unwound"));
    }

    #[test]
    fn a_loop_entered_again_by_an_outer_back_edge_is_bounded_by_the_outer_count() {
        // The inner loop starts afresh on each of the outer loop's iterations, but the outer loop's 5 are beyond
        // --unwind 4, so the path still ends with no verdict.
        let cp = harness("()V", |code, _, _| nested_loops(code, |code| code.iconst(5), |code| code.iconst(1)));
        let out = check(&cp, "Check", "check", &Options { unwind: 4, invariants: false, ..Options::default() }).unwrap();
        assert_eq!(out.verdict, Verdict::Unverifiable, "{:?}", out.problem);
        assert!(out.problem.unwrap().contains("not fully unwound"));

        // Two loops that overlap, neither inside the other: a: if (x >= 100) goto out; b: x++; if (x % 2 == 0)
        // goto a; goto b. Each back edge to a starts b's count again, but nothing starts a's again, so the path
        // still ends, at a's fifth back edge.
        let cp = harness("()V", |code, _, _| {
            let (a, b, out) = (code.label(), code.label(), code.label());
            code.iconst(0);
            code.store(Kind::Int, 1);
            code.bind(a);
            code.load(Kind::Int, 1);
            code.iconst(100);
            code.if_icmp(Cond::Ge, out);
            code.bind(b);
            code.iinc(1, 1);
            code.load(Kind::Int, 1);
            code.iconst(2);
            code.op(0x70); // irem
            code.if_zero(Cond::Eq, a); // back to a, leaving b's loop
            code.goto(b); // back to b, after a's head
            code.bind(out);
        });
        let out = check(&cp, "Check", "check", &Options { unwind: 4, invariants: false, ..Options::default() }).unwrap();
        assert_eq!(out.verdict, Verdict::Unverifiable, "{:?}", out.problem);
        assert!(out.problem.unwrap().contains("not fully unwound"));
    }

    #[test]
    fn a_loop_is_unwound_per_call_of_its_method() {
        // count() runs a loop 3 times; four calls of it in a row are within --unwind 4.
        let cp = harness("()V", |code, writer, fail| {
            let mut callee = CodeBuilder::new();
            callee.max_locals = 2;
            callee.max_stack = 2;
            let (top, done) = (callee.label(), callee.label());
            callee.iconst(0);
            callee.store(Kind::Int, 0);
            callee.bind(top);
            callee.load(Kind::Int, 0);
            callee.iconst(3);
            callee.if_icmp(Cond::Ge, done);
            callee.iinc(0, 1);
            callee.goto(top);
            callee.bind(done);
            callee.load(Kind::Int, 0);
            callee.return_(Some(Kind::Int));
            writer.methods.push(MethodWriter { access: flags::PUBLIC | flags::STATIC, name: "count".into(), descriptor: "()I".into(), code: Some(callee) });
            let count = writer.pool.method_ref("Check", "count", "()I");
            for _ in 0..4 {
                code.op_u16(0xb8, count);
            }
            for _ in 0..3 {
                code.op(0x60); // iadd
            }
            code.iconst(12);
            code.if_icmp(Cond::Ne, fail);
        });
        let out = check(&cp, "Check", "check", &Options { unwind: 4, ..Options::default() }).unwrap();
        assert_eq!(out.verdict, Verdict::Verified, "{:?}", out.problem);
    }

    #[test]
    fn a_division_is_built_in_full_only_when_the_solver_gets_it_wrong() {
        // x % y < y for x >= 0 and y > 0: what holds of every remainder proves it, with no division circuit.
        let cp = harness("(II)V", |code, _, fail| {
            let ok = code.label();
            code.load(Kind::Int, 0);
            code.if_zero(Cond::Lt, ok);
            code.load(Kind::Int, 1);
            code.if_zero(Cond::Le, ok);
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.op(0x70); // irem
            code.load(Kind::Int, 1);
            code.if_icmp(Cond::Ge, fail);
            code.bind(ok);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Verified, "{:?}", out.problem);
        assert_eq!((out.divisions, out.refined), (1, 0), "{}", out.summary());

        // x / y == 3 claimed impossible: refuted with an input whose real quotient is 3, the circuit built if the
        // solver's first guess was not a real division.
        let cp = harness("(II)V", |code, _, fail| {
            let ok = code.label();
            code.load(Kind::Int, 1);
            code.if_zero(Cond::Eq, ok);
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.op(0x6c); // idiv
            code.iconst(3);
            code.if_icmp(Cond::Eq, fail);
            code.bind(ok);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Violation, "{:?}", out.problem);
        let (x, y): (i32, i32) = (out.raw_inputs[&0].parse().unwrap(), out.raw_inputs[&1].parse().unwrap());
        assert_eq!(x.wrapping_div(y), 3, "{x} / {y}");
        assert!(out.refined <= 1, "{}", out.summary());
        assert!(out.summary().contains(&format!("{} of 1 divisions and 0 of 0 multiplications built in full", out.refined)));
    }

    /// A run that writes its solver calls is the same run, and the transcript holds every clause and call it made,
    /// which give the same answers when run again ([`transcript`]).
    #[test]
    fn a_transcript_holds_every_clause_and_call_and_replays_with_the_same_answers() {
        // x / y == 3 claimed impossible, behind two branches: refuted, after calls on both branches and the
        // division's facts, perhaps its circuit too.
        let cp = harness("(II)V", |code, _, fail| {
            let ok = code.label();
            code.load(Kind::Int, 1);
            code.if_zero(Cond::Eq, ok);
            code.load(Kind::Int, 0);
            code.if_zero(Cond::Lt, ok);
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.op(0x6c); // idiv
            code.iconst(3);
            code.if_icmp(Cond::Eq, fail);
            code.bind(ok);
        });
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("deeper/check.icnf");
        let plain = run(&cp);
        let recorded = check(&cp, "Check", "check", &Options { transcript: Some(path.clone()), ..Options::default() }).unwrap();
        let same = |o: &Outcome| (o.verdict, o.paths, o.solves, o.clauses, o.variables, o.raw_inputs.clone(), o.refined);
        assert_eq!(same(&recorded), same(&plain));
        assert_eq!((plain.transcript.as_ref(), recorded.transcript.as_ref()), (None, Some(&path)));
        assert!(recorded.summary().ends_with(&format!("; solver calls written to {}", path.display())), "{}", recorded.summary());

        let text = std::fs::read_to_string(&path).unwrap();
        assert!(text.starts_with(&format!("c jvmcontract {}: the own checker's solver calls, in order", env!("CARGO_PKG_VERSION"))), "{text}");
        assert!(text.contains(&format!("\nc solver: {}\n", solver_signature())), "{text}");
        assert!(text.contains("\nc check: Check.check(II)V\nc options: unwind 16, max array length 8, max paths 200000, merge after 512, timeout 600.000 s, gaps strict\np inccnf\n1 0\n"), "{text}");
        let replay = transcript::replay(&path, None).unwrap();
        assert!(replay.calls.len() >= 2 && replay.calls.len() as u64 <= recorded.solves, "{} calls of {}", replay.calls.len(), recorded.solves);
        assert_eq!(replay.clauses, recorded.clauses);
        assert_eq!(replay.variables, recorded.variables);
        assert_eq!((replay.contradictions, replay.undecided, replay.decided), (0, 0, 0), "{}", replay.summary());
        assert!(replay.calls.iter().all(|c| c.limit.is_some_and(|l| l > 0.0 && l <= 600.0)), "{:?}", replay.calls);
        assert_eq!(replay.calls.last().map(|c| c.recorded), Some("sat"), "the violation's input is the last model asked for");
        assert_eq!(replay.ending, Some(format!("end: {} clauses, {} calls; Violation", recorded.clauses, replay.calls.len())));

        // One that cannot be written stops the run before it starts, since it was asked for.
        let blocked = dir.path().join("file");
        std::fs::write(&blocked, "").unwrap();
        let e = check(&cp, "Check", "check", &Options { transcript: Some(blocked.join("x.icnf")), ..Options::default() }).unwrap_err();
        assert!(e.to_string().starts_with("cannot write the transcript"), "{e}");
    }


    #[test]
    fn the_engine_gives_its_solver_nothing_but_clauses_limits_and_calls() {
        // The same refuted division as the transcript's test, on a solver behind the interface that logs what it is
        // given: the outcome is the plain run's, and the clauses and calls it saw are the outcome's and the
        // transcript's, in the same order.
        let cp = harness("(II)V", |code, _, fail| {
            let ok = code.label();
            code.load(Kind::Int, 1);
            code.if_zero(Cond::Eq, ok);
            code.load(Kind::Int, 0);
            code.if_zero(Cond::Lt, ok);
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.op(0x6c); // idiv
            code.iconst(3);
            code.if_icmp(Cond::Eq, fail);
            code.bind(ok);
        });
        let plain = run(&cp);
        sat::Logged::take();
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("logged.icnf");
        let logged = check(&cp, "Check", "check", &Options { solver: sat::Logged::boxed, transcript: Some(path.clone()), ..Options::default() }).unwrap();
        let events = sat::Logged::take();
        let same = |o: &Outcome| (o.verdict, o.paths, o.solves, o.clauses, o.variables, o.raw_inputs.clone(), o.refined);
        assert_eq!(same(&logged), same(&plain));

        let clauses: Vec<&Vec<Lit>> = events.iter().filter_map(|e| if let sat::Event::Clause(c) = e { Some(c) } else { None }).collect();
        let calls: Vec<(&Vec<Lit>, Option<bool>)> = events.iter().filter_map(|e| if let sat::Event::Solve(a, r) = e { Some((a, *r)) } else { None }).collect();
        assert_eq!(clauses.len() as u64, logged.clauses);
        assert_eq!(clauses.first().map(|c| c.as_slice()), Some(&[TRUE][..]), "the constant first");
        assert!(calls.len() >= 2 && calls.len() as u64 <= logged.solves, "{} calls of {}", calls.len(), logged.solves);
        // Every call is made under the limit last set, and the limit is within the check's budget; a branch probe is
        // limited by conflicts as well, at least the floor's (VF-010), and every other call is not.
        let mut limit = None;
        for e in &events {
            match e {
                sat::Event::Limit(l) => limit = *l,
                sat::Event::Solve(..) => assert!(limit.is_some_and(|l| l > 0.0 && l <= 600.0), "{events:?}"),
                sat::Event::Clause(_) | sat::Event::WorkLimit(_) => {}
            }
        }
        let work_limits = |events: &[sat::Event]| {
            let mut work = None;
            events.iter().filter_map(|e| match e {
                sat::Event::WorkLimit(w) => {
                    work = *w;
                    None
                }
                sat::Event::Solve(..) => Some(work),
                _ => None,
            }).collect::<Vec<_>>()
        };
        let probes = work_limits(&events);
        assert!(probes.contains(&Some(PROBE_CONFLICTS)) && probes.contains(&None), "{probes:?}");

        // The transcript names the solver the check ran on, and holds what that solver was given.
        let text = std::fs::read_to_string(&path).unwrap();
        assert!(text.contains(&format!("\nc solver: logged {}\n", solver_signature())), "{text}");
        let replay = transcript::replay_on(&mut sat::Cadical::new(), &path, None).unwrap();
        assert_eq!(replay.clauses, logged.clauses);
        assert_eq!(replay.calls.iter().map(|c| c.recorded).collect::<Vec<_>>(), calls.iter().map(|(_, r)| transcript::answer_name(*r)).collect::<Vec<_>>());
        assert_eq!(replay.calls.iter().map(|c| c.assumptions).collect::<Vec<_>>(), calls.iter().map(|(a, _)| a.len()).collect::<Vec<_>>());
        assert_eq!(replay.contradictions, 0, "{}", replay.summary());

        // A replay goes through the interface too: on the logged solver it gives the same clauses and calls again.
        let again = transcript::replay_on(&mut *sat::Logged::boxed(), &path, None).unwrap();
        assert_eq!(again.solver, format!("logged {}", solver_signature()));
        let replayed = sat::Logged::take();
        assert_eq!(replayed.iter().filter(|e| matches!(e, sat::Event::Clause(_))).cloned().collect::<Vec<_>>(), events.iter().filter(|e| matches!(e, sat::Event::Clause(_))).cloned().collect::<Vec<_>>());
        assert_eq!(replayed.iter().filter_map(|e| if let sat::Event::Solve(a, r) = e { Some((a.clone(), *r)) } else { None }).collect::<Vec<_>>(), calls.iter().map(|(a, r)| ((*a).clone(), *r)).collect::<Vec<_>>());
        // The transcript holds each probe's conflict limit, and the replay gives it again.
        assert_eq!(work_limits(&replayed), probes);
    }

    #[test]
    fn a_check_on_bitwuzla_decides_as_on_cadical_and_replays_cadicals_calls() {
        // Bitwuzla given the engine's clauses (Phase 6c's SAT-only comparison), and given its terms (the word-level
        // prototype), when it is installed here. Its models may differ from CaDiCaL's, and so the lemmas and the
        // input found, but not the verdicts.
        if let Err(e) = bitwuzla::available() {
            eprintln!("skipped: {}", e.0);
            return;
        }
        let division = harness("(II)V", |code, _, fail| {
            let ok = code.label();
            code.load(Kind::Int, 1);
            code.if_zero(Cond::Eq, ok);
            code.load(Kind::Int, 0);
            code.if_zero(Cond::Lt, ok);
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.op(0x6c); // idiv
            code.iconst(3);
            code.if_icmp(Cond::Eq, fail);
            code.bind(ok);
        });
        let product = harness("(II)V", |code, _, fail| {
            let ok = code.label();
            code.load(Kind::Int, 1);
            code.iconst(8);
            code.if_icmp(Cond::Ne, ok);
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.op(0x68); // imul
            code.load(Kind::Int, 0);
            code.iconst(3);
            code.op(0x78); // ishl
            code.if_icmp(Cond::Ne, fail);
            code.bind(ok);
        });
        let dir = tempfile::tempdir().unwrap();
        for (name, cp, expected) in [("division", &division, Verdict::Violation), ("product", &product, Verdict::Verified)] {
            let cadical_path = dir.path().join(format!("{name}-cadical.icnf"));
            let bitwuzla_path = dir.path().join(format!("{name}-bitwuzla.icnf"));
            let on_cadical = check(cp, "Check", "check", &Options { solver: sat::cadical, transcript: Some(cadical_path.clone()), ..Options::default() }).unwrap();
            let on_bitwuzla = check(cp, "Check", "check", &Options { solver: bitwuzla::boxed, transcript: Some(bitwuzla_path.clone()), ..Options::default() }).unwrap();
            assert_eq!(on_cadical.verdict, expected, "{name}: {}", on_cadical.summary());
            assert_eq!(on_bitwuzla.verdict, expected, "{name}: {}", on_bitwuzla.summary());
            assert_eq!((on_cadical.solver.as_str(), on_bitwuzla.solver.as_str()), ("CaDiCaL", "Bitwuzla"));
            if expected == Verdict::Violation {
                // The input Bitwuzla's model gives is a violation too: x >= 0, y != 0 and x / y == 3.
                let (x, y): (i32, i32) = (on_bitwuzla.raw_inputs[&0].parse().unwrap(), on_bitwuzla.raw_inputs[&1].parse().unwrap());
                assert!(x >= 0 && y != 0 && x.wrapping_div(y) == 3, "{x} / {y}");
            }
            // Each transcript names its solver, and CaDiCaL's calls, replayed on Bitwuzla, get CaDiCaL's answers.
            let text = std::fs::read_to_string(&bitwuzla_path).unwrap();
            assert!(text.contains("\nc solver: Bitwuzla 0.8.2 "), "{text}");
            let replay = transcript::replay_on(&mut bitwuzla::Bitwuzla::new().unwrap(), &cadical_path, None).unwrap();
            assert_eq!(replay.clauses, on_cadical.clauses);
            assert_eq!(replay.contradictions, 0, "{name}: {}", replay.summary());
            assert!(replay.solver.starts_with("Bitwuzla 0.8.2 "), "{}", replay.solver);
            // Given terms: the same verdict, a real input, the operations as terms and no lemma, and no transcript,
            // since there are no clauses to record.
            let on_terms = check(cp, "Check", "check", &Options { solver: bitwuzla::boxed_words, ..Options::default() }).unwrap();
            assert_eq!(on_terms.verdict, expected, "{name}: {}", on_terms.summary());
            assert_eq!(on_terms.clauses, 1, "{name}: only the constant's unit clause");
            assert_eq!((on_terms.divisions, on_terms.multiplications), (0, 0), "{name}: {}", on_terms.summary());
            if expected == Verdict::Violation {
                let (x, y): (i32, i32) = (on_terms.raw_inputs[&0].parse().unwrap(), on_terms.raw_inputs[&1].parse().unwrap());
                assert!(x >= 0 && y != 0 && x.wrapping_div(y) == 3, "{x} / {y}");
            }
            let refused = check(cp, "Check", "check", &Options { solver: bitwuzla::boxed_words, transcript: Some(dir.path().join("terms.icnf")), ..Options::default() }).unwrap_err();
            assert!(refused.0.contains("it records clauses"), "{}", refused.0);
        }
    }
    #[test]
    fn a_multiplication_is_built_in_full_only_when_the_solver_gets_it_wrong() {
        // x * y == x << 3 for y == 8: what holds of every product proves it, with no multiplier.
        let cp = harness("(II)V", |code, _, fail| {
            let ok = code.label();
            code.load(Kind::Int, 1);
            code.iconst(8);
            code.if_icmp(Cond::Ne, ok);
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.op(0x68); // imul
            code.load(Kind::Int, 0);
            code.iconst(3);
            code.op(0x78); // ishl
            code.if_icmp(Cond::Ne, fail);
            code.bind(ok);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Verified, "{:?}", out.problem);
        assert_eq!((out.multiplications, out.refined_multiplications), (1, 0), "{}", out.summary());

        // (x / y) * y == x - x % y: the identity, the same bits on both sides, no product and no circuit.
        let cp = harness("(II)V", |code, _, fail| {
            let ok = code.label();
            code.load(Kind::Int, 1);
            code.if_zero(Cond::Eq, ok);
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.op(0x6c); // idiv
            code.load(Kind::Int, 1);
            code.op(0x68); // imul
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.op(0x70); // irem
            code.op(0x64); // isub
            code.if_icmp(Cond::Ne, fail);
            code.bind(ok);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Verified, "{:?}", out.problem);
        assert_eq!((out.divisions, out.refined, out.multiplications), (1, 0, 0), "{}", out.summary());

        // x * y == 150000 claimed impossible: refuted with factors whose real product is that, the circuit built
        // if the solver's first guess was not a real product.
        let cp = harness("(II)V", |code, _, fail| {
            let ok = code.label();
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.op(0x68); // imul
            code.iconst(30_000);
            code.iconst(5);
            code.op(0x68); // imul of constants, folded: 150000
            code.if_icmp(Cond::Eq, fail);
            code.bind(ok);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Violation, "{:?}", out.problem);
        let (x, y): (i32, i32) = (out.raw_inputs[&0].parse().unwrap(), out.raw_inputs[&1].parse().unwrap());
        assert_eq!(x.wrapping_mul(y), 150_000, "{x} * {y}");
        assert!(out.refined_multiplications <= 1, "{}", out.summary());
    }

    #[test]
    fn an_array_parameter_has_every_length_up_to_the_bound_and_its_elements_are_inputs() {
        // a.length <= 8 (the default bound) holds; a.length < 8 does not, and the array named is 8 long.
        let cp = harness("([I)V", |code, _, fail| {
            code.load(Kind::Ref, 0);
            code.op(0xbe); // arraylength
            code.iconst(8);
            code.if_icmp(Cond::Gt, fail);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Verified, "{:?}", out.problem);
        let cp = harness("([I)V", |code, _, fail| {
            code.load(Kind::Ref, 0);
            code.op(0xbe);
            code.iconst(8);
            code.if_icmp(Cond::Ge, fail);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Violation, "{:?}", out.problem);
        assert_eq!(out.raw_arrays[&0].as_ref().unwrap().len(), 8);

        // a.length == 2 && a[0] + a[1] == 10 is claimed impossible: refuted, with the two elements named, from
        // the first stage.
        let cp = harness("([I)V", |code, _, fail| {
            let ok = code.label();
            code.load(Kind::Ref, 0);
            code.op(0xbe);
            code.iconst(2);
            code.if_icmp(Cond::Ne, ok);
            code.load(Kind::Ref, 0);
            code.iconst(0);
            code.op(0x2e); // iaload
            code.load(Kind::Ref, 0);
            code.iconst(1);
            code.op(0x2e);
            code.op(0x60); // iadd
            code.iconst(10);
            code.if_icmp(Cond::Eq, fail);
            code.bind(ok);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Violation, "{:?}", out.problem);
        let a: Vec<i32> = out.raw_arrays[&0].as_ref().unwrap().iter().map(|v| v.parse().unwrap()).collect();
        assert_eq!(a.len(), 2, "{a:?}");
        assert_eq!(a[0] + a[1], 10, "{a:?}");
        assert!(a.iter().all(|v| (0..=20).contains(v)), "{a:?}");
        assert_eq!(out.stage.as_deref(), Some("[0:20]"));
        assert!(out.raw_inputs.is_empty());
    }

    #[test]
    fn an_index_out_of_bounds_is_an_exception_path_and_a_store_is_read_back() {
        // a[i] throws ArrayIndexOutOfBoundsException exactly when i < 0 || i >= a.length.
        let cp = harness("([II)V", |code, writer, fail| {
            let try_start = code.label();
            let try_end = code.label();
            let handler = code.label();
            let ok = code.label();
            let out_of_bounds = code.label();
            code.bind(try_start);
            code.load(Kind::Ref, 0);
            code.load(Kind::Int, 1);
            code.op(0x2e); // iaload
            code.op(0x57); // pop
            code.load(Kind::Int, 1);
            code.if_zero(Cond::Lt, fail); // read although i < 0: impossible
            code.load(Kind::Int, 1);
            code.load(Kind::Ref, 0);
            code.op(0xbe);
            code.if_icmp(Cond::Ge, fail); // read although i >= a.length: impossible
            code.bind(try_end);
            code.goto(ok);
            code.bind(handler);
            code.op(0x57);
            code.load(Kind::Int, 1);
            code.if_zero(Cond::Lt, out_of_bounds);
            code.load(Kind::Int, 1);
            code.load(Kind::Ref, 0);
            code.op(0xbe);
            code.if_icmp(Cond::Ge, out_of_bounds);
            code.goto(fail); // thrown although 0 <= i < a.length: impossible
            code.bind(out_of_bounds);
            code.bind(ok);
            let exception = writer.pool.class("java/lang/ArrayIndexOutOfBoundsException");
            code.handler(try_start, try_end, handler, Some(exception));
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Verified, "{:?}", out.problem);

        // With 0 <= i, j < a.length and i != j: after a[i] = v, a[i] == v and a[j] is what it was.
        let cp = harness("([IIII)V", |code, _, fail| {
            let ok = code.label();
            code.load(Kind::Int, 1);
            code.if_zero(Cond::Lt, ok);
            code.load(Kind::Int, 2);
            code.if_zero(Cond::Lt, ok);
            code.load(Kind::Int, 1);
            code.load(Kind::Ref, 0);
            code.op(0xbe);
            code.if_icmp(Cond::Ge, ok);
            code.load(Kind::Int, 2);
            code.load(Kind::Ref, 0);
            code.op(0xbe);
            code.if_icmp(Cond::Ge, ok);
            code.load(Kind::Int, 1);
            code.load(Kind::Int, 2);
            code.if_icmp(Cond::Eq, ok);
            code.load(Kind::Ref, 0);
            code.load(Kind::Int, 2);
            code.op(0x2e);
            code.store(Kind::Int, 4); // b = a[j]
            code.load(Kind::Ref, 0);
            code.load(Kind::Int, 1);
            code.load(Kind::Int, 3);
            code.op(0x4f); // a[i] = v
            code.load(Kind::Ref, 0);
            code.load(Kind::Int, 1);
            code.op(0x2e);
            code.load(Kind::Int, 3);
            code.if_icmp(Cond::Ne, fail); // a[i] != v: impossible
            code.load(Kind::Ref, 0);
            code.load(Kind::Int, 2);
            code.op(0x2e);
            code.load(Kind::Int, 4);
            code.if_icmp(Cond::Ne, fail); // a[j] != b: impossible
            code.bind(ok);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Verified, "{:?}", out.problem);
    }

    /// Phase 5 of `llm-dlc/loops/engine-priorities.md`, enums: an array of references holds an object or null per
    /// cell, an index that is an input splits the path per cell, at a join too and with the paths merged there, and
    /// `clone()` is another array with the same cells.
    #[test]
    fn an_array_of_references_holds_its_objects_and_an_input_index_splits_the_path() {
        // For 0 <= n <= 2: a = new Object[3]; a[0] = "x"; a[1] = a; r = a[n > 0 ? n : 0], the index chosen at a join.
        // r is null exactly when n == 2; b = a.clone() has r at n, and b[0] = b leaves a[0] the literal.
        // `violate` adds `assert r != a`, which n == 1 refutes.
        let build = |violate: bool| {
            harness("(I)V", move |code, w, fail| {
                let (done, zero, index, some, next) = (code.label(), code.label(), code.label(), code.label(), code.label());
                let object = w.pool.class("java/lang/Object");
                let objects = w.pool.class("[Ljava/lang/Object;");
                let x = w.pool.string("x");
                let clone = w.pool.method_ref("[Ljava/lang/Object;", "clone", "()Ljava/lang/Object;");
                code.load(Kind::Int, 0);
                code.if_zero(Cond::Lt, done);
                code.load(Kind::Int, 0);
                code.iconst(2);
                code.if_icmp(Cond::Gt, done);
                code.iconst(3);
                code.op_u16(0xbd, object); // anewarray
                code.store(Kind::Ref, 1);
                code.load(Kind::Ref, 1);
                code.iconst(0);
                code.ldc(x);
                code.op(0x53); // aastore
                code.load(Kind::Ref, 1);
                code.iconst(1);
                code.load(Kind::Ref, 1);
                code.op(0x53);
                code.load(Kind::Ref, 1);
                code.load(Kind::Int, 0);
                code.if_zero(Cond::Le, zero);
                code.load(Kind::Int, 0);
                code.goto(index);
                code.bind(zero);
                code.iconst(0);
                code.bind(index);
                code.op(0x32); // aaload
                code.store(Kind::Ref, 2);
                code.load(Kind::Ref, 2);
                code.if_nonnull(some);
                code.load(Kind::Int, 0);
                code.iconst(2);
                code.if_icmp(Cond::Ne, fail);
                code.goto(next);
                code.bind(some);
                code.load(Kind::Int, 0);
                code.iconst(2);
                code.if_icmp(Cond::Eq, fail);
                code.bind(next);
                code.load(Kind::Ref, 1);
                code.op_u16(0xb6, clone);
                code.op_u16(0xc0, objects); // checkcast
                code.store(Kind::Ref, 3);
                code.load(Kind::Ref, 3);
                code.load(Kind::Int, 0);
                code.op(0x32);
                code.load(Kind::Ref, 2);
                code.if_acmpne(fail);
                code.load(Kind::Ref, 3);
                code.iconst(0);
                code.load(Kind::Ref, 3);
                code.op(0x53);
                code.load(Kind::Ref, 1);
                code.iconst(0);
                code.op(0x32);
                code.ldc(x);
                code.if_acmpne(fail);
                if violate {
                    let fine = code.label();
                    code.load(Kind::Ref, 2);
                    code.load(Kind::Ref, 1);
                    code.if_acmpne(fine);
                    code.goto(fail);
                    code.bind(fine);
                }
                code.bind(done);
            })
        };
        let merged = Options { merge_after: 0, ..Options::default() };
        for options in [Options::default(), merged.clone()] {
            let out = check(&build(false), "Check", "check", &options).unwrap();
            assert_eq!(out.verdict, Verdict::Verified, "merge after {}: {:?} {}", options.merge_after, out.problem, out.summary());
            let out = check(&build(true), "Check", "check", &options).unwrap();
            assert_eq!(out.verdict, Verdict::Violation, "merge after {}: {:?} {}", options.merge_after, out.problem, out.summary());
            assert_eq!(out.raw_inputs.get(&0).map(String::as_str), Some("1"), "{:?}", out.raw_inputs);
        }
        let out = check(&build(false), "Check", "check", &merged).unwrap();
        assert!(out.merges > 0, "the paths met at the index's join and were merged: {}", out.summary());

        // An object stored into an array of another element type (ArrayStoreException) is refused.
        let cp = harness("(I)V", |code, w, _| {
            let strings = w.pool.class("java/lang/String");
            let object = w.pool.class("java/lang/Object");
            let init = w.pool.method_ref("java/lang/Object", "<init>", "()V");
            code.iconst(1);
            code.op_u16(0xbd, strings);
            code.iconst(0);
            code.op_u16(0xbb, object);
            code.op(0x59);
            code.op_u16(0xb7, init);
            code.op(0x53);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Unverifiable, "{:?}", out.problem);
        assert!(out.problem.as_deref().unwrap_or("").contains("ArrayStoreException"), "{:?}", out.problem);
    }

    #[test]
    fn a_new_array_is_within_the_bound_or_beyond_the_engine_and_cells_are_as_wide_as_their_elements() {
        // A copy as long as the parameter, filled by the harness's loop, reads back the same: the size is the
        // parameter's length, which the first path's condition bounds.
        let cp = harness("([I)V", |code, _, fail| {
            let loop_ = code.label();
            let done = code.label();
            let check = code.label();
            let checked = code.label();
            code.load(Kind::Ref, 0);
            code.op(0xbe);
            code.op_u8(0xbc, 10); // newarray int
            code.store(Kind::Ref, 1);
            code.iconst(0);
            code.store(Kind::Int, 2);
            code.bind(loop_);
            code.load(Kind::Int, 2);
            code.load(Kind::Ref, 0);
            code.op(0xbe);
            code.if_icmp(Cond::Ge, done);
            code.load(Kind::Ref, 1);
            code.load(Kind::Int, 2);
            code.load(Kind::Ref, 0);
            code.load(Kind::Int, 2);
            code.op(0x2e);
            code.op(0x4f);
            code.iinc(2, 1);
            code.goto(loop_);
            code.bind(done);
            code.iconst(0);
            code.store(Kind::Int, 2);
            code.bind(check);
            code.load(Kind::Int, 2);
            code.load(Kind::Ref, 0);
            code.op(0xbe);
            code.if_icmp(Cond::Ge, checked);
            code.load(Kind::Ref, 1);
            code.load(Kind::Int, 2);
            code.op(0x2e);
            code.load(Kind::Ref, 0);
            code.load(Kind::Int, 2);
            code.op(0x2e);
            code.if_icmp(Cond::Ne, fail);
            code.iinc(2, 1);
            code.goto(check);
            code.bind(checked);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Verified, "{:?} {:?} {}", out.problem, out.raw_arrays, out.paths);

        // An array of a size the engine cannot bound is beyond it.
        let cp = harness("(I)V", |code, _, _| {
            code.load(Kind::Int, 0);
            code.op_u8(0xbc, 10);
            code.op(0x57);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Unverifiable, "{:?}", out.problem);
        assert!(out.problem.as_deref().unwrap_or("").contains("computed size"), "{:?}", out.problem);

        // A byte array's cell keeps eight bits: 200 stored reads back as -56; a char's sixteen, without sign.
        let cp = harness("([B[C)V", |code, _, fail| {
            let ok = code.label();
            code.load(Kind::Ref, 0);
            code.op(0xbe);
            code.if_zero(Cond::Eq, ok);
            code.load(Kind::Ref, 1);
            code.op(0xbe);
            code.if_zero(Cond::Eq, ok);
            code.load(Kind::Ref, 0);
            code.iconst(0);
            code.iconst(20);
            code.iconst(10);
            code.op(0x68); // imul: 200 folded, since iconst takes a byte
            code.op(0x54); // bastore
            code.load(Kind::Ref, 0);
            code.iconst(0);
            code.op(0x33); // baload
            code.iconst(-56);
            code.if_icmp(Cond::Ne, fail);
            code.load(Kind::Ref, 1);
            code.iconst(0);
            code.op(0x34); // caload
            code.if_zero(Cond::Lt, fail);
            code.load(Kind::Ref, 1);
            code.iconst(0);
            code.iconst(-1);
            code.op(0x55); // castore
            code.load(Kind::Ref, 1);
            code.iconst(0);
            code.op(0x34);
            code.iconst(16);
            code.iconst(16);
            code.op(0x68);
            code.op(0x59); // dup
            code.op(0x68); // imul: 65536 folded
            code.iconst(1);
            code.op(0x64); // isub
            code.if_icmp(Cond::Ne, fail);
            code.bind(ok);
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Verified, "{:?}", out.problem);
    }

    #[test]
    fn an_overflow_check_calls_into_math() {
        // Math.multiplyExact(a, b) throws exactly when (long) a * b does not fit an int, and returns a * b
        // otherwise: both sides are the engine's own circuits, which fold together.
        let cp = harness("(II)V", |code, writer, fail| {
            let try_start = code.label();
            let try_end = code.label();
            let handler = code.label();
            let ok = code.label();
            let exact = writer.pool.method_ref("java/lang/Math", "multiplyExact", "(II)I");
            let fits = |code: &mut CodeBuilder, target| {
                // (long) a * (long) b == (long) (a * b)  ->  jump to target
                code.load(Kind::Int, 0);
                code.op(0x85); // i2l
                code.load(Kind::Int, 1);
                code.op(0x85);
                code.op(0x69); // lmul
                code.load(Kind::Int, 0);
                code.load(Kind::Int, 1);
                code.op(0x68); // imul
                code.op(0x85);
                code.op(0x94); // lcmp
                code.if_zero(Cond::Eq, target);
            };
            code.bind(try_start);
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.op_u16(0xb8, exact);
            code.load(Kind::Int, 0);
            code.load(Kind::Int, 1);
            code.op(0x68);
            code.if_icmp(Cond::Ne, fail); // the exact product is the product
            let fine = code.label();
            fits(code, fine);
            code.goto(fail); // returned although the product does not fit
            code.bind(fine);
            code.bind(try_end);
            code.goto(ok);
            code.bind(handler);
            code.op(0x57);
            fits(code, fail); // threw although the product fits
            code.bind(ok);
            let arithmetic = writer.pool.class("java/lang/ArithmeticException");
            code.handler(try_start, try_end, handler, Some(arithmetic));
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Verified, "{:?}", out.problem);

        // addExact on longs: a claim that it never throws is refuted with inputs that overflow.
        let cp = harness("(JJ)V", |code, writer, fail| {
            let try_start = code.label();
            let try_end = code.label();
            let handler = code.label();
            let ok = code.label();
            let exact = writer.pool.method_ref("java/lang/Math", "addExact", "(JJ)J");
            code.bind(try_start);
            code.load(Kind::Long, 0);
            code.load(Kind::Long, 2);
            code.op_u16(0xb8, exact);
            code.op(0x58); // pop2
            code.bind(try_end);
            code.goto(ok);
            code.bind(handler);
            code.op(0x57);
            code.goto(fail);
            code.bind(ok);
            let arithmetic = writer.pool.class("java/lang/ArithmeticException");
            code.handler(try_start, try_end, handler, Some(arithmetic));
        });
        let out = run(&cp);
        assert_eq!(out.verdict, Verdict::Violation, "{:?}", out.problem);
        let a: i64 = out.raw_inputs[&0].parse().unwrap();
        let b: i64 = out.raw_inputs[&2].parse().unwrap();
        assert!(a.checked_add(b).is_none(), "{a} + {b}");
    }
}
