# -*- coding: utf-8 -*-
"""
e2e_wave2.py - Wave 2 端到端验证（主控集成 + 数据层落库）

驱动 TrainerSystem（main → router → agents → storage）跑通三条终局路径，
校验对峙值轨迹、终局判定、以及 storage 落库（sessions / turns / users）。

三条路径（与 §3.4 终局条件一一对应）：
1. 暴击 ×2 → 优秀通关（RESOLVE，achievement_score 90）
2. r-violence 红线 → 失控（DEADLOCK，achievement_score 30）
3. 普通合规 ×10 → 及格通关（RESOLVE，achievement_score 65）
"""
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import time

from contracts import Stage
from main import TrainerSystem

# 可靠输入（关键词确定性匹配，见 strategy_kb）：
CRIT = "我理解你，但我不接受这种说法，请停止。我会保持距离，按规则处理，保留记录，并求助物业工作人员。"  # 命中 7 维 → 100 → 暴击
RED_VIOLENCE = "我打你，弄死你！"                                   # 命中 r-violence → 一票否决
COMPLIANT = "我理解你，但请按规则处理。"                              # 命中 calm+legal+polite → 40 → -5

SCENARIO = "neighbor-noise"  # critsToPass=2，minorSafe=True


def section(title):
    print()
    print("=" * 60)
    print(f"【{title}】")
    print("=" * 60)


def assert_eq(actual, expected, label):
    ok = actual == expected
    print(f"  {'✓' if ok else '✗ FAIL'} {label}: 期望={expected}，实际={actual}")
    assert ok, f"{label} 断言失败"
    return ok


def main():
    system = TrainerSystem()
    ts = int(time.time() * 1000)  # 唯一后缀，避免重复运行撞 sessions 主键

    # ------------------------------------------------------------------
    # 路径1：暴击 ×2 → 优秀通关
    # ------------------------------------------------------------------
    section("路径1：暴击 ×2 → 优秀通关")
    user1, sess1 = f"e2e_user1_{ts}", f"e2e_sess1_{ts}"
    opening, card = system.start_session(user1, sess1, SCENARIO, "adult")
    assert_eq(opening, system.scenario_store.get_scenario(SCENARIO)["opening"], "开场白已写入")
    assert_eq(card.title, "表达边界", "教学卡默认招式=场景第一个能力点")

    t1 = system.handle_turn(user1, sess1, SCENARIO, "adult", CRIT)
    assert_eq(t1.score.total_score, 100, "暴击1 总分")
    assert_eq(t1.confrontation_value, 35, "暴击1 对峙值 50→35（-15）")
    assert_eq(t1.next_stage, Stage.PRESSURE, "暴击1 尚未通关（暴击1<2）")

    t2 = system.handle_turn(user1, sess1, SCENARIO, "adult", CRIT)
    assert_eq(t2.confrontation_value, 20, "暴击2 对峙值 35→20（-15）")
    assert_eq(t2.next_stage, Stage.RESOLVE, "暴击2 达到 critsToPass → 优秀通关")

    r1 = system.end_session(user1, sess1, SCENARIO, "adult")
    assert_eq(r1.goal_achieved, True, "优秀：goal_achieved")
    assert_eq(r1.achievement_score, 90, "优秀：达成度 90")

    s1 = system.storage.get_session(sess1)
    assert_eq(s1["final_stage"], Stage.RESOLVE, "sessions 落库 final_stage")
    assert_eq(s1["goal_achieved"], 1, "sessions 落库 goal_achieved")
    assert_eq(s1["achievement_score"], 90, "sessions 落库 achievement_score")
    assert_eq(len(system.storage.get_turns(sess1)), 2, "turns 落库 2 条")
    assert_eq(system.storage.get_profile(user1).get("practice_count"), 1, "users 画像 practice_count=1")

    # ------------------------------------------------------------------
    # 路径2：r-violence 红线 → 失控
    # ------------------------------------------------------------------
    section("路径2：r-violence 红线 → 失控")
    user2, sess2 = f"e2e_user2_{ts}", f"e2e_sess2_{ts}"
    system.start_session(user2, sess2, SCENARIO, "adult")

    t = system.handle_turn(user2, sess2, SCENARIO, "adult", RED_VIOLENCE)
    assert_eq(t.score.red_line_hits, ["r-violence"], "命中 r-violence 红线")
    assert_eq(t.score.total_score, 30, "红线一票否决 total=30")
    assert_eq(t.confrontation_value, 75, "红线对峙值 50→75（+25）")
    assert_eq(t.next_stage, Stage.DEADLOCK, "r-violence 直接失控")

    r2 = system.end_session(user2, sess2, SCENARIO, "adult")
    assert_eq(r2.goal_achieved, False, "失控：goal_achieved=False")
    assert_eq(r2.achievement_score, 30, "失控：达成度 30")
    s2 = system.storage.get_session(sess2)
    assert_eq(s2["final_stage"], Stage.DEADLOCK, "sessions 落库 final_stage=deadlock")

    # ------------------------------------------------------------------
    # 路径3：普通合规 ×10 → 及格通关
    # ------------------------------------------------------------------
    section("路径3：普通合规 ×10 → 及格通关")
    user3, sess3 = f"e2e_user3_{ts}", f"e2e_sess3_{ts}"
    system.start_session(user3, sess3, SCENARIO, "adult")

    trace = []
    last = None
    for i in range(1, 11):
        last = system.handle_turn(user3, sess3, SCENARIO, "adult", COMPLIANT)
        trace.append(last.confrontation_value)
        assert_eq(last.confrontation_value, 50 - 5 * i, f"第{i}回合对峙值 50-5*{i}")
    assert_eq(trace[-1], 0, "10 回合压平对峙值")
    assert_eq(last.next_stage, Stage.RESOLVE, "压平但暴击不足 → 及格通关")

    r3 = system.end_session(user3, sess3, SCENARIO, "adult")
    assert_eq(r3.goal_achieved, True, "及格：goal_achieved=True")
    assert_eq(r3.achievement_score, 65, "及格：达成度 65")
    assert_eq(system.storage.get_profile(user3).get("latest_weak_point"), "还差 2 次暴击即优秀",
              "画像 latest_weak_point")

    # ------------------------------------------------------------------
    print()
    print("=" * 60)
    print("✅ 全部断言通过（3 条终局路径 + 数据层落库校验）")
    print("=" * 60)


if __name__ == "__main__":
    main()
