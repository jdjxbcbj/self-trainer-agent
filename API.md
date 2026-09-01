# API 契约（v1 · 冻结）

「安全对线训练场」后端 HTTP API 的四端点契约。前端 `safety-confrontation-game/` 按此联调。

- Base URL：本地联调 `http://localhost:8000`
- 启动：`py -m uvicorn api:app --port 8000 --reload`
- 数据格式：JSON；请求 / 响应均为 UTF-8。
- 用户区分：**无登录**。前端用 localStorage 生成随机 `user_id`（任意字符串）传入，后端不校验格式。
- 会话归属：`POST /sessions` 由**后端**生成 `session_id`，前端保存它；后续 turn / end 只用 `session_id`。
- 错误约定：参数非法 → `400 {"detail": "..."}`；场景 / 会话不存在 → `404 {"detail": "..."}`。

## 枚举

- `audience`：`"minor"`（青少年，仅 minorSafe 场景）| `"adult"`（成年人，全场景）
- `next_stage`：`"opening"` | `"pressure"` | `"resolve"`（通关）| `"deadlock"`（失控）| `"end"`（到时）
  - 终局（`resolve` / `deadlock` / `end`）后，前端应调 `POST /sessions/{sid}/end` 触发复盘。

## 1. GET /scenarios

列出可用场景。

- Query（可选）：`audience` = `"minor"` 只返回 minorSafe 场景；缺省或 `"adult"` 返回全部。
- 200 响应：场景对象数组，每个场景字段：
  - `id`、`moduleId`、`title`、`premise`、`personaName`、`opening`（均 string）
  - `riskLevel`（`"low"|"medium"|"high"`）、`minorSafe`（bool）、`critsToPass`（int）
  - `laws`（string[]）、`criteria`（string[]）、`hint`（string）
  - `lines`（object）：`{"low": [...], "mid": [...], "high": [...], "yield": [...]}`，四档 NPC 台词（各 string[]）
- 示例：`GET /scenarios?audience=minor`

## 2. POST /sessions

开新会话（落库 + 开场白 + 教学卡）。

- Body：`{"user_id": string, "scenario_id": string, "audience": "minor"|"adult"}`
- 200 响应：

```json
{
  "session_id": "3f9c…",
  "opening": "就这点声音你也要管？……",
  "teaching_card": {
    "title": "表达边界", "when": "……", "how": "……",
    "why": "……", "scenario_id": "neighbor-noise", "example": "……"
  }
}
```

- 错误：400（audience 非法）、404（scenario_id 不存在）

## 3. POST /sessions/{session_id}/turns

处理一次用户回合（评分 + NPC 回应 + 实时提示 + 阶段判定 + 落库）。

- Body：`{"user_response": string}`
- 200 响应：

```json
{
  "score": {
    "total_score": 100,
    "dimensions": {"表达边界": 100, "……": 0},
    "red_line_hits": [],
    "feedback": "……",
    "suggested_strategy": "……"
  },
  "ai_reply": "大家都能忍，怎么就你不行？",
  "confrontation_value": 35,
  "next_stage": "pressure",
  "teaching_hint": "……（收尾回合为 null）"
}
```

- `score.dimensions`：object，键为维度中文名，值为 0~100 整数。
- `red_line_hits`：命中红线 ID 数组（可空）。
- `confrontation_value`：0~100 整数，本回合「更新后」的对峙值（前端对峙值条直接用）。
- `teaching_hint`：string 或 null。
- 错误：404（session_id 不存在或已结束）

## 4. POST /sessions/{session_id}/end

结束会话并复盘（落库 sessions + 更新画像）。

- Body：无
- 200 响应：

```json
{
  "summary": "整场对话对峙值从 50 走到 20，终局为优秀通关，共打出 2 次暴击。",
  "goal_achieved": true,
  "achievement_score": 90,
  "weak_points": ["可再补齐取证/求助环节"],
  "profile_update": {"practice_count": 1, "latest_weak_point": "……"}
}
```

- 错误：404（session_id 不存在或已结束）

## 前端联调最小流程

1. `GET /scenarios?audience=<身份>` 拿场景列表。
2. 用户选场景后 `POST /sessions`（`user_id` = localStorage 随机 uid）。
3. 每轮用户输入 → `POST /sessions/{sid}/turns`：用 `ai_reply` 渲染 NPC、`confrontation_value` 更新对峙值条、`next_stage` 判断是否终局。
4. `next_stage` ∈ {`resolve`, `deadlock`, `end`} → `POST /sessions/{sid}/end` 渲染复盘。
