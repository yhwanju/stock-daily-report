from __future__ import annotations

import time
from collections.abc import Callable

import schedule


def start_weekday_schedule(job: Callable[[], object], run_at: str) -> None:
    schedule.every().monday.at(run_at).do(job)
    schedule.every().tuesday.at(run_at).do(job)
    schedule.every().wednesday.at(run_at).do(job)
    schedule.every().thursday.at(run_at).do(job)
    schedule.every().friday.at(run_at).do(job)

    while True:
        schedule.run_pending()
        time.sleep(30)
