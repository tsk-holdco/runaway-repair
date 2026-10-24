"""A 70-line reproduction of a job queue that repairs itself to death.

Run it:  python runaway_repair.py

WHAT THIS IS. A deliberately small, dependency-free simulation of a failure mode that is easy to
build by accident and hard to see from inside: a reconciler that files repair work for failed jobs,
whose repair jobs fail, and are themselves swept and repaired. Nobody designs this loop. Every
individual step is locally correct.

WHAT THIS IS NOT. It is not a fix, and it does not pretend to be one. It reproduces the problem so
you can recognise it in your own queue. The mechanisms that bound it are described in the README.
"""
from __future__ import annotations

import itertools

_ids = itertools.count(1)


class Job:
    __slots__ = ("id", "kind", "parent", "state", "attempts")

    def __init__(self, kind, parent=None):
        self.id = next(_ids)
        self.kind = kind
        self.parent = parent
        self.state = "ready"
        self.attempts = 0

    def __repr__(self):
        p = "" if self.parent is None else " (repair of #%d)" % self.parent
        return "#%d %s%s" % (self.id, self.kind, p)


def run_job(job, flaky_until_tick, tick):
    """The work itself. It fails while the downstream dependency is unhealthy."""
    job.attempts += 1
    job.state = "failed" if tick < flaky_until_tick else "done"
    return job.state


def reconcile(queue, tick, flaky_until_tick, log):
    """The sweeper. Each rule below is defensible on its own.

    1. Run anything ready.
    2. A failed job needs repairing, so file a repair job for it.
    3. A repair job that has itself failed is a failed job, so rule 2 applies to it too.

    Rule 3 is the one that closes the loop, and it is not a bug anybody wrote deliberately -- it is
    rule 2 applied uniformly, which is exactly what makes it survive code review.
    """
    for job in list(queue):
        if job.state == "ready":
            run_job(job, flaky_until_tick, tick)

    for job in list(queue):
        if job.state == "failed" and not any(j.parent == job.id for j in queue):
            repair = Job("repair", parent=job.id)
            queue.append(repair)
            log.append("tick %2d: %s failed -> filed %s" % (tick, job, repair))


def main():
    # The dependency is down for the first 6 ticks. A real outage; nothing exotic.
    FLAKY_UNTIL = 6
    queue = [Job("deliver-invoice")]
    log = []

    for tick in range(1, 9):
        reconcile(queue, tick, FLAKY_UNTIL, log)

    for line in log:
        print(line)

    print("")
    print("after 8 ticks: %d jobs in the queue, from 1 original" % len(queue))
    print("depth of the repair chain: %d" % _depth(queue))
    print("")
    print("The dependency recovered at tick 6. The queue did not: by then it was busy repairing")
    print("its own repairs, and every one of those is a real row somebody has to explain.")
    print("")
    print("Three things bound this, and none of them is 'retry less':")
    print("  * a budget the whole lineage shares, so one sick dependency cannot spend the queue")
    print("  * a test for material progress, so a retry has to earn the next one")
    print("  * quarantine, so a job can leave circulation without being lost")
    print("")
    print("Worked through properly: https://opsbaseline.gumroad.com/l/cdnlw")


def _depth(queue):
    by_id = {j.id: j for j in queue}
    best = 0
    for j in queue:
        d, cur = 0, j
        while cur.parent is not None and cur.parent in by_id:
            d += 1
            cur = by_id[cur.parent]
        best = max(best, d)
    return best


if __name__ == "__main__":
    main()
