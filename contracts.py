# -*- coding: utf-8 -*-
"""
contracts.py - 接口契约（唯一真源）

本项目「数据形状 + 枚举常量」的唯一定义处。
所有模块 import 这里的数据类与常量，保证接口一致。

⚠️ 约束：
- 子 Agent 只读本文件，实现自己那份方法签名时，返回类型须与本文件定义对齐。
- 只有主控（编排本项目的对话）允许修改本文件。

Python 3.9 兼容：类型注解用 typing 模块（Optional 而非 X | Y）。
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any


# ============================================================
# 对话阶段枚举
# ============================================================
class Stage:
    """对话阶段（编排路由状态机的状态集合，规则判定，非 LLM）"""
    OPENING = "opening"       # 寒暄开场
    PRESSURE = "pressure"     # 催婚施压（绕回/升级都仍属施压阶段）
    RESOLVE = "resolve"       # 划界成功，冲突收敛
    DEADLOCK = "deadlock"     # 情绪失控 / 僵持
    END = "end"               # 会话结束（触发复盘 Agent）


# ============================================================
# 约束枚举（关系维护意愿 4 档光谱）
# ============================================================
CONSTRAINTS = {
    "want_maintain": "想维持关系",
    "endure_but_record": "能忍但记账",
    "dont_care": "无所谓",
    "want_cutoff": "想断联",
}


# ============================================================
# 数据类
# ============================================================
@dataclass
class SessionMessage:
    """一条会话消息"""
    role: str            # "user"（我） 或 "ai"（王阿姨）
    content: str


@dataclass
class ScoreResult:
    """评分 Agent 的回合级评分结果"""
    total_score: int                      # 0-100
    dimensions: Dict[str, int]            # {维度中文名: 0-100}
    feedback: str                         # 个性化反馈
    suggested_strategy: str               # 下一轮推荐策略（教学 Agent 上线后由其接管）


@dataclass
class TurnResult:
    """一次用户回合的完整返回（编排路由汇总后返回）"""
    score: ScoreResult
    ai_reply: str                         # 王阿姨的回应（由扮演 Agent 生成）
    next_persona_state: Dict[str, Any]    # 下一轮 persona_state
    next_stage: str                       # 下一阶段（Stage 常量之一）
    teaching_hint: Optional[str] = None   # 实时提示（教学 Agent，可空）


@dataclass
class TeachingCard:
    """教学卡（教学 Agent 在进场景时预生成，非每轮调用）"""
    title: str        # 招式名
    when: str         # 什么时候用
    how: str          # 怎么用（含 1 个例子）
    why: str          # 为什么
    constraint: str   # 适用约束 ID
    example: str      # 话术示例


@dataclass
class ReviewResult:
    """复盘 Agent 的会话级总结结果"""
    summary: str                       # 会话总结
    goal_achieved: bool                # 是否达成该约束目标
    achievement_score: int             # 会话级达成度 0-100
    weak_points: List[str]             # 薄弱点列表
    profile_update: Dict[str, Any]     # 写入用户画像的增量


# ============================================================
# 默认 persona_state（动态状态默认值；具体场景可在 scenario_store 覆盖）
# ============================================================
DEFAULT_PERSONA_STATE = {
    "emotion": 0.3,        # 当前情绪 0~1
    "patience": 0.6,       # 当前耐心 0~1，越低越容易绕回催婚
    "deflect_count": 0,    # 已被转移话题成功的次数
}
