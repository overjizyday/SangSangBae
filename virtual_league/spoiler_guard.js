const SYNC_TICK_SECONDS = 2;
const DAY_ORDER_SYNC = ["월", "화", "수", "목", "금", "토", "일"];
const WEEKDAY_ORDER_SYNC = Object.fromEntries(DAY_ORDER_SYNC.map((day, index) => [day, index]));
const COMPETITION_ORDER_SYNC = { acl: 0, local_cup: 1, championship: 2, fa_cup: 3, super_cup: 4, league: 5 };

function feedEventCount(feed) {
  return Array.isArray(feed.events) ? feed.events.length : 0;
}

function groupedFeeds(feeds) {
  const sorted = [...feeds].sort((a, b) => {
    const aw = Number(a.week || 0);
    const bw = Number(b.week || 0);
    if (aw !== bw) return aw - bw;
    const ad = WEEKDAY_ORDER_SYNC[String(a.day || "")] ?? 99;
    const bd = WEEKDAY_ORDER_SYNC[String(b.day || "")] ?? 99;
    if (ad !== bd) return ad - bd;
    const ac = COMPETITION_ORDER_SYNC[String(a.competition || "")] ?? 99;
    const bc = COMPETITION_ORDER_SYNC[String(b.competition || "")] ?? 99;
    if (ac !== bc) return ac - bc;
    return String(a.match_id || "").localeCompare(String(b.match_id || ""));
  });

  const groups = new Map();
  for (const feed of sorted) {
    const key = `${Number(feed.week || 0)}|${String(feed.day || "")}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(feed);
  }
  return Array.from(groups.values());
}

function groupDuration(group) {
  return Math.max(0, ...group.map(feedEventCount)) + 1;
}

function loadReplayStartMs(replayStartKey) {
  try {
    const raw = localStorage.getItem(replayStartKey);
    const parsed = raw ? Number(raw) : NaN;
    if (Number.isFinite(parsed) && parsed > 0) return parsed;
    const now = Date.now();
    localStorage.setItem(replayStartKey, String(now));
    return now;
  } catch (err) {
    return Date.now();
  }
}

function completedMatchIds(feeds, replayStartedAt, nowMs = Date.now()) {
  const groups = groupedFeeds(feeds);
  const totalTicks = groups.reduce((sum, group) => sum + groupDuration(group), 0);
  const completed = new Set();
  if (!totalTicks) return completed;

  const startMs = Number.isFinite(replayStartedAt) ? replayStartedAt : nowMs;
  const elapsedTicks = Math.max(0, Math.floor((nowMs - startMs) / (SYNC_TICK_SECONDS * 1000)));
  if (elapsedTicks <= 0) return completed;
  if (elapsedTicks >= totalTicks) {
    for (const group of groups) {
      for (const feed of group) completed.add(String(feed.match_id));
    }
    return completed;
  }

  let tick = elapsedTicks;
  let groupIndex = 0;
  for (; groupIndex < groups.length; groupIndex += 1) {
    const duration = groupDuration(groups[groupIndex]);
    if (tick < duration) break;
    tick -= duration;
  }

  for (let index = 0; index < groupIndex; index += 1) {
    for (const feed of groups[index]) completed.add(String(feed.match_id));
  }
  return completed;
}

function guardCalendar(feeds, replayStartedAt) {
  const completed = completedMatchIds(feeds, replayStartedAt);
  const feedById = new Map(feeds.map((feed) => [String(feed.match_id || ""), feed]));
  document.querySelectorAll(".match").forEach((matchEl, index) => {
    const scoreEl = matchEl.querySelector(".score");
    if (!scoreEl) return;
    const matchId = String(matchEl.dataset.matchId || "");
    const feed = feedById.get(matchId) || null;
    const done = completed.has(matchId);
    if (!done) {
      scoreEl.textContent = "예정";
      scoreEl.style.color = "#9aa3af";
    } else if (feed) {
      scoreEl.textContent = `${Number(feed.away_score || 0)} - ${Number(feed.home_score || 0)}`;
      scoreEl.style.color = "";
    }
  });
}

function resultRow(feed) {
  return {
    competition: String(feed.competition || ""),
    home_team_id: String(feed.home_team_id || ""),
    away_team_id: String(feed.away_team_id || ""),
    home_score: Number(feed.home_score || 0),
    away_score: Number(feed.away_score || 0),
  };
}

function emptyStats(teamId, teamNames) {
  return {
    team_id: teamId,
    team_name: teamNames.get(teamId) || teamId,
    played: 0,
    wins: 0,
    draws: 0,
    losses: 0,
    gf: 0,
    ga: 0,
    gd: 0,
    points: 0,
  };
}

function calculateStandings(teamIds, matches, teamNames) {
  const table = new Map(teamIds.map((id) => [id, emptyStats(id, teamNames)]));
  for (const match of matches) {
    if (!table.has(match.home_team_id)) table.set(match.home_team_id, emptyStats(match.home_team_id, teamNames));
    if (!table.has(match.away_team_id)) table.set(match.away_team_id, emptyStats(match.away_team_id, teamNames));
    const home = table.get(match.home_team_id);
    const away = table.get(match.away_team_id);
    home.played += 1;
    away.played += 1;
    home.gf += match.home_score;
    home.ga += match.away_score;
    away.gf += match.away_score;
    away.ga += match.home_score;
    if (match.home_score > match.away_score) {
      home.wins += 1; home.points += 3; away.losses += 1;
    } else if (match.home_score < match.away_score) {
      away.wins += 1; away.points += 3; home.losses += 1;
    } else {
      home.draws += 1; away.draws += 1; home.points += 1; away.points += 1;
    }
  }
  const rows = Array.from(table.values()).map((row) => ({ ...row, gd: row.gf - row.ga }));
  rows.sort((a, b) => (
    b.points - a.points ||
    b.gd - a.gd ||
    b.gf - a.gf ||
    a.ga - b.ga ||
    String(a.team_name).localeCompare(String(b.team_name), "ko")
  ));
  rows.forEach((row, index) => { row.rank = index + 1; });
  return rows;
}

function standingsTable(rows, compact = false) {
  const headers = compact ? ["순위", "팀", "경기"] : ["순위", "팀", "경기", "승", "무", "패", "득점", "실점", "득실", "승점"];
  const cols = compact ? ["rank", "team_name", "played"] : ["rank", "team_name", "played", "wins", "draws", "losses", "gf", "ga", "gd", "points"];
  return `
    <table>
      <thead><tr>${headers.map((header) => `<th>${header}</th>`).join("")}</tr></thead>
      <tbody>${rows.map((row) => `<tr>${cols.map((col) => `<td>${row[col] ?? ""}</td>`).join("")}</tr>`).join("")}</tbody>
    </table>
  `;
}

function injectCupStyles() {
  if (document.getElementById("spoiler-guard-styles")) return;
  const style = document.createElement("style");
  style.id = "spoiler-guard-styles";
  style.textContent = `
    .cup-tabs { display: flex; gap: 8px; margin: 0 0 12px; flex-wrap: wrap; }
    .cup-tab {
      border: 1px solid #d8dee8;
      background: #f8fafc;
      color: #172033;
      border-radius: 6px;
      padding: 6px 10px;
      cursor: pointer;
      font: inherit;
      font-size: 12px;
    }
    .cup-tab.active { background: #172033; color: #fff; border-color: #172033; }
    .cup-view[hidden] { display: none; }
    .cup-group { margin-bottom: 14px; }
    .cup-group h3, .bracket-round h3 { margin: 0 0 8px; font-size: 13px; }
    .bracket { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
    .bracket-round { min-width: 0; }
    .bracket-match {
      border: 1px solid #d8dee8;
      border-radius: 8px;
      background: #f8fafc;
      padding: 8px;
      margin-bottom: 8px;
      font-size: 12px;
    }
    .bracket-team { display: flex; justify-content: space-between; gap: 8px; padding: 2px 0; }
    .bracket-team.winner { font-weight: 700; color: #0f766e; }
    .bracket-meta { color: #657083; font-size: 11px; margin-bottom: 4px; }
    .leg-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
    .leg-box {
      border: 1px solid #e5eaf2;
      border-radius: 6px;
      background: #fff;
      padding: 6px;
      min-width: 0;
    }
    .leg-label { color: #657083; font-size: 11px; margin-bottom: 4px; }
    .pending { color: #9aa3af; }
  `;
  document.head.appendChild(style);
}

function matchCompleted(match, completed) {
  return completed.has(String(match.id || match.match_id || ""));
}

function matchToResult(match) {
  return {
    competition: String(match.competition || ""),
    home_team_id: String(match.home_team_id || ""),
    away_team_id: String(match.away_team_id || ""),
    home_score: Number(match.home_score || 0),
    away_score: Number(match.away_score || 0),
  };
}

function teamLabel(teamId, teamNames) {
  return teamNames.get(String(teamId || "")) || String(teamId || "");
}

function renderBracket(matches, completed, teamNames, prerequisiteMatches = []) {
  const stageOrder = {
    preliminary: 0, regional_po: 1, qf: 2, sf: 3, final: 4,
    ACL1_po: 0, ACL1_qf: 1, ACL1_sf: 2, ACL1_final: 3,
    ACL2_po: 0, ACL2_qf: 1, ACL2_sf: 2, ACL2_final: 3,
    ACL3_po: 0, ACL3_qf: 1, ACL3_sf: 2, ACL3_final: 3,
  };
  const stageLabels = {
    preliminary: "예선",
    regional_po: "통합 PO",
    qf: "8강",
    sf: "4강",
    final: "결승",
  };
  const visibleMatches = visibleBracketMatches(matches, completed, stageOrder, prerequisiteMatches);
  const stages = new Map();
  for (const match of visibleMatches) {
    const stage = String(match.stage || "stage");
    if (!stages.has(stage)) stages.set(stage, []);
    stages.get(stage).push(match);
  }
  const rounds = Array.from(stages.entries()).sort((a, b) => {
    const ao = stageOrder[a[0]] ?? 50;
    const bo = stageOrder[b[0]] ?? 50;
    return ao - bo || a[0].localeCompare(b[0]);
  });
  if (!rounds.length) return `<p class="pending">표시할 토너먼트 경기가 없습니다.</p>`;
  return `<div class="bracket">${rounds.map(([stage, stageMatches]) => `
    <section class="bracket-round">
      <h3>${stageLabels[stage] || bracketStageLabel(stage)}</h3>
      ${groupBracketMatches(stageMatches).map((matchGroup) => {
        const first = matchGroup[0];
        const aggregateWinner = aggregateWinnerId(matchGroup, completed);
        return `
          <div class="bracket-match">
            <div class="bracket-meta">W${Number(first.week || 0)} · ${String(first.round || "")}${matchGroup.length > 1 ? " · 2-leg" : ""}</div>
            ${matchGroup.length > 1 ? `
              <div class="leg-grid">
                ${matchGroup.map((match) => renderLegBox(match, completed, teamNames, aggregateWinner)).join("")}
              </div>
            ` : renderLegBox(first, completed, teamNames, aggregateWinner)}
          </div>
        `;
      }).join("")}
    </section>
  `).join("")}</div>`;
}

function bracketStageLabel(stage) {
  const value = String(stage || "");
  if (value.endsWith("_po")) return "PO";
  if (value.endsWith("_qf")) return "8강";
  if (value.endsWith("_sf")) return "4강";
  if (value.endsWith("_final")) return "결승";
  if (value.endsWith("_group")) return "조별";
  return value;
}

function groupBracketMatches(matches) {
  const groups = new Map();
  for (const match of matches) {
    const teams = [String(match.home_team_id || ""), String(match.away_team_id || "")].sort().join("|");
    const key = `${String(match.stage || "")}|${String(match.round || "")}|${teams}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(match);
  }
  return Array.from(groups.values())
    .map((items) => items.sort((a, b) => Number(a.leg || 1) - Number(b.leg || 1) || Number(a.week || 0) - Number(b.week || 0)))
    .sort((a, b) => Number(a[0].match_no || 0) - Number(b[0].match_no || 0) || Number(a[0].week || 0) - Number(b[0].week || 0));
}

function visibleBracketMatches(matches, completed, stageOrder, prerequisiteMatches = []) {
  const stages = Array.from(new Set(matches.map((match) => String(match.stage || "stage"))))
    .sort((a, b) => (stageOrder[a] ?? 50) - (stageOrder[b] ?? 50) || a.localeCompare(b));
  const visibleStages = new Set();

  for (const stage of stages) {
    const order = stageOrder[stage] ?? 50;
    const priorStages = stages.filter((item) => (stageOrder[item] ?? 50) < order);
    const prerequisitesDone = prerequisiteMatches.every((match) => matchCompleted(match, completed));
    const priorDone = priorStages.every((priorStage) => matches
      .filter((match) => String(match.stage || "stage") === priorStage)
      .every((match) => matchCompleted(match, completed)));
    if (prerequisitesDone && priorDone) {
      visibleStages.add(stage);
    }
  }

  return matches.filter((match) => visibleStages.has(String(match.stage || "stage")));
}

function aggregateWinnerId(matchGroup, completed) {
  if (!matchGroup.every((match) => matchCompleted(match, completed))) return "";
  const totals = new Map();
  for (const match of matchGroup) {
    totals.set(String(match.home_team_id || ""), (totals.get(String(match.home_team_id || "")) || 0) + Number(match.home_score || 0));
    totals.set(String(match.away_team_id || ""), (totals.get(String(match.away_team_id || "")) || 0) + Number(match.away_score || 0));
  }
  const sorted = Array.from(totals.entries()).sort((a, b) => b[1] - a[1]);
  if (sorted.length >= 2 && sorted[0][1] === sorted[1][1]) return String(matchGroup[matchGroup.length - 1].winner_team_id || "");
  return sorted[0]?.[0] || "";
}

function renderLegBox(match, completed, teamNames, aggregateWinner) {
  const done = matchCompleted(match, completed);
  const home = teamLabel(match.home_team_id, teamNames);
  const away = teamLabel(match.away_team_id, teamNames);
  const homeScore = done ? Number(match.home_score || 0) : "예정";
  const awayScore = done ? Number(match.away_score || 0) : "예정";
  const legLabel = match.leg ? `Leg ${Number(match.leg)}` : "단판";
  return `
    <div class="leg-box">
      <div class="leg-label">${legLabel} · W${Number(match.week || 0)}</div>
      <div class="bracket-team ${aggregateWinner === String(match.away_team_id || "") ? "winner" : ""}">
        <span>${away}</span><span>${awayScore}</span>
      </div>
      <div class="bracket-team ${aggregateWinner === String(match.home_team_id || "") ? "winner" : ""}">
        <span>${home}</span><span>${homeScore}</span>
      </div>
    </div>
  `;
}

function renderLocalCupPanel(panel, localCup, completed, teamNames) {
  const activeTarget = panel.dataset.activeCupTarget || "local-groups";
  const matches = Array.isArray(localCup?.matches) ? localCup.matches : [];
  const groupMatches = matches.filter((match) => String(match.stage || "") === "regional_qualifier");
  const knockoutMatches = matches.filter((match) => String(match.stage || "") !== "regional_qualifier");
  const regions = Array.from(new Set(groupMatches.map((match) => String(match.region || "지역 예선"))));
  const groupsHtml = regions.map((region) => {
    const regionMatches = groupMatches.filter((match) => String(match.region || "지역 예선") === region);
    const teamIds = Array.from(new Set(regionMatches.flatMap((match) => [String(match.home_team_id || ""), String(match.away_team_id || "")]).filter(Boolean)));
    const completedRegionMatches = regionMatches.filter((match) => matchCompleted(match, completed)).map(matchToResult);
    const rows = calculateStandings(teamIds, completedRegionMatches, teamNames);
    return `<section class="cup-group"><h3>${region}</h3>${standingsTable(rows, false)}</section>`;
  }).join("");

  panel.innerHTML = `
    <h2>local_cup</h2>
    <div class="cup-tabs">
      <button class="cup-tab ${activeTarget === "local-groups" ? "active" : ""}" data-cup-target="local-groups">조별 순위</button>
      <button class="cup-tab ${activeTarget === "local-bracket" ? "active" : ""}" data-cup-target="local-bracket">토너먼트</button>
    </div>
    <div class="cup-view" data-cup-view="local-groups" ${activeTarget === "local-groups" ? "" : "hidden"}>${groupsHtml || `<p class="pending">조별 경기가 없습니다.</p>`}</div>
    <div class="cup-view" data-cup-view="local-bracket" ${activeTarget === "local-bracket" ? "" : "hidden"}>${renderBracket(knockoutMatches, completed, teamNames, groupMatches)}</div>
  `;
}

function renderTournamentPanel(panel, title, payload, completed, teamNames) {
  const matches = Array.isArray(payload?.matches) ? payload.matches : [];
  const held = payload?.held !== false;
  panel.innerHTML = `
    <h2>${title}</h2>
    ${held ? renderBracket(matches, completed, teamNames) : `<p class="pending">이번 시즌에는 진행되지 않습니다.</p>`}
  `;
}

function extendAclTeamNames(teamNames, acl) {
  const participants = acl?.participants;
  if (!participants || typeof participants !== "object") return;
  for (const rows of Object.values(participants)) {
    if (!Array.isArray(rows)) continue;
    for (const row of rows) {
      const teamId = String(row?.team_id || "");
      const teamName = String(row?.team_name || teamId);
      if (teamId) teamNames.set(teamId, teamName);
    }
  }
}

function renderAclPanel(panel, league, acl, completed, teamNames) {
  const activeTarget = panel.dataset.activeCupTarget || `${league}-groups`;
  const matches = Array.isArray(acl?.matches) ? acl.matches : [];
  const participants = Array.isArray(acl?.participants?.[league]) ? acl.participants[league] : [];
  const groupMatches = matches.filter((match) => String(match.stage || "") === `${league}_group`);
  const knockoutMatches = matches.filter((match) => {
    const stage = String(match.stage || "");
    return stage.startsWith(`${league}_`) && stage !== `${league}_group`;
  });
  const groupNames = Array.from(new Set(groupMatches.map((match) => String(match.group || "")).filter(Boolean))).sort();
  const groupsHtml = groupNames.map((groupName) => {
    const matchesInGroup = groupMatches.filter((match) => String(match.group || "") === groupName);
    const teamIds = Array.from(new Set([
      ...participants
        .filter((row) => matchesInGroup.some((match) => String(match.home_team_id || "") === String(row.team_id || "") || String(match.away_team_id || "") === String(row.team_id || "")))
        .map((row) => String(row.team_id || "")),
      ...matchesInGroup.flatMap((match) => [String(match.home_team_id || ""), String(match.away_team_id || "")]),
    ].filter(Boolean)));
    const completedGroupMatches = matchesInGroup.filter((match) => matchCompleted(match, completed)).map(matchToResult);
    const groupRows = calculateStandings(teamIds, completedGroupMatches, teamNames);
    return `<section class="cup-group"><h3>Group ${groupName}</h3>${standingsTable(groupRows, false)}</section>`;
  }).join("");

  panel.innerHTML = `
    <h2>${league}</h2>
    <div class="cup-tabs">
      <button class="cup-tab ${activeTarget === `${league}-groups` ? "active" : ""}" data-cup-target="${league}-groups">조별리그</button>
      <button class="cup-tab ${activeTarget === `${league}-bracket` ? "active" : ""}" data-cup-target="${league}-bracket">토너먼트</button>
    </div>
    <div class="cup-view" data-cup-view="${league}-groups" ${activeTarget === `${league}-groups` ? "" : "hidden"}>${groupsHtml || `<p class="pending">조별리그 경기가 없습니다.</p>`}</div>
    <div class="cup-view" data-cup-view="${league}-bracket" ${activeTarget === `${league}-bracket` ? "" : "hidden"}>${renderBracket(knockoutMatches, completed, teamNames, groupMatches)}</div>
  `;
}

function wireTabs() {
  document.querySelectorAll(".cup-tab").forEach((button) => {
    button.addEventListener("click", () => {
      const panel = button.closest(".panel");
      if (!panel) return;
      panel.dataset.activeCupTarget = button.dataset.cupTarget || "";
      panel.querySelectorAll(".cup-tab").forEach((item) => item.classList.toggle("active", item === button));
      panel.querySelectorAll(".cup-view").forEach((view) => {
        view.hidden = view.dataset.cupView !== button.dataset.cupTarget;
      });
    });
  });
}

function guardStandings(feeds, teams, cups, replayStartedAt) {
  injectCupStyles();
  const completed = completedMatchIds(feeds, replayStartedAt);
  const completedFeeds = feeds.filter((feed) => completed.has(String(feed.match_id))).map(resultRow);
  const teamNames = new Map((Array.isArray(teams) ? teams : []).map((team) => [String(team.id), String(team.name || team.id)]));
  const allLeagueTeams = Array.from(teamNames.keys());
  extendAclTeamNames(teamNames, cups.acl);

  document.querySelectorAll("main.grid .panel").forEach((panel) => {
    const title = panel.querySelector("h2");
    if (!title) return;
    const competition = title.textContent.trim();
    if (!completedFeeds.length) {
      panel.querySelector("table")?.remove();
      panel.querySelectorAll(".cup-tabs, .cup-view").forEach((node) => node.remove());
      if (!panel.querySelector(".pending")) {
        panel.insertAdjacentHTML("beforeend", `<p class="pending">아직 경기가 시작되지 않았습니다.</p>`);
      }
      return;
    }
    if (competition === "local_cup") {
      renderLocalCupPanel(panel, cups.localCup, completed, teamNames);
      return;
    }
    if (competition === "championship") {
      renderTournamentPanel(panel, "championship", cups.championship, completed, teamNames);
      return;
    }
    if (competition === "fa_cup") {
      renderTournamentPanel(panel, "fa_cup", cups.faCup, completed, teamNames);
      return;
    }
    if (competition === "ACL1" || competition === "ACL2" || competition === "ACL3") {
      renderAclPanel(panel, competition, cups.acl, completed, teamNames);
      return;
    }
    const matches = completedFeeds.filter((match) => match.competition === competition);
    const teamIds = competition === "league"
      ? allLeagueTeams
      : Array.from(new Set(feeds
          .filter((feed) => String(feed.competition || "") === competition)
          .flatMap((feed) => [String(feed.home_team_id || ""), String(feed.away_team_id || "")])
          .filter(Boolean)));
    const rows = calculateStandings(teamIds, matches, teamNames);
    panel.querySelector("table")?.remove();
    panel.insertAdjacentHTML("beforeend", standingsTable(rows, competition !== "league" && competition !== "super_cup"));
  });
  wireTabs();
}

async function main() {
  const [season, serverReplayState, feeds, teams, localCup, championship, faCup, acl] = await Promise.all([
    fetch("./season.json", { cache: "no-store" }).then((r) => r.json()).catch(() => ({})),
    fetch("/api/replay-state", { cache: "no-store" }).then((r) => r.json()).catch(() => ({})),
    fetch("./live_feed.json", { cache: "no-store" }).then((r) => r.json()),
    fetch("./teams.json", { cache: "no-store" }).then((r) => r.json()).catch(() => []),
    fetch("./local_cup.json", { cache: "no-store" }).then((r) => r.json()).catch(() => ({})),
    fetch("./championship.json", { cache: "no-store" }).then((r) => r.json()).catch(() => ({})),
    fetch("./fa_cup.json", { cache: "no-store" }).then((r) => r.json()).catch(() => ({})),
    fetch("./acl.json", { cache: "no-store" }).then((r) => r.json()).catch(() => ({})),
  ]);
  const replayStartedAt = Date.parse(String(serverReplayState?.replay_started_at || season?.replay_started_at || season?.generated_at || ""));
  if (document.querySelector(".match")) guardCalendar(feeds, replayStartedAt);
  if (document.querySelector("main.grid")) guardStandings(feeds, teams, { localCup, championship, faCup, acl }, replayStartedAt);
  setInterval(() => {
    if (document.querySelector(".match")) guardCalendar(feeds, replayStartedAt);
    if (document.querySelector("main.grid")) guardStandings(feeds, teams, { localCup, championship, faCup, acl }, replayStartedAt);
  }, SYNC_TICK_SECONDS * 1000);
}

function selectChunkInfo(manifest, nowMs = Date.now()) {
  const chunks = Array.isArray(manifest?.chunks) ? manifest.chunks : [];
  if (!chunks.length) return null;
  let selected = chunks[0];
  for (const chunk of chunks) {
    const start = Date.parse(String(chunk.start_run_at || ""));
    if (Number.isFinite(start) && start <= nowMs) {
      selected = chunk;
    } else {
      break;
    }
  }
  return selected;
}

function selectTickFromChunk(chunkPayload, nowMs = Date.now()) {
  const ticks = Array.isArray(chunkPayload?.ticks) ? chunkPayload.ticks : [];
  if (!ticks.length) return null;
  let low = 0;
  let high = ticks.length - 1;
  let selected = 0;
  while (low <= high) {
    const mid = Math.floor((low + high) / 2);
    const runAt = Date.parse(String(ticks[mid]?.run_at || ""));
    if (!Number.isFinite(runAt) || runAt <= nowMs) {
      selected = mid;
      low = mid + 1;
    } else {
      high = mid - 1;
    }
  }
  return ticks[selected] || ticks[0];
}

function guardCalendarFromReplay(replay, snapshot) {
  const completed = new Set((replay?.completion_order || []).slice(0, Number(snapshot?.completed_count || 0)));
  const scheduleById = new Map((replay.schedule || []).map((match) => [String(match.match_id || ""), match]));
  document.querySelectorAll(".match").forEach((matchEl) => {
    const scoreEl = matchEl.querySelector(".score");
    if (!scoreEl) return;
    const matchId = String(matchEl.dataset.matchId || "");
    const match = scheduleById.get(matchId);
    if (!match || !completed.has(matchId)) {
      scoreEl.textContent = "예정";
      scoreEl.style.color = "#9aa3af";
      return;
    }
    scoreEl.textContent = `${Number(match.away_score || 0)} - ${Number(match.home_score || 0)}`;
    scoreEl.style.color = "";
  });
}

function renderReplayStandingsTable(rows, teamNames) {
  if (!rows || !rows.length) {
    return `<p class="pending">아직 반영된 경기가 없습니다.</p>`;
  }
  return standingsTable(rows.map((row) => ({
    rank: row.rank,
    team_name: teamNames.get(String(row.team_id || "")) || row.team_name || row.team_id,
    played: row.played,
    wins: row.wins,
    draws: row.draws,
    losses: row.losses,
    gf: row.goals_for ?? row.gf ?? 0,
    ga: row.goals_against ?? row.ga ?? 0,
    gd: row.goal_difference ?? row.gd ?? 0,
    points: row.points,
  })), false);
}

function guardStandingsFromReplay(snapshot, teams) {
  const teamNames = new Map((Array.isArray(teams) ? teams : []).map((team) => [String(team.id), String(team.name || team.id)]));
  document.querySelectorAll("main.grid .panel").forEach((panel) => {
    const title = panel.querySelector("h2");
    if (!title) return;
    const competition = title.textContent.trim();
    panel.querySelector("table")?.remove();
    panel.querySelectorAll(".cup-tabs, .cup-view, .pending").forEach((node) => node.remove());
    if (competition === "league") {
      panel.insertAdjacentHTML("beforeend", renderReplayStandingsTable(snapshot?.standings?.league || [], teamNames));
    } else {
      panel.insertAdjacentHTML("beforeend", `<p class="pending">이 페이지는 현재 tick JSON 기준 리그 순위를 표시합니다.</p>`);
    }
  });
}

function guardCalendarFromReplay(replay, snapshot) {
  const completedCount = Number(snapshot?.completed_count || 0);
  const completed = new Set((replay?.completion_order || []).slice(0, completedCount));
  const scheduleById = new Map((replay.schedule || []).map((match) => [String(match.match_id || ""), match]));
  document.querySelectorAll(".match").forEach((matchEl) => {
    const scoreEl = matchEl.querySelector(".score");
    if (!scoreEl) return;
    const matchId = String(matchEl.dataset.matchId || "");
    const match = scheduleById.get(matchId);
    const revealed = match && completedCount >= Number(match.reveal_after_count || 0);
    matchEl.hidden = !revealed;
    if (!revealed) return;
    if (!match || !completed.has(matchId)) {
      scoreEl.textContent = "Scheduled";
      scoreEl.style.color = "#9aa3af";
      return;
    }
    scoreEl.textContent = `${Number(match.away_score || 0)} - ${Number(match.home_score || 0)}`;
    scoreEl.style.color = "";
  });
  document.querySelectorAll("details.fold").forEach((fold) => {
    const visibleMatches = Array.from(fold.querySelectorAll(".match")).filter((match) => !match.hidden);
    fold.hidden = visibleMatches.length === 0;
  });
}

async function main() {
  const [manifest, teams] = await Promise.all([
    fetch("./replay_manifest.json", { cache: "no-store" }).then((r) => r.json()),
    fetch("./teams.json", { cache: "no-store" }).then((r) => r.json()).catch(() => []),
  ]);
  const [schedule, completionOrder] = await Promise.all([
    fetch(`./${manifest.schedule_path || "replay_schedule.json"}`, { cache: "no-store" }).then((r) => r.json()),
    fetch(`./${manifest.completion_order_path || "replay_completion_order.json"}`, { cache: "no-store" }).then((r) => r.json()),
  ]);
  const replay = { ...manifest, schedule, completion_order: completionOrder };
  const chunkCache = new Map();
  async function loadSnapshot() {
    const chunkInfo = selectChunkInfo(manifest);
    if (!chunkInfo) return null;
    if (!chunkCache.has(chunkInfo.path)) {
      chunkCache.set(chunkInfo.path, fetch(`./${chunkInfo.path}`, { cache: "no-store" }).then((r) => r.json()));
    }
    const chunkPayload = await chunkCache.get(chunkInfo.path);
    return selectTickFromChunk(chunkPayload);
  }
  const render = async () => {
    const snapshot = await loadSnapshot();
    if (document.querySelector(".match")) guardCalendarFromReplay(replay, snapshot);
    if (document.querySelector("main.grid")) guardStandingsFromReplay(snapshot, teams);
  };
  await render();
  setInterval(() => render().catch((err) => console.error(err)), Number(replay.tick_seconds || 2) * 1000);
}

main().catch((err) => console.error(err));
