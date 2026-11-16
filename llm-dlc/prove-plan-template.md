# The plan of a `/prove-java-change` run

What stage 2 of the skill writes (to `llm-dlc/loop-summaries/prove-change/plan.md`, not committed) and stage 3
turns into examples ([`runtime.md`](runtime.md#stage-2-evaluate-the-changes-and-order-them)). Everything below the
marker is the template: one "Change" section per change, in the order they are to be proved, the most accessible
first. Stage 3 fills in nothing the plan leaves open, so a field that can't be filled is a question, written under
"Open questions", not a guess.

<!-- template -->
# Plan

**Request:** the request, as the user gave it

**Machine:** whether it is enough for these changes, what limits it, and the budget (from `doctor.py`)

**Order:** the numbers, the most accessible first, with one line on why each sits where it does

## Change NNN: a short title

- **Request:** this change's part of the request, as given
- **Source:** the pull request or commit on github.com
- **Revisions:** before and after, each as a full commit, and how each is prepared (published JARs, the commit's
  own build, or a source slice compiled against pinned JARs)
- **Subject:** the class and method the claims are about
- **Meant to change:** what the change is for
- **Must keep:** what it must leave as it was
- **Claims:** one entry per claim, each in full: the property, the revision it is about, its domain, its
  assumptions, its bounds, and the answer expected (established or refuted)
- **Replay:** the concrete inputs that show the change on a JVM, and what each revision gives for them
- **Closest past examples:** their numbers, and what they cost
- **Expected to be hard:** what the verifier may not model yet
- **Estimate:** hours and tokens, roughly
- **Accessibility:** why it sits where it does in the order

## Set aside

A change that can't be prepared (it is not on GitHub, a revision won't build, a claim can't be stated yet), with
its reason.

## Open questions

What only the user can answer, each with the change it holds up.
