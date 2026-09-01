# -*- coding: utf-8 -*-
"""
test_backend.py - 后端单测（pytest 约定 + standalone runner）

把 e2e_wave2.py 的断言沉淀为可重复跑的用例，覆盖：
1. 三条终局路径（暴击→优秀 / r-violence→失控 / 普通合规→及格）
2. storage 落库（sessions / turns / users）
3. GSB 红线检测（RSB 四类红线 + 一票否决）

pytest 约定：函数名 test_* + assert，可用 `py -m pytest test_backend.py` 跑；
同时自带 standalone runner，没装 pytest 时 `py test_backend.py` 也能跑。
"""
import sys
import time
import traceback

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import config
from contracts import Stage
from main import TrainerSystem
from strategy_kb import StrategyKB

# 可靠输入（关键词确定性匹配，见 strategy_kb）
CRIT = "我理解你，但我不接受这种说法，请停止。我会保持距离，按规则处理，保留记录，并求助物业工作人员。"  # 命中 7 维 → 100 → 暴击
RED_VIOLENCE = "我打你，弄死你！"                                   # r-violence → 一票否决
COMPLIANT = "我理解你，但请按规则处理。"                              # calm+legal+polite → 40 → -5

SCENARIO = "neighbor-noise"  # critsToPass=2，minorSafe=True


def _uid(prefix):
    """唯一后缀，避免重复运行撞 sessions 主键。"""
    return f"{prefix}_{int(time.time() * 1000)}"


# ------------------------------------------------------------------
# 终局路径
# ------------------------------------------------------------------

def test_path_crit_excellent():
    """暴击 ×2 → 优秀通关（RESOLVE，达成度 90）"""
    system = TrainerSystem()
    user = _uid("t_user1")
    sess = _uid("t_sess1")
    system.start_session(user, sess, SCENARIO, "adult")

    t1 = system.handle_turn(user, sess, SCENARIO, "adult", CRIT)
    assert t1.confrontation_value == 35, "暴击1 对峙值 50→35"
    assert t1.next_stage == Stage.PRESSURE, "暴击1 尚未通关（1<2）"

    t2 = system.handle_turn(user, sess, SCENARIO, "adult", CRIT)
    assert t2.confrontation_value == 20, "暴击2 对峙值 35→20"
    assert t2.next_stage == Stage.RESOLVE, "暴击2 达到 critsToPass → 优秀"

    r = system.end_session(user, sess, SCENARIO, "adult")
    assert r.goal_achieved is True
    assert r.achievement_score == 90


def test_path_redline_deadlock():
    """r-violence 红线 → 失控（DEADLOCK，达成度 30）"""
    system = TrainerSystem()
    user = _uid("t_user2")
    sess = _uid("t_sess2")
    system.start_session(user, sess, SCENARIO, "adult")

    t = system.handle_turn(user, sess, SCENARIO, "adult", RED_VIOLENCE)
    assert t.score.red_line_hits == ["r-violence"]
    assert t.score.total_score == 30, "红线一票否决 total=30"
    assert t.confrontation_value == 75, "红线对峙值 50→75"
    assert t.next_stage == Stage.DEADLOCK, "r-violence 直接失控"

    r = system.end_session(user, sess, SCENARIO, "adult")
    assert r.goal_achieved is False
    assert r.achievement_score == 30


def test_path_compliant_pass():
    """普通合规 ×10 → 及格通关（RESOLVE，达成度 65）"""
    system = TrainerSystem()
    user = _uid("t_user3")
    sess = _uid("t_sess3")
    system.start_session(user, sess, SCENARIO, "adult")

    last = None
    for i in range(1, 11):
        last = system.handle_turn(user, sess, SCENARIO, "adult", COMPLIANT)
        assert last.confrontation_value == 50 - 5 * i, f"第{i}回合对峙值 50-5*{i}"
    assert last.next_stage == Stage.RESOLVE, "压平但暴击不足 → 及格"

    r = system.end_session(user, sess, SCENARIO, "adult")
    assert r.goal_achieved is True
    assert r.achievement_score == 65


# ------------------------------------------------------------------
# 数据层落库
# ------------------------------------------------------------------

def test_storage_persistence():
    """sessions / turns / users 三表落库校验"""
    system = TrainerSystem()
    user = _uid("t_user4")
    sess = _uid("t_sess4")
    system.start_session(user, sess, SCENARIO, "adult")

    system.handle_turn(user, sess, SCENARIO, "adult", CRIT)
    system.handle_turn(user, sess, SCENARIO, "adult", CRIT)
    review = system.end_session(user, sess, SCENARIO, "adult")

    s = system.storage.get_session(sess)
    assert s["final_stage"] == Stage.RESOLVE
    assert s["goal_achieved"] == 1
    assert s["achievement_score"] == 90

    turns = system.storage.get_turns(sess)
    assert len(turns) == 2, "turns 落库 2 条"
    assert turns[0]["confrontation_value"] == 35
    assert turns[1]["confrontation_value"] == 20

    profile = system.storage.get_profile(user)
    assert profile.get("practice_count") == 1
    assert review.profile_update["practice_count"] == 1


# ------------------------------------------------------------------
# GSB 红线检测（RSB）
# ------------------------------------------------------------------

def test_gsb_red_lines():
    """四类红线关键词检测 + 一票否决"""
    kb = StrategyKB()
    assert kb.detect_red_line("你滚吧，废物！")["id"] == "r-insult"
    assert kb.detect_red_line("我打你，弄死你！")["id"] == "r-violence"
    assert kb.detect_red_line("我要曝光你身份证，人肉你！")["id"] == "r-illegal"
    assert kb.detect_red_line("你们国家都这样！")["id"] == "r-foreign"
    assert kb.detect_red_line("我理解你，请按规则处理。") is None

    # 一票否决：命中红线 → total_score 30、记 red_line_hits
    from judge_agent import JudgeAgent
    from scenario_store import ScenarioStore
    judge = JudgeAgent()
    scenario = ScenarioStore().get_scenario(SCENARIO)
    r = judge.judge(scenario, "adult", [], "你滚吧，废物！")
    assert r.total_score == 30
    assert r.red_line_hits == ["r-insult"]


# ------------------------------------------------------------------
# LLM 兜底降级（enable_llm_fallback=True 但无 key → 回退规则）
# ------------------------------------------------------------------

def test_llm_fallback_degrades_to_rules():
    """开关打开但无 key 时，roleplay / review 优雅降级到规则结果（不因 LLM 失败中断）"""
    # 强制无 key，保证确定性地走「降级到规则」路径，与本地是否配了 .env 无关
    saved_key = config.LLM_API_KEY
    config.LLM_API_KEY = ""
    try:
        system = TrainerSystem(enable_llm_fallback=True)
        user = _uid("t_user5")
        sess = _uid("t_sess5")
        system.start_session(user, sess, SCENARIO, "adult")

        # roleplay：无 key → ai_reply 必须是场景 lines 里的某句预写台词（规则回退）
        scenario = system.scenario_store.get_scenario(SCENARIO)
        all_lines = [l for tier_lines in scenario["lines"].values() for l in tier_lines]

        t1 = system.handle_turn(user, sess, SCENARIO, "adult", CRIT)
        assert t1.ai_reply in all_lines, f"无 key 应回退规则句，实际={t1.ai_reply}"

        # 打出 2 次暴击通关后，review 的 summary 应回退模板总结（非空、含「对峙值」）
        t2 = system.handle_turn(user, sess, SCENARIO, "adult", CRIT)
        assert t2.next_stage == Stage.RESOLVE
        r = system.end_session(user, sess, SCENARIO, "adult")
        assert r.summary and "对峙值" in r.summary, f"无 key 应回退模板总结，实际={r.summary}"
    finally:
        config.LLM_API_KEY = saved_key


# ------------------------------------------------------------------
# standalone runner（无 pytest 时也可跑）
# ------------------------------------------------------------------

def _run_all():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for t in tests:
        name = t.__name__
        try:
            t()
            print(f"  PASS  {name}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {name}: {e}")
            failed += 1
        except Exception:
            print(f"  ERROR {name}:")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    _run_all()
