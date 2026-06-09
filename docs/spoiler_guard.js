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

function rankStandingsRows(rows) {
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

function knockoutStageOrder(stage) {
  const lower = String(stage || "").toLowerCase();
  if (lower.includes("preliminary")) return 0;
  if (lower === "po" || lower === "regional_po" || lower.endsWith("_po")) return 1;
  if (/^r\d+$/.test(lower)) return 2;
  if (lower.includes("r16")) return 3;
  if (lower.includes("qf")) return 4;
  if (lower.includes("sf")) return 5;
  if (lower.includes("final")) return 6;
  return 9;
}

function matchExecutionKey(match) {
  return [
    Number(match.week || 0),
    WEEKDAY_ORDER_SYNC[String(match.day || "")] ?? 99,
    Number(match.match_no || 0),
    Number(match.leg || 0),
    String(match.id || match.match_id || ""),
  ];
}

function compareExecutionKeys(a, b) {
  for (let index = 0; index < a.length; index += 1) {
    if (a[index] !== b[index]) return a[index] < b[index] ? -1 : 1;
  }
  return 0;
}

function knockoutScheduleRows(matches, completed, prerequisiteMatches = []) {
  const stageOrder = {
    preliminary: 0, po: 1, regional_po: 1, r16: 2, qf: 3, sf: 4, final: 5,
    ACL1_po: 0, ACL1_r16: 1, ACL1_qf: 2, ACL1_sf: 3, ACL1_final: 4,
    ACL2_po: 0, ACL2_r16: 1, ACL2_qf: 2, ACL2_sf: 3, ACL2_final: 4,
    ACL3_po: 0, ACL3_r16: 1, ACL3_qf: 2, ACL3_sf: 3, ACL3_final: 4,
  };
  return groupBracketMatches(visibleBracketMatches(matches, completed, stageOrder, prerequisiteMatches));
}

function legText(match, completed, teamNames) {
  if (!match) return "";
  const home = teamLabel(match.home_team_id, teamNames);
  const away = teamLabel(match.away_team_id, teamNames);
  if (!matchCompleted(match, completed)) {
    return `${home} vs ${away}`;
  }
  return `${home} ${Number(match.home_score || 0)}-${Number(match.away_score || 0)} ${away}`;
}

function winnerText(matchGroup, completed, teamNames) {
  const winner = aggregateWinnerId(matchGroup, completed);
  return winner ? teamLabel(winner, teamNames) : "";
}

function renderKnockoutScheduleTable(matchGroups, completed, teamNames) {
  if (!matchGroups.length) {
    return `<p class="pending">확정된 토너먼트 일정이 없습니다.</p>`;
  }
  const orderedGroups = [...matchGroups].sort((a, b) => {
    const aFirst = a[0];
    const bFirst = b[0];
    return knockoutStageOrder(aFirst?.stage) - knockoutStageOrder(bFirst?.stage)
      || compareExecutionKeys(matchExecutionKey(aFirst), matchExecutionKey(bFirst))
      || Number(aFirst?.match_no || 0) - Number(bFirst?.match_no || 0)
      || String(aFirst?.round || "").localeCompare(String(bFirst?.round || ""), "ko");
  });
  const rows = orderedGroups.map((matchGroup) => {
    const first = matchGroup[0];
    const byLeg = new Map(matchGroup.map((match) => [Number(match.leg || 1), match]));
    const leg1 = byLeg.get(1) || first;
    const leg2 = byLeg.get(2);
    return `
      <tr>
        <td>${String(first.round || "")}</td>
        <td>${String(first.region || "")}</td>
        <td>${Number(first.match_no || 0)}</td>
        <td>${legText(leg1, completed, teamNames)}</td>
        <td>${legText(leg2, completed, teamNames)}</td>
        <td>${winnerText(matchGroup, completed, teamNames)}</td>
      </tr>
    `;
  }).join("");
  return `
    <table>
      <thead><tr><th>라운드</th><th>지역</th><th>매치</th><th>1차전</th><th>2차전</th><th>승자</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function completedReplayMatches(replay, snapshot, predicate) {
  const completedCount = Number(snapshot?.completed_count || 0);
  const completed = new Set((replay?.completion_order || []).slice(0, completedCount));
  const schedule = Array.isArray(replay?.schedule) ? replay.schedule : [];
  return schedule.filter((match) => completed.has(String(match.match_id || "")) && (!predicate || predicate(match)));
}

function matchResultFromReplay(match) {
  return {
    competition: String(match.competition || ""),
    home_team_id: String(match.home_team_id || ""),
    away_team_id: String(match.away_team_id || ""),
    home_score: Number(match.home_score || 0),
    away_score: Number(match.away_score || 0),
  };
}

function groupStandingsSections(groups, completed, teamNames, labelPrefix = "") {
  return Array.from(groups.entries())
    .sort((a, b) => String(a[0]).localeCompare(String(b[0]), "ko"))
    .map(([groupName, matches]) => {
      const teamIds = Array.from(new Set(matches.flatMap((match) => [
        String(match.home_team_id || ""),
        String(match.away_team_id || ""),
      ]).filter(Boolean)));
      const rows = calculateStandings(
        teamIds,
        matches.filter((match) => completed.has(String(match.match_id || ""))).map(matchResultFromReplay),
        teamNames,
      );
      return `<section class="cup-group"><h3>${labelPrefix}${groupName}</h3>${standingsTable(rows, false)}</section>`;
    })
    .join("");
}

function replaceViewContent(panel, viewId, html) {
  const view = panel.querySelector(`#${viewId}`);
  if (view) {
    view.innerHTML = html;
    return;
  }
  panel.insertAdjacentHTML("beforeend", html);
}

function renderBracket(matches, completed, teamNames, prerequisiteMatches = []) {
  const stageOrder = {
    preliminary: 0, po: 1, regional_po: 1, r16: 2, qf: 3, sf: 4, final: 5,
    ACL1_po: 0, ACL1_r16: 1, ACL1_qf: 2, ACL1_sf: 3, ACL1_final: 4,
    ACL2_po: 0, ACL2_r16: 1, ACL2_qf: 2, ACL2_sf: 3, ACL2_final: 4,
    ACL3_po: 0, ACL3_r16: 1, ACL3_qf: 2, ACL3_sf: 3, ACL3_final: 4,
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
    const ao = stageOrder[a[0]] ?? knockoutStageOrder(a[0]);
    const bo = stageOrder[b[0]] ?? knockoutStageOrder(b[0]);
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
  if (value.endsWith("_r16")) return "16강";
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
    .sort((a, b) => knockoutStageOrder(a[0]?.stage) - knockoutStageOrder(b[0]?.stage)
      || compareExecutionKeys(matchExecutionKey(a[0]), matchExecutionKey(b[0]))
      || Number(a[0].match_no || 0) - Number(b[0].match_no || 0)
      || String(a[0].round || "").localeCompare(String(b[0].round || ""), "ko"));
}

function visibleBracketMatches(matches, completed, stageOrder, prerequisiteMatches = []) {
  const stages = Array.from(new Set(matches.map((match) => String(match.stage || "stage"))))
    .sort((a, b) => (stageOrder[a] ?? knockoutStageOrder(a)) - (stageOrder[b] ?? knockoutStageOrder(b)) || a.localeCompare(b));
  const visibleStages = new Set();

  for (const stage of stages) {
    const order = stageOrder[stage] ?? knockoutStageOrder(stage);
    const priorStages = stages.filter((item) => (stageOrder[item] ?? knockoutStageOrder(item)) < order);
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
  const activeTarget = panel.dataset.activeViewTarget || "local_cup-rank";
  const matches = Array.isArray(localCup?.matches) ? localCup.matches : [];
  const groupMatches = matches.filter((match) => String(match.stage || "") === "regional_qualifier");
  const knockoutMatches = matches.filter((match) => String(match.stage || "") !== "regional_qualifier");
  const knockoutGroups = knockoutScheduleRows(knockoutMatches, completed, groupMatches);
  const hasKnockout = knockoutGroups.length > 0;
  const rankHidden = activeTarget === "local_cup-knockout" && hasKnockout ? "hidden" : "";
  const knockoutHidden = rankHidden ? "" : "hidden";
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
    <div class="view-toggle" role="group" aria-label="local_cup 보기">
      <button class="toggle-btn ${rankHidden ? "" : "active"}" type="button" data-target="local_cup-rank">순위</button>
      <button class="toggle-btn ${rankHidden ? "active" : ""}" type="button" data-target="local_cup-knockout" ${hasKnockout ? "" : "disabled"}>토너먼트</button>
    </div>
    <div class="view-panel" id="local_cup-rank" ${rankHidden}>${groupsHtml || `<p class="pending">조별 경기가 없습니다.</p>`}</div>
    <div class="view-panel" id="local_cup-knockout" ${knockoutHidden}>${renderKnockoutScheduleTable(knockoutGroups, completed, teamNames)}</div>
  `;
}

function renderTournamentPanel(panel, title, payload, completed, teamNames) {
  const matches = Array.isArray(payload?.matches) ? payload.matches : [];
  const held = payload?.held !== false;
  const knockoutGroups = held ? knockoutScheduleRows(matches, completed) : [];
  const hasKnockout = knockoutGroups.length > 0;
  const standingsRows = Array.isArray(payload?.standings)
    ? payload.standings.map((row, index) => ({
        rank: row.rank ?? index + 1,
        team_name: teamNames.get(String(row.team_id || "")) || row.team_name || row.team_id,
      }))
    : [];
  panel.innerHTML = `
    <h2>${title}</h2>
    <div class="view-toggle" role="group" aria-label="${title} 보기">
      <button class="toggle-btn active" type="button" data-target="${title}-rank">순위</button>
      <button class="toggle-btn" type="button" data-target="${title}-knockout" ${hasKnockout ? "" : "disabled"}>토너먼트</button>
    </div>
    <div class="view-panel" id="${title}-rank">
      ${standingsRows.length ? standingsTable(standingsRows, true) : held ? `<p class="pending">순위는 경기 완료 후 반영됩니다.</p>` : `<p class="pending">이번 시즌에는 진행되지 않습니다.</p>`}
    </div>
    <div class="view-panel" id="${title}-knockout" hidden>${renderKnockoutScheduleTable(knockoutGroups, completed, teamNames)}</div>
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
  const activeTarget = panel.dataset.activeViewTarget || `${league}-rank`;
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
  const knockoutGroups = knockoutScheduleRows(knockoutMatches, completed, groupMatches);
  const hasKnockout = knockoutGroups.length > 0;
  const rankHidden = activeTarget === `${league}-knockout` && hasKnockout ? "hidden" : "";
  const knockoutHidden = rankHidden ? "" : "hidden";

  panel.innerHTML = `
    <h2>${league}</h2>
    <div class="view-toggle" role="group" aria-label="${league} 보기">
      <button class="toggle-btn ${rankHidden ? "" : "active"}" type="button" data-target="${league}-rank">조별리그 순위</button>
      <button class="toggle-btn ${rankHidden ? "active" : ""}" type="button" data-target="${league}-knockout" ${hasKnockout ? "" : "disabled"}>토너먼트</button>
    </div>
    <div class="view-panel" id="${league}-rank" ${rankHidden}>${groupsHtml || `<p class="pending">조별리그 경기가 없습니다.</p>`}</div>
    <div class="view-panel" id="${league}-knockout" ${knockoutHidden}>${renderKnockoutScheduleTable(knockoutGroups, completed, teamNames)}</div>
  `;
}

function wireViewToggles() {
  document.querySelectorAll(".view-toggle").forEach((toggle) => {
    toggle.querySelectorAll(".toggle-btn").forEach((button) => {
      if (button.dataset.viewToggleWired === "1") return;
      button.dataset.viewToggleWired = "1";
      button.addEventListener("click", () => {
        const panel = button.closest(".panel");
        if (button.disabled || !panel) return;
        panel.dataset.activeViewTarget = button.dataset.target || "";
        toggle.querySelectorAll(".toggle-btn").forEach((item) => item.classList.toggle("active", item === button));
        panel.querySelectorAll(".view-panel").forEach((view) => {
          view.hidden = view.id !== button.dataset.target;
        });
      });
    });
  });
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
  wireViewToggles();
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
    replaceViewContent(panel, `${competition}-rank`, standingsTable(rows, competition !== "league" && competition !== "super_cup"));
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
    panel.querySelectorAll(".cup-tabs, .cup-view, .pending").forEach((node) => node.remove());
    if (competition === "league") {
      replaceViewContent(panel, "league-rank", renderReplayStandingsTable(snapshot?.standings?.league || [], teamNames));
    } else {
      replaceViewContent(panel, `${competition}-rank`, `<p class="pending">이 페이지는 현재 tick JSON 기준 리그 순위를 표시합니다.</p>`);
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

function groupNameForMatch(match) {
  const explicit = String(match.group || "").trim();
  if (explicit) return explicit;
  const id = String(match.match_id || "");
  const found = id.match(/-G([A-Z])-R/i);
  return found ? found[1].toUpperCase() : "A";
}

function renderAclGroupStandingsFromReplay(league, replay, snapshot, teamNames) {
  const completedCount = Number(snapshot?.completed_count || 0);
  const completed = new Set((replay?.completion_order || []).slice(0, completedCount));
  const groupMatches = (replay?.schedule || []).filter((match) => String(match.stage || "") === `${league}_group`);
  if (!groupMatches.length) return `<p class="pending">No group matches available.</p>`;
  const revealAfter = Math.min(...groupMatches.map((match) => Number(match.reveal_after_count || 0)));
  if (completedCount < revealAfter) return `<p class="pending">Group stage fixtures are not confirmed yet.</p>`;

  const groups = new Map();
  for (const match of groupMatches) {
    const group = groupNameForMatch(match);
    if (!groups.has(group)) groups.set(group, []);
    groups.get(group).push(match);
  }

  return Array.from(groups.entries())
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([group, matches]) => {
      const teamIds = Array.from(new Set(matches.flatMap((match) => [
        String(match.home_team_id || ""),
        String(match.away_team_id || ""),
      ]).filter(Boolean)));
      const completedMatches = matches
        .filter((match) => completed.has(String(match.match_id || "")))
        .map(resultRow);
      const rows = calculateStandings(teamIds, completedMatches, teamNames);
      return `<section class="cup-group"><h3>Group ${group}</h3>${standingsTable(rows, false)}</section>`;
    })
    .join("");
}

function aclKnockoutGroupsFromReplay(league, replay, snapshot) {
  const completedCount = Number(snapshot?.completed_count || 0);
  const completed = new Set((replay?.completion_order || []).slice(0, completedCount));
  const schedule = Array.isArray(replay?.schedule) ? replay.schedule : [];
  const groupMatches = schedule.filter((match) => String(match.stage || "") === `${league}_group`);
  const knockoutMatches = schedule.filter((match) => {
    const stage = String(match.stage || "");
    if (!stage.startsWith(`${league}_`) || stage === `${league}_group`) return false;
    return completedCount >= Number(match.reveal_after_count || 0);
  });
  return {
    completed,
    groups: knockoutScheduleRows(knockoutMatches, completed, groupMatches),
  };
}

function renderSuperCupFromReplay(panel, replay, snapshot, teamNames) {
  panel.querySelectorAll(".view-toggle, .pending, table").forEach((node) => node.remove());
  const matches = completedReplayMatches(replay, snapshot, (match) => String(match.competition || "") === "super_cup");
  const entrants = Array.isArray(replay?.superCup?.entrants) ? replay.superCup.entrants : [];
  const basePoints = new Map(entrants.map((row) => [String(row.team_id || ""), Number(row.points || 0)]));
  const entrantIds = entrants.map((row) => String(row.team_id || "")).filter(Boolean);
  const scheduleIds = Array.from(new Set(
    (replay?.schedule || [])
      .filter((match) => String(match.competition || "") === "super_cup")
      .flatMap((match) => [String(match.home_team_id || ""), String(match.away_team_id || "")])
      .filter(Boolean)
  ));
  const teamIds = entrantIds.length ? entrantIds : scheduleIds;
  const rows = calculateStandings(teamIds, matches.map(matchResultFromReplay), teamNames);
  for (const row of rows) {
    row.points += basePoints.get(String(row.team_id)) || 0;
  }
  rankStandingsRows(rows);
  panel.insertAdjacentHTML("beforeend", rows.length ? standingsTable(rows, false) : `<p class="pending">아직 슈퍼컵 경기가 없습니다.</p>`);
}

function renderLocalCupFromReplay(panel, replay, snapshot, teamNames) {
  const completedCount = Number(snapshot?.completed_count || 0);
  const completed = new Set((replay?.completion_order || []).slice(0, completedCount));
  const schedule = (replay?.schedule || []).filter((match) => String(match.competition || "") === "local_cup");
  const regionalMatches = schedule.filter((match) => String(match.stage || "") === "regional_qualifier");
  const groupMatches = schedule.filter((match) => String(match.stage || "") === "group");
  const knockoutMatches = schedule.filter((match) => !["regional_qualifier", "group"].includes(String(match.stage || "")));
  const activeTarget = panel.dataset.activeViewTarget || "local_cup-regional";
  const regionalDone = regionalMatches.length > 0 && regionalMatches.every((match) => completed.has(String(match.match_id || "")));
  const hasGroups = groupMatches.length > 0;
  const groupEnabled = hasGroups && regionalDone;
  const knockoutGroups = knockoutScheduleRows(knockoutMatches.filter((match) => completedCount >= Number(match.reveal_after_count || 0)), completed, [...regionalMatches, ...groupMatches]);
  const hasKnockout = knockoutGroups.length > 0;
  const selectedTarget = activeTarget === "local_cup-groups" && groupEnabled
    ? activeTarget
    : activeTarget === "local_cup-knockout" && hasKnockout
      ? activeTarget
      : "local_cup-regional";

  const regionalGroups = new Map();
  for (const match of regionalMatches) {
    const label = [String(match.region || "지역예선"), String(match.group || "")].filter(Boolean).join(" ");
    if (!regionalGroups.has(label)) regionalGroups.set(label, []);
    regionalGroups.get(label).push(match);
  }
  const cupGroups = new Map();
  for (const match of groupMatches) {
    const label = String(match.group || "Group");
    if (!cupGroups.has(label)) cupGroups.set(label, []);
    cupGroups.get(label).push(match);
  }

  panel.innerHTML = `
    <h2>local_cup</h2>
    <div class="view-toggle" role="group" aria-label="local_cup 보기">
      <button class="toggle-btn ${selectedTarget === "local_cup-regional" ? "active" : ""}" type="button" data-target="local_cup-regional">지역예선순위</button>
      <button class="toggle-btn ${selectedTarget === "local_cup-groups" ? "active" : ""}" type="button" data-target="local_cup-groups" ${groupEnabled ? "" : "disabled"}>조별예선순위</button>
      <button class="toggle-btn ${selectedTarget === "local_cup-knockout" ? "active" : ""}" type="button" data-target="local_cup-knockout" ${hasKnockout ? "" : "disabled"}>토너먼트</button>
    </div>
    <div class="view-panel" id="local_cup-regional" ${selectedTarget === "local_cup-regional" ? "" : "hidden"}>
      ${regionalGroups.size ? groupStandingsSections(regionalGroups, completed, teamNames) : `<p class="pending">지역예선 경기가 없습니다.</p>`}
    </div>
    <div class="view-panel" id="local_cup-groups" ${selectedTarget === "local_cup-groups" ? "" : "hidden"}>
      ${groupEnabled ? groupStandingsSections(cupGroups, completed, teamNames, "Group ") : `<p class="pending">조별예선은 지역예선 종료 후 표시됩니다.</p>`}
    </div>
    <div class="view-panel" id="local_cup-knockout" ${selectedTarget === "local_cup-knockout" ? "" : "hidden"}>
      ${renderKnockoutScheduleTable(knockoutGroups, completed, teamNames)}
    </div>
  `;
  wireViewToggles();
}

function renderChampionshipFromReplay(panel, replay, snapshot, teamNames) {
  panel.querySelectorAll(".view-toggle, .view-panel, .pending, table").forEach((node) => node.remove());
  const completedCount = Number(snapshot?.completed_count || 0);
  const completed = new Set((replay?.completion_order || []).slice(0, completedCount));
  const matches = (replay?.schedule || []).filter((match) => String(match.competition || "") === "championship");
  const visible = matches.filter((match) => completedCount >= Number(match.reveal_after_count || 0));
  const groups = knockoutScheduleRows(visible, completed);
  panel.insertAdjacentHTML("beforeend", renderKnockoutScheduleTable(groups, completed, teamNames));
}

function setKnockoutButtonState(panel, target, enabled) {
  const button = panel.querySelector(`.toggle-btn[data-target="${target}"]`);
  if (!button) return;
  button.disabled = !enabled;
  if (!enabled && button.classList.contains("active")) {
    const rankButton = panel.querySelector(".toggle-btn[data-target$='-rank']");
    rankButton?.click();
  }
}

function guardStandingsFromReplay(snapshot, teams, replay) {
  const teamNames = new Map((Array.isArray(teams) ? teams : []).map((team) => [String(team.id), String(team.name || team.id)]));
  extendAclTeamNames(teamNames, replay?.acl || {});
  document.querySelectorAll("main.grid .panel").forEach((panel) => {
    const title = panel.querySelector("h2");
    if (!title) return;
    const competition = title.textContent.trim();
    panel.querySelectorAll(".cup-tabs, .cup-view, .pending, .cup-group").forEach((node) => node.remove());
    if (competition === "league") {
      replaceViewContent(panel, "league-rank", renderReplayStandingsTable(snapshot?.standings?.league || [], teamNames));
      return;
    }
    if (competition === "super_cup") {
      renderSuperCupFromReplay(panel, replay, snapshot, teamNames);
      return;
    }
    if (competition === "local_cup") {
      renderLocalCupFromReplay(panel, replay, snapshot, teamNames);
      return;
    }
    if (competition === "championship") {
      renderChampionshipFromReplay(panel, replay, snapshot, teamNames);
      return;
    }
    if (competition === "ACL1" || competition === "ACL2" || competition === "ACL3") {
      replaceViewContent(panel, `${competition}-rank`, renderAclGroupStandingsFromReplay(competition, replay, snapshot, teamNames));
      const knockout = aclKnockoutGroupsFromReplay(competition, replay, snapshot);
      replaceViewContent(panel, `${competition}-knockout`, renderKnockoutScheduleTable(knockout.groups, knockout.completed, teamNames));
      setKnockoutButtonState(panel, `${competition}-knockout`, knockout.groups.length > 0);
      return;
    }
    replaceViewContent(panel, `${competition}-rank`, `<p class="pending">Standings for this competition are not available in the current replay snapshot.</p>`);
  });
}

async function main() {
  const [manifest, teams, acl, superCup] = await Promise.all([
    fetch("./replay_manifest.json", { cache: "no-store" }).then((r) => r.json()),
    fetch("./teams.json", { cache: "no-store" }).then((r) => r.json()).catch(() => []),
    fetch("./acl.json", { cache: "no-store" }).then((r) => r.json()).catch(() => ({})),
    fetch("./super_cup.json", { cache: "no-store" }).then((r) => r.json()).catch(() => ({})),
  ]);
  const [schedule, completionOrder] = await Promise.all([
    fetch(`./${manifest.schedule_path || "replay_schedule.json"}`, { cache: "no-store" }).then((r) => r.json()),
    fetch(`./${manifest.completion_order_path || "replay_completion_order.json"}`, { cache: "no-store" }).then((r) => r.json()),
  ]);
  const replay = { ...manifest, schedule, completion_order: completionOrder, acl, superCup };
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
    if (document.querySelector("main.grid")) guardStandingsFromReplay(snapshot, teams, replay);
  };
  await render();
  setInterval(() => render().catch((err) => console.error(err)), Number(replay.tick_seconds || 2) * 1000);
}

main().catch((err) => console.error(err));
