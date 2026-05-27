"""
数据导出服务模块

支持将管理后台数据导出为 CSV 格式，便于运营分析和报表生成。
"""

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
    """
    将数据列表导出为 CSV 格式

    @param data: 数据列表，每个元素为一行记录（字典）
    @param columns: 指定导出的列名，None 则使用所有键
    @param filename_prefix: 文件名前缀
    @return: (csv_content, filename) CSV 内容和文件名
    """
    if not data:
        return "", f"{filename_prefix}_empty.csv"

    # 确定列名
    if columns is None:
        columns = list(data[0].keys())

    # 写入 CSV
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(data)

    # 生成文件名（含时间戳）
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"{filename_prefix}_{timestamp}.csv"

    return output.getvalue(), filename


def export_users_csv(db) -> tuple[str, str]:
    """
    导出用户数据为 CSV

    @param db: 数据库实例
    @return: (csv_content, filename)
    """
    users = db.fetchall(
        "SELECT id, username, nickname, role, points, checkin_count, "
        "quiz_correct, quiz_total, status, created_at "
        "FROM users ORDER BY created_at DESC"
    )

    # 格式化时间戳
    for user in users:
        if user.get("created_at"):
            user["created_at"] = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(user["created_at"])
            )

    return export_to_csv(users, filename_prefix="ecosort_users")


def export_checkins_csv(db) -> tuple[str, str]:
    """
    导出打卡数据为 CSV

    @param db: 数据库实例
    @return: (csv_content, filename)
    """
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
    """
    导出答题记录为 CSV

    @param db: 数据库实例
    @return: (csv_content, filename)
    """
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
