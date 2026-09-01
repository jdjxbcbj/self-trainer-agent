# -*- coding: utf-8 -*-
"""
router.py - 编排路由 Router（安全对线训练场）

编排主控：按既定流程「调度」各子 Agent，自己不亲自打分、不生成台词、不写复盘逻辑。

一条链路分工：
  评分        -> JudgeAgent.judge（GSB 维度 + RSB 红线）
  NPC 台词    -> RoleplayAgent.reply（按对峙值层级选台词）
  实时提示    -> TeachingAgent.get_hint
  教学卡      -> TeachingAgent.get_card（进场景时预生成）
  会话复盘    -> ReviewAgent.review
  短时记忆    -> SessionMemory（会话消息 + 对峙值 + 阶段）
  持久化      -> Storage（sessions / turns / users）

对峙值状态机（§3.4 冻结值）：由 router 统一用 compute_confrontation_delta / is_crit
算对峙值涨落与终局，各子 Agent 只读 contracts 常量、不各写各的。

编排层内部还持有两个「会话级计数」（暴击数、回合数）：它们只在终局判定与复盘时
被 router 使用，不交给任何子 Agent，因此不放进 SessionMemory（那是共享短时记忆），
而是由 router 自建 dict 维护，职责边界更清晰。
"""

from contracts import (
    Stage,
    TurnResult,
    ReviewResult,
    is_crit,
    compute_confrontation_delta,
    CONFRONTATION_MIN,
    CONFRONTATION_MAX,
    CRITS_TO_PASS_DEFAULT,
    RESOLVE_CONFRONT,
    DEADLOCK_CONFRONT,
    ROUND_LIMIT,
)
from scenario_store import ScenarioStore
from memory import SessionMemory
from storage import Storage
from judge_agent import JudgeAgent
from roleplay_agent import RoleplayAgent
from teaching_agent import TeachingAgent
from review_agent import ReviewAgent


class Router:
    """编排主控：串联各 Agent 完成会话开局 / 一次用户回合 / 一次会话复盘"""

    def __init__(self):
        """
        初始化并持有全部子 Agent 组件。

        为什么在 __init__ 就全部实例化：Router 是长生命周期的主控，
        一次初始化后反复调度，避免每个回合重复 new 对象（各 Agent 内部
        可能持有 DB 连接、知识库等有初始化成本的状态）。
        """
        self.scenario_store = ScenarioStore()
        self.memory = SessionMemory()
        self.storage = Storage()
        self.judge_agent = JudgeAgent()
        self.roleplay_agent = RoleplayAgent()
        self.teaching_agent = TeachingAgent()
        self.review_agent = ReviewAgent()
        # 会话级编排计数（只归 router 使用，见模块 docstring）
        self._crit_counts = {}    # session_id -> 累计暴击数
        self._turn_counts = {}    # session_id -> 累计回合数
        print("[Router] 编排路由初始化完成")

    # ------------------------------------------------------------------
    # 会话开局
    # ------------------------------------------------------------------

    def start_session(self, user_id, session_id, scenario_id, audience):
        """
        开新会话：落库（upsert_user + create_session）、重置计数、由 NPC 起头（开场白）。

        参数:
            user_id: 用户ID
            session_id: 会话ID
            scenario_id: 场景ID
            audience: 训练身份（Audience.MINOR / Audience.ADULT）

        返回:
            tuple: (opening, teaching_card)
                opening       str          NPC 开场白（已写入短时记忆）
                teaching_card TeachingCard 进场景预生成的教学卡
        """
        print(f"[Router] 开始新会话：session={session_id}，scenario={scenario_id}，audience={audience}")

        # 步骤1：取场景配置（含开场白 / critsToPass / lines 等）
        scenario = self.scenario_store.get_scenario(scenario_id)

        # 步骤2：数据层落库——先 upsert 用户（sessions 外键依赖 users），再建会话行
        self.storage.upsert_user(user_id, audience)
        self.storage.create_session(session_id, user_id, scenario_id, audience)

        # 步骤3：重置会话级编排计数（暴击数 / 回合数归零）
        self._crit_counts[session_id] = 0
        self._turn_counts[session_id] = 0

        # 步骤4：NPC 起头——开场白写入短时记忆，作为该会话的第一条 AI 消息
        # 为什么要把开场白落进 memory：这样首个 handle_turn 时 history 非空，
        # roleplay 才会按对峙值层级选台词（而非再次返回开场白），评委也能拿到完整上下文。
        opening = scenario.get("opening", "")
        self.memory.add_message(session_id, "ai", opening)

        # 步骤5：进场景时预生成教学卡（规则生成，不调 LLM）
        card = self.teaching_agent.get_card(scenario_id, audience)

        print(f"[Router] 会话开局完成，NPC 开场白已就位")
        return opening, card

    # ------------------------------------------------------------------
    # 单回合
    # ------------------------------------------------------------------

    def handle_turn(self, user_id, session_id, scenario_id, audience, user_response) -> TurnResult:
        """
        处理一次用户回合：调度各 Agent，汇总成 TurnResult。

        参数:
            user_id: 用户ID（本回合流程不直接使用，为接口一致保留）
            session_id: 会话ID
            scenario_id: 场景ID
            audience: 训练身份（Audience.MINOR / Audience.ADULT）
            user_response: 用户本轮回应文本

        返回:
            TurnResult: 评分 + NPC 回应 + 下一轮对峙值 + 下一阶段 + 实时提示
        """
        print(f"[Router] 开始处理用户回合：session={session_id}，scenario={scenario_id}")

        # 步骤1：取场景配置
        scenario = self.scenario_store.get_scenario(scenario_id)

        # 步骤2：取当前会话上下文快照（历史 + 对峙值）。
        # 为什么先取历史再写新消息：本轮评分/生成需要的是「用户回应之前」的历史，
        # 若先 add_message 会把本轮回应也喂进上下文，造成信息泄漏。
        history = self.memory.get_context(session_id)
        current_confrontation = self.memory.get_confrontation(session_id)

        # 步骤3：交给评分 Agent 打分（Router 不自己评分）
        score = self.judge_agent.judge(scenario, audience, history, user_response)

        # 步骤4：按本回合表现计算对峙值涨落（§3.4 冻结规则，与当前对峙值无关）
        delta = compute_confrontation_delta(score.total_score, score.red_line_hits)
        next_confrontation = max(
            CONFRONTATION_MIN, min(CONFRONTATION_MAX, current_confrontation + delta)
        )

        # 步骤5：更新会话级计数（暴击数 / 回合数）
        crit_count = self._crit_counts.get(session_id, 0)
        if is_crit(score.total_score, score.red_line_hits):
            crit_count += 1
            self._crit_counts[session_id] = crit_count
        turn_count = self._turn_counts.get(session_id, 0) + 1
        self._turn_counts[session_id] = turn_count

        # 步骤6：终局判定（对峙值状态机 + 红线，见 §3.4）
        crits_to_pass = scenario.get("critsToPass", CRITS_TO_PASS_DEFAULT)
        next_stage = self._determine_next_stage(
            next_confrontation, score.red_line_hits, crit_count, turn_count, crits_to_pass
        )

        # 步骤7：交给扮演 Agent 生成 NPC 台词（依据「本回合更新后」的对峙值）
        ai_reply = self.roleplay_agent.reply(
            scenario, audience, history, user_response, next_confrontation
        )

        # 步骤8：交给教学 Agent 生成实时提示（规则优先，不调 LLM）
        hint = self.teaching_agent.get_hint(scenario, audience, next_stage, history)

        print(f"[Router] 阶段判定完成：{next_stage}（对峙值={next_confrontation}，暴击={crit_count}）")

        # 步骤9：把本轮结果写回记忆（先 user 后 ai，保持时序；顺序不可颠倒）
        self.memory.add_message(session_id, "user", user_response)
        self.memory.add_message(session_id, "ai", ai_reply)
        self.memory.set_confrontation(session_id, next_confrontation)
        self.memory.set_stage(session_id, next_stage)

        # 步骤10：【数据层】持久化本轮到 turns 表（只追加，不改 sessions）
        self.storage.write_turn(session_id, {
            "turn_index": turn_count,
            "user_response": user_response,
            "ai_reply": ai_reply,
            "score_total": score.total_score,
            "score_dimensions": score.dimensions,
            "red_line_hits": score.red_line_hits,
            "confrontation_value": next_confrontation,
            # persona_state 是旧「王阿姨催婚」模型的角色动态状态残留列；
            # 新模型的对峙值已由 confrontation_value 列承载，此处写空字典占位。
            "persona_state": {},
            "teaching_hint": hint,
            "next_stage": next_stage,
        })

        # 步骤11：组装并返回完整回合结果
        return TurnResult(
            score=score,
            ai_reply=ai_reply,
            confrontation_value=next_confrontation,
            next_stage=next_stage,
            teaching_hint=hint,
        )

    # ------------------------------------------------------------------
    # 会话复盘
    # ------------------------------------------------------------------

    def end_session(self, user_id, session_id, scenario_id, audience) -> ReviewResult:
        """
        会话结束，触发复盘：调度复盘 Agent，落库 sessions + 更新用户画像。

        返回:
            ReviewResult: 会话总结 + 是否通关 + 达成度 + 画像增量
        """
        print(f"[Router] 开始结束会话：session={session_id}，scenario={scenario_id}")

        # 步骤1：取场景 / 历史 / 用户画像 / 终局信息快照
        scenario = self.scenario_store.get_scenario(scenario_id)
        history = self.memory.get_context(session_id)
        profile = self.storage.get_profile(user_id)
        final_stage = self.memory.get_stage(session_id)
        confrontation = self.memory.get_confrontation(session_id)
        crit_count = self._crit_counts.get(session_id, 0)

        # 步骤2：交给复盘 Agent 生成复盘结果（终局信息由 router 传入）
        review = self.review_agent.review(
            session_id, user_id, scenario, audience, history, profile,
            final_stage, confrontation, crit_count,
        )

        # 步骤3：【数据层】sessions 标 ended + 写 final_stage/achievement/goal
        self.storage.end_session(session_id, review, final_stage)

        # 步骤4：【数据层】把复盘产出的画像增量写回 users.profile_json
        self.storage.update_profile(user_id, review.profile_update)

        print(f"[Router] 复盘完成，goal_achieved={review.goal_achieved}")
        return review

    # ------------------------------------------------------------------
    # 清理（开发期便利）
    # ------------------------------------------------------------------

    def clear_session(self, session_id):
        """清空某会话的短时记忆与编排计数（不触发复盘，不删落库数据）。"""
        self.memory.clear(session_id)
        self._crit_counts.pop(session_id, None)
        self._turn_counts.pop(session_id, None)
        print(f"[Router] 已清空会话 {session_id} 的短时记忆与计数")

    # ------------------------------------------------------------------
    # 内部：终局判定（§3.4 冻结规则）
    # ------------------------------------------------------------------

    @staticmethod
    def _determine_next_stage(confrontation, red_line_hits, crit_count, turn_count, crits_to_pass):
        """
        按 §3.4 冻结规则判定下一阶段（确定性，非 LLM）。

        优先级顺序（与 verify_state_machine 一致）：
        1. 失控 deadlock：对峙值 ≥ DEADLOCK_CONFRONT，或命中 r-violence（暴力红线）
        2. 优秀 resolve：暴击数 ≥ critsToPass 且 对峙值 ≤ RESOLVE_CONFRONT
        3. 及格 resolve：对峙值 ≤ 0 且 暴击数 < critsToPass
        4. 到时 end：回合数 ≥ ROUND_LIMIT
        5. 否则继续 pressure
        """
        if "r-violence" in red_line_hits or confrontation >= DEADLOCK_CONFRONT:
            return Stage.DEADLOCK
        if crit_count >= crits_to_pass and confrontation <= RESOLVE_CONFRONT:
            return Stage.RESOLVE
        if confrontation <= CONFRONTATION_MIN and crit_count < crits_to_pass:
            return Stage.RESOLVE
        if turn_count >= ROUND_LIMIT:
            return Stage.END
        return Stage.PRESSURE
