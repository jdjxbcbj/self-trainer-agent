# safe-trainer 多 Agent 后端 · 架构与开发规划 v5

> 版本：v5（补「无暴击终局」规则 + 三条决策拍板 + 数据用途声明 v1；在 v4 基础上）
> 状态：**5 项决策已拍板，4 项待 Wave 0 前补拍**
> 日期：2026-08-31
> 定位：回答「要做哪些模块、职责边界、接口长什么样、数据怎么存、按什么顺序开发、怎么并行开发」。批准后即作为开发依据。
> 配套：《PRD.md》管「做什么、为什么」，本文件管「怎么做」。

---

## 0. 一句话结论

**当前唯一在开发的项目是 `self-trainer-agent/`（纯 Python 多 Agent 后端）。产品定位已从「软技能 / 关系维护」升维为「安全对线训练场」（全年龄段场景化安全教育）。下一步：把后端的场景/约束模型从「王阿姨催婚」同步为「安全场景」，并补上数据层（持久化），再冻结接口契约、拆子 Agent 并行开发。**

前端（`safety-confrontation-game/`）已先行做出 6 个安全场景与评分规则（SDB/GSB/RSB），后端要跟上前端的产品方向。

---

## 1. 范围与前提

### 1.1 项目边界

| 项 | 结论 |
|---|---|
| 开发中的项目 | **只有 `self-trainer-agent/` 一个**（纯 Python 多 Agent 后端） |
| 前端 | `safety-confrontation-game/`（Next.js，已做出 6 场景 demo），**本期不与后端联调**，仅作为场景/评分规则的**数据来源参照** |
| `safe-trainer/`（Vite + JS） | 早期尝试，已废弃，方法论可复用、代码不整合 |
| 评分模块 7 文件 | ✅ 已跑通，作为「格式/日志/注释规范」样板；**其场景/约束模型需同步**（见 §3） |
| 开发模型 | **本对话 = 主控（orchestrator）；各模块 = 子 Agent（subagent）并行开发** |

### 1.2 已交付：评分模块（现状盘点）

`self-trainer-agent/` 现有 14 个文件，已通过命令行实测（真实 DeepSeek API 调用成功）。**但当前场景仍是「王阿姨催婚」，约束仍是「关系维护意愿 4 档」，与前端「安全对线训练场」不一致，需要同步。**

| 文件 | 职责 | 状态 |
|---|---|---|
| `config.py` | 全局配置，API Key 从环境变量 `LLM_API_KEY` 读取 | ✅ |
| `scenario_store.py` | 场景数据（仅 `wang_ayi_cuihun`） | 🟡 需替换为 6 个安全场景（SDB） |
| `strategy_kb.py` | 约束→评分维度/高低分特征（4 档关系维护意愿） | 🟡 需替换为 GSB（通用 7+2 维度 + 红线） |
| `memory.py` | 会话级消息历史（纯内存 `defaultdict`） | 🟡 需扩展（对峙值/阶段） |
| `profile.py` | 用户画像（SQLite `profiles.db`，单表 JSON） | 🟡 需并入 `storage.py` 的 users 表 |
| `judge_agent.py` | 评分 Agent 核心（构造 prompt→调 LLM→解析） | 🟡 评分口径需从「约束策略」改为「安全维度 + 红线」 |
| `roleplay_agent.py` | 扮演 Agent（生成 NPC 回应 + 动态状态） | 🟡 需替换「催婚人设/执念度」为「对峙值/升级层级」 |
| `teaching_agent.py` | 教学 Agent（教学卡 + 实时提示） | 🟡 需替换招式为「合规提示」 |
| `review_agent.py` | 复盘 Agent（会话总结 + 目标达成 + 画像） | ✅ 结构可复用，口径需同步 |
| `knowledge_base.py` | 知识库（方法论文案 + 法条） | 🟡 法条/方法论需换安全场景内容 |
| `router.py` | 编排路由（状态机 + Agent 调度） | 🟡 阶段判定需换「对峙值/红线」 |
| `main.py` | `TrainerSystem` 总装配 | ✅ 结构可复用 |
| `cli.py` | 命令行入口 | 🟡 场景/约束选项需换安全场景 |
| `contracts.py` | 接口契约（唯一真源） | 🟡 数据类/枚举需同步 |

**必须被后续模块对齐的规范**（样板，保持不变）：
- 每步日志：`[模块名] 步骤N - 动作`，如 `[JudgeAgent] 步骤3 - 调用LLM评分...`。
- 模拟模式兜底：无 Key / 无 openai / 调用失败 / JSON 解析失败 → 全部回退固定模拟结果，开箱即用。
- 中文注释 + UTF-8 控制台适配（`sys.stdout.reconfigure`）。
- 评分 Agent「不生成对话」——仅指评分 Agent 本身不生成；后端整体生成 NPC 回应的职责归「场景扮演 Agent」。

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
│  ├─ judge_agent.py    评分 Agent    🟡 回合级打分 + 反馈 + 红线  │
│  ├─ roleplay_agent.py 场景扮演 Agent 🟡 生成 NPC 回应 + 对峙值    │
│  ├─ teaching_agent.py 教学 Agent    🟡 合规提示 + 实时提示        │
│  └─ review_agent.py   复盘 Agent    ✅ 会话总结+目标达成+画像     │
└──────────────┬───────────────────────────────────────────────┘
               │ 读写
               ▼
┌──────────────────────────────────────────────────────────────┐
│  支撑层                                                       │
│  ├─ contracts.py       接口契约（唯一真源，并行开发的地基）       │
│  ├─ storage.py         数据层（统一封装 SQLite 连接与迁移）⬜新增  │
│  ├─ memory.py          短时记忆（会话消息+对峙值+阶段）           │
│  ├─ scenario_store.py  场景库 SDB（6 安全场景，含 risk/criteria） │
│  ├─ strategy_kb.py     评分库 GSB（通用维度 + 红线 RSB）          │
│  └─ knowledge_base.py  知识库（方法论/法条，内容层）              │
└──────────────────────────────────────────────────────────────┘
```

图例：✅ 已完成　🟡 部分完成（需同步）　⬜ 未开始

---

## 3. 场景/约束模型同步（本次核心变更）

### 3.1 从「关系维护」到「安全自保」：约束模型替换

v2 的约束是「关系维护意愿 4 档」（`want_maintain`/`endure_but_record`/`dont_care`/`want_cutoff`），对应单一场景「王阿姨催婚」。前端已升级为「安全对线训练场」，约束模型替换如下：

| 旧（v2） | 新（v3） | 说明 |
|---|---|---|
| 约束 4 档（关系维护意愿） | **训练身份 `audience`**（minor/adult） | 决定可选场景、是否分流评分 |
| （无） | **场景风险等级 `riskLevel`**（low/medium/high） | 决定对峙值涨落与红线严格度 |
| 单一场景「王阿姨催婚」 | **6 个安全场景**（4 模块，见 §3.2） | 每个场景自带 `criteria`/`laws`/`lines`/`hint` |
| 评分按「约束 × 策略」差异化 | **GSB 通用 7+2 维度 + RSB 红线一票否决** | 见 §3.3 |

### 3.2 场景库 SDB（`scenario_store.py` 替换）

前端已定义 4 模块 × 6 场景，后端 `scenario_store.py` 按此重建：

| 模块 moduleId | 模块名 | 场景 scenarioId | 风险 | 未成年可用 |
|---|---|---|---|---|
| `domestic` | 国内日常边界 | `neighbor-noise` 邻里噪音纠纷 | low | ✅ |
| `domestic` | 国内日常边界 | `relative-pressure` 亲戚道德绑架 | low | ✅ |
| `domestic` | 国内日常边界 | `campus-boundary` 校园冒犯与求助 | low | ✅ |
| `legal` | 普法合规维权 | `merchant-rights` 商家拒绝退款 | medium | ❌ |
| `overseas` | 海外涉外冲突 | `overseas-slur` 海外种族挑衅 | medium | ❌ |
| `negotiation` | 情绪控场谈判 | `rage-deescalation` 暴怒对峙降温 | high | ❌ |

**每个场景的数据结构**（替代旧 `persona_params`）：

```python
{
    "id": "neighbor-noise",
    "moduleId": "domestic",
    "title": "邻里噪音纠纷",
    "premise": "晚上休息时间，邻居持续制造噪音，并反过来指责你事多。",
    "personaName": "蛮横邻居",
    "opening": "就这点声音你也要管？大家都是邻居，你别这么小题大做。",
    "riskLevel": "low",            # low / medium / high
    "minorSafe": True,             # 未成年身份是否可进
    "critsToPass": 2,              # 通关所需暴击次数
    "laws": ["民法典相邻关系：…"],   # 法条（可空）
    "criteria": ["表达边界", "保持冷静", "提出规则化处理", "必要时留存记录"],  # 本场景能力点
    "lines": {                     # NPC 按对峙值层级选台词
        "low":  ["你这么说不就是想让我什么都别干？", "…"],
        "mid":  ["你要投诉就投诉，我还怕你不成？", "…"],
        "high": ["你再说一句试试，我现在就找你理论。", "…"],
        "yield":["行，我今晚注意点，你也别把事情闹大。", "…"],
    },
    "hint": "我理解你有生活需求，但现在是休息时间。请把音量降下来；…",
}
```

**静态 vs 动态分离（沿用 v2 设计，换了字段）**：
- **静态**（写死 SDB，不随对话变）：`riskLevel` / `criteria` / `laws` / `lines` / `hint` / `minorSafe` / `critsToPass`。
- **动态**（随会话存记忆，每轮由扮演 Agent 输出下一轮值）：`confrontation_value`（对峙值 0~100，起始 50）+ 由此推导的 `escalation_tier`（low/mid/high/yield）。

### 3.3 评分库 GSB + 红线库 RSB（`strategy_kb.py` 替换）

v2 的「约束→评分维度权重」替换为**通用安全评分维度 + 红线**，与前端 `scoreRules`/`redLines` 对齐：

**GSB 正向维度（7 个，关键词 + 权重）**：

| 维度 | 关键词示例 | 权重 |
|---|---|---|
| 表达边界 boundary | 不接受/请停止/不能/边界/keep your distance | 18 |
| 保持冷静 calm | 我理解/我听到/冷静/先停 | 14 |
| 合规合法 legal | 规则/法律/民法典/物业/平台/report | 18 |
| 降温控场 deescalate | 保持距离/不争吵/按事实/下一步 | 16 |
| 取证意识 evidence | 记录/录音/凭证/保留/证据 | 14 |
| 礼貌 polite | 请/谢谢/麻烦 | 8 |
| 求助意识 risk-avoid | 求助/找老师/家长/消协/报警/工作人员 | 12 |

**GSB 负向维度（2 个，反向扣分）**：指责对抗（都怪你/你必须/闭嘴，-18）、空洞敷衍（随便/算了/没事，-12）。

**RSB 红线（4 类，一票否决，命中即违规失分并给合规替代句）**：
1. `r-insult` 辱骂（滚/废物/傻/垃圾/idiot/stupid）
2. `r-violence` 暴力威胁（打你/弄死/动手/砸/kill）
3. `r-illegal` 违法维权（曝光身份证/人肉/堵门/威胁家人）
4. `r-foreign` 歧视性反击（涉外场景）

> ✅ **评分口径已定**：`judge_agent` 默认纯走 GSB+RSB 确定性打分（本地规则库优先）；LLM 兜底本期**不实现，只留 `enable_llm_fallback=False` 参数位**。等真实数据落库后，再用数据判断 LLM 兜底值不值（见 §9 已拍板第 1 项）。

### 3.4 对峙值（`confrontation_value`）与状态机

- 单局从 **50** 起跳。用户回应越合规/降温，对峙值下降；越顶撞/空洞，对峙值上升；命中红线直接跳涨。
- NPC 台词按对峙值分层：`≥70 → high`，`45~69 → mid`，`<45 → low`，`≤25 → yield`（服软）。
- 阶段状态机（规则判定，非 LLM）：

```
opening（开场） → pressure（施压对峙） → [用户回应]
                                           │
              ┌────────────────────────────┼────────────────┐
              │ 对峙值 < 阈值 / 达 critsToPass │ 对峙值 ≥ 危险线    │ 命中红线
              ▼                              ▼                ▼
          resolve（通关）                 deadlock（失控僵持）  deadlock + 违规记录
                                           └────────┬───────┘
                                                    ▼
                                                  end → 触发复盘
```

阶段判定仍用**规则**（对峙值阈值 + 红线 + 暴击数 + round_limit），LLM 分类器后置。

**判定参数（默认值，Wave 0 冻结前可微调；子 Agent 实现以此为准，不得各写各的）**：

| 参数 | 默认值 | 说明 |
|---|---|---|
| 总分计算 | `clamp(Σ命中正向维度权重 − Σ命中负向扣分, 0, 100)` | 正向权重见 §3.3；负向 -18 / -12 |
| 红线一票否决 | 命中红线 → `total_score ≤ 30` 且记入 `red_line_hits` | 不叠加普通扣分 |
| 暴击（crit） | 单回合 `total_score ≥ 85` 且 `red_line_hits` 为空 | 计 1 次暴击 |
| 对峙值起始 | `50`（int，clamp 到 [0,100]） | |
| 对峙值涨落 | 红线 `+25`；`score<40 → +10`；`40≤score<85 → −5`；暴击（≥85）→ `−15`（含额外 −10） | **按本回合表现**，与当前对峙值无关 |
| NPC 台词层级 | `≥70 high` / `45~69 mid` / `<45 low` / `≤25 yield` | |
| 通关 resolve（优秀） | 累计暴击数 ≥ `critsToPass` 且 对峙值 ≤ 40 | `critsToPass` 来自 SDB |
| 通关 resolve（及格） | 对峙值 ≤ 0 且暴击数 < `critsToPass` | 全程压住但没打出暴击 → 判及格、`achievement_score` 降档，不留死循环 |
| 失控 deadlock | 对峙值 ≥ 85，或命中 `r-violence`（暴力红线） | |
| 到时 end | 达到 `round_limit` 仍未 resolve/deadlock → 触发复盘 | `round_limit` 由 config 定义，按当前对峙值判达成度 |

> ⚠️ **涨落方向**：对峙值变化取决于**本回合表现**（得分 / 红线 / 暴击），**不是当前对峙值区间**。v3 曾误写成「按当前区间」（`<40 → +10`、`70~84 → −10`），导致局势越缓越反弹、`resolve` 永远不可达——已修正，冻结前务必用模拟输入推演一遍状态机（见 §7.2 Wave 0）。

---

## 4. 核心数据契约

### 4.1 一次用户回合的流程（所有 Agent 的协作骨架）

```
输入：user_response（+ user_id / session_id / scenario_id / audience）

Router.handle_turn：
  1. 读 SessionMemory：历史 + 对峙值/层级 + 阶段
  2. 评分：judge_agent.judge(...) → ScoreResult（GSB 维度 + RSB 红线命中）
  3. 扮演：roleplay_agent.reply(...) → (NPC 回应, 下一轮对峙值/层级)
  4. 教学：teaching_agent.get_hint(...) → 合规提示（可空，规则/缓存）
  5. 判定下一阶段（对峙值状态机 + 红线）
  6. 写记忆：user 回应 + NPC 回应 + 下一轮对峙值/层级 + next_stage
  7. 【数据层】storage.write_turn(...) 持久化本轮到 turns 表
  8. 返回 TurnResult

会话结束 Router.end_session：
  → review_agent.review(...) → ReviewResult
  → 【数据层】storage.end_session(...) 写 sessions 表 + 更新 users 画像
```

### 4.2 `TurnResult` 返回结构（前端/CLI 一次拿全）

```json
{
  "score": {
    "total_score": 75,
    "dimensions": {"表达边界": 82, "保持冷静": 70, "...": "..."},
    "red_line_hits": [],
    "feedback": "...",
    "suggested_strategy": "..."
  },
  "ai_reply": "你要投诉就投诉，我还怕你不成？",
  "confrontation_value": 55,
  "next_stage": "pressure",
  "teaching_hint": "别被带节奏，回到事实和规则上"
}
```

### 4.3 训练身份 `audience`（唯一真源，写在 `contracts.py`）

| ID | 中文名 | 说明 |
|---|---|---|
| `minor` | 青少年 | 仅进入 `minorSafe` 场景，评分口径可后续分流 |
| `adult` | 成年人 | 全场景 |

> 旧「关系维护意愿 4 档」作废。若未来要恢复「想维持关系 vs 想断联」的差异化，作为**场景级 criteria 的变体**在 SDB 里挂，不再作为全局约束。

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
    dimensions: dict        # {维度中文名: 0-100}
    red_line_hits: list     # 命中的红线 ID（可空）
    feedback: str
    suggested_strategy: str

@dataclass
class TurnResult:
    score: ScoreResult
    ai_reply: str
    confrontation_value: int     # 下一轮对峙值 0~100
    next_stage: str
    teaching_hint: Optional[str] = None

@dataclass
class TeachingCard:
    title: str; when: str; how: str; why: str
    scenario_id: str; example: str

@dataclass
class ReviewResult:
    summary: str
    goal_achieved: bool
    achievement_score: int   # 0-100 会话级
    weak_points: list
    profile_update: dict

# 方法签名（只定义，不实现）
class JudgeAgent:        # 🟡 同步评分口径
    def judge(self, scenario, audience, history, user_response) -> ScoreResult: ...

class RoleplayAgent:     # 🟡 换对峙值模型
    def reply(self, scenario, audience, history, user_response, confrontation) -> tuple[str, int]: ...
    # 返回 (NPC 回应, 下一轮对峙值)

class TeachingAgent:     # 🟡 换合规提示
    def get_card(self, scenario_id, audience) -> TeachingCard: ...
    def get_hint(self, scenario, audience, stage, history) -> str: ...

class ReviewAgent:       # ✅ 结构复用，口径同步
    def review(self, session_id, user_id, scenario, audience, history, profile) -> ReviewResult: ...

class SessionMemory:     # 🟡 扩展
    def add_message(self, session_id, role, content): ...
    def get_context(self, session_id, limit=None) -> list: ...
    def get_confrontation(self, session_id) -> int: ...
    def set_confrontation(self, session_id, value): ...
    def get_stage(self, session_id) -> str: ...
    def set_stage(self, session_id, stage): ...
    def clear(self, session_id): ...

class Storage:           # ⬜ 新增（数据层，见 §6）
    def migrate(self) -> None: ...
    def write_turn(self, session_id, turn) -> None: ...
    def end_session(self, session_id, review) -> None: ...
    def get_session(self, session_id) -> dict: ...
    def get_turns(self, session_id) -> list: ...
    def upsert_user(self, user_id, audience) -> None: ...
    def get_profile(self, user_id) -> dict: ...
    def update_profile(self, user_id, update) -> None: ...

class KnowledgeBase:     # 🟡 换安全场景法条/方法论
    def get_method(self, scenario_id, strategy) -> dict: ...
    def get_legal(self, scenario_id) -> list: ...

class Router:            # 🟡 换阶段判定 + 接 storage
    def handle_turn(self, user_id, session_id, scenario_id, audience, user_response) -> TurnResult: ...
    def end_session(self, user_id, session_id, scenario_id, audience) -> ReviewResult: ...
```

---

## 6. 数据层（新增）

> 本节是本版新增。目标：把「画像 SQLite」升级为「可查询、可迁移、可沉淀训练数据」的持久化层。

### 6.1 为什么要有数据层

当前只有 `profile.py` 把用户画像存进单表 `profiles.db`，对话历史 (`memory.py`) 是纯内存、进程退出即丢。缺三样东西：

1. **会话持久化**：一场训练要能重开、能查历史回合。
2. **数据沉淀**：回合级数据（回应/得分/红线/对峙值）是后续优化评分规则、训练模型、做画像的原料，现在全丢。
3. **统一连接与迁移**：散落的 `sqlite3.connect` 各自建表，无法演进 schema。

### 6.2 四张表

统一由一个 SQLite 文件承载，`storage.py` 负责建表与迁移。

```sql
-- schema_version：迁移版本追踪（storage.migrate 依据它决定跑哪些迁移）
CREATE TABLE schema_version (
    version    INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

-- users：用户与训练身份 + 画像（画像 JSON 列，替代 profile.py 的单表）
CREATE TABLE users (
    user_id      TEXT PRIMARY KEY,
    audience     TEXT NOT NULL DEFAULT 'adult',  -- minor / adult
    profile_json TEXT,                            -- 用户画像，JSON 字符串
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

-- sessions：一次训练会话
CREATE TABLE sessions (
    session_id        TEXT PRIMARY KEY,
    user_id           TEXT NOT NULL REFERENCES users(user_id),
    scenario_id       TEXT NOT NULL,
    audience          TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'active',  -- active / ended
    final_stage       TEXT,
    achievement_score INTEGER,
    goal_achieved     INTEGER,                          -- 0/1
    created_at        TEXT NOT NULL,
    ended_at          TEXT
);
CREATE INDEX idx_sessions_user ON sessions(user_id);

-- turns：每个回合
CREATE TABLE turns (
    turn_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id           TEXT NOT NULL REFERENCES sessions(session_id),
    turn_index           INTEGER NOT NULL,
    user_response        TEXT NOT NULL,
    ai_reply             TEXT,
    score_total          INTEGER,
    score_dimensions     TEXT,      -- JSON：{维度中文名: 分数}
    red_line_hits        TEXT,      -- JSON：命中的红线 ID 列表
    confrontation_value  INTEGER,   -- 该回合结束后的对峙值
    persona_state        TEXT,      -- JSON：角色动态状态快照
    teaching_hint        TEXT,
    next_stage           TEXT,
    created_at           TEXT NOT NULL
);
CREATE INDEX idx_turns_session ON turns(session_id);
```

> 注：SQLite 外键默认不强制，需在连接时开启 `PRAGMA foreign_keys = ON`（由 `storage.py` 统一处理）。

### 6.3 数据生命周期与写入点

| 事件 | 写入 | 表 |
|---|---|---|
| 用户首次进入 | `storage.upsert_user(user_id, audience)` | users |
| 开新会话 | `storage` 建 sessions 行（status=active） | sessions |
| **每次 `handle_turn`** | `storage.write_turn(...)` 追加一轮 | turns |
| **每次 `end_session`** | `storage.end_session(...)` 把 sessions 标 ended + 写 final_stage/achievement_score/goal_achieved，并 `update_profile` 更新 users.profile_json | sessions + users |
| 读画像 | `storage.get_profile(user_id)` | users |

**关键原则**：
- `handle_turn` **只写 turns**（追加，不改 sessions）；`end_session` **写 sessions + 更新画像**。回合与结算分离，避免每个回合都去 `UPDATE sessions`。
- 画像（profile）由**复盘 Agent 在 end_session 时产出增量**，其余 Agent 只读。
- `memory.py` 仍承担**短时记忆**（会话内热数据），`storage.py` 承担**持久化**（冷数据落盘）。两者职责不混：`handle_turn` 先写内存、再落 turns 表，保证「热路径快、冷路径不丢」。

### 6.4 `storage.py` 统一封装

```python
class Storage:
    """数据层唯一入口：统一封装 SQLite 连接、建表、迁移。"""

    def __init__(self, db_path=None):
        # 短连接模型（沿用 profile.py 的做法）：每次操作新建连接，避免并发隐患

    def migrate(self) -> None:
        # 读 schema_version，按顺序应用未执行的迁移脚本（幂等）

    def write_turn(self, session_id, turn: dict) -> None: ...
    def end_session(self, session_id, review: ReviewResult) -> None: ...
    def get_session(self, session_id) -> dict: ...
    def get_turns(self, session_id) -> list: ...
    def upsert_user(self, user_id, audience) -> None: ...
    def get_profile(self, user_id) -> dict: ...
    def update_profile(self, user_id, update: dict) -> None: ...
```

- **迁移机制**：迁移脚本按版本号编号（`migrations/0001_init.sql` → …），`schema_version` 记录已应用版本，`migrate()` 幂等跑增量。避免散落的 `CREATE TABLE IF NOT EXISTS`。
- **替代 `profile.py`**：`profile.py` 的 `UserProfile.get/update` 逻辑并入 `storage.py` 的 `get_profile/update_profile`（画像存 `users.profile_json`）。`profile.py` 可保留为 `storage.py` 的薄封装或删除，实现时定夺。

### 6.5 数据收集策略（与 PRD 呼应）

- **先落盘、后分析**：MVP 阶段只管把 turns/sessions 完整写下来，不做埋点/分析。数据是后续「优化 GSB 规则库」「训练评分模型」「用户画像」的原料。
- **画像字段从简起步**：`profile_json` 先只存复盘产出的 `practice_count`、`latest_weak_point` 等扁平字段，避免过早设计复杂画像 schema。
- **数据用途声明（v1，本期即生效）**：
  1. **用途**：仅用于本地练习复盘与评分规则优化，不外传、不商用。
  2. **存储位置**：本地单机 SQLite 文件（`self-trainer-agent/` 目录下）。
  3. **删除方式**：删除对应 `.db` 文件即彻底删除全部数据（无云端副本）。
  > 这是将来上服务端做脱敏/删除策略的起点；现在数据为空，定声明零成本。

---

## 7. 并行开发编排（主控 + 子 Agent）

**模型**：本对话 = 主控，定义契约、拆任务、集成；子 Agent = 各自实现一个模块，**只改自己的文件**，互不冲突。

### 7.1 为什么不需要 worktree

- 各模块文件**完全不相交**（见下表），子 Agent 各改各的文件，不存在同一文件并发写。
- 靠「契约冻结 + 文件不相交」就够，不需要 worktree。

### 7.2 开发波浪（Wave）

**Wave 0 —— 主控串行（冻结契约 + 同步场景 + 冻结判定参数 + 改评分 Agent）**
- 重写 `contracts.py`（数据类 + 枚举 + 方法签名，即 §5）。
- 同步 `scenario_store.py` 为 6 安全场景（SDB）、`strategy_kb.py` 为 GSB+RSB，并**冻结 §3.4 判定参数**（暴击/对峙值/红线）——这些参数子 Agent 只读。
- 改造 `judge_agent.py`：从「调 LLM 用 strategy prompt 打分」改为「消费 GSB+RSB 确定性打分」；LLM 兜底本期不实现，只留 `enable_llm_fallback=False` 参数位（见 §9 已拍板第 1 项）。
- 写 `storage.py` 骨架（§6.4 签名 + 建表 + migrate 桩）。
- 用几组模拟输入**推演对峙值状态机**（普通合规 / 暴击 / 红线 / 顶撞各一组），确认 `resolve` 与 `deadlock` 均可达、无震荡后再冻结参数。
- 产出：所有子 Agent 开工前必读的契约。

**Wave 1 —— 子 Agent 并行（6 个，每个只写一个文件）**

| 子 Agent | 负责文件 | 依赖（只读） |
|---|---|---|
| S1 知识库 | `knowledge_base.py` | contracts, scenario_store |
| S2 记忆 | `memory.py` | contracts, config |
| S3 数据层 | `storage.py` | contracts, config |
| S4 扮演 | `roleplay_agent.py` | contracts, scenario_store, config |
| S5 教学 | `teaching_agent.py` | contracts, strategy_kb, knowledge_base(S1，接口约定即可) |
| S6 复盘 | `review_agent.py` | contracts, storage(S3，接口约定即可) |

> 说明：`storage.py`（数据层基座）从原 S2 拆出独立成一个子 Agent，避免「一人扛 memory + storage 两文件」的单点风险；`judge_agent.py` 归主控 Wave 0 改造（它消费 GSB/RSB、与评分口径强耦合，不宜并行）；`router.py` 移入 Wave 2（见下），因为它要真实调度所有 Agent 才能做端到端验证，仅靠签名单测不充分。

每个子 Agent 的**统一开工要求**：
1. 先读 `contracts.py`、`config.py`、`scenario_store.py`、`strategy_kb.py`，以及 §3.4 判定参数。
2. 只实现自己那份签名，不碰别人文件，不改 `contracts.py`。
3. 遵循样板规范：中文注释、`[模块名] 步骤N` 日志、模拟模式兜底。

**Wave 2 —— 主控串行（集成 + 验证）**
- 实现 `router.py`：阶段状态机（§3.4 判定参数）+ 真实调度各 Agent + 接 `storage`。
- 把 `main.py` 的 `TrainerSystem` 接上 `router` 与 `storage`（`handle_turn` 落 turns、`end_session` 落 sessions），保留 `score()` 兼容。
- 更新 `cli.py`：场景选项换成 6 安全场景 + 身份选择；一次回合 = 评分 + 扮演 + 教学提示；会话结束触发复盘 + 落库。
- 端到端 CLI 测试：补数据层落库校验 + 暴击/通关/红线用例。

**Wave 3 —— 可选，后置**
- HTTP API 层（FastAPI）暴露给前端；单元测试；知识库 RAG；数据层查询/分析接口。

---

## 8. 开发路线图

| 阶段 | 内容 | 交付物 | 状态 |
|---|---|---|---|
| 0 | 评分模块 | 7 文件，CLI 可跑 | ✅ 完成（待同步） |
| 1 | Wave 0：契约冻结 + 场景同步 + 数据层骨架 | `contracts.py` + SDB/GSB + `storage.py` 桩 | ⬜ 待开工 |
| 2 | Wave 1：6 子 Agent 并行 | 6 模块实现 | ⬜ |
| 3 | Wave 2：集成 + 验证 | `TrainerSystem` + 新 CLI 全流程 | ⬜ |
| 4 | Wave 3：HTTP + 测试 | API + 单测 | 后置 |

---

## 9. 决策记录

### 已拍板（本版确认，Wave 0 直接照此执行）

1. **评分口径**：**规则库优先**——`judge_agent` 默认纯走 GSB+RSB 确定性打分；LLM 兜底本期**不实现，只留 `enable_llm_fallback=False` 参数位**。数据落库后，再用真实数据判断 LLM 兜底值不值。评分权不交给模型。
2. **推进方式**：按「Wave 0 → Wave 1 并行 → Wave 2 集成」推进。
3. **爽感归属**：爽感（暴击/连击/等级/徽章）由**前端本地 demo** 承担，后端不落爽感字段；联调时再决定是否入库。（已同步 PRD §5.6）
4. **判定参数**：§3.4 反推默认值**直接冻结**（暴击 ≥85、对峙值涨落 ±5/10/25、红线 ≤30、yield ≤25），并补「无暴击终局」（对峙值 ≤0 → 及格通关）。联调后若暴击命中率 <15%，把暴击阈值从 85 降到 80。
5. **数据用途声明**：本期即生效（§6.5 三句话：用途 / 存储位置 / 删除方式）。

### 仍待定（Wave 0 前补拍）

6. **并行子 Agent 用哪种方式**：默认「并行 `Agent` 工具调用（6 个同时，文件不相交）」；若要更强流程控制可用 `Workflow` 编排（需你明确一句「用 workflow」）。
7. **`profile.py` 去留**：并入 `storage.py`（画像存 users 表）后，是删还是留薄封装？（我建议删，避免两处 DB 连接）
8. **`score()` 向后兼容**：`main.py` 的 `score()` 方法是否保留？（我建议保留一个兼容方法）
9. **训练身份分流**：未成年评分口径本期是否分流，还是先只做「场景隔离（minorSafe）」？（我建议先只做场景隔离）
