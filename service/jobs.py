from __future__ import annotations

import sys
import traceback
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import generate_weekly_outputs as weekly_outputs  # noqa: E402
import generate_weekly_report as excel_report  # noqa: E402

from service import dingtalk_docs, dingtalk_table


def load_configs() -> dict[str, dict[str, Any]]:
    return excel_report.load_configs()


def build_success_feedback(result: weekly_outputs.WeeklyOutputResult) -> str:
    return f"生成记录 {result.record_count} 条，缺失字段 {result.missing_field_count} 处，缺图 {result.image_issue_count} 条。"


def run_schedule_job(record_id: str) -> dict[str, Any]:
    configs = load_configs()
    try:
        dingtalk_table.mark_running(configs, record_id)
        schedule = dingtalk_table.fetch_schedule_row(configs, record_id)
        business = excel_report.parse_business(schedule.business, configs["report_rules"])
        stem = weekly_outputs.format_schedule_report_stem(schedule.business, schedule.year, schedule.week, schedule.end)
        result = weekly_outputs.generate_weekly_outputs(
            start=schedule.start,
            end=schedule.end,
            business=business,
            output_mode="all",
            stem=stem,
            overwrite=True,
            configs=configs,
        )
        docs_config = dingtalk_docs.load_docs_config()
        report_url = dingtalk_docs.upload_report_directory(docs_config, schedule.business, schedule.year, stem, result.output_paths)
        status_name = "生成异常" if result.data_quality_warnings else "已生成"
        feedback = build_success_feedback(result)
        dingtalk_table.mark_success(configs, record_id, stem, report_url, feedback, status_name)
        return {
            "ok": True,
            "recordId": record_id,
            "business": schedule.business,
            "startDate": schedule.start.isoformat(),
            "endDate": schedule.end.isoformat(),
            "stem": stem,
            "reportDir": str(result.report_dir),
            "outputFiles": [str(path) for path in result.output_paths],
            "reportUrl": report_url,
            "recordCount": result.record_count,
            "status": status_name,
            "feedback": feedback,
        }
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        try:
            dingtalk_table.mark_failed(configs, record_id, message)
        except Exception:
            message = message + "\n\n回写失败状态也失败：\n" + traceback.format_exc()
        raise RuntimeError(message) from exc
