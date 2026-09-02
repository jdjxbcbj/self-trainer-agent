# -*- coding: utf-8 -*-
"""
smoke_api.py - API 层冒烟测试（Wave 3）

直接调用 api.py 的端点函数（不经 uvicorn），验证：
- FastAPI app + TrainerSystem(enable_llm_fallback=True) 能正常装配
- /scenarios 过滤、/sessions 开新会话、/turns 处理回合、/end 复盘全链路
- asdict 序列化 dataclass 正确、session_id -> 上下文映射正确

真实 HTTP 联调：uvicorn api:app --reload 后 curl，或前端直接调。
"""
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import api
from api import StartRequest, TurnRequest

CRIT = "我理解你，但我不接受这种说法，请停止。我会保持距离，按规则处理，保留记录，并求助物业工作人员。"


def main():
    # 场景列表（成年人：全部）
    all_scenarios = api.list_scenarios("adult")
    print(f"成人场景数：{len(all_scenarios)}")

    # 开新会话
    started = api.start_session(
        StartRequest(user_id="smoke_user", scenario_id="neighbor-noise", audience="adult")
    )
    sid = started["session_id"]
    print(f"session_id={sid}")
    print(f"开场白：{started['opening']}")
    print(f"教学卡标题：{started['teaching_card']['title']}")

    # 第一次暴击（未通关）
    t = api.handle_turn(sid, TurnRequest(user_response=CRIT))
    print(f"回合1：stage={t['next_stage']}，score={t['score']['total_score']}，ai_reply={t['ai_reply']}")

    # 第二次暴击 → 优秀通关（critsToPass=2）
    t2 = api.handle_turn(sid, TurnRequest(user_response=CRIT))
    print(f"回合2：stage={t2['next_stage']}，score={t2['score']['total_score']}，ai_reply={t2['ai_reply']}")

    # 结束复盘
    r = api.end_session(sid)
    print(f"复盘：achieved={r['goal_achieved']}，达成度={r['achievement_score']}")
    print(f"总结：{r['summary']}")

    # 会话不存在的错误路径
    try:
        api.handle_turn("no-such-session", TurnRequest(user_response="你好"))
        print("✗ 未知会话未报错")
    except Exception as e:
        print(f"✓ 未知会话正确报错：{e}")

    print("\n✅ API 直调冒烟通过")

    test_http()


def test_http():
    """真实 HTTP 层验证（TestClient 走 Starlette 路由 + CORS + JSON 序列化）"""
    from fastapi.testclient import TestClient

    client = TestClient(api.app)

    r = client.get("/scenarios", params={"audience": "adult"})
    assert r.status_code == 200
    print(f"HTTP GET /scenarios -> {r.status_code}，场景数={len(r.json())}")

    r = client.post(
        "/sessions",
        json={"user_id": "http_user", "scenario_id": "neighbor-noise", "audience": "adult"},
    )
    assert r.status_code == 200
    sid = r.json()["session_id"]
    print(f"HTTP POST /sessions -> {r.status_code}，session_id={sid}")

    r = client.post(f"/sessions/{sid}/turns", json={"user_response": CRIT})
    assert r.status_code == 200
    turn = r.json()
    print(f"HTTP POST turns -> {r.status_code}，score={turn['score']['total_score']}，stage={turn['next_stage']}")

    r = client.post(f"/sessions/{sid}/end")
    assert r.status_code == 200
    review = r.json()
    print(f"HTTP POST end -> {r.status_code}，achieved={review['goal_achieved']}")

    # B3：结束后会话已清理，再调 /turns 应 404
    r = client.post(f"/sessions/{sid}/turns", json={"user_response": "再试一次"})
    print(f"HTTP 结束后 turns -> {r.status_code}（应 404）")
    assert r.status_code == 404

    r = client.post("/sessions/nope/turns", json={"user_response": "hi"})
    print(f"HTTP 未知会话 -> {r.status_code}")

    print("✅ HTTP 冒烟通过")


if __name__ == "__main__":
    main()
