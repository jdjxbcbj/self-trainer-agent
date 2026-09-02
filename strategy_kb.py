# -*- coding: utf-8 -*-
"""
strategy_kb.py - 评分库 GSB + 红线库 RSB

维护「安全对线训练场」的评分维度（GSB）与红线（RSB）。
这是评分的核心依据，JudgeAgent 读取这里的数据做确定性打分（不调 LLM）。

- GSB 正向维度（7 个，关键词命中 + 权重）
- GSB 负向维度（2 个，关键词命中反向扣分）
- RSB 红线（4 类，一票否决）

数据与前端 demo/app.js 的 scoreRules / redLines 对齐（见 PLAN.md §3.3）。
关键词匹配是朴素的子串匹配（大小写不敏感），是已知的「很智障」局限，
后续优化方向是更丰富的特征 + 场景 criteria 加权 + 红线精确化（见 §9 决策第 1 项）。
"""

import copy
import re


# ============================================================
# GSB 正向维度（7 个，命中关键词即 +weight）
# ============================================================
POSITIVE_DIMENSIONS = [
    {"id": "g-boundary", "name": "表达边界", "weight": 18,
     "keywords": ["不接受", "请停止", "不能", "边界", "不会", "keep your distance", "do not"]},
    {"id": "g-calm", "name": "保持冷静", "weight": 14,
     "keywords": ["我理解", "我听到", "冷静", "先停", "我们先", "I hear", "I understand"]},
    {"id": "g-legal", "name": "合规合法", "weight": 18,
     "keywords": ["规则", "法律", "民法典", "消费者权益", "规定", "依法", "条例", "法规", "report", "security"]},
    {"id": "g-deescalate", "name": "降温控场", "weight": 16,
     "keywords": ["保持距离", "离开", "不争吵", "不升级", "按事实", "下一步", "step away"]},
    {"id": "g-evidence", "name": "取证意识", "weight": 14,
     "keywords": ["记录", "录音", "凭证", "截图", "保留", "证据", "record"]},
    {"id": "g-polite", "name": "礼貌", "weight": 8,
     "keywords": ["请", "谢谢", "麻烦", "please"]},
    {"id": "g-risk", "name": "求助意识", "weight": 12,
     "keywords": ["求助", "找老师", "老师", "家长", "消协", "报警", "工作人员",
                  "物业", "学校", "平台", "公安", "保安", "警察", "居委会", "staff"]},
]

# ============================================================
# GSB 负向维度（2 个，命中关键词反向扣分，weight 为负）
# ============================================================
NEGATIVE_DIMENSIONS = [
    {"id": "p-blame", "name": "指责对抗", "weight": -18,
     "keywords": ["都怪你", "你必须", "少废话", "闭嘴"]},
    {"id": "p-empty", "name": "空洞敷衍", "weight": -12,
     "keywords": ["随便", "算了", "没事", "都行"]},
]

# ============================================================
# RSB 红线（4 类，一票否决）
# ============================================================
RED_LINES = [
    {"id": "r-insult", "category": "insult",
     "keywords": ["滚", "废物", "傻", "垃圾", "贱", "idiot", "stupid"],
     "message": "出现辱骂，会把安全训练变成互撕。",
     "alternative": "我不同意你的说法，也不会接受这种沟通方式。请回到事实和规则。",
     "law": "民法典人格权保护：避免侮辱、诽谤等侵权风险。"},
    {"id": "r-violence", "category": "violence",
     "keywords": ["打你", "弄死", "揍", "动手", "砸", "kill", "hit you"],
     "message": "出现暴力威胁，直接判定违规失分。",
     "alternative": "我不会使用威胁或暴力。如果你继续靠近，我会离开并求助。",
     "law": "治安管理处罚法：殴打、威胁他人人身安全可能承担法律责任。"},
    {"id": "r-illegal", "category": "illegal",
     "keywords": ["曝光你身份证", "人肉", "砸店", "堵门", "威胁你家人"],
     "message": "违法维权会让自己从受害方变成风险方。",
     "alternative": "我会保留凭证，通过平台、消协、物业、学校或公安等合法渠道处理。",
     "law": "民法典与个人信息保护相关规则：不得非法公开他人隐私和个人信息。"},
    {"id": "r-foreign", "category": "foreign",
     "keywords": ["你们国家都", "你这种种族", "racist back", "your race"],
     "message": "涉外场景中使用歧视性反击会放大风险。",
     "alternative": "Please keep your distance. I do not accept discriminatory language and will report this to staff/security.",
     "law": "涉外冲突优先避险、留证、求助，避免歧视性反击。"},
]


# 否定词（B2）：红线关键词紧邻这些词表示「不做」，不算违规
NEGATION_WORDS = ["不会", "不要", "不想", "不能", "不敢", "没有", "别再", "无需", "绝不",
                  "不", "别", "没", "莫", "勿", "无"]


def _is_negated(lower, idx):
    """关键词在 lower[idx] 处命中，判断其是否被紧邻否定词否定。"""
    prefix = lower[max(0, idx - 2):idx]
    return any(prefix.endswith(w) for w in NEGATION_WORDS)


def _contains_non_negated(lower, kw):
    """kw 在 lower 中至少出现一次且未被否定。"""
    for m in re.finditer(re.escape(kw), lower):
        if not _is_negated(lower, m.start()):
            return True
    return False


class StrategyKB:
    """评分库 + 红线库，提供维度/红线数据与关键词匹配工具"""

    def get_dimensions(self):
        """返回正向 + 负向维度列表（深拷贝，避免外部误改内部数据）。"""
        return {
            "positive": copy.deepcopy(POSITIVE_DIMENSIONS),
            "negative": copy.deepcopy(NEGATIVE_DIMENSIONS),
        }

    def get_red_lines(self):
        """返回红线列表（深拷贝）。"""
        return copy.deepcopy(RED_LINES)

    def match_dimensions(self, text):
        """匹配文本命中的正向/负向维度。

        参数:
            text: 用户回应文本

        返回:
            (hits, penalties)：hits = 命中的正向维度列表，penalties = 命中的负向维度列表。
            返回的是内部常量 dict 的引用，仅供只读（JudgeAgent 不修改它们）。
        """
        lower = text.lower()
        hits = [d for d in POSITIVE_DIMENSIONS
                if any(k.lower() in lower for k in d["keywords"])]
        penalties = [d for d in NEGATIVE_DIMENSIONS
                     if any(k.lower() in lower for k in d["keywords"])]
        return hits, penalties

    def detect_red_line(self, text):
        """检测文本是否命中红线（一票否决）。

        否定词过滤（B2）：关键词紧邻「不/别/不要/不会/没」等否定词时视为否定，
        不再一票否决（如「我不会打你」「别动手」不算暴力威胁）。

        返回:
            dict: 命中的红线配置；未命中返回 None。
        """
        lower = text.lower()
        for r in RED_LINES:
            for kw in r["keywords"]:
                if _contains_non_negated(lower, kw.lower()):
                    return r
        return None
