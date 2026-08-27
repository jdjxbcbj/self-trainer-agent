# -*- coding: utf-8 -*-
"""
router.py - 编排路由 Router

safe-trainer 的编排主控。它只负责按既定流程「调度」各子 Agent，
自己不亲自打分、不生成对话、不写画像逻辑（写画像通过调用 UserProfile 完成）。

一条链路分工：
  打分        -> JudgeAgent.judge
  王阿姨回应   -> RoleplayAgent.reply（同时返回下一轮 persona 状态）
  实时提示     -> TeachingAgent.get_hint
  会话复盘     -> ReviewAgent.review
  画像读写     -> UserProfile.get / update
  记忆读写     -> ConversationMemory
"""

from contracts import Stage, TurnResult, ReviewResult, ScoreResult
from scenario_store import ScenarioStore
from strategy_kb import StrategyKB
from memory import ConversationMemory
from profile import UserProfile
from judge_agent import JudgeAgent
from roleplay_agent import RoleplayAgent
from teaching_agent import TeachingAgent
from review_agent import ReviewAgent


class Router:
    """编排主控：串联各 Agent 完成一次用户回合 / 一次会话复盘"""

    def __init__(self):
        """
        初始化并持有全部子 Agent 组件。

        为什么在 __init__ 就全部实例化：Router 是长生命周期的主控，
        一次初始化后反复调度，避免每个回合重复 new 对象（各 Agent 内部
        可能持有 DB 连接、知识库等有初始化成本的状态）。
        """
        self.scenario_store = ScenarioStore()
        self.strategy_kb = StrategyKB()
        self.memory = ConversationMemory()
        self.profile = UserProfile()
        self.judge_agent = JudgeAgent()
        self.roleplay_agent = RoleplayAgent()
        self.teaching_agent = TeachingAgent()
        self.review_agent = ReviewAgent()
        print("[Router] 编排路由初始化完成")

    def handle_turn(self, user_id, session_id, scenario_id, constraint, user_response) -> TurnResult:
        """
        处理一次用户回合：调度各 Agent，汇总成 TurnResult。

        参数:
            user_id: 用户ID（当前回合流程未直接使用，但为接口一致保留）
            session_id: 会话ID
            scenario_id: 场景ID
            constraint: 约束ID
            user_response: 用户本轮回应文本

        返回:
            TurnResult: 评分 + 王阿姨回应 + 下一阶段 + 下一 persona 状态 + 实时提示
        """
        print(f"[Router] 开始处理用户回合：session={session_id}，scenario={scenario_id}")

        # 步骤1：取场景配置（含人设参数与初始 persona 状态）
        scenario = self.scenario_store.get_scenario(scenario_id)

        # 步骤2：取当前会话的上下文快照。
        # 为什么先取历史再写新消息：本轮评分/生成需要的是「用户回应之前」的历史，
        # 若先 add_message 会把本轮回应也喂进上下文，造成信息泄漏。
        history = self.memory.get_context(session_id)
        persona_state = self.memory.get_persona_state(session_id)
        stage = self.memory.get_stage(session_id)

        # 步骤3：交给评分 Agent 打分（Router 不自己评分）。
        # judge 返回 dict（评分模块 v1 的既有实现），这里在编排边界统一
        # 转成契约里的 ScoreResult，保证下游（TurnResult/CLI）拿到的是强类型对象，
        # 而不是各模块各自返回的散装结构。dict 键与 ScoreResult 字段一一对应，
        # 因此用 **dict 展开直接构造即可。
        score = ScoreResult(**self.judge_agent.judge(scenario, constraint, history, user_response))

        # 步骤4：交给扮演 Agent 生成王阿姨回应，并更新下一轮 persona 状态。
        # 为什么 persona 状态由扮演 Agent 维护：情绪/耐心/被转移次数是角色的
        # 动态行为参数，只有扮演 Agent 最清楚该怎么演化，Router 只负责透传。
        ai_reply, next_persona_state = self.roleplay_agent.reply(
            scenario, constraint, history, user_response, persona_state
        )

        # 步骤5：交给教学 Agent 生成实时提示（规则优先，不调 LLM）
        hint = self.teaching_agent.get_hint(scenario, constraint, stage, history)

        # 步骤6：规则判定下一阶段。
        # 为什么用规则而非 LLM：阶段是编排层状态机的硬边界，要求确定性、
        # 零延迟、可预测，交给 LLM 反而引入波动与成本。规则按优先级短路：
        if next_persona_state["emotion"] >= 0.8:
            # 情绪失控：王阿姨被彻底激怒，对话僵住，优先于分数判定
            next_stage = Stage.DEADLOCK
        elif score.total_score >= 80:
            # 本轮高分解围：用户成功划界，冲突收敛，进入收尾
            next_stage = Stage.RESOLVE
        else:
            # 绕回催婚或升级施压，本质上都仍处于「施压」阶段
            next_stage = Stage.PRESSURE

        print(f"[Router] 阶段判定完成：{next_stage}")

        # 步骤7：把本轮结果写回记忆（先 user 后 ai，保持时序；顺序不可颠倒）
        self.memory.add_message(session_id, "user", user_response)
        self.memory.add_message(session_id, "ai", ai_reply)
        self.memory.set_persona_state(session_id, next_persona_state)
        self.memory.set_stage(session_id, next_stage)

        # 步骤8：组装并返回完整回合结果
        return TurnResult(
            score=score,
            ai_reply=ai_reply,
            next_persona_state=next_persona_state,
            next_stage=next_stage,
            teaching_hint=hint,
        )

    def end_session(self, user_id, session_id, scenario_id, constraint) -> ReviewResult:
        """
        会话结束，触发复盘：调度复盘 Agent 并写回用户画像。

        返回:
            ReviewResult: 会话总结 + 是否达成目标 + 画像增量等
        """
        print(f"[Router] 开始结束会话：session={session_id}，scenario={scenario_id}")

        # 步骤1：取场景 / 历史 / 用户画像快照
        scenario = self.scenario_store.get_scenario(scenario_id)
        history = self.memory.get_context(session_id)
        profile = self.profile.get(user_id)

        # 步骤2：交给复盘 Agent 生成复盘结果
        review = self.review_agent.review(
            session_id, user_id, scenario, constraint, history, profile
        )

        # 步骤3：把复盘产出的画像增量写回（Router 不自写画像逻辑，只调 UserProfile）
        self.profile.update(user_id, review.profile_update)

        # 步骤4：打印复盘结论
        print(f"[Router] 复盘完成，goal_achieved={review.goal_achieved}")

        # 步骤5：返回复盘结果
        return review
