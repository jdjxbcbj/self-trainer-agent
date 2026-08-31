const modules = {
  domestic: "国内日常边界",
  legal: "普法合规维权",
  overseas: "海外涉外冲突",
  negotiation: "情绪控场谈判",
};

const scenarios = [
  {
    id: "neighbor-noise",
    moduleId: "domestic",
    title: "邻里噪音纠纷",
    premise: "晚上休息时间，邻居持续制造噪音，并反过来指责你事多。",
    personaName: "蛮横邻居",
    opening: "就这点声音你也要管？大家都是邻居，你别这么小题大做。",
    riskLevel: "low",
    minorSafe: true,
    critsToPass: 2,
    laws: ["民法典相邻关系：相邻各方应当按照有利生产、方便生活、团结互助、公平合理原则处理相邻关系。"],
    criteria: ["表达边界", "保持冷静", "提出规则化处理", "必要时留存记录"],
    lines: {
      low: ["你这么说不就是想让我什么都别干？", "大家都能忍，怎么就你不行？"],
      mid: ["你要投诉就投诉，我还怕你不成？", "别拿规矩压我，你先证明是我。"],
      high: ["你再说一句试试，我现在就找你理论。", "你录啊，我看你能怎么样。"],
      yield: ["行，我今晚注意点，你也别把事情闹大。", "那先按物业规定处理，别吵了。"],
    },
    hint: "我理解你有生活需求，但现在是休息时间。请把音量降下来；如果持续影响休息，我会记录时间并联系物业按规则处理。",
  },
  {
    id: "relative-pressure",
    moduleId: "domestic",
    title: "亲戚道德绑架",
    premise: "亲戚临时要求你承担不合理费用，并用家人关系施压。",
    personaName: "施压亲戚",
    opening: "都是一家人，你条件好一点，帮一下怎么了？别这么计较。",
    riskLevel: "low",
    minorSafe: true,
    critsToPass: 2,
    laws: ["民法典自愿原则：民事主体从事民事活动，应当遵循自愿原则。"],
    criteria: ["礼貌拒绝", "不解释过度", "给出可行边界", "不被情绪裹挟"],
    lines: {
      low: ["你这样太冷漠了吧？", "你是不是看不起我们家？"],
      mid: ["我话都说到这份上了，你还不帮？", "以后家里有事你也别开口。"],
      high: ["我现在就告诉大家你多自私。", "你必须今天给个说法。"],
      yield: ["那我知道你的意思了。", "既然你说清楚了，我再想别的办法。"],
    },
    hint: "我理解你现在有压力，但这笔费用我不能承担。我能做的是帮你一起梳理其他方案，这个边界我不会改变。",
  },
  {
    id: "merchant-rights",
    moduleId: "legal",
    title: "商家拒绝退款",
    premise: "商品存在明显问题，商家以“售出不退”为由拒绝处理。",
    personaName: "强硬商家",
    opening: "我们店规写得很清楚，售出概不退换，你找谁都没用。",
    riskLevel: "medium",
    minorSafe: false,
    critsToPass: 2,
    laws: ["消费者权益保护法：消费者享有知悉真实情况、公平交易、依法求偿等权利。"],
    criteria: ["提出事实", "保存凭证", "明确诉求", "说明合法渠道"],
    lines: {
      low: ["你说有问题就有问题？", "我们一直都是这个规矩。"],
      mid: ["别吓唬我，投诉也没用。", "你自己不会用，不能怪我们。"],
      high: ["你再闹我就让保安处理。", "我们不可能赔，你爱去哪去哪。"],
      yield: ["那你把凭证发来，我们登记处理。", "可以先走检测流程。"],
    },
    hint: "我不接受“售出概不退换”排除法定责任。商品问题、付款记录和沟通记录我会保留，请按消费者权益保护法给出退换或检测方案。",
  },
  {
    id: "campus-boundary",
    moduleId: "domestic",
    title: "校园冒犯与求助",
    premise: "同学反复拿你的隐私开玩笑，周围有人起哄。",
    personaName: "起哄同学",
    opening: "开个玩笑而已，你这么认真干嘛？不会真生气了吧？",
    riskLevel: "low",
    minorSafe: true,
    critsToPass: 2,
    laws: ["未成年人保护相关原则：学校应当保护未成年人人格尊严，预防欺凌。"],
    criteria: ["明确不舒服", "要求停止", "寻求成年人帮助", "不互相羞辱"],
    lines: {
      low: ["大家都笑了，你别扫兴。", "你不让说是不是心虚？"],
      mid: ["你去告老师啊，谁怕谁。", "以后我们都不带你玩。"],
      high: ["你敢说出去试试。", "我就说了，你能怎么样？"],
      yield: ["行，不说了。", "那你别告状，我以后注意。"],
    },
    hint: "我不接受你拿我的隐私开玩笑，请立刻停止。如果继续，我会保留记录并找老师或家长帮助处理。",
  },
  {
    id: "overseas-slur",
    moduleId: "overseas",
    title: "海外种族挑衅",
    premise: "公共场所遇到带有歧视意味的挑衅，需要英文得体回应并优先避险。",
    personaName: "挑衅路人",
    opening: "Why are you even here? Go back where you came from.",
    riskLevel: "medium",
    minorSafe: false,
    critsToPass: 2,
    laws: ["海外场景原则：避免升级冲突，优先离开现场并向场地方、学校或警方求助。"],
    criteria: ["简短英文边界", "不回骂", "拉开距离", "求助或取证"],
    lines: {
      low: ["What, you can't speak now?", "I'm just saying the truth."],
      mid: ["You people are always too sensitive.", "Don't record me."],
      high: ["Come here and say that again.", "I'll make you leave."],
      yield: ["Fine, whatever.", "Okay, I'm leaving."],
    },
    hint: "Do not speak to me like that. I am stepping away now, and I will report this to staff/security. Please keep your distance.",
  },
  {
    id: "rage-deescalation",
    moduleId: "negotiation",
    title: "暴怒对峙降温",
    premise: "对方情绪激动、声音很大，并试图把你拉入争吵。",
    personaName: "暴怒对峙者",
    opening: "你今天必须给我说清楚！别想走！",
    riskLevel: "high",
    minorSafe: false,
    critsToPass: 3,
    laws: ["治安管理处罚法相关风险：避免互殴、威胁、侮辱等升级行为。"],
    criteria: ["承认情绪不承认指控", "降低音量", "给选择", "必要时离场求助"],
    lines: {
      low: ["你别装冷静，我就问你怎么办？", "你现在必须回答。"],
      mid: ["你是不是心虚？", "你敢走我就追上去。"],
      high: ["我控制不住了，你别逼我。", "今天谁也别想好过。"],
      yield: ["那你先说方案。", "行，先停一下。"],
    },
    hint: "我听到你很生气，但我不会在威胁和吼叫中处理问题。我们先各退一步，保持距离，再按事实说下一步；如果继续升级，我会离开并求助。",
  },
];

const redLines = [
  { id: "r-insult", category: "insult", keywords: ["滚", "废物", "傻", "垃圾", "贱", "idiot", "stupid"], message: "出现辱骂，会把安全训练变成互撕。", alternative: "我不同意你的说法，也不会接受这种沟通方式。请回到事实和规则。", law: "民法典人格权保护：避免侮辱、诽谤等侵权风险。" },
  { id: "r-violence", category: "violence", keywords: ["打你", "弄死", "揍", "动手", "砸", "kill", "hit you"], message: "出现暴力威胁，直接判定违规失分。", alternative: "我不会使用威胁或暴力。如果你继续靠近，我会离开并求助。", law: "治安管理处罚法：殴打、威胁他人人身安全可能承担法律责任。" },
  { id: "r-illegal", category: "illegal", keywords: ["曝光你身份证", "人肉", "砸店", "堵门", "威胁你家人"], message: "违法维权会让自己从受害方变成风险方。", alternative: "我会保留凭证，通过平台、消协、物业、学校或公安等合法渠道处理。", law: "民法典与个人信息保护相关规则：不得非法公开他人隐私和个人信息。" },
  { id: "r-foreign", category: "foreign", keywords: ["你们国家都", "你这种种族", "racist back", "your race"], message: "涉外场景中使用歧视性反击会放大风险。", alternative: "Please keep your distance. I do not accept discriminatory language and will report this to staff/security.", law: "涉外冲突优先避险、留证、求助，避免歧视性反击。" },
];

const scoreRules = [
  { id: "g-boundary", dimension: "boundary", keywords: ["不接受", "请停止", "不能", "边界", "不会", "keep your distance", "do not"], weight: 18 },
  { id: "g-calm", dimension: "calm", keywords: ["我理解", "我听到", "冷静", "先停", "我们先", "I hear", "I understand"], weight: 14 },
  { id: "g-legal", dimension: "legal", keywords: ["规则", "法律", "民法典", "消费者权益", "物业", "学校", "平台", "公安", "report", "security"], weight: 18 },
  { id: "g-deescalate", dimension: "deescalate", keywords: ["保持距离", "离开", "不争吵", "不升级", "按事实", "下一步", "step away"], weight: 16 },
  { id: "g-evidence", dimension: "evidence", keywords: ["记录", "录音", "凭证", "截图", "保留", "证据", "record"], weight: 14 },
  { id: "g-polite", dimension: "polite", keywords: ["请", "谢谢", "麻烦", "please"], weight: 8 },
  { id: "g-risk", dimension: "risk-avoid", keywords: ["求助", "找老师", "家长", "消协", "报警", "工作人员", "staff"], weight: 12 },
  { id: "p-blame", dimension: "deescalate", keywords: ["都怪你", "你必须", "少废话", "闭嘴"], weight: -18 },
  { id: "p-empty", dimension: "boundary", keywords: ["随便", "算了", "没事", "都行"], weight: -12 },
];

const badges = [
  { id: "calm", title: "零情绪失控", desc: "无违规完成一局" },
  { id: "crit", title: "合规暴击达人", desc: "累计 3 次暴击" },
  { id: "evidence", title: "取证意识", desc: "使用记录/凭证/证据话术" },
  { id: "minor", title: "自保入门", desc: "完成青少年安全关卡" },
];

let audience = "minor";
let activeScenario = scenarios[0];
let state = freshState(activeScenario);
let progress = loadProgress();

const $ = (id) => document.getElementById(id);

function freshState(scenario) {
  return { scenarioId: scenario.id, turns: [{ role: "opponent", text: scenario.opening }], confrontation: 50, crits: 0, violations: 0, completed: false };
}

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

function textHits(text, keywords) {
  const lower = text.toLowerCase();
  return keywords.some((k) => lower.includes(k.toLowerCase()));
}

function detectRisk(text) {
  return redLines.find((r) => textHits(text, r.keywords)) || null;
}

function scoreReply(text) {
  const risk = detectRisk(text);
  if (risk) {
    return { tier: "violation", score: 0, delta: 22, hits: [], penalties: [risk.id], risk, reason: risk.message };
  }

  const hits = [];
  const penalties = [];
  let score = Math.min(18, Math.floor(text.trim().length / 4));
  for (const rule of scoreRules) {
    if (textHits(text, rule.keywords)) {
      score += rule.weight;
      if (rule.weight > 0) hits.push(rule);
      else penalties.push(rule.id);
    }
  }
  const uniqueDimensions = new Set(hits.map((h) => h.dimension));
  const tier = score >= 72 && uniqueDimensions.size >= 5 ? "crit" : score >= 38 ? "weak" : "weak";
  const delta = tier === "crit" ? -30 : penalties.length ? 8 : -6;
  const reason = tier === "crit" ? "精准暴击：边界、冷静、合规、止损与取证意识形成闭环。" : "普通回应：没有违规，但边界或行动路径还不够清晰。";
  return { tier, score: Math.max(0, Math.min(100, score)), delta, hits, penalties, risk: null, reason };
}

function opponentReply(scenario, judgement, confrontation, turnIndex) {
  if (judgement.tier === "violation") return "你也开始威胁/辱骂了？这样事情只会更糟。";
  if (judgement.tier === "crit") return pick(scenario.lines.yield, turnIndex);
  if (confrontation >= 70) return pick(scenario.lines.high, turnIndex);
  if (confrontation >= 46) return pick(scenario.lines.mid, turnIndex);
  return pick(scenario.lines.low, turnIndex);
}

function pick(list, index) {
  return list[index % list.length];
}

function clamp(n, min, max) {
  return Math.max(min, Math.min(max, n));
}

function submitReply(text) {
  if (!text.trim() || state.completed) return;
  const judgement = scoreReply(text);
  state.turns.push({ role: "user", text, judgement });
  state.confrontation = clamp(state.confrontation + judgement.delta, 0, 100);
  if (judgement.tier === "crit") state.crits += 1;
  if (judgement.tier === "violation") state.violations += 1;
  state.completed = state.violations > 0 || state.crits >= activeScenario.critsToPass || state.confrontation >= 95 || state.turns.length >= 9;
  if (!state.completed) {
    const reply = opponentReply(activeScenario, judgement, state.confrontation, state.turns.length);
    const safeReply = detectRisk(reply) ? "我们先暂停。请通过合法渠道处理，不继续升级。" : reply;
    state.turns.push({ role: "opponent", text: safeReply, judgement: null });
  }
  if (state.completed) awardProgress();
  render();
}

function awardProgress() {
  const passed = state.crits >= activeScenario.critsToPass && state.violations === 0;
  const xp = passed ? 80 + state.crits * 20 : state.violations ? 10 : 35;
  progress.xp += xp;
  progress.crits += state.crits;
  if (passed && !progress.completed.includes(activeScenario.id)) progress.completed.push(activeScenario.id);
  if (passed && state.violations === 0) addBadge("calm");
  if (progress.crits >= 3) addBadge("crit");
  if (state.turns.some((t) => t.role === "user" && /记录|凭证|证据|截图|录音|record/i.test(t.text))) addBadge("evidence");
  if (passed && audience === "minor") addBadge("minor");
  saveProgress();
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

function availableScenarios() {
  return scenarios.filter((s) => audience === "adult" || s.minorSafe);
}

function selectScenario(id) {
  const next = scenarios.find((s) => s.id === id);
  if (!next || (audience === "minor" && !next.minorSafe)) return;
  activeScenario = next;
  state = freshState(next);
  render();
}

function debrief() {
  const userTurns = state.turns.filter((t) => t.role === "user");
  if (userTurns.length === 0) return null;
  const passed = state.crits >= activeScenario.critsToPass && state.violations === 0;
  const errors = userTurns
    .map((t, i) => ({ t, i }))
    .filter(({ t }) => t.judgement.tier !== "crit")
    .map(({ t, i }) => ({
      turn: i + 1,
      text: t.text,
      issue: t.judgement.tier === "violation" ? t.judgement.reason : "回应偏弱：需要更明确的边界、规则渠道或取证意识。",
      alt: t.judgement.risk ? t.judgement.risk.alternative : activeScenario.hint,
    }));
  const best = userTurns.filter((t) => t.judgement.tier === "crit").map((t) => t.text);
  return { passed, errors, best, xp: passed ? 80 + state.crits * 20 : state.violations ? 10 : 35 };
}

function render() {
  renderScenarios();
  renderProgress();
  renderArena();
  renderReport();
}

function renderScenarios() {
  const list = $("scenarioList");
  const available = availableScenarios();
  $("scenarioCount").textContent = `${available.length} 个可训练`;
  list.innerHTML = scenarios.map((s) => {
    const locked = audience === "minor" && !s.minorSafe;
    return `<button type="button" class="scenario-card ${s.id === activeScenario.id ? "active" : ""} ${locked ? "locked" : ""}" data-scenario="${s.id}" ${locked ? "disabled" : ""}>
      <strong>${s.title}</strong>
      <span>${modules[s.moduleId]} · ${riskLabel(s.riskLevel)}${locked ? " · 青少年模式隐藏" : ""}</span>
    </button>`;
  }).join("");
  list.querySelectorAll("button[data-scenario]").forEach((btn) => btn.addEventListener("click", () => selectScenario(btn.dataset.scenario)));
}

function riskLabel(level) {
  return { low: "低风险", medium: "中风险", high: "高风险", extreme: "极高风险" }[level];
}

function renderProgress() {
  $("levelTitle").textContent = levelTitle();
  $("xpValue").textContent = progress.xp;
  $("xpBar").style.width = `${Math.min(100, progress.xp % 300 / 3)}%`;
  $("badgeList").innerHTML = badges.map((b) => `<span class="badge ${progress.badges.includes(b.id) ? "earned" : ""}" title="${b.desc}">${b.title}</span>`).join("");
}

function renderArena() {
  $("moduleTag").textContent = modules[activeScenario.moduleId];
  $("scenarioTitle").textContent = activeScenario.title;
  $("scenarioPremise").textContent = activeScenario.premise;
  $("criteriaStrip").innerHTML = activeScenario.criteria.map((c) => `<span class="chip">${c}</span>`).join("");
  $("confrontationValue").textContent = state.confrontation;
  const bar = $("confrontationBar");
  bar.style.width = `${state.confrontation}%`;
  bar.style.background = state.confrontation >= 75 ? "var(--danger)" : state.confrontation >= 48 ? "var(--warn)" : "var(--good)";
  $("dialogueLog").innerHTML = state.turns.map((t) => turnHtml(t)).join("");
  $("dialogueLog").scrollTop = $("dialogueLog").scrollHeight;
  const lastJudge = [...state.turns].reverse().find((t) => t.judgement)?.judgement;
  $("coachTitle").textContent = lastJudge ? judgeTitle(lastJudge.tier, lastJudge.score) : "等待你的第一句回应";
  $("coachText").textContent = lastJudge ? coachText(lastJudge) : "暴击标准：边界清晰、情绪稳定、合规合法、止损控场、有取证或求助意识。";
  $("replyInput").disabled = state.completed;
}

function turnHtml(t) {
  const who = t.role === "user" ? "你" : activeScenario.personaName;
  const tag = t.judgement ? `<span class="judge-tag ${t.judgement.tier}">${judgeLabel(t.judgement.tier)} · ${t.judgement.score}分</span>` : "";
  return `<article class="turn ${t.role}"><span class="speaker">${who}</span><div class="bubble">${escapeHtml(t.text)}</div>${tag}</article>`;
}

function judgeLabel(tier) {
  return { crit: "精准暴击", weak: "普通回应", violation: "违规失分" }[tier];
}

function judgeTitle(tier, score) {
  return `${judgeLabel(tier)} · ${score}分`;
}

function coachText(j) {
  if (j.tier === "violation") return `${j.reason} 替代话术：${j.risk.alternative}`;
  if (j.tier === "crit") return `命中 ${new Set(j.hits.map((h) => h.dimension)).size} 个维度。对峙值下降 ${Math.abs(j.delta)}，继续保持事实、规则和求助路径。`;
  return "这句没有踩红线，但建议补上：明确边界 + 规则渠道 + 记录/求助。";
}

function renderReport() {
  const d = debrief();
  if (!d) {
    $("reportBody").className = "empty-report";
    $("reportBody").textContent = "完成至少一轮回应后，这里会生成错误点、法律风险、最优话术和通关结论。";
    return;
  }
  $("reportBody").className = "";
  const laws = activeScenario.laws.map((l) => `<li>${l}</li>`).join("");
  const errors = d.errors.length ? d.errors.map((e) => `<li>第 ${e.turn} 轮：${e.issue}<br><strong>替代：</strong>${escapeHtml(e.alt)}</li>`).join("") : "<li>本局没有明显错误点。</li>";
  const best = d.best.length ? d.best.map((b) => `<li>${escapeHtml(b)}</li>`).join("") : "<li>还没有形成暴击话术，试着补齐五大标准。</li>";
  $("reportBody").innerHTML = `
    <div class="report-metric">
      <div><strong>${d.passed ? "通过" : state.completed ? "未通过" : "训练中"}</strong><span>结论</span></div>
      <div><strong>${state.crits}</strong><span>暴击</span></div>
      <div><strong>${d.xp}</strong><span>预估 XP</span></div>
    </div>
    <p class="label">错误点与替代话术</p><ul class="report-list">${errors}</ul>
    <p class="label">本局最佳话术</p><ul class="report-list">${best}</ul>
    <p class="label">合规依据</p><ul class="report-list">${laws}</ul>`;
}

function escapeHtml(text) {
  return text.replace(/[&<>"]/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[m]));
}

document.querySelectorAll(".mode-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    audience = btn.dataset.audience;
    document.querySelectorAll(".mode-btn").forEach((b) => b.classList.toggle("active", b === btn));
    if (audience === "minor" && !activeScenario.minorSafe) activeScenario = availableScenarios()[0];
    state = freshState(activeScenario);
    render();
  });
});

$("replyForm").addEventListener("submit", (event) => {
  event.preventDefault();
  const input = $("replyInput");
  submitReply(input.value);
  input.value = "";
});

$("hintBtn").addEventListener("click", () => {
  $("replyInput").value = activeScenario.hint;
  $("replyInput").focus();
});

$("resetBtn").addEventListener("click", () => {
  state = freshState(activeScenario);
  $("replyInput").disabled = false;
  render();
});

render();
