# -*- coding: utf-8 -*-
"""
strategy_kb.py - 策略知识库

维护「约束条件 -> 评分标准」的映射。
每个约束下定义了推荐策略、高分/低分特征，以及评分维度的权重配置。
这是评分的核心依据，JudgeAgent 会读取这里的数据来构造评分 prompt。
"""


class StrategyKB:
    """策略知识库，根据约束ID返回对应的策略配置字典"""

    # 4 种约束的完整策略配置
    _STRATEGIES = {
        "want_maintain": {
            "constraint_name": "想维持关系",
            "recommended_strategies": ["转移话题", "幽默带过", "软边界表达", "捧杀式回避"],
            "high_score_features": [
                "没有正面冲突",
                "成功把话头引开",
                "没有让对方下不来台",
                "关系氛围保持和谐",
                " subtly 表达了自己的立场",
            ],
            "low_score_features": [
                "直接顶撞长辈",
                "让对话冷场",
                "说重话伤感情",
                "完全妥协没有任何边界",
                "撒谎编造对象",
            ],
            "dimensions": [
                {"name": "边界守住", "weight": 0.3, "description": "是否在不撕破脸的前提下表达了自己的立场"},
                {"name": "关系维护", "weight": 0.4, "description": "是否保持了和谐的氛围，没有让对方难堪"},
                {"name": "冲突化解", "weight": 0.3, "description": "是否成功化解了当前这一轮催婚压力"},
            ],
        },
        "endure_but_record": {
            "constraint_name": "能忍但记账",
            "recommended_strategies": ["先接一招", "暗示边界", "表面应承内心保留", "留后手"],
            "high_score_features": [
                "表面保持了和谐",
                "暗示了自己的不满",
                "没有完全妥协",
                "给自己留了退路",
                "没有被牵着走",
            ],
            "low_score_features": [
                "完全顺从没有任何表达",
                "当场翻脸",
                "被PUA成功",
                "承诺了自己做不到的事",
            ],
            "dimensions": [
                {"name": "边界守住", "weight": 0.4, "description": "是否表达了自己的立场，哪怕是委婉的"},
                {"name": "关系维护", "weight": 0.3, "description": "表面是否保持了和谐"},
                {"name": "冲突化解", "weight": 0.3, "description": "是否暂时化解了压力"},
            ],
        },
        "dont_care": {
            "constraint_name": "无所谓",
            "recommended_strategies": ["随意应对", "不投入情绪", "敷衍", "保持自己的节奏"],
            "high_score_features": [
                "没有被对方的情绪带动",
                "保持了自己的节奏",
                "没有投入过多精力",
                "没有被PUA",
            ],
            "low_score_features": [
                "被带节奏情绪激动",
                "过度解释",
                "为了对方改变自己的立场",
            ],
            "dimensions": [
                {"name": "边界守住", "weight": 0.4, "description": "是否保持了自己的立场不被动摇"},
                {"name": "关系维护", "weight": 0.2, "description": "关系是否维持（无所谓的情况下权重低）"},
                {"name": "情绪稳定", "weight": 0.4, "description": "是否没有被对方带动情绪"},
            ],
        },
        "want_cutoff": {
            "constraint_name": "想断联",
            "recommended_strategies": ["直接划底线", "减少互动", "冷处理", "明确拒绝"],
            "high_score_features": [
                "边界清晰明确",
                "没有给对方继续的空间",
                "表达了不想继续的态度",
                "没有模棱两可",
            ],
            "low_score_features": [
                "模棱两可给了幻想",
                "敷衍但没有明确拒绝",
                "因为面子妥协",
                "说了重话但没有实际行动",
            ],
            "dimensions": [
                {"name": "边界守住", "weight": 0.5, "description": "是否清晰明确地划了底线"},
                {"name": "关系维护", "weight": 0.1, "description": "关系是否维持（想断联的情况下权重极低）"},
                {"name": "态度明确", "weight": 0.4, "description": "是否没有模棱两可，给了对方明确信号"},
            ],
        },
    }

    def get_strategy(self, constraint):
        """
        根据约束ID返回对应的策略配置。

        参数:
            constraint: 约束ID，例如 "want_maintain"

        返回:
            dict: 包含 constraint_name / recommended_strategies /
                  high_score_features / low_score_features / dimensions

        异常:
            KeyError: 约束ID不存在时抛出
        """
        print(f"[StrategyKB] 获取约束策略：{constraint}")
        if constraint not in self._STRATEGIES:
            raise KeyError(f"约束不存在：{constraint}")
        # 返回副本，避免外部误改
        return {
            "constraint_name": self._STRATEGIES[constraint]["constraint_name"],
            "recommended_strategies": list(self._STRATEGIES[constraint]["recommended_strategies"]),
            "high_score_features": list(self._STRATEGIES[constraint]["high_score_features"]),
            "low_score_features": list(self._STRATEGIES[constraint]["low_score_features"]),
            "dimensions": [dict(d) for d in self._STRATEGIES[constraint]["dimensions"]],
        }
