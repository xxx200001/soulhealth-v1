"""检验指标归一化词典 —— 自第二套 Demo（DRP 平台 ingest/lexicon.py）迁移。

在注册表精确匹配之上加两层 OCR 容错：
  第 1 层  精确匹配（registry.resolve_alias）      置信度 1.0
  第 2 层  OCR 混淆字符折叠（0↔O、1↔I、5↔S…）      置信度 0.95
  第 3 层  单字符编辑距离（距离 ≤1 且候选唯一）     置信度 0.85

三条安全红线（原样保留 ——"宁可漏配，不可错配"）：
  红线 1  短键禁入模糊层：NA/CA 编辑距离恰为 1，长度 <4 只允许精确与折叠；
  红线 2  数字位禁止参与编辑距离：HbA1c 的 1 是语义不是噪声；
  红线 3  歧义即拒绝：折叠或模糊命中 ≥2 个指标码时返回无匹配并带出候选。

错配的代价是一条无法被下游校验发现的毒数据（把血钾配成血钠，数值单位
全都合法）；拒绝的代价只是这一项"未标准化"，仍以原始名称保留展示。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .registry import ReferenceRegistry, normalize_alias

_CONFUSION_FOLD: dict[str, str] = {
    "0": "O", "Q": "O", "D": "O",
    "1": "I", "L": "I", "|": "I", "!": "I",
    "5": "S",
    "8": "B", "Β": "B",
    "2": "Z",
    "6": "G",
    "Μ": "M", "Α": "A", "Ε": "E", "Ο": "O", "Ρ": "P", "Τ": "T",
    "Γ": "R",
}


def fold_confusions(normalized: str) -> str:
    return "".join(_CONFUSION_FOLD.get(ch, ch) for ch in normalized)


_FUZZY_MIN_LEN = 4
_CONF_EXACT = 1.0
_CONF_FOLD = 0.95
_CONF_FUZZY = 0.85


@dataclass(frozen=True)
class LexiconMatch:
    code: Optional[str]
    confidence: float
    method: str  # exact / fold / fuzzy / none / ambiguous
    query: str
    candidates: tuple = field(default=())

    @property
    def matched(self) -> bool:
        return self.code is not None


class IndicatorLexicon:
    """无状态查询，构造时一次性建好索引，可跨线程复用。"""

    def __init__(self, registry: ReferenceRegistry):
        self.registry = registry
        self._folded: dict[str, str] = {}
        folded_collisions: dict[str, set] = {}
        fuzzy_pool: list = []

        for code in registry.codes:
            meta = registry.get(code)
            names = (code, meta.name_cn, *meta.aliases)
            seen_keys: set = set()
            for name in names:
                key = normalize_alias(name)
                if not key or key in seen_keys:
                    continue
                seen_keys.add(key)
                fkey = fold_confusions(key)
                prev = self._folded.get(fkey)
                if prev is not None and prev != code:
                    folded_collisions.setdefault(fkey, {prev}).add(code)
                else:
                    self._folded[fkey] = code
                if len(key) >= _FUZZY_MIN_LEN:
                    fuzzy_pool.append((key, code))

        for fkey, codes in folded_collisions.items():
            self._folded.pop(fkey, None)
        self._fuzzy_keys = tuple(fuzzy_pool)
        self._collisions = {k: tuple(sorted(v)) for k, v in folded_collisions.items()}

    def _direct_lookup(self, raw_name: str) -> LexiconMatch:
        query = normalize_alias(raw_name)
        if not query:
            return LexiconMatch(None, 0.0, "none", query="")

        code = self.registry.resolve_alias(raw_name)
        if code is not None:
            return LexiconMatch(code, _CONF_EXACT, "exact", query=query)

        fkey = fold_confusions(query)
        if fkey in self._collisions:
            return LexiconMatch(None, 0.0, "ambiguous", query=query,
                                candidates=self._collisions[fkey])
        code = self._folded.get(fkey)
        if code is not None:
            return LexiconMatch(code, _CONF_FOLD, "fold", query=query)

        if len(query) < _FUZZY_MIN_LEN:
            return LexiconMatch(None, 0.0, "none", query=query)

        hits: dict = {}
        for key, kcode in self._fuzzy_keys:
            if kcode in hits:
                continue
            if _within_one_edit_no_digit(query, key):
                hits[kcode] = key
        if len(hits) == 1:
            ((code, _k),) = hits.items()
            return LexiconMatch(code, _CONF_FUZZY, "fuzzy", query=query)
        if len(hits) > 1:
            return LexiconMatch(None, 0.0, "ambiguous", query=query,
                                candidates=tuple(sorted(hits)))
        return LexiconMatch(None, 0.0, "none", query=query)

    def lookup(self, raw_name: str) -> LexiconMatch:
        res = self._direct_lookup(raw_name)
        if res.matched:
            return res
        cleaned = re.sub(r"^\s*\d+[\.、:：\-\s]+\s*", "", raw_name or "").strip()
        if cleaned and cleaned != raw_name:
            res = self._direct_lookup(cleaned)
            if res.matched:
                return res
        target = cleaned or (raw_name or "")
        # 如果包含比值/除号关系，禁止截断并错配到单侧指标（如 AST/ALT 不得错配为 AST）
        if "/" in target or "比" in target or "RATIO" in target.upper():
            return LexiconMatch(None, 0.0, "none", query=target)

        tokens = [t.strip(" ()[]（）【】:：·")
                  for t in re.split(r"[\s()（）\[\]]+", target)
                  if t.strip(" ()[]（）【】:：·")]
        for t in tokens:
            if len(t) >= 2 or t in self.registry.codes:
                res = self._direct_lookup(t)
                if res.matched:
                    return res
        return res


def _within_one_edit_no_digit(a: str, b: str) -> bool:
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:
        diff = [(ca, cb) for ca, cb in zip(a, b) if ca != cb]
        if len(diff) != 1:
            return False
        ca, cb = diff[0]
        return not (ca.isdigit() or cb.isdigit())
    if la > lb:
        a, b, la, lb = b, a, lb, la
    i = j = 0
    edited: Optional[str] = None
    while i < la and j < lb:
        if a[i] == b[j]:
            i += 1
            j += 1
            continue
        if edited is not None:
            return False
        edited = b[j]
        j += 1
    if edited is None:
        edited = b[-1]
    return not edited.isdigit()


_lexicon: Optional[IndicatorLexicon] = None


def get_lexicon() -> IndicatorLexicon:
    global _lexicon
    if _lexicon is None:
        from .registry import get_registry
        _lexicon = IndicatorLexicon(get_registry())
    return _lexicon
