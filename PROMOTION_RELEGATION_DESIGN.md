# 승강제 설계안

이 문서는 현재 `virtual_league` 구조에 승강제를 어떻게 붙일지 정리한 설계안이다.
목표는 "지금 당장 승강리그를 하나 더 만드는 것"이 아니라, 사용자가 시즌 시작 전에 규칙을 입력하고 그 규칙이 다음 시즌부터 반영되도록 만드는 것이다.

## 현재 구조 요약

- `team_registry.py`
  - `teams.json` 읽기/쓰기
  - 팀 추가
  - `professional` 플래그만 존재
- `season.py`
  - 시즌 생성의 중심
  - 리그 일정 생성
  - 전 시즌 순위 읽기
  - 컵 대회 생성
  - `standings.json`, `schedule.json`, `live_feed.json` 작성
- `league.py`
  - 주어진 팀 목록으로 리그 일정 생성
- `future_competitions.py`
  - `promotion_relegation_playoffs`가 TODO로만 존재

즉, 현재는 "팀 원장"과 "시즌 생성"은 있지만, "다음 시즌 팀 편성 정책"은 없다.

## 설계 원칙

1. 시즌 생성과 승강 규칙 입력을 분리한다.
2. 승강 규칙은 시즌 데이터와 분리해서 저장한다.
3. 과거 시즌은 고정 보존하고, 새 규칙은 특정 시즌부터만 적용한다.
4. 하위리그가 당장 없어도 규칙 구조는 미리 지원한다.
5. 사용자 수정 가능성이 높은 값은 설정 파일로 둔다.

## 어디에 꽂아야 하는가

승강제는 경기 엔진이 아니라 `create_season()`의 시작 부분에 들어가야 한다.

권장 흐름:

1. 사용자가 "다음 시즌 설정 세션"에서 규칙 입력
2. 규칙 파일 저장
3. `create_season()`이 규칙 파일과 직전 시즌 결과를 읽음
4. 시즌 참가팀 목록을 tier policy에 따라 재구성
5. 그 결과로 `generate_league_schedule()` 실행
6. 시즌 결과와 함께 어떤 규칙이 적용됐는지 `season.json`에 저장

## 새로 필요한 설정 파일

권장 파일명:

- `league_rules.json`

역할:

- 승격/강등 수
- 승강전 방식
- 적용 시작 시즌
- 티어 구조
- 하위리그 존재 여부

예시 구조:

```json
{
  "effective_from_year": 1972,
  "tiers": [
    {
      "tier": 1,
      "name": "K League",
      "auto_promote": 0,
      "auto_relegate": 2,
      "playoff": {
        "enabled": true,
        "teams": 2,
        "format": "two_leg"
      }
    },
    {
      "tier": 2,
      "name": "Challenge",
      "auto_promote": 2,
      "auto_relegate": 2
    }
  ]
}
```

이 구조의 핵심은 "리그 수"가 아니라 "티어 정책"을 저장한다는 점이다.
나중에 하위리그가 생겨도 같은 포맷으로 확장 가능하다.

## 팀 데이터에 추가할 정보

`teams.json`에는 최소한 다음 중 하나가 더 필요하다.

- `tier`
- `league_group`
- `active_from`
- `active_until`

권장 방식은 `tier`다.

예:

```json
{
  "id": "T01",
  "name": "수원",
  "region": "경기",
  "professional": true,
  "tier": 1
}
```

이렇게 두면 승강 후 다음 시즌에 어느 풀로 들어갈지 계산하기 쉽다.

## 새 모듈 제안

권장 파일:

- `virtual_league/promotion.py`

역할:

- 전 시즌 `standings.json` 읽기
- 규칙 파일 읽기
- 승격/강등 대상 계산
- 승강전 대상 계산
- 다음 시즌 참가팀 목록 생성

예상 함수:

- `load_league_rules(path) -> dict`
- `resolve_next_season_teams(seasons_dir, year, teams, rules) -> list[Team]`
- `build_promotion_bracket(...) -> list[Match]`
- `apply_promotion_results(...) -> dict`

## `season.py`에서 바뀌는 지점

현재 `create_season()`은 `season_teams = ensure_team_file(...)`로 바로 시작한다.
이 부분을 다음처럼 바꿔야 한다.

1. 팀 원장 로드
2. 규칙 로드
3. 적용 대상 시즌인지 검사
4. 필요하면 전 시즌 순위 기반으로 팀 재배치
5. 그 결과를 `season_teams`로 사용
6. 이후 기존 로직 유지

즉, 리그 일정 생성 자체는 그대로 두고, 그 앞단의 입력팀만 바꾼다.

## 다음 시즌 설정 세션

사용자가 직접 조정할 수 있어야 하는 값:

- 자동 승격 팀 수
- 자동 강등 팀 수
- 승강전 사용 여부
- 승강전 진출 범위
- 승강전 형식
- 적용 시작 시즌

권장 인터페이스 순서:

1. 설정 파일 편집
2. 미리보기
3. 확인 후 시즌 생성

CLI로 시작해도 되고, 나중에 웹 UI로 옮겨도 된다.

## 구현 우선순위

1. `league_rules.json` 포맷 정의
2. `promotion.py` 추가
3. `season.py`에 규칙 적용 훅 추가
4. `teams.json`에 `tier` 지원 추가
5. 승강전 경기 생성 연결
6. 설정 미리보기/검증 명령 추가

## 현재 단계에서 하지 않을 것

- 하위리그를 지금 당장 강제로 만들지 않는다.
- 기존 시즌 데이터 구조를 한 번에 갈아엎지 않는다.
- 경기 엔진을 승강제 전용으로 분기하지 않는다.

핵심은 "규칙이 바뀌어도 시즌 생성 코드가 안 깨지는 구조"를 먼저 만드는 것이다.

