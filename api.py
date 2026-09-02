# -*- coding: utf-8 -*-
"""
api.py - HTTP API 层（Wave 3）

用 FastAPI 把 TrainerSystem 暴露成 REST 接口，供前端「安全对线训练场」本地联调：

    GET  /scenarios                      列出可用场景（可选 ?audience=minor|adult 过滤）
    POST /sessions                       开新会话（后端生成 session_id，返回开场白+教学卡）
    POST /sessions/{session_id}/turns    处理一次用户回合
    POST /sessions/{session_id}/end      结束会话并复盘

约定（与「本地联调优先」对齐）：
- 用户区分：不做登录，由前端用随机 uid（localStorage）当 user_id 传入，见 PLAN §9。
- 会话归属：后端在 start 时生成 session_id，并在进程内记录 session_id -> (user_id/scenario/audience)，
  后续 turn/end 只需带 session_id。
- LLM 兜底：默认关（规则路径瞬时）；设 LLM_FALLBACK_ENABLED=1 才启用，无 key 时自动回退规则，
  不影响接口。
- 并发：本地单用户联调为主，用一把进程内锁串行化，避免 memory/计数器竞态；上云前需改造为
  请求级隔离（多用户/多会话并发时，当前 Router 的进程内状态并不隔离）。

启动：uvicorn api:app --reload   （或 py -m uvicorn api:app --reload）
"""

import sys
import threading
import uuid
from dataclasses import asdict
from typing import Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import config
from contracts import Audience
from main import TrainerSystem


app = FastAPI(title="安全对线训练场 API", version="0.1.0")

# 本地联调放开跨域；无登录/无 cookie，故 allow_credentials=False（避免与 "*" 冲突）。
# 上云前收紧 allow_origins 为具体前端域名。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 长生命周期训练系统（进程内单例）。LLM 兜底默认关（规则路径瞬时）；
# 设 LLM_FALLBACK_ENABLED=1 才启用（有 key 用 LLM、无 key 回退规则）。
system = TrainerSystem(enable_llm_fallback=config.LLM_FALLBACK_ENABLED)

# 会话上下文：session_id -> {"user_id", "scenario_id", "audience"}（仅本进程内存，重启即失）
_sessions = {}

# 串行化锁：Router/SessionMemory/计数器非线程安全，本地联调单用户够用，上云前再改造。
_lock = threading.Lock()


# ----------------------------------------------------------------------
# 请求模型
# ----------------------------------------------------------------------

class StartRequest(BaseModel):
    user_id: str
    scenario_id: str
    audience: str  # "minor" | "adult"


class TurnRequest(BaseModel):
    user_response: str


def _valid_audience(audience: str) -> bool:
    return audience in (Audience.MINOR, Audience.ADULT)


# ----------------------------------------------------------------------
# 路由
# ----------------------------------------------------------------------

@app.get("/scenarios")
def list_scenarios(audience: Optional[str] = None):
    """列出可用场景。audience=minor 时仅返回 minorSafe 场景（场景隔离，见 §9 决策 #9）。"""
    if audience is not None and not _valid_audience(audience):
        raise HTTPException(status_code=400, detail="audience 必须是 minor 或 adult")
    return system.scenario_store.list_scenarios(audience)


@app.post("/sessions")
def start_session(req: StartRequest):
    """开新会话：落库 + NPC 开场白 + 教学卡。返回 session_id 供后续 turn/end 使用。"""
    if not _valid_audience(req.audience):
        raise HTTPException(status_code=400, detail="audience 必须是 minor 或 adult")

    session_id = uuid.uuid4().hex
    with _lock:
        try:
            opening, card = system.start_session(
                req.user_id, session_id, req.scenario_id, req.audience
            )
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))
        _sessions[session_id] = {
            "user_id": req.user_id,
            "scenario_id": req.scenario_id,
            "audience": req.audience,
        }
    return {
        "session_id": session_id,
        "opening": opening,
        "teaching_card": asdict(card),
    }


@app.post("/sessions/{session_id}/turns")
def handle_turn(session_id: str, req: TurnRequest):
    """处理一次用户回合：评分 + NPC 回应 + 实时提示 + 阶段判定 + 落库。"""
    ctx = _sessions.get(session_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail="会话不存在或已结束，请重新 start")
    with _lock:
        result = system.handle_turn(
            ctx["user_id"], session_id, ctx["scenario_id"], ctx["audience"], req.user_response
        )
    return asdict(result)


@app.post("/sessions/{session_id}/end")
def end_session(session_id: str):
    """结束会话并复盘：返回总结 + 是否通关 + 达成度 + 画像增量。"""
    ctx = _sessions.get(session_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail="会话不存在或已结束，请重新 start")
    with _lock:
        result = system.end_session(
            ctx["user_id"], session_id, ctx["scenario_id"], ctx["audience"]
        )
        _sessions.pop(session_id, None)
    return asdict(result)
