# -*- coding: utf-8 -*-
"""
memory.py - 对话记忆（简化版）

用 defaultdict(list) 在内存中模拟对话历史存储。
每个 session_id 对应一个消息列表，不涉及持久化（进程退出即丢失）。
"""

from collections import defaultdict

import config
from contracts import DEFAULT_PERSONA_STATE, Stage


class ConversationMemory:
    """对话记忆类，按会话存储消息"""

    def __init__(self):
        # defaultdict(list)：访问不存在的 session 时自动创建空列表，省去初始化判断
        self._sessions = defaultdict(list)
        # 动态 persona 状态：访问不存在的 session 时自动返回空 dict（再由 get_persona_state 兜底为默认值）
        self._persona_states = defaultdict(dict)
        # 对话阶段：访问不存在的 session 时自动返回空字符串（再由 get_stage 兜底为 Stage.OPENING）
        self._stages = defaultdict(str)

    def add_message(self, session_id, role, content):
        """
        向指定会话追加一条消息。

        参数:
            session_id: 会话ID
            role: "user"（我）或 "ai"（王阿姨）
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
        # 取最近的 limit 条；切片保留原有顺序（从旧到新）
        context = messages[-limit:]
        print(f"[Memory] 获取会话 {session_id} 最近 {len(context)} 条历史")
        return context

    def clear(self, session_id):
        """清空指定会话的所有历史"""
        self._sessions.pop(session_id, None)
        print(f"[Memory] 已清空会话 {session_id}")

    def get_persona_state(self, session_id):
        """
        获取指定会话的动态 persona 状态（情绪/耐心/被转移话题次数等）。

        为什么返回拷贝：调用方拿到的是独立副本，外部修改不会污染内部存储，
        避免「多人拿到同一份引用、互相覆盖」这类隐性 bug。
        """
        state = self._persona_states.get(session_id)
        if state is None:
            # 从未设置过该会话的状态，返回默认值的一份拷贝
            print(f"[Memory] 会话 {session_id} 无 persona 状态，返回默认值")
            return dict(DEFAULT_PERSONA_STATE)
        print(f"[Memory] 获取会话 {session_id} 的 persona 状态：{state}")
        return dict(state)

    def set_persona_state(self, session_id, state):
        """
        设置指定会话的动态 persona 状态。

        为什么存 dict(state) 拷贝：入参可能是调用方后续还会继续改的字典，
        直接引用会导致内部状态被外部无意篡改；存副本隔离二者生命周期。
        """
        self._persona_states[session_id] = dict(state)
        print(f"[Memory] 会话 {session_id} 已更新 persona 状态：{state}")

    def get_stage(self, session_id):
        """
        获取指定会话当前所处阶段。

        为什么不存在时返回 Stage.OPENING：一次新会话默认从「寒暄开场」起步，
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
