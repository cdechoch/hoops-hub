"""Pick which jobs to run for this tick. A GitHub Actions cron fires this every 5 minutes.

live    every tick: scores, news, trends, injuries
hourly  at the top of each hour: HoopsMatic contracts and cap sheets, league stats (leaders, rookies, teams)
daily   09:00 UTC: Spotrac and HoopsHype fallbacks if HoopsMatic is unreachable
weekly  Monday 09:00 UTC: draft board
FORCE=all runs everything. JOBS=live,daily picks jobs by hand.
"""
import os
import sys
import traceback

import common as c
import scores, news, trends, injuries, league, salaries, cap, draft, hoopsmatic


def due():
    forced = os.environ.get("FORCE", "").lower() == "all"
    manual = [j for j in os.environ.get("JOBS", "").split(",") if j]
    n = c.now()
    top = n.minute < 5
    jobs = {"live"}
    if forced or "hourly" in manual or top:
        jobs.add("hourly")
    if forced or "daily" in manual or (top and n.hour == 9):
        jobs.add("daily")
    if forced or "weekly" in manual or (top and n.hour == 9 and n.weekday() == 0):
        jobs.add("weekly")
    jobs.update(manual)
    return jobs


def step(fn):
    try:
        fn()
    except Exception:
        traceback.print_exc()


def main():
    jobs = due()
    print("jobs:", sorted(jobs))
    if "live" in jobs:
        step(scores.run)
        step(news.run)
        step(trends.run)
        step(injuries.run)
    hm_ok = False
    if "hourly" in jobs or "daily" in jobs:
        try:
            hm_ok = hoopsmatic.run()
        except Exception:
            traceback.print_exc()
    if "daily" in jobs and not hm_ok:
        step(salaries.run)  # fallbacks when HoopsMatic is unreachable
        step(cap.run)
    if "hourly" in jobs:
        step(league.run)
    if "weekly" in jobs:
        step(draft.run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
