"""趋势与纵向比较 —— 迁移自第二套 Demo（DRP serving/trend.py）的报告侧逻辑。

规格书 §7：日期排序、趋势曲线、本次 VS 历史属确定性计算，由程序完成，
不消耗 LLM Token（§8）。X 轴一律使用真实检查日期 observed_at（F-DATA-05）。

保留的核心判定（与原实现一致）：
  - is_real_change：相对变化超过该指标的 RCV 才算"真实变化"，否则视为
    分析误差 + 个体内生物学波动（"报告里说平稳"和"规则里判平稳"永远同源）；
  - 本次 VS 上一次必须携带两个具体检查日期（F-AN-07 / AC-10）；
  - 只叙述真实变化条目，噪声波动不淹没重点（原 compare_latest 设计）。

新增：连续异常次数 / 连续同向真实变化（streak），供健康问题排序使用。
去除：pandas 依赖与"风险概率走势"（1Y/3Y/5Y 概率不再是核心输出，F-AN-08）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .registry import IndicatorMeta

_DEFAULT_RCV = 0.25  # 未注册指标的保守兜底：变化 >25% 才视为真实


@dataclass(frozen=True)
class SeriesPoint:
    value: float
    date: str              # YYYY-MM-DD 真实检查日期
    report_id: Optional[str]
    grade: int
    unit: Optional[str] = None


@dataclass(frozen=True)
class PairComparison:
    """本次 VS 上一次：两个具体日期 + RCV 判定。"""
    prev_value: float
    curr_value: float
    prev_date: str
    curr_date: str
    delta: float
    delta_pct: Optional[float]
    rcv: float
    is_real_change: bool
    direction: str          # 上升 / 下降 / 平稳
    prev_grade: int
    curr_grade: int

    @property
    def worsened(self) -> bool:
        return abs(self.curr_grade) > abs(self.prev_grade)

    @property
    def improved(self) -> bool:
        return abs(self.curr_grade) < abs(self.prev_grade)

    def to_dict(self) -> dict:
        return {
            "prev_value": self.prev_value, "curr_value": self.curr_value,
            "prev_date": self.prev_date, "curr_date": self.curr_date,
            "delta": round(self.delta, 4),
            "delta_pct": round(self.delta_pct, 4) if self.delta_pct is not None else None,
            "rcv": round(self.rcv, 4),
            "is_real_change": self.is_real_change, "direction": self.direction,
            "prev_grade": self.prev_grade, "curr_grade": self.curr_grade,
            "worsened": self.worsened, "improved": self.improved,
        }


@dataclass
class SeriesInsight:
    """一条标准化指标的纵向洞察。"""
    code: str
    points: List[SeriesPoint]
    latest: SeriesPoint
    compare: Optional[PairComparison]      # <2 个点时为 None
    abnormal_streak: int                   # 末尾连续异常次数
    rise_streak: int                       # 末尾连续"真实上升"步数
    fall_streak: int
    persistent_direction: Optional[str]    # 持续上升 / 持续下降 / None

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "points": [{"value": p.value, "date": p.date, "report_id": p.report_id,
                        "grade": p.grade, "unit": p.unit} for p in self.points],
            "latest": {"value": self.latest.value, "date": self.latest.date,
                       "grade": self.latest.grade, "report_id": self.latest.report_id,
                       "unit": self.latest.unit},
            "compare": self.compare.to_dict() if self.compare else None,
            "abnormal_streak": self.abnormal_streak,
            "rise_streak": self.rise_streak,
            "fall_streak": self.fall_streak,
            "persistent_direction": self.persistent_direction,
        }


def _direction_and_real(prev: float, curr: float, rcv: float):
    if abs(prev) < 1e-9:
        return "平稳", False
    rel = (curr - prev) / abs(prev)
    if abs(rel) <= rcv:
        return "平稳", False
    return ("上升" if rel > 0 else "下降"), True


def compare_pair(prev: SeriesPoint, curr: SeriesPoint, rcv: float) -> PairComparison:
    direction, real = _direction_and_real(prev.value, curr.value, rcv)
    delta = curr.value - prev.value
    pct = (delta / abs(prev.value)) if abs(prev.value) > 1e-9 else None
    return PairComparison(
        prev_value=prev.value, curr_value=curr.value,
        prev_date=prev.date, curr_date=curr.date,
        delta=delta, delta_pct=pct, rcv=rcv,
        is_real_change=real, direction=direction,
        prev_grade=prev.grade, curr_grade=curr.grade,
    )


def analyze_series(code: str, points: List[SeriesPoint],
                   meta: Optional[IndicatorMeta]) -> Optional[SeriesInsight]:
    """输入按 observed_at 升序的点位（同日多次取最后一条由调用方处理）。"""
    if not points:
        return None
    pts = sorted(points, key=lambda p: p.date)
    rcv = meta.rcv if meta is not None else _DEFAULT_RCV
    latest = pts[-1]

    compare = compare_pair(pts[-2], latest, rcv) if len(pts) >= 2 else None

    # 末尾连续异常
    abnormal_streak = 0
    for p in reversed(pts):
        if p.grade != 0:
            abnormal_streak += 1
        else:
            break

    # 末尾连续同向步数（按符号；零变化即中断）。
    # "持续"的真实性不看单步——高变异指标（如 ALT 的 RCV≈55%）的缓慢爬升
    # 每一步都可能落在 RCV 内——而看【累计变化】是否超过 RCV：
    # 42→58→76 累计 +81% > 55% ⇒ 持续上升成立；40→41→42 累计 5% ⇒ 不成立。
    rise = fall = 0
    for i in range(len(pts) - 1, 0, -1):
        delta = pts[i].value - pts[i - 1].value
        if delta > 0 and fall == 0:
            rise += 1
        elif delta < 0 and rise == 0:
            fall += 1
        else:
            break
    persistent = None
    streak = max(rise, fall)
    if streak >= 2:
        start = pts[-(streak + 1)].value
        if abs(start) > 1e-9 and abs(pts[-1].value - start) / abs(start) > rcv:
            persistent = "持续上升" if rise else "持续下降"

    return SeriesInsight(code=code, points=pts, latest=latest, compare=compare,
                         abnormal_streak=abnormal_streak,
                         rise_streak=rise, fall_streak=fall,
                         persistent_direction=persistent)


def trend_phrase(insight: SeriesInsight, name_cn: str, unit: str = "") -> str:
    """面向用户的一句话趋势描述（含具体数值与日期，AC-10）。"""
    u = unit or (insight.latest.unit or "")
    if insight.persistent_direction:
        shown = insight.points[-4:]
        vals = " → ".join(f"{p.value:g}" for p in shown)
        return (f"{name_cn} 多次记录呈{insight.persistent_direction}"
                f"（{vals}{u}，{shown[0].date} → {shown[-1].date}）")
    c = insight.compare
    if c is None:
        return f"{name_cn} 当前 {insight.latest.value:g}{u}（{insight.latest.date}），历史记录不足以判断趋势"
    if not c.is_real_change:
        return (f"{name_cn} 与 {c.prev_date} 相比基本平稳，"
                f"维持在 {c.curr_value:g}{u} 附近（{c.curr_date}）")
    pct = f"（{c.delta_pct:+.1%}）" if c.delta_pct is not None else ""
    tag = "，程度较前次加重" if c.worsened else ("，较前次有所改善" if c.improved else "")
    return (f"{name_cn} 由 {c.prev_date} 的 {c.prev_value:g}{u} "
            f"{c.direction}至 {c.curr_date} 的 {c.curr_value:g}{u}{pct}{tag}")
