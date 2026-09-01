// -*- coding: utf-8 -*-
// demo/app.js — 「安全对线训练场」Demo（API 客户端版）
//
// 已从「本地打分」改为「后端 API 客户端」，契约见后端仓库 API.md（已冻结）：
//   场景列表  GET  /scenarios?audience=  → 场景菜单数据
//   开新会话  POST /sessions             → session_id + 开场白 + 教学卡
//   每回合    POST /sessions/{id}/turns  → 评分 + NPC 回应 + 对峙值 + 阶段 + 实时提示
//   复盘      POST /sessions/{id}/end    → 总结 + 是否通关 + 达成度 + 薄弱点
//
// 本地联调先启动后端：py -m uvicorn api:app --port 8000 --reload
// 用户区分：不做登录，用 localStorage 随机 uid 当 user_id 传入（见 API.md §8）。

const API_BASE = "http://localhost:8000";

// 模块显示名（仅 UI 文案；评分/台词/红线都在后端本地规则库）
const modules = {
  domestic: "国内日常边界",
  legal: "普法合规维权",
  overseas: "海外涉外冲突",
  negotiation: "情绪控场谈判",
};

// 徽章（本地成长展示，非评分逻辑）
const badges = [
  { id: "calm", title: "零情绪失控", desc: "无违规完成一局" },
  { id: "crit", title: "合规暴击达人", desc: "累计 3 次暴击" },
  { id: "evidence", title: "取证意识", desc: "使用记录/凭证/证据话术" },
  { id: "minor", title: "自保入门", desc: "完成青少年安全关卡" },
];

// ---------------- 全局状态 ----------------
let audience = "minor";
let scenarios = [];       // 从后端 GET /scenarios 拉取
let activeScenario = null;
let sessionId = null;     // 后端生成的会话 ID
let turns = [];           // [{ role, text, judgement? }]
let confrontation = 50;
let completed = false;
let lastStage = "opening";
let lastScore = null;         // 最近评分 { total_score, red_line_hits, feedback, suggested_strategy }
let lastTeachingHint = null;  // 最近实时提示（教学 Agent）
let teachingCard = null;      // 开场教学卡
let review = null;            // 复盘结果
let busy = true;              // 初始 true，避免首屏闪「未连接」
let progress = loadProgress();

const $ = (id) => document.getElementById(id);

// ---------------- 用户身份（随机 uid，无登录） ----------------
function getUserId() {
  let uid = localStorage.getItem("scg_user_id");
  if (!uid) {
    uid = (crypto && crypto.randomUUID)
      ? crypto.randomUUID()
      : "u_" + Math.random().toString(36).slice(2) + Date.now().toString(36);
    localStorage.setItem("scg_user_id", uid);
  }
  return uid;
}

// ---------------- 进度（本地 XP/徽章） ----------------
function loadProgress() {
  try {
    return JSON.parse(localStorage.getItem("scg_demo_progress")) || { xp: 0, crits: 0, completed: [], badges: [] };
  } catch {
    return { xp: 0, crits: 0, completed: [], badges: [] };
  }
}

function saveProgress() {
  localStorage.setItem("scg_demo_progress", JSON.stringify(progress));
}

function addBadge(id) {
  if (!progress.badges.includes(id)) progress.badges.push(id);
}

function levelTitle() {
  if (progress.xp >= 560) return "高阶控场谈判官";
  if (progress.xp >= 300) return "合规维权师";
  if (progress.xp >= 120) return "边界达人";
  return "新手自保";
}

// ---------------- HTTP 封装 ----------------
async function api(path, opts = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    let detail = "";
    try { detail = (await res.json()).detail || ""; } catch {}
    throw new Error(detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ---------------- 状态条 / 忙碌态 ----------------
function setStatus(msg, kind) {
  const el = $("backendStatus");
  if (!el) return;
  if (!msg) { el.hidden = true; el.textContent = ""; el.className = "backend-status"; return; }
  el.hidden = false;
  el.textContent = msg;
  el.className = `backend-status ${kind || ""}`;
}

function setBusy(b) {
  busy = b;
  const input = $("replyInput");
  const btn = $("replyForm") ? $("replyForm").querySelector("button.primary") : null;
  if (input) input.disabled = completed || busy;
  if (btn) btn.disabled = completed || busy;
}

// ---------------- 启动 / 场景加载 ----------------
async function boot() {
  setStatus("正在连接后端…", "loading");
  try {
    scenarios = await api(`/scenarios?audience=${audience}`);
    if (scenarios.length) await selectScenario(scenarios[0].id);
    else setStatus("", "");
  } catch (e) {
    scenarios = [];
    setStatus(`后端未连接（${e.message}）。请先启动后端：py -m uvicorn api:app --port 8000 --reload`, "error");
  } finally {
    setBusy(false);
    render();
  }
}

async function selectScenario(id) {
  const next = scenarios.find((s) => s.id === id);
  if (!next) return false;
  setBusy(true);
  try {
    const res = await api("/sessions", {
      method: "POST",
      body: JSON.stringify({ user_id: getUserId(), scenario_id: id, audience }),
    });
    activeScenario = next;
    sessionId = res.session_id;
    teachingCard = res.teaching_card;
    turns = [{ role: "opponent", text: res.opening }];
    confrontation = 50;
    completed = false;
    lastStage = "opening";
    lastScore = null;
    lastTeachingHint = null;
    review = null;
    setStatus("", "");
    return true;
  } catch (e) {
    setStatus(`开新会话失败：${e.message}`, "error");
    return false;
  } finally {
    setBusy(false);
    render();
  }
}

async function submitReply(text) {
  if (!text.trim() || completed || !sessionId) return false;
  setBusy(true);
  try {
    const r = await api(`/sessions/${sessionId}/turns`, {
      method: "POST",
      body: JSON.stringify({ user_response: text }),
    });
    const score = r.score || {};
    const redLineHits = score.red_line_hits || [];
    turns.push({
      role: "user",
      text,
      judgement: {
        total_score: score.total_score,
        red_line_hits: redLineHits,
        crit: redLineHits.length === 0 && score.total_score >= 85,
        violation: redLineHits.length > 0,
      },
    });
    confrontation = r.confrontation_value;
    lastScore = score;
    lastTeachingHint = r.teaching_hint;
    lastStage = r.next_stage;
    turns.push({ role: "opponent", text: r.ai_reply });
    completed = ["resolve", "deadlock", "end"].includes(r.next_stage);
    setStatus("", "");
    if (completed) await endAndReview();
    return true;
  } catch (e) {
    setStatus(`回合请求失败：${e.message}`, "error");
    return false;
  } finally {
    setBusy(false);
    render();
  }
}

async function endAndReview() {
  try {
    review = await api(`/sessions/${sessionId}/end`, { method: "POST" });
  } catch (e) {
    review = { summary: `复盘请求失败：${e.message}`, goal_achieved: false, achievement_score: 0, weak_points: [] };
  }
  awardProgress();
}

// 本地 XP/徽章结算，依据后端返回的评分/通关结果（不再本地打分）
function awardProgress() {
  const js = turns.filter((t) => t.role === "user" && t.judgement);
  const crits = js.filter((t) => t.judgement.crit).length;
  const violations = js.filter((t) => t.judgement.violation).length;
  const passed = review ? review.goal_achieved : false;
  const xp = passed ? 80 + crits * 20 : violations ? 10 : 35;
  progress.xp += xp;
  progress.crits += crits;
  if (passed && !progress.completed.includes(activeScenario.id)) progress.completed.push(activeScenario.id);
  if (passed && violations === 0) addBadge("calm");
  if (progress.crits >= 3) addBadge("crit");
  if (turns.some((t) => t.role === "user" && /记录|凭证|证据|截图|录音|record/i.test(t.text))) addBadge("evidence");
  if (passed && audience === "minor") addBadge("minor");
  saveProgress();
}

// ---------------- 渲染 ----------------
function render() {
  renderScenarios();
  renderProgress();
  renderArena();
  renderReport();
}

function riskLabel(level) {
  return { low: "低风险", medium: "中风险", high: "高风险", extreme: "极高风险" }[level];
}

function renderScenarios() {
  const list = $("scenarioList");
  $("scenarioCount").textContent = `${scenarios.length} 个可训练`;
  if (!scenarios.length) {
    list.innerHTML = `<p class="small-copy">${busy ? "正在连接后端…" : "后端未连接，请启动后端服务。"}</p>`;
    return;
  }
  list.innerHTML = scenarios.map((s) => {
    return `<button type="button" class="scenario-card ${s.id === activeScenario?.id ? "active" : ""}" data-scenario="${s.id}" title="${escapeHtml(s.premise)}">
      <span class="sc-row">
        <strong>${escapeHtml(s.title)}</strong>
        <span class="risk-pill risk-${s.riskLevel}">${riskLabel(s.riskLevel)}</span>
      </span>
      <span class="sc-module">${modules[s.moduleId]}</span>
    </button>`;
  }).join("");
  list.querySelectorAll("button[data-scenario]").forEach((btn) =>
    btn.addEventListener("click", () => selectScenario(btn.dataset.scenario))
  );
}

function renderProgress() {
  $("levelTitle").textContent = levelTitle();
  $("xpValue").textContent = progress.xp;
  $("xpBar").style.width = `${Math.min(100, (progress.xp % 300) / 3)}%`;
  const badgeEarned = $("badgeEarned");
  if (badgeEarned) badgeEarned.textContent = `${progress.badges.length} / ${badges.length}`;
  $("badgeList").innerHTML = badges
    .map((b) => `<span class="badge ${progress.badges.includes(b.id) ? "earned" : ""}" title="${b.desc}">${b.title}</span>`)
    .join("");
}

function renderArena() {
  $("moduleTag").textContent = activeScenario ? modules[activeScenario.moduleId] : "—";
  $("scenarioTitle").textContent = activeScenario ? activeScenario.title : "请选择关卡";
  $("scenarioPremise").textContent = activeScenario ? activeScenario.premise : "连接后端并选择一个场景后开始实景演练。";
  $("criteriaStrip").innerHTML = activeScenario
    ? activeScenario.criteria.map((c) => `<span class="chip">${escapeHtml(c)}</span>`).join("")
    : "";
  $("confrontationValue").textContent = confrontation;
  const bar = $("confrontationBar");
  bar.style.width = `${confrontation}%`;
  bar.style.background = confrontation >= 75 ? "var(--danger)" : confrontation >= 48 ? "var(--warn)" : "var(--good)";
  $("dialogueLog").innerHTML = turns.map((t) => turnHtml(t)).join("");
  $("dialogueLog").scrollTop = $("dialogueLog").scrollHeight;
  $("coachTitle").textContent = coachTitle();
  $("coachText").textContent = coachText();
  const input = $("replyInput");
  const btn = $("replyForm") ? $("replyForm").querySelector("button.primary") : null;
  if (input) input.disabled = completed || busy;
  if (btn) btn.disabled = completed || busy;
}

function judgeTier(score) {
  if (score.red_line_hits && score.red_line_hits.length) return "violation";
  if (score.total_score >= 85) return "crit";
  return "weak";
}

function judgeLabel(score) {
  return { crit: "精准暴击", weak: "普通回应", violation: "违规失分" }[judgeTier(score)];
}

function turnHtml(t) {
  const who = t.role === "user" ? "你" : activeScenario.personaName;
  const tag = t.judgement
    ? `<span class="judge-tag ${judgeTier(t.judgement)}">${judgeLabel(t.judgement)} · ${t.judgement.total_score}分</span>`
    : "";
  return `<article class="turn ${t.role}"><span class="speaker">${who}</span><div class="bubble">${escapeHtml(t.text)}</div>${tag}</article>`;
}

function coachTitle() {
  if (completed && review) return review.goal_achieved ? "通关 · 复盘" : "未通关 · 复盘";
  if (lastScore) return `${judgeLabel(lastScore)} · ${lastScore.total_score}分`;
  if (teachingCard) return `教学卡：${teachingCard.title}`;
  return "等待你的第一句回应";
}

function coachText() {
  if (completed && review) return review.summary;
  if (lastTeachingHint) return `💡 ${lastTeachingHint}`;
  if (lastScore) {
    const s = lastScore.suggested_strategy ? ` 建议：${lastScore.suggested_strategy}` : "";
    return `${lastScore.feedback}${s}`;
  }
  if (teachingCard) return `【${teachingCard.title}】${teachingCard.how} 示例：${teachingCard.example}`;
  return "暴击标准：边界清晰、情绪稳定、合规合法、止损控场、有取证或求助意识。";
}

function renderReport() {
  const body = $("reportBody");
  if (!activeScenario) {
    body.className = "empty-report";
    body.textContent = "连接后端后，这里会生成复盘报告。";
    return;
  }
  if (!review) {
    body.className = "empty-report";
    body.textContent = "完成至少一轮回应后，这里会生成错误点、法律风险、最优话术和通关结论。";
    return;
  }
  body.className = "";
  const critTurns = turns.filter((t) => t.role === "user" && t.judgement && t.judgement.crit).map((t) => t.text);
  const laws = activeScenario.laws.map((l) => `<li>${escapeHtml(l)}</li>`).join("");
  const weak = review.weak_points && review.weak_points.length
    ? review.weak_points.map((w) => `<li>${escapeHtml(w)}</li>`).join("")
    : "<li>本局没有明显薄弱点。</li>";
  const best = critTurns.length
    ? critTurns.map((b) => `<li>${escapeHtml(b)}</li>`).join("")
    : "<li>还没有形成暴击话术，试着补齐标准。</li>";
  const userTurns = turns.filter((t) => t.role === "user").length;
  body.innerHTML = `
    <div class="report-metric">
      <div><strong>${review.goal_achieved ? "通过" : "未通过"}</strong><span>结论</span></div>
      <div><strong>${review.achievement_score}</strong><span>达成度</span></div>
      <div><strong>${userTurns}</strong><span>回合</span></div>
    </div>
    <p class="label">复盘总结</p><p class="small-copy">${escapeHtml(review.summary)}</p>
    <p class="label">薄弱点</p><ul class="report-list">${weak}</ul>
    <p class="label">本局最佳话术</p><ul class="report-list">${best}</ul>
    <p class="label">合规依据</p><ul class="report-list">${laws}</ul>`;
}

function escapeHtml(text) {
  return text.replace(/[&<>"]/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[m]));
}

// ---------------- 事件绑定 ----------------
document.querySelectorAll(".mode-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    audience = btn.dataset.audience;
    document.querySelectorAll(".mode-btn").forEach((b) => b.classList.toggle("active", b === btn));
    activeScenario = null;
    boot(); // 重新按 audience 拉场景并重开首场景
  });
});

$("replyForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = $("replyInput");
  if (await submitReply(input.value)) input.value = "";
});

$("hintBtn").addEventListener("click", () => {
  if (!activeScenario) return;
  $("replyInput").value = activeScenario.hint;
  $("replyInput").focus();
});

$("resetBtn").addEventListener("click", () => {
  if (activeScenario) selectScenario(activeScenario.id);
});

// ---------------- 启动 ----------------
render();
boot();
