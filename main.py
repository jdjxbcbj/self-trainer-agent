# -*- coding: utf-8 -*-
"""
main.py - 主装配（TrainerSystem）

从最早的 ScoreSystem（只做评分）演化为 TrainerSystem（完整训练闭环）。
它本身不做任何业务判断，只是把 Router 装配起来，对外提供统一入口，
并保留 score() 作为向后兼容的「仅评分」快捷方法。

一条完整回合由 Router.handle_turn 调度：评分 → 对峙值涨落 → 终局判定 → 扮演 → 教学 → 写记忆 → 落库。
会话开局由 Router.start_session 调度：落库（user/session）+ NPC 开场白 + 教学卡。
会话结束由 Router.end_session 调度：复盘 → 落库 sessions + 更新画像。
"""

from scenario_store import ScenarioStore
from judge_agent import JudgeAgent
from router import Router


class TrainerSystem:
    """训练系统主装配：对外统一入口，内部委托 Router 编排"""

    def __init__(self):
        # Router 内部已初始化并持有全部子 Agent（含记忆/数据层/知识库等），
        # 这里只保留几个最常用的引用，方便 CLI 直接读取历史、写 AI 消息。
        self.router = Router()
        self.scenario_store = self.router.scenario_store
        self.memory = self.router.memory
        self.storage = self.router.storage
        self.judge_agent = self.router.judge_agent
        print("[主链路] 训练系统初始化完成")

    # ------------------------------------------------------------------
    # 完整闭环
    # ------------------------------------------------------------------

    def start_session(self, user_id, session_id, scenario_id, audience):
        """
        开新会话：落库 + NPC 开场白 + 教学卡。
        委托 Router，返回 (opening, teaching_card)。
        """
        return self.router.start_session(user_id, session_id, scenario_id, audience)

    def handle_turn(self, user_id, session_id, scenario_id, audience, user_response):
        """
        处理一次完整用户回合：评分 + NPC 回应 + 实时提示 + 阶段判定 + 写记忆 + 落库。
        委托 Router，返回 TurnResult。
        """
        return self.router.handle_turn(
            user_id, session_id, scenario_id, audience, user_response
        )

    def end_session(self, user_id, session_id, scenario_id, audience):
        """
        结束会话：复盘 + 落库 sessions + 更新画像，返回 ReviewResult。
        """
        return self.router.end_session(user_id, session_id, scenario_id, audience)

    def clear_session(self, session_id):
        """清空某个会话的短时记忆与编排计数（不触发复盘、不删落库数据）。"""
        self.router.clear_session(session_id)

    # ------------------------------------------------------------------
    # 向后兼容（保留原 ScoreSystem 的用法）
    # ------------------------------------------------------------------

    def score(self, session_id, scenario_id, audience, user_response):
        """
        【向后兼容】仅评分，不生成 NPC 回应、不判阶段、不落库。
        供早期 CLI / 测试沿用。返回 ScoreResult（与 judge_agent.judge 一致）。

        说明：旧签名的 constraint 已随模型升级为 audience（训练身份），
        语义对应「王阿姨催婚」的约束位。
        """
        print(f"[主链路] 收到评分请求（仅评分），场景={scenario_id}，audience={audience}")
        scenario = self.scenario_store.get_scenario(scenario_id)
        history = self.memory.get_context(session_id)
        result = self.judge_agent.judge(scenario, audience, history, user_response)
        self.memory.add_message(session_id, "user", user_response)
        print(f"[主链路] 评分完成，总分={result.total_score}")
        return result

    def add_ai_message(self, session_id, content):
        """把 AI（NPC）的回应手动写入短时记忆。用于 CLI 的 ai: 手动注入。"""
        self.memory.add_message(session_id, "ai", content)
