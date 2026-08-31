# -*- coding: utf-8 -*-
"""
verify_state_machine.py - 对峙值状态机 + 评分引擎回归验证

验证两部分：
1. 评分引擎（judge_agent）：红线一票否决 / 维度匹配 / 暴击判定。
2. 对峙值状态机：四条终局路径（普通合规 / 暴击×2 / 顶撞 / 红线）+ 边界用例，
   确认 resolve（优秀+及格）/ deadlock / round_limit 均可达、无震荡。
"""
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from contracts import (
    compute_confrontation_delta, is_crit, tier_for,
    CONFRONTATION_START, CONFRONTATION_MIN, CONFRONTATION_MAX,
    RESOLVE_CONFRONT, DEADLOCK_CONFRONT, ROUND_LIMIT, Stage,
)
from judge_agent import JudgeAgent
from scenario_store import ScenarioStore


def clamp(v):
    return max(CONFRONTATION_MIN, min(CONFRONTATION_MAX, v))


print("=" * 60)
print("【1】评分引擎 sanity 检查")
print("=" * 60)
store = ScenarioStore()
scenario = store.get_scenario("neighbor-noise")
judge = JudgeAgent()

cases = [
    ("红线（辱骂）", "你滚吧，废物！"),
    ("普通回应（边界不清）", "哦，知道了。"),
    ("良好回应（部分维度）", "我理解你，但这不能接受，请停止，我会记录并联系物业。"),
    ("完美回应（应触发暴击）", "我理解你，但我不接受这种说法，请停止。我会保持距离，按规则处理，保留记录，并求助物业工作人员。"),
]
for name, text in cases:
    r = judge.judge(scenario, "adult", [], text)
    crit = is_crit(r.total_score, r.red_line_hits)
    print(f"  [{name}] 总分={r.total_score} 红线={r.red_line_hits} 暴击={crit}")
    print(f"      命中维度={[k for k, v in r.dimensions.items() if v > 0]}")
    print(f"      反馈={r.feedback}")

print()
print("=" * 60)
print("【2】对峙值状态机推演（起始 50）")
print("=" * 60)


def simulate(name, rounds, crits_to_pass):
    """rounds: [(total_score, red_line_id_or_None), ...]"""
    conf = CONFRONTATION_START
    crits = 0
    trace = [conf]
    stage = Stage.PRESSURE
    for i, (score, rl) in enumerate(rounds, start=1):
        hits = [rl] if rl else []
        delta = compute_confrontation_delta(score, hits)
        conf = clamp(conf + delta)
        if is_crit(score, hits):
            crits += 1
        trace.append(conf)
        # 终局判定（顺序：失控 > 优秀 > 及格 > round_limit）
        if conf >= DEADLOCK_CONFRONT or (hits and rl == "r-violence"):
            stage = "deadlock（失控）"
            break
        if crits >= crits_to_pass and conf <= RESOLVE_CONFRONT:
            stage = "resolve（优秀）"
            break
        if conf <= 0 and crits < crits_to_pass:
            stage = "resolve（及格）"
            break
        if i >= ROUND_LIMIT:
            stage = "end（round_limit 兜底）"
            break
    print(f"  [{name}]")
    print(f"      轨迹: {' → '.join(map(str, trace))}")
    print(f"      终局: {stage}（暴击={crits}）")
    print()


# 路径1：普通合规（score 60，无红线）→ 每回合 -5，10 回合压到 0
simulate("普通合规（score=60，-5/回合）", [(60, None)] * ROUND_LIMIT, crits_to_pass=2)

# 路径2：暴击×2（score 90，无红线）→ 每回合 -15
simulate("暴击×2（score=90，-15/回合）", [(90, None), (90, None)], crits_to_pass=2)

# 路径3：顶撞（score 30，无红线）→ 每回合 +10
simulate("顶撞（score=30，+10/回合）", [(30, None)] * ROUND_LIMIT, crits_to_pass=2)

# 路径4：红线（score 30，命中 r-insult）→ 每回合 +25
simulate("红线（命中 r-insult，+25/回合）", [(30, "r-insult")] * ROUND_LIMIT, crits_to_pass=2)

# 路径5：打 1 次暴击后普通合规 → 先压到 0，暴击不足 → 及格（v5 新增终局）
simulate("暴击1次+压平（先到 0，暴击不足）", [(90, None)] + [(60, None)] * ROUND_LIMIT, crits_to_pass=2)

# 路径6：暴力红线（r-violence）→ 直接 deadlock（不依赖对峙值）
simulate("暴力红线（r-violence 直接失控）", [(30, "r-violence")], crits_to_pass=2)

print("=" * 60)
print("【3】NPC 台词层级推导（yield 优先）")
print("=" * 60)
for v in [0, 25, 26, 44, 45, 69, 70, 100]:
    print(f"  对峙值 {v:>3} → {tier_for(v)}")
