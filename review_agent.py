# -*- coding: utf-8 -*-
"""
review_agent.py - 复盘 Agent 核心

负责在会话终局时，根据编排层（router）传入的终局信息做确定性复盘：
goal_achieved / achievement_score / summary / weak_points / profile_update。

规则复盘（确定性，默认）：终局信息（final_stage / confrontation / crit_count）由 router 传入，
review 据此按 contracts §3.4 冻结规则计算，判定可复现、零延迟。
LLM 兜底（可选）：enable_llm_fallback=True 且已配 LLM_API_KEY 时，仅 summary 文本改用
DeepSeek 生成更个性化总结；判定数据（goal / 达成度 / weak_points / profile_update）不变，
且 LLM 失败自动回退模板总结，绝不中断主流程。

- 旧版「王阿姨催婚」的 CONSTRAINT_GOAL / CONSTRAINT_NAME 作废删除，
  旧版 _build_prompt / _call_llm / _parse_result / _mock_review 那套 LLM 逻辑一并删除。

数据类一律从 contracts 导入，不自己定义。
Python 3.9 兼容：类型注解用 typing 模块（不用 X | Y）。
"""

from typing import Any, Dict, List

import config
from contracts import CRITS_TO_PASS_DEFAULT, ReviewResult, Stage


class ReviewAgent:
    """复盘 Agent，核心方法 review 返回 ReviewResult（规则判定，LLM 兜底可选）"""

    def __init__(self, enable_llm_fallback: bool = False):
        """
        初始化复盘 Agent。

        参数:
            enable_llm_fallback: 是否启用 LLM 兜底生成更个性化总结。
                默认 False（纯规则复盘）；True 时（且已配 LLM_API_KEY）仅 summary 文本
                用 LLM 生成，判定数据仍走规则，失败自动回退模板总结。
        """
        self.enable_llm_fallback = enable_llm_fallback

    def review(
        self,
        session_id: str,
        user_id: str,
        scenario: Dict[str, Any],
        audience: str,
        history: List[Dict[str, str]],
        profile: Dict[str, Any],
        final_stage: str,
        confrontation: int,
        crit_count: int,
    ) -> ReviewResult:
        """
        复盘主流程（规则判定为主，LLM 兜底可选，仅影响 summary 文本）。

        参数:
            session_id: 会话ID（本期不参与业务逻辑，保留以对齐接口签名）
            user_id: 用户ID（本期不参与业务逻辑，保留以对齐接口签名）
            scenario: 场景配置字典（含 title / critsToPass 等）
            audience: 训练身份（本期不参与业务逻辑，保留以对齐接口签名）
            history: 完整对话历史列表（规则判定不依赖；LLM 兜底总结时作为上下文）
            profile: 用户画像字典（可能为空 dict，用于累加 practice_count）
            final_stage: 终局阶段（contracts.Stage 常量之一，由 router 传入）
            confrontation: 最终对峙值（int，0~100）
            crit_count: 累计暴击数（int）

        返回:
            ReviewResult: 会话级复盘结果

        判定规则（§3.4 冻结值，不得各写各的）：
            goal_achieved = (final_stage == Stage.RESOLVE)
            achievement_score 分档：优秀 90 / 及格 65 / 失控 30 / 到时 50，
            并 clamp 到 [SCORE_MIN, SCORE_MAX]。
        """
        # 步骤1：读取场景通关所需暴击数与场景名（critsToPass 来自 SDB，缺省回退 contracts 默认值）
        crits_to_pass = scenario.get("critsToPass", CRITS_TO_PASS_DEFAULT)
        scenario_title = scenario.get("title", "未命名场景")
        print(f"[ReviewAgent] 步骤1 - 读取场景「{scenario_title}」通关所需暴击数={crits_to_pass}")

        # 步骤2：按终局判定 goal_achieved 与 achievement_score（§3.4 分档）
        goal_achieved = (final_stage == Stage.RESOLVE)
        if final_stage == Stage.RESOLVE:
            if crit_count >= crits_to_pass:
                # 优秀通关：通关且暴击数达标
                outcome = "优秀通关"
                achievement_score = 90
            else:
                # 及格通关：压平但对峙值先到，暴击没凑够 → 降档
                outcome = "及格通关"
                achievement_score = 65
        elif final_stage == Stage.DEADLOCK:
            # 失控：对峙值 ≥ 85 或命中暴力红线
            outcome = "失控"
            achievement_score = 30
        elif final_stage == Stage.END:
            # 到时：回合耗尽仍未 resolve/deadlock
            outcome = "回合耗尽"
            achievement_score = 50
        else:
            # 兜底：非终局阶段（OPENING/PRESSURE 等），理论上不会走到，按最低分处理
            outcome = "未明确终局"
            achievement_score = config.SCORE_MIN

        # 夹到 [SCORE_MIN, SCORE_MAX]，保证返回值一定落在合法区间
        achievement_score = max(config.SCORE_MIN, min(config.SCORE_MAX, achievement_score))
        print(
            f"[ReviewAgent] 步骤2 - 终局={final_stage}，goal_achieved={goal_achieved}，"
            f"达成度={achievement_score}"
        )

        # 步骤3：按终局推导薄弱点（1~3 条字符串）
        if final_stage == Stage.RESOLVE:
            if crit_count >= crits_to_pass:
                # 已优秀：给 1 条进阶建议
                weak_points = ["可再补齐取证/求助环节"]
            else:
                # 及格：压平但暴击没凑够，点出还差几次
                missing = crits_to_pass - crit_count
                weak_points = [f"还差 {missing} 次暴击即优秀"]
        elif final_stage == Stage.DEADLOCK:
            weak_points = ["对峙值失控，注意避免顶撞/命中红线"]
        elif final_stage == Stage.END:
            weak_points = ["回合耗尽，未压平对峙值"]
        else:
            weak_points = ["对话未走到明确终局"]
        print(f"[ReviewAgent] 步骤3 - 薄弱点={weak_points}")

        # 步骤4：拼装模板化总结（确定性）；开关打开时用 LLM 生成更个性化总结，失败回退
        summary = (
            f"整场对话对峙值从 50 走到 {confrontation}，终局为{outcome}，"
            f"共打出 {crit_count} 次暴击。"
        )
        if self.enable_llm_fallback:
            llm_summary = self._llm_summary(scenario, history, outcome, achievement_score, crit_count)
            if llm_summary:
                summary = llm_summary
                print(f"[ReviewAgent] 步骤4 - 采用 LLM 总结：{summary}")
            else:
                print("[ReviewAgent] 步骤4 - LLM 未命中，回退模板总结")
        print(f"[ReviewAgent] 步骤4 - 总结：{summary}")

        # 步骤5：计算画像增量（practice_count 在原有基础上累加，非覆盖）
        profile = profile or {}
        practice_count = profile.get("practice_count", 0) + 1
        profile_update = {
            "practice_count": practice_count,
            "latest_weak_point": weak_points[0],
        }
        print(f"[ReviewAgent] 步骤5 - 画像增量={profile_update}")

        # 步骤6：组装并返回 ReviewResult
        print(f"[ReviewAgent] 步骤6 - 返回复盘结果，达成度={achievement_score}")
        return ReviewResult(
            summary=summary,
            goal_achieved=goal_achieved,
            achievement_score=achievement_score,
            weak_points=weak_points,
            profile_update=profile_update,
        )

    def _llm_summary(self, scenario, history, outcome, achievement_score, crit_count):
        """调 DeepSeek 生成更个性化的复盘总结；失败返回 None（回退模板总结）。"""
        from llm import call_deepseek

        title = scenario.get("title", "未命名场景")
        system_prompt = (
            f"你是「安全对线训练场」的一名教练。请根据这场关于「{title}」的训练对话，"
            f"用 2~3 句话客观总结用户的表现：先点出做得好的地方，再指出最需要改进的一点。"
            f"参考信息：终局={outcome}，达成度={achievement_score}/100，打出 {crit_count} 次暴击。"
            f"语气客观、不评判对错、不重复这些数据本身。只输出总结正文，不要标题、不要列表符号。"
        )
        user_prompt = "\n".join(
            [f"{'NPC' if m['role'] == 'ai' else '我'}：{m['content']}" for m in history]
        )
        return call_deepseek(system_prompt, user_prompt)
