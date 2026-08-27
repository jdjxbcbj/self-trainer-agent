# -*- coding: utf-8 -*-
"""
teaching_agent.py - 教学 Agent 核心

负责在进场景时预生成教学卡（get_card），以及在回合中给出实时提示（get_hint）。

设计原则：
- 规则优先：本轮只做规则 / 静态生成，不调用 LLM，避免每轮延迟。
- 文案基于 strategy_kb 的 recommended_strategies 组织，保证与评分标准一致。
- 数据类一律从 contracts 导入，不自己定义。
"""

from contracts import TeachingCard, Stage
from strategy_kb import StrategyKB


class TeachingAgent:
    """教学 Agent，核心方法 get_card（预生成教学卡）+ get_hint（实时提示）"""

    def __init__(self):
        self.strategy_kb = StrategyKB()

    def get_card(self, scenario_id: str, constraint: str):
        """
        进场景时预生成一张教学卡（规则 / 静态生成，不调 LLM）。

        参数:
            scenario_id: 场景ID，例如 "wang_ayi_cuihun"
            constraint: 约束ID，例如 "want_maintain"

        返回:
            TeachingCard: 教学卡数据类

        逻辑：
        1. 从 strategy_kb 取 recommended_strategies，第一个作为默认招式名 strategy_name。
        2. 从 knowledge_base 取方法论内容（dict，键 title/when/how/why/example）。
        3. 组装 TeachingCard(title, when, how, why, constraint, example) 返回。
        """
        print(f"[TeachingAgent] 生成教学卡：场景={scenario_id}，约束={constraint}")

        # 步骤1：取该约束下的推荐策略，第一个作为默认招式
        strategy = self.strategy_kb.get_strategy(constraint)
        strategy_name = strategy["recommended_strategies"][0]
        print(f"[TeachingAgent] 当前约束「{constraint}」，选中招式：{strategy_name}")

        # 步骤2：从知识库取该约束 + 招式对应的方法论内容
        # 说明：knowledge_base 由另一名子 Agent 并行开发，此处按约定签名调用，
        #      返回结构为 {"title","when","how","why","example"}。
        from knowledge_base import KnowledgeBase

        method = KnowledgeBase().get_method(constraint, strategy_name)

        # 步骤3：组装教学卡并返回
        return TeachingCard(
            title=method["title"],
            when=method["when"],
            how=method["how"],
            why=method["why"],
            constraint=constraint,
            example=method["example"],
        )

    def get_hint(self, scenario: dict, constraint: str, stage: str, history: list) -> str:
        """
        回合中的实时提示，规则优先（不调 LLM，避免每轮延迟）。

        参数:
            scenario: 场景配置字典
            constraint: 约束ID
            stage: 当前对话阶段（contracts.Stage 常量之一）
            history: 对话历史列表

        返回:
            str: 一句话提示（可为空字符串）
        """
        print(f"[TeachingAgent] 生成实时提示：阶段={stage}，约束={constraint}")

        # 施压阶段：给出稳住关系 + 立住边界的提示
        if stage == Stage.PRESSURE:
            return "王阿姨还在催，试试『软边界表达』既稳住关系又立住边界"

        # 收尾阶段：这轮可以收尾了，不再给提示
        if stage in (Stage.RESOLVE, Stage.DEADLOCK):
            return ""

        # 其他（如开场）：先接住关心，再表达自己的节奏
        return "先接住对方的关心，再表达自己的节奏"
