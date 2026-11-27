# Generated-brief quality: what the controls show, and what to change

**For the domain agent.** This brief is an internal change to this repository: no setup phase, and no pull requests to verify.

- **Your task:** make the four changes under *Suggested lines for the brief-generation template* below, in `llm-dlc/loops/brief-generation-template.md` and in whatever renders or tests it. Then carry out the part of *How to check the change worked* that is yours.
- **The companion:** `~/code/scripts/analysis/architecture.md`, the working architecture of this repository. It covers who owns which concern and where to edit it, which record answers which question, the capabilities and their migration decisions, and how a run's results feed the next plan. Read it before you start, and follow its *How execution changes the next plan* (capture, reconcile, plan, land, observe) for this change.
- **Where the evidence comes from:** the user compared six generated briefs against rationale files the user wrote and keeps private. Those files, and the comparisons made from them, are held out as controls for future generated briefs. Don't look for them or ask for them. The counts below are all you need.

## The headline

Across 155 controlled cases (L, N, O, P, Q, R), the brief author (Codex Astra at ultra effort) **misread none and missed none.** It was usually sharper per case than the user's rationale:

| Batch | Match | Sharper | Different angle | Missed |
|---|---:|---:|---:|---:|
| L01–L20 | 6 | 11 | 3 | 0 |
| N01–N05 | 0 | 4 | 1 | 0 |
| O01–O20 | 2 | 14 | 4 | 0 |
| P01–P30 | 5 | 22 | 3 | 0 |
| Q01–Q30 | 6 | 20 | 4 | 0 |
| R01–R50 | 19 | 28 | 3 | 0 |

**Batch size made no difference:** quality and generation time were flat up to 50 PRs. The batch-size limit lies downstream, in setup and verification.

## What it gets wrong, consistently

1. **It drops the one-variable second observation.** The user's rationales often pair the main observation with a second one that changes a single variable: a reversed order, the other direction, a mixed argument. The author keeps the main one and drops or blurs the second:
   - O: 9 of 20 dropped;
   - P: 6 kept, 18 partly, 6 dropped, with 4 of 6 order variations dropped;
   - Q: 12 kept, 16 partly, 2 dropped, with all 3 explicit reversals dropped;
   - R: 15 kept, 28 partly, 7 dropped, with 6 of 12 order variations dropped.

   The same pattern shows in L (L06, L07, L12, L18) and N (N01's mixed arguments, N03's backward history, N04's rotation). It doesn't vary with batch size, so it's a rubric or handoff gap, not overload. The verification agents won some of it back on their own (N03, N04), but not reliably.
2. **It weakens order oracles.** Three times (P16, Q03, R31) it accepted "either order", or a set-like check, where the behaviour defines an order.
3. **It picks heavier observations than needed.** It reaches for databases, JMS or child processes where a smaller public call would show the same thing (Q, and 3 cases in R). That costs setup time, which is now the bottleneck.
4. **It adds predictions of its own,** 18 that the merged code would still be wrong (across O, P, Q, R). That turned out to be a strength: several were real upstream defects. L's picocli and JGraphT bugs were brief-only predictions, and O's three Spring 7.0.10 defects were the three the comparison flagged. Keep this.

## Suggested lines for the brief-generation template

Word them to fit the template. They go into `llm-dlc/loops/brief-generation-template.md`, in the rules for each case.

1. **One single-variable second observation per case.** After the main observation, add a second that changes exactly one input (order, direction, an argument, a boundary) and says what each revision should do. Where the behaviour depends on order, the second observation is the reversal.
2. **Keep the order when the behaviour defines one.** Don't write "either order", or compare as sets, when the code under change produces an order. State that order and check it.
3. **Prefer the cheapest observation that shows the change.** Use a plain public call on the shipped API before a database, message broker, server or child process. Use the heavier one only when the change can't be seen without it, and say why.
4. **Keep the predictions of defects that remain.** Where the landed code looks still wrong, say so as a separate prediction with its own observation. (This keeps strength 4 explicit, so a rubric change doesn't train it away.)

## How to check the change worked

- **Yours:** a test that shows the four rules in the handoff a brief author actually receives. Test the rendered generation prompt, not only the template file.
- **The user's, after you land:** on the next generated list that has a rationale file, the comparison is repeated the same way. It counts second observations kept, order reversals kept, oracles weakened and heavier-than-needed observations. The aim is most second observations kept, every reversal kept, and no weakened oracles, while still missing and misreading nothing. Report what you changed so that this check can be made against it.
