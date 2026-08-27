# -*- coding: utf-8 -*-
"""
review_agent.py - 复盘Agent核心

负责把「场景 + 约束 + 完整对话历史 + 用户画像」交给 LLM（或模拟逻辑）做会话级复盘，
返回结构化的复盘结果（总结、目标达成判定、达成度、薄弱点、画像增量）。

真实模式：config.LLM_API_KEY 不为空且安装了 openai 库时，调用 DeepSeek API。
模拟模式：其余情况，返回固定的模拟复盘结果，保证项目开箱即用。

本模块只负责生成 ReviewResult（含 profile_update 增量），
不负责把增量写入画像——那一步由路由层调用 UserProfile.update 完成。
"""

import json

import config
from contracts import ReviewResult


class ReviewAgent:
    """复盘Agent，核心方法 review 返回 ReviewResult"""

    # 每个约束的核心目标，用于构造复盘 prompt 时说明「用户整场想达成什么」。
    # 与 judge_agent.py 的 CONSTRAINT_GOAL 保持一致口径，保证评分与复盘目标统一。
    CONSTRAINT_GOAL = {
        "want_maintain": "既守住自己的边界，又不破坏与王阿姨的关系",
        "endure_but_record": "表面维持和谐，同时暗中守住底线、不被牵着走",
        "dont_care": "不被对方情绪带动，保持自己的节奏和立场",
        "want_cutoff": "清晰明确地划清界限，不给对方继续纠缠的空间",
    }

    # 约束中文名（4 档光谱，与 contracts.CONSTRAINTS 对齐）
    CONSTRAINT_NAME = {
        "want_maintain": "想维持关系",
        "endure_but_record": "能忍但记账",
        "dont_care": "无所谓",
        "want_cutoff": "想断联",
    }

    def review(self, session_id, user_id, scenario, constraint, history, profile):
        """
        复盘主流程。

        参数:
            session_id: 会话ID（本版本不参与业务逻辑，保留以对齐接口签名）
            user_id: 用户ID（同上，保留以对齐接口签名）
            scenario: 场景配置字典（含 name / description / character）
            constraint: 约束ID，例如 "want_maintain"
            history: 完整对话历史列表 [{"role": "...", "content": "..."}]
            profile: 用户画像字典（可能为空 dict）

        返回:
            ReviewResult: 会话级复盘结果
        """
        # 步骤1：获取约束中文名与核心目标
        print("[ReviewAgent] 步骤1 - 获取约束中文名与核心目标...")
        constraint_name = self.CONSTRAINT_NAME.get(constraint, "守住边界")
        goal = self.CONSTRAINT_GOAL.get(constraint, "守住自己的边界")

        # 步骤2：构造复盘 prompt
        print("[ReviewAgent] 步骤2 - 构造复盘prompt...")
        prompt = self._build_prompt(scenario, constraint_name, goal, history, profile)

        # 步骤3：调用LLM复盘（真实模式优先，失败回退模拟模式）
        print("[ReviewAgent] 步骤3 - 调用LLM复盘...")
        result = None
        raw = self._call_llm(prompt)
        if raw is not None:
            result = self._parse_result(raw)

        # 步骤4：真实模式解析失败 / 未启用真实模式，走模拟模式
        if result is None:
            print("[ReviewAgent] 步骤4 - 使用模拟复盘...")
            result = self._mock_review()
        else:
            print("[ReviewAgent] 步骤4 - 成功解析LLM复盘结果...")

        # 步骤5：校验字段并组装 ReviewResult 返回
        print(f"[ReviewAgent] 步骤5 - 返回复盘结果，达成度={result['achievement_score']}")
        return ReviewResult(
            summary=result["summary"],
            goal_achieved=result["goal_achieved"],
            achievement_score=result["achievement_score"],
            weak_points=result["weak_points"],
            profile_update=result["profile_update"],
        )

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _build_prompt(self, scenario, constraint_name, goal, history, profile):
        """把场景、约束、完整历史、画像组装成给LLM的复盘 prompt"""

        # 把完整对话历史格式化为「王阿姨：xxx / 我：xxx」；历史为空则写"（无对话）"。
        lines = []
        for msg in history:
            name = "王阿姨" if msg.get("role") == "ai" else "我"
            lines.append(f"{name}：{msg.get('content', '')}")
        history_text = "\n".join(lines) if lines else "（无对话）"

        # 用户画像可能为空 dict，做一次兜底说明，避免 prompt 里出现空值难读。
        if profile:
            profile_text = "\n".join(f"- {k}：{v}" for k, v in profile.items())
        else:
            profile_text = "（暂无画像）"

        prompt = f"""你是软技能训练的复盘教练，负责对一整场冲突对话做总结与目标达成判定。

【场景信息】
- 场景名称：{scenario.get('name')}
- 场景描述：{scenario.get('description')}
- 角色人设：{scenario.get('character')}

【约束条件】
- 约束名称：{constraint_name}
- 核心目标：{goal}

【完整对话历史】
{history_text}

【用户画像】
{profile_text}

【输出要求】
严格返回JSON，不要输出任何额外文字、解释或代码块标记。
JSON格式必须与下面完全一致：
{{
  "goal_achieved": 布尔,        // 整场是否达成该约束目标
  "achievement_score": 整数,    // 0-100，会话级达成度
  "summary": "2-3句总结，说明整场对话的走向、是否守住边界、关系氛围如何",
  "weak_points": ["薄弱点1", "薄弱点2"],  // 1~3个字符串，指出用户最需要改进的地方
  "profile_update": {{           // 画像增量，可简单，例如
    "practice_count": 1,
    "latest_weak_point": "..."
  }}
}}

说明：
- goal_achieved 表示整场对话是否达成了该约束目标（bool）。
- achievement_score 是会话级达成度（0-100 整数），60 及以上可视为达成。
- weak_points 给 1~3 个字符串。
- profile_update 是写入用户画像的增量，给出本次复盘可沉淀的一两条信息即可。
"""
        return prompt

    def _call_llm(self, prompt):
        """
        调用真实 DeepSeek API。
        返回 LLM 原始文本；未配置 / 未安装 openai / 调用失败时返回 None。
        """
        # 未配置 API Key 直接走模拟模式
        if not config.LLM_API_KEY:
            print("[ReviewAgent] 未配置 LLM_API_KEY，走模拟模式")
            return None

        # 尝试导入 openai 库
        try:
            from openai import OpenAI
        except ImportError:
            print("[ReviewAgent] 未安装 openai 库，走模拟模式（可执行 pip install openai）")
            return None

        try:
            client = OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL)
            resp = client.chat.completions.create(
                model=config.LLM_MODEL,
                messages=[
                    {"role": "system", "content": "你是软技能训练的复盘教练，只输出JSON。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,  # 降低随机性，让复盘判定更稳定
            )
            content = resp.choices[0].message.content
            print(f"[ReviewAgent] LLM 返回内容（前120字符）：{content[:120]}")
            return content
        except Exception as e:
            # 任何调用异常都打印错误并回退模拟模式，保证流程不中断
            print(f"[ReviewAgent] 调用LLM失败：{e}，走模拟模式")
            return None

    def _parse_result(self, raw):
        """
        解析 LLM 返回的 JSON 文本为复盘结果字典。
        解析失败或字段类型不符合要求时返回 None（由调用方回退模拟模式）。
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
            print(f"[ReviewAgent] 解析LLM返回JSON失败：{e}")
            return None

        # 校验顶层必须是 JSON 对象
        if not isinstance(data, dict):
            print("[ReviewAgent] LLM返回不是JSON对象，走模拟模式")
            return None

        # 校验必需字段都存在
        for key in ("goal_achieved", "achievement_score", "summary", "weak_points", "profile_update"):
            if key not in data:
                print(f"[ReviewAgent] LLM返回缺少字段 {key}，走模拟模式")
                return None

        # 校验 goal_achieved 是布尔值
        if not isinstance(data["goal_achieved"], bool):
            print("[ReviewAgent] goal_achieved 不是布尔值，走模拟模式")
            return None

        # 校验 achievement_score 是 int 且在有效范围内
        if not isinstance(data["achievement_score"], int):
            print("[ReviewAgent] achievement_score 不是整数，走模拟模式")
            return None
        if not (config.SCORE_MIN <= data["achievement_score"] <= config.SCORE_MAX):
            print("[ReviewAgent] achievement_score 超出范围，走模拟模式")
            return None

        # 校验 summary 是非空字符串
        if not isinstance(data["summary"], str) or not data["summary"].strip():
            print("[ReviewAgent] summary 不是有效字符串，走模拟模式")
            return None

        # 校验 weak_points 是字符串列表
        if not isinstance(data["weak_points"], list) or not all(
            isinstance(w, str) for w in data["weak_points"]
        ):
            print("[ReviewAgent] weak_points 不是字符串列表，走模拟模式")
            return None

        # 校验 profile_update 是字典
        if not isinstance(data["profile_update"], dict):
            print("[ReviewAgent] profile_update 不是字典，走模拟模式")
            return None

        return data

    def _mock_review(self):
        """
        模拟复盘：返回固定的模拟结果，格式与真实模式完全一致。
        achievement_score 固定 70，goal_achieved 按 (>=60) 判定为 True。
        """
        achievement_score = 70
        return {
            "goal_achieved": achievement_score >= 60,
            "achievement_score": achievement_score,
            "summary": "这是模拟复盘，配置API Key后会调用真实LLM。整体来看你基本守住了自己的边界，氛围也没有彻底闹僵。",
            "weak_points": ["表达边界时还不够明确"],
            "profile_update": {"practice_count": 1},
        }
