#!/usr/bin/env python3
"""Runs the same live-SSH collection as clicking "Collect Now" in the web
UI, but headless — for cron/scheduled runs so history keeps filling in
even when nobody has the browser open.

Example crontab (collect every 15 min during office hours, weekdays):
    */15 8-18 * * 1-5 cd /path/to/netmon_web && python3 cron_collect.py >> collect.log 2>&1
"""
import db
import logic

if __name__ == "__main__":
    db.init_db()
    for line in logic.run_live_collection():
        print(line)
