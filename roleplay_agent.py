# -*- coding: utf-8 -*-
"""
roleplay_agent.py - 场景扮演Agent核心（安全对线训练场）

负责扮演场景中的 NPC，根据「本回合更新后的对峙值」推导 NPC 台词层级，
从场景的 lines 四档台词中选出一句返回。

规则路径（确定性，默认）：按对峙值 → 台词层级 → lines 轮换选句。
LLM 兜底（可选）：enable_llm_fallback=True 且已配 LLM_API_KEY 时，调 DeepSeek
生成更自然的 NPC 台词；任何失败都回退到上面的规则句，绝不中断主流程。

与旧版（王阿姨催婚）的差异：
- 旧 CONSTRAINT_GOAL / CONSTRAINT_NAME / PERSONA_PARAM_DESC（催婚执念度等）已作废删除。
- 旧 reply 返回 (ai_reply, next_persona_state) 元组；新版只返回 NPC 台词 str。
- 对峙值的「更新」由编排层 router 负责（compute_confrontation_delta），本 Agent 只负责
  依据传入的对峙值选台词，不维护任何角色动态状态。

Python 3.9 兼容：类型注解用 typing 模块（Optional 而非 X | Y）。
"""

from typing import Any, Dict, List

from contracts import tier_for


class RoleplayAgent:
    """场景扮演Agent，核心方法 reply 根据对峙值返回 NPC 的下一句台词（str）。"""

    def __init__(self, enable_llm_fallback: bool = False):
        """
        参数:
            enable_llm_fallback: 是否启用 LLM 兜底。默认 False，只走规则选台词（确定性）。
                                 True 时（且已配 LLM_API_KEY）尝试用 LLM 生成更自然的台词，
                                 失败自动回退规则句，绝不中断主流程。
        """
        self.enable_llm_fallback = enable_llm_fallback

    def reply(self, scenario: Dict[str, Any], audience: str,
              history: List[Dict[str, str]], user_response: str,
              confrontation: int) -> str:
        """
        扮演主流程：先按规则选台词（确定性兜底），开关打开时尝试 LLM 生成更自然台词。

        参数:
            scenario: 场景配置字典（含 opening 开场白、lines 四档台词、personaName 等）
            audience: 训练身份（Audience.MINOR / Audience.ADULT），本期选台词不依赖它，
                      保留参数位以对齐接口契约。
            history: 对话历史列表 [{"role": "...", "content": "..."}]（不含本回合回应）
            user_response: 用户当前回应文本
            confrontation: 本回合「更新后」的对峙值（router 已用 compute_confrontation_delta
                           算好），用它推导台词层级。

        返回:
            str: NPC 的下一句台词。
        """
        # 步骤1：开场判断——会话首句（history 为空）固定返回场景开场白
        print("[RoleplayAgent] 步骤1 - 判断是否开场首句...")
        if not history:
            opening = scenario.get("opening", "")
            print(f"[RoleplayAgent] 步骤1 - history 为空，返回开场白：{opening}")
            return opening

        # 步骤2：由对峙值推导 NPC 台词层级（contracts.tier_for 纯函数）
        print("[RoleplayAgent] 步骤2 - 由对峙值推导台词层级...")
        tier = tier_for(confrontation)
        print(f"[RoleplayAgent] 步骤2 - confrontation={confrontation} -> tier={tier}")

        # 步骤3：从场景 lines 中按历史轮数取模轮换选台词（规则句，作为 LLM 兜底的回退）
        print("[RoleplayAgent] 步骤3 - 从 lines 轮换选台词...")
        lines = scenario.get("lines", {}).get(tier, [])
        if not lines:
            # 防御兜底：契约保证 lines 含 yield/low/mid/high 四档，缺失时回退开场白
            print("[RoleplayAgent] 步骤3 - 该层级无台词，回退开场白")
            rule_reply = scenario.get("opening", "")
        else:
            index = len(history) % len(lines)
            rule_reply = lines[index]
            print(f"[RoleplayAgent] 步骤3 - tier={tier}，第 {len(history)} 轮，取第 {index} 句")

        # 步骤4：LLM 兜底（可选）——开关打开时尝试生成更自然的台词，失败回退规则句
        if self.enable_llm_fallback:
            llm_reply = self._llm_reply(scenario, history, user_response, confrontation)
            if llm_reply:
                print(f"[RoleplayAgent] 步骤4 - 采用 LLM 台词：{llm_reply}")
                return llm_reply
            print("[RoleplayAgent] 步骤4 - LLM 未命中，回退规则台词")

        # 步骤5：返回选中的台词（规则句或 LLM 句）
        print(f"[RoleplayAgent] 步骤5 - 返回NPC台词：{rule_reply}")
        return rule_reply

    def _llm_reply(self, scenario, history, user_response, confrontation):
        """调 DeepSeek 生成一句更自然的 NPC 台词；失败返回 None（回退规则句）。"""
        from llm import call_deepseek

        persona = scenario.get("personaName", "对方")
        premise = scenario.get("premise", "")
        system_prompt = (
            f"你正在扮演一个安全对线训练场景里的 NPC「{persona}」。"
            f"场景背景：{premise}"
            f"当前对峙值 {confrontation}/100（数值越高表示你越强硬、越接近冲突失控）。"
            f"请自然地说出一句符合当下对峙程度、继续施压或周旋的话，"
            f"为训练用户的「安全回应」能力服务。"
            f"只输出这一句台词本身：不要加引号、不要「NPC：」前缀、不要解释、不要动作描写。"
        )
        # 组装完整对话（history 不含本回合回应，末尾补上 user_response）
        dialogue = [f"{'对方' if m['role'] == 'ai' else '我'}：{m['content']}" for m in history]
        dialogue.append(f"我：{user_response}")
        user_prompt = "\n".join(dialogue)

        text = call_deepseek(system_prompt, user_prompt)
        if not text:
            return None
        # 去掉模型可能自带的引号 / 前缀
        text = text.strip().strip('"“”')
        for prefix in ("NPC：", "对方：", "对方:"):
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
        return text or None
