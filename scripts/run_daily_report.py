from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from stock_reports.core.config import load_app_config
from stock_reports.daily_report.scheduler import start_weekday_schedule
from stock_reports.daily_report.service import DailyReportService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the stock daily report job.")
    parser.add_argument(
        "--config",
        default=str(ROOT_DIR / "config" / "daily_report.example.yaml"),
        help="Path to daily report config yaml.",
    )
    parser.add_argument("--once", action="store_true", help="Run the report job once.")
    parser.add_argument("--schedule", action="store_true", help="Run weekday scheduler.")
    parser.add_argument("--send", action="store_true", help="Send to Discord webhook.")
    parser.add_argument("--dry-run", action="store_true", help="Print report without sending.")
    parser.add_argument("--sample-data", action="store_true", help="Use built-in sample data.")
    parser.add_argument(
        "--template",
        choices=("markdown", "card_news", "research_update"),
        default="markdown",
        help="Output template to render.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(ROOT_DIR / "output"),
        help="Directory for generated card news PNG files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_app_config(Path(args.config))
    service = DailyReportService(config)
    output_dir = Path(args.output_dir)

    should_send = args.send and not args.dry_run

    if args.schedule:
        start_weekday_schedule(
            job=lambda: service.run_once(
                send=should_send,
                template=args.template,
                output_dir=output_dir,
            ),
            run_at=config.report.schedule_time,
        )
        return

    if args.once or not args.schedule:
        if args.template == "research_update":
            message = service.run_research_update(send=should_send)
            if message and (args.dry_run or not should_send):
                print(message)
            return
        report_text = service.run_once(
            send=should_send,
            use_sample_data=args.sample_data,
            fallback_to_sample=args.dry_run,
            template=args.template,
            output_dir=output_dir,
        )
        if args.dry_run or not should_send:
            print(report_text)


if __name__ == "__main__":
    main()
