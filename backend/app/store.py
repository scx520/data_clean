"""Local metadata and immutable source/result files."""
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(os.environ.get("DATA_CLEAN_HOME", Path(__file__).resolve().parents[2] / ".data"))


def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def connect():
    connection = sqlite3.connect(ROOT / "platform.sqlite3", timeout=30)
    connection.row_factory = sqlite3.Row
    return connection


def query(sql, args=(), one=False):
    with connect() as db:
        cursor = db.execute(sql, args)
        if cursor.description:
            result = [dict(r) for r in cursor.fetchall()]
            return (result[0] if result else None) if one else result


def write_json(folder, identity, data):
    target = ROOT / folder / f"{identity}.json"
    temporary = target.with_suffix(f".{uuid4().hex}.tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    temporary.replace(target)


def read_json(folder, identity):
    return json.loads((ROOT / folder / f"{identity}.json").read_text(encoding="utf-8"))


def add_dataset(name, columns, rows, source="import"):
    identity = uuid4().hex
    write_json("datasets", identity, {"columns": columns, "rows": rows})
    query("INSERT INTO datasets VALUES (?,?,?,?,?,?,?)", (identity, name, len(rows), len(columns), now(), source, json.dumps(columns, ensure_ascii=False)))
    return identity


def initialize():
    for folder in ("datasets", "results"):
        (ROOT / folder).mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS datasets (
            id TEXT PRIMARY KEY, name TEXT, row_count INTEGER, column_count INTEGER,
            created_at TEXT, source TEXT, columns_json TEXT);
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY, name TEXT, dataset_id TEXT, dataset_name TEXT,
            status TEXT, created_at TEXT, finished_at TEXT, rules_json TEXT,
            summary_json TEXT, error TEXT);
        CREATE TABLE IF NOT EXISTS templates (
            id TEXT PRIMARY KEY, name TEXT, description TEXT, rules_json TEXT, created_at TEXT);
        """)
        db.execute("UPDATE tasks SET status='failed', error='服务重启中断了任务，请重新执行' WHERE status IN ('pending','running')")
    # Only seed on the first launch. Demo data is always labelled as synthetic.
    marker = ROOT / ".initialized"
    if not marker.exists():
        columns = ["客户编号", "客户姓名", "手机号", "邮箱", "所属城市", "注册日期", "消费金额", "客户等级"]
        surnames = ["陈", "林", "张", "王", "李", "赵", "刘", "徐"]
        names = ["晓雨", "明远", "子涵", "思源", "嘉宁", "一诺"]
        cities = ["济南", "青岛", "烟台", "潍坊", "淄博", "泰安"]
        rows = []
        for i in range(48):
            values = [f"C{i + 1:04d}", f" {surnames[i % 8]}{names[i % 6]} " if i % 7 == 0 else f"{surnames[i % 8]}{names[i % 6]}",
                      "138-0013-8000" if i % 17 == 0 else f"138{i + 13008000:08d}",
                      "" if i % 9 == 0 else f"USER{i + 1:02d}@EXAMPLE.COM", "" if i % 8 == 0 else cities[i % 6],
                      f"2026/{i % 9 + 1:02d}/{i % 26 + 1:02d}", "待核实" if i % 19 == 0 else f"{(i + 1) * 128:,}.00", ["普通", "银卡", "金卡"][i % 3]]
            rows.append({"_row_id": i + 1, **dict(zip(columns, values))})
        for index in (2, 9, 16, 25):
            rows.append({**rows[index], "_row_id": len(rows) + 1})
        add_dataset("客户信息示例（模拟数据）.csv", columns, rows, "demo")
        marker.write_text(now(), encoding="utf-8")
