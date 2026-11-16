# The watcher's summary

What the watcher of a `/prove-java-change` run prints at each interval (every 30 minutes unless
`watch.py interval` says otherwise), filled in by [`tools/watch.py`](tools/watch.py)'s `summary`. Everything below
the marker is the template; a `{name}` is replaced, and the rest is printed as it is. What changed since the last
summary comes first, so a reader who looks only at the top still sees what moved.

| Placeholder | What goes there |
|---|---|
| `{time}`, `{elapsed}`, `{since}` | The time (UTC), how long the loop has run, and how long ago the last summary was |
| `{changed}` | One line per change since the last summary: an example that changed state, a claim that got its answer, new commits, jobs queued or in |
| `{loop}` | The cycle, the example it is on and that example's cycle, how long the cycle has run, the session's tool calls so far and when it last wrote anything |
| `{examples}` | How many are done, which wait on a proof (with their jobs still out), which have not started |
| `{item}`, `{example}` | The example under way: its state by its own folder, its claims by answer, its jobs not in yet |
| `{jobs}` | The verification queue: running, queued, finished and not collected, collected |
| `{attention}` | What may need the watcher or the user: a question of the loop's, a silent session, a failed job, a queued merge, the loop's end |

<!-- template -->
### {time} UTC · {elapsed} into the run · {since}

**Changed**
{changed}

**Loop:** {loop}
**Examples:** {examples}
**Example {item}:** {example}
**Verification jobs:** {jobs}

**Needs attention**
{attention}
