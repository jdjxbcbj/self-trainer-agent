# -*- coding: utf-8 -*-
"""
judge_agent.py - 评分 Agent（确定性打分）

负责把「场景 + 用户回应」交给本地规则库（GSB + RSB）做确定性打分，
返回结构化的评分结果。本期不调 LLM（见 PLAN.md §9 决策第 1 项）。

打分规则（见 PLAN.md §3.4 判定参数）：
1. 红线一票否决：命中 RSB 红线 → total_score = RED_LINE_CAP（30），记入 red_line_hits，
   不叠加普通扣分。
2. 维度匹配：命中 GSB 正向维度 +weight、负向维度 -weight，总分 clamp 到 [0,100]。
3. 暴击判定：total_score ≥ CRIT_THRESHOLD 且无红线 → 暴击（由 is_crit 判定）。

LLM 兜底本期不实现，只留 enable_llm_fallback 参数位（将来接入语义兜底）。
"""

import config
from contracts import ScoreResult, RED_LINE_CAP, is_crit
from strategy_kb import StrategyKB


class JudgeAgent:
    """评分 Agent，核心方法 judge 返回结构化评分结果"""

    def __init__(self, enable_llm_fallback=False):
        self.strategy_kb = StrategyKB()
        # LLM 兜底开关：本期不实现，仅保留参数位（见 PLAN.md §9 决策第 1 项）。
        self.enable_llm_fallback = enable_llm_fallback

    def judge(self, scenario, audience, history, user_response):
        """
        评分主流程（确定性打分）。

        参数:
            scenario: 场景配置字典（含 hint 等）
            audience: 训练身份（本期评分未成年/成人共用，此参数预留未来分流）
            history: 对话历史列表（本期关键词匹配只看当前回应，此参数预留）
            user_response: 用户当前回应文本

        返回:
            ScoreResult: total_score / dimensions / red_line_hits / feedback / suggested_strategy
        """
        # 步骤1：红线检测（一票否决，优先级最高）
        print("[JudgeAgent] 步骤1 - 红线检测...")
        red_line = self.strategy_kb.detect_red_line(user_response)
        if red_line is not None:
            return self._violation_score(red_line)

        # 步骤2：维度匹配
        print("[JudgeAgent] 步骤2 - 维度匹配...")
        hits, penalties = self.strategy_kb.match_dimensions(user_response)

        # 步骤3：计算总分（命中正向 +权重、负向 -权重，clamp 到 [0,100]）
        print("[JudgeAgent] 步骤3 - 计算总分...")
        total = sum(d["weight"] for d in hits) + sum(d["weight"] for d in penalties)
        total = max(config.SCORE_MIN, min(config.SCORE_MAX, total))

        # 步骤4：判定暴击（total_score ≥ 85 且无红线）
        crit = is_crit(total, [])

        # 步骤5：组装分维度得分（7 个正向维度：命中 100，未命中 0）
        positive = self.strategy_kb.get_dimensions()["positive"]
        hit_ids = {d["id"] for d in hits}
        dimensions = {d["name"]: (100 if d["id"] in hit_ids else 0) for d in positive}

        # 步骤6：生成反馈 + 推荐话术
        feedback = self._build_feedback(crit, hits, penalties)
        suggested = scenario.get("hint", "")

        print(f"[JudgeAgent] 步骤7 - 返回评分结果，总分={total}，暴击={crit}")
        return ScoreResult(
            total_score=total,
            dimensions=dimensions,
            red_line_hits=[],
            feedback=feedback,
            suggested_strategy=suggested,
        )

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _violation_score(self, red_line):
        """命中红线时的一票否决评分（total_score 取 RED_LINE_CAP，不叠加普通扣分）。"""
        print(f"[JudgeAgent] 命中红线 {red_line['id']}，一票否决")
        return ScoreResult(
            total_score=RED_LINE_CAP,
            dimensions={},   # 命中红线不逐项打维度分
            red_line_hits=[red_line["id"]],
            feedback=f"{red_line['message']} 替代话术：{red_line['alternative']}",
            suggested_strategy=red_line["alternative"],
        )

    def _build_feedback(self, crit, hits, penalties):
        """按规则生成反馈文案（替代原 LLM 生成的个性化反馈）。"""
        if crit:
            names = "、".join(d["name"] for d in hits)
            return f"精准暴击：命中 {len(hits)} 个维度（{names}），边界、冷静、合规、止损与取证意识形成闭环。"
        parts = []
        if penalties:
            names = "、".join(d["name"] for d in penalties)
            parts.append(f"踩中负向维度「{names}」")
        parts.append("没有违规，但建议补上：明确边界 + 规则渠道 + 记录/求助。")
        return "普通回应：" + "；".join(parts)
