# Shop

A small pricing kernel behind one thin Spring route, so that a check can take in every part of a change at once:
what the route's consumers observe, how the kernel's old and new objects correspond, and which proofs can be reused.
It is the subject of the joint-run examples, checked by `jvmcontract compare`
([`lib/README.md`](../../../lib/README.md#comparing-two-builds)). Its sources are the `before` build of the
foundations loop's joint example, [`lib/tests/fixtures/foundations/`](../../../lib/tests/fixtures/foundations/README.md),
and its examples' patches turn it into that fixture's `after` build and each of its defects; the fixture is what
`lib/tests/compare.rs` holds the tool to, and the examples are the same change run by `build.py`.

[`QuotesController`](src/main/java/shop/QuotesController.java) answers `POST /quotes` with the total of a quote, an
amount in cents for each item and how many items, and sends a `QuoteEvent` to the `quotes` topic through a
`KafkaTemplate` when the total is positive. [`Pricing`](src/main/java/shop/Pricing.java) computes the total, with a
tenth off ten items or more, and hands a quote back for another quantity, changed in place. `POST /quotes/text`
answers the same total as text.

## Layout

```
src/main/java/     the route, the kernel, the quote and the event record
src/stubs/java/    stand-ins for the Spring classes the route compiles against (KafkaTemplate, the web annotations):
                   on the class path, never in the build that is checked, so the template stays a framework type
src/test/java/     plain tests, run by Tests.main: the route against a template that records what it is sent
```

The tests go through the route alone: it is the only API whose signature every version of the examples keeps (the
refactor changes `Quote`'s constructor).

## Verify it

From the repository's root, with `jvmcontract` on the `PATH`:

```bash
cd examples/apps/shop
javac -parameters -g -d build/stubs $(find src/stubs/java -name '*.java')
javac -parameters -g -cp build/stubs -d build/main $(find src/main/java -name '*.java')
javac -parameters -g -cp build/main:build/stubs -d build/test $(find src/test/java -name '*.java')
java -ea -cp build/main:build/test:build/stubs shop.Tests
jvmcontract compare OLD/build/main build/main --cache build/proof-cache   # an earlier build, compared with this one
```

[`build.py`](../../tools/build.py) does the same for an example (`TOOL_APPS["shop"]`): it compiles the unpatched and
the patched copies, runs the tests, and runs `jvmcontract compare` between them twice under one fresh proof cache, as
the example's B9 check.
