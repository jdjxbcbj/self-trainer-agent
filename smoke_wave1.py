# -*- coding: utf-8 -*-
"""
_smoke_wave1.py - Wave 1 冒烟测试（临时，不提交）

导入全部模块 + 逐个 exercise Wave 1 新增的 5 个模块，
重点抓跨 Agent 集成点（S5 调 S1 的签名、S6 的 ReviewResult、S4 的 tier_for、S2 的 clamp）。
"""
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from contracts import (
    Stage, CONFRONTATION_START, compute_confrontation_delta, CONFRONTATION_MIN, CONFRONTATION_MAX,
)
from memory import SessionMemory
from knowledge_base import KnowledgeBase
from roleplay_agent import RoleplayAgent
from teaching_agent import TeachingAgent
from review_agent import ReviewAgent
from scenario_store import ScenarioStore
from judge_agent import JudgeAgent

print("=== 导入全部模块 OK ===")

# 1. SessionMemory
mem = SessionMemory()
assert mem.get_confrontation("s1") == CONFRONTATION_START, "默认对峙值应为 50"
mem.set_confrontation("s1", 999)
assert mem.get_confrontation("s1") == CONFRONTATION_MAX, "clamp 上限应为 100"
mem.set_confrontation("s1", -5)
assert mem.get_confrontation("s1") == CONFRONTATION_MIN, "clamp 下限应为 0"
assert mem.get_stage("s1") == Stage.OPENING, "默认阶段应为 opening"
mem.set_stage("s1", Stage.PRESSURE)
assert mem.get_stage("s1") == Stage.PRESSURE
mem.add_message("s1", "user", "你好")
mem.add_message("s1", "ai", "有事吗")
ctx = mem.get_context("s1")
assert len(ctx) == 2 and ctx[0]["role"] == "user", "消息顺序错误"
mem.clear("s1")
assert mem.get_context("s1") == [], "clear 未清空"
print("1. SessionMemory OK")

# 2. KnowledgeBase
kb = KnowledgeBase()
for s in ["表达边界", "保持冷静", "合规合法", "降温控场", "取证意识", "礼貌", "求助意识"]:
    m = kb.get_method("neighbor-noise", s)
    assert set(m) == {"title", "when", "how", "why", "example"}, f"{s} 五要素缺失"
assert kb.get_method("neighbor-noise", "不存在的招式")["title"] == "不存在的招式", "兜底逻辑错误"
legal = kb.get_legal("neighbor-noise")
assert isinstance(legal, list) and len(legal) > 0, "get_legal 未返回法条"
assert kb.get_legal("不存在的场景") == [], "未知场景应返回 []"
print("2. KnowledgeBase OK")

# 3. RoleplayAgent
rp = RoleplayAgent()
store = ScenarioStore()
sc = store.get_scenario("neighbor-noise")
assert rp.reply(sc, "adult", [], "你好", 50) == sc["opening"], "开场应返回 opening"
line = rp.reply(sc, "adult", [{"role": "ai", "content": "x"}], "回应", 20)
assert line in sc["lines"]["yield"], f"yield 台词选错: {line}"
line2 = rp.reply(sc, "adult", [{"role": "ai", "content": "x"}], "回应", 90)
assert line2 in sc["lines"]["high"], f"high 台词选错: {line2}"
print("3. RoleplayAgent OK")

# 4. TeachingAgent
ta = TeachingAgent()
card = ta.get_card("neighbor-noise", "adult")
assert card.scenario_id == "neighbor-noise", "教学卡 scenario_id 错误"
assert card.title, "教学卡 title 为空"
hint = ta.get_hint(sc, "adult", Stage.PRESSURE, [])
assert hint, "施压阶段应有提示"
assert ta.get_hint(sc, "adult", Stage.DEADLOCK, []) == "", "终局阶段应无提示"
print("4. TeachingAgent OK")

# 5. ReviewAgent
ra = ReviewAgent()
r = ra.review("sid", "uid", sc, "adult", [], {}, Stage.RESOLVE, 20, 2)
assert r.goal_achieved and r.achievement_score == 90, f"优秀判定错误: {r}"
r2 = ra.review("sid", "uid", sc, "adult", [], {}, Stage.RESOLVE, 0, 1)
assert r2.goal_achieved and r2.achievement_score == 65, f"及格判定错误: {r2}"
r3 = ra.review("sid", "uid", sc, "adult", [], {}, Stage.DEADLOCK, 90, 0)
assert not r3.goal_achieved and r3.achievement_score == 30, f"失控判定错误: {r3}"
r4 = ra.review("sid", "uid", sc, "adult", [], {}, Stage.END, 60, 0)
assert not r4.goal_achieved and r4.achievement_score == 50, f"到时判定错误: {r4}"
print("5. ReviewAgent OK")

# 6. 端到端小模拟（不依赖 router）：judge → 对峙值 → roleplay → 记忆
jd = JudgeAgent()
resp = "我理解你，但我不能接受。请停止，我会记录并联系物业。"
sr = jd.judge(sc, "adult", [], resp)
delta = compute_confrontation_delta(sr.total_score, sr.red_line_hits)
next_c = max(CONFRONTATION_MIN, min(CONFRONTATION_MAX, CONFRONTATION_START + delta))
print(f"6. judge 得分={sr.total_score} 红线={sr.red_line_hits} delta={delta} next对峙值={next_c}")
print()
print("=== Wave 1 冒烟测试全部通过 ===")
