"""指标参考区间注册表 —— 自第二套 Demo（DRP 平台 data/reference.py）迁移。

按《技术需求规格书》§7"AI/规则/程序职责边界"：单位标准化、指标映射、
阈值异常判断由规则完成并持久化，不交给 LLM 自由生成。

保留原实现的三个关键设计：
  1. 按 (指标, 性别, 年龄) 匹配最具体参考区间，性别未知取男女并集兜底；
  2. RCV（参考变化值）= 2.77·√(CVa²+CVi²)：两次检测的相对变化超过 RCV
     才认定为"真实变化"，是趋势判定（上升/下降/平稳）的唯一依据 ——
     替代第二套 Demo 中 1Y/3Y/5Y 概率模型成为 V1 的纵向比较地基；
  3. grade_multiplier 分级：不同指标的危险梯度不同（ALT 超 3 倍才算中度，
     血钾超 1.2 倍已是危急），分级边界写在 configs/indicators.yaml，不硬编码。

移除项：lab_id 多实验室版本管理、log_transform 建模用途（V1 无模型训练）。
"""
from __future__ import annotations

import functools
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

SEX_MALE = "M"
SEX_FEMALE = "F"
SEX_UNKNOWN = "U"
_SEX_ANY = "ANY"

# 异常分级：带符号整数，负=偏低 正=偏高；0=正常。
GRADE_LABELS = {
    -3: "重度偏低", -2: "中度偏低", -1: "轻度偏低",
    0: "正常", 1: "轻度偏高", 2: "中度偏高", 3: "重度偏高",
}


def to_halfwidth(s: str) -> str:
    """全角转半角。化验单 OCR 输出里全角字母数字极常见（ＡＬＴ / ＨｂＡ１ｃ）。"""
    out = []
    for ch in s:
        code = ord(ch)
        if 0xFF01 <= code <= 0xFF5E:
            out.append(chr(code - 0xFEE0))
        elif code == 0x3000:
            out.append(" ")
        else:
            out.append(ch)
    return "".join(out)


def normalize_alias(name: Optional[str]) -> str:
    """别名归一化：全角转半角、去空格分隔符、统一大写、微量符号μ转u。
    不去数字（HbA1c 的 1 是语义）。"""
    if name is None:
        return ""
    s = to_halfwidth(str(name)).strip()
    s = s.replace("μ", "u").replace("µ", "u").replace("Μ", "U").upper()
    for ch in " \t_·．.-()（）:：,，/^":
        s = s.replace(ch, "")
    return s


@dataclass(frozen=True)
class RefInterval:
    lower: Optional[float]
    upper: Optional[float]
    sex: str
    age_low: float
    age_high: float

    def contains(self, value: float) -> bool:
        if self.lower is not None and value < self.lower:
            return False
        if self.upper is not None and value > self.upper:
            return False
        return True


@dataclass(frozen=True)
class GradeMultiplier:
    mild: float = 1.0
    moderate: float = 2.0
    severe: float = 3.0


@dataclass
class IndicatorMeta:
    code: str
    name_cn: str
    aliases: tuple
    canonical_unit: str
    unit_conversions: dict
    plausible_range: tuple
    magnitude_fix: bool
    critical_low: Optional[float]
    critical_high: Optional[float]
    grade_multiplier: GradeMultiplier
    cv_intra: float
    cv_analytical: float
    intervals: tuple = field(default=())

    # ---------------- 参考区间匹配 ----------------
    def match_interval(self, sex: str, age: Optional[float]) -> Optional[RefInterval]:
        """先性别精确匹配（M/F 优先于 ANY），再年龄落点；多条命中取年龄跨度最窄。
        性别未知且无 ANY 区间时取男女并集，避免把正常值误判为异常。"""
        if not self.intervals:
            return None
        age_val = age if age is not None else -1.0

        def age_ok(iv: RefInterval) -> bool:
            if age is None or age <= 0:
                return True
            return iv.age_low <= age_val < iv.age_high

        sex_norm = (sex or SEX_UNKNOWN).upper()
        if sex_norm in (SEX_MALE, SEX_FEMALE):
            candidates = [iv for iv in self.intervals
                          if iv.sex in (sex_norm, _SEX_ANY) and age_ok(iv)]
            specific = [iv for iv in candidates if iv.sex == sex_norm]
            pool = specific or candidates
        else:
            pool = [iv for iv in self.intervals if iv.sex == _SEX_ANY and age_ok(iv)]
            if not pool:
                merged = self._merge_sex_intervals(age_ok)
                if merged is not None:
                    return merged
        if not pool:
            if sex_norm in (SEX_MALE, SEX_FEMALE):
                fallback = [iv for iv in self.intervals if iv.sex in (sex_norm, _SEX_ANY)]
                specific = [iv for iv in fallback if iv.sex == sex_norm]
                pool = specific or fallback
            else:
                pool = list(self.intervals)
        if not pool:
            return None
        return min(pool, key=lambda iv: iv.age_high - iv.age_low)

    def _merge_sex_intervals(self, age_ok) -> Optional[RefInterval]:
        pool = [iv for iv in self.intervals if age_ok(iv)]
        if not pool:
            return None
        lowers = [iv.lower for iv in pool if iv.lower is not None]
        uppers = [iv.upper for iv in pool if iv.upper is not None]
        return RefInterval(
            lower=min(lowers) if lowers else None,
            upper=max(uppers) if uppers else None,
            sex=_SEX_ANY,
            age_low=min(iv.age_low for iv in pool),
            age_high=max(iv.age_high for iv in pool),
        )

    # ---------------- 校验 ----------------
    def is_plausible(self, value: float) -> bool:
        lo, hi = self.plausible_range
        return lo <= value <= hi

    def is_critical(self, value: float) -> bool:
        if self.critical_low is not None and value <= self.critical_low:
            return True
        if self.critical_high is not None and value >= self.critical_high:
            return True
        return False

    def convert_to_canonical(self, value: float, unit: Optional[str]) -> Optional[float]:
        """可安全换算时返回标准化值；单位未知/不可换算返回 None（F-DATA-02：
        趋势比较不得混用不可比单位）。"""
        if unit is None or not str(unit).strip():
            return value  # 无单位视作已是 canonical（报告常省略单位）
        u = normalize_alias(unit)
        cu = normalize_alias(self.canonical_unit)
        if u == cu:
            return value
        for k, factor in self.unit_conversions.items():
            if normalize_alias(k) == u:
                return value * float(factor)
        return None

    # ---------------- RCV ----------------
    @functools.cached_property
    def rcv(self) -> float:
        """参考变化值（双侧 95%）：RCV = 2.77·√(CVa² + CVi²)。
        血钠 CVi 仅 0.7% 而 CRP 高达 42%，统一拍脑袋阈值会同时制造
        大量假阳性和假阴性 —— 因此 RCV 是趋势判定的唯一依据。"""
        return 2.77 * math.sqrt(self.cv_analytical ** 2 + self.cv_intra ** 2)


def grade_value(meta: IndicatorMeta, value: float,
                sex: str = "ANY", age: Optional[float] = None) -> int:
    """按注册表分级：返回 -3..3。迁移自 DRP serving/referral.grade_value。"""
    iv = meta.match_interval(sex=sex, age=age)
    if iv is None:
        return 0
    gm = meta.grade_multiplier
    if iv.upper is not None and value > iv.upper:
        if value >= iv.upper * gm.severe:
            return 3
        if value >= iv.upper * gm.moderate:
            return 2
        if value > iv.upper * gm.mild:
            return 1
        return 0
    if iv.lower is not None and value < iv.lower:
        if gm.severe > 0 and value <= iv.lower / gm.severe:
            return -3
        if gm.moderate > 0 and value <= iv.lower / gm.moderate:
            return -2
        if gm.mild > 0 and value < iv.lower / gm.mild:
            return -1
    return 0


def grade_from_ref(value: float, ref_low: Optional[float],
                   ref_high: Optional[float],
                   gm: GradeMultiplier = GradeMultiplier()) -> int:
    """兜底分级：注册表未收录该指标时，用当次报告自带参考范围判轻度异常。"""
    if ref_high is not None and value > ref_high:
        if value >= ref_high * gm.severe:
            return 3
        if value >= ref_high * gm.moderate:
            return 2
        return 1
    if ref_low is not None and value < ref_low:
        if gm.severe > 0 and value <= ref_low / gm.severe:
            return -3
        if gm.moderate > 0 and value <= ref_low / gm.moderate:
            return -2
        return -1
    return 0


class ReferenceRegistry:
    """指标注册表：全系统唯一入口，业务代码禁止硬编码参考区间。"""

    def __init__(self, cfg: dict):
        self.version: str = cfg.get("version", "unknown")
        self.source: str = cfg.get("source", "")
        self._defaults: dict = cfg.get("defaults", {}) or {}
        self._indicators: dict[str, IndicatorMeta] = {}
        self._alias_index: dict[str, str] = {}

        for code, raw in (cfg.get("indicators") or {}).items():
            meta = self._build_meta(code, raw)
            self._indicators[meta.code] = meta
            for alias in meta.aliases:
                key = normalize_alias(alias)
                if key in self._alias_index and self._alias_index[key] != meta.code:
                    raise ValueError(
                        f"别名冲突: '{alias}' 同时指向 "
                        f"{self._alias_index[key]} 和 {meta.code}")
                self._alias_index[key] = meta.code

    def _build_meta(self, code: str, raw: dict) -> IndicatorMeta:
        d = self._defaults
        gm_raw = raw.get("grade_multiplier") or d.get("grade_multiplier") or {}
        crit = raw.get("critical") or {}
        plausible = raw.get("plausible_range") or [float("-inf"), float("inf")]
        intervals = []
        for iv in raw.get("reference") or []:
            age = iv.get("age", [0, 120])
            intervals.append(RefInterval(
                lower=_as_float(iv.get("lower")), upper=_as_float(iv.get("upper")),
                sex=str(iv.get("sex", _SEX_ANY)).upper(),
                age_low=float(age[0]), age_high=float(age[1]),
            ))
        return IndicatorMeta(
            code=code.upper(),
            name_cn=raw.get("name_cn", code),
            aliases=tuple(raw.get("aliases") or [code]),
            canonical_unit=raw.get("canonical_unit", ""),
            unit_conversions={str(k): float(v)
                              for k, v in (raw.get("unit_conversions") or {}).items()},
            plausible_range=(float(plausible[0]), float(plausible[1])),
            magnitude_fix=bool(raw.get("magnitude_fix", d.get("magnitude_fix", True))),
            critical_low=_as_float(crit.get("low")),
            critical_high=_as_float(crit.get("high")),
            grade_multiplier=GradeMultiplier(
                mild=float(gm_raw.get("mild", 1.0)),
                moderate=float(gm_raw.get("moderate", 2.0)),
                severe=float(gm_raw.get("severe", 3.0))),
            cv_intra=float(raw.get("cv_intra", d.get("cv_intra", 0.10))),
            cv_analytical=float(raw.get("cv_analytical", d.get("cv_analytical", 0.05))),
            intervals=tuple(intervals),
        )

    # ---------------- 查询 ----------------
    def get(self, code: str) -> Optional[IndicatorMeta]:
        return self._indicators.get((code or "").upper())

    def resolve_alias(self, raw_name: str) -> Optional[str]:
        return self._alias_index.get(normalize_alias(raw_name))

    @property
    def codes(self) -> tuple:
        return tuple(self._indicators.keys())

    def __contains__(self, code: str) -> bool:
        return (code or "").upper() in self._indicators

    def __len__(self) -> int:
        return len(self._indicators)

    @classmethod
    def from_yaml(cls, path) -> "ReferenceRegistry":
        with Path(path).open("r", encoding="utf-8") as f:
            return cls(yaml.safe_load(f))


def _as_float(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    return float(v)


# ---------------------------------------------------------------- 单例
_registry: Optional[ReferenceRegistry] = None


def get_registry() -> ReferenceRegistry:
    global _registry
    if _registry is None:
        from .. import config
        _registry = ReferenceRegistry.from_yaml(config.INDICATORS_YAML)
    return _registry
