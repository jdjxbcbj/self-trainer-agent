# -*- coding: utf-8 -*-
"""
roleplay_agent.py - 场景扮演Agent核心

负责扮演场景中的角色（如王阿姨），根据「人设 + 静态性格参数 + 动态状态 + 用户回应」
生成该角色的下一句话，并更新角色的动态状态（情绪/耐心/被转移次数）。

真实模式：config.LLM_API_KEY 不为空且安装了 openai 库时，调用 DeepSeek API 生成自然回复。
模拟模式：其余情况，返回固定的模拟回复 + 微调后的状态，保证项目开箱即用。

与 judge_agent.py 的关系：
- judge_agent 负责「给用户回应打分」，roleplay_agent 负责「生成角色回应 + 推进角色状态」。
- 两者共用同一套 5 步模式与日志规范，便于后续维护。
"""

import json

import config


class RoleplayAgent:
    """场景扮演Agent，核心方法 reply 返回角色的下一句话和更新后的角色状态"""

    # 每个约束的核心目标，用于构造 prompt 时说明「用户想达成什么」。
    # 扮演Agent 需要理解用户的目标，才能在「合理施加压力」的同时给用户的回应留出生效空间。
    # 该文案与 judge_agent.py 的 CONSTRAINT_GOAL 保持一致，避免两处口径不一致。
    CONSTRAINT_GOAL = {
        "want_maintain": "既守住自己的边界，又不破坏与王阿姨的关系",
        "endure_but_record": "表面维持和谐，同时暗中守住底线、不被牵着走",
        "dont_care": "不被对方情绪带动，保持自己的节奏和立场",
        "want_cutoff": "清晰明确地划清界限，不给对方继续纠缠的空间",
    }

    # 约束ID -> 约束中文名，用于 prompt 中展示（避免依赖 strategy_kb，扮演Agent 只需中文名）。
    CONSTRAINT_NAME = {
        "want_maintain": "想维持关系",
        "endure_but_record": "能忍但记账",
        "dont_care": "无所谓",
        "want_cutoff": "想断联",
    }

    # 静态性格参数的数值含义说明，写入 prompt 帮助 LLM 理解人设参数。
    PERSONA_PARAM_DESC = {
        "催婚执念度": "越高越容易绕回催婚",
        "面子敏感度": "越高越在意晚辈是否'懂事'",
        "容易被转移度": "越高越容易接转移话题的茬",
        "情绪波动": "越高越容易被激怒或哄好",
    }

    def reply(self, scenario, constraint, history, user_response, persona_state):
        """
        扮演主流程：生成角色下一句话，并更新角色动态状态。

        参数:
            scenario: 场景配置字典（含 character / persona_params）
            constraint: 约束ID，例如 "want_maintain"
            history: 对话历史列表 [{"role": "...", "content": "..."}]
            user_response: 用户当前回应文本
            persona_state: 角色当前动态状态 dict（emotion / patience / deflect_count）

        返回:
            tuple: (ai_reply: str, next_persona_state: dict)
        """
        # 步骤1：获取约束与角色信息
        print("[RoleplayAgent] 步骤1 - 获取约束与角色信息...")
        character = scenario.get("character", "")
        persona_params = scenario.get("persona_params", {})

        # 步骤2：构造扮演 prompt
        print("[RoleplayAgent] 步骤2 - 构造扮演prompt...")
        prompt = self._build_prompt(
            scenario, constraint, character, persona_params,
            history, user_response, persona_state,
        )

        # 步骤3：调用LLM生成角色回复（真实模式优先，失败回退模拟模式）
        print("[RoleplayAgent] 步骤3 - 调用LLM生成角色回复...")
        result = None
        raw = self._call_llm(prompt)
        if raw is not None:
            result = self._parse_result(raw)

        # 步骤4：真实模式解析失败 / 未启用真实模式，走模拟模式
        if result is None:
            print("[RoleplayAgent] 步骤4 - 使用模拟扮演...")
            result = self._mock_reply(persona_state)
        else:
            print("[RoleplayAgent] 步骤4 - 成功解析LLM返回结果...")

        # 步骤5：校验 + 夹紧 + 返回
        print("[RoleplayAgent] 步骤5 - 返回角色回复与状态...")
        ai_reply = result["ai_reply"]
        next_persona_state = self._clamp_persona_state(result["next_persona_state"])
        return ai_reply, next_persona_state

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _build_prompt(self, scenario, constraint, character, persona_params,
                      history, user_response, persona_state):
        """把角色人设、性格参数、动态状态、约束、历史、回应组装成给LLM的扮演 prompt"""

        # 把对话历史格式化为「王阿姨：xxx / 我：xxx」
        lines = []
        for msg in history:
            name = "王阿姨" if msg["role"] == "ai" else "我"
            lines.append(f"{name}：{msg['content']}")
        history_text = "\n".join(lines) if lines else "（暂无对话历史）"

        # 静态性格参数格式化为「键（数值含义）：数值」文本
        params_lines = []
        for key, value in persona_params.items():
            desc = self.PERSONA_PARAM_DESC.get(key, "")
            params_lines.append(f"- {key}（{desc}）：{value}")
        params_text = "\n".join(params_lines) if params_lines else "（无静态性格参数）"

        # 约束核心目标（按约束ID查，未知约束时给一个兜底描述）
        constraint_name = self.CONSTRAINT_NAME.get(constraint, constraint)
        goal = self.CONSTRAINT_GOAL.get(constraint, "守住自己的边界")

        # 动态状态格式化为文本
        emotion = persona_state.get("emotion", 0.3)
        patience = persona_state.get("patience", 0.6)
        deflect_count = persona_state.get("deflect_count", 0)

        prompt = f"""你是冲突场景角色扮演者，负责扮演下面这个角色并生成它的下一句话。

【角色设定】
你要扮演场景里的角色（{character}），生成该角色对用户回应的下一句话。
要求：符合人设、语气自然、口语化，像真人长辈在说话，不要机械或书面。

【静态性格参数】
数值越大，对应倾向越强（0~1）：
{params_text}

【当前动态状态】
- emotion（情绪）：{emotion}，0~1，越高越激动/被激怒
- patience（耐心）：{patience}，0~1，越低越容易绕回催婚、越不耐烦
- deflect_count（已被转移话题次数）：{deflect_count}

【约束条件】
用户想达成的目标（{constraint_name}）：{goal}

注意：你扮演的是王阿姨，要「合理地继续施加压力」，但同时要让用户的回应有空间生效——
即用户如果接得好，你可以被安抚或被转移，不能无视用户的有效回应而机械复读催婚。

【对话历史】
{history_text}

【用户当前回应】
{user_response}

【输出要求】
严格返回JSON，不要输出任何额外文字、解释或代码块标记。
JSON格式必须与下面完全一致：
{{
  "ai_reply": "王阿姨下一句话",
  "next_persona_state": {{
    "emotion": 0~1浮点,
    "patience": 0~1浮点,
    "deflect_count": 非负整数
  }}
}}

next_persona_state 反映这一轮之后王阿姨的情绪/耐心变化：
- emotion 受「情绪波动」参数影响（情绪波动越高，用户回应越容易让情绪发生明显变化）；
- patience 随对话推进逐步下降，用户有效回应可能暂缓下降；
- deflect_count 在被用户成功转移话题时 +1，其余情况保持不变。
"""
        return prompt

    def _call_llm(self, prompt):
        """
        调用真实 DeepSeek API 生成角色回复。
        返回 LLM 原始文本；未配置 / 未安装 openai / 调用失败时返回 None。
        """
        # 未配置 API Key 直接走模拟模式
        if not config.LLM_API_KEY:
            print("[RoleplayAgent] 未配置 LLM_API_KEY，走模拟模式")
            return None

        # 尝试导入 openai 库
        try:
            from openai import OpenAI
        except ImportError:
            print("[RoleplayAgent] 未安装 openai 库，走模拟模式（可执行 pip install openai）")
            return None

        try:
            client = OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL)
            resp = client.chat.completions.create(
                model=config.LLM_MODEL,
                messages=[
                    {"role": "system", "content": "你是冲突场景的角色扮演者，只输出JSON。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,  # 提高随机性，让角色扮演更自然、更有戏剧性
            )
            content = resp.choices[0].message.content
            print(f"[RoleplayAgent] LLM 返回内容（前120字符）：{content[:120]}")
            return content
        except Exception as e:
            # 任何调用异常都打印错误并回退模拟模式，保证流程不中断
            print(f"[RoleplayAgent] 调用LLM失败：{e}，走模拟模式")
            return None

    def _parse_result(self, raw):
        """
        解析 LLM 返回的 JSON 文本为扮演结果字典。
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
            print(f"[RoleplayAgent] 解析LLM返回JSON失败：{e}")
            return None

        # 校验必需字段：ai_reply 与 next_persona_state（必须是 dict）
        if not isinstance(data, dict):
            print("[RoleplayAgent] LLM返回不是JSON对象，走模拟模式")
            return None
        if "ai_reply" not in data:
            print("[RoleplayAgent] LLM返回缺少字段 ai_reply，走模拟模式")
            return None
        if "next_persona_state" not in data:
            print("[RoleplayAgent] LLM返回缺少字段 next_persona_state，走模拟模式")
            return None
        if not isinstance(data["next_persona_state"], dict):
            print("[RoleplayAgent] next_persona_state 不是对象，走模拟模式")
            return None

        return data

    def _clamp_persona_state(self, persona_state):
        """
        夹紧并补齐角色动态状态，确保所有值落在合法范围。
        - emotion / patience 夹紧到 0~1
        - deflect_count 夹紧为非负整数
        缺失字段用安全默认值补齐，避免下游拿到非法数据。
        """
        def _clamp_float(v, default):
            try:
                return max(0.0, min(1.0, float(v)))
            except (TypeError, ValueError):
                return default

        def _clamp_int(v, default):
            try:
                return max(0, int(v))
            except (TypeError, ValueError):
                return default

        return {
            "emotion": _clamp_float(persona_state.get("emotion"), 0.3),
            "patience": _clamp_float(persona_state.get("patience"), 0.6),
            "deflect_count": _clamp_int(persona_state.get("deflect_count"), 0),
        }

    def _mock_reply(self, persona_state):
        """
        模拟扮演：返回固定的模拟回复 + 基于当前状态的微调状态。
        返回结构与真实模式完全一致，保证下游无感知切换。
        """
        # 基于传入 persona_state 微调：情绪小增、耐心略降、被转移次数不变。
        # 这样多轮对话中状态会自然演化，而不是永远停在初始值。
        next_state = {
            "emotion": persona_state.get("emotion", 0.3) + 0.05,
            "patience": persona_state.get("patience", 0.6) - 0.05,
            "deflect_count": persona_state.get("deflect_count", 0),
        }
        # 复用同一套夹紧逻辑，确保微调后仍落在合法范围。
        next_state = self._clamp_persona_state(next_state)

        print("[RoleplayAgent] 这是模拟扮演，配置API Key后会调用真实LLM")
        return {
            "ai_reply": "哎呀，你这孩子，又跟我打岔。不过我说真的，你这婚事到底怎么打算的？",
            "next_persona_state": next_state,
        }
