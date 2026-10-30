"""Local, deterministic clustering with explicit exclusions and derived columns."""
from __future__ import annotations

from collections import Counter
from hashlib import blake2b



def validate_cluster(options, fields, columns):
    if not fields or len(fields) > 20:
        raise ValueError("聚类分析请选择 1–20 个字段")
    mode = options.get("mode", "numeric")
    if mode not in ("numeric", "text"):
        raise ValueError("聚类方式无效")
    try:
        k = int(options.get("clusters", "3"))
    except (TypeError, ValueError) as error:
        raise ValueError("分组数量须为 2–12 的整数") from error
    if not 2 <= k <= 12:
        raise ValueError("分组数量须为 2–12 的整数")
    output = options.get("output", "聚类分组").strip()
    if not output or len(output) > 40 or output == "_row_id":
        raise ValueError("分组字段名称须为 1–40 个字符，且不能是系统保留字段")
    if output in columns:
        raise ValueError(f"分组字段「{output}」已存在，请修改名称，避免覆盖原始数据")
    return mode, k, output


def cluster_rows(rows, columns, fields, options):
    # Load machine learning libraries only when an analysis rule is used.
    import numpy as np
    from sklearn.cluster import KMeans, MiniBatchKMeans
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.preprocessing import StandardScaler
    from threadpoolctl import threadpool_limits

    mode, k, output = validate_cluster(options, fields, columns)
    indices, values, documents, issues = [], [], [], []
    name = "聚类分析"
    for index, row in enumerate(rows):
        if mode == "numeric":
            numbers = []
            invalid = False
            for field in fields:
                raw = str(row.get(field, ""))
                try:
                    number = float(raw.strip().replace(",", ""))
                    if not np.isfinite(number) or abs(number) > 1e100:
                        raise ValueError
                    numbers.append(number)
                except (ValueError, OverflowError):
                    invalid = True
                    issues.append({"row_id": row["_row_id"], "field": field, "value": raw,
                                   "rule": name, "reason": "数值为空、无效或过大，此行未参与聚类"})
            if not invalid:
                indices.append(index)
                values.append(numbers)
        else:
            text = " ".join(str(row.get(field, "")).strip()[:512] for field in fields).strip()
            if not text:
                issues.append({"row_id": row["_row_id"], "field": "、".join(fields), "value": "",
                               "rule": name, "reason": "分析文本为空，此行未参与聚类"})
            else:
                indices.append(index)
                documents.append(text)
    if len(indices) < k:
        raise ValueError(f"聚类有效记录仅 {len(indices)} 行，少于设置的 {k} 组；请减少分组数量或先处理缺失 / 格式问题")

    # Fixed seed and limited native workers keep preview/execution repeatable and
    # prevent concurrent desktop requests from consuming every CPU core.
    with threadpool_limits(limits=1):
        if mode == "numeric":
            matrix = StandardScaler().fit_transform(np.asarray(values, dtype=float))
            if np.unique(matrix, axis=0).shape[0] < k:
                raise ValueError("数值特征的不同组合少于分组数量，请减少分组数量或选择其他字段")
            model = KMeans(n_clusters=k, random_state=42, n_init=10, max_iter=100) if len(indices) <= 10000 else MiniBatchKMeans(n_clusters=k, random_state=42, n_init=3, batch_size=1024)
            labels = model.fit_predict(matrix)
        else:
            vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(1, 3), max_features=5000, sublinear_tf=True)
            try:
                matrix = vectorizer.fit_transform(documents)
            except ValueError as error:
                raise ValueError("文本中没有可用于聚类的内容，请选择其他字段") from error
            # Identical sparse feature rows cannot form distinct clusters.
            patterns = {blake2b(matrix.indices[matrix.indptr[i]:matrix.indptr[i + 1]].tobytes()
                                + np.round(matrix.data[matrix.indptr[i]:matrix.indptr[i + 1]], 12).tobytes(), digest_size=16).digest()
                        for i in range(matrix.shape[0])}
            if len(patterns) < k:
                raise ValueError("文本特征的不同组合少于分组数量，请减少分组数量或选择其他字段")
            del patterns
            model = MiniBatchKMeans(n_clusters=k, random_state=42, n_init=5, batch_size=1024, max_iter=100)
            labels = model.fit_predict(matrix)

    # Group numbers carry no ranking meaning. Canonicalize by first source row.
    mapping = {}
    for label in labels:
        mapping.setdefault(int(label), len(mapping) + 1)
    if len(mapping) < k:
        raise ValueError(f"当前特征只能稳定形成 {len(mapping)} 组，少于设置的 {k} 组；请减少分组数量或调整字段")
    assigned = {index: f"分组 {mapping[int(label)]:02d}" for index, label in zip(indices, labels)}
    changes = []
    groups = []
    for index, row in enumerate(rows):
        label = assigned.get(index, "未参与")
        row[output] = label
        changes.append({"row_id": row["_row_id"], "field": output, "before": "", "after": label,
                        "rule": name, "action": "annotate"})
    counts = Counter(assigned.values())
    for label in sorted(counts):
        members = [index for index in indices if assigned[index] == label]
        group = {"label": label, "count": len(members), "share": round(len(members) / len(indices) * 100, 1)}
        if mode == "numeric":
            array = np.asarray([values[i] for i, index in enumerate(indices) if assigned[index] == label])
            group["means"] = {field: round(float(array[:, j].mean()), 4) for j, field in enumerate(fields)}
        else:
            positions = [i for i, index in enumerate(indices) if assigned[index] == label]
            weights = np.asarray(matrix[positions].mean(axis=0)).ravel()
            terms = vectorizer.get_feature_names_out()
            candidates = np.argsort(weights)[::-1]
            group["keywords"] = [str(terms[i]) for i in candidates if weights[i] > 0 and len(str(terms[i]).strip()) >= 2][:6]
            group["examples"] = [documents[i][:80] for i in positions[:2]]
        groups.append(group)
    report = {"mode": mode, "algorithm": type(model).__name__, "fields": list(fields), "output": output,
              "clusters": k, "participating_rows": len(indices), "excluded_rows": len(rows) - len(indices),
              "groups": groups,
              "note": "按数值相近程度分组，已自动标准化量纲。分组编号不代表优劣。" if mode == "numeric" else "按文字片段相似度分组，不代表语义理解或业务类别；每字段最多取前 512 字参与分析。"}
    return output, changes, issues, report
