"""framework/lib/taxonomy.py — 场景轴（category）：受控词表 + 关键词自动分类。

两轴模型（PRD v2.1 DDR-5）：
  bucket    治理轴（物理目录）：技能从哪来、走哪条治理路径
            （公开桶 / .private 私有 / local 自动收编 / borrowed 借阅 / .archive 归档）
  category  场景轴（sidecar 多标签）：用户想干什么时该想到它（infra/coding/design…）

为什么不建场景目录（skills/design/…）：
  1. 目录是单亲的，技能天然跨场景（fusion-mcp = making + coding；
     macos-nas-ops = infra + macos）——单亲目录迫使分类学扭曲；
  2. 治理轴已经占了物理目录，再切一层 = 双份存储/软链，sync/archive/
     update-check 全链路复杂化；
  3. 场景会演化：改标签是 sidecar 一行，改目录是 git mv + sidecar source
     失效 + sync map 全改；
  4. 互操作：SKILL.md frontmatter 是 agentskills.io 开放标准（规范无
     category 字段），lichen 私有元数据一律进 sidecar——borrowed 同步
     覆盖 frontmatter 但不覆盖 sidecar，场景标签活得久。

自动分类是确定性卫生动作（关键词命中计分），不是模型猜测：可复现、可测试、
错了 `framework categorize <id> <cat>` 手动改。无命中不打标（宁缺勿滥），
由 evolve 挂 T1 提示人工分类。

计分规则：
  id/name 命中 2 分；description 命中 1 分；正文命中 1 分（仅 reinforcing：
  该 category 已从 id/name/description 拿到 ≥2 分时才计入，且封顶 +2）。
  总分 ≥ MIN_SCORE 入标签，按分数降序，最多 MAX_LABELS 个。
  ASCII 关键词按词首边界匹配（\\bgit 命中 git/gitops，不命中 digit）；
  CJK 关键词按子串匹配。
"""

from __future__ import annotations

import re
from pathlib import Path

BODY_CHARS = 3000      # 正文参与计分的长度上限（控制 hook 耗时）
MIN_SCORE = 2          # 入标签阈值
MAX_LABELS = 3         # 单技能最多标签（防"什么都是"的噪声标签）


def load(cfg: dict) -> dict:
    """从生效配置取词表 {cat: {label, keywords}}。缺省 {}（分类静默降级）。

    词表在 config.default.json，用户可在 state/config.json 增量扩展
    （load_config 是 deep_merge，加新 category 不用抄全表）。
    """
    tax = cfg.get("taxonomy") if isinstance(cfg, dict) else None
    if not isinstance(tax, dict):
        return {}
    out = {}
    for cat, spec in tax.items():
        if not isinstance(spec, dict):
            continue
        kws = [str(k).strip().lower() for k in (spec.get("keywords") or []) if str(k).strip()]
        if kws:
            out[str(cat)] = {"label": str(spec.get("label") or cat), "keywords": kws}
    return out


def bucket_default(bucket: str, cfg: dict) -> list:
    """桶 → 默认场景标签（回填用：bucket 语义已知时不必猜关键词）。"""
    m = (cfg or {}).get("category_defaults") or {}
    return [str(c) for c in (m.get(bucket) or [])]


def _hits(keyword: str, text: str) -> int:
    """关键词命中文本返回 1，否则 0（每源每词最多计 1 分）。"""
    if not text:
        return 0
    t = text.lower()
    kw = keyword.lower()
    if kw.isascii():
        # 词首边界：\bgit 命中 git/gitops/gitignore，不命中 digit
        return 1 if re.search(r"\b" + re.escape(kw), t) else 0
    return 1 if kw in t else 0


def _skill_texts(skill: dict) -> tuple:
    """(head, desc, body)：head = id + frontmatter name（权重最高）。"""
    sid = str(skill.get("id") or "")
    if not sid and skill.get("dir"):
        sid = Path(str(skill["dir"])).name
    fm = skill.get("fm") or {}
    head = f"{sid} {fm.get('name') or ''}"
    desc = str(fm.get("description") or "")
    body = ""
    d = skill.get("dir")
    if d:
        try:
            raw = (Path(str(d)) / "SKILL.md").read_text(encoding="utf-8", errors="replace")
            parts = raw.split("---", 2)
            body = parts[2] if len(parts) >= 3 else raw
        except OSError:
            body = ""
    return head, desc, body[:BODY_CHARS]


def classify(skill: dict, tax: dict) -> list:
    """关键词计分分类。返回按分数降序的 category 列表（可能为空=不猜）。"""
    if not tax:
        return []
    head, desc, body = _skill_texts(skill)
    scores = {}
    for cat, spec in tax.items():
        s = 0
        for kw in spec["keywords"]:
            if _hits(kw, head):
                s += 2
            if _hits(kw, desc):
                s += 1
        if s < MIN_SCORE:
            continue  # 正文只 reinforcing，不 initiate
        for kw in spec["keywords"]:
            if _hits(kw, body):
                s += 1
        scores[cat] = min(s, MIN_SCORE + 4)  # 封顶，防单类别刷分
    return [c for c, _ in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))][:MAX_LABELS]


def normalize(cats, tax: dict) -> tuple:
    """拆分 (词表内, 词表外)。词表外保留原值（对方词表不同），doctor 警告。"""
    valid, unknown = [], []
    for c in cats or []:
        c = str(c)
        (valid if c in tax else unknown).append(c)
    return valid, unknown
