/* Адал Кеңесші — веб-клиент.
 * Без фреймворков: чистый JavaScript, чтобы код было легко объяснить.
 * marked — Markdown → HTML, DOMPurify — очистка HTML от XSS.
 */
"use strict";

// ---------- Тексты интерфейса (RU / KZ) ----------
const I18N = {
  ru: {
    tagline: "AI-навигатор по внутренней политике РК",
    tab_chat: "Чат", tab_concepts: "Ценности", tab_quiz: "Квиз", tab_sources: "Источники",
    eyebrow: "Конституция 2026 · Послания · Ценности",
    hero1: "Честные ответы", hero2: "о главном в стране",
    hero_lead: "Спросите, например:",
    stat1: "статей Конституции", stat2: "официальных документов", stat3: "фрагментов в базе", stat4: "языка: қазақша, русский",
    placeholder: "Спросите о Конституции, ценностях, Посланиях…",
    disclaimer: "Бот не является государственным органом. Ответы формируются по официальным документам; для юридически значимых решений сверяйтесь с первоисточником.",
    concepts_eyebrow: "Указ № 1081 от 5 ноября 2025 г.",
    concepts_title: "Принципы и ценности внутренней политики",
    concepts_text: "Отметка показывает, закреплено ли понятие в Конституции 2026 года.",
    quiz_eyebrow: "Геймификация",
    quiz_title: "Квиз «Адал азамат»",
    quiz_text: "7 вопросов по Конституции 2026 и ценностям внутренней политики. Каждый ответ — со ссылкой на документ.",
    sources_title: "База знаний",
    sources_text: "Бот отвечает только по этим официальным документам. Каждый ответ содержит ссылку на первоисточник.",
    step_search: "Ищу в 1575 фрагментах официальных документов",
    step_found: "Найдено {n} фрагментов{c}",
    step_found_c: " · {k} из Конституции",
    step_rewrite: "Уточнил вопрос: «{q}»",
    step_none: "Подходящих документов не найдено",
    step_write: "Пишу ответ со ссылками на источники",
    sources: "Все найденные фрагменты ({n})", open_src: "Открыть первоисточник ↗",
    article: "Статья", preamble: "Преамбула",
    copy: "Копировать", copied: "Скопировано", listen: "Озвучить", stop_listen: "Стоп",
    helpful: "Полезно", not_helpful: "Не полезно", thanks: "Спасибо за оценку!",
    const_tag: "📜 Конституция 2026", n_sources: "{n} источн.",
    stopped: "Генерация остановлена.",
    net_error: "Нет соединения с сервером. Проверьте интернет и попробуйте снова.",
    ask_bot: "Спросить бота →",
    const_direct: "📜 Закреплено в Конституции 2026", const_related: "🔗 Связано с Конституцией 2026", const_none: "В Конституции не упоминается",
    quiz_intro: "Проверьте, насколько хорошо вы знаете новую Конституцию и ценности страны. Займёт 2 минуты.",
    quiz_start: "Начать квиз", quiz_q: "Вопрос {i} из {n}",
    quiz_nick: "Ваше имя для таблицы лидеров (необязательно)", quiz_submit: "Узнать результат",
    quiz_result: "Ваш результат", quiz_again: "Пройти ещё раз", quiz_leaders: "🏆 Таблица лидеров",
    quiz_source: "Источник", quiz_correct: "Верно", quiz_wrong: "Неверно",
    quiz_level: ["Загляните во вкладку «Ценности» — там всё кратко!", "Хорошее начало, Адал азамат!", "Отлично! Вы хорошо знаете ценности страны.", "Превосходно! Настоящий эксперт."],
    types: { constitution: "Конституция", decree: "Указ", address: "Послание", speech: "Выступление", concept: "Статья", law: "Закон" },
    suggestions: [
      ["📜", "Конституция 2026", "Какие принципы закреплены в статье 3 Конституции?", true],
      ["⚖️", "Закон и Порядок", "Что такое «Закон и Порядок» и закреплён ли он в Конституции?", true],
      ["🤝", "Ценности", "Кто такой «Адал азамат»?"],
      ["🏛️", "Курултай", "Как устроен Курултай по новой Конституции?"],
      ["👂", "Принципы", "Что означает «Слышащее государство» на практике?"],
      ["🛡️", "Антикоррупция", "Что такое коррупция и конфликт интересов по закону РК?"],
    ],
  },
  kk: {
    tagline: "ҚР ішкі саясаты бойынша AI-навигатор",
    tab_chat: "Чат", tab_concepts: "Құндылықтар", tab_quiz: "Квиз", tab_sources: "Дереккөздер",
    eyebrow: "2026 Конституциясы · Жолдаулар · Құндылықтар",
    hero1: "Елдің басты құжаттары", hero2: "туралы адал жауаптар",
    hero_lead: "Мысалы, сұраңыз:",
    stat1: "Конституция бабы", stat2: "ресми құжат", stat3: "базадағы үзінді", stat4: "тіл: қазақша, орысша",
    placeholder: "Конституция, құндылықтар, Жолдаулар туралы сұраңыз…",
    disclaimer: "Бот мемлекеттік орган емес. Жауаптар ресми құжаттар негізінде беріледі; заңдық маңызы бар шешімдер үшін бастапқы дереккөзді тексеріңіз.",
    concepts_eyebrow: "2025 жылғы 5 қарашадағы № 1081 Жарлық",
    concepts_title: "Ішкі саясаттың қағидаттары мен құндылықтары",
    concepts_text: "Белгі ұғымның 2026 жылғы Конституцияда бекітілгенін көрсетеді.",
    quiz_eyebrow: "Геймификация",
    quiz_title: "«Адал азамат» квизі",
    quiz_text: "2026 жылғы Конституция мен ішкі саясат құндылықтары бойынша 7 сұрақ. Әр жауап құжатқа сілтемемен.",
    sources_title: "Білім базасы",
    sources_text: "Бот тек осы ресми құжаттар негізінде жауап береді. Әр жауапта бастапқы дереккөзге сілтеме бар.",
    step_search: "Ресми құжаттардың 1575 үзіндісінен іздеп жатырмын",
    step_found: "{n} үзінді табылды{c}",
    step_found_c: " · {k} — Конституциядан",
    step_rewrite: "Сұрақты нақтыладым: «{q}»",
    step_none: "Сәйкес құжат табылмады",
    step_write: "Дереккөзге сілтемемен жауап жазып жатырмын",
    sources: "Табылған барлық үзінділер ({n})", open_src: "Бастапқы дереккөзді ашу ↗",
    article: "бап", preamble: "Кіріспе",
    copy: "Көшіру", copied: "Көшірілді", listen: "Тыңдау", stop_listen: "Тоқтату",
    helpful: "Пайдалы", not_helpful: "Пайдасыз", thanks: "Бағаңызға рахмет!",
    const_tag: "📜 2026 Конституциясы", n_sources: "{n} дереккөз",
    stopped: "Жауап тоқтатылды.",
    net_error: "Сервермен байланыс жоқ. Интернетті тексеріп, қайталап көріңіз.",
    ask_bot: "Боттан сұрау →",
    const_direct: "📜 2026 Конституциясында бекітілген", const_related: "🔗 2026 Конституциясымен байланысты", const_none: "Конституцияда аталмайды",
    quiz_intro: "Жаңа Конституция мен ел құндылықтарын қаншалықты білетініңізді тексеріңіз. 2 минут қана.",
    quiz_start: "Квизді бастау", quiz_q: "{n} сұрақтың {i}-сі",
    quiz_nick: "Көшбасшылар кестесі үшін атыңыз (міндетті емес)", quiz_submit: "Нәтижені білу",
    quiz_result: "Сіздің нәтижеңіз", quiz_again: "Қайта өту", quiz_leaders: "🏆 Көшбасшылар кестесі",
    quiz_source: "Дереккөз", quiz_correct: "Дұрыс", quiz_wrong: "Қате",
    quiz_level: ["«Құндылықтар» бөлімін қараңыз — бәрі қысқа әрі нұсқа!", "Жақсы бастама, Адал азамат!", "Керемет! Ел құндылықтарын жақсы білесіз.", "Тамаша! Нағыз сарапшы."],
    types: { constitution: "Конституция", decree: "Жарлық", address: "Жолдау", speech: "Сөз", concept: "Мақала", law: "Заң" },
    suggestions: [
      ["📜", "2026 Конституциясы", "Конституцияның 3-бабында қандай қағидаттар бекітілген?", true],
      ["⚖️", "Заң мен Тәртіп", "«Заң мен Тәртіп» деген не және ол Конституцияда бекітілген бе?", true],
      ["🤝", "Құндылықтар", "«Адал азамат» дегеніміз кім?"],
      ["🏛️", "Құрылтай", "Жаңа Конституция бойынша Құрылтай қалай құрылады?"],
      ["👂", "Қағидаттар", "«Халық үніне құлақ асатын мемлекет» іс жүзінде нені білдіреді?"],
      ["🛡️", "Сыбайлас жемқорлық", "Заң бойынша сыбайлас жемқорлық және мүдделер қақтығысы дегеніміз не?"],
    ],
  },
};

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
const state = {
  lang: safeGet("lang") || "ru",
  history: [],          // последние реплики для контекста диалога
  controller: null,     // AbortController текущего запроса
  loaded: {},
};

function safeGet(k) { try { return localStorage.getItem(k); } catch { return null; } }
function safeSet(k, v) { try { localStorage.setItem(k, v); } catch { /* приватный режим */ } }
const t = (key, vars = {}) => String(I18N[state.lang][key] ?? key).replace(/\{(\w+)\}/g, (_, v) => vars[v] ?? "");
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ---------- Шаңырақ — национальный символ единства, «сердце» бота ----------
function shanyrakSVG(draw = false) {
  const uyk = Array.from({ length: 24 }, (_, i) => {
    const a = (i * 15 * Math.PI) / 180;
    const p = (r) => [(50 + Math.cos(a) * r).toFixed(2), (50 + Math.sin(a) * r).toFixed(2)];
    const [x1, y1] = p(41.5), [x2, y2] = p(49);
    return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"/>`;
  }).join("");
  return `<svg class="shanyrak${draw ? " draw" : ""}" viewBox="0 0 100 100" aria-hidden="true">
    <g class="uyk">${uyk}</g>
    <circle class="core" cx="50" cy="50" r="33"/>
    <circle class="ring" cx="50" cy="50" r="38" stroke="url(#sh-grad)"/>
    <circle class="ring-in" cx="50" cy="50" r="33"/>
    <g class="bars">
      <path d="M40 18.6Q36.5 50 40 81.4"/><path d="M50 17V83"/><path d="M60 18.6Q63.5 50 60 81.4"/>
      <path d="M18.6 40Q50 36.5 81.4 40"/><path d="M17 50H83"/><path d="M18.6 60Q50 63.5 81.4 60"/>
    </g>
  </svg>`;
}
document.body.insertAdjacentHTML("afterbegin",
  `<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>
     <linearGradient id="sh-grad" x1="0" y1="0" x2="1" y2="1">
       <stop offset="0" stop-color="#00A3C4"/><stop offset=".55" stop-color="#2BC0DE"/><stop offset="1" stop-color="#F5B800"/>
     </linearGradient></defs></svg>`);
$$(".shanyrak-slot").forEach((el) => { el.innerHTML = shanyrakSVG(el.dataset.size === "orb"); });

// ---------- Тема ----------
function isDark() {
  const forced = document.documentElement.dataset.theme;
  return forced ? forced === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
}
const savedTheme = safeGet("theme");
if (savedTheme) document.documentElement.dataset.theme = savedTheme;
$("#theme").addEventListener("click", () => {
  const next = isDark() ? "light" : "dark";
  const apply = () => { document.documentElement.dataset.theme = next; };
  document.startViewTransition && !reduceMotion ? document.startViewTransition(apply) : apply();
  safeSet("theme", next);
});

// ---------- Язык ----------
function applyLang() {
  document.documentElement.lang = state.lang === "kk" ? "kk" : "ru";
  $$("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
  $$("[data-i18n-ph]").forEach((el) => { el.placeholder = t(el.dataset.i18nPh); });
  $$(".lang-switch button").forEach((b) => b.classList.toggle("active", b.dataset.lang === state.lang));
  $(".lang-switch").dataset.pos = state.lang === "kk" ? "0" : "1";
  renderSuggestions();
  startTyper();
  state.loaded = {};  // перерисовать вкладки на новом языке
  const active = $(".tab.active").dataset.tab;
  if (active !== "chat") loadTab(active);
  requestAnimationFrame(moveTabIndicator);
}
$$(".lang-switch button").forEach((b) =>
  b.addEventListener("click", () => { state.lang = b.dataset.lang; safeSet("lang", state.lang); applyLang(); }));

// ---------- Вкладки (с плавным индикатором и View Transitions) ----------
function moveTabIndicator() {
  const a = $(".tab.active"), ind = $(".tab-ind");
  if (!a || !ind) return;
  ind.style.width = a.offsetWidth + "px";
  ind.style.transform = `translateX(${a.offsetLeft}px)`;
}
addEventListener("resize", moveTabIndicator);
document.fonts?.ready.then(moveTabIndicator);
$$(".tab").forEach((tab) => tab.addEventListener("click", () => switchTab(tab.dataset.tab)));
function switchTab(name) {
  const apply = () => {
    $$(".tab").forEach((x) => { x.classList.toggle("active", x.dataset.tab === name); x.setAttribute("aria-selected", x.dataset.tab === name); });
    $$(".panel").forEach((p) => p.classList.toggle("active", p.id === `tab-${name}`));
    moveTabIndicator();
    loadTab(name);
  };
  document.startViewTransition && !reduceMotion ? document.startViewTransition(apply) : apply();
}
function loadTab(name) {
  if (state.loaded[name]) return;
  state.loaded[name] = true;
  if (name === "concepts") loadConcepts();
  if (name === "quiz") quizIntro();
  if (name === "sources") loadSources();
}

// ---------- Подсветка карточек под курсором ----------
document.addEventListener("pointermove", (e) => {
  const card = e.target.closest?.(".chip, .concept");
  if (!card) return;
  const r = card.getBoundingClientRect();
  card.style.setProperty("--mx", `${e.clientX - r.left}px`);
  card.style.setProperty("--my", `${e.clientY - r.top}px`);
});

// ---------- Приветствие: подсказки, «печатная машинка», счётчики ----------
function renderSuggestions() {
  const box = $("#suggestions");
  if (!box) return;
  box.innerHTML = I18N[state.lang].suggestions.map(([icon, label, q, gold], i) => `
    <button class="chip ${gold ? "gold" : ""}" style="--i:${i}" data-q="${esc(q)}">
      <span class="chip-top"><span class="chip-cat">${esc(label)}</span><span class="chip-ic">${icon}</span></span>
      <span class="chip-q">${esc(q)}</span>
      <span class="chip-go" aria-hidden="true">→</span>
    </button>`).join("");
  $$(".chip", box).forEach((b) => b.addEventListener("click", () => ask(b.dataset.q)));
}

let typerRun = 0;
async function startTyper() {
  const el = $("#typer");
  if (!el) return;
  const run = ++typerRun;
  const qs = I18N[state.lang].suggestions.map((s) => s[2]);
  if (reduceMotion) { el.textContent = qs[0]; return; }
  for (let k = 0; run === typerRun && document.contains(el); k = (k + 1) % qs.length) {
    const q = qs[k];
    for (let i = 1; i <= q.length && run === typerRun; i++) { el.textContent = q.slice(0, i); await sleep(32); }
    await sleep(2200);
    for (let i = q.length; i >= 0 && run === typerRun; i--) { el.textContent = q.slice(0, i); await sleep(14); }
    await sleep(300);
  }
}

async function countUp() {
  // Актуальные размеры базы знаний — с сервера
  try {
    const h = await fetch("/api/health").then((r) => r.json());
    if (h.documents) $('.stat b[data-count="31"]')?.setAttribute("data-count", h.documents);
    if (h.chunks) $('.stat b[data-count="1575"]')?.setAttribute("data-count", h.chunks);
  } catch { /* оставим значения из разметки */ }
  $$(".stat b[data-count]").forEach((el) => {
    const end = +el.dataset.count;
    if (reduceMotion) return;
    const t0 = performance.now(), dur = 1400;
    const tick = (now) => {
      const p = Math.min(1, (now - t0) / dur);
      el.textContent = Math.round(end * (1 - Math.pow(1 - p, 3)));
      if (p < 1) requestAnimationFrame(tick);
    };
    el.textContent = "0";
    setTimeout(() => requestAnimationFrame(tick), 700);
  });
}

// ---------- Чат ----------
const input = $("#input");
const sendBtn = $("#send");
const composer = $("#chat-form");
const messagesEl = $("#messages");

composer.addEventListener("submit", (e) => {
  e.preventDefault();
  if (state.controller) { state.controller.abort(); return; }  // кнопка «стоп»
  ask(input.value);
});
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); composer.requestSubmit(); }
});
input.addEventListener("input", autoGrow);
function autoGrow() { input.style.height = "auto"; input.style.height = Math.min(input.scrollHeight, 160) + "px"; }

function setBusy(busy) {
  sendBtn.classList.toggle("stop", busy);
  composer.classList.toggle("busy", busy);
  sendBtn.setAttribute("aria-label", busy ? "Стоп" : "Отправить");
}

function scrollDown() { messagesEl.scrollTop = messagesEl.scrollHeight; }

function addUserMsg(text) {
  const el = document.createElement("div");
  el.className = "msg user";
  el.innerHTML = `<div class="bubble"></div>`;
  el.firstChild.textContent = text;
  messagesEl.appendChild(el);
}

function addBotMsg() {
  const el = document.createElement("div");
  el.className = "msg bot thinking busy streaming";
  el.innerHTML = `
    <span class="avatar shanyrak-slot">${shanyrakSVG()}</span>
    <div class="bubble"><div class="steps"></div><div class="answer"></div><div class="extra"></div></div>`;
  messagesEl.appendChild(el);
  return el;
}

/** Шаги конвейера RAG — пользователь видит, что бот реально делает */
function addStep(stepsEl, text) {
  const row = document.createElement("div");
  row.className = "step-row run";
  row.innerHTML = `<span class="st"></span><span class="sx"></span>`;
  row.lastChild.textContent = text;
  stepsEl.appendChild(row);
  return row;
}
function finishStep(row, text) {
  if (!row) return;
  row.className = "step-row ok";
  row.firstChild.textContent = "✓";
  if (text) row.lastChild.textContent = text;
}

/** Markdown → безопасный HTML, затем [n] → кликабельные ссылки на источники */
function renderAnswer(container, text, sourcesCount) {
  container.innerHTML = DOMPurify.sanitize(marked.parse(text, { breaks: true }));
  // Строка «📜 Закреплено в Конституции» — золотая печать; «ℹ️» — нейтральная пометка
  $$("p, li", container).forEach((el) => {
    if (el.textContent.includes("📜")) el.classList.add("seal");
    else if (el.textContent.trim().startsWith("ℹ️")) el.classList.add("info-line");
  });
  if (!sourcesCount) return;
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) if (/\[\d{1,2}(?:,\s*\d{1,2})*\]/.test(walker.currentNode.nodeValue)) nodes.push(walker.currentNode);
  for (const node of nodes) {
    const frag = document.createDocumentFragment();
    node.nodeValue.split(/(\[\d{1,2}(?:,\s*\d{1,2})*\])/).forEach((part) => {
      const m = part.match(/^\[([\d,\s]+)\]$/);
      if (!m) { frag.appendChild(document.createTextNode(part)); return; }
      m[1].split(",").map((x) => +x.trim()).forEach((n) => {
        if (n < 1 || n > sourcesCount) return;
        const b = document.createElement("button");
        b.className = "cite"; b.type = "button"; b.textContent = n; b.dataset.n = n;
        frag.appendChild(b);
      });
    });
    node.replaceWith(frag);
  }
}

function srcWhere(s) {
  const L = I18N[state.lang];
  if (!s.article) return "";
  if (s.article === "преамбула" || s.article === "кіріспе") return L.preamble;
  return state.lang === "kk" ? `${s.article}-${L.article}` : `${L.article} ${s.article}`;
}

function sourceCard(s, cited) {
  const L = I18N[state.lang];
  const where = srcWhere(s);
  return `
    <div class="src ${cited ? "cited" : ""}" data-n="${s.n}">
      <div class="src-head"><span class="src-n">[${s.n}]</span>
        <span class="src-type ${s.is_constitution ? "const" : ""}">${esc(L.types[s.type] || s.type)}${where ? " · " + esc(where) : ""}${s.date ? " · " + esc(s.date) : ""}</span></div>
      <div class="src-title">${esc(s.title)}</div>
      <div class="src-snippet">${esc(s.snippet)}</div>
      <a href="${esc(s.link)}" target="_blank" rel="noopener noreferrer">${esc(t("open_src"))}</a>
    </div>`;
}

function renderSources(extra, sources, cited) {
  if (!sources.length) return;
  const L = I18N[state.lang];
  const citedSet = new Set(cited);
  const main = cited.length ? sources.filter((s) => citedSet.has(s.n)) : sources.slice(0, 3);
  const ordered = [...main, ...sources.filter((s) => !main.includes(s))];
  // Короткие «чипы» процитированных источников; полные карточки — по клику
  const chips = main.map((s, i) => `
    <button type="button" class="src-chip ${s.is_constitution ? "const" : ""}" style="--i:${i}" data-n="${s.n}">
      <b>${s.n}</b> ${s.is_constitution ? "📜 " : ""}${esc(L.types[s.type] || s.type)}${srcWhere(s) ? " · " + esc(srcWhere(s)) : ""}${!s.is_constitution && s.date ? " · " + esc(s.date.split(",")[0]) : ""}
    </button>`).join("");
  const box = document.createElement("div");
  box.innerHTML = `
    <div class="src-chips">${chips}</div>
    <details class="sources">
      <summary>${esc(t("sources", { n: sources.length }))}</summary>
      <div class="src-list">${ordered.map((s) => sourceCard(s, citedSet.has(s.n))).join("")}</div>
    </details>`;
  extra.appendChild(box);
}

function renderActions(extra, info, text, nSources) {
  const bar = document.createElement("div");
  bar.className = "actions";
  bar.innerHTML = `
    <button class="act" data-a="up" title="${esc(t("helpful"))}" aria-label="${esc(t("helpful"))}">👍</button>
    <button class="act" data-a="down" title="${esc(t("not_helpful"))}" aria-label="${esc(t("not_helpful"))}">👎</button>
    <button class="act" data-a="copy">⧉ ${esc(t("copy"))}</button>
    <button class="act" data-a="tts">🔊 ${esc(t("listen"))}</button>
    <span class="meta">${info.constitution ? `<span class="const-flag">${esc(t("const_tag"))}</span> · ` : ""}${nSources ? esc(t("n_sources", { n: nSources })) + " · " : ""}${(info.latency_ms / 1000).toFixed(1)} s</span>`;
  bar.addEventListener("click", async (e) => {
    const btn = e.target.closest(".act");
    if (!btn) return;
    const a = btn.dataset.a;
    if (a === "up" || a === "down") {
      $$('[data-a="up"],[data-a="down"]', bar).forEach((b) => b.classList.remove("on"));
      btn.classList.add("on");
      try {
        await fetch("/api/feedback", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query_id: info.query_id, value: a === "up" ? 1 : -1 }) });
        btn.title = t("thanks");
      } catch { /* оценка не критична */ }
    } else if (a === "copy") {
      try { await navigator.clipboard.writeText(text); btn.textContent = "✓ " + t("copied"); } catch { /* нет доступа */ }
    } else if (a === "tts") {
      speak(text, btn);
    }
  });
  extra.appendChild(bar);
}

// Клик по [n] или чипу — раскрыть и подсветить карточку источника
messagesEl.addEventListener("click", (e) => {
  const c = e.target.closest(".cite, .src-chip");
  if (!c) return;
  const card = $(`.src[data-n="${c.dataset.n}"]`, c.closest(".bubble"));
  if (!card) return;
  card.closest("details").open = true;
  card.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "nearest" });
  card.classList.add("flash");
  setTimeout(() => card.classList.remove("flash"), 1400);
});

async function ask(raw) {
  const question = String(raw || "").trim();
  if (!question || state.controller) return;
  if (!$("#tab-chat").classList.contains("active")) switchTab("chat");
  const welcome = $("#welcome");
  if (welcome) { typerRun++; welcome.remove(); }
  input.value = ""; autoGrow();
  addUserMsg(question);
  const el = addBotMsg();
  const stepsEl = $(".steps", el), answerEl = $(".answer", el), extra = $(".extra", el);
  let stepSearch = addStep(stepsEl, t("step_search")), stepWrite = null;
  scrollDown();

  state.controller = new AbortController();
  setBusy(true);
  let text = "", sources = [], done = null, pending = false;
  const paint = () => { pending = false; renderAnswer(answerEl, text, sources.length); scrollDown(); };

  try {
    const resp = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, history: state.history.slice(-6), lang: state.lang }),
      signal: state.controller.signal,
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.error || err.detail?.[0]?.msg || `HTTP ${resp.status}`);
    }
    // Читаем поток Server-Sent Events
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    for (;;) {
      const { value, done: end } = await reader.read();
      if (end) break;
      buf += decoder.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf("\n\n")) >= 0) {
        const line = buf.slice(0, i).trim(); buf = buf.slice(i + 2);
        if (!line.startsWith("data:")) continue;
        const ev = JSON.parse(line.slice(5));
        if (ev.type === "sources") {
          sources = ev.sources;
          const k = sources.filter((s) => s.is_constitution).length;
          finishStep(stepSearch, t("step_found", { n: sources.length, c: k ? t("step_found_c", { k }) : "" }));
          stepSearch = null;
          if (ev.search_query) finishStep(addStep(stepsEl, ""), t("step_rewrite", { q: ev.search_query }));
          stepWrite = addStep(stepsEl, t("step_write"));
          el.classList.remove("thinking");
        } else if (ev.type === "delta") {
          if (stepSearch) { finishStep(stepSearch, t("step_none")); stepSearch = null; }
          el.classList.remove("thinking");
          text += ev.text;
          if (!pending) { pending = true; requestAnimationFrame(paint); }
        } else if (ev.type === "replace") {
          text = ev.text;
          if (!ev.keep_sources) { sources = []; answerEl.classList.add("no-info"); }
          if (!pending) { pending = true; requestAnimationFrame(paint); }
        } else if (ev.type === "done") {
          done = ev;
        } else if (ev.type === "error") {
          throw new Error(ev.message);
        }
      }
    }
    finishStep(stepWrite);
    paint();
    if (done && !done.answered) { answerEl.classList.add("no-info"); sources = []; }
    stepsEl.classList.add("collapsed");
    if (done) {
      renderSources(extra, sources, done.cited);
      renderActions(extra, done, text, done.cited.length);
      state.history.push({ role: "user", content: question }, { role: "assistant", content: text });
    }
  } catch (err) {
    stepsEl.classList.add("collapsed");
    if (err.name === "AbortError") {
      if (text) paint();
      answerEl.insertAdjacentHTML("beforeend", `<p class="status-line">⏹ ${esc(t("stopped"))}</p>`);
    } else {
      const msg = err instanceof TypeError ? t("net_error") : err.message;
      answerEl.innerHTML = `<p class="error-box">⚠️ ${esc(msg)}</p>`;
    }
  } finally {
    el.classList.remove("thinking", "busy", "streaming");
    state.controller = null;
    setBusy(false);
    scrollDown();
    input.focus({ preventScroll: true });
  }
}

// ---------- Голос: ввод (Web Speech API) и озвучка ----------
const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const micBtn = $("#mic");
let rec = null;
if (!Recognition) micBtn.style.display = "none";
micBtn.addEventListener("click", () => {
  if (rec) { rec.stop(); return; }
  rec = new Recognition();
  rec.lang = state.lang === "kk" ? "kk-KZ" : "ru-RU";
  rec.interimResults = true;
  const base = input.value ? input.value + " " : "";
  rec.onresult = (e) => {
    input.value = base + Array.from(e.results).map((r) => r[0].transcript).join("");
    autoGrow();
  };
  rec.onend = () => { micBtn.classList.remove("rec"); rec = null; if (input.value.trim()) input.focus(); };
  rec.onerror = () => { micBtn.classList.remove("rec"); rec = null; };
  micBtn.classList.add("rec");
  rec.start();
});

function speak(text, btn) {
  if (!("speechSynthesis" in window)) return;
  if (speechSynthesis.speaking) { speechSynthesis.cancel(); btn.textContent = "🔊 " + t("listen"); return; }
  const plain = text.replace(/\[[\d,\s]+\]/g, "").replace(/[*_#>`|]/g, "").replace(/📜|ℹ️/g, "");
  const u = new SpeechSynthesisUtterance(plain);
  u.lang = state.lang === "kk" ? "kk-KZ" : "ru-RU";
  const voice = speechSynthesis.getVoices().find((v) => v.lang.startsWith(state.lang === "kk" ? "kk" : "ru"));
  if (voice) u.voice = voice;
  u.onend = () => { btn.textContent = "🔊 " + t("listen"); };
  btn.textContent = "⏹ " + t("stop_listen");
  speechSynthesis.speak(u);
}

// ---------- Справочник ценностей ----------
async function loadConcepts() {
  const box = $("#concepts");
  const items = await fetch("/api/concepts").then((r) => r.json());
  box.innerHTML = items.map((c, i) => {
    const L = c[state.lang];
    const st = c.constitution.status;
    return `
      <article class="concept" style="--i:${i}">
        <div class="concept-icon">${c.icon}</div>
        <h3>${esc(L.name)}</h3>
        <p>${esc(L.short)}</p>
        <div class="const-tag ${st}"><b>${esc(t("const_" + st))}</b>${esc(c.constitution[state.lang])}</div>
        <button class="ask-btn" data-q="${esc(L.question)}">${esc(t("ask_bot"))}</button>
      </article>`;
  }).join("");
  $$("button[data-q]", box).forEach((b) => b.addEventListener("click", () => ask(b.dataset.q)));
}

// ---------- Квиз ----------
const quiz = { questions: [], answers: {}, i: 0 };
const KEYS = { ru: ["А", "Б", "В", "Г"], kk: ["А", "Ә", "Б", "В"] };
function quizIntro() {
  $("#quiz").innerHTML = `
    <div class="quiz-intro">
      <span class="big shanyrak-slot">${shanyrakSVG(true)}</span>
      <p>${esc(t("quiz_intro"))}</p>
      <button class="btn" id="quiz-start">${esc(t("quiz_start"))}</button>
    </div>`;
  $("#quiz-start").addEventListener("click", quizStart);
}
async function quizStart() {
  quiz.questions = await fetch(`/api/quiz?lang=${state.lang}`).then((r) => r.json());
  quiz.answers = {}; quiz.i = 0;
  quizRender();
}
function quizRender() {
  const box = $("#quiz");
  const n = quiz.questions.length;
  if (quiz.i >= n) {
    box.innerHTML = `
      <div class="quiz-form">
        <span class="qring" style="--p:100%"><span>${n}/${n}</span></span>
        <p>${esc(t("quiz_nick"))}</p>
        <input id="nick" maxlength="24" autocomplete="nickname" aria-label="${esc(t("quiz_nick"))}">
        <button class="btn" id="quiz-submit">${esc(t("quiz_submit"))}</button>
      </div>`;
    $("#nick").value = safeGet("nick") || "";
    $("#quiz-submit").addEventListener("click", quizSubmit);
    return;
  }
  const q = quiz.questions[quiz.i];
  box.innerHTML = `
    <div class="quiz-top">
      <span class="qring" style="--p:${(quiz.i / n) * 100}%"><span>${quiz.i + 1}/${n}</span></span>
      <span class="status-line">${esc(t("quiz_q", { i: quiz.i + 1, n }))}</span>
    </div>
    <h3>${esc(q.question)}</h3>
    <div class="options">${q.options.map((o, k) => `<button class="option" style="--i:${k}" data-k="${k}"><span class="key">${KEYS[state.lang][k]}</span><span>${esc(o)}</span></button>`).join("")}</div>`;
  $$(".option", box).forEach((b) => b.addEventListener("click", async () => {
    if (quiz.answers[q.id] !== undefined) return;
    quiz.answers[q.id] = +b.dataset.k;
    b.classList.add("picked");
    await sleep(reduceMotion ? 0 : 260);
    quiz.i += 1;
    quizRender();
  }));
}
async function quizSubmit() {
  const nickname = $("#nick").value.trim();
  safeSet("nick", nickname);
  const res = await fetch(`/api/quiz/submit?lang=${state.lang}`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answers: quiz.answers, nickname }),
  }).then((r) => r.json());
  const byId = Object.fromEntries(quiz.questions.map((q) => [q.id, q]));
  const ratio = res.score / Math.max(1, res.total);
  const level = I18N[state.lang].quiz_level[Math.min(3, Math.floor(ratio * 4))];
  const leaders = await fetch("/api/quiz/leaderboard").then((r) => r.json()).catch(() => []);
  $("#quiz").innerHTML = `
    <div class="result">
      <span class="status-line">${esc(t("quiz_result"))}</span>
      <div class="score"><span id="score-n">0</span> / ${res.total}</div>
      <p><b>${esc(level)}</b></p>
      <button class="btn ghost" id="quiz-again">${esc(t("quiz_again"))}</button>
    </div>
    <div class="review">${res.results.map((r, i) => `
      <div class="review-item" style="--i:${i}">
        <b class="${r.correct ? "ok" : "bad"}">${r.correct ? "✓ " + esc(t("quiz_correct")) : "✗ " + esc(t("quiz_wrong"))}</b> — ${esc(byId[r.id].question)}<br>
        <b>${esc(byId[r.id].options[r.answer])}</b>. ${esc(r.explanation)}<br>
        <small>${esc(t("quiz_source"))}: ${esc(r.source)}</small>
      </div>`).join("")}</div>
    ${leaders.length ? `<div class="leaderboard"><b>${esc(t("quiz_leaders"))}</b><ol>${leaders.map((l) => `<li>${esc(l.nickname)} — ${l.score}/${l.total}</li>`).join("")}</ol></div>` : ""}`;
  $("#quiz-again").addEventListener("click", quizStart);
  // счётчик баллов и конфетти за хороший результат
  const sn = $("#score-n");
  for (let k = 0; k <= res.score; k++) { sn.textContent = k; if (!reduceMotion) await sleep(110); }
  if (ratio >= 0.7) confetti();
}

function confetti() {
  if (reduceMotion) return;
  const cv = $("#confetti"), ctx = cv.getContext("2d");
  const W = (cv.width = innerWidth * devicePixelRatio), H = (cv.height = innerHeight * devicePixelRatio);
  const colors = ["#00A3C4", "#2BC0DE", "#F5B800", "#FFD45C", "#FFFFFF"];
  const parts = Array.from({ length: 160 }, () => ({
    x: W / 2 + (Math.random() - 0.5) * W * 0.3, y: H * 0.35,
    vx: (Math.random() - 0.5) * 22 * devicePixelRatio, vy: (-Math.random() * 18 - 6) * devicePixelRatio,
    s: (4 + Math.random() * 6) * devicePixelRatio, r: Math.random() * Math.PI, vr: (Math.random() - 0.5) * 0.3,
    c: colors[(Math.random() * colors.length) | 0],
  }));
  const t0 = performance.now();
  (function frame(now) {
    ctx.clearRect(0, 0, W, H);
    for (const p of parts) {
      p.vy += 0.55 * devicePixelRatio; p.vx *= 0.99; p.x += p.vx; p.y += p.vy; p.r += p.vr;
      ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.r); ctx.fillStyle = p.c;
      ctx.fillRect(-p.s / 2, -p.s / 4, p.s, p.s / 2); ctx.restore();
    }
    if (now - t0 < 3200) requestAnimationFrame(frame); else ctx.clearRect(0, 0, W, H);
  })(t0);
}

// ---------- Источники: лента ----------
async function loadSources() {
  const docs = await fetch("/api/sources").then((r) => r.json());
  const L = I18N[state.lang];
  $("#source-list").innerHTML = docs.filter((d) => d.lang === state.lang).map((d, i) => `
    <a class="doc ${d.type === "constitution" ? "const" : ""}" style="--i:${i}" href="${esc(d.url)}" target="_blank" rel="noopener noreferrer">
      <span class="doc-type">${esc(L.types[d.type] || d.type)}</span>
      <span class="doc-title">${esc(d.title)}</span>
      <span class="doc-date">${esc(d.date.split(",")[0])}</span>
    </a>`).join("");
}

applyLang();
countUp();
input.focus({ preventScroll: true });

// Ссылка вида /?q=вопрос сразу задаёт вопрос (удобно для QR-кода и обмена)
const sharedQ = new URLSearchParams(location.search).get("q");
if (sharedQ) ask(sharedQ.slice(0, 1000));
