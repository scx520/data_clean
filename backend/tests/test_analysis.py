import copy

import pytest

from app.engine import clean


def config(mode="numeric", k="2", output="聚类分组", fields=None):
    return {"id": "cluster", "type": "cluster", "enabled": True, "fields": fields or ["金额"], "options": {"mode": mode, "clusters": k, "output": output}}


def test_numeric_clusters_are_separated_repeatable_and_preserve_originals():
    columns = ["编号", "金额", "次数"]
    rows = [{"_row_id": i + 1, "编号": str(i), "金额": str(value), "次数": str(value * 1_000_000)} for i, value in enumerate([10, 11, 12, 1000, 1001, 1002])]
    original = copy.deepcopy(rows)
    rules = [config(fields=["金额", "次数"])]
    first, second = clean(rows, columns, rules), clean(rows, columns, rules)
    assert rows == original
    assert columns == ["编号", "金额", "次数"]
    assert first["rows"] == second["rows"]
    assert first["rows"][0]["聚类分组"] == first["rows"][2]["聚类分组"]
    assert first["rows"][3]["聚类分组"] != first["rows"][0]["聚类分组"]
    assert first["after"] == first["before"]
    assert first["columns"][-1] == "聚类分组"
    assert len(first["changes"]) == 6
    assert all(change["action"] == "annotate" for change in first["changes"])
    assert first["rule_stats"][0]["annotated_cells"] == 6
    report = first["analyses"][0]
    assert [g["count"] for g in report["groups"]] == [3, 3]
    assert report["groups"][0]["means"]["金额"] == 11


def test_excluded_numeric_rows_are_retained_and_explicitly_reported():
    rows = [{"_row_id": i + 1, "金额": value} for i, value in enumerate(["1,000", "1001", "10", "11", "", "未知", "inf"])]
    result = clean(rows, ["金额"], [config()])
    assert len(result["rows"]) == 7
    assert [r["聚类分组"] for r in result["rows"][-3:]] == ["未参与"] * 3
    assert result["analyses"][0]["excluded_rows"] == 3
    assert len(result["issues"]) == 3


def test_chinese_text_clustering_handles_empty_rows_and_exports_features():
    texts = ["移动通信营业厅", "移动通信营业厅", "移动通信营业厅", "水果蔬菜超市", "水果蔬菜超市", "水果蔬菜超市", ""]
    rows = [{"_row_id": i + 1, "名称": text} for i, text in enumerate(texts)]
    result = clean(rows, ["名称"], [config(mode="text", fields=["名称"])])
    labels = [r["聚类分组"] for r in result["rows"]]
    assert labels[0] == labels[1] == labels[2]
    assert labels[3] == labels[4] == labels[5]
    assert labels[0] != labels[3]
    assert labels[-1] == "未参与"
    report = result["analyses"][0]
    assert report["participating_rows"] == 6
    assert all(g["keywords"] and g["examples"] for g in report["groups"])


@pytest.mark.parametrize("rule", [config(k="1"), config(k="13"), config(k="2.5"), config(output="金额"), config(output="_row_id"), config(mode="unknown")])
def test_invalid_cluster_parameters_fail_clearly(rule):
    with pytest.raises(ValueError):
        clean([{"_row_id": 1, "金额": "10"}], ["金额"], [rule])


def test_identical_features_and_insufficient_records_do_not_fake_groups():
    for rows in ([{"_row_id": 1, "金额": "10"}], [{"_row_id": i, "金额": "10"} for i in range(5)]):
        with pytest.raises(ValueError):
            clean(rows, ["金额"], [config()])
    with pytest.raises(ValueError):
        clean([{"_row_id": i, "名称": "相同企业"} for i in range(5)], ["名称"], [config(mode="text", fields=["名称"])])


def test_multiple_clustering_rules_use_unique_output_fields():
    rows = [{"_row_id": i, "金额": str(i)} for i in range(6)]
    result = clean(rows, ["金额"], [config(), config(output="第二分组")])
    assert result["columns"] == ["金额", "聚类分组", "第二分组"]
    assert len(result["analyses"]) == 2
    with pytest.raises(ValueError):
        clean(rows, ["金额"], [config(), config()])
