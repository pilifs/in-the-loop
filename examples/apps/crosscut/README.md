# Crosscut

The pure kernels behind the cross-cutting concerns of a Spring Boot service: the decision a transaction interceptor makes, a circuit breaker's state machine, a retry policy, a rate limiter's refill, an `Idempotency-Key` receiver, a Kafka partitioner and a batch listener's commit, a JWT validator's clock-skew check, and a cache's expiry.
Each is the few lines inside a framework component that decide what happens, written as a function so that it can be proved, with the framework component left to perform what the kernel decides.
It is the third subject system of the [examples](../../README.md) (023 to 033, 075 to 080, 120, 122 to 139, 150 to 152), verified by [`jvmcontract`](../../../lib/README.md), the Rust tool.

The design rule is the one that makes these kernels provable and the framework around them testable: a kernel takes its inputs as arguments (the clock reading, the HTTP status, whether a transaction is active) and returns a decision; it reads no clock, spawns no thread and touches no socket of its own.
The module's [capability contract](src/contract/capabilities.contract) says so, with every capability `none`, and the build checks it.
Every kernel here has a contract, a property, a regression proof or a model checked on every build.

## The kernels, and the Spring component each sits in

| Kernel | Where it lives in a service | What it decides | Verified by | Examples |
|---|---|---|---|---|
| [`tx.TransactionBoundary`](src/main/java/net/terminalvalue/crosscut/tx/TransactionBoundary.java) | `TransactionInterceptor` around a `@Transactional` method | How the method enlists in the running transaction (the seven propagations), and whether the transaction commits or rolls back when the method ends (runtime exception, error, checked exception, `rollbackFor`, `noRollbackFor`, rollback-only) | Behavioural contracts: all [16](src/contract/TransactionBoundary.enter.contract) and [22](src/contract/TransactionBoundary.exit.contract) cases | 025 |
| [`resilience.CircuitBreaker`](src/main/java/net/terminalvalue/crosscut/resilience/CircuitBreaker.java) | A Resilience4j `CircuitBreaker` (`@CircuitBreaker`) | The CLOSED, OPEN and HALF_OPEN transitions on each call requested and each call completed | A [behavioural contract](src/contract/CircuitBreaker.decide.contract): all 44 cases, drawn as a state machine, and a [TLA+ model](spec/README.md#the-circuit-breaker-model) of the component that owns the breaker, checked by TLC for its invariants and, under fairness, for three liveness properties | 026, 075, 076, 077 |
| [`retry.RetryPolicy`](src/main/java/net/terminalvalue/crosscut/retry/RetryPolicy.java) | A `RestClient` or `WebClient` retry filter, `@Retryable` | Whether a failed HTTP call may be retried, by status, idempotency and attempt | A property: never past the last attempt, never a non-idempotent request the server may have run, never 501; regression proofs against the previous version | 027, 028 |
| [`retry.Backoff`](src/main/java/net/terminalvalue/crosscut/retry/Backoff.java) | The same filter's wait between attempts (Spring Retry's `ExponentialBackOffPolicy`, Resilience4j's `IntervalFunction.ofExponentialBackoff`) | How long the next attempt waits: the base doubled up to the cap, a record's method on its own components | Regression proofs against the previous version, on the record's components, and across a component added to the record | 126, 127, 130, 131 |
| [`retry.RetryThrottling`](src/main/java/net/terminalvalue/crosscut/retry/RetryThrottling.java) | A gRPC channel's retry throttling (`retryThrottling` in its service config) | What a call's outcome does to the channel's `Throttle`, a mutable object every call shares, and whether a retry may be made; which throttle the channel keeps across a config update | Regression proofs over the throttle as an object made by its constructor, which makes it full: its fields as each version leaves it and the identity relations within each version compared, the claim covering constructor-made throttles only | 150, 151, 152 |
| [`ratelimit.TokenBucket`](src/main/java/net/terminalvalue/crosscut/ratelimit/TokenBucket.java) | Spring Cloud Gateway's `RequestRateLimiter`, Bucket4j | The tokens and the credited time after a refill | Properties: never below the tokens held, never above the capacity, no part of a period forgotten; regression proofs of the refill within the module's precondition, by the tool's own checker | 031, 132, 133 |
| [`ratelimit.Window`](src/main/java/net/terminalvalue/crosscut/ratelimit/Window.java) | A fixed-window counter per client (Spring Cloud Gateway's rate limiter, Resilience4j's `RateLimiter` cycles) | The counter after a request: one more in the same window, or the first of a new one, as a record the method returns | Regression proofs across the counter record gaining a component, the records related on the components they share, of the start aligned by a mask instead of a remainder, and of the start as the window's index times its length, held in a `long` or in an `int` | 134 to 139 |
| [`ratelimit.RetryAfter`](src/main/java/net/terminalvalue/crosscut/ratelimit/RetryAfter.java) | The `Retry-After` a gateway answers a refused request with (Bucket4j's `nanosToWaitForRefill`) | How long a refused request waits for a token, from the refill arithmetic above | A property: nothing while a token is there, else at most a period; regression proofs against the previous version, with the refill helpers it calls taken as one function in both versions | 120 |
| [`idempotency.IdempotentReceiver`](src/main/java/net/terminalvalue/crosscut/idempotency/IdempotentReceiver.java) | A `OncePerRequestFilter` for the `Idempotency-Key` header | Execute, replay the stored response, or refuse (409, 422), per key state | A [behavioural contract](src/contract/IdempotentReceiver.decide.contract), and a [TLA+ model](spec/README.md) of a client retrying against it, checked by TLC under two configurations, the record expiring or not | 029, 030, 078, 079, 080 |
| [`kafka.Partitioner`](src/main/java/net/terminalvalue/crosscut/kafka/Partitioner.java) | A custom `Partitioner` for a `KafkaTemplate` | The partition of a key's hash | A property: every hash lands on a partition of the topic; a regression proof against the previous version, by the tool's own checker | 023, 124 |
| [`kafka.BatchCommit`](src/main/java/net/terminalvalue/crosscut/kafka/BatchCommit.java) | A batch `@KafkaListener` with the `DefaultErrorHandler` | The offset to commit after a batch with a failed record | A property: one past the last record that is done, never further, never short; a regression proof of its move into a `Batch` record against the static function | 032, 128, 129 |
| [`security.JwtTimestamps`](src/main/java/net/terminalvalue/crosscut/security/JwtTimestamps.java) | Spring Security's `JwtTimestampValidator` | Whether a token is valid at an instant, with the clock-skew tolerance | Properties: skew only widens acceptance, and a token is valid at every instant of its window; a regression proof under the module's precondition, by the tool's own checker | 024, 125 |
| [`cache.Expiry`](src/main/java/net/terminalvalue/crosscut/cache/Expiry.java) | A `@Cacheable` cache's expire-after-write (Caffeine) | Whether an entry has expired, with `Long.MAX_VALUE` as "never" | A property: expired exactly when the time to live has elapsed; regression proofs of the test turned into the time left, related to the boolean by a stated relation | 033, 122, 123 |

The framework glue is not in this module: it is where the clock, the thread pool, the database and the HTTP response live, and it is what the service's integration tests cover.
A kernel is used from it in one line, for example in a transaction interceptor:

```java
TransactionOutcome outcome = TransactionBoundary.exit(completionOf(invocation), status.isRollbackOnly());
```

so that the part of the component that decides is the part the build proves, and the part that performs is the part the tests exercise.

## Layout

```
src/main/java/        the kernels
src/test/java/        plain tests, run by Tests.main; no framework, no build system
src/contract/         the contracts the build checks:
  *.decide.contract, *.enter.contract, *.exit.contract   behavioural contracts (generated by `jvmcontract update`)
  properties.contract   the properties proved by JBMC (written by hand; the proofs are regenerated)
  capabilities.contract what the module's bytecode can reach (generated)
  api.contract          the public surface (generated)
spec/                 the TLA+ models of the idempotent receiver and the circuit breaker, each with a second configuration (an expiring record; liveness); the *Contract.tla files are generated from the contracts
verify.sh             compile, test, and run every check below
```

## Verify it

```bash
examples/apps/crosscut/verify.sh
```

which is, step by step (from this directory, with `jvmcontract` on the `PATH`, as `cargo install --path ../../../lib` puts it):

```bash
javac -parameters -g -d build/main $(find src/main/java -name '*.java')
javac -parameters -g -cp build/main -d build/test $(find src/test/java -name '*.java')
java -ea -cp build/main:build/test net.terminalvalue.crosscut.Tests

jvmcontract verify --contracts src/contract --classes build/main --module crosscut --sources src/main/java
jvmcontract prove --properties src/contract/properties.contract --classes build/main
jvmcontract tla src/contract/IdempotentReceiver.decide.contract spec/IdempotentReceiverContract.tla
jvmcontract tlc spec/IdempotentReceiver.tla --library ../../tools/tla/standard-modules
jvmcontract tlc spec/IdempotentReceiver.tla --config spec/IdempotentReceiverExpiring.cfg --library ../../tools/tla/standard-modules
jvmcontract tla src/contract/CircuitBreaker.decide.contract spec/CircuitBreakerContract.tla
jvmcontract tlc spec/CircuitBreaker.tla --library ../../tools/tla/standard-modules
jvmcontract tlc spec/CircuitBreaker.tla --config spec/CircuitBreakerLive.cfg --library ../../tools/tla/standard-modules
```

Compiling takes a second, the tests less, the four contracts milliseconds, the seven property proofs in about forty seconds with JBMC (the token bucket's refill time, with its remainder, is most of it), and TLC a second for each of the four model runs (168 states and 308, 102 and 102).
No Gradle and no JVM start is needed for the contracts: `jvmcontract` reads the class files and the JDK's image directly.

To change a kernel's behaviour on purpose: make the change, run `jvmcontract update --contracts src/contract --classes build/main --module crosscut`, and commit the contract diff with the code. To state a new guarantee: add a block to `properties.contract`.
