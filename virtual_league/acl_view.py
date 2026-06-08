from __future__ import annotations

from html import escape
from pathlib import Path


def write_acl_participants_html(path: Path, acl_payload: dict[str, object]) -> None:
    path.write_text(render_acl_participants_html(acl_payload), encoding="utf-8")


def _participant_kind(slot: str) -> str:
    return "대체" if slot == "Z" else "정규"


def _country_list(items: list[dict[str, object]]) -> str:
    countries = [str(item.get("country", "")) for item in items]
    return ", ".join(escape(country) for country in countries)


def _group_conflict_label(items: list[dict[str, object]]) -> str:
    countries = [str(item.get("country", "")) for item in items]
    return "중복 없음" if len(countries) == len(set(countries)) else "중복 있음"


def _ranking_display_rows(rankings: list[dict[str, object]]) -> list[dict[str, object]]:
    return [dict(row) for row in rankings]


def render_acl_participants_html(acl_payload: dict[str, object]) -> str:
    rankings = acl_payload.get("country_rankings", [])
    groups = acl_payload.get("groups", {})
    participants = acl_payload.get("participants", {})

    ranking_rows = "".join(
        f"<tr><td>{escape(str(row.get('regional_rank', row.get('rank', ''))))}</td>"
        f"<td>{escape(str(row.get('slot', '')))}</td>"
        f"<td>{escape(str(row.get('country', '')))}</td>"
        f"<td>{escape(str(row.get('region', '')))}</td>"
        f"<td>{escape(str(row.get('adjusted_score', '')))}</td></tr>"
        for row in _ranking_display_rows(list(rankings))
    )

    league_sections = []
    for league in ["ACL1", "ACL2", "ACL3"]:
        rows = list(participants.get(league, []))
        group_map = groups.get(league, {})
        participant_rows = "".join(
            f"<tr class=\"{escape(str(item.get('slot', '')))}\">"
            f"<td>{escape(str(item.get('slot', '')))}</td>"
            f"<td>{escape(_participant_kind(str(item.get('slot', ''))))}</td>"
            f"<td>{escape(str(item.get('country', '')))}</td>"
            f"<td>{escape(str(item.get('team_name', item.get('team_id', ''))))}</td>"
            f"<td>{escape(str(item.get('region', '')))}</td>"
            f"</tr>"
            for item in rows
        )
        group_rows = "".join(
            f"<tr><td>{escape(group)}</td>"
            f"<td>{escape(_country_list([next((item for item in rows if str(item.get('team_id')) == team_id), {'country': team_id}) for team_id in members]))}</td>"
            f"<td>{escape(_group_conflict_label([next((item for item in rows if str(item.get('team_id')) == team_id), {'country': team_id}) for team_id in members]))}</td></tr>"
            for group, members in sorted(group_map.items())
        )
        league_sections.append(
            f"""
            <section class="panel">
              <h2>{league}</h2>
              <div class="grid">
                <div>
                  <h3>참가팀</h3>
                  <table>
                    <thead>
                      <tr><th>슬롯</th><th>유형</th><th>국가</th><th>팀명</th><th>권역</th></tr>
                    </thead>
                    <tbody>{participant_rows}</tbody>
                  </table>
                </div>
                <div>
                  <h3>조편성</h3>
                  <table>
                    <thead>
                      <tr><th>조</th><th>국가</th><th>국가 충돌</th></tr>
                    </thead>
                    <tbody>{group_rows}</tbody>
                  </table>
                </div>
              </div>
            </section>
            """
        )

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ACL 참가팀 보기</title>
  <style>
    :root {{
      --bg: #f4f7fb;
      --panel: #ffffff;
      --border: #dbe3ee;
      --text: #132238;
      --muted: #5d6b7e;
      --accent: #0f5b99;
      --soft: #eaf2fb;
      --danger: #8f3b3b;
    }}
    body {{
      margin: 0;
      font-family: "Malgun Gothic", Arial, sans-serif;
      background:
        radial-gradient(circle at top left, #dbeafe 0, transparent 34%),
        radial-gradient(circle at top right, #e0f2fe 0, transparent 28%),
        var(--bg);
      color: var(--text);
    }}
    header {{
      padding: 24px 24px 12px;
    }}
    h1 {{
      margin: 0;
      font-size: 28px;
      letter-spacing: -0.02em;
    }}
    .sub {{
      margin-top: 8px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
    }}
    .legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
      color: var(--muted);
      font-size: 12px;
    }}
    .chip {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 10px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.78);
      border: 1px solid var(--border);
    }}
    .panel {{
      margin: 16px;
      padding: 16px;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 14px;
      box-shadow: 0 10px 24px rgba(15, 23, 42, 0.04);
    }}
    .grid {{
      display: grid;
      grid-template-columns: 1.25fr 1fr;
      gap: 16px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
    }}
    th, td {{
      border: 1px solid var(--border);
      padding: 7px 8px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: var(--soft);
      font-weight: 700;
    }}
    h2, h3 {{
      margin: 0 0 10px;
    }}
    .Z {{
      background: #fff8e8;
    }}
    .conflict-no {{
      color: #166534;
      font-weight: 700;
    }}
    .conflict-yes {{
      color: var(--danger);
      font-weight: 700;
    }}
    @media (max-width: 900px) {{
      .grid {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>ACL 참가팀 보기</h1>
    <div class="sub">
      최근 ACL 생성 로직 기준으로 참가팀, 대체 슬롯, 그리고 조편성을 같이 보여줍니다.
      같은 국가 팀은 가능한 한 같은 조에 겹치지 않도록 배치됩니다.
    </div>
    <div class="legend">
      <span class="chip">정규: 일반 슬롯 팀</span>
      <span class="chip">대체: <code>Z</code> 슬롯으로 들어간 우승권 대체팀</span>
      <span class="chip">국가 충돌 없음: 같은 조에 같은 국가가 없음</span>
    </div>
  </header>

  <section class="panel">
    <h2>권역 순위</h2>
    <table>
      <thead>
        <tr><th>순위</th><th>슬롯</th><th>국가</th><th>권역</th><th>점수</th></tr>
      </thead>
      <tbody>{ranking_rows}</tbody>
    </table>
  </section>
  {''.join(league_sections)}
</body>
</html>
"""
