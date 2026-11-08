# Two more edits of the joint example, for the cost report

The builds `lib/tests/preparation.rs` adds to the foundations loop's joint example
([`../foundations/`](../foundations/README.md), examples 190 and 191), so that its report has every case the
[acceptance contract](../../../../llm-dlc/loops/application-core-acceptance.md#measurement-deliberately-limited) asks for
(J4): a cold run, an exact rerun, an unrelated edit, a safe rewrite of a helper and a real defect (`offset`). Each
directory is overlaid on `../foundations/after/`, as that fixture's defects are: its files replace theirs, or are
added. Both are checked from the proof cache a cold run of `after` leaves, as a developer's next edit would be.

| Build | What it changes | What the run should show |
|---|---|---|
| `unrelated-edit` | adds `shop.Shipping`, a class no route or kernel method reaches | every proof an exact hit: no claim's closure has changed |
| `helper-rewrite` | rewrites `Pricing.discount` again, the tenth taken first (`long tenth = gross / 10; return quantity >= 10 ? tenth : 0;`) | `discount` proved again on its own; `total` proved again with that new proof as one function in both versions (helper evidence, not an exact hit); `withQuantity` an exact hit; the route proved again, since its proof reads the helper's body |

Both keep `after`'s behaviour: `Shipping` is called by nothing, and the rewritten `discount` gives `after`'s result
on every input (a division by the constant 10 can't throw, so computing it first changes nothing).
