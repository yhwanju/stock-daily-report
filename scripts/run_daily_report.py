from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from stock_reports.core.config import load_app_config
from stock_reports.daily_report.scheduler import start_weekday_schedule
from stock_reports.daily_report.service import DailyReportService


KST = ZoneInfo("Asia/Seoul")
SCHEDULE_GUARD_START_MINUTE = 7 * 60 + 40
SCHEDULE_GUARD_END_MINUTE = 8 * 60 + 10
SCHEDULE_GUARD_BLOCK_MESSAGE = (
    "[stock-manager] schedule 실행 시간이 허용 범위가 아니므로 리포트 발송을 생략합니다."
)


@dataclass(frozen=True)
class ScheduleGuardContext:
    event_name: str
    github_ref: str
    utc_now: datetime
    kst_now: datetime
    is_schedule_event: bool
    is_allowed_time: bool

    @property
    def passed(self) -> bool:
        return not self.is_schedule_event or self.is_allowed_time


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


def _build_schedule_guard_context(now_utc: datetime | None = None) -> ScheduleGuardContext:
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    elif now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    else:
        now_utc = now_utc.astimezone(timezone.utc)

    kst_now = now_utc.astimezone(KST)
    kst_minute = kst_now.hour * 60 + kst_now.minute
    is_allowed_time = SCHEDULE_GUARD_START_MINUTE <= kst_minute <= SCHEDULE_GUARD_END_MINUTE
    event_name = os.getenv("GITHUB_EVENT_NAME", "")

    return ScheduleGuardContext(
        event_name=event_name,
        github_ref=os.getenv("GITHUB_REF", ""),
        utc_now=now_utc,
        kst_now=kst_now,
        is_schedule_event=event_name == "schedule",
        is_allowed_time=is_allowed_time,
    )


def _format_log_time(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S %Z")


def _log_schedule_guard(context: ScheduleGuardContext) -> None:
    print(f"[stock-manager] GitHub event name: {context.event_name or '(unset)'}")
    print(f"[stock-manager] GitHub ref: {context.github_ref or '(unset)'}")
    print(f"[stock-manager] 현재 UTC 시간: {_format_log_time(context.utc_now)}")
    print(f"[stock-manager] 현재 KST 시간: {_format_log_time(context.kst_now)}")
    print(f"[stock-manager] schedule 이벤트 여부: {context.is_schedule_event}")
    status = "통과" if context.passed else "차단"
    print(f"[stock-manager] 시간 가드 통과/차단 여부: {status}")


def main() -> None:
    args = parse_args()
    config = load_app_config(Path(args.config))
    service = DailyReportService(config)
    output_dir = Path(args.output_dir)

    should_send = args.send and not args.dry_run
    schedule_guard = _build_schedule_guard_context()
    _log_schedule_guard(schedule_guard)
    if should_send and not schedule_guard.passed:
        print(SCHEDULE_GUARD_BLOCK_MESSAGE)
        return

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
