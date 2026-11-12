"""Run the drift check once or on an interval."""

from __future__ import annotations

import argparse
import json
import time

from nexvia_fraud.config import get_settings
from nexvia_fraud.db.engine import make_engine, make_session_factory
from nexvia_fraud.db.repo import init_db
from nexvia_fraud.drift.job import run_drift_check


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Run the Evidently drift check")
    parser.add_argument("--once", action="store_true", help="run one check and exit")
    parser.add_argument("--interval", type=int, default=settings.drift_interval_seconds)
    args = parser.parse_args()

    engine = make_engine(settings.database_url)
    init_db(engine)
    session_factory = make_session_factory(engine)

    while True:
        with session_factory() as session:
            result = run_drift_check(
                session,
                settings.drift_reference_path,
                settings.drift_share_threshold,
                settings.drift_min_rows,
            )
        print(json.dumps(result, default=str), flush=True)

        if args.once:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
