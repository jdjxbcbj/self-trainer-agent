# safe-trainer 多 Agent 后端 · 架构与开发规划 v2（最终版）

> 版本：v2（修正 v1 的两处前提错误 + 补充并行开发编排模型）
> 状态：**待最终确认**
> 日期：2026-08-27
> 定位：回答「要做哪些模块、职责边界、接口长什么样、按什么顺序开发、怎么并行开发」。批准后即作为开发依据。

---

## 0. 一句话结论

**当前唯一在开发的项目是 `self-trainer-agent/`（纯 Python 多 Agent 后端），评分模块已跑通。下一步不是堆代码，而是先「冻结接口契约」，再把各模块拆给子 Agent 并行开发，最后由本对话（主控）集成。**

`safe-trainer/` 目录是早期 Vite 前端尝试，**不作为联调目标**，仅复用其方法论（关系维护意愿光谱、教学卡三字段），代码不整合。

---

## 1. 范围与前提（本次已纠正）

### 1.1 项目边界

| 项 | 结论 |
|---|---|
| 开发中的项目 | **只有 `self-trainer-agent/` 一个**（纯 Python 多 Agent 后端） |
| 前端 | **无「现有前端」**。未来前端是另一期工作，本期只做后端 |
| `safe-trainer/`（Vite + JS） | 早期尝试，历史参考。方法论可复用，代码不整合、不迁移 |
| 评分模块 7 文件 | ✅ 已完成，纳入整体架构，作为「格式/日志/注释规范」样板 |
| 开发模型 | **本对话 = 主控（orchestrator）；各模块 = 子 Agent（subagent）并行开发** |

### 1.2 已交付：评分模块（现状盘点）

`self-trainer-agent/` 现有 7 个文件，已通过命令行实测（真实 DeepSeek API 调用成功）：

| 文件 | 职责 | 状态 |
|---|---|---|
| `config.py` | 全局配置，API Key 从环境变量 `LLM_API_KEY` 读取 | ✅ |
| `scenario_store.py` | 场景数据（`wang_ayi_cuihun`） | ✅ 需小幅扩展（补 persona_params） |
| `strategy_kb.py` | 约束→策略/高低分特征/评分维度权重 | ✅ |
| `memory.py` | 会话级消息历史（纯内存 `defaultdict`） | 🟡 需扩展（persona_state/阶段） |
| `judge_agent.py` | 评分 Agent 核心（构造 prompt→调 LLM→解析） | ✅ |
| `main.py` | `ScoreSystem` 主链路编排 | 🟡 需演化为总编排 |
| `cli.py` | 命令行交互入口 | ✅ |

**必须被后续模块对齐的规范**（样板）：
- 每步日志：`[模块名] 步骤N - 动作`，如 `[JudgeAgent] 步骤3 - 调用LLM评分...`。
- 模拟模式兜底：无 Key / 无 openai / 调用失败 / JSON 解析失败 → 全部回退固定模拟结果，开箱即用。
- 中文注释 + UTF-8 控制台适配（`sys.stdout.reconfigure`）。
- 评分 Agent「不生成对话」——仅指评分 Agent 本身不生成；后端整体生成王阿姨回应的职责归「场景扮演 Agent」。

---

## 2. 总体架构

```
┌──────────────────────────────────────────────────────────────┐
│  CLI（cli.py，开发期入口）/ 未来 HTTP API（本期不做）              │
└──────────────┬───────────────────────────────────────────────┘
               ▼
┌──────────────────────────────────────────────────────────────┐
│  编排层                                                       │
│  router.py     编排路由：对话阶段状态机 + Agent 调度             │
│  main.py       总装配：初始化各组件，对外统一入口（TrainerSystem）│
└──────────────┬───────────────────────────────────────────────┘
               │ 按阶段调度
               ▼
┌──────────────────────────────────────────────────────────────┐
│  Agent 层                                                     │
│  ├─ judge_agent.py    评分 Agent    ✅ 回合级打分 + 反馈        │
│  ├─ roleplay_agent.py 场景扮演 Agent ⬜ 生成王阿姨回应+状态       │
│  ├─ teaching_agent.py 教学 Agent    ⬜ 教学卡 + 实时提示         │
│  └─ review_agent.py   复盘 Agent    ⬜ 会话总结+目标达成+画像     │
└──────────────┬───────────────────────────────────────────────┘
               │ 读写
               ▼
┌──────────────────────────────────────────────────────────────┐
│  支撑层                                                       │
│  ├─ contracts.py       接口契约（唯一真源，并行开发的地基）       │
│  ├─ memory.py          短时记忆（会话消息+persona_state+阶段）   │
│  ├─ profile.py         长时记忆（用户画像，SQLite）              │
│  ├─ knowledge_base.py  知识库（方法论/法条/场景，内容层）         │
│  ├─ scenario_store.py  场景数据（含性格参数）                    │
│  └─ strategy_kb.py     策略库（约束→评分标准，规则层）            │
└──────────────────────────────────────────────────────────────┘
```

图例：✅ 已完成　🟡 部分完成　⬜ 未开始

---

## 3. 模块职责与边界（逐个定死）

### 3.1 接口契约 `contracts.py` —— ⬜ 新增，**并行开发的地基**

**为什么它排第一**：并行开发最大的风险不是「某模块难」，而是「两个模块各写各的，接口对不上」。`contracts.py` 是**唯一真源**——所有数据形状、函数签名、常量枚举都定义在这里，所有子 Agent 开工前先读它，只按它的签名实现，不改它的定义。

包含：
- 阶段枚举 `Stage`（见 §4.1）
- 约束 ID + 中文名映射（4 档，见 §4.4）
- 数据类：`SessionMessage` / `ScoreResult` / `TurnResult` / `TeachingCard` / `ReviewResult` / `PersonaState`
- 各 Agent 的**方法签名**（见 §5，只定义签名和 docstring，不实现）

> 唯一允许改动 `contracts.py` 的是主控（本对话）。子 Agent 只读。

### 3.2 评分 Agent `judge_agent.py` —— ✅ 已完成

**职责**：回合级打分。判「这一句回应，在该约束下好不好」，输出分数 + 反馈 + 建议策略。
**不负责**：生成王阿姨回应、判「整场目标达成」、给教学卡。
**联调时的小改动**：`suggested_strategy` 字段保留（CLI 演示用），等教学 Agent 上线后统一由教学 Agent 出「下一轮怎么练」，评分只出分数 + 反馈。评分 Agent 本体不改。

### 3.3 场景扮演 Agent `roleplay_agent.py` —— ⬜ 新增

**职责**：生成「王阿姨」的下一句回应，并输出**下一轮的 persona_state**。

**关键设计：静态性格参数 vs 动态状态分离**

- **静态参数**（写死在 `scenario_store.py`，不可变，是人设常量）：
  ```python
  "persona_params": {
      "催婚执念度": 0.7,   # 越高越容易绕回催婚
      "面子敏感度": 0.8,   # 越高越在意晚辈是否"懂事"
      "容易被转移度": 0.4, # 越高越容易接转移话题的茬
      "情绪波动": 0.3,     # 越高越容易被激怒/哄好
  }
  ```
- **动态状态 `persona_state`**（随会话存进记忆，每轮由扮演 Agent 输出下一轮值）：
  ```python
  {
      "emotion": 0.3,       # 当前情绪 0~1
      "patience": 0.6,      # 当前耐心 0~1，越低越容易绕回催婚
      "deflect_count": 0,   # 已被转移话题成功的次数（影响语气/绕回概率）
  }
  ```

**为什么这么分**：静态参数是「这个人是什么样」，动态状态是「这个人现在怎么样」。LLM 不擅长做概率跳转，所以把「下一轮状态」也交给 LLM 输出、由代码**夹紧到 0~1 范围**校验。扮演 Agent 的 prompt 同时给静态参数 + 当前状态，让它既「演得像」又「记得上一轮发生了什么」。

### 3.4 教学 Agent `teaching_agent.py` —— ⬜ 新增

**职责**：
- `get_card`：进场景时按约束**预生成**一张教学卡（缓存，非每轮调用）。
- `get_hint`：回合中实时提示（规则/缓存优先，避免每轮一次 LLM 调用造成延迟）。

**教学卡 schema**（补上 v1 缺失的字段定义）：
```python
TeachingCard = {
    "title":      "转移话题",               # 招式名
    "when":       "对方没恶意、只是热情过头…",  # 什么时候用
    "how":        "不接催婚的球，把话头抛回对方得意的事，例：…",  # 怎么用（含1个例子）
    "why":        "不正面顶=不给把柄，不让冷场=关系不破",          # 为什么
    "constraint": "want_maintain",          # 该招式在哪个约束下是正解
    "example":    "阿姨您别光说我，尝尝这个菜。表姐最近怎么样啦？"
}
```

**与评分 Agent 的边界（裁决）**：
- 教学 = 回合**前/中**的主动教练；评分 = 回合**后**的被动反馈。
- `suggested_strategy` 最终归教学 Agent 出；评分 Agent 保留字段仅作兼容。

### 3.5 复盘 Agent `review_agent.py` —— ⬜ 新增

**职责**：会话**结束后**触发，产出会话总结 + 目标达成判定 + 更新用户画像。

**触发条件**（任一满足即结束会话，见 §4.1 状态机）：
- 用户主动退出；或 达到 `round_limit`；或 进入 `resolve`/`deadlock` 终态。

**「目标达成制」的归属（裁决）**：
- 评分 Agent = **回合级**：判单句质量。
- 复盘 Agent = **会话级**：判「整场是否守住边界/达成该约束目标」，输出 `goal_achieved` + `achievement_score`（0-100），并把回合分加权汇总。
- 这样 PRD 的「目标达成制」落在复盘 Agent，而不是挤进评分 Agent。

**产出**：`summary`（总结）+ `weak_points`（薄弱点）+ `profile_update`（写入长时画像的增量）。

### 3.6 记忆系统 —— 🟡 拆两层

| 层 | 文件 | 内容 | 生命周期 | 现状 |
|---|---|---|---|---|
| 短时 `SessionMemory` | `memory.py` | 会话消息 + `persona_state` + 当前阶段 | 会话内 | 🟡 需加 persona_state/阶段字段 |
| 长时 `UserProfile` | `profile.py` | 画像：约束偏好、练习次数、薄弱点、历史达成度 | 跨会话 | ⬜ 新增 |

- `profile.py` 用 **SQLite**（标准库 `sqlite3`，够用，不引 Redis/向量库），存用户画像。
- 画像由**复盘 Agent 在会话结束时更新**，评分/教学/扮演只读。

### 3.7 知识库 `knowledge_base.py` —— ⬜ 新增

**与 `strategy_kb.py` 的分层（裁决）**：
- `strategy_kb.py` = **规则层**：约束→策略→评分维度权重，评分/教学直接消费。✅ 已有。
- `knowledge_base.py` = **内容层**：方法论文案、法条、场景扩展内容，供教学卡和复盘引用。⬜ 新增。

**检索方式**：第一阶段**结构化硬编码**（和 `strategy_kb` 一样），RAG/向量检索后置——当前数据量不配引入向量库，属过度设计。
**法条范围**：按场景挂载，不提前铺（当前催婚场景法条几乎用不上）。

### 3.8 编排路由 `router.py` —— ⬜ 新增，**主控优先交付**

**职责**：对话阶段状态机（§4.1）+ 按阶段调度 Agent（§4.2 回合流）。只调度，不自己打分/生成对话。

---

## 4. 核心数据契约

### 4.1 对话阶段状态机（裁决：规则优先）

```
opening（寒暄） → pressure（催婚施压） → [用户回应]
                                            │
                  ┌─────────────────────────┤
                  │ 转移成功          │ 转移失败/顶撞        │ 划界成功      │ 情绪失控
                  ▼                   ▼                     ▼              ▼
              pressure（绕回）   pressure（升级）        resolve        deadlock
                                                                  │
                  ┌───────────────────────────────────────────────┘
                  ▼
                end → 触发复盘
```

阶段判定用**规则**（关键词 + `persona_state` 阈值 + `deflect_count` + `round_limit`），LLM 分类器后置。规则可预测、零成本、可调试，符合当前学习阶段。

### 4.2 一次用户回合的流程（所有 Agent 的协作骨架）

```
输入：user_response（+ user_id / session_id / scenario_id / constraint）

Router.handle_turn：
  1. 读 SessionMemory：历史 + persona_state + 阶段
  2. 评分：judge_agent.judge(...) → ScoreResult
  3. 扮演：roleplay_agent.reply(...) → (王阿姨回应, next_persona_state)
  4. 教学：teaching_agent.get_hint(...) → 实时提示（可空，规则/缓存）
  5. 判定下一阶段（状态机）
  6. 写记忆：user 回应 + 王阿姨回应 + next_persona_state + next_stage
  7. 返回 TurnResult

会话结束 Router.end_session：
  → review_agent.review(...) → ReviewResult + 更新 UserProfile
```

### 4.3 `TurnResult` 返回结构（前端/CLI 一次拿全）

```json
{
  "score": { "total_score": 75, "dimensions": {...}, "feedback": "...", "suggested_strategy": "..." },
  "ai_reply": "哎呀广场舞是挺好…不过婚事也该抓紧了",
  "next_persona_state": { "emotion": 0.35, "patience": 0.55, "deflect_count": 1 },
  "next_stage": "pressure",
  "teaching_hint": "王阿姨绕回来了，试试软边界表达"
}
```

### 4.4 约束 ID（唯一真源，4 档，写在 `contracts.py`）

| ID | 中文名 |
|---|---|
| `want_maintain` | 想维持关系 |
| `endure_but_record` | 能忍但记账 |
| `dont_care` | 无所谓 |
| `want_cutoff` | 想断联 |

> 这是「关系维护意愿」4 档光谱，与 `strategy_kb.py` 现有 4 约束一致。之前误把 `safe-trainer/` 的 3 档当联调目标，作废。

---

## 5. 接口契约（`contracts.py` 蓝图，签名级）

> 子 Agent 只实现这些签名，不改签名。主控先冻结此文件。

```python
# 数据类
@dataclass
class SessionMessage:
    role: str          # "user" | "ai"
    content: str

@dataclass
class ScoreResult:
    total_score: int
    dimensions: dict   # {维度中文名: 0-100}
    feedback: str
    suggested_strategy: str

@dataclass
class TurnResult:
    score: ScoreResult
    ai_reply: str
    next_persona_state: dict
    next_stage: str
    teaching_hint: str | None

@dataclass
class TeachingCard:
    title: str; when: str; how: str; why: str
    constraint: str; example: str

@dataclass
class ReviewResult:
    summary: str
    goal_achieved: bool
    achievement_score: int   # 0-100 会话级
    weak_points: list
    profile_update: dict

# 方法签名（只定义，不实现）
class JudgeAgent:        # ✅ 已实现
    def judge(self, scenario, constraint, history, user_response) -> ScoreResult: ...

class RoleplayAgent:     # ⬜
    def reply(self, scenario, constraint, history, user_response, persona_state) -> tuple[str, dict]: ...
    # 返回 (王阿姨回应, 下一轮 persona_state)

class TeachingAgent:     # ⬜
    def get_card(self, scenario_id, constraint) -> TeachingCard: ...
    def get_hint(self, scenario, constraint, stage, history) -> str: ...

class ReviewAgent:       # ⬜
    def review(self, session_id, user_id, scenario, constraint, history, profile) -> ReviewResult: ...

class SessionMemory:     # 🟡 扩展
    def add_message(self, session_id, role, content): ...
    def get_context(self, session_id, limit=None) -> list: ...
    def get_persona_state(self, session_id) -> dict: ...
    def set_persona_state(self, session_id, state): ...
    def get_stage(self, session_id) -> str: ...
    def set_stage(self, session_id, stage): ...
    def clear(self, session_id): ...

class UserProfile:       # ⬜
    def get(self, user_id) -> dict: ...
    def update(self, user_id, update) -> None: ...

class KnowledgeBase:     # ⬜
    def get_method(self, constraint, strategy) -> dict: ...
    def get_legal(self, scenario_id) -> list: ...

class Router:            # ⬜
    def handle_turn(self, user_id, session_id, scenario_id, constraint, user_response) -> TurnResult: ...
    def end_session(self, user_id, session_id, scenario_id, constraint) -> ReviewResult: ...
```

---

## 6. 并行开发编排（主控 + 子 Agent）

**模型**：本对话 = 主控，定义契约、拆任务、集成；子 Agent = 各自实现一个模块，**只改自己的文件**，互不冲突。

### 6.1 为什么不需要 worktree

- 各模块文件**完全不相交**（见下表），子 Agent 各改各的文件，不存在同一文件并发写。
- worktree 是「同一仓库内隔离并行改动」的工具；这里靠「契约冻结 + 文件不相交」就够，**不需要 worktree**。
- 若后续要隔离「实验性重构」再考虑 worktree，当前不必。

### 6.2 开发波浪（Wave）

**Wave 0 —— 主控串行（冻结契约）**
- 写 `contracts.py`（数据类 + 枚举 + 方法签名，即 §5）。
- 给每个新模块写**骨架桩**（签名 + 中文 docstring + `raise NotImplementedError`）。
- 扩展 `scenario_store.py` 补 `persona_params`（小改，主控自己做，避免和子 Agent 抢文件）。
- 产出：所有子 Agent 开工前必读的契约。

**Wave 1 —— 子 Agent 并行（6 个同时）**

| 子 Agent | 负责文件 | 依赖（只读） |
|---|---|---|
| S1 知识库 | `knowledge_base.py` | contracts, strategy_kb |
| S2 记忆 | `memory.py`（扩展）+ `profile.py` | contracts, config |
| S3 扮演 | `roleplay_agent.py` | contracts, scenario_store, config |
| S4 教学 | `teaching_agent.py` | contracts, strategy_kb, knowledge_base(S1，接口约定即可) |
| S5 复盘 | `review_agent.py` | contracts, profile(S2，接口约定即可) |
| S6 路由 | `router.py` | contracts（只读所有签名） |

> 说明：S4/S5 标「接口约定即可」的依赖——它们只需按 `contracts.py` 的签名调用 S1/S2 的类，不必等 S1/S2 真正完成，因为签名已冻结。这是「契约先行」能让它们真正并行的原因。

每个子 Agent 的**统一开工要求**：
1. 先读 `contracts.py`、`config.py`、`strategy_kb.py`、`scenario_store.py`。
2. 只实现自己那份签名，不碰别人文件，不改 `contracts.py`。
3. 遵循样板规范：中文注释、`[模块名] 步骤N` 日志、模拟模式兜底。

**Wave 2 —— 主控串行（集成 + 验证）**
- 把 `main.py` 从 `ScoreSystem` 演化为 `TrainerSystem`（初始化所有组件，暴露 `handle_turn` / `end_session`，保留 `score` 兼容）。
- 更新 `cli.py`：一次回合 = 评分 + 扮演 + 教学提示；会话结束触发复盘。
- 端到端 CLI 测试（沿用现有测试脚本 + 补复盘/扮演的用例）。

**Wave 3 —— 可选，后置**
- HTTP API 层（FastAPI）暴露给未来前端；单元测试；知识库 RAG。

---

## 7. 开发路线图

| 阶段 | 内容 | 交付物 | 状态 |
|---|---|---|---|
| 0 | 评分模块 | 7 文件，CLI 可跑 | ✅ 完成 |
| 1 | Wave 0：契约冻结 + 骨架桩 | `contracts.py` + 各模块桩 | ⬜ 待开工 |
| 2 | Wave 1：6 子 Agent 并行 | 6 模块实现 | ⬜ |
| 3 | Wave 2：集成 + 验证 | `TrainerSystem` + 新 CLI 全流程 | ⬜ |
| 4 | Wave 3：HTTP + 测试 | API + 单测 | 后置 |

---

## 8. 开放决策（请拍板后我开工）

1. **是否按「Wave 0 → Wave 1 并行 → Wave 2 集成」推进？**（我建议是）
2. **并行子 Agent 用哪种方式**：我默认用「并行 `Agent` 工具调用（6 个同时，文件不相交）」。若你要更强的流程控制/结果汇总，可用 `Workflow` 编排——需要你明确一句「用 workflow」。
3. **`main.py` 的 `ScoreSystem` 是否保留向后兼容**（保留 `score()` 方法供旧 CLI 用，还是直接重构为 `TrainerSystem`）？（我建议保留一个兼容方法，降低回归风险）
4. **`persona_params` 数值**：当前用你给的 0.7/0.8/0.4/0.3，是否需要调整后再冻结？
5. **项目要不要现在就 `git init`**（当前 `self-trainer-agent/` 还不是 git 仓库）？建议 Wave 0 冻结契约时顺手 init + 写好 `.gitignore`（排除 `.env`/`__pycache__`），方便回溯契约变更。
