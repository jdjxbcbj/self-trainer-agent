# -*- coding: utf-8 -*-
"""
storage.py - 数据层（统一封装 SQLite 连接与迁移）

把散落的 sqlite3 连接收敛到一处，负责：
- 建表 + 迁移（schema_version 追踪版本，migrate() 幂等跑增量）
- 会话/回合持久化（sessions / turns 表）
- 用户画像（users 表，替代 profile.py 的单表）

四张表：schema_version / users / sessions / turns（见 PLAN.md §6.2）。

为什么「短连接」：sqlite3 连接非线程安全，每次操作新建连接，
避免共享连接在多 Agent 并发下的隐患（沿用 profile.py 的做法）。
"""

import json
import os
import sqlite3
from datetime import datetime

import config


# 数据库文件与本模块放在同一目录，避免依赖当前工作目录
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trainer.db")


# 迁移脚本：按版本号递增。schema_version 记录已应用版本，migrate() 幂等跑增量。
MIGRATIONS = [
    # 版本 1：初始建表（四张表，见 PLAN.md §6.2）
    """
    CREATE TABLE IF NOT EXISTS schema_version (
        version    INTEGER PRIMARY KEY,
        applied_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS users (
        user_id      TEXT PRIMARY KEY,
        audience     TEXT NOT NULL DEFAULT 'adult',
        profile_json TEXT,
        created_at   TEXT NOT NULL,
        updated_at   TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS sessions (
        session_id        TEXT PRIMARY KEY,
        user_id           TEXT NOT NULL REFERENCES users(user_id),
        scenario_id       TEXT NOT NULL,
        audience          TEXT NOT NULL,
        status            TEXT NOT NULL DEFAULT 'active',
        final_stage       TEXT,
        achievement_score INTEGER,
        goal_achieved     INTEGER,
        created_at        TEXT NOT NULL,
        ended_at          TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

    CREATE TABLE IF NOT EXISTS turns (
        turn_id              INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id           TEXT NOT NULL REFERENCES sessions(session_id),
        turn_index           INTEGER NOT NULL,
        user_response        TEXT NOT NULL,
        ai_reply             TEXT,
        score_total          INTEGER,
        score_dimensions     TEXT,
        red_line_hits        TEXT,
        confrontation_value  INTEGER,
        persona_state        TEXT,
        teaching_hint        TEXT,
        next_stage           TEXT,
        created_at           TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_id);
    """,
]


class Storage:
    """数据层唯一入口：统一封装 SQLite 连接、建表、迁移。"""

    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH
        self.migrate()

    # ------------------------------------------------------------------
    # 迁移
    # ------------------------------------------------------------------

    def migrate(self):
        """按顺序应用未执行的迁移脚本（幂等）。"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            current = self._current_version(conn)
            for version, script in enumerate(MIGRATIONS, start=1):
                if version <= current:
                    continue
                conn.executescript(script)
                conn.execute(
                    "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                    (version, self._now()),
                )
                print(f"[Storage] 已应用迁移 v{version}")
            conn.commit()
        finally:
            conn.close()

    def _current_version(self, conn):
        """读取当前已应用的迁移版本（schema_version 表不存在则视为 0）。"""
        try:
            row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
            return row[0] or 0
        except sqlite3.OperationalError:
            return 0

    # ------------------------------------------------------------------
    # 会话 / 回合
    # ------------------------------------------------------------------

    def create_session(self, session_id, user_id, scenario_id, audience):
        """开新会话：写一条 status=active 的 sessions 行（见 PLAN.md §6.3）。"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT INTO sessions (session_id, user_id, scenario_id, audience, status, created_at)
                VALUES (?, ?, ?, ?, 'active', ?)
                """,
                (session_id, user_id, scenario_id, audience, self._now()),
            )
            conn.commit()
        finally:
            conn.close()
        print(f"[Storage] 已创建会话：session={session_id}，scenario={scenario_id}")

    def write_turn(self, session_id, turn):
        """追加一回合到 turns 表（handle_turn 每次调用，只追加，不改 sessions）。

        参数:
            turn: dict，键为 turn_index / user_response / ai_reply / score_total /
                  score_dimensions / red_line_hits / confrontation_value /
                  persona_state / teaching_hint / next_stage（见 §6.2 turns 表）。
        """
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT INTO turns (
                    session_id, turn_index, user_response, ai_reply, score_total,
                    score_dimensions, red_line_hits, confrontation_value,
                    persona_state, teaching_hint, next_stage, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    turn.get("turn_index"),
                    turn.get("user_response"),
                    turn.get("ai_reply"),
                    turn.get("score_total"),
                    json.dumps(turn.get("score_dimensions") or {}, ensure_ascii=False),
                    json.dumps(turn.get("red_line_hits") or [], ensure_ascii=False),
                    turn.get("confrontation_value"),
                    json.dumps(turn.get("persona_state") or {}, ensure_ascii=False),
                    turn.get("teaching_hint"),
                    turn.get("next_stage"),
                    self._now(),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        print(f"[Storage] 已写入回合：session={session_id}，turn_index={turn.get('turn_index')}")

    def end_session(self, session_id, review, final_stage):
        """结束会话：sessions 标 ended + 写复盘结论。

        参数:
            review: ReviewResult（含 achievement_score / goal_achieved）
            final_stage: 终局阶段（Stage 常量之一，由调用方 router 传入）
        """
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                UPDATE sessions SET
                    status = 'ended',
                    final_stage = ?,
                    achievement_score = ?,
                    goal_achieved = ?,
                    ended_at = ?
                WHERE session_id = ?
                """,
                (
                    final_stage,
                    review.achievement_score,
                    1 if review.goal_achieved else 0,
                    self._now(),
                    session_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        print(f"[Storage] 已结束会话：session={session_id}，final_stage={final_stage}")

    def get_session(self, session_id):
        """读取某条会话（返回 dict 或 None）。"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        finally:
            conn.close()
        return dict(row) if row else None

    def get_turns(self, session_id):
        """读取某会话的全部回合（按 turn_index 升序）。"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM turns WHERE session_id = ? ORDER BY turn_index", (session_id,)
            ).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # 用户画像（替代 profile.py）
    # ------------------------------------------------------------------

    def upsert_user(self, user_id, audience):
        """新增/更新用户（首次进入时调用）；已存在则只更新 audience，不覆盖 profile_json。"""
        conn = sqlite3.connect(self.db_path)
        try:
            now = self._now()
            conn.execute(
                """
                INSERT INTO users (user_id, audience, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    audience = excluded.audience,
                    updated_at = excluded.updated_at
                """,
                (user_id, audience, now, now),
            )
            conn.commit()
        finally:
            conn.close()
        print(f"[Storage] 已 upsert 用户：user={user_id}，audience={audience}")

    def get_profile(self, user_id):
        """读取指定用户画像（不存在返回空 dict {}）。"""
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT profile_json FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
        finally:
            conn.close()
        if row is None or row[0] is None:
            return {}
        return json.loads(row[0])

    def update_profile(self, user_id, update):
        """增量更新用户画像：读出现有画像，浅合并 update，再写回（沿用 profile.py 语义）。"""
        existing = self.get_profile(user_id)
        existing.update(update)

        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "UPDATE users SET profile_json = ?, updated_at = ? WHERE user_id = ?",
                (json.dumps(existing, ensure_ascii=False), self._now(), user_id),
            )
            conn.commit()
        finally:
            conn.close()
        print(f"[Storage] 已更新用户 {user_id} 画像")

    # ------------------------------------------------------------------
    # 工具
    # ------------------------------------------------------------------

    def _now(self):
        """当前时间戳（ISO 8601，秒级精度）。"""
        return datetime.now().isoformat(timespec="seconds")
