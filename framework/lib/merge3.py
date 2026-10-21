"""framework/lib/merge3.py — 逐行三方合并（base / ours / theirs）。

用 difflib 的匹配块把两侧相对 base 的改动对齐：
  - 只有一侧改动的区域 → 取那一侧
  - 两侧改动相同 → 取一份
  - 两侧改动不同 → 冲突标记（<<<<<<< ours / ======= / >>>>>>> theirs）
纯插入落在同一位置的，视为冲突（避免两份插入被无声拼接）。
"""

from __future__ import annotations

import difflib


def _changes(base: list, other: list) -> list:
    """返回 [(base_start, base_end, replacement_lines)]，只含差异区域。"""
    sm = difflib.SequenceMatcher(a=base, b=other, autojunk=False)
    out = []
    for tag, i1, i2, _j1, j2 in sm.get_opcodes():
        if tag != "equal":
            out.append((i1, i2, other[_j1:j2]))
    return out


def _overlap(a, b) -> bool:
    """两个改动区域是否冲突：区间真正相交才算。

    a/b 是 (start, end, side, replacement) 四元组。
    同点纯插入（start==end）不互斥——双方在文件末尾各追加一节是常见协作，
    放行后按 ours→theirs 顺序拼接，两节都保留（git 的并列追加语义）。
    """
    s1, e1 = a[0], a[1]
    s2, e2 = b[0], b[1]
    return s1 < e2 and s2 < e1


def merge_text(base: str, ours: str, theirs: str):
    """合并三个版本的文本。返回 (merged_text, conflict_count)。"""
    b = base.splitlines()
    o = ours.splitlines()
    t = theirs.splitlines()
    events = ([(s, e, "o", rep) for s, e, rep in _changes(b, o)]
              + [(s, e, "t", rep) for s, e, rep in _changes(b, t)])
    if not events:
        return ours, 0
    events.sort(key=lambda x: (x[0], x[1]))

    result = []
    conflicts = 0
    pos = 0
    i = 0
    while i < len(events):
        group = [events[i]]
        j = i + 1
        while j < len(events) and any(_overlap(events[j], g) for g in group):
            group.append(events[j])
            j += 1
        start = min(g[0] for g in group)
        end = max(g[1] for g in group)
        result.extend(b[pos:start])
        reps = {}
        for s, e, side, rep in group:
            reps[side] = rep  # 同侧多区域被 group 合并时后者覆盖，极端场景可接受
        if len(reps) == 1:
            result.extend(next(iter(reps.values())))
        elif reps.get("o") == reps.get("t"):
            result.extend(reps["o"])
        else:
            conflicts += 1
            result.append("<<<<<<< ours")
            result.extend(reps.get("o", b[start:end]))
            result.append("=======")
            result.extend(reps.get("t", b[start:end]))
            result.append(">>>>>>> theirs")
        pos = end
        i = j

    result.extend(b[pos:])
    text = "\n".join(result)
    # join 丢尾换行：原文本以 \n 结尾时补回，避免制造 "no newline at EOF" diff 噪声
    if ours.endswith("\n") and not text.endswith("\n"):
        text += "\n"
    return text, conflicts


def merge_files(base_dir, ours_dir, theirs_dir, rel: str):
    """合并单个文件。返回 (status, content_or_None)。

    status: "same" | "ours" | "theirs" | "merged" | "conflict" | "binary_conflict"
    """
    import base64
    import hashlib

    def _read(d):
        p = (d / rel) if d else None
        if not p or not p.is_file():
            return None
        return p.read_bytes()

    def _is_text(data):
        if data is None:
            return True
        try:
            data.decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False

    bo, oo, to = _read(base_dir), _read(ours_dir), _read(theirs_dir)
    if oo == to:
        return "same", None
    if oo == bo:
        return "theirs", to
    if to == bo:
        return "ours", None
    if not (_is_text(oo) and _is_text(to) and _is_text(bo)):
        return "binary_conflict", None
    merged, conflicts = merge_text(
        bo.decode("utf-8") if bo else "",
        oo.decode("utf-8") if oo else "",
        to.decode("utf-8") if to else "",
    )
    if conflicts:
        return "conflict", merged
    return "merged", merged
