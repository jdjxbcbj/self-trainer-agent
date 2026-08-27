# -*- coding: utf-8 -*-
"""
scenario_store.py - 场景数据存储

负责提供冲突场景的配置数据。
当前版本只有一个内置场景，数据直接写死在代码里，
后续可以扩展为从数据库或文件读取。

每个场景包含：
- 基础信息：id / name / description / character
- persona_params：角色静态性格参数（人设常量，不随对话变化）
- initial_persona_state：角色动态状态的初始值（随对话演化）
"""

import copy

from contracts import DEFAULT_PERSONA_STATE


class ScenarioStore:
    """场景数据存储类，按 scenario_id 返回场景配置字典"""

    # 内置场景数据（后续可扩展为从外部数据源读取）
    _SCENARIOS = {
        "wang_ayi_cuihun": {
            "id": "wang_ayi_cuihun",
            "name": "王阿姨催婚",
            "description": "过年聚餐，亲戚王阿姨当众催婚，问你什么时候结婚",
            "character": (
                "王阿姨，55岁，热情但固执的长辈，爱面子，觉得催婚是关心晚辈，"
                "说话直来直去，容易被转移话题但绕几圈还会回到催婚上"
            ),
            # 静态性格参数：人设常量，不随对话变化。
            # 数值越大，对应倾向越强（0~1）。
            "persona_params": {
                "催婚执念度": 0.7,   # 越高越容易绕回催婚
                "面子敏感度": 0.8,   # 越高越在意晚辈是否"懂事"
                "容易被转移度": 0.4, # 越高越容易接转移话题的茬
                "情绪波动": 0.3,     # 越高越容易被激怒或哄好
            },
            # 动态状态初始值：随对话演化，由扮演 Agent 每轮更新。
            "initial_persona_state": dict(DEFAULT_PERSONA_STATE),
        },
    }

    def get_scenario(self, scenario_id):
        """
        根据场景ID返回场景配置字典。

        参数:
            scenario_id: 场景ID，例如 "wang_ayi_cuihun"

        返回:
            dict: 包含 id / name / description / character /
                  persona_params / initial_persona_state

        异常:
            KeyError: 场景不存在时抛出（由调用方决定如何处理）
        """
        print(f"[ScenarioStore] 获取场景：{scenario_id}")
        if scenario_id not in self._SCENARIOS:
            raise KeyError(f"场景不存在：{scenario_id}")
        # 深拷贝：场景里含嵌套 dict（persona_params / initial_persona_state），
        # 浅拷贝会导致外部误改内部数据，这里用 copy.deepcopy 彻底隔离。
        return copy.deepcopy(self._SCENARIOS[scenario_id])
