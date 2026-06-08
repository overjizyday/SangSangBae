const DAY_ORDER = ["월", "화", "수", "목", "금", "토", "일"];
const WEEKDAY_ORDER = Object.fromEntries(DAY_ORDER.map((day, index) => [day, index]));
const COMPETITION_ORDER = { acl: 0, local_cup: 1, championship: 2, fa_cup: 3, super_cup: 4, league: 5 };
const ACTION_CODE_TO_LABEL = {
  12: "H1", 13: "H1", 14: "H2", 15: "H2", 16: "H2", 17: "H3", 18: "H3", 19: "H3",
  21: "K", 23: "K", 24: "2B1", 25: "K", 26: "2B1", 27: "K", 28: "2B2", 29: "K",
  31: "GO", 32: "GO", 34: "GO", 35: "GO", 36: "GO", 37: "DO", 38: "DO", 39: "DO",
  41: "FO", 42: "FO", 43: "FO", 45: "SF1", 46: "SF1", 47: "SF2", 48: "SF2", 49: "TO",
  51: "B", 52: "B", 53: "B", 54: "HP", 56: "SB", 57: "SB", 58: "SB", 59: "SB",
  61: "H1", 62: "H2", 63: "H2", 64: "H3", 65: "H3", 67: "2B1", 68: "2B2", 69: "HR",
  71: "K", 72: "K", 73: "K", 74: "K", 75: "K", 76: "K", 78: "K", 79: "K",
  81: "FO", 82: "FO", 83: "FO", 84: "SF1", 85: "SF1", 86: "SF2", 87: "SF2", 89: "HR",
  91: "GO", 92: "GO", 93: "GO", 94: "GO", 95: "DO", 96: "DO", 97: "E", 98: "3B",
};
const WEEK_ANCHOR_WEEK = 7;
const WEEK_ANCHOR_DAY_INDEX = WEEKDAY_ORDER["일"];
const WEEK_ANCHOR_MONTH_DAY = [5, 5];

const stateKey = `live-replay-state:${location.pathname}`;
const foldKey = `live-fold:${location.pathname}`;

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function looksLikeCode(name) {
  const value = String(name || "").trim();
  return /^[A-Za-z0-9_]+$/.test(value) || value.includes("_FC") || value.startsWith("T");
}

function displayTeamName(teamId, rawName, teamNames) {
  if (rawName && rawName !== teamId && !looksLikeCode(rawName)) {
    return rawName;
  }
  return teamNames.get(teamId) || rawName || teamId;
}

function seasonDayDate(year, week, day) {
  const anchor = new Date(Date.UTC(year, WEEK_ANCHOR_MONTH_DAY[0] - 1, WEEK_ANCHOR_MONTH_DAY[1]));
  const dayIndex = WEEKDAY_ORDER[day] ?? 0;
  const deltaDays = (week - WEEK_ANCHOR_WEEK) * 7 + (dayIndex - WEEK_ANCHOR_DAY_INDEX);
  anchor.setUTCDate(anchor.getUTCDate() + deltaDays);
  return anchor;
}

function formatSeasonDateLabel(year, week, day) {
  if (week <= 0) {
    return `${year} / Season complete`;
  }
  const current = seasonDayDate(year, week, day);
  return `${current.toISOString().slice(0, 10)} | W${week} / ${day}`;
}

function loadSavedState() {
  try {
    const raw = localStorage.getItem(stateKey);
    return raw ? JSON.parse(raw) : null;
  } catch (err) {
    return null;
  }
}

function saveState(state) {
  try {
    localStorage.setItem(stateKey, JSON.stringify(state));
  } catch (err) {}
}

function loadOpenFoldKeys() {
  try {
    const raw = localStorage.getItem(foldKey);
    return raw ? new Set(JSON.parse(raw)) : new Set();
  } catch (err) {
    return new Set();
  }
}

function saveOpenFoldKeys() {
  const keys = Array.from(document.querySelectorAll("details[data-fold-key][open]"))
    .map((el) => el.dataset.foldKey)
    .filter(Boolean);
  try {
    localStorage.setItem(foldKey, JSON.stringify(keys));
  } catch (err) {}
}

function restoreOpenFoldKeys() {
  const keys = loadOpenFoldKeys();
  document.querySelectorAll("details[data-fold-key]").forEach((el) => {
    if (keys.has(el.dataset.foldKey)) {
      el.open = true;
    }
  });
}

function buildTeamNames(teams, competitions) {
  const teamNames = new Map(teams.map((team) => [team.id, team.name]));
  for (const competition of competitions) {
    const participants = competition?.participants;
    if (!participants || typeof participants !== "object") continue;
    for (const leagueItems of Object.values(participants)) {
      if (!Array.isArray(leagueItems)) continue;
      for (const item of leagueItems) {
        if (!item || typeof item !== "object") continue;
        const teamId = String(item.team_id || "").trim();
        if (!teamId) continue;
        teamNames.set(teamId, displayTeamName(teamId, String(item.team_name || teamId), teamNames));
      }
    }
  }
  return teamNames;
}

function groupFeedsByDay(feeds) {
  const sorted = [...feeds].sort((a, b) => {
    const aw = Number(a.week || 0);
    const bw = Number(b.week || 0);
    if (aw !== bw) return aw - bw;
    const ad = WEEKDAY_ORDER[String(a.day || "")] ?? 99;
    const bd = WEEKDAY_ORDER[String(b.day || "")] ?? 99;
    if (ad !== bd) return ad - bd;
    const ac = COMPETITION_ORDER[String(a.competition || "")] ?? 99;
    const bc = COMPETITION_ORDER[String(b.competition || "")] ?? 99;
    if (ac !== bc) return ac - bc;
    return String(a.match_id || "").localeCompare(String(b.match_id || ""));
  });

  const groups = new Map();
  for (const feed of sorted) {
    const key = `${Number(feed.week || 0)}|${String(feed.day || "")}`;
    if (!groups.has(key)) {
      groups.set(key, { week: Number(feed.week || 0), day: String(feed.day || ""), matches: [] });
    }
    groups.get(key).matches.push(feed);
  }
  return Array.from(groups.values());
}

function eventAt(feed, index) {
  const events = Array.isArray(feed.events) ? feed.events : [];
  if (index < 0 || index >= events.length) return null;
  const item = events[index];
  return item && typeof item === "object" ? item : null;
}

function formatBases(value) {
  const normalized = String(value || "").trim().toLowerCase();
  return normalized && normalized !== "-" && normalized !== "empty" && normalized !== "none" ? value : "empty";
}

function basesState(value) {
  const normalized = String(value || "").trim().toLowerCase();
  if (!normalized || normalized === "-" || normalized === "empty" || normalized === "none") {
    return [false, false, false];
  }
  return [
    normalized.includes("1") || normalized.includes("first") || normalized.includes("1b"),
    normalized.includes("2") || normalized.includes("second") || normalized.includes("2b"),
    normalized.includes("3") || normalized.includes("third") || normalized.includes("3b"),
  ];
}

function fallbackEventCode(eventName) {
  const mapping = { out: 21, walk: 51, single: 12, double: 14, triple: 17, home_run: 69, coinflip_run: 69 };
  return mapping[eventName] ?? null;
}

function currentSnapshot(feed, progress) {
  const events = Array.isArray(feed.events) ? feed.events : [];
  if (!events.length) {
    return {
      inning: 1, half: "top", outs: 0, bases: "-",
      last_event: "pregame", plate_appearance: null, event_code: null,
      score_away: Number(feed.away_score || 0), score_home: Number(feed.home_score || 0),
      done: true,
    };
  }
  if (progress <= 0) {
    const first = eventAt(feed, 0) || {};
    return {
      inning: Number(first.inning || 1),
      half: String(first.half || "top"),
      outs: 0,
      bases: "empty",
      last_event: "pregame",
      plate_appearance: null,
      event_code: null,
      score_away: Number(first.score_away_before ?? feed.away_score ?? 0),
      score_home: Number(first.score_home_before ?? feed.home_score ?? 0),
      done: false,
    };
  }
  const last = eventAt(feed, Math.min(progress, events.length) - 1) || {};
  const done = progress >= events.length;
  if (!done && Number(last.outs_after || 0) >= 3) {
    const inning = Number(last.inning || 1);
    const half = String(last.half || "top");
    return {
      inning: half === "bottom" ? inning + 1 : inning,
      half: half === "bottom" ? "top" : "bottom",
      outs: 0,
      bases: "empty",
      last_event: String(last.event || "play"),
      plate_appearance: last.plate_appearance ?? null,
      event_code: last.event_code ?? fallbackEventCode(String(last.event || "")),
      score_away: Number(last.score_away_after ?? feed.away_score ?? 0),
      score_home: Number(last.score_home_after ?? feed.home_score ?? 0),
      done: false,
    };
  }
  return {
    inning: Number(last.inning || 1),
    half: String(last.half || "top"),
    outs: Number(last.outs_after || 0),
    bases: formatBases(String(last.bases_after || "empty")),
    last_event: String(last.event || "play"),
    plate_appearance: last.plate_appearance ?? null,
    event_code: last.event_code ?? fallbackEventCode(String(last.event || "")),
    score_away: Number(last.score_away_after ?? feed.away_score ?? 0),
    score_home: Number(last.score_home_after ?? feed.home_score ?? 0),
    done,
  };
}

function renderDiamond(bases) {
  const [on1, on2, on3] = basesState(bases);
  return `
    <div class="diamond">
      <div class="base b2 ${on2 ? "on" : ""}"></div>
      <div class="base b3 ${on3 ? "on" : ""}"></div>
      <div class="base b1 ${on1 ? "on" : ""}"></div>
      <div class="base home"></div>
    </div>
  `;
}

function formatLastPlay(snapshot, debug) {
  if (snapshot.last_event === "pregame") return "pregame";
  if (debug && snapshot.event_code != null) {
    const label = ACTION_CODE_TO_LABEL[Number(snapshot.event_code)] || String(snapshot.last_event).toUpperCase();
    return `${snapshot.event_code} ${label}`;
  }
  return snapshot.last_event;
}

function renderMatchCard(feed, snapshot, teamNames, index, debug) {
  const home = displayTeamName(String(feed.home_team_id || ""), teamNames.get(String(feed.home_team_id || "")) || String(feed.home_team_id || ""), teamNames);
  const away = displayTeamName(String(feed.away_team_id || ""), teamNames.get(String(feed.away_team_id || "")) || String(feed.away_team_id || ""), teamNames);
  const badgeClass = snapshot.done ? "over" : (String(snapshot.half) === "top" ? "top" : "bot");
  const badgeText = snapshot.done ? "Complete" : `${snapshot.inning} ${String(snapshot.half).charAt(0).toUpperCase() + String(snapshot.half).slice(1)}`;
  const outdots = Array.from({ length: Math.min(Number(snapshot.outs || 0), 3) }, () => '<span class="outdot"></span>').join("");
  const lastPlay = escapeHtml(formatLastPlay(snapshot, debug));
  return `
    <div class="card">
      <div class="header">
        <div>Game ${index + 1}</div>
        <div class="badge ${badgeClass}">${escapeHtml(badgeText)}</div>
      </div>
      <div class="teams-row">
        ${renderTeamBlock(away)}
        <div class="score-center"><span class="score-away">${escapeHtml(snapshot.score_away)}</span><span class="score-sep">:</span><span class="score-home">${escapeHtml(snapshot.score_home)}</span></div>
        ${renderTeamBlock(home)}
      </div>
      <div class="row"><div class="meta">Outs</div><div class="outs">${outdots}</div></div>
      ${renderDiamond(String(snapshot.bases))}
      <div class="lastact">Last play: ${lastPlay}</div>
    </div>
  `;
}

function renderTeamBlock(name) {
  return `<div class="team-block"><div class="team-name">${escapeHtml(name)}</div></div>`;
}

function calculateStandings(teamList, matches) {
  const names = new Map(teamList.map((team) => [team.id, team.name]));
  const table = new Map();
  for (const team of teamList) {
    table.set(team.id, {
      team_id: team.id,
      team_name: team.name,
      played: 0,
      wins: 0,
      draws: 0,
      losses: 0,
      goals_for: 0,
      goals_against: 0,
      goal_difference: 0,
      points: 0,
    });
  }

  for (const match of matches) {
    if (match.home_score == null || match.away_score == null) continue;
    if (!table.has(match.home_team_id) || !table.has(match.away_team_id)) continue;
    const home = table.get(match.home_team_id);
    const away = table.get(match.away_team_id);
    home.played += 1; away.played += 1;
    home.goals_for += Number(match.home_score); home.goals_against += Number(match.away_score);
    away.goals_for += Number(match.away_score); away.goals_against += Number(match.home_score);
    if (Number(match.home_score) > Number(match.away_score)) {
      home.wins += 1; away.losses += 1; home.points += 3;
    } else if (Number(match.home_score) < Number(match.away_score)) {
      away.wins += 1; home.losses += 1; away.points += 3;
    } else {
      home.draws += 1; away.draws += 1; home.points += 1; away.points += 1;
    }
  }

  const rows = Array.from(table.values()).map((row) => ({
    ...row,
    goal_difference: row.goals_for - row.goals_against,
    team_name: names.get(row.team_id) || row.team_name || row.team_id,
  }));

  rows.sort((a, b) => (
    (b.points - a.points) ||
    (b.goal_difference - a.goal_difference) ||
    (b.goals_for - a.goals_for) ||
    (a.goals_against - b.goals_against) ||
    String(a.team_name).localeCompare(String(b.team_name), "ko")
  ));

  rows.forEach((row, index) => { row.rank = index + 1; });
  return rows;
}

function renderStandingsTable(rows, teamNames, compact = false) {
  if (!rows || !rows.length) {
    return `<p class="empty">No standings available.</p>`;
  }
  const columns = compact
    ? ["#", "Team", "P", "W", "D", "L", "GF", "GA", "GD", "Pts"]
    : ["#", "Team", "P", "W", "D", "L", "GF", "GA", "GD", "Pts"];
  const body = rows.map((row) => `
    <tr>
      <td>${escapeHtml(row.rank)}</td>
      <td>${escapeHtml(displayTeamName(row.team_id, row.team_name, teamNames))}</td>
      <td>${escapeHtml(row.played)}</td>
      <td>${escapeHtml(row.wins)}</td>
      <td>${escapeHtml(row.draws)}</td>
      <td>${escapeHtml(row.losses)}</td>
      <td>${escapeHtml(row.goals_for ?? row.gf ?? 0)}</td>
      <td>${escapeHtml(row.goals_against ?? row.ga ?? 0)}</td>
      <td>${escapeHtml(row.goal_difference ?? row.gd ?? 0)}</td>
      <td>${escapeHtml(row.points)}</td>
    </tr>
  `).join("");
  return `
    <table class="${compact ? "compact" : ""}">
      <thead>
        <tr>${columns.map((col) => `<th>${escapeHtml(col)}</th>`).join("")}</tr>
      </thead>
      <tbody>${body}</tbody>
    </table>
  `;
}

function renderFold(title, content, open = false, key = "") {
  const openAttr = open ? " open" : "";
  const dataAttr = key ? ` data-fold-key="${escapeHtml(key)}"` : "";
  return `<details class="fold"${openAttr}${dataAttr}><summary>${escapeHtml(title)}</summary>${content}</details>`;
}

function renderSuperCupStandings(superCup, completedMatches, teamNames) {
  if (!superCup || !superCup.entrants || !Array.isArray(superCup.entrants) || !superCup.entrants.length) {
    return `<p class="empty">No standings available.</p>`;
  }
  const activeMatches = completedMatches.filter((match) => match.competition === "super_cup");
  const participantIds = superCup.entrants.map((row) => String(row.team_id || "")).filter(Boolean);
  const subset = Array.from(new Map(participantIds.map((id) => [id, { id, name: teamNames.get(id) || id }])).values());
  const basePoints = new Map(superCup.entrants.map((row) => [String(row.team_id || ""), Number(row.points || 0)]));
  const names = new Map(superCup.entrants.map((row) => [String(row.team_id || ""), String(row.team_name || row.team_id || "")]));
  const standings = calculateStandings(subset, activeMatches).map((row) => ({
    ...row,
    points: row.points + (basePoints.get(row.team_id) || 0),
    team_name: names.get(row.team_id) || row.team_name,
  }));
  standings.sort((a, b) => (
    (b.points - a.points) ||
    (b.goal_difference - a.goal_difference) ||
    (b.goals_for - a.goals_for) ||
    (a.goals_against - b.goals_against) ||
    String(a.team_name).localeCompare(String(b.team_name), "ko")
  ));
  standings.forEach((row, index) => { row.rank = index + 1; });
  return renderStandingsTable(standings, teamNames, true);
}

function isCompetitionComplete(feeds, progressByMatch, competition) {
  return feeds
    .filter((feed) => String(feed.competition || "") === competition)
    .every((feed) => Number(progressByMatch[feed.match_id] || 0) >= (Array.isArray(feed.events) ? feed.events.length : 0));
}

function buildCompletedMatches(feeds, progressByMatch) {
  return feeds
    .filter((feed) => Number(progressByMatch[feed.match_id] || 0) >= (Array.isArray(feed.events) ? feed.events.length : 0))
    .map((feed) => ({
      competition: String(feed.competition || ""),
      stage: String(feed.stage || ""),
      round: feed.round,
      week: Number(feed.week || 0),
      day: String(feed.day || ""),
      match_id: String(feed.match_id || ""),
      home_team_id: String(feed.home_team_id || ""),
      away_team_id: String(feed.away_team_id || ""),
      home_score: Number(feed.home_score || 0),
      away_score: Number(feed.away_score || 0),
    }));
}

function renderApp({
  season,
  teams,
  feeds,
  superCup,
  state,
  groups,
  teamNames,
}) {
  const app = document.getElementById("app");
  const subtitle = document.getElementById("subtitle");
  const currentGroup = groups[state.groupIndex] || null;
  const currentLabel = currentGroup ? `W${currentGroup.week} / ${currentGroup.day}` : "Not started";
  subtitle.textContent = `Virtual date: ${currentGroup ? formatSeasonDateLabel(Number(season.year || 0), currentGroup.week, currentGroup.day) : `${season.year || ""} / Not started`} | Current day: ${currentLabel}`;

  const cards = currentGroup
    ? currentGroup.matches.map((feed, index) => {
        const progress = Number(state.progressByMatch[feed.match_id] || 0);
        const snapshot = currentSnapshot(feed, progress);
        return renderMatchCard(feed, snapshot, teamNames, index, Boolean(state.debug));
      }).join("")
    : `<p class="empty">No active matches.</p>`;

  const completedMatches = buildCompletedMatches(feeds, state.progressByMatch);
  const leagueRows = calculateStandings(
    teams,
    completedMatches.filter((match) => match.competition === "league")
  );
  const superCupHtml = renderSuperCupStandings(superCup, completedMatches, teamNames);
  const futureGroups = groups.slice(state.groupIndex + 1, state.groupIndex + 7);
  const upcomingHtml = futureGroups.length
    ? futureGroups.map((group) => `<li>W${group.week} / ${group.day}</li>`).join("")
    : `<li>Season complete.</li>`;

  const leagueSection = `<div class="standings-main"><h3 class="subsection-title">리그 순위</h3>${renderStandingsTable(leagueRows, teamNames)}</div>`;
  const superCupSection = renderFold("슈퍼컵", superCupHtml, false, "standings-super_cup");

  app.innerHTML = `
    <section class="panel">
      <h2 class="section-title">Matches This Day</h2>
      <div class="matches"><div class="board"><div class="grid">${cards}</div></div></div>
    </section>
    <aside class="panel aside">
      <h2 class="section-title">Standings</h2>
      ${leagueSection}
      ${superCupSection}
      <h2 class="section-title" style="margin-top:18px;">Upcoming</h2>
      <ul>${upcomingHtml}</ul>
      <div style="margin-top:18px; color: var(--muted); font-size: 12px;">
        Other views: <a class="link" href="./calendar.html">calendar</a> · <a class="link" href="./standings.html">standings</a>
      </div>
    </aside>
  `;

  restoreOpenFoldKeys();
  document.querySelectorAll("details[data-fold-key]").forEach((el) => {
    el.addEventListener("toggle", saveOpenFoldKeys);
  });
}

function advanceState(state, groups) {
  if (state.paused || state.groupIndex >= groups.length) return false;
  const group = groups[state.groupIndex];
  let advanced = false;
  let allDone = true;
  for (const feed of group.matches) {
    const progress = Number(state.progressByMatch[feed.match_id] || 0);
    const eventCount = Array.isArray(feed.events) ? feed.events.length : 0;
    if (progress < eventCount) {
      state.progressByMatch[feed.match_id] = progress + 1;
      advanced = true;
      allDone = false;
    }
  }
  if (allDone) {
    state.groupIndex += 1;
    return true;
  }
  if (advanced) {
    state.tickCount += 1;
  }
  return advanced;
}

function groupDuration(group) {
  const maxEvents = Math.max(
    0,
    ...group.matches.map((feed) => (Array.isArray(feed.events) ? feed.events.length : 0))
  );
  return maxEvents + 1;
}

function replayTotalTicks(groups) {
  return groups.reduce((total, group) => total + groupDuration(group), 0);
}

function syncedReplayState(groups, feeds, tickSeconds, startMs = Date.now(), nowMs = Date.now()) {
  const progressByMatch = Object.fromEntries(feeds.map((feed) => [feed.match_id, 0]));
  const totalTicks = replayTotalTicks(groups);
  if (!groups.length || totalTicks <= 0) {
    return { groupIndex: 0, tickCount: 0, debug: false, paused: false, progressByMatch };
  }

  const elapsedTicks = Math.max(0, Math.floor((nowMs - startMs) / (tickSeconds * 1000)));
  if (elapsedTicks <= 0) {
    return {
      groupIndex: -1,
      tickCount: 0,
      debug: false,
      paused: false,
      progressByMatch,
    };
  }
  if (elapsedTicks >= totalTicks) {
    groups.forEach((group) => {
      group.matches.forEach((feed) => {
        progressByMatch[feed.match_id] = Array.isArray(feed.events) ? feed.events.length : 0;
      });
    });
    return {
      groupIndex: groups.length,
      tickCount: totalTicks,
      debug: false,
      paused: false,
      progressByMatch,
    };
  }

  let tick = elapsedTicks;
  let groupIndex = 0;
  for (let index = 0; index < groups.length; index += 1) {
    const duration = groupDuration(groups[index]);
    if (tick < duration) {
      groupIndex = index;
      break;
    }
    tick -= duration;
  }

  groups.slice(0, groupIndex).forEach((group) => {
    group.matches.forEach((feed) => {
      progressByMatch[feed.match_id] = Array.isArray(feed.events) ? feed.events.length : 0;
    });
  });

  const currentGroup = groups[groupIndex] || null;
  if (currentGroup) {
    currentGroup.matches.forEach((feed) => {
      const eventCount = Array.isArray(feed.events) ? feed.events.length : 0;
      progressByMatch[feed.match_id] = Math.min(tick, eventCount);
    });
  }

  return {
    groupIndex,
    tickCount: tick,
    debug: false,
    paused: false,
    progressByMatch,
  };
}

async function main() {
  const [season, serverReplayState, teams, feeds, superCup, localCup, championship, acl] = await Promise.all([
    fetch("./season.json").then((r) => r.json()),
    fetch("/api/replay-state", { cache: "no-store" }).then((r) => r.json()).catch(() => ({})),
    fetch("./teams.json").then((r) => r.json()),
    fetch("./live_feed.json").then((r) => r.json()),
    fetch("./super_cup.json").then((r) => r.json()).catch(() => ({})),
    fetch("./local_cup.json").then((r) => r.json()).catch(() => ({})),
    fetch("./championship.json").then((r) => r.json()).catch(() => ({})),
    fetch("./acl.json").then((r) => r.json()).catch(() => ({})),
  ]);

  const groups = groupFeedsByDay(feeds);
  const tickSeconds = 2;
  const saved = loadSavedState() || {};
  const replayStartedAt = Date.parse(String(serverReplayState?.replay_started_at || season?.replay_started_at || season?.generated_at || ""));
  const startMs = Number.isFinite(replayStartedAt) ? replayStartedAt : Date.now();
  let state = { ...syncedReplayState(groups, feeds, tickSeconds, startMs), debug: Boolean(saved.debug), paused: false };
  let pausedState = null;
  const teamNames = buildTeamNames(teams, [superCup, localCup, championship, acl].filter((item) => item && typeof item === "object"));

  const toggleButton = document.getElementById("togglePlay");
  const resetButton = document.getElementById("resetReplay");

  function persist() {
    saveState({
      debug: state.debug,
    });
  }

  toggleButton.addEventListener("click", () => {
    if (pausedState) {
      pausedState = null;
      state = { ...syncedReplayState(groups, feeds, tickSeconds, startMs), debug: state.debug, paused: false };
      toggleButton.textContent = "Pause";
    } else {
      pausedState = JSON.parse(JSON.stringify(state));
      pausedState.paused = true;
      toggleButton.textContent = "Live";
    }
    persist();
    renderApp({ season, teams, feeds, superCup, state: pausedState || state, groups, teamNames });
  });

  resetButton.addEventListener("click", () => {
    pausedState = null;
    state = { ...syncedReplayState(groups, feeds, tickSeconds, startMs), debug: state.debug, paused: false };
    toggleButton.textContent = "Pause";
    persist();
    renderApp({ season, teams, feeds, superCup, state, groups, teamNames });
  });

  renderApp({ season, teams, feeds, superCup, state, groups, teamNames });
  persist();

  setInterval(() => {
    if (!pausedState) {
      state = { ...syncedReplayState(groups, feeds, tickSeconds, startMs), debug: state.debug, paused: false };
      renderApp({ season, teams, feeds, superCup, state, groups, teamNames });
      persist();
    }
  }, tickSeconds * 1000);

  window.addEventListener("pagehide", persist);
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

function upcomingScheduleItemsFromSnapshot(replay, snapshot, limit = 7) {
  const completedCount = Number(snapshot?.completed_count || 0);
  const completed = new Set((replay?.completion_order || []).slice(0, completedCount));
  const active = new Set((snapshot?.active_matches || []).map((match) => String(match.match_id || "")));
  const rows = [];
  for (const match of replay?.schedule || []) {
    const matchId = String(match.match_id || "");
    if (!matchId || completed.has(matchId) || active.has(matchId)) continue;
    if (completedCount < Number(match.reveal_after_count || 0)) continue;
    rows.push(match);
    if (rows.length >= limit) break;
  }
  return rows;
}

function renderApp({ season, teams, replay, snapshot, teamNames }) {
  const app = document.getElementById("app");
  const subtitle = document.getElementById("subtitle");
  const currentLabel = snapshot && snapshot.week ? `W${snapshot.week} / ${snapshot.day}` : "Not started";
  const runAt = snapshot?.run_at ? new Date(snapshot.run_at) : null;
  const runAtText = runAt && Number.isFinite(runAt.getTime()) ? runAt.toLocaleString() : "";
  subtitle.textContent = `Virtual date: ${snapshot?.week ? formatSeasonDateLabel(Number(season.year || 0), Number(snapshot.week || 0), String(snapshot.day || "")) : `${season.year || ""} / Not started`} | Current day: ${currentLabel} | Tick ${snapshot?.tick ?? 0} @ ${runAtText}`;

  const cards = snapshot?.active_matches?.length
    ? snapshot.active_matches.map((match, index) => renderMatchCard(match, match.snapshot || {}, teamNames, index, false)).join("")
    : `<p class="empty">No active matches.</p>`;
  const leagueRows = snapshot?.standings?.league || calculateStandings(teams, []);
  const upcoming = upcomingScheduleItemsFromSnapshot(replay, snapshot);
  const upcomingHtml = upcoming.length
    ? upcoming.map((match) => `<li>W${escapeHtml(match.week)} / ${escapeHtml(match.day)} · ${escapeHtml(match.competition)} · ${escapeHtml(displayTeamName(match.away_team_id, teamNames.get(match.away_team_id), teamNames))} @ ${escapeHtml(displayTeamName(match.home_team_id, teamNames.get(match.home_team_id), teamNames))}</li>`).join("")
    : `<li>Season complete.</li>`;
  const leagueSection = `<div class="standings-main"><h3 class="subsection-title">League Standings</h3>${renderStandingsTable(leagueRows, teamNames)}</div>`;

  app.innerHTML = `
    <section class="panel">
      <h2 class="section-title">Matches This Day</h2>
      <div class="matches"><div class="board"><div class="grid">${cards}</div></div></div>
    </section>
    <aside class="panel aside">
      <h2 class="section-title">Standings</h2>
      ${leagueSection}
      <h2 class="section-title" style="margin-top:18px;">Upcoming</h2>
      <ul>${upcomingHtml}</ul>
      <div style="margin-top:18px; color: var(--muted); font-size: 12px;">
        Other views: <a class="link" href="./calendar.html">calendar</a> · <a class="link" href="./standings.html">standings</a>
      </div>
    </aside>
  `;
}

async function main() {
  const [season, manifest, teams, superCup, localCup, championship, acl] = await Promise.all([
    fetch("./season.json").then((r) => r.json()),
    fetch("./replay_manifest.json", { cache: "no-store" }).then((r) => r.json()),
    fetch("./teams.json").then((r) => r.json()),
    fetch("./super_cup.json").then((r) => r.json()).catch(() => ({})),
    fetch("./local_cup.json").then((r) => r.json()).catch(() => ({})),
    fetch("./championship.json").then((r) => r.json()).catch(() => ({})),
    fetch("./acl.json").then((r) => r.json()).catch(() => ({})),
  ]);
  const [schedule, completionOrder] = await Promise.all([
    fetch(`./${manifest.schedule_path || "replay_schedule.json"}`, { cache: "no-store" }).then((r) => r.json()),
    fetch(`./${manifest.completion_order_path || "replay_completion_order.json"}`, { cache: "no-store" }).then((r) => r.json()),
  ]);
  const replay = { ...manifest, schedule, completion_order: completionOrder };
  const teamNames = buildTeamNames(teams, [superCup, localCup, championship, acl].filter((item) => item && typeof item === "object"));
  const chunkCache = new Map();
  async function loadCurrentSnapshot() {
    const chunkInfo = selectChunkInfo(manifest);
    if (!chunkInfo) return null;
    if (!chunkCache.has(chunkInfo.path)) {
      chunkCache.set(chunkInfo.path, fetch(`./${chunkInfo.path}`, { cache: "no-store" }).then((r) => r.json()));
    }
    const chunkPayload = await chunkCache.get(chunkInfo.path);
    return selectTickFromChunk(chunkPayload);
  }
  let snapshot = await loadCurrentSnapshot();
  let pausedSnapshot = null;
  const toggleButton = document.getElementById("togglePlay");
  const resetButton = document.getElementById("resetReplay");

  toggleButton.addEventListener("click", () => {
    if (pausedSnapshot) {
      pausedSnapshot = null;
      toggleButton.textContent = "Pause";
      loadCurrentSnapshot().then((nextSnapshot) => {
        snapshot = nextSnapshot;
        renderApp({ season, teams, replay, snapshot, teamNames });
      }).catch((err) => console.error(err));
      return;
    } else {
      pausedSnapshot = JSON.parse(JSON.stringify(snapshot));
      toggleButton.textContent = "Live";
    }
    renderApp({ season, teams, replay, snapshot: pausedSnapshot || snapshot, teamNames });
  });

  resetButton.addEventListener("click", () => {
    pausedSnapshot = replay.ticks?.[0] || null;
    toggleButton.textContent = "Live";
    renderApp({ season, teams, replay, snapshot: pausedSnapshot || snapshot, teamNames });
  });

  renderApp({ season, teams, replay, snapshot, teamNames });
  setInterval(() => {
    if (!pausedSnapshot) {
      loadCurrentSnapshot().then((nextSnapshot) => {
        snapshot = nextSnapshot;
        renderApp({ season, teams, replay, snapshot, teamNames });
      }).catch((err) => console.error(err));
    }
  }, Number(replay.tick_seconds || 2) * 1000);
}

main().catch((err) => {
  const app = document.getElementById("app");
  if (app) {
    app.innerHTML = `<section class="panel"><h2 class="section-title">Failed to load replay</h2><p class="empty">${escapeHtml(err.message || err)}</p></section>`;
  }
  console.error(err);
});
