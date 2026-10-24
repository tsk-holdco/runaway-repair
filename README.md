# Runaway repair: when a job queue repairs itself to death

A small, runnable reproduction of a failure mode that is easy to build by accident and genuinely
hard to see from inside the system that has it.

```
tick  1: #1 deliver-invoice failed -> filed #2 repair (repair of #1)
tick  2: #2 repair (repair of #1) failed -> filed #3 repair (repair of #2)
tick  3: #3 repair (repair of #2) failed -> filed #4 repair (repair of #3)
tick  4: #4 repair (repair of #3) failed -> filed #5 repair (repair of #4)
tick  5: #5 repair (repair of #4) failed -> filed #6 repair (repair of #5)

after 8 ticks: 6 jobs in the queue, from 1 original
depth of the repair chain: 5
```

```bash
python demo/runaway_repair.py
```

No dependencies, no install, ~70 lines.

## The shape of the bug

You have a reconciler. It sweeps failed rows and files repair work for them. That is a good idea
and most mature queues grow one.

Then:

1. A job fails because something downstream is unhealthy.
2. The reconciler sweeps it, classifies it, files a repair job.
3. The repair job runs while the dependency is still unhealthy, so it fails too.
4. **The repair job is now itself a failed row.** The reconciler sweeps it and files a repair job
   for the repair job.

Nobody writes step 4. Step 4 is step 2 applied uniformly, which is precisely why it survives review:
every rule in isolation is defensible, and the loop only exists in the composition.

The demo's dependency recovers at tick 6. The queue does not — by then it is busy repairing its own
repairs, and each of those is a real row that somebody eventually has to explain.

## Why the obvious fixes do not hold

**"Cap the attempts."** A per-job attempt counter never trips here. Each job in that chain has
attempted exactly once. The chain grows sideways, not deep, and the counter is measuring the wrong
object.

**"Add exponential backoff."** Backoff changes *when* the loop runs, not whether it terminates. A
slower runaway is still a runaway, and it is harder to notice.

**"Use a dead-letter queue."** Correct and insufficient. A DLQ catches a job that exhausted its
retries; it does not catch a job that keeps being *replaced by a new job* that has retries of its
own.

**"Detect duplicates."** Each repair job is genuinely distinct — different id, different parent,
different timestamp. They are not duplicates. They are a lineage.

## What actually bounds it

Three mechanisms, and the useful insight is that all three operate on the **lineage** — the original
job and everything filed on its behalf, treated as one object — rather than on individual rows:

- **A shared retry budget.** Spent by the lineage, not the row, so one unhealthy dependency cannot
  consume the whole queue's capacity no matter how many repair jobs it spawns.
- **A material-progress test.** A retry has to *earn* the next one by changing something
  observable. "It failed differently" is not progress; neither is "it got further before failing".
- **Quarantine.** A way for a job to leave circulation without being deleted, and a defined
  condition under which it may come back — which is not "a human noticed".

This repo demonstrates the problem and names the mechanisms. It does not implement them.

## The full treatment

The complete design — failure fingerprinting, the oscillation case (a job that succeeds, regresses
and is re-filed, which no attempt counter catches because every individual attempt looks fine), the
hold-versus-quarantine distinction, a breaker that stays tripped until there is new evidence,
telling a bug in your own system from a failure in the world, plus a dependency-free Python
reference implementation — is a paid guide:

**[Bounded Self-Repair for Job Queues](https://opsbaseline.gumroad.com/l/cdnlw) — $29**

Stated plainly because you should know what the link is before you click it: that is a commercial
product, this repo is not a teaser with the good part removed, and the demo above is complete and
useful on its own whether or not you ever buy anything. If it is not useful to you, the guide has a
30-day no-questions refund.

## Status

The demo is the whole of this repository today. Issues and corrections are welcome — particularly
if you have hit this in production and it took a different shape than the one modelled here.
