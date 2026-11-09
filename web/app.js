"use strict";
/* Hoops Hub: reads the JSON files the pipeline publishes under ./data and renders each section.
   Saved copies paint instantly on launch, then fresh data replaces them. */

const TABS = [
  ["live", "Live"], ["standings", "Standings"], ["trending", "Trending"], ["news", "News"], ["injuries", "Injuries"],
  ["draft", "Draft"], ["rookies", "Rookies"], ["leaders", "Leaders"], ["teams", "Teams"], ["contracts", "Contracts"], ["cap", "Cap"],
];
const DATA_FOR = {
  live: ["scores"], standings: ["standings"], trending: ["trends"], news: ["news"], injuries: ["injuries"], draft: ["draft"],
  rookies: ["rookies"], leaders: ["leaders"], teams: ["teams"], contracts: ["contracts"], cap: ["cap"],
};
const ALL_DATA = [...new Set(Object.values(DATA_FOR).flat())];
const REFRESH_MS = 60 * 1000;
const view = document.getElementById("view");
const tabsEl = document.getElementById("tabs");
const stampEl = document.getElementById("stamp");
const bell = document.getElementById("bell");
const tickerEl = document.getElementById("ticker");
const cache = {};
const failed = {};
const fresh = new Set();
const ui = {
  tab: "live", newsWin: "live", newsSrc: "all", newsMore: 60, trendWin: "1h", leaderMode: "perGame", leaderCat: "PTS", pos: "G",
  team: "", injTeam: "all", q: "", cTeam: "all", cExt: "all", cTrade: "all", cMore: 60, stView: "conf", dq: "", dMore: 50,
};

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
const skeleton = () => `<div class="skel" aria-busy="true" aria-label="Loading"><i></i><i></i><i></i><i></i><i></i><i></i></div>`;
const logo = (u, big) => (u ? `<img ${big ? "" : 'class="lg" '}src="${esc(u)}" alt="" loading="lazy" onerror="this.style.visibility='hidden'">` : "");
const tlogo = (t) => logo(t.logo || logoUrl(t.name, "nba") || logoUrl(t.name, "college"));
/* Team logos by name, abbreviation or school. Built-in table first, the pipeline's fuller table layered on top. */
const LOGOS = { nba: {}, college: {} };
const nick = (n) => (/Trail Blazers$/.test(n || "") ? "Trail Blazers" : String(n || "").split(" ").pop());
const lkey = (s) => String(s == null ? "" : s).toLowerCase().replace(/[^a-z0-9]/g, "");
function initials(name) {
  const w = String(name || "?").replace(/[()]/g, "").split(/\s+/).filter(Boolean);
  return (w.length > 1 ? w[0][0] + w[1][0] : (w[0] || "?").slice(0, 2)).toUpperCase();
}
function logoUrl(name, kind) {
  const k = lkey(name), t = LOGOS[kind] || {};
  if (t[k]) return t[k];
  const bare = lkey(String(name).replace(/\(.*?\)/g, ""));
  if (t[bare]) return t[bare];
  if (kind === "college") { const sw = lkey(String(name).replace(/^university of /i, "").replace(/ university$/i, "")); if (t[sw]) return t[sw]; }
  if (kind === "nba") { const nick = lkey(String(name).split(" ").pop()); if (t[nick]) return t[nick]; }
  return "";
}
/* One team chip: logo (or initials when there is none) followed by the name. kind is "nba" or "college". */
function tm(name, kind, label) {
  if (!name) return "";
  const u = logoUrl(name, kind || "nba");
  const icon = u ? `<img class="lg" src="${esc(u)}" alt="" loading="lazy" onerror="this.outerHTML='<span class=&quot;lg&quot;>${esc(initials(name))}</span>'">` : `<span class="lg">${esc(initials(name))}</span>`;
  return `<span class="tc">${icon}${esc(label == null ? name : label)}</span>`;
}
async function loadLogos() {
  for (const path of ["seed/logos.json", "data/logos.json"]) {
    try {
      const d = await fetchJson(path);
      Object.assign(LOGOS.nba, d.nba || {}); Object.assign(LOGOS.college, d.college || {});
    } catch (e) { /* the other table still works */ }
  }
}
const title = (t, sub) => `<h2 class="bar-title">${esc(t)}${sub ? `<span class="sub">${esc(sub)}</span>` : ""}</h2>`;

/* ---------- Data loading: saved copy first, network second ---------- */
function saved(name) {
  const raw = store("hh:" + name);
  if (!raw) return null;
  try { return JSON.parse(raw); } catch (e) { return null; }
}
async function fetchJson(path) {
  const r = await fetch(`${path}?t=${Math.floor(Date.now() / 30000)}`, { cache: "no-store" });
  if (!r.ok) throw new Error(r.status);
  return r.json();
}
async function load(name, force) {
  if (cache[name] && !force) return cache[name];
  try {
    let d;
    try { d = await fetchJson(`data/${name}.json`); } catch (e) { if (name === "draft") d = await fetchJson("seed/draft.json"); else throw e; }
    cache[name] = d; failed[name] = false; fresh.add(name);
    try { const s = JSON.stringify(d); if (s.length < 700000) store("hh:" + name, s); } catch (e) { /* storage full */ }
  } catch (e) {
    failed[name] = true;
    if (!cache[name]) cache[name] = saved(name);
  }
  return cache[name];
}
function primeFromSaved() {
  ALL_DATA.forEach((n) => { const s = saved(n); if (s) cache[n] = s; });
}

/* ---------- Live ---------- */
function gameCard(g) {
  const live = g.state === "in", done = g.state === "post";
  const status = live ? `<span class="live">${esc(g.detail)}</span>` : done ? `<span>Final</span>`
    : `<span>${esc(new Date(g.start).toLocaleString([], { weekday: "short", hour: "numeric", minute: "2-digit" }))}</span>`;
  const side = (t, win) => `<div class="tm ${done && !win ? "lose" : ""}">${tlogo(t)}
    <span class="nm">${esc(t.name)} <span class="kv">${esc(t.record)}</span></span><span class="sc">${g.state === "pre" ? "" : t.score}</span></div>`;
  const aw = Number(g.away.score) > Number(g.home.score);
  const perf = (g.performers || []).map((p) =>
    `<div><span class="tag ${p.tag}">${p.tag === "hot" ? "Hot" : "Cold"}</span><span><b>${esc(p.name)}</b> ${esc(p.team)}, ${esc(p.line)}</span></div>`).join("");
  const cls = g.followed.includes("ku") ? "ku" : g.followed.includes("um") ? "um" : "";
  return `<article class="game ${cls}"><div class="head"><span>${esc(g.league)}</span>${status}</div>
    ${side(g.away, aw)}${side(g.home, !aw)}${perf ? `<div class="perf">${perf}</div>` : ""}</article>`;
}
async function renderLive() {
  const d = cache.scores;
  if (!d) return failed.scores ? empty("Scores are not available yet", "The first update has not finished. This page checks again every minute.") : skeleton();
  const fol = d.games.filter((g) => g.followed.length), nba = d.games.filter((g) => !g.followed.length);
  return `${title("Kansas and Miami")}
    ${fol.length ? `<div class="games">${fol.map(gameCard).join("")}</div>` : empty("No Kansas or Miami games today", "Games show up here the day they are played.")}
    ${title("NBA", nba.length ? nba.length + " games" : "")}
    ${nba.length ? `<div class="games">${nba.map(gameCard).join("")}</div>` : empty("No NBA games today", "Games show up here the day they are played.")}`;
}
function drawTicker() {
  const d = cache.scores;
  const games = d ? d.games.filter((g) => g.state !== "pre") : [];
  if (!games.length) { tickerEl.hidden = true; return; }
  const item = (g) => `<span class="tk"><b>${esc(g.away.abbr)} ${g.away.score}</b><b>${esc(g.home.abbr)} ${g.home.score}</b>
    <span class="st ${g.state === "in" ? "live" : ""}">${g.state === "in" ? esc(g.detail) : "Final"}</span></span>`;
  const one = games.map(item).join("");
  const anyLive = games.some((g) => g.state === "in");
  const run = anyLive || games.length > 3;
  tickerEl.hidden = false;
  tickerEl.classList.toggle("run", run);
  tickerEl.style.setProperty("--tick-s", Math.max(30, games.length * 6) + "s");
  tickerEl.innerHTML = `<div class="ticker-track">${run ? one + one : one}</div>`;
}

/* ---------- Standings, streaks and last 10 ---------- */
const stSeg = () => [["conf", "Conference"], ["streaks", "Streaks"], ["last10", "Last 10"]]
  .map(([k, l]) => `<button class="btn" data-act="stView" data-v="${k}" aria-pressed="${ui.stView === k}">${l}</button>`).join("");
const streakCell = (s) => (s ? `<span class="${String(s).startsWith("W") ? "good" : "bad"}">${esc(s)}</span>` : "");
const seedOf = (t) => (String(t.seed).match(/^\d+$/) ? Number(t.seed) : 99);
function confTable(conf, teams) {
  const rows = teams.map((t, i) => {
    const s = seedOf(t) === 99 ? i + 1 : seedOf(t);
    return `<tr class="${s === 6 ? "cut" : s === 10 ? "cut2" : ""}"><td class="team">${s}. ${tlogo(t)}${esc(t.name)}</td><td>${esc(t.w)}</td><td>${esc(t.l)}</td><td>${esc(t.pct)}</td>
      <td>${esc(t.gb)}</td><td>${streakCell(t.streak)}</td><td>${esc(t.l10)}</td><td>${esc(t.home)}</td><td>${esc(t.away)}</td><td>${esc(t.diff)}</td></tr>`;
  }).join("");
  return `${title(conf + "ern Conference")}<div class="tbl"><table class="sticky1"><thead><tr><th class="l">Team</th><th>W</th><th>L</th><th>PCT</th><th>GB</th><th>Strk</th><th>L10</th><th>Home</th><th>Away</th><th>Diff</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}
function streakList(list, kind) {
  if (!list.length) return empty(kind === "w" ? "No active win streaks" : "No active losing streaks", "Streaks show once teams have played.");
  return `<div class="list">${list.map((t) => `<div class="row"><span class="badge ${kind}">${esc(t.streak)}</span>
    <div class="main"><div class="t">${tlogo(t)}${esc(t.name)}</div><div class="s">${esc(t.conf)}, ${esc(t.w)}-${esc(t.l)}, last 10 ${esc(t.l10 || "n/a")}</div></div></div>`).join("")}</div>`;
}
async function renderStandings() {
  const d = cache.standings, seg = `<div class="chips">${stSeg()}</div>`;
  if (!d || !d.teams.length) return seg + (failed.standings ? empty("Standings are not available yet", "ESPN did not answer. This page checks again every minute.") : skeleton());
  const teams = d.teams;
  if (ui.stView === "streaks") {
    const wins = teams.filter((t) => t.streakN > 0).sort((a, b) => b.streakN - a.streakN).slice(0, 12);
    const loss = teams.filter((t) => t.streakN < 0).sort((a, b) => a.streakN - b.streakN).slice(0, 12);
    return `${seg}<div class="cols two"><div>${title("Win streaks")}${streakList(wins, "w")}</div><div>${title("Losing streaks")}${streakList(loss, "l")}</div></div>
      <p class="note">Active streaks only. Updated every few minutes during games.</p>`;
  }
  if (ui.stView === "last10") {
    const rows = teams.filter((t) => t.l10w != null).sort((a, b) => b.l10w - a.l10w || b.streakN - a.streakN).map((t, i) => {
      const w = t.l10w, bar = Array.from({ length: 10 }, (_, k) => `<i class="${k < w ? "w" : ""}"></i>`).join("");
      return `<tr><td class="num">${i + 1}</td><td class="team">${tlogo(t)}${esc(t.name)}</td><td>${esc(t.conf)}</td><td><b>${esc(t.l10)}</b></td>
        <td class="l"><span class="l10" aria-hidden="true">${bar}</span></td><td>${streakCell(t.streak)}</td><td>${esc(t.w)}-${esc(t.l)}</td></tr>`;
    }).join("");
    return seg + (rows ? `${title("Best to worst over the last 10 games")}<div class="tbl"><table><thead><tr><th>#</th><th class="l">Team</th><th>Conf</th><th>L10</th><th class="l">Wins in 10</th><th>Strk</th><th>Season</th></tr></thead><tbody>${rows}</tbody></table></div>`
      : empty("Last 10 is not available yet", "Standings did not include recent form."));
  }
  const east = teams.filter((t) => t.conf.startsWith("East")), west = teams.filter((t) => t.conf.startsWith("West"));
  return `${seg}${east.length ? confTable("East", east) : ""}${west.length ? confTable("West", west) : ""}
    <p class="note">The solid line marks the top 6 who clinch a playoff spot. The dashed line marks the play-in, seeds 7 to 10.</p>`;
}

/* ---------- Trending ---------- */
async function renderTrending() {
  const d = cache.trends;
  const seg = ["1h", "4h", "24h"].map((w) => `<button class="btn" data-act="trendWin" data-v="${w}" aria-pressed="${ui.trendWin === w}">Past ${w === "24h" ? "24 hours" : w === "4h" ? "4 hours" : "hour"}</button>`).join("");
  if (!d) return `<div class="chips">${seg}</div>` + (failed.trends ? empty("No trend data yet", "Trends build from headlines as the feeds update.") : skeleton());
  const rows = d.windows[ui.trendWin] || [];
  const body = rows.length ? `<div class="list">${rows.map((r, i) => {
    const bits = [r.news ? `${r.news} news` : "", r.reddit ? `${r.reddit} Reddit` : "", r.game ? (r.game === "hot" ? "hot in a game" : "cold in a game") : "", r.trends ? "on Google Trends" : ""].filter(Boolean).join(", ");
    return `<div class="row"><span class="rk">${i + 1}</span>
    <div class="main"><div class="t">${esc(r.name)} ${r.earlier ? '<span class="tag later">Earlier</span>' : ""}</div><div class="s">${r.kind === "team" ? "Team" : "Player"}${bits ? ", " + esc(bits) : ", mentioned earlier in the day"}</div></div>
    <div class="end">${r.score}</div></div>`;
  }).join("")}</div>` : empty("Nothing trending yet", "Names show up as soon as headlines mention them.");
  return `<div class="chips">${seg}</div>${body}
    <p class="note">Score combines headline mentions, Reddit activity, Google Trends and standout box scores. Names marked Earlier had no mentions in this window and come from the next longer one. X and TikTok have no free public feeds, so they are not counted.</p>`;
}

/* ---------- News ---------- */
const newsRow = (i) => `<a class="row" href="${esc(i.url)}" target="_blank" rel="noopener"><span class="main"><span class="t">${esc(i.title)}</span>
  ${i.summary ? `<span class="sum">${esc(i.summary)}</span>` : ""}
  <span class="s">${esc(i.source)}, ${rel(i.published)}${i.outlets > 1 ? `, ${i.outlets} outlets` : ""}</span></span></a>`;
async function renderNews() {
  const d = cache.news;
  const wins = [["live", "Live feed"], ["1", "Hottest hour"], ["4", "Hottest 4 hours"], ["24", "Hottest 24 hours"]];
  const seg = wins.map(([k, l]) => `<button class="btn" data-act="newsWin" data-v="${k}" aria-pressed="${ui.newsWin === k}">${l}</button>`).join("");
  if (!d) return `<div class="chips">${seg}</div>` + (failed.news ? empty("No news yet", "The feed refreshes every few minutes.") : skeleton());
  const sources = [...new Set(d.items.map((i) => i.source))].sort((a, b) => a.localeCompare(b));
  const sel = `<select class="btn" data-act="newsSrc" aria-label="Source"><option value="all">All sources</option>${sources.map((s) => `<option ${ui.newsSrc === s ? "selected" : ""}>${esc(s)}</option>`).join("")}</select>`;
  let items = d.items.filter((i) => ui.newsSrc === "all" || i.source === ui.newsSrc);
  let body;
  if (ui.newsWin === "live") {
    const total = items.length; ui.newsMore = Number(ui.newsMore) || 60;
    body = items.length ? `<div class="list news">${items.slice(0, ui.newsMore).map(newsRow).join("")}</div>` +
      (total > ui.newsMore ? `<div class="chips" style="margin-top:16px"><button class="btn" data-act="newsMore" data-v="${ui.newsMore + 60}">Show more (${total - ui.newsMore} left)</button></div>` : "")
      : empty("No stories yet", "Stories appear as the feeds update.");
  } else {
    const cut = Date.now() - Number(ui.newsWin) * 3600e3;
    const hot = items.filter((i) => Date.parse(i.published) >= cut).sort((a, b) => b.hot - a.hot).slice(0, 40);
    const ids = new Set(hot.map((i) => i.id));
    // A quiet hour still shows the hottest recent stories, marked as earlier.
    const fill = hot.length < 8 ? items.filter((i) => !ids.has(i.id)).sort((a, b) => b.hot - a.hot).slice(0, 12 - hot.length) : [];
    body = (hot.length ? `<div class="list news">${hot.map(newsRow).join("")}</div>` : "") +
      (fill.length ? `${title("Hottest from earlier")}<div class="list news">${fill.map(newsRow).join("")}</div>` : "") +
      (!hot.length && !fill.length ? empty("No stories in this window", "Try a longer window.") : "");
  }
  return `<div class="chips">${seg}${sel}</div>${body}`;
}

/* ---------- Injuries ---------- */
async function renderInjuries() {
  const d = cache.injuries;
  if (!d) return failed.injuries ? empty("No injury report yet", "The report refreshes every few minutes.") : skeleton();
  const opts = `<option value="all">All teams</option>` + d.teams.map((t) => `<option ${ui.injTeam === t.team ? "selected" : ""}>${esc(t.team)}</option>`).join("");
  const teams = d.teams.filter((t) => ui.injTeam === "all" || t.team === ui.injTeam);
  return `<div class="chips"><select class="btn" data-act="injTeam" aria-label="Team">${opts}</select></div>` +
    (teams.length ? teams.map((t) => `<h2 class="bar-title">${tm(t.team, "nba")}<span class="sub">${t.players.length + (t.players.length === 1 ? " player" : " players")}</span></h2><div class="tbl"><table>
    <thead><tr><th class="l">Player</th><th class="l">Reported injury</th><th class="l">Status</th><th class="l">Expected return</th></tr></thead><tbody>
    ${t.players.map((p) => `<tr><td class="l"><b>${esc(p.name)}</b> <span class="kv">${tm(t.team, "nba", nick(t.team))}</span></td><td class="l">${esc(p.injury)}</td><td class="l">${esc(p.status)}</td>
    <td class="l">${esc(p.return || p.note || "No date reported")}</td></tr>`).join("")}</tbody></table></div>`).join("") : empty("No injuries reported", "Nobody is listed for this team."));
}

/* ---------- Draft ---------- */
function draftRows(d) {
  const q = ui.dq.trim().toLowerCase();
  let list = d.players.filter((p) => !q || p.name.toLowerCase().includes(q) || String((p.profile || {}).school || "").toLowerCase().includes(q));
  const total = list.length; ui.dMore = Number(ui.dMore) || 50; list = list.slice(0, q ? 150 : ui.dMore);
  const mv = (m) => m == null ? `<span class="kv">new</span>` : m > 0 ? `<span class="up">+${m}</span>` : m < 0 ? `<span class="down">${m}</span>` : `<span class="kv">0</span>`;
  const rows = list.map((p) => {
    const pr = p.profile || {};
    const facts = [["Position", pr.pos], ["School or team", pr.school], ["Class", pr.class], ["Height", pr.height], ["Weight", pr.weight],
      ["Wingspan", pr.wingspan], ["From", pr.hometown]].filter((x) => x[1]).map((x) => `<span class="kv">${x[0]}: <b>${esc(x[1])}</b></span>`).join("");
    const st = pr.stats ? `<div class="stats">This season: ${pr.stats.pts} pts, ${pr.stats.reb} reb, ${pr.stats.ast} ast, ${pr.stats.fg}% FG, ${pr.stats.tp}% 3P in ${pr.stats.gp} games</div>` : "";
    const srcs = Object.entries(p.ranks).map(([s, r]) => `${esc(s)} #${r}`).join(", ");
    const cb = pr.combine ? Object.entries({ "Height": pr.combine.height_bare, "Wingspan": pr.combine.wingspan, "Reach": pr.combine.reach, "Max vert": pr.combine.max_vert, "Lane": pr.combine.lane, "Sprint": pr.combine.sprint })
      .filter((x) => x[1]).map((x) => `<span class="kv">${x[0]}: <b>${esc(x[1])}</b></span>`).join(" ") : "";
    const intel = (p.intel || []).map((n) => `<a href="${esc(n.url)}" target="_blank" rel="noopener">${esc(n.title)} <span class="kv">${esc(n.source)}</span></a>`).join("");
    return `<details class="p"><summary><span class="rk" style="width:32px;text-align:right;font-weight:700">${p.rank}</span>
      <span style="flex:1;min-width:0"><b>${esc(p.name)}</b> <span class="kv">${esc(pr.pos || "")}</span> ${pr.school ? `<span class="kv">${tm(pr.school, "college")}</span>` : ""}</span>${mv(p.move)}</summary>
      <div class="pbody">${pr.note ? `<div class="word">${esc(pr.note)}</div>` : ""}${st}<div class="facts">${facts || '<span class="kv">Profile not available yet</span>'}</div>
      <div class="kv">Previous rank: <b>${p.prev || "none"}</b>. Consensus average: <b>${p.avg}</b></div>
      ${cb ? `<div>Combine ${esc(pr.combine.year)}: ${cb}</div>` : ""}
      <div class="kv">Source ranks: ${srcs}</div>${intel ? `<div>${intel}</div>` : ""}</div></details>`;
  }).join("");
  return (rows ? `<div class="list">${rows}</div>` : empty("No prospects match", "Try a different name or school.")) +
    (!q && total > list.length ? `<div class="chips" style="margin-top:16px"><button class="btn" data-act="dMore" data-v="${ui.dMore + 50}">Show more (${total - list.length} left)</button></div>` : "");
}
function mockHtml(d) {
  const m = d.mocks || {};
  const schoolOf = (name) => { const k = lkey(name).replace(/(jr|sr|ii|iii|iv)$/, ""); const hit = d.players.find((p) => lkey(p.name).replace(/(jr|sr|ii|iii|iv)$/, "") === k); return hit && hit.profile ? hit.profile.school : ""; };
  const block = (v, withTeam) => v && v.picks ? `<section class="mock">${title(v.title, "30 picks")}<div class="list"><ol>${v.picks.map((x) => {
    const sc = schoolOf(x.player);
    return `<li><span class="pk">${x.pick}</span>${withTeam ? tm(x.team, "nba", nick(x.team)) : ""}<span><b>${esc(x.player)}</b>${sc ? ` <span class="kv">${tm(sc, "college")}</span>` : ""}</span></li>`;
  }).join("")}</ol></div></section>` : "";
  return block(m.v2, true) + block(m.v1, false);
}
async function renderDraft() {
  const d = cache.draft;
  if (!d) return failed.draft ? empty("Draft board not built yet", "The board is rebuilt every Monday from big boards and mock drafts.") : skeleton();
  return `<div class="chips"><input id="dq" class="btn" type="search" placeholder="Search prospects or schools" value="${esc(ui.dq)}" aria-label="Search prospects"></div>
    ${title(`${d.label} consensus board`, `${d.players.length} prospects`)}<div id="dlist">${draftRows(d)}</div>
    ${mockHtml(d)}
    <p class="note">Sources: ${esc(d.sources.join(", "))}. Moves compare with last week's board. The board rebuilds every Monday and adds more prospects as sources publish deeper lists.</p>`;
}

/* ---------- Rookies ---------- */
const statRow = (p, i) => `<tr><td class="l"><b>${i ? i + ". " : ""}${esc(p.name)}</b> <span class="kv">${tm(p.team, "nba")}</span></td><td>${p.gp}</td><td>${p.min}</td>
  <td>${p.pts}</td><td>${p.reb}</td><td>${p.ast}</td><td>${p.stl}</td><td>${p.blk}</td><td>${p.fg}</td><td>${p.tp}</td></tr>`;
const statHead = `<thead><tr><th class="l">Player</th><th>GP</th><th>MIN</th><th>PTS</th><th>REB</th><th>AST</th><th>STL</th><th>BLK</th><th>FG%</th><th>3P%</th></tr></thead>`;
async function renderRookies() {
  const d = cache.rookies;
  if (!d) return failed.rookies ? empty("No rookie stats yet", "Rookie stats appear once the stats feed has refreshed.") : skeleton();
  if (!d.players.length) return empty("No rookie stats yet", "Rookie stats appear once rookies have played.");
  return `${title(d.class_label, "Top 15 by impact")}
    <div class="tbl"><table class="sticky1">${statHead}<tbody>${d.top15.map((p) => statRow(p, p.rank)).join("")}</tbody></table></div>
    ${title("All rookies", d.players.length + " players")}
    <div class="tbl"><table class="sticky1">${statHead}<tbody>${d.players.map((p) => statRow(p)).join("")}</tbody></table></div>
    <p class="note">The top 15 ranks a per game impact index (points, rebounds, assists, steals, blocks, turnovers, shooting). Updated hourly.</p>`;
}

/* ---------- Leaders ---------- */
const CAT_NAMES = { PTS: "Points", REB: "Rebounds", AST: "Assists", STL: "Steals", BLK: "Blocks", FG3M: "3-pointers made",
  FG_PCT: "FG%", FG3_PCT: "3P%", FT_PCT: "FT%", TOV: "Turnovers", MIN: "Minutes", FGM: "Field goals made", FTM: "Free throws made" };
async function renderLeaders() {
  const d = cache.leaders;
  const modes = [["perGame", "Per game"], ["totals", "Totals"], ["pos", "By position"], ["top150", "Top 150"]]
    .map(([k, l]) => `<button class="btn" data-act="leaderMode" data-v="${k}" aria-pressed="${ui.leaderMode === k}">${l}</button>`).join("");
  if (!d) return `<div class="chips">${modes}</div>` + (failed.leaders ? empty("No leaderboards yet", "Leaderboards refresh hourly.") : skeleton());
  if (ui.leaderMode === "perGame" || ui.leaderMode === "totals") {
    const set = d[ui.leaderMode], cats = Object.keys(set);
    if (!set[ui.leaderCat]) ui.leaderCat = cats[0];
    const sel = `<select class="btn" data-act="leaderCat" aria-label="Category">${cats.map((c) => `<option value="${c}" ${c === ui.leaderCat ? "selected" : ""}>${CAT_NAMES[c] || c}</option>`).join("")}</select>`;
    return `<div class="chips">${modes}${sel}</div><div class="list">${set[ui.leaderCat].map((r, i) => `<div class="row"><span class="rk">${i + 1}</span>
      <div class="main"><div class="t">${esc(r.name)}</div><div class="s">${tm(r.team, "nba")}</div></div><div class="end">${r.val}</div></div>`).join("")}</div>`;
  }
  let list, head;
  if (ui.leaderMode === "pos") {
    const posBtns = [["G", "Guards"], ["F", "Forwards"], ["C", "Centers"]].map(([k, l]) => `<button class="btn" data-act="pos" data-v="${k}" aria-pressed="${ui.pos === k}">${l}</button>`).join("");
    list = d.byPosition[ui.pos] || []; head = `<div class="chips">${modes}${posBtns}</div>`;
  } else { list = d.top150; head = `<div class="chips">${modes}</div>`; }
  return head + `<div class="tbl"><table class="sticky1">${statHead}<tbody>${list.map((p) => statRow(p, p.rank)).join("")}</tbody></table></div>
    <p class="note">Ranked by a per game impact index. Players need at least 40% of games played and 12 minutes a game.</p>`;
}

/* ---------- Teams ---------- */
const rk = (r) => `<span class="${r <= 8 ? "good" : r >= 23 ? "bad" : "kv"}">#${r}</span>`;
function mockPicksFor(t) {
  const m = cache.draft && cache.draft.mocks && cache.draft.mocks.v2; if (!m) return "";
  const me = logoUrl(t.name, "nba"), mine = m.picks.filter((x) => (me ? logoUrl(x.team, "nba") === me : lkey(x.team) === lkey(t.name)));
  if (!mine.length) return `${title("Projected " + (cache.draft.cycle || "") + " picks", "Cyro and Mikey mock 2.0")}<div class="list"><div class="row"><span class="kv">No first round picks in this mock</span></div></div>`;
  return `${title("Projected " + (cache.draft.cycle || "") + " picks", "Cyro and Mikey mock 2.0")}<div class="list">${mine.map((x) => `<div class="row"><span class="rk">${x.pick}</span><div class="main"><div class="t">${esc(x.player)}</div><div class="s">Pick ${x.pick}${(() => { const sc = ((cache.draft.players.find((p) => lkey(p.name) === lkey(x.player)) || {}).profile || {}).school; return sc ? ", " + tm(sc, "college") : ""; })()}</div></div></div>`).join("")}</div>`;
}
async function renderTeams() {
  const d = cache.teams;
  if (!d || !d.teams.length) return failed.teams || (d && !d.teams.length) ? empty("No team data yet", "Team pages refresh hourly.") : skeleton();
  if (!ui.team) ui.team = d.teams[0].name;
  const t = d.teams.find((x) => x.name === ui.team) || d.teams[0];
  const sel = `<div class="chips"><select class="btn" data-act="team" aria-label="Team">${d.teams.map((x) => `<option ${x.name === t.name ? "selected" : ""}>${esc(x.name)}</option>`).join("")}</select></div>`;
  const stats = (obj, names) => Object.keys(obj || {}).length ? `<div class="tbl"><table><thead><tr><th class="l">Stat</th><th>Value</th><th>Rank</th></tr></thead><tbody>
    ${Object.entries(obj).map(([k, v]) => `<tr><td class="l">${names[k] || k}</td><td>${v.v}</td><td>${rk(v.r)}</td></tr>`).join("")}</tbody></table></div>` : empty("Not available", "Stats arrive with the next hourly refresh.");
  const N = { PTS: "Points", REB: "Rebounds", AST: "Assists", STL: "Steals", BLK: "Blocks", TOV: "Turnovers", FG_PCT: "FG%", FG3_PCT: "3P%", FT_PCT: "FT%",
    OPP_PTS: "Points allowed", OPP_REB: "Rebounds allowed", OPP_AST: "Assists allowed", OPP_FG_PCT: "Opponent FG%", OPP_FG3_PCT: "Opponent 3P%", OPP_TOV: "Opponent turnovers" };
  const pk = (arr) => arr.length ? arr.map((p) => `<div class="row"><div class="main"><div class="t">${p.year} round ${p.round}${p.from && p.from !== "own" ? ", from " + esc(p.from) : ""}</div>
    <div class="s">${esc(p.protection || p.reason || "")}</div></div></div>`).join("") : `<div class="row"><span class="kv">None listed</span></div>`;
  return sel + `<div class="hero">${logo(t.logo, true)}<div><div class="big">${esc(t.name)}</div>
    <div class="kv">${esc(t.conf)}${t.seed ? ", seed " + esc(t.seed) : ""}, streak ${esc(t.streak || "n/a")}, last 10 ${esc(t.l10 || "n/a")}, home ${esc(t.home || "n/a")}, away ${esc(t.away || "n/a")}, behind ${esc(t.gb || "n/a")}</div></div>
    <div class="rec">${esc(t.w)}-${esc(t.l)}</div></div>
    ${title("Team stats")}${stats(t.stats, N)}
    ${title("What opponents do against them")}${stats(t.opp, N)}
    ${title("Players and salaries", t.players.length + " players")}<div class="tbl"><table class="sticky1"><thead><tr><th class="l">Player</th><th>Pos</th><th>Ht</th><th>Wt</th><th>Salary</th><th>Thru</th><th>GP</th><th>MIN</th><th>PTS</th><th>REB</th><th>AST</th></tr></thead><tbody>
    ${t.players.map((p) => `<tr><td class="l"><b>${esc(p.name)}</b></td><td>${esc(p.pos || "")}</td><td>${esc(p.ht || "")}</td><td>${p.wt || ""}</td><td>${money(p.salary)}</td><td>${esc(p.contract_end || "")}${p.option ? " (" + esc(p.option) + ")" : ""}</td><td>${p.gp}</td><td>${p.min}</td><td>${p.pts}</td><td>${p.reb}</td><td>${p.ast}</td></tr>`).join("")}</tbody></table></div>
    ${mockPicksFor(t)}${title("Draft picks they can trade")}<div class="list">${pk(t.picks.tradable)}</div>
    ${title("Draft picks they cannot trade")}<div class="list">${pk(t.picks.locked)}</div>`;
}

/* ---------- Contracts ---------- */
const STATUS_LABEL = { GUARANTEED: "Guaranteed", "NON-GUARANTEED": "Non-guaranteed", "TEAM OPTION": "Team option", "PLAYER OPTION": "Player option" };
const EXT_CLASS = { eligible: "good", future: "", extended: "", rookie: "", ineligible: "bad", na: "", unknown: "" };
function extLine(p) {
  const bits = [];
  if (p.since) bits.push(`<span class="kv">Since <b>${esc(p.since)}</b></span>`);
  if (p.ext && p.ext.text && p.ext.text !== "-") bits.push(`<span class="kv">Ext. <span class="pill ${EXT_CLASS[p.ext.status] || ""}">${esc(p.ext.text)}</span></span>`);
  if (p.trade) bits.push(`<span class="kv">Trade <span class="pill ${p.trade.type === "restricted" || p.trade.type === "ntc" ? "bad" : ""}">${esc(p.trade.text)}</span></span>`);
  if (p.maxpct) bits.push(`<span class="kv">Max <b>${p.maxpct}%</b>${p.dv ? " DV" : ""}</span>`);
  return bits.length ? `<div class="extline">${bits.join("")}</div>` : "";
}
function contractRows(d) {
  ui.cMore = Number(ui.cMore) || 60;
  const q = ui.q.trim().toLowerCase();
  let list = d.players.filter((p) => (ui.cTeam === "all" || p.team === ui.cTeam) && (!q || p.name.toLowerCase().includes(q))
    && (ui.cExt === "all" || (p.ext && p.ext.status === ui.cExt)) && (ui.cTrade === "all" || (ui.cTrade === "none" ? !p.trade : p.trade && p.trade.type === ui.cTrade)));
  list = list.sort((a, b) => (b.years[0] ? b.years[0].sal : 0) - (a.years[0] ? a.years[0].sal : 0));
  const total = list.length; list = list.slice(0, ui.cMore);
  const rows = list.map((p) => {
    const yrs = p.years.map((y) => `<tr><td class="l">${esc(y.y)}</td><td>${money(y.sal)}</td><td>${y.ch && y.ch !== y.sal ? money(y.ch) : ""}</td><td class="l">${esc(STATUS_LABEL[y.st] || y.st)}</td></tr>`).join("");
    const facts = [["With team since", p.since], ["Drafted", p.draft_year ? p.draft_year + (p.draft_pick ? ", pick " + p.draft_pick : "") : ""],
      ["Max contract", p.maxpct ? p.maxpct + "% of cap" + (p.dv ? " (Designated Veteran eligible)" : "") : ""],
      ["Extension", p.ext && p.ext.detail ? p.ext.text + ". " + p.ext.detail : ""], ["Trade", p.trade ? (p.trade.detail || p.trade.text) : ""], ["Exception", p.exception], ["Signed", p.signed ? p.signed + (p.signed_by ? " by " + p.signed_by : "") : ""], ["Trade kicker", p.kicker],
      ["Likely bonus", p.likely], ["Unlikely bonus", p.unlikely], ["Notes", p.notes]].filter((x) => x[1]).map((x) => `<span class="kv">${x[0]}: <b>${esc(x[1])}</b></span>`).join("");
    return `<details class="p"><summary><span style="flex:1;min-width:0"><b>${esc(p.name)}</b> <span class="kv">${tm(p.team, "nba")}</span>${extLine(p)}</span>
      <b>${money(p.years[0] && p.years[0].sal)}</b><span class="kv">${esc(p.end ? "thru " + p.end : "")}${p.option ? ", " + esc(p.option) : ""}</span></summary>
      <div class="pbody" style="padding-left:16px"><div class="tbl"><table><thead><tr><th class="l">Season</th><th>Salary</th><th>Cap hold</th><th class="l">Status</th></tr></thead><tbody>${yrs}</tbody></table></div>
      <div class="kv">Total guaranteed: <b>${money(p.total)}</b></div>${facts ? `<div class="facts">${facts}</div>` : ""}</div></details>`;
  }).join("");
  return (rows ? `<div class="list">${rows}</div>` : empty("No contracts match", "Try a different name or team.")) +
    (total > list.length ? `<div class="chips" style="margin-top:16px"><button class="btn" data-act="cMore" data-v="${ui.cMore + 60}">Show more (${total - list.length} left)</button></div>` : "");
}
async function renderContracts() {
  const d = cache.contracts;
  if (!d) return failed.contracts ? empty("No contracts yet", "Contracts refresh hourly from HoopsMatic.") : skeleton();
  const teams = [...new Set(d.players.map((p) => p.team))].sort();
  const sel = `<select class="btn" data-act="cTeam" aria-label="Team"><option value="all">All teams</option>${teams.map((t) => `<option ${ui.cTeam === t ? "selected" : ""}>${esc(t)}</option>`).join("")}</select>`;
  const opt = (cur, pairs) => pairs.map(([v, l]) => `<option value="${v}" ${cur === v ? "selected" : ""}>${l}</option>`).join("");
  const selExt = `<select class="btn" data-act="cExt" aria-label="Extension eligibility">${opt(ui.cExt, [["all", "Any extension status"], ["eligible", "Extension eligible now"], ["future", "Eligible later"], ["extended", "Already extended"], ["rookie", "Rookie scale"], ["ineligible", "Ineligible"], ["na", "Not applicable"]])}</select>`;
  const selTr = `<select class="btn" data-act="cTrade" aria-label="Trade status">${opt(ui.cTrade, [["all", "Any trade status"], ["restricted", "Trade restricted"], ["ntc", "No-trade clause"], ["expiring", "Expiring"], ["none", "No restriction"]])}</select>`;
  return `<div class="chips"><input id="q" class="btn" type="search" placeholder="Search players" value="${esc(ui.q)}" aria-label="Search players">${sel}${selExt}${selTr}</div>
    <div id="clist">${contractRows(d)}</div><p class="note">Contract data and the extension, trade and max contract rules follow hoopsmatic.com/contracts. Cap holds shown only when they differ from salary. Extension and trade dates are calculated from the signing date, so check the notes on unusual deals.</p>`;
}

/* ---------- Cap ---------- */
async function renderCap() {
  const d = cache.cap;
  if (!d) return failed.cap ? empty("No cap data yet", "Cap sheets refresh hourly.") : skeleton();
  const th = d.thresholds || {};
  const cell = (v) => `<td class="${v != null && v < 0 ? "bad" : ""}">${money(v)}</td>`;
  const e = (t) => t.exceptions || {};
  const mle = (t) => (e(t).mle_type ? esc(e(t).mle_type) + (e(t).mle_left != null ? ", " + money(e(t).mle_left) + " left" : "") : "None");
  const detail = (t) => {
    const used = (e(t).mle_used_on || []).map((u) => `${esc(u.player)} ${money(u.amount)}`).join(", ");
    const tp = (t.tpes || []).map((x) => `<div class="row"><div class="main"><div class="t">${money(x.value)} trade exception</div><div class="s">Expires ${esc(x.expires)}</div></div></div>`).join("");
    return `<details class="p"><summary><span style="flex:1"><b>${tm(t.team, "nba")}</b></span><span class="kv">${esc(t.status || "")}</span><span class="kv">${(t.tpes || []).length} TPE</span></summary>
      <div class="pbody" style="padding-left:16px"><div class="kv">Mid-level: <b>${mle(t)}</b>${used ? ", used on " + used : ""}</div>
      <div class="kv">Bi-annual exception: <b>${e(t).bae != null ? money(e(t).bae) : "n/a"}</b></div>
      ${tp ? `<div class="list">${tp}</div>` : `<div class="kv">No trade exceptions</div>`}</div></details>`;
  };
  return `${title((th.season || "") + " lines")}<div class="list"><div class="row"><div class="main">
    <div class="s">Cap ${money(th.salary_cap)}, tax ${money(th.luxury_tax)}, first apron ${money(th.first_apron)}, second apron ${money(th.second_apron)}</div></div></div></div>
    ${title("Space and room, by team")}<div class="tbl"><table class="sticky1">
    <thead><tr><th class="l">Team</th><th>Payroll</th><th>Cap space</th><th>Under tax by</th><th>Under 1st apron by</th><th>Under 2nd apron by</th><th class="l">Mid-level</th><th>BAE</th></tr></thead><tbody>
    ${d.teams.map((t) => `<tr><td class="l"><b>${tm(t.team, "nba")}</b></td><td>${money(t.payroll)}</td>${cell(t.cap_space)}${cell(t.tax_room)}${cell(t.first_apron_room)}${cell(t.second_apron_room)}
    <td class="l">${mle(t)}</td><td>${e(t).bae != null ? money(e(t).bae) : "n/a"}</td></tr>`).join("")}</tbody></table></div>
    ${title("Exceptions and trade exceptions")}<div class="list">${d.teams.map(detail).join("")}</div>
    <p class="note">Negative numbers mean the team is over that line. Source: ${esc(d.source || "")}.</p>`;
}

/* ---------- Shell ---------- */
const RENDER = { live: renderLive, standings: renderStandings, trending: renderTrending, news: renderNews, injuries: renderInjuries, draft: renderDraft,
  rookies: renderRookies, leaders: renderLeaders, teams: renderTeams, contracts: renderContracts, cap: renderCap };

function drawTabs() {
  tabsEl.innerHTML = TABS.map(([k, l]) => `<button class="tab" role="tab" id="tab-${k}" data-tab="${k}" aria-selected="${ui.tab === k}">${l}</button>`).join("");
  const sel = document.getElementById("tab-" + ui.tab); if (sel && sel.scrollIntoView) sel.scrollIntoView({ block: "nearest", inline: "center" });
}
async function draw(keepScroll) {
  const y = window.scrollY;
  view.innerHTML = await RENDER[ui.tab]();
  if (keepScroll) window.scrollTo(0, y);
  drawTicker();
  const stamps = Object.values(cache).filter(Boolean).map((v) => Date.parse(v.updated)).filter(Boolean);
  stampEl.textContent = stamps.length ? "Updated " + rel(new Date(Math.max(...stamps)).toISOString()) : "Loading";
}
async function refresh() {
  const names = [...new Set([...DATA_FOR[ui.tab], "scores"])];
  const before = JSON.stringify(cache.scores && cache.scores.games.map((g) => [g.id, g.state, g.home.score, g.away.score]));
  await Promise.all(names.map((n) => load(n, true)));
  localNotify(before);
  draw(true);
}
/* After the first paint, fetch every other section so tab switches are instant. */
function warmAll() {
  ALL_DATA.filter((n) => !fresh.has(n)).forEach((n) => load(n, true).then(() => {
    if (DATA_FOR[ui.tab].includes(n) && view.querySelector(".skel")) draw(true);
  }));
}
async function ensure() {
  const miss = DATA_FOR[ui.tab].filter((n) => !fresh.has(n)), tab = ui.tab;
  if (!miss.length) return;
  await Promise.all(miss.map((n) => load(n, true)));
  if (ui.tab === tab) draw(true);
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
async function localNotify() {
  const d = cache.scores; if (!d) return;
  const snap = {}; d.games.forEach((g) => (snap[g.id] = g));
  if (lastGames && store("alerts") === "on" && "Notification" in window && Notification.permission === "granted") {
    for (const g of d.games) {
      const o = lastGames[g.id]; if (!o) continue;
      const label = `${g.away.abbr} ${g.away.score}, ${g.home.abbr} ${g.home.score}`;
      let ttl = null;
      if (o.state === "pre" && g.state === "in") ttl = `Starting: ${g.away.abbr} at ${g.home.abbr}`;
      if (o.state !== "post" && g.state === "post") ttl = `Final: ${label}`;
      if (ttl) {
        const reg = await navigator.serviceWorker.getRegistration();
        if (reg) reg.showNotification(ttl, { body: g.league, icon: "icon-192.png", tag: g.id });
      }
    }
  }
  lastGames = snap;
}

document.addEventListener("click", (e) => {
  const tab = e.target.closest("[data-tab]");
  if (tab) { ui.tab = tab.dataset.tab; store("tab", ui.tab); drawTabs(); draw(); ensure(); window.scrollTo(0, 0); return; }
  const a = e.target.closest("[data-act]");
  if (a && a.tagName !== "SELECT") { ui[a.dataset.act] = a.dataset.v; if (a.dataset.act === "newsWin") ui.newsMore = 60; draw(true); }
});
document.addEventListener("change", (e) => {
  const a = e.target.closest("select[data-act]"); if (a) { ui[a.dataset.act] = a.value; ui.newsMore = 60; draw(true); }
});
document.addEventListener("input", (e) => {
  if (e.target.id === "q") {
    ui.q = e.target.value; ui.cMore = 60;
    const box = document.getElementById("clist"); if (box && cache.contracts) box.innerHTML = contractRows(cache.contracts);
  }
  if (e.target.id === "dq") {
    ui.dq = e.target.value; ui.dMore = 50;
    const box = document.getElementById("dlist"); if (box && cache.draft) box.innerHTML = draftRows(cache.draft);
  }
});
bell.addEventListener("click", toggleAlerts);

(async function init() {
  const saved = location.hash.slice(1) || store("tab"); if (saved && RENDER[saved]) ui.tab = saved;
  drawTabs(); bellState();
  primeFromSaved();
  loadLogos().then(() => draw(true));
  await draw();                               // paint the last saved data at once
  await Promise.all(DATA_FOR[ui.tab].concat("scores").map((n) => load(n, true)));
  await draw(); await localNotify();          // then swap in fresh data
  warmAll();
  setInterval(refresh, REFRESH_MS);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); });
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
})();
