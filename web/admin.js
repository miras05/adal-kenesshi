"use strict";
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (n) => (n ?? 0).toLocaleString("ru-RU");

function getToken() { try { return sessionStorage.getItem("admin_token") || ""; } catch { return ""; } }
function setToken(v) { try { sessionStorage.setItem("admin_token", v); } catch { /* ignore */ } }

async function load(token) {
  const r = await fetch("/api/stats", { headers: { "X-Admin-Token": token } });
  if (r.status === 401) throw new Error("Неверный токен");
  if (!r.ok) throw new Error(`Ошибка ${r.status}`);
  return r.json();
}

function render(s) {
  const kpis = [
    ["Всего запросов", fmt(s.total_queries)],
    ["За 24 часа", fmt(s.queries_24h)],
    ["Уникальных пользователей", fmt(s.unique_users)],
    ["Найден ответ", `${s.answered_rate ?? 0}%`],
    ["Среднее время ответа", `${((s.avg_latency_ms || 0) / 1000).toFixed(1)} с`],
    ["👍 / 👎", `${fmt(s.likes)} / ${fmt(s.dislikes)}`],
    ["Игр в квиз", fmt(s.quiz_games)],
    ["Токены (вход/выход)", `${fmt(s.tokens_in)} / ${fmt(s.tokens_out)}`],
    ["Ошибок", fmt(s.errors)],
  ];
  $("#kpis").innerHTML = kpis.map(([l, v]) => `<div class="kpi"><div class="v">${esc(v)}</div><div class="l">${esc(l)}</div></div>`).join("");

  const days = [...s.by_day].reverse();
  const max = Math.max(1, ...days.map((d) => d.n));
  $("#by-day").innerHTML = days.length ? days.map((d) => `
    <div class="bar" title="${esc(d.day)}: ${d.n} запросов, с ответом ${d.answered}">
      <b>${d.n}</b>
      <div class="col" style="height:${(d.n / max) * 100}%"><div class="ans" style="height:${(d.answered / d.n) * 100}%"></div></div>
      <small>${esc(d.day.slice(5))}</small>
    </div>`).join("") : "<p>Пока нет данных</p>";

  const rows = (arr, key) => {
    const total = arr.reduce((a, x) => a + x.n, 0) || 1;
    return arr.map((x) => `<div class="row"><span style="min-width:70px">${esc(x[key] || "—")}</span>
      <div class="track"><div class="fill" style="width:${(x.n / total) * 100}%"></div></div><b>${x.n}</b></div>`).join("") || "<p>—</p>";
  };
  $("#by-lang").innerHTML = rows(s.by_lang.map((x) => ({ ...x, lang: x.lang === "kk" ? "қазақша" : "русский" })), "lang");
  $("#by-channel").innerHTML = rows(s.by_channel, "channel");
  $("#top").innerHTML = s.top_questions.map((q) => `<li>${esc(q.question)} <b>×${q.n}</b></li>`).join("") || "<li>—</li>";
  $("#unanswered").innerHTML = s.unanswered.map((q) => `<li>${esc(q.question)} <small>(${esc(q.at)})</small></li>`).join("") || "<li>Все вопросы получили ответ 🎉</li>";
}

async function start(token) {
  try {
    render(await load(token));
    setToken(token);
    $("#login").hidden = true;
    $("#dash").hidden = false;
    setTimeout(() => start(token), 15000); // автообновление
  } catch (e) {
    $("#login").hidden = false;
    $("#dash").hidden = true;
    $("#login-err").textContent = e.message;
  }
}

$("#login").addEventListener("submit", (e) => { e.preventDefault(); start($("#token").value.trim()); });
if (getToken()) start(getToken());
