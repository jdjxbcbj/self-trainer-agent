# -*- coding: utf-8 -*-
"""
contracts.py - 接口契约（唯一真源）

本项目「数据形状 + 枚举常量 + 判定参数」的唯一定义处。
所有模块 import 这里的数据类与常量，保证接口一致。

⚠️ 约束：
- 子 Agent 只读本文件，实现自己那份方法签名时，返回类型须与本文件定义对齐。
- 只有主控（编排本项目的对话）允许修改本文件。

Python 3.9 兼容：类型注解用 typing 模块（Optional 而非 X | Y）。

本版已从「王阿姨催婚 / 关系维护意愿 4 档」同步为「安全对线训练场」：
- 旧 CONSTRAINTS（关系维护意愿）→ 训练身份 Audience（minor/adult）
- 旧 DEFAULT_PERSONA_STATE（情绪/耐心/被转移次数）→ 对峙值 confrontation_value
- 新增判定参数（§3.4 冻结值）+ is_crit / compute_confrontation_delta 纯函数
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


# ============================================================
# 对话阶段枚举
# ============================================================
class Stage:
    """对话阶段（编排路由状态机的状态集合，规则判定，非 LLM）"""
    OPENING = "opening"       # 开场（NPC 先起头）
    PRESSURE = "pressure"     # 施压对峙（占据会话主体）
    RESOLVE = "resolve"       # 通关（优秀/及格，见 §3.4 终局条件）
    DEADLOCK = "deadlock"     # 失控（对峙值≥85 或命中暴力红线）
    END = "end"               # 会话结束（触发复盘 Agent）


# ============================================================
# 训练身份枚举（替代旧「关系维护意愿 4 档」）
# ============================================================
class Audience:
    """训练身份"""
    MINOR = "minor"           # 青少年：仅进入 minorSafe 场景
    ADULT = "adult"           # 成年人：全场景


AUDIENCES = {
    Audience.MINOR: "青少年",
    Audience.ADULT: "成年人",
}


# ============================================================
# 对峙值层级（NPC 台词层级）
# ============================================================
class Tier:
    """NPC 台词层级（由对峙值推导，yield 优先级最高，见 tier_for）"""
    YIELD = "yield"           # ≤25：服软
    LOW = "low"               # 26~44
    MID = "mid"               # 45~69
    HIGH = "high"             # ≥70


def tier_for(confrontation_value: int) -> str:
    """由对峙值推导 NPC 台词层级（§3.4 冻结：yield 优先，不与 low 重叠）。

    返回 Tier 常量之一。
    """
    if confrontation_value <= YIELD_THRESHOLD:
        return Tier.YIELD
    if confrontation_value < LOW_THRESHOLD:
        return Tier.LOW
    if confrontation_value < MID_THRESHOLD:
        return Tier.MID
    return Tier.HIGH


# ============================================================
# 判定参数（§3.4 冻结值；子 Agent 只读，不得各写各的）
# ============================================================
# 对峙值
CONFRONTATION_START = 50       # 单局起始
CONFRONTATION_MIN = 0
CONFRONTATION_MAX = 100

# 暴击（crit）
CRIT_THRESHOLD = 85            # 单回合 total_score ≥ 85 且无红线 → 暴击

# 红线一票否决
RED_LINE_CAP = 30              # 命中红线 → total_score 上限 30（不叠加普通扣分）

# 对峙值涨落（按本回合表现，与当前对峙值无关）
CONFRONT_DELTA = {
    "red_line": 25,            # 命中红线 → +25
    "crit": -15,               # 暴击（≥85 且无红线）→ -15（含额外 -10）
    "low": 10,                 # score < 40 → +10
    "mid": -5,                 # 40 ≤ score < 85 → -5
}

# NPC 台词层级阈值
YIELD_THRESHOLD = 25           # ≤25 → yield
LOW_THRESHOLD = 45             # <45 → low（26~44）
MID_THRESHOLD = 70             # <70 → mid（45~69），≥70 → high

# 终局条件
RESOLVE_CONFRONT = 40          # 优秀通关：对峙值 ≤ 40
CRITS_TO_PASS_DEFAULT = 2      # 默认通关所需暴击数（场景可覆盖）
DEADLOCK_CONFRONT = 85         # 对峙值 ≥ 85 → 失控
ROUND_LIMIT = 20               # 回合上限（≥10，保证「及格通关」可达）


def is_crit(total_score: int, red_line_hits: List[str]) -> bool:
    """是否暴击：单回合 total_score ≥ CRIT_THRESHOLD 且未命中红线（§3.4）。"""
    return not red_line_hits and total_score >= CRIT_THRESHOLD


def compute_confrontation_delta(total_score: int, red_line_hits: List[str]) -> int:
    """对峙值涨落（§3.4 冻结规则）：按本回合表现，与当前对峙值无关。

    返回 int（+25 / -15 / +10 / -5），调用方负责 clamp 到 [CONFRONTATION_MIN, CONFRONTATION_MAX]。
    """
    if red_line_hits:
        return CONFRONT_DELTA["red_line"]
    if total_score >= CRIT_THRESHOLD:
        return CONFRONT_DELTA["crit"]
    if total_score < 40:
        return CONFRONT_DELTA["low"]
    return CONFRONT_DELTA["mid"]


# ============================================================
# 数据类
# ============================================================
@dataclass
class SessionMessage:
    """一条会话消息"""
    role: str            # "user"（用户） 或 "ai"（NPC）
    content: str


@dataclass
class ScoreResult:
    """评分 Agent 的回合级评分结果"""
    total_score: int                       # 0-100
    dimensions: Dict[str, int]             # {维度中文名: 0-100}
    red_line_hits: List[str]               # 命中的红线 ID（可空）
    feedback: str                          # 个性化反馈
    suggested_strategy: str                # 推荐策略 / 合规替代句


@dataclass
class TurnResult:
    """一次用户回合的完整返回（编排路由汇总后返回）"""
    score: ScoreResult
    ai_reply: str                          # NPC 回应（由扮演 Agent 生成）
    confrontation_value: int               # 下一轮对峙值 0~100
    next_stage: str                        # 下一阶段（Stage 常量之一）
    teaching_hint: Optional[str] = None    # 实时提示（教学 Agent，可空）


@dataclass
class TeachingCard:
    """教学卡（教学 Agent 在进场景时预生成，非每轮调用）"""
    title: str        # 招式名
    when: str         # 什么时候用
    how: str          # 怎么用（含 1 个例子）
    why: str          # 为什么
    scenario_id: str  # 适用场景 ID
    example: str      # 话术示例


@dataclass
class ReviewResult:
    """复盘 Agent 的会话级总结结果"""
    summary: str                       # 会话总结
    goal_achieved: bool                # 是否通关
    achievement_score: int             # 会话级达成度 0-100
    weak_points: List[str]             # 薄弱点列表
    profile_update: Dict[str, Any]     # 写入用户画像的增量
