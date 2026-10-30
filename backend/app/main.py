from __future__ import annotations

import csv
import io
import json
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from uuid import uuid4

import pandas as pd
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from . import store
from .engine import clean, quality, validate_rules


@asynccontextmanager
async def lifespan(app):
    store.initialize()
    yield


app = FastAPI(title="通用数据清洗平台", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_methods=["*"], allow_headers=["*"])


class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(max_length=100)
    type: Literal["trim", "fill", "dedupe", "replace", "case", "convert", "validate"]
    enabled: bool = True
    fields: list[str] = Field(default_factory=list, max_length=200)
    options: dict[str, str] = Field(default_factory=dict)


class RunRequest(BaseModel):
    rules: list[Rule] = Field(max_length=30)
    name: str = Field(default="数据清洗任务", min_length=1, max_length=100)


class TemplateRequest(RunRequest):
    description: str = Field(default="", max_length=500)


def dataset_or_404(identity, allow_deleted=False):
    record = store.query("SELECT * FROM datasets WHERE id=?", (identity,), one=True)
    if not record:
        raise HTTPException(404, "数据集不存在")
    if record["deleted_at"] and not allow_deleted:
        raise HTTPException(409, "数据集已移入回收站，请恢复后再清洗")
    return record, store.read_json("datasets", identity)


def serialize_task(record):
    return {**{k: v for k, v in record.items() if not k.endswith("_json")},
            "rules": json.loads(record["rules_json"]), "summary": json.loads(record["summary_json"] or "null")}


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/datasets")
def datasets(deleted: bool = False):
    condition = "IS NOT NULL" if deleted else "IS NULL"
    return [{**{k: v for k, v in d.items() if k != "columns_json"}, "columns": json.loads(d["columns_json"])} for d in store.query(f"SELECT * FROM datasets WHERE deleted_at {condition} ORDER BY created_at DESC, rowid DESC")]


@app.delete("/api/datasets/{identity}", status_code=204)
def delete_dataset(identity: str):
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        record = db.execute("SELECT id FROM datasets WHERE id=? AND deleted_at IS NULL", (identity,)).fetchone()
        if not record:
            raise HTTPException(404, "数据集不存在或已移入回收站")
        active = db.execute("SELECT id FROM tasks WHERE dataset_id=? AND status IN ('pending','running') LIMIT 1", (identity,)).fetchone()
        if active:
            raise HTTPException(409, "此数据集有正在执行的任务，请完成后再删除")
        db.execute("UPDATE datasets SET deleted_at=? WHERE id=?", (store.now(), identity))


@app.post("/api/datasets/{identity}/restore", status_code=204)
def restore_dataset(identity: str):
    with store.connect() as db:
        cursor = db.execute("UPDATE datasets SET deleted_at=NULL WHERE id=? AND deleted_at IS NOT NULL", (identity,))
        if not cursor.rowcount:
            raise HTTPException(404, "回收站中没有此数据集")


@app.get("/api/datasets/{identity}")
def dataset(identity: str, page: int = 1, page_size: int = 50, search: str = ""):
    if page < 1 or page_size < 1 or page_size > 200:
        raise HTTPException(400, "分页参数无效")
    record, data = dataset_or_404(identity, allow_deleted=True)
    rows = data["rows"]
    if search:
        rows = [r for r in rows if any(search.casefold() in str(r.get(c, "")).casefold() for c in data["columns"])]
    return {**{k: v for k, v in record.items() if k != "columns_json"}, "columns": data["columns"], "rows": rows[(page - 1) * page_size:page * page_size],
            "total": len(rows), "quality": quality(data["rows"], data["columns"])}


def parse_upload(content, filename):
    suffix = Path(filename).suffix.lower()
    try:
        if suffix == ".csv":
            for encoding in ("utf-8-sig", "gb18030"):
                try:
                    decoded = content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError("CSV 编码无法识别，请另存为 UTF-8")
            reader = csv.reader(io.StringIO(decoded))
            header = next(reader, [])
            records = []
            for line_number, record in enumerate(reader, 2):
                if not record or all(not v.strip() for v in record):
                    continue
                if len(record) != len(header):
                    raise ValueError(f"第 {line_number} 行列数与表头不一致")
                records.append(record)
                if len(records) > 100_000:
                    raise ValueError("第一版每个文件最多支持 100,000 行")
        else:
            frame = pd.read_excel(io.BytesIO(content), dtype=str, keep_default_na=False, header=None, nrows=100_002)
            header = [] if frame.empty else frame.iloc[0].tolist()
            records = frame.iloc[1:].fillna("").values.tolist()
        columns = [str(c).strip() for c in header]
        if not columns or len(columns) > 200 or any(not c for c in columns):
            raise ValueError("表头不能为空，且最多支持 200 列")
        if len(set(columns)) != len(columns):
            raise ValueError("表头存在重复字段，请先修改字段名称")
        if "_row_id" in columns:
            raise ValueError("_row_id 为系统保留字段，请修改字段名称")
        if not records:
            raise ValueError("文件中没有数据记录")
        if len(records) > 100_000:
            raise ValueError("第一版每个文件最多支持 100,000 行")
        rows = [{"_row_id": i + 1, **dict(zip(columns, map(str, row)))} for i, row in enumerate(records)]
        return store.add_dataset(filename, columns, rows)
    except (ValueError, pd.errors.ParserError) as error:
        raise HTTPException(400, str(error)) from error
    except Exception as error:
        raise HTTPException(400, "文件无法读取，请确认文件格式和内容完整") from error


@app.post("/api/datasets", status_code=201)
async def upload(file: UploadFile = File(...)):
    filename = Path((file.filename or "").replace("\\", "/")).name
    if Path(filename).suffix.lower() not in (".csv", ".xlsx"):
        raise HTTPException(400, "仅支持 CSV 和 XLSX 文件")
    content = await file.read(20 * 1024 * 1024 + 1)
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(400, "文件大小不能超过 20 MB")
    identity = await run_in_threadpool(parse_upload, content, filename)
    return {"id": identity}


def prepared(identity, request):
    record, data = dataset_or_404(identity)
    rules = [r.model_dump() for r in request.rules]
    try:
        validate_rules(rules, data["columns"])
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    if not any(r["enabled"] for r in rules):
        raise HTTPException(400, "请至少启用一条清洗规则")
    return record, data, rules


@app.post("/api/datasets/{identity}/preview")
def preview(identity: str, request: RunRequest):
    _, data, rules = prepared(identity, request)
    result = clean(data["rows"], data["columns"], rules)
    preview_id = store.save_preview(result)
    return {**result, "preview_id": preview_id, "rows": result["rows"][:200], "changes": result["changes"][:500], "issues": result["issues"][:500],
            "total_changes": len(result["changes"]), "total_issues": len(result["issues"])}


def paginated_result(data, page, page_size, view, search):
    if page < 1 or page_size < 1 or page_size > 200:
        raise HTTPException(400, "分页参数无效")
    items = data[view]
    if search:
        items = [r for r in items if any(search.casefold() in str(v).casefold() for v in r.values())]
    return {"items": items[(page - 1) * page_size:page * page_size], "total": len(items),
            "columns": data["columns"], "before": data["before"], "after": data["after"]}


@app.get("/api/previews/{identity}")
def preview_result(identity: str, page: int = 1, page_size: int = 50,
                   view: Literal["rows", "changes", "issues"] = "rows", search: str = ""):
    try:
        result = store.read_preview(identity)
    except FileNotFoundError as error:
        raise HTTPException(404, "预览不存在或已过期，请重新点击预览效果") from error
    return paginated_result(result, page, page_size, view, search)


def execute_task(identity, data, rules):
    try:
        store.query("UPDATE tasks SET status='running' WHERE id=?", (identity,))
        result = clean(data["rows"], data["columns"], rules)
        store.write_json("results", identity, result)
        summary = {"before": result["before"], "after": result["after"], "changes": len(result["changes"]), "issues": len(result["issues"]), "rule_stats": result["rule_stats"]}
        store.query("UPDATE tasks SET status='success', finished_at=?, summary_json=? WHERE id=?", (store.now(), json.dumps(summary, ensure_ascii=False), identity))
    except Exception:
        store.query("UPDATE tasks SET status='failed', finished_at=?, error=? WHERE id=?", (store.now(), "执行失败，请检查数据和规则后重试", identity))
        import logging
        logging.exception("Cleaning task %s failed", identity)


@app.post("/api/datasets/{identity}/tasks", status_code=202)
def run(identity: str, request: RunRequest, background: BackgroundTasks):
    record, data, rules = prepared(identity, request)
    task_id = uuid4().hex
    # Serialize task submission with deletion so a concurrent request cannot start
    # new work against a dataset that has just moved to the recycle bin.
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        active = db.execute("SELECT id FROM datasets WHERE id=? AND deleted_at IS NULL", (identity,)).fetchone()
        if not active:
            raise HTTPException(409, "数据集已移入回收站，请恢复后再清洗")
        db.execute("INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?)", (task_id, request.name, identity, record["name"], "pending", store.now(), None, json.dumps(rules, ensure_ascii=False), None, None))
    background.add_task(execute_task, task_id, data, rules)
    return {"id": task_id}


@app.get("/api/tasks")
def tasks():
    return [serialize_task(t) for t in store.query("SELECT * FROM tasks ORDER BY created_at DESC, rowid DESC")]


@app.get("/api/tasks/{identity}")
def task(identity: str):
    record = store.query("SELECT * FROM tasks WHERE id=?", (identity,), one=True)
    if not record:
        raise HTTPException(404, "任务不存在")
    return serialize_task(record)


@app.get("/api/tasks/{identity}/result")
def task_result(identity: str, page: int = 1, page_size: int = 50, view: Literal["rows", "changes", "issues"] = "rows", search: str = ""):
    record = task(identity)
    if record["status"] != "success":
        raise HTTPException(409, "任务尚未成功完成")
    data = store.read_json("results", identity)
    return paginated_result(data, page, page_size, view, search)


def csv_stream(rows, columns):
    yield "\ufeff"
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(columns)
    yield buffer.getvalue()
    for row in rows:
        buffer.seek(0)
        buffer.truncate(0)
        # Keep spreadsheet applications from executing text as formulas on opening.
        values = [str(row.get(c, "")) for c in columns]
        writer.writerow(["'" + v if v.lstrip().startswith(("=", "+", "-", "@")) and not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", v.strip()) else v for v in values])
        yield buffer.getvalue()


@app.get("/api/tasks/{identity}/export")
def export(identity: str, kind: Literal["data", "changes", "issues", "report"] = "data", format: Literal["csv", "xlsx"] = "csv"):
    record = task(identity)
    if record["status"] != "success":
        raise HTTPException(409, "任务尚未成功完成")
    result = store.read_json("results", identity)
    if kind == "report":
        report = {"软件": "通用数据清洗平台 V1.0", "任务": record, "质量统计": {"清洗前": result["before"], "清洗后": result["after"]}, "规则统计": result["rule_stats"], "说明": "质量评分根据缺失单元格和整行重复记录计算，格式异常单独列示。"}
        return StreamingResponse(iter([json.dumps(report, ensure_ascii=False, indent=2)]), media_type="application/json", headers={"Content-Disposition": 'attachment; filename="quality-report.json"'})
    key = {"data": "rows", "changes": "changes", "issues": "issues"}[kind]
    columns = result["columns"] if kind == "data" else (["row_id", "field", "before", "after", "rule", "action"] if kind == "changes" else ["row_id", "field", "value", "rule", "reason"])
    rows = result[key]
    if format == "xlsx":
        buffer = io.BytesIO()
        frame = pd.DataFrame(rows, columns=columns)
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            frame.to_excel(writer, index=False)
            # Explicit string cells preserve literal formulas and leading zeroes without changing values.
            for cells in writer.sheets["Sheet1"].iter_rows():
                for cell in cells:
                    if isinstance(cell.value, str):
                        cell.data_type = "s"
        buffer.seek(0)
        return StreamingResponse(buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="{kind}.xlsx"'})
    return StreamingResponse(csv_stream(rows, columns), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{kind}.csv"'})


@app.get("/api/templates")
def templates():
    return [{**{k: v for k, v in t.items() if k != "rules_json"}, "rules": json.loads(t["rules_json"])} for t in store.query("SELECT * FROM templates ORDER BY created_at DESC, rowid DESC")]


@app.post("/api/templates", status_code=201)
def save_template(request: TemplateRequest):
    identity = uuid4().hex
    store.query("INSERT INTO templates VALUES (?,?,?,?,?)", (identity, request.name, request.description, json.dumps([r.model_dump() for r in request.rules], ensure_ascii=False), store.now()))
    return {"id": identity}


@app.delete("/api/templates/{identity}", status_code=204)
def delete_template(identity: str):
    store.query("DELETE FROM templates WHERE id=?", (identity,))


# The production build and API share one origin and one launch command.
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/favicon.svg", include_in_schema=False)
    def favicon():
        return FileResponse(DIST / "favicon.svg", media_type="image/svg+xml")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(DIST / "index.html")
