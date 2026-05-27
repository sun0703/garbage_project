"""数据导出，CSV格式"""

import csv
import io
import logging
import time
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


def export_to_csv(
    data: List[Dict],
    columns: Optional[List[str]] = None,
    filename_prefix: str = "ecosort_export",
) -> tuple[str, str]:
    """通用CSV导出，返回(内容, 文件名)"""
    if not data:
        return "", f"{filename_prefix}_empty.csv"

    if columns is None:
        columns = list(data[0].keys())

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(data)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"{filename_prefix}_{timestamp}.csv"

    return output.getvalue(), filename


def export_users_csv(db) -> tuple[str, str]:
    """导出用户表"""
    users = db.fetchall(
        "SELECT id, username, nickname, role, points, checkin_count, "
        "quiz_correct, quiz_total, status, created_at "
        "FROM users ORDER BY created_at DESC"
    )

    for user in users:
        if user.get("created_at"):
            user["created_at"] = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(user["created_at"])
            )

    return export_to_csv(users, filename_prefix="ecosort_users")


def export_checkins_csv(db) -> tuple[str, str]:
    """导出打卡记录"""
    checkins = db.fetchall(
        "SELECT c.id, u.username, c.point_id, c.lat, c.lng, "
        "c.category, c.points_earned, c.created_at "
        "FROM checkins c LEFT JOIN users u ON c.user_id = u.id "
        "ORDER BY c.created_at DESC LIMIT 10000"
    )

    for c in checkins:
        if c.get("created_at"):
            c["created_at"] = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(c["created_at"])
            )

    return export_to_csv(checkins, filename_prefix="ecosort_checkins")


def export_quiz_records_csv(db) -> tuple[str, str]:
    """导出答题记录"""
    records = db.fetchall(
        "SELECT qr.id, u.username, qr.question_id, qr.selected, "
        "qr.is_correct, qr.points_earned, qr.created_at "
        "FROM quiz_records qr LEFT JOIN users u ON qr.user_id = u.id "
        "ORDER BY qr.created_at DESC LIMIT 10000"
    )

    for r in records:
        if r.get("created_at"):
            r["created_at"] = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(r["created_at"])
            )

    return export_to_csv(records, filename_prefix="ecosort_quiz_records")
