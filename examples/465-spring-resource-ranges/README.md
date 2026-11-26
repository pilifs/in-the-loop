# A stale range validator returns the current resource in full

Four resource routes agreed on the status, Content-Range and body for stale, matching, weak and date validators.

| History | Observation |
|---|---|
| Intent | With a stale strong ETag every parent route returned 206 and bcd. Every merged route returned 200 and abcdef with no Content-Range. |
| Control | With no validator or with the matching strong ETag, every route returned 206, bytes 1-3/6 and bcd on both revisions. |
| Challenge | A malformed range with a stale tag and a valid range with a weak tag both yielded the entire resource on all four merged routes. |
| Date validator | With each route's emitted Last-Modified the merge served bcd. Moving that date forward one second produced the full body on all four routes. The parent served bcd for both dates. |

The same six-byte file, fixed modification time and ETag reach an MVC static handler, a ResponseEntity controller return-value processor, a functional MVC route and a WebFlux resource handler. Each response body is read after handling.

With the prepared Spring cache, run `python3 examples/tools/build.py 465` to repeat all histories on both revisions. [Predictions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime lock](runtime.json) · [Observed returns](observations.json) · [Spring PR #37218](https://github.com/spring-projects/spring-framework/pull/37218)
