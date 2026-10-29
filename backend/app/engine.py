"""Deterministic cleaning engine. Original row identifiers survive filtering."""
from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime
from typing import Any

import pandas as pd

RULE_NAMES = {
    "trim": "去除首尾空格", "fill": "填充缺失值", "dedupe": "去除重复记录",
    "replace": "文本替换", "case": "统一英文大小写", "convert": "转换字段格式",
    "validate": "标记异常数据",
}


def missing(value: Any) -> bool:
    return value is None or str(value).strip() == ""


def quality(rows: list[dict], columns: list[str]) -> dict:
    counts = Counter(tuple(str(row.get(c, "")) for c in columns) for row in rows)
    field_missing = {c: sum(missing(r.get(c)) for r in rows) for c in columns}
    cells = len(rows) * len(columns)
    missing_count = sum(field_missing.values())
    duplicate_count = sum(n - 1 for n in counts.values())
    score = round(max(0, 100 * (1 - (missing_count + duplicate_count * len(columns)) / cells)), 1) if cells else 100
    return {"rows": len(rows), "columns": len(columns), "missing_cells": missing_count,
            "duplicate_rows": duplicate_count, "score": score, "field_missing": field_missing}


def validate_rules(rules: list[dict], columns: list[str]) -> None:
    if len(rules) > 30:
        raise ValueError("每次最多配置 30 条规则")
    for rule in rules:
        if rule["type"] not in RULE_NAMES:
            raise ValueError("不支持的规则类型")
        if not rule.get("enabled", True):
            continue
        fields = rule.get("fields", [])
        if any(f not in columns for f in fields):
            raise ValueError("规则包含不存在的字段，请重新选择")
        kind, options = rule["type"], rule.get("options", {})
        if kind in ("fill", "replace", "case", "convert", "validate") and not fields:
            raise ValueError(f"请为「{RULE_NAMES[kind]}」选择字段")
        if kind == "fill" and missing(options.get("value")):
            raise ValueError("请填写缺失值的替代内容")
        if kind == "replace" and not options.get("search"):
            raise ValueError("待替换文本不能为空")
        if kind == "case" and options.get("mode", "upper") not in ("upper", "lower"):
            raise ValueError("大小写转换方式无效")
        if kind == "convert" and options.get("format", "date") not in ("date", "number"):
            raise ValueError("字段转换格式无效")
        if kind == "validate" and options.get("format", "phone") not in ("phone", "email"):
            raise ValueError("校验格式无效")


def clean(source: list[dict], columns: list[str], rules: list[dict]) -> dict:
    validate_rules(rules, columns)
    rows = [r.copy() for r in source]
    changes, issues, rule_stats = [], [], []
    for index, rule in enumerate(rules):
        if not rule.get("enabled", True):
            continue
        kind = rule["type"]
        fields = rule.get("fields") or columns
        options = rule.get("options", {})
        start_changes, start_issues = len(changes), len(issues)
        name = RULE_NAMES[kind]
        if kind == "dedupe":
            seen, kept = set(), []
            for row in rows:
                key = tuple(str(row.get(c, "")) for c in fields)
                if key in seen:
                    changes.append({"row_id": row["_row_id"], "field": "整行", "before": "重复记录", "after": "已移除", "rule": name, "action": "delete"})
                else:
                    seen.add(key)
                    kept.append(row)
            rows = kept
        else:
            for row in rows:
                for field in fields:
                    before = str(row.get(field, ""))
                    after = before
                    if kind == "trim":
                        after = before.strip()
                    elif kind == "fill" and missing(before):
                        after = str(options.get("value", ""))
                    elif kind == "replace":
                        after = before.replace(str(options["search"]), str(options.get("replacement", "")))
                    elif kind == "case":
                        after = before.upper() if options.get("mode", "upper") == "upper" else before.lower()
                    elif kind == "convert" and not missing(before):
                        try:
                            if options.get("format", "date") == "number":
                                number = float(before.replace(",", ""))
                                if not math.isfinite(number):
                                    raise ValueError("not finite")
                                after = format(number, ".15g")
                            else:
                                # Parse each value independently: mixed date formats are common in imports.
                                value = pd.to_datetime(before.strip(), errors="raise")
                                after = value.strftime("%Y-%m-%d")
                        except (ValueError, TypeError, OverflowError):
                            issues.append({"row_id": row["_row_id"], "field": field, "value": before, "rule": name, "reason": "格式转换失败，保留原值"})
                    elif kind == "validate" and not missing(before):
                        pattern = r"1[3-9]\d{9}" if options.get("format", "phone") == "phone" else r"[^\s@]+@[^\s@]+\.[^\s@]+"
                        if not re.fullmatch(pattern, before):
                            issues.append({"row_id": row["_row_id"], "field": field, "value": before, "rule": name, "reason": "手机号格式异常" if options.get("format", "phone") == "phone" else "邮箱格式异常"})
                    if before != after:
                        row[field] = after
                        changes.append({"row_id": row["_row_id"], "field": field, "before": before, "after": after, "rule": name, "action": "update"})
        rule_stats.append({"index": index + 1, "name": name, "changes": len(changes) - start_changes, "issues": len(issues) - start_issues})
    return {"rows": rows, "columns": columns, "changes": changes, "issues": issues,
            "before": quality(source, columns), "after": quality(rows, columns), "rule_stats": rule_stats,
            "executed_at": datetime.now().astimezone().isoformat()}
