# -*- coding: utf-8 -*-
"""
teaching_agent.py - 教学 Agent 核心（安全对线训练场）

负责在进场景时预生成一张教学卡（get_card），以及在回合中给出实时合规提示（get_hint）。

与旧版（王阿姨催婚）的差异：
- 旧 get_card 依赖 strategy_kb.get_strategy(constraint) 按「催婚约束」选招式；
  新版默认招式名直接取场景第一个能力点 scenario["criteria"][0]（如「表达边界」）。
- 旧 KnowledgeBase().get_method(constraint, strategy_name) 按约束取方法论；
  新版改为 get_method(scenario_id, 招式名)，按场景取方法论五要素。
- 旧 TeachingCard 字段 constraint → 新版 scenario_id。
- get_hint 的第二参数由 constraint 改为 audience（本期保留参数位，不分流内容）。

设计原则：
- 规则优先：全部规则 / 静态生成，不调 LLM，避免每轮延迟。
- 数据类一律从 contracts 导入，不自己定义。

Python 3.9 兼容：类型注解用 typing 模块风格（避免 X | Y 联合写法）。
"""

from contracts import TeachingCard, Stage
from scenario_store import ScenarioStore


class TeachingAgent:
    """教学 Agent，核心方法 get_card（预生成教学卡）+ get_hint（实时合规提示）"""

    def get_card(self, scenario_id: str, audience: str) -> TeachingCard:
        """
        进场景时预生成一张教学卡（规则 / 静态生成，不调 LLM）。

        参数:
            scenario_id: 场景ID，例如 "neighbor-noise"
            audience: 训练身份（Audience.MINOR / Audience.ADULT）。
                      本期仅保留参数位，不据此分化内容（未成年/成人分流后置）。

        返回:
            TeachingCard: 教学卡数据类（title/when/how/why/scenario_id/example）

        逻辑：
        1. 从 scenario_store 取场景，默认招式名 = 场景第一个能力点 criteria[0]。
        2. 从 knowledge_base 取该场景 + 招式对应的方法论五要素
           {title,when,how,why,example}。
        3. 组装 TeachingCard 返回。
        """
        print(f"[TeachingAgent] 步骤1 - 生成教学卡：场景={scenario_id}，audience={audience}")

        # 步骤1：取场景配置，默认招式名 = 场景第一个能力点（如「表达边界」）
        scenario = ScenarioStore().get_scenario(scenario_id)
        strategy_name = scenario["criteria"][0]
        print(f"[TeachingAgent] 步骤1 - 场景「{scenario['title']}」，选中招式：{strategy_name}")

        # 步骤2：从知识库取该场景 + 招式对应的方法论五要素
        # 说明：knowledge_base 由另一名子 Agent 并行开发，此处按约定签名调用，
        #      返回结构为 {"title","when","how","why","example"}。
        #      懒导入写在方法内部，这样 S1 尚未就绪时也不会 import 报错。
        from knowledge_base import KnowledgeBase

        method = KnowledgeBase().get_method(scenario_id, strategy_name)

        # 步骤3：组装教学卡并返回（字段对齐 contracts.TeachingCard）
        print(f"[TeachingAgent] 步骤3 - 组装教学卡完成：{strategy_name}")
        return TeachingCard(
            title=method["title"],
            when=method["when"],
            how=method["how"],
            why=method["why"],
            scenario_id=scenario_id,
            example=method["example"],
        )

    def get_hint(self, scenario: dict, audience: str, stage: str, history: list) -> str:
        """
        回合中的实时合规提示，规则生成（不调 LLM，避免每轮延迟）。

        参数:
            scenario: 场景配置字典（含 hint 一句合规提示）
            audience: 训练身份（Audience.MINOR / Audience.ADULT），本期保留参数位，
                      不据此分化提示内容。
            stage: 当前对话阶段（contracts.Stage 常量之一）
            history: 对话历史列表（本期保留参数位，暂不据此调整提示）

        返回:
            str: 一句话提示（收尾阶段返回空字符串，表示不再提示）

        三阶段分支：
        - PRESSURE：返回场景 hint（一句合规提示），为空则给通用提示。
        - RESOLVE / DEADLOCK：收尾，返回空字符串。
        - 其他（如 OPENING）：返回一句开场引导。
        """
        print(f"[TeachingAgent] 步骤1 - 生成实时提示：阶段={stage}，audience={audience}")

        # 施压对峙阶段：给出场景的合规提示（一句「既表达边界又不升级」的话术）
        if stage == Stage.PRESSURE:
            hint = scenario.get("hint", "")
            if hint:
                print("[TeachingAgent] 步骤2 - PRESSURE：返回场景合规提示")
                return hint
            print("[TeachingAgent] 步骤2 - PRESSURE：场景无提示，返回通用提示")
            return "别被带节奏，回到事实和规则上"

        # 收尾阶段（通关 / 失控）：不再给提示，返回空字符串
        if stage in (Stage.RESOLVE, Stage.DEADLOCK):
            print("[TeachingAgent] 步骤2 - 收尾阶段，不再提示")
            return ""

        # 其他阶段（如 OPENING）：返回一句开场引导
        print("[TeachingAgent] 步骤2 - 开场阶段，返回开场引导")
        return "先接住对方的情绪，再明确表达你的边界"
