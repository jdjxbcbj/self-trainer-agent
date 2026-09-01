# -*- coding: utf-8 -*-
"""
roleplay_agent.py - 场景扮演Agent核心（安全对线训练场）

负责扮演场景中的 NPC，根据「本回合更新后的对峙值」推导 NPC 台词层级，
从场景的 lines 四档台词中选出一句返回。

与旧版（王阿姨催婚）的差异：
- 旧 CONSTRAINT_GOAL / CONSTRAINT_NAME / PERSONA_PARAM_DESC（催婚执念度等）已作废删除。
- 旧 reply 返回 (ai_reply, next_persona_state) 元组；新版只返回 NPC 台词 str。
- 对峙值的「更新」由编排层 router 负责（compute_confrontation_delta），本 Agent 只负责
  依据传入的对峙值选台词，不维护任何角色动态状态。

与 judge_agent.py 的关系：
- judge_agent 负责「给用户回应打分」，roleplay_agent 负责「根据对峙值选 NPC 台词」。
- 两者同为规则判定的确定性模块，本期不调 LLM。

Python 3.9 兼容：类型注解用 typing 模块（Optional 而非 X | Y）。
"""

from typing import Any, Dict, List

from contracts import tier_for


class RoleplayAgent:
    """场景扮演Agent，核心方法 reply 根据对峙值返回 NPC 的下一句台词（str）。"""

    def __init__(self, enable_llm_fallback: bool = False):
        """
        参数:
            enable_llm_fallback: 是否启用 LLM 兜底。本期固定为 False，只走规则选台词，
                                 与 judge_agent 保持一致（确定性、不调 LLM）。
                                 （将来接入真实 LLM 生成更自然的台词时，可在此开关。）
        """
        self.enable_llm_fallback = enable_llm_fallback

    def reply(self, scenario: Dict[str, Any], audience: str,
              history: List[Dict[str, str]], user_response: str,
              confrontation: int) -> str:
        """
        扮演主流程：根据对峙值推导 NPC 台词层级，并选出一句台词返回。

        参数:
            scenario: 场景配置字典（含 opening 开场白、lines 四档台词、personaName 等）
            audience: 训练身份（Audience.MINOR / Audience.ADULT），本期选台词不依赖它，
                      保留参数位以对齐接口契约。
            history: 对话历史列表 [{"role": "...", "content": "..."}]
            user_response: 用户当前回应文本（本期选台词不依赖它，保留参数位）
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

        # 步骤3：从场景 lines 中按历史轮数取模轮换选台词（避免每轮同一句）
        print("[RoleplayAgent] 步骤3 - 从 lines 轮换选台词...")
        lines = scenario.get("lines", {}).get(tier, [])
        if not lines:
            # 防御兜底：契约保证 lines 含 yield/low/mid/high 四档，缺失时回退开场白
            print("[RoleplayAgent] 步骤3 - 该层级无台词，回退开场白")
            return scenario.get("opening", "")
        index = len(history) % len(lines)
        ai_reply = lines[index]
        print(f"[RoleplayAgent] 步骤3 - tier={tier}，第 {len(history)} 轮，取第 {index} 句")

        # 步骤4：返回选中的台词
        print(f"[RoleplayAgent] 步骤4 - 返回NPC台词：{ai_reply}")
        return ai_reply
