# -*- coding: utf-8 -*-
"""
memory.py - 会话记忆（短时记忆模块）

用 defaultdict 在内存中模拟对话历史存储。
每个 session_id 对应：
- 消息列表（add_message / get_context）
- 对峙值 confrontation_value（0~100，起始 50）
- 对话阶段 Stage（规则判定状态机，非 LLM）

不涉及持久化（进程退出即丢失）。
"""

from collections import defaultdict

import config
from contracts import (
    CONFRONTATION_MAX,
    CONFRONTATION_MIN,
    CONFRONTATION_START,
    Stage,
)


class SessionMemory:
    """会话记忆类，按会话存储消息与动态状态（对峙值 + 阶段）"""

    def __init__(self):
        # defaultdict(list)：访问不存在的 session 时自动创建空列表，省去初始化判断
        self._sessions = defaultdict(list)
        # 对峙值：访问不存在的 session 时自动返回 None（再由 get_confrontation 兜底为 CONFRONTATION_START）
        self._confrontations = defaultdict(lambda: None)
        # 对话阶段：访问不存在的 session 时自动返回空字符串（再由 get_stage 兜底为 Stage.OPENING）
        self._stages = defaultdict(str)

    def add_message(self, session_id, role, content):
        """
        向指定会话追加一条消息。

        参数:
            session_id: 会话ID
            role: "user"（用户）或 "ai"（NPC）
            content: 消息文本
        """
        if role not in ("user", "ai"):
            raise ValueError(f"非法的 role：{role}（只能是 user 或 ai）")

        self._sessions[session_id].append({"role": role, "content": content})
        print(f"[Memory] 会话 {session_id} 追加消息（role={role}）：{content[:20]}...")

        # 防止内存无限增长：超过上限就删掉最老的消息
        max_len = config.DEFAULT_HISTORY_LIMIT * 2
        if len(self._sessions[session_id]) > max_len:
            overflow = len(self._sessions[session_id]) - max_len
            del self._sessions[session_id][:overflow]
            print(f"[Memory] 会话 {session_id} 超过上限，已裁剪 {overflow} 条最老消息")

    def get_context(self, session_id, limit=None):
        """
        返回指定会话最近 limit 条消息（按时间从旧到新）。

        参数:
            session_id: 会话ID
            limit: 取最近几条，None 则使用默认值 config.DEFAULT_HISTORY_LIMIT

        返回:
            list: [{"role": "...", "content": "..."}, ...]
        """
        if limit is None:
            limit = config.DEFAULT_HISTORY_LIMIT

        messages = self._sessions.get(session_id, [])
        # 取最近的 limit 条；切片既保留原有顺序（从旧到新），又返回一份拷贝隔离内部状态
        context = messages[-limit:]
        print(f"[Memory] 获取会话 {session_id} 最近 {len(context)} 条历史")
        return context

    def get_confrontation(self, session_id):
        """
        获取指定会话当前对峙值（0~100）。

        为什么从未设置过时返回 CONFRONTATION_START（50）：一次新会话默认从中性
        对峙值起步，这是状态机的合法起点，避免下游拿到 None 再做兜底判断。
        """
        value = self._confrontations.get(session_id)
        if value is None:
            print(f"[Memory] 会话 {session_id} 无对峙值记录，返回默认值 {CONFRONTATION_START}")
            return CONFRONTATION_START
        print(f"[Memory] 获取会话 {session_id} 当前对峙值：{value}")
        return value

    def set_confrontation(self, session_id, value):
        """
        设置指定会话的对峙值，并 clamp 到 [CONFRONTATION_MIN, CONFRONTATION_MAX]（0~100）。

        对峙值是 int（不可变类型），无需拷贝，直接存储即可。
        """
        clamped = max(CONFRONTATION_MIN, min(CONFRONTATION_MAX, value))
        self._confrontations[session_id] = clamped
        print(f"[Memory] 会话 {session_id} 对峙值已更新为：{clamped}")

    def get_stage(self, session_id):
        """
        获取指定会话当前所处阶段。

        为什么不存在时返回 Stage.OPENING：一次新会话默认从「开场」起步，
        这是状态机的合法起点，避免下游拿到空字符串再做兜底判断。
        """
        stage = self._stages.get(session_id)
        if stage is None or stage == "":
            print(f"[Memory] 会话 {session_id} 无阶段记录，返回默认阶段 {Stage.OPENING}")
            return Stage.OPENING
        print(f"[Memory] 获取会话 {session_id} 当前阶段：{stage}")
        return stage

    def set_stage(self, session_id, stage):
        """
        设置指定会话当前所处阶段。

        阶段是纯字符串常量（Stage 枚举值），不可变类型无需拷贝，
        直接存储即可，后续读取/比较都是值语义。
        """
        self._stages[session_id] = stage
        print(f"[Memory] 会话 {session_id} 阶段已更新为：{stage}")

    def clear(self, session_id):
        """清空指定会话的所有历史、对峙值与阶段"""
        self._sessions.pop(session_id, None)
        self._confrontations.pop(session_id, None)
        self._stages.pop(session_id, None)
        print(f"[Memory] 已清空会话 {session_id}")
