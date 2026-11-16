# The plan of a `/prove-java-change` run

What stage 2 of the skill writes (to `llm-dlc/loop-summaries/prove-change/plan.md`, not committed) and stage 3
turns into examples ([`runtime.md`](runtime.md#stage-2-evaluate-and-order-them-and-design-or-review-their-claims)).
Everything below the marker is the template: one "Change" section per change or example named, in the order they
are to be proved, the most accessible first. Stage 3 fills in nothing the plan leaves open, so a field that can't be
filled is a question, written under "Open questions", not a guess.

The same plan is written as data beside it, `plan.json`, as [`prove-plan.schema.json`](prove-plan.schema.json)
says: the designed claim files and tasks exactly as the setup writes them (`examples/tools/scaffold_example.py`),
and for every example the controls, the entry, the preparation, the validation commands and when its setup is done.
`python3 llm-dlc/tools/watch.py plan --check` checks it. An example whose claims are reused from an accepted review
needs only its order, its entry and its validation there.

<!-- template -->
# Plan

**Request:** the request, as the user gave it

**Machine:** whether it is enough for these changes, what limits it, and the budget (from `doctor.py`)

**Order:** the numbers, the most accessible first, with one line on why each sits where it does

## Change NNN: a short title

- **Review:** designed (stage 2 wrote the claims), reviewed (the example's claims read again, with remarks) or
  reused (unchanged since an accepted review)
- **Request:** this change's part of the request, as given
- **Source:** the pull request or commit on github.com
- **Revisions:** before and after, each as a full commit, and how each is prepared (published JARs, the commit's
  own build, or a source slice compiled against pinned JARs)
- **Subject:** the class and method the claims are about
- **Meant to change:** what the change is for
- **Must keep:** what it must leave as it was
- **Claims:** one entry per claim, each in full: the property, the revision it is about, its domain, its
  assumptions, its bounds, and the answer expected (established or refuted)
- **Preservation boundary:** what the change may alter, and what it must keep
- **Bounds:** the bounds that make the claims meaningful, and why each is enough
- **Controls:** inputs that must hold, inputs that must fail, and the constructed mutant that must fail the claim
- **Entry:** the method the proof enters, the adapter if the route can't enter it, how its inputs are built, and
  whether it is expected to go through the route, an adapter, or not until a named gap is closed
- **Environment:** every assumption about the environment (locale, JDK, configuration, the code around the entry)
- **Remarks:** for claims that exist, where one misstates the example's own pages (the setup corrects it as said
  here) or something is missing or too narrow (a suggestion, which is the user's)
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
