import copy

import pytest

from app.engine import clean, quality


def rule(kind, fields=None, **options):
    return {"id": kind, "type": kind, "enabled": True, "fields": fields or [], "options": options}


def test_ordered_cleaning_is_traceable_and_does_not_mutate_source():
    columns = ["姓名", "城市", "邮箱"]
    rows = [
        {"_row_id": 1, "姓名": " 张三 ", "城市": "", "邮箱": "A@EXAMPLE.COM"},
        {"_row_id": 2, "姓名": "张三", "城市": "未知", "邮箱": "a@example.com"},
        {"_row_id": 3, "姓名": "李四", "城市": "济南", "邮箱": "b@example.com"},
    ]
    original = copy.deepcopy(rows)
    result = clean(rows, columns, [rule("trim"), rule("fill", ["城市"], value="未知"), rule("case", ["邮箱"], mode="lower"), rule("dedupe")])
    assert rows == original
    assert [r["_row_id"] for r in result["rows"]] == [1, 3]
    assert result["rows"][0]["城市"] == "未知"
    assert result["changes"][-1]["row_id"] == 2
    assert result["changes"][-1]["action"] == "delete"
    assert result["before"]["missing_cells"] == 1
    assert result["after"]["missing_cells"] == 0
    assert result["after"]["score"] == 100
    assert sum(s["changes"] for s in result["rule_stats"]) == len(result["changes"])


def test_conversion_failure_preserves_values_and_records_issues():
    rows = [
        {"_row_id": 5, "金额": "1,280.50", "日期": "2026/01/05", "手机": "138-0013-8000"},
        {"_row_id": 8, "金额": "待核实", "日期": "无日期", "手机": "13800138000"},
    ]
    result = clean(rows, ["金额", "日期", "手机"], [rule("convert", ["金额"], format="number"), rule("convert", ["日期"], format="date"), rule("replace", ["手机"], search="-", replacement=""), rule("validate", ["手机"], format="phone")])
    assert result["rows"][0]["金额"] == "1280.5"
    assert result["rows"][0]["日期"] == "2026-01-05"
    assert result["rows"][0]["手机"] == "13800138000"
    assert result["rows"][1]["金额"] == "待核实"
    assert len(result["issues"]) == 2
    assert {i["row_id"] for i in result["issues"]} == {8}


def test_dedupe_uses_selected_fields_and_disabled_rules_are_skipped():
    rows = [{"_row_id": 1, "姓名": "甲", "城市": "济南"}, {"_row_id": 2, "姓名": "甲", "城市": "青岛"}]
    disabled = {**rule("replace", ["城市"], search="济南", replacement="北京"), "enabled": False}
    result = clean(rows, ["姓名", "城市"], [disabled, rule("dedupe", ["姓名"])])
    assert result["rows"] == [rows[0]]
    assert len(result["rule_stats"]) == 1


@pytest.mark.parametrize("config", [rule("fill", ["城市"], value=""), rule("replace", ["城市"], search=""), rule("trim", ["不存在"]), rule("convert", ["城市"], format="unknown")])
def test_invalid_configuration_is_rejected(config):
    with pytest.raises(ValueError):
        clean([{"_row_id": 1, "城市": "济南"}], ["城市"], [config])


def test_quality_empty_and_whitespace_fields():
    assert quality([], ["城市"])["score"] == 100
    result = quality([{"_row_id": 1, "城市": " "}, {"_row_id": 2, "城市": " "}], ["城市"])
    assert result["missing_cells"] == 2
    assert result["duplicate_rows"] == 1
    assert result["score"] == 0
