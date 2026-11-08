"use strict";
/* Hoops Hub: reads the JSON files the pipeline publishes under ./data and renders each section. */

const TABS = [
  ["live", "Live"], ["trending", "Trending"], ["news", "News"], ["injuries", "Injuries"],
  ["draft", "Draft"], ["rookies", "Rookies"], ["leaders", "Leaders"], ["teams", "Teams"], ["contracts", "Contracts"], ["cap", "Cap"],
];
const REFRESH_MS = 60 * 1000;
const view = document.getElementById("view");
const tabsEl = document.getElementById("tabs");
const stampEl = document.getElementById("stamp");
const bell = document.getElementById("bell");
const cache = {};
const ui = { tab: "live", newsWin: "live", trendWin: "1h", leaderMode: "perGame", leaderCat: "PTS", pos: "all",
  team: "", injTeam: "all", capSort: "payroll", q: "", cTeam: "all", cMore: 60 };

function store(k, v) {
  try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; }
}
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = (n) => (n == null || n === "" ? "n/a" : (n < 0 ? "-" : "") + "$" + (Math.abs(n) / 1e6).toFixed(1) + "M");
const rel = (iso) => {
  const t = Date.parse(iso); if (!t) return "";
  const m = Math.round((Date.now() - t) / 60000);
  if (m < 1) return "just now"; if (m < 60) return m + "m ago";
  if (m < 1440) return Math.round(m / 60) + "h ago"; return Math.round(m / 1440) + "d ago";
};
const empty = (title, body) => `<div class="empty"><b>${esc(title)}</b>${esc(body)}</div>`;

async function load(name, force) {
  if (cache[name] && !force) return cache[name];
  try {
    const r = await fetch(`data/${name}.json?t=${Math.floor(Date.now() / 30000)}`, { cache: "no-store" });
    if (!r.ok) throw new Error(r.status);
    cache[name] = await r.json();
  } catch (e) { cache[name] = cache[name] || null; }
  return cache[name];
}

/* ---------- Live ---------- */
function gameCard(g) {
  const live = g.state === "in", done = g.state === "post";
  const status = live ? `<span class="status live">${esc(g.detail)}</span>` : done ? `<span class="status">Final</span>`
    : `<span class="status">${esc(new Date(g.start).toLocaleString([], { weekday: "short", hour: "numeric", minute: "2-digit" }))}</span>`;
  const side = (t, win) => `<div class="line ${done && !win ? "lose" : ""}">
    <img src="${esc(t.logo)}" alt="" loading="lazy" onerror="this.style.visibility='hidden'">
    <span class="nm">${esc(t.name)} <span class="kv">${esc(t.record)}</span></span>
    <span class="sc">${g.state === "pre" ? "" : t.score}</span></div>`;
  const aw = g.away.score > g.home.score;
  const perf = (g.performers || []).map((p) =>
    `<div class="${p.tag}"><span class="tag ${p.tag === "hot" ? "up" : ""}">${p.tag === "hot" ? "Hot" : "Cold"}</span><b>${esc(p.name)}</b> ${esc(p.team)}, ${esc(p.line)}</div>`).join("");
  return `<article class="game ${g.followed.join(" ")}">
    <div class="meta"><span>${esc(g.league)}</span>${status}</div>
    ${side(g.away, aw)}${side(g.home, !aw)}
    ${perf ? `<div class="perf">${perf}</div>` : ""}</article>`;
}
async function renderLive() {
  const d = await load("scores");
  if (!d) return empty("No scores yet", "The first update has not run. Check back in a few minutes.");
  const fol = d.games.filter((g) => g.followed.length), nba = d.games.filter((g) => !g.followed.length);
  return `<h2 class="section-title">Kansas and Miami</h2>
    ${fol.length ? fol.map(gameCard).join("") : empty("No KU or Miami games today", "Games show up here the day they are played.")}
    <h2 class="section-title">NBA</h2>
    ${nba.length ? nba.map(gameCard).join("") : empty("No NBA games today", "Games show up here the day they are played.")}`;
}

/* ---------- Trending ---------- */
async function renderTrending() {
  const d = await load("trends");
  const seg = ["1h", "4h", "24h"].map((w) => `<button class="chip" data-act="trendWin" data-v="${w}" aria-pressed="${ui.trendWin === w}">Past ${w === "24h" ? "24 hours" : w === "4h" ? "4 hours" : "hour"}</button>`).join("");
  if (!d) return `<div class="sub">${seg}</div>` + empty("No trend data yet", "Trends build from headlines and Reddit posts as the feeds update.");
  const rows = d.windows[ui.trendWin] || [];
  const body = rows.length ? `<div class="list">${rows.map((r, i) => `<div class="row"><span class="rk">${i + 1}</span>
    <div class="main"><div class="t">${esc(r.name)}</div><div class="s">${esc(r.kind === "team" ? "Team" : "Player")}: ${r.news} news, ${r.reddit} Reddit${r.trends ? ", on Google Trends" : ""}</div></div>
    <div class="end">${r.score}</div></div>`).join("")}</div>` : empty("Nothing trending in this window", "Try a longer window.");
  return `<div class="sub">${seg}</div>${body}
    <p class="note">Score combines headline mentions, Reddit activity and Google Trends. X and TikTok have no free public feeds, so they are not counted.</p>`;
}

/* ---------- News ---------- */
async function renderNews() {
  const d = await load("news");
  const wins = [["live", "Live feed"], ["1", "Hottest hour"], ["4", "Hottest 4 hours"], ["24", "Hottest 24 hours"]];
  const seg = wins.map(([k, l]) => `<button class="chip" data-act="newsWin" data-v="${k}" aria-pressed="${ui.newsWin === k}">${l}</button>`).join("");
  if (!d) return `<div class="sub">${seg}</div>` + empty("No news yet", "The feed refreshes every few minutes.");
  let items = d.items.slice();
  if (ui.newsWin !== "live") {
    const cut = Date.now() - Number(ui.newsWin) * 3600e3;
    items = items.filter((i) => Date.parse(i.published) >= cut).sort((a, b) => b.hot - a.hot);
  }
  items = items.slice(0, 60);
  return `<div class="sub">${seg}</div>` + (items.length ? `<div class="list news">${items.map((i) => `
    <a class="row" href="${esc(i.url)}" target="_blank" rel="noopener"><span class="main"><span class="t">${esc(i.title)}</span>
    <span class="s">${esc(i.source)}, ${rel(i.published)}${i.outlets > 1 ? `, ${i.outlets} outlets` : ""}</span></span></a>`).join("")}</div>`
    : empty("No stories in this window", "Try a longer window."));
}

/* ---------- Injuries ---------- */
async function renderInjuries() {
  const d = await load("injuries");
  if (!d) return empty("No injury report yet", "The report refreshes every few minutes.");
  const opts = `<option value="all">All teams</option>` + d.teams.map((t) => `<option ${ui.injTeam === t.team ? "selected" : ""}>${esc(t.team)}</option>`).join("");
  const teams = d.teams.filter((t) => ui.injTeam === "all" || t.team === ui.injTeam);
  return `<div class="sub"><select class="chip" data-act="injTeam" aria-label="Team">${opts}</select></div>` +
    teams.map((t) => `<h2 class="section-title">${esc(t.team)}</h2><div class="tablewrap"><table>
    <tr><th>Player</th><th class="l">Reported injury</th><th>Status</th><th class="l">Expected return</th></tr>
    ${t.players.map((p) => `<tr><td>${esc(p.name)}</td><td class="l">${esc(p.injury)}</td><td>${esc(p.status)}</td>
    <td class="l">${esc(p.return || p.note || "No date reported")}</td></tr>`).join("")}</table></div>`).join("");
}

/* ---------- Draft ---------- */
async function renderDraft() {
  const d = await load("draft");
  if (!d) return empty("Draft board not built yet", "The board is rebuilt every Monday from big boards and mock drafts.");
  const mv = (m) => m == null ? `<span class="kv">new</span>` : m > 0 ? `<span class="up">+${m}</span>` : m < 0 ? `<span class="down">${m}</span>` : `<span class="kv">0</span>`;
  const rows = d.players.map((p) => {
    const pr = p.profile || {};
    const facts = [["Position", pr.pos], ["School or team", pr.school], ["Class", pr.class], ["Height", pr.height], ["Weight", pr.weight],
      ["Wingspan", pr.wingspan], ["From", pr.hometown]].filter((x) => x[1]).map((x) => `<span class="kv">${x[0]}: <b>${esc(x[1])}</b></span>`).join("");
    const srcs = Object.entries(p.ranks).map(([s, r]) => `${esc(s)} #${r}`).join(", ");
    const cb = pr.combine ? Object.entries({ "Height": pr.combine.height_bare, "Wingspan": pr.combine.wingspan, "Reach": pr.combine.reach, "Max vert": pr.combine.max_vert, "Lane": pr.combine.lane, "Sprint": pr.combine.sprint })
      .filter((x) => x[1]).map((x) => `<span class="kv">${x[0]}: <b>${esc(x[1])}</b></span>`).join(" ") : "";
    const intel = (p.intel || []).map((n) => `<a href="${esc(n.url)}" target="_blank" rel="noopener">${esc(n.title)}</a> <span class="kv">${esc(n.source)}</span>`).join("<br>");
    return `<details class="p"><summary><span class="rk" style="width:28px;text-align:right;font-weight:700">${p.rank}</span>
      <span style="flex:1;font-weight:600">${esc(p.name)} <span class="kv">${esc(pr.pos || "")} ${esc(pr.school || "")}</span></span>${mv(p.move)}</summary>
      <div class="pbody"><div>${facts || '<span class="kv">Profile not available yet</span>'}</div>
      <div class="kv">Previous rank: <b>${p.prev || "none"}</b>. Consensus average: <b>${p.avg}</b></div>
      ${cb ? `<div>Combine ${esc(pr.combine.year)}: ${cb}</div>` : ""}
      <div class="kv">Source ranks: ${srcs}</div>${intel ? `<div>${intel}</div>` : ""}</div></details>`;
  }).join("");
  return `<h2 class="section-title">${esc(d.label)} consensus top ${d.players.length}</h2>
    <div class="list">${rows}</div><p class="note">Sources: ${esc(d.sources.join(", "))}. Moves compare with last week's board.</p>`;
}

/* ---------- Rookies ---------- */
const statRow = (p, i) => `<tr><td>${i ? i + ". " : ""}${esc(p.name)} <span class="kv">${esc(p.team)}</span></td><td>${p.gp}</td><td>${p.min}</td>
  <td>${p.pts}</td><td>${p.reb}</td><td>${p.ast}</td><td>${p.stl}</td><td>${p.blk}</td><td>${p.fg}</td><td>${p.tp}</td></tr>`;
const statHead = `<tr><th>Player</th><th>GP</th><th>MIN</th><th>PTS</th><th>REB</th><th>AST</th><th>STL</th><th>BLK</th><th>FG%</th><th>3P%</th></tr>`;
async function renderRookies() {
  const d = await load("rookies");
  if (!d || !d.players.length) return empty("No rookie stats yet", "Rookie stats appear once the NBA stats feed has refreshed.");
  return `<h2 class="section-title">${esc(d.class_label)}: consensus top 15</h2>
    <div class="tablewrap"><table>${statHead}${d.top15.map((p) => statRow(p, p.rank)).join("")}</table></div>
    <h2 class="section-title">All rookies</h2>
    <div class="tablewrap"><table>${statHead}${d.players.map((p) => statRow(p)).join("")}</table></div>
    <p class="note">Top 15 ranks a per game impact index (points, rebounds, assists, steals, blocks, turnovers, shooting). Updated daily.</p>`;
}

/* ---------- Leaders ---------- */
const CAT_NAMES = { PTS: "Points", REB: "Rebounds", AST: "Assists", STL: "Steals", BLK: "Blocks", FG3M: "3-pointers made",
  FG_PCT: "FG%", FG3_PCT: "3P%", FT_PCT: "FT%", TOV: "Turnovers", MIN: "Minutes", FGM: "Field goals made", FTM: "Free throws made" };
async function renderLeaders() {
  const d = await load("leaders");
  const modes = [["perGame", "Per game"], ["totals", "Totals"], ["pos", "By position"], ["top150", "Top 150"]]
    .map(([k, l]) => `<button class="chip" data-act="leaderMode" data-v="${k}" aria-pressed="${ui.leaderMode === k}">${l}</button>`).join("");
  if (!d) return `<div class="sub">${modes}</div>` + empty("No leaderboards yet", "Leaderboards refresh hourly.");
  if (ui.leaderMode === "perGame" || ui.leaderMode === "totals") {
    const set = d[ui.leaderMode], cats = Object.keys(set);
    if (!set[ui.leaderCat]) ui.leaderCat = cats[0];
    const sel = `<select class="chip" data-act="leaderCat" aria-label="Category">${cats.map((c) => `<option value="${c}" ${c === ui.leaderCat ? "selected" : ""}>${CAT_NAMES[c] || c}</option>`).join("")}</select>`;
    return `<div class="sub">${modes}${sel}</div><div class="list">${set[ui.leaderCat].map((r, i) => `<div class="row"><span class="rk">${i + 1}</span>
      <div class="main"><div class="t">${esc(r.name)}</div><div class="s">${esc(r.team)}</div></div><div class="end">${r.val}</div></div>`).join("")}</div>`;
  }
  let list, title;
  if (ui.leaderMode === "pos") {
    if (ui.pos === "all") ui.pos = "G";
    const posBtns = [["G", "Guards"], ["F", "Forwards"], ["C", "Centers"]].map(([k, l]) => `<button class="chip" data-act="pos" data-v="${k}" aria-pressed="${ui.pos === k}">${l}</button>`).join("");
    list = d.byPosition[ui.pos] || []; title = `<div class="sub">${modes}${posBtns}</div>`;
  } else { list = d.top150; title = `<div class="sub">${modes}</div>`; }
  return title + `<div class="tablewrap"><table>${statHead}${list.map((p) => statRow(p, p.rank)).join("")}</table></div>
    <p class="note">Ranked daily by a per game impact index. Players need at least 40% of games played and 12 minutes a game.</p>`;
}

/* ---------- Teams ---------- */
const rk = (r) => `<span class="${r <= 8 ? "rank-good" : r >= 23 ? "rank-bad" : "kv"}">#${r}</span>`;
async function renderTeams() {
  const d = await load("teams");
  if (!d || !d.teams.length) return empty("No team data yet", "Team pages refresh hourly.");
  if (!ui.team) ui.team = d.teams[0].name;
  const t = d.teams.find((x) => x.name === ui.team) || d.teams[0];
  const sel = `<div class="sub"><select class="chip" data-act="team" aria-label="Team">${d.teams.map((x) => `<option ${x.name === t.name ? "selected" : ""}>${esc(x.name)}</option>`).join("")}</select></div>`;
  const stats = (obj, names) => Object.keys(obj || {}).length ? `<div class="tablewrap"><table><tr><th>Stat</th><th>Value</th><th>Rank</th></tr>
    ${Object.entries(obj).map(([k, v]) => `<tr><td>${names[k] || k}</td><td>${v.v}</td><td>${rk(v.r)}</td></tr>`).join("")}</table></div>` : empty("Not available", "Stats arrive with the next hourly refresh.");
  const N = { PTS: "Points", REB: "Rebounds", AST: "Assists", STL: "Steals", BLK: "Blocks", TOV: "Turnovers", FG_PCT: "FG%", FG3_PCT: "3P%", FT_PCT: "FT%",
    OPP_PTS: "Points allowed", OPP_REB: "Rebounds allowed", OPP_AST: "Assists allowed", OPP_FG_PCT: "Opponent FG%", OPP_FG3_PCT: "Opponent 3P%", OPP_TOV: "Opponent turnovers" };
  const pk = (arr) => arr.length ? arr.map((p) => `<div class="row"><div class="main"><div class="t">${p.year} round ${p.round}${p.from && p.from !== "own" ? ", from " + esc(p.from) : ""}</div>
    <div class="s">${esc(p.protection || p.reason || "")}</div></div></div>`).join("") : `<div class="row"><span class="kv">None listed</span></div>`;
  return sel + `<div class="game ${""}"><div class="meta"><span>${esc(t.conf)}${t.seed ? ", seed " + esc(t.seed) : ""}</span><span>Streak ${esc(t.streak || "n/a")}</span></div>
    <div class="line"><img src="${esc(t.logo)}" alt="" onerror="this.style.visibility='hidden'"><span class="nm">${esc(t.name)}</span><span class="sc">${esc(t.w)}-${esc(t.l)}</span></div>
    <div class="kv">Home ${esc(t.home || "n/a")}, away ${esc(t.away || "n/a")}, last 10 ${esc(t.l10 || "n/a")}, behind ${esc(t.gb || "n/a")}</div></div>
    <h2 class="section-title">Team stats</h2>${stats(t.stats, N)}
    <h2 class="section-title">What opponents do against them</h2>${stats(t.opp, N)}
    <h2 class="section-title">Players and salaries</h2><div class="tablewrap"><table><tr><th>Player</th><th>Pos</th><th>Ht</th><th>Wt</th><th>Salary</th><th>Thru</th><th>GP</th><th>MIN</th><th>PTS</th><th>REB</th><th>AST</th></tr>
    ${t.players.map((p) => `<tr><td>${esc(p.name)}</td><td>${esc(p.pos || "")}</td><td>${esc(p.ht || "")}</td><td>${p.wt || ""}</td><td>${money(p.salary)}</td><td>${esc(p.contract_end || "")}${p.option ? " (" + esc(p.option) + ")" : ""}</td><td>${p.gp}</td><td>${p.min}</td><td>${p.pts}</td><td>${p.reb}</td><td>${p.ast}</td></tr>`).join("")}</table></div>
    <h2 class="section-title">Draft picks they can trade</h2><div class="list">${pk(t.picks.tradable)}</div>
    <h2 class="section-title">Draft picks they cannot trade</h2><div class="list">${pk(t.picks.locked)}</div>`;
}

/* ---------- Contracts ---------- */
const STATUS_LABEL = { GUARANTEED: "Guaranteed", "NON-GUARANTEED": "Non-guaranteed", "TEAM OPTION": "Team option", "PLAYER OPTION": "Player option" };
function contractRows(d) {
  ui.cMore = Number(ui.cMore) || 60;
  const q = ui.q.trim().toLowerCase();
  let list = d.players.filter((p) => (ui.cTeam === "all" || p.team === ui.cTeam) && (!q || p.name.toLowerCase().includes(q)));
  list = list.sort((a, b) => (b.years[0] ? b.years[0].sal : 0) - (a.years[0] ? a.years[0].sal : 0));
  const total = list.length; list = list.slice(0, ui.cMore);
  const rows = list.map((p) => {
    const yrs = p.years.map((y) => `<tr><td>${esc(y.y)}</td><td>${money(y.sal)}</td><td>${y.ch && y.ch !== y.sal ? money(y.ch) : ""}</td><td>${esc(STATUS_LABEL[y.st] || y.st)}</td></tr>`).join("");
    const facts = [["Exception", p.exception], ["Signed", p.signed ? p.signed + (p.signed_by ? " by " + p.signed_by : "") : ""], ["Trade kicker", p.kicker],
      ["Likely bonus", p.likely], ["Unlikely bonus", p.unlikely], ["Notes", p.notes]].filter((x) => x[1]).map((x) => `<span class="kv">${x[0]}: <b>${esc(x[1])}</b></span>`).join("");
    return `<details class="p"><summary><span style="flex:1;font-weight:600">${esc(p.name)} <span class="kv">${esc(p.team)}</span></span>
      <span style="font-weight:700">${money(p.years[0] && p.years[0].sal)}</span><span class="kv">${esc(p.end ? "thru " + p.end : "")}${p.option ? ", " + esc(p.option) : ""}</span></summary>
      <div class="pbody" style="padding-left:14px"><div class="tablewrap"><table><tr><th>Season</th><th>Salary</th><th>Cap hold</th><th>Status</th></tr>${yrs}</table></div>
      <div class="kv">Total guaranteed: <b>${money(p.total)}</b></div>${facts ? `<div>${facts}</div>` : ""}</div></details>`;
  }).join("");
  return (rows ? `<div class="list">${rows}</div>` : empty("No contracts match", "Try a different name or team.")) +
    (total > list.length ? `<div class="sub" style="margin-top:12px"><button class="chip" data-act="cMore" data-v="${ui.cMore + 60}">Show more (${total - list.length} left)</button></div>` : "");
}
async function renderContracts() {
  const d = await load("contracts");
  if (!d) return empty("No contracts yet", "Contracts refresh hourly from HoopsMatic.");
  const teams = [...new Set(d.players.map((p) => p.team))].sort();
  const sel = `<select class="chip" data-act="cTeam" aria-label="Team"><option value="all">All teams</option>${teams.map((t) => `<option ${ui.cTeam === t ? "selected" : ""}>${esc(t)}</option>`).join("")}</select>`;
  return `<div class="sub"><input id="q" class="chip" type="search" placeholder="Search players" value="${esc(ui.q)}" aria-label="Search players" style="min-width:180px">${sel}</div>
    <div id="clist">${contractRows(d)}</div><p class="note">Contract data from HoopsMatic. Cap holds shown only when they differ from salary.</p>`;
}

/* ---------- Cap ---------- */
async function renderCap() {
  const d = await load("cap");
  if (!d) return empty("No cap data yet", "Cap sheets refresh hourly.");
  const th = d.thresholds || {};
  const cell = (v) => `<td class="${v != null && v < 0 ? "rank-bad" : ""}">${money(v)}</td>`;
  const e = (t) => t.exceptions || {};
  const mle = (t) => (e(t).mle_type ? esc(e(t).mle_type) + (e(t).mle_left != null ? ", " + money(e(t).mle_left) + " left" : "") : "None");
  const detail = (t) => {
    const used = (e(t).mle_used_on || []).map((u) => `${esc(u.player)} ${money(u.amount)}`).join(", ");
    const tp = (t.tpes || []).map((x) => `<div class="row"><div class="main"><div class="t">${money(x.value)} trade exception</div><div class="s">Expires ${esc(x.expires)}</div></div></div>`).join("");
    return `<details class="p"><summary><span style="flex:1;font-weight:600">${esc(t.team)}</span><span class="kv">${esc(t.status || "")}</span><span class="kv">${(t.tpes || []).length} TPE</span></summary>
      <div class="pbody" style="padding-left:14px"><div class="kv">Mid-level: <b>${mle(t)}</b>${used ? ", used on " + used : ""}</div>
      <div class="kv">Bi-annual exception: <b>${e(t).bae != null ? money(e(t).bae) : "n/a"}</b></div>
      ${tp ? `<div class="list">${tp}</div>` : `<div class="kv">No trade exceptions</div>`}</div></details>`;
  };
  return `<div class="list"><div class="row"><div class="main"><div class="t">${esc(th.season || "")} lines</div>
    <div class="s">Cap ${money(th.salary_cap)}, tax ${money(th.luxury_tax)}, first apron ${money(th.first_apron)}, second apron ${money(th.second_apron)}</div></div></div></div>
    <h2 class="section-title">Space and room, by team</h2><div class="tablewrap"><table>
    <tr><th>Team</th><th>Payroll</th><th>Cap space</th><th>Under tax by</th><th>Under 1st apron by</th><th>Under 2nd apron by</th><th class="l">Mid-level</th><th>BAE</th></tr>
    ${d.teams.map((t) => `<tr><td>${esc(t.team)}</td><td>${money(t.payroll)}</td>${cell(t.cap_space)}${cell(t.tax_room)}${cell(t.first_apron_room)}${cell(t.second_apron_room)}
    <td class="l">${mle(t)}</td><td>${e(t).bae != null ? money(e(t).bae) : "n/a"}</td></tr>`).join("")}</table></div>
    <h2 class="section-title">Exceptions and trade exceptions</h2><div class="list">${d.teams.map(detail).join("")}</div>
    <p class="note">Negative numbers mean the team is over that line. Source: ${esc(d.source || "")}.</p>`;
}

/* ---------- Shell ---------- */
const RENDER = { live: renderLive, trending: renderTrending, news: renderNews, injuries: renderInjuries, draft: renderDraft,
  rookies: renderRookies, leaders: renderLeaders, teams: renderTeams, contracts: renderContracts, cap: renderCap };

function drawTabs() {
  tabsEl.innerHTML = TABS.map(([k, l]) => `<button class="tab" role="tab" data-tab="${k}" aria-selected="${ui.tab === k}">${l}</button>`).join("");
}
async function draw(keepScroll) {
  const y = window.scrollY;
  view.innerHTML = await RENDER[ui.tab]();
  if (keepScroll) window.scrollTo(0, y);
  const stamps = Object.values(cache).filter(Boolean).map((v) => Date.parse(v.updated)).filter(Boolean);
  stampEl.textContent = stamps.length ? "Updated " + rel(new Date(Math.max(...stamps)).toISOString()) : "Waiting for first update";
}
async function refresh() {
  const names = { live: ["scores"], trending: ["trends"], news: ["news"], injuries: ["injuries"], draft: ["draft"], rookies: ["rookies"], leaders: ["leaders"], teams: ["teams"], contracts: ["contracts"], cap: ["cap"] }[ui.tab];
  const before = JSON.stringify(cache.scores && cache.scores.games.map((g) => [g.id, g.state, g.home.score, g.away.score]));
  await Promise.all(names.map((n) => load(n, true)));
  if (ui.tab !== "live") await load("scores", true);
  localNotify(before);
  draw(true);
}

/* ---------- Alerts while the app is open ---------- */
function toast(msg) {
  const t = document.getElementById("toast"); t.textContent = msg; t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 3500);
}
function bellState() {
  const on = store("alerts") === "on" && "Notification" in window && Notification.permission === "granted";
  bell.dataset.on = String(on); bell.textContent = on ? "Alerts on" : "Alerts off";
}
async function toggleAlerts() {
  if (!("Notification" in window)) { toast("This browser does not support alerts. On iPhone, add the app to your Home Screen first."); return; }
  if (store("alerts") === "on") { store("alerts", "off"); bellState(); toast("Alerts off"); return; }
  const p = Notification.permission === "granted" ? "granted" : await Notification.requestPermission();
  if (p === "granted") { store("alerts", "on"); toast("Alerts on while the app is open"); } else toast("Alerts are blocked in your browser settings");
  bellState();
}
let lastGames = null;
async function localNotify(beforeJson) {
  const d = cache.scores; if (!d) return;
  const snap = {}; d.games.forEach((g) => (snap[g.id] = g));
  if (lastGames && store("alerts") === "on" && Notification.permission === "granted") {
    for (const g of d.games) {
      const o = lastGames[g.id]; if (!o) continue;
      const label = `${g.away.abbr} ${g.away.score}, ${g.home.abbr} ${g.home.score}`;
      let title = null;
      if (o.state === "pre" && g.state === "in") title = `Starting: ${g.away.abbr} at ${g.home.abbr}`;
      if (o.state !== "post" && g.state === "post") title = `Final: ${label}`;
      if (title) {
        const reg = await navigator.serviceWorker.getRegistration();
        if (reg) reg.showNotification(title, { body: g.league, icon: "icon-192.png", tag: g.id });
      }
    }
  }
  lastGames = snap;
}

document.addEventListener("click", (e) => {
  const tab = e.target.closest("[data-tab]");
  if (tab) { ui.tab = tab.dataset.tab; store("tab", ui.tab); drawTabs(); draw(); window.scrollTo(0, 0); return; }
  const a = e.target.closest("[data-act]");
  if (a && a.tagName !== "SELECT") { ui[a.dataset.act] = a.dataset.v; draw(true); }
});
document.addEventListener("change", (e) => {
  const a = e.target.closest("select[data-act]"); if (a) { ui[a.dataset.act] = a.value; draw(true); }
});
document.addEventListener("input", (e) => {
  if (e.target.id !== "q") return;
  ui.q = e.target.value; ui.cMore = 60;
  const box = document.getElementById("clist"); if (box && cache.contracts) box.innerHTML = contractRows(cache.contracts);
});
bell.addEventListener("click", toggleAlerts);

(async function init() {
  const saved = location.hash.slice(1) || store("tab"); if (saved && RENDER[saved]) ui.tab = saved;
  drawTabs(); bellState();
  await load("scores"); await draw();
  await localNotify();
  setInterval(refresh, REFRESH_MS);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); });
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
})();
