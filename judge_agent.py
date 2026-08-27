# -*- coding: utf-8 -*-
"""
judge_agent.py - 评分Agent核心

负责把「场景 + 约束 + 历史 + 用户回应」交给 LLM（或模拟逻辑）打分，
返回结构化的评分结果。

真实模式：config.LLM_API_KEY 不为空且安装了 openai 库时，调用 DeepSeek API。
模拟模式：其余情况，返回固定的模拟评分结果，保证项目开箱即用。
"""

import json

import config
from strategy_kb import StrategyKB


class JudgeAgent:
    """评分Agent，核心方法 judge 返回结构化评分结果"""

    # 每个约束的核心目标，用于构造评分 prompt 时说明「用户想达成什么」。
    # 该信息不在 strategy_kb 中定义，属于评分Agent的评述性文案，放在这里更合适。
    CONSTRAINT_GOAL = {
        "want_maintain": "既守住自己的边界，又不破坏与王阿姨的关系",
        "endure_but_record": "表面维持和谐，同时暗中守住底线、不被牵着走",
        "dont_care": "不被对方情绪带动，保持自己的节奏和立场",
        "want_cutoff": "清晰明确地划清界限，不给对方继续纠缠的空间",
    }

    def __init__(self):
        self.strategy_kb = StrategyKB()

    def judge(self, scenario, constraint, history, user_response):
        """
        评分主流程。

        参数:
            scenario: 场景配置字典（含 name / description / character）
            constraint: 约束ID，例如 "want_maintain"
            history: 对话历史列表 [{"role": "...", "content": "..."}]
            user_response: 用户当前回应文本

        返回:
            dict: {"total_score", "dimensions", "feedback", "suggested_strategy"}
        """
        # 步骤1：获取该约束下的评分标准
        print("[JudgeAgent] 步骤1 - 获取评分标准...")
        strategy = self.strategy_kb.get_strategy(constraint)

        # 步骤2：构造评分 prompt
        print("[JudgeAgent] 步骤2 - 构造评分prompt...")
        prompt = self._build_prompt(scenario, constraint, strategy, history, user_response)

        # 步骤3：调用LLM评分（真实模式优先，失败回退模拟模式）
        print("[JudgeAgent] 步骤3 - 调用LLM评分...")
        result = None
        raw = self._call_llm(prompt)
        if raw is not None:
            result = self._parse_result(raw)

        # 步骤4：真实模式解析失败 / 未启用真实模式，走模拟模式
        if result is None:
            print("[JudgeAgent] 步骤4 - 使用模拟评分...")
            result = self._mock_score(strategy)
        else:
            print("[JudgeAgent] 步骤4 - 成功解析LLM评分结果...")

        # 步骤5：返回结果
        print(f"[JudgeAgent] 步骤5 - 返回评分结果，总分={result['total_score']}")
        return result

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _build_prompt(self, scenario, constraint, strategy, history, user_response):
        """把场景、约束、历史、回应组装成给LLM的评分 prompt"""

        # 把对话历史格式化为「王阿姨：xxx / 我：xxx」
        lines = []
        for msg in history:
            name = "王阿姨" if msg["role"] == "ai" else "我"
            lines.append(f"{name}：{msg['content']}")
        history_text = "\n".join(lines) if lines else "（暂无对话历史）"

        # 评分维度格式化为文本
        dim_text = "\n".join(
            f"- {d['name']}（权重 {d['weight']}）：{d['description']}"
            for d in strategy["dimensions"]
        )

        # 高分/低分特征格式化为文本
        high_text = "\n".join(f"- {f}" for f in strategy["high_score_features"])
        low_text = "\n".join(f"- {f}" for f in strategy["low_score_features"])

        # 约束核心目标（按约束ID查，未知约束时给一个兜底描述）
        goal = self.CONSTRAINT_GOAL.get(constraint, "守住自己的边界")

        prompt = f"""你是软技能训练的评分专家，负责评估用户在冲突场景中的回应。

【场景信息】
- 场景名称：{scenario.get('name')}
- 场景描述：{scenario.get('description')}
- 角色人设：{scenario.get('character')}

【约束条件】
- 约束名称：{strategy['constraint_name']}
- 核心目标：{goal}

【评分标准】
高分特征（出现这些是加分项）：
{high_text}

低分特征（出现这些是扣分项）：
{low_text}

【评分维度】
{dim_text}

【对话历史】
{history_text}

【用户当前回应】
{user_response}

【输出要求】
严格返回JSON，不要输出任何额外文字、解释或代码块标记。
JSON格式必须与下面完全一致：
{{
  "total_score": 整数,  // 0-100
  "dimensions": {{       // 各维度得分，key 是维度中文名，value 是 0-100 的整数
    "维度名1": 80,
    "维度名2": 75
  }},
  "feedback": "个性化反馈，2-3句话，说明好在哪里、差在哪里、为什么这个分数",
  "suggested_strategy": "从推荐策略中选一个"
}}

其中 suggested_strategy 必须从以下推荐策略中选择一个：
{", ".join(strategy["recommended_strategies"])}
"""
        return prompt

    def _call_llm(self, prompt):
        """
        调用真实 DeepSeek API。
        返回 LLM 原始文本；未配置 / 未安装 openai / 调用失败时返回 None。
        """
        # 未配置 API Key 直接走模拟模式
        if not config.LLM_API_KEY:
            print("[JudgeAgent] 未配置 LLM_API_KEY，走模拟模式")
            return None

        # 尝试导入 openai 库
        try:
            from openai import OpenAI
        except ImportError:
            print("[JudgeAgent] 未安装 openai 库，走模拟模式（可执行 pip install openai）")
            return None

        try:
            client = OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL)
            resp = client.chat.completions.create(
                model=config.LLM_MODEL,
                messages=[
                    {"role": "system", "content": "你是软技能训练的评分专家，只输出JSON。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,  # 降低随机性，让评分更稳定
            )
            content = resp.choices[0].message.content
            print(f"[JudgeAgent] LLM 返回内容（前120字符）：{content[:120]}")
            return content
        except Exception as e:
            # 任何调用异常都打印错误并回退模拟模式，保证流程不中断
            print(f"[JudgeAgent] 调用LLM失败：{e}，走模拟模式")
            return None

    def _parse_result(self, raw):
        """
        解析 LLM 返回的 JSON 文本为评分结果字典。
        解析失败或格式不符合要求时返回 None（由调用方回退模拟模式）。
        """
        if not raw:
            return None

        # 去除可能出现的 ```json ... ``` 代码块标记
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            # 去掉可能的 "json" 前缀
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            print(f"[JudgeAgent] 解析LLM返回JSON失败：{e}")
            return None

        # 校验必需字段
        if not isinstance(data, dict):
            print("[JudgeAgent] LLM返回不是JSON对象，走模拟模式")
            return None
        for key in ("total_score", "dimensions", "feedback", "suggested_strategy"):
            if key not in data:
                print(f"[JudgeAgent] LLM返回缺少字段 {key}，走模拟模式")
                return None

        # 校验 total_score 是 int 且在有效范围内
        if not isinstance(data["total_score"], int):
            print("[JudgeAgent] total_score 不是整数，走模拟模式")
            return None
        if not (config.SCORE_MIN <= data["total_score"] <= config.SCORE_MAX):
            print("[JudgeAgent] total_score 超出范围，走模拟模式")
            return None

        return data

    def _mock_score(self, strategy):
        """
        模拟评分：返回固定的模拟结果，格式与真实模式完全一致。
        总分固定 75，各维度得分以总分为基准、按权重相对平均值浮动，
        体现「权重越高的维度得分越高」，保证模拟数据看起来合理。
        """
        mock_total = 75
        dims = strategy["dimensions"]
        # 平均权重，用于计算每个维度相对平均水平的浮动
        avg_weight = 1.0 / len(dims)

        dimensions = {}
        for d in dims:
            # 总分 ± (权重偏离平均值的幅度) * 100，权重越高分越高
            score = round(mock_total + (d["weight"] - avg_weight) * 100)
            score = max(config.SCORE_MIN, min(config.SCORE_MAX, score))
            dimensions[d["name"]] = score

        # 推荐策略默认选第一个
        suggested = strategy["recommended_strategies"][0]

        return {
            "total_score": mock_total,
            "dimensions": dimensions,
            "feedback": "这是模拟评分，配置API Key后会调用真实LLM评分。当前回应整体中规中矩，建议结合推荐策略进一步优化表达。",
            "suggested_strategy": suggested,
        }
