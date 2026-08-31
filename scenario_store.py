# -*- coding: utf-8 -*-
"""
scenario_store.py - 场景库 SDB（场景数据存储）

负责提供「安全对线训练场」的冲突场景配置数据。
当前版本内置 6 个安全场景（4 模块），数据写死在代码里，
后续可扩展为从数据库或文件读取。

每个场景包含（静态，不随对话变化，见 PLAN.md §3.2）：
- 基础信息：id / moduleId / title / premise / personaName / opening
- riskLevel（low/medium/high）/ minorSafe / critsToPass
- laws（法条）/ criteria（本场景能力点）/ hint（一句合规提示）
- lines：NPC 按对峙值层级选台词（low / mid / high / yield）

动态状态（对峙值 confrontation_value）由 memory.py 存储，不在此处。

数据与前端 demo/app.js 的 scenarios 对齐。
"""

import copy

from contracts import Audience


# 模块名映射
MODULES = {
    "domestic": "国内日常边界",
    "legal": "普法合规维权",
    "overseas": "海外涉外冲突",
    "negotiation": "情绪控场谈判",
}


class ScenarioStore:
    """场景数据存储类，按 scenario_id 返回场景配置字典"""

    _SCENARIOS = {
        "neighbor-noise": {
            "id": "neighbor-noise",
            "moduleId": "domestic",
            "title": "邻里噪音纠纷",
            "premise": "晚上休息时间，邻居持续制造噪音，并反过来指责你事多。",
            "personaName": "蛮横邻居",
            "opening": "就这点声音你也要管？大家都是邻居，你别这么小题大做。",
            "riskLevel": "low",
            "minorSafe": True,
            "critsToPass": 2,
            "laws": ["民法典相邻关系：相邻各方应当按照有利生产、方便生活、团结互助、公平合理原则处理相邻关系。"],
            "criteria": ["表达边界", "保持冷静", "提出规则化处理", "必要时留存记录"],
            "lines": {
                "low": ["你这么说不就是想让我什么都别干？", "大家都能忍，怎么就你不行？"],
                "mid": ["你要投诉就投诉，我还怕你不成？", "别拿规矩压我，你先证明是我。"],
                "high": ["你再说一句试试，我现在就找你理论。", "你录啊，我看你能怎么样。"],
                "yield": ["行，我今晚注意点，你也别把事情闹大。", "那先按物业规定处理，别吵了。"],
            },
            "hint": "我理解你有生活需求，但现在是休息时间。请把音量降下来；如果持续影响休息，我会记录时间并联系物业按规则处理。",
        },
        "relative-pressure": {
            "id": "relative-pressure",
            "moduleId": "domestic",
            "title": "亲戚道德绑架",
            "premise": "亲戚临时要求你承担不合理费用，并用家人关系施压。",
            "personaName": "施压亲戚",
            "opening": "都是一家人，你条件好一点，帮一下怎么了？别这么计较。",
            "riskLevel": "low",
            "minorSafe": True,
            "critsToPass": 2,
            "laws": ["民法典自愿原则：民事主体从事民事活动，应当遵循自愿原则。"],
            "criteria": ["礼貌拒绝", "不解释过度", "给出可行边界", "不被情绪裹挟"],
            "lines": {
                "low": ["你这样太冷漠了吧？", "你是不是看不起我们家？"],
                "mid": ["我话都说到这份上了，你还不帮？", "以后家里有事你也别开口。"],
                "high": ["我现在就告诉大家你多自私。", "你必须今天给个说法。"],
                "yield": ["那我知道你的意思了。", "既然你说清楚了，我再想别的办法。"],
            },
            "hint": "我理解你现在有压力，但这笔费用我不能承担。我能做的是帮你一起梳理其他方案，这个边界我不会改变。",
        },
        "merchant-rights": {
            "id": "merchant-rights",
            "moduleId": "legal",
            "title": "商家拒绝退款",
            "premise": "商品存在明显问题，商家以“售出不退”为由拒绝处理。",
            "personaName": "强硬商家",
            "opening": "我们店规写得很清楚，售出概不退换，你找谁都没用。",
            "riskLevel": "medium",
            "minorSafe": False,
            "critsToPass": 2,
            "laws": ["消费者权益保护法：消费者享有知悉真实情况、公平交易、依法求偿等权利。"],
            "criteria": ["提出事实", "保存凭证", "明确诉求", "说明合法渠道"],
            "lines": {
                "low": ["你说有问题就有问题？", "我们一直都是这个规矩。"],
                "mid": ["别吓唬我，投诉也没用。", "你自己不会用，不能怪我们。"],
                "high": ["你再闹我就让保安处理。", "我们不可能赔，你爱去哪去哪。"],
                "yield": ["那你把凭证发来，我们登记处理。", "可以先走检测流程。"],
            },
            "hint": "我不接受“售出概不退换”排除法定责任。商品问题、付款记录和沟通记录我会保留，请按消费者权益保护法给出退换或检测方案。",
        },
        "campus-boundary": {
            "id": "campus-boundary",
            "moduleId": "domestic",
            "title": "校园冒犯与求助",
            "premise": "同学反复拿你的隐私开玩笑，周围有人起哄。",
            "personaName": "起哄同学",
            "opening": "开个玩笑而已，你这么认真干嘛？不会真生气了吧？",
            "riskLevel": "low",
            "minorSafe": True,
            "critsToPass": 2,
            "laws": ["未成年人保护相关原则：学校应当保护未成年人人格尊严，预防欺凌。"],
            "criteria": ["明确不舒服", "要求停止", "寻求成年人帮助", "不互相羞辱"],
            "lines": {
                "low": ["大家都笑了，你别扫兴。", "你不让说是不是心虚？"],
                "mid": ["你去告老师啊，谁怕谁。", "以后我们都不带你玩。"],
                "high": ["你敢说出去试试。", "我就说了，你能怎么样？"],
                "yield": ["行，不说了。", "那你别告状，我以后注意。"],
            },
            "hint": "我不接受你拿我的隐私开玩笑，请立刻停止。如果继续，我会保留记录并找老师或家长帮助处理。",
        },
        "overseas-slur": {
            "id": "overseas-slur",
            "moduleId": "overseas",
            "title": "海外种族挑衅",
            "premise": "公共场所遇到带有歧视意味的挑衅，需要英文得体回应并优先避险。",
            "personaName": "挑衅路人",
            "opening": "Why are you even here? Go back where you came from.",
            "riskLevel": "medium",
            "minorSafe": False,
            "critsToPass": 2,
            "laws": ["海外场景原则：避免升级冲突，优先离开现场并向场地方、学校或警方求助。"],
            "criteria": ["简短英文边界", "不回骂", "拉开距离", "求助或取证"],
            "lines": {
                "low": ["What, you can't speak now?", "I'm just saying the truth."],
                "mid": ["You people are always too sensitive.", "Don't record me."],
                "high": ["Come here and say that again.", "I'll make you leave."],
                "yield": ["Fine, whatever.", "Okay, I'm leaving."],
            },
            "hint": "Do not speak to me like that. I am stepping away now, and I will report this to staff/security. Please keep your distance.",
        },
        "rage-deescalation": {
            "id": "rage-deescalation",
            "moduleId": "negotiation",
            "title": "暴怒对峙降温",
            "premise": "对方情绪激动、声音很大，并试图把你拉入争吵。",
            "personaName": "暴怒对峙者",
            "opening": "你今天必须给我说清楚！别想走！",
            "riskLevel": "high",
            "minorSafe": False,
            "critsToPass": 3,
            "laws": ["治安管理处罚法相关风险：避免互殴、威胁、侮辱等升级行为。"],
            "criteria": ["承认情绪不承认指控", "降低音量", "给选择", "必要时离场求助"],
            "lines": {
                "low": ["你别装冷静，我就问你怎么办？", "你现在必须回答。"],
                "mid": ["你是不是心虚？", "你敢走我就追上去。"],
                "high": ["我控制不住了，你别逼我。", "今天谁也别想好过。"],
                "yield": ["那你先说方案。", "行，先停一下。"],
            },
            "hint": "我听到你很生气，但我不会在威胁和吼叫中处理问题。我们先各退一步，保持距离，再按事实说下一步；如果继续升级，我会离开并求助。",
        },
    }

    def get_scenario(self, scenario_id):
        """
        根据场景 ID 返回场景配置字典。

        参数:
            scenario_id: 场景ID，例如 "neighbor-noise"

        返回:
            dict: 场景配置（含 id / moduleId / title / premise / personaName / opening /
                  riskLevel / minorSafe / critsToPass / laws / criteria / lines / hint）

        异常:
            KeyError: 场景不存在时抛出（由调用方决定如何处理）
        """
        print(f"[ScenarioStore] 获取场景：{scenario_id}")
        if scenario_id not in self._SCENARIOS:
            raise KeyError(f"场景不存在：{scenario_id}")
        # 深拷贝：场景里含嵌套 dict（lines 等），浅拷贝会导致外部误改内部数据。
        return copy.deepcopy(self._SCENARIOS[scenario_id])

    def list_scenarios(self, audience=None):
        """
        列出所有场景（可按训练身份过滤）。

        参数:
            audience: 训练身份（Audience.MINOR / Audience.ADULT），None 表示不过滤。
                      未成年人只返回 minorSafe=True 的场景（§9 决策第 9 项：本期只做场景隔离）。

        返回:
            list: 场景配置字典列表（按定义顺序）
        """
        scenarios = [copy.deepcopy(s) for s in self._SCENARIOS.values()]
        if audience == Audience.MINOR:
            scenarios = [s for s in scenarios if s["minorSafe"]]
            print(f"[ScenarioStore] 列出未成年可用场景：{len(scenarios)} 个")
        else:
            print(f"[ScenarioStore] 列出全部场景：{len(scenarios)} 个")
        return scenarios
