from __future__ import annotations

import csv
import json
import random
import re
from functools import lru_cache
from collections.abc import Sequence
from pathlib import Path
from string import ascii_uppercase

from .models import Match, Team
from .tournament_resolution import simulate_match

REGIONAL_SLOTS = list("ABCDEFGHIJKLMNOPQRSTUVW")
RANKING_SLOTS = list(ascii_uppercase)
ACL_RANKING_ROOT = Path(__file__).resolve().parent.parent
ACL_EAST_RANKING_PATH = ACL_RANKING_ROOT / "afc_association_ranking_east_points.csv"
ACL_WEST_RANKING_PATH = ACL_RANKING_ROOT / "afc_association_ranking_west_points.csv"
CITY_COLUMN_NAMES = [f"도시명{i}" for i in range(1, 11)]

WEST_SLOT_COUNTRIES = [
    "Saudi Arabia",
    "Qatar",
    "United Arab Emirates",
    "Iran",
    "Iraq",
    "Uzbekistan",
    "Jordan",
    "Oman",
    "Kuwait",
    "Bahrain",
    "Syria",
    "Palestine",
    "Lebanon",
    "Yemen",
    "Turkmenistan",
    "Tajikistan",
    "Kazakhstan",
    "Afghanistan",
    "Maldives",
    "Nepal",
    "Sri Lanka",
    "Bangladesh",
]

EAST_SLOT_COUNTRIES = [
    "Japan",
    "Korea Republic",
    "China PR",
    "Australia",
    "Indonesia",
    "Malaysia",
    "Thailand",
    "Vietnam",
    "Philippines",
    "Singapore",
    "Hong Kong",
    "Chinese Taipei",
    "Myanmar",
    "Cambodia",
    "Laos",
    "Brunei",
    "North Korea",
    "India",
    "Pakistan",
    "Bhutan",
    "Mongolia",
    "Macau",
]

WEST_GROUPS = ["A", "B", "C", "D"]
EAST_GROUPS = ["E", "F", "G", "H"]
GROUP_WEEKS = {1: 4, 2: 6, 3: 8, 4: 10, 5: 12, 6: 14}

REGIONAL_SCORE_LADDER = [
    100,
    96,
    93,
    90,
    87,
    84,
    81,
    78,
    75,
    72,
    69,
    66,
    63,
    60,
    57,
    54,
    51,
    48,
    45,
    42,
    39,
    36,
]

CITY_POOLS = {
    "Saudi Arabia": ["리야드", "제다", "메카", "메디나", "담맘", "타이프", "카심", "하사", "아브하", "하일"],
    "Qatar": ["도하", "알라이얀", "알와크라", "알코르", "움살랄", "루사일", "메사이드", "알샤말", "알시하니야", "두칸"],
    "United Arab Emirates": ["두바이", "아부다비", "샤르자", "알아인", "아지만", "푸자이라", "라스알카이마", "움알쿠와인", "칼바", "디바"],
    "Iran": ["테헤란", "마슈하드", "이스파한", "쉬라즈", "타브리즈", "카라지", "아흐바즈", "콤", "케르만샤", "라슈트"],
    "Iraq": ["바그다드", "바스라", "모술", "에르빌", "나자프", "키르쿠크", "술라이마니야", "카르발라", "디와니야", "나시리야"],
    "Uzbekistan": ["타슈켄트", "사마르칸트", "부하라", "페르가나", "안디잔", "나망간", "누쿠스", "지작", "카르시", "테르메즈"],
    "Jordan": ["암만", "자르카", "이르비드", "아카바", "마프라크", "마다바", "살트", "타필라", "카라크", "루세이파"],
    "Oman": ["무스카트", "살랄라", "소하르", "니즈와", "수르", "이브라", "바르카", "브레미", "케이블", "하므라"],
    "Kuwait": ["쿠웨이트시티", "하왈리", "파르와니야", "아흐마디", "주와일", "자흐라", "무바라크알카비르", "사바히야", "살미야", "파하힐"],
    "Bahrain": ["마나마", "무하라크", "리파", "이사타운", "하마드타운", "시트라", "압달리", "히디", "자흐라", "잔다나"],
    "Syria": ["다마스쿠스", "알레포", "홈스", "하마", "라타키아", "타르투스", "데이르에조르", "라카", "수웨이다", "키스와"],
    "Palestine": ["가자", "라말라", "나블루스", "헤브론", "제닌", "베들레헴", "칼킬리야", "툴카름", "리파", "칼타"],
    "Lebanon": ["베이루트", "트리폴리", "시돈", "타이레", "잘레", "나바티예", "바알베크", "안잘라", "브루만나", "주니에"],
    "Yemen": ["사나", "아덴", "타이즈", "호데이다", "시브와", "마리브", "이브", "달리아", "라흐즈", "자프라"],
    "Turkmenistan": ["아시가바트", "투르크메나바트", "다쇼구즈", "마리", "발칸아바트", "바하르덴", "아나우", "세르다르", "코네우르겐치", "테젠"],
    "Tajikistan": ["두샨베", "후잔드", "보흐타르", "쿨롭", "이스타라브샨", "펜지켄트", "이소라", "캉기르트", "꼼소몰라바드", "노빈"],
    "Kazakhstan": ["알마티", "아스타나", "쉼켄트", "카라간다", "아크토베", "타랏", "파블로다르", "우스튜르트", "오랄", "코스타나이"],
    "Afghanistan": ["카불", "헤라트", "마자르이샤리프", "칸다하르", "잘랄라바드", "쿤두즈", "가즈니", "파이자바드", "라슈카르가", "바미안"],
    "Maldives": ["말레", "훌후말레", "아두", "푸바물라", "바아톨", "라아톨", "하알리알톨", "샤비야니톨", "라비아니톨", "다알톨"],
    "Nepal": ["카트만두", "포카라", "라리트푸르", "비라트나가르", "비르간지", "부트왈", "다란", "헷다우다", "잔악푸르", "네팔군즈"],
    "Sri Lanka": ["콜롬보", "캔디", "갈레", "자프나", "누와라엘리야", "트린코말리", "바티칼로아", "쿠루네갈라", "아누라다푸라", "모나라갈라"],
    "Bangladesh": ["다카", "치타공", "쿨나", "라지샤히", "실렛", "바리살", "랑푸르", "미멘싱", "코밀라", "보그라"],
    "Japan": ["도쿄", "오사카", "요코하마", "고베", "나고야", "삿포로", "후쿠오카", "가와사키", "사이타마", "센다이"],
    "Korea Republic": ["서울", "부산", "인천", "대구", "대전", "광주", "수원", "울산", "전주", "창원"],
    "China PR": ["상하이", "베이징", "광저우", "선전", "청두", "우한", "톈진", "충칭", "난징", "항저우"],
    "Australia": ["시드니", "멜버른", "브리즈번", "퍼스", "애들레이드", "캔버라", "호바트", "다윈", "골드코스트", "뉴캐슬"],
    "Indonesia": ["자카르타", "수라바야", "반둥", "메단", "스마랑", "마카사르", "족자카르타", "팔렘방", "발릭파판", "데폭"],
    "Malaysia": ["쿠알라룸푸르", "조호르바루", "페낭", "이포", "코타키나발루", "쿠칭", "말라카", "클랑", "알로르세타르", "쿠알라테렝가누"],
    "Thailand": ["방콕", "치앙마이", "푸껫", "파타야", "콘깬", "나콘랏차시마", "핫야이", "우본랏차타니", "수랏타니", "송클라"],
    "Vietnam": ["하노이", "호찌민", "다낭", "하이퐁", "껀터", "냐짱", "빈", "후에", "달랏", "비엔호아"],
    "Philippines": ["마닐라", "세부", "다바오", "일로일로", "바콜로드", "바기오", "카가얀데오로", "제너럴산토스", "잠보앙가", "타클로반"],
    "Singapore": ["싱가포르", "우드랜즈", "탐피니스", "주롱", "베독", "앙모키오", "브라델", "파시르리스", "퐁골", "이슌"],
    "Hong Kong": ["홍콩", "구룡", "센트럴", "완차이", "췬완", "사틴", "타이포", "췬이", "츈문", "리틀송"],
    "Chinese Taipei": ["타이베이", "가오슝", "타이중", "타이난", "반차오", "지룽", "신주", "자이", "펑위안", "루강"],
    "Myanmar": ["양곤", "만달레이", "네피도", "바고", "모울메인", "타웅지", "파테인", "메익", "몬와", "툰지"],
    "Cambodia": ["프놈펜", "시엠립", "바탐방", "시하누크빌", "캄퐁참", "캄퐁톰", "포이펫", "크라티에", "캄폿", "수아리엡"],
    "Laos": ["비엔티안", "루앙프라방", "팍세", "사바나켓", "타케크", "샤이냐부리", "폰사완", "무앙사이", "세콩", "아타푸"],
    "Brunei": ["반다르스리브가완", "무아라", "쿠알라벨라잇", "투통", "판타이", "세리", "림방", "파고", "나가리", "토튼"],
    "North Korea": ["평양", "함흥", "남포", "원산", "신의주", "청진", "개성", "사리원", "혜산", "라선"],
    "India": ["뉴델리", "뭄바이", "벵갈루루", "콜카타", "첸나이", "하이데라바드", "푸네", "아메다바드", "수라트", "자이푸르"],
    "Pakistan": ["카라치", "라호르", "이슬라마바드", "파이살라바드", "라왈핀디", "물탄", "구즈란왈라", "페샤와르", "케타", "시알코트"],
    "Bhutan": ["팀푸", "파로", "푸나카", "왕두", "추카", "가사", "트롱사", "몬가르", "르눕체", "사마츠"],
    "Mongolia": ["울란바토르", "에르데네트", "다르항", "차강노르", "외르헝", "바양홍고르", "홉드", "고비알타이", "수흐바타르", "도르노드"],
    "Macau": ["마카오", "타이파", "콜로안", "세나도", "산토안토니오", "산라자로", "프레이르", "아레아", "나모반", "코타이"],
    "Kyrgyzstan": ["비슈케크", "오시", "잘랄아바드", "카라콜", "토크목", "나린", "발릭치", "바트켄", "카라발타", "키질키야"],
    "Palau": ["\ucf54\ub85c\ub974", "\uc5b8\uac00\ub974\ub8e8\ubbac\ub4dc", "\uc544\uc774\ub77c\uc774", "\uba54\ub808\ucf54\ud06c", "\uc5b8\uac00\ub974\ub9c8\uc6b0", "\uc5b8\uac00\ucc8c\ub871", "\uc5b8\uac00\ud31d", "\uc5b8\uae30\uc640\ub974", "\ud398\ub808\ub9ac\uc720", "\uc554\uac00\uc6b0\ub974"],
    "Timor-Leste": ["딜리", "바우카우", "말리아나", "수아이", "베말라", "리퀴사", "글레노", "라우템", "오에쿠시", "사메"],
    "Guam": ["하갓냐", "데데도", "타무닝", "이고", "망길라오", "바리가다", "산타리타", "차란파고오르도트", "아산마이나", "탈로포포"],
    "Northern Mariana Islands": ["가라판", "사이판", "치란가", "수수페", "타포차우", "산호세", "산로케", "하가만", "탈라기", "이잔"],
}

"""
COUNTRY_NAME_KO = {
    "Saudi Arabia": "사우디아라비아",
    "Qatar": "카타르",
    "United Arab Emirates": "아랍에미리트",
    "Iran": "이란",
    "Iraq": "이라크",
    "Uzbekistan": "우즈베키스탄",
    "Jordan": "요르단",
    "Oman": "오만",
    "Kuwait": "쿠웨이트",
    "Bahrain": "바레인",
    "Syria": "시리아",
    "Palestine": "팔레스타인",
    "Lebanon": "레바논",
    "Yemen": "예멘",
    "Turkmenistan": "투르크메니스탄",
    "Tajikistan": "타지키스탄",
    "Kazakhstan": "카자흐스탄",
    "Afghanistan": "아프가니스탄",
    "Maldives": "몰디브",
    "Nepal": "네팔",
    "Sri Lanka": "스리랑카",
    "Bangladesh": "방글라데시",
    "Japan": "일본",
    "Korea Republic": "대한민국",
    "China PR": "중국",
    "Australia": "호주",
    "Indonesia": "인도네시아",
    "Malaysia": "말레이시아",
    "Thailand": "태국",
    "Vietnam": "베트남",
    "Philippines": "필리핀",
    "Singapore": "싱가포르",
    "Hong Kong": "홍콩",
    "Chinese Taipei": "중화 타이베이",
    "Myanmar": "미얀마",
    "Cambodia": "캄보디아",
    "Laos": "라오스",
    "Brunei": "브루나이",
    "North Korea": "북한",
    "India": "인도",
    "Pakistan": "파키스탄",
    "Bhutan": "부탄",
    "Mongolia": "몽골",
    "Macau": "마카오",
}
COUNTRY_NAME_EN = {value: key for key, value in COUNTRY_NAME_KO.items()}


def display_country_name(country: str) -> str:
    return COUNTRY_NAME_KO.get(str(country), str(country))


def country_pool_key(country: str) -> str:
    value = str(country)
    return COUNTRY_NAME_EN.get(value, value)


def country_id_key(country: str) -> str:
    value = country_pool_key(country)
    return COUNTRY_NAME_EN.get(value, value)


def _association_ranking_path(region: str) -> Path:
    return ACL_WEST_RANKING_PATH if region == "west" else ACL_EAST_RANKING_PATH


def _parse_points(value: object) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError, AttributeError):
        return 0.0


def _parse_city_names(raw: dict[str, object]) -> tuple[str, ...]:
    city_names = []
    for column in CITY_COLUMN_NAMES:
        value = str(raw.get(column, "")).strip()
        if value:
            city_names.append(value)
    return tuple(city_names)


@lru_cache(maxsize=1)
def _load_association_city_pools() -> dict[str, tuple[str, ...]]:
    pools: dict[str, tuple[str, ...]] = {}
    for region in ("east", "west"):
        path = _association_ranking_path(region)
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for raw in reader:
                source_country = str(raw.get("country", "")).strip()
                if not source_country:
                    continue
                city_names = _parse_city_names(raw)
                if city_names:
                    display_name = display_country_name(source_country)
                    pools[source_country] = city_names
                    pools[display_name] = city_names
                    pools[country_pool_key(source_country)] = city_names
    return pools


def association_city_pool(country: str) -> list[str]:
    key = str(country).strip()
    pool = _load_association_city_pools().get(key)
    if not pool:
        pool = _load_association_city_pools().get(display_country_name(key))
    if not pool:
        pool = _load_association_city_pools().get(country_pool_key(key))
    if pool:
        return list(pool)
    fallback = CITY_POOLS.get(country_pool_key(country))
    if fallback:
        return list(fallback)
    return [display_country_name(country)]


def _load_association_ranking_rows(region: str) -> list[dict[str, object]]:
    path = _association_ranking_path(region)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: list[dict[str, object]] = []
        for raw in reader:
            source_country = str(raw.get("country", "")).strip()
            if not source_country:
                continue
            source_slot = str(raw.get("slot_letter", "")).strip()
            reserve = region == "east" and source_slot == "W"
            rows.append(
                {
                    "source_slot": source_slot,
                    "source_country": source_country,
                    "country_code": str(raw.get("code", "")).strip(),
                    "country": display_country_name(source_country),
                    "region": region,
                    "base_score": _parse_points(raw.get("base_points")),
                    "point_delta": _parse_points(raw.get("point_delta")),
                    "source_points": _parse_points(raw.get("points")),
                    "reserve": reserve,
                }
            )
    return rows


"""

COUNTRY_NAME_KO = {
    "Saudi Arabia": "\uC0AC\uC6B0\uB514\uC544\uB77C\uBE44\uC544",
    "Qatar": "\uCE74\uD0C0\uB974",
    "United Arab Emirates": "\uC544\uB78D\uC5D0\uBBF8\uB9AC\uD2B8",
    "Iran": "\uC774\uB780",
    "Iraq": "\uC774\uB77C\uD06C",
    "Uzbekistan": "\uC6B0\uC988\uBCA0\uD0A4\uC2A4\uD0C4",
    "Jordan": "\uC694\uB974\uB2E8",
    "Oman": "\uC624\uB9CC",
    "Kuwait": "\uCFE0\uC6E8\uC774\uD2B8",
    "Bahrain": "\uBC14\uB808\uC778",
    "Syria": "\uC2DC\uB9AC\uC544",
    "Palestine": "\uD314\uB808\uC2A4\uD0C0\uC778",
    "Lebanon": "\uB808\uBC14\uB17C",
    "Yemen": "\uC608\uBA58",
    "Turkmenistan": "\uD22C\uB974\uD06C\uBA54\uB2C8\uC2A4\uD0C4",
    "Tajikistan": "\uD0C0\uC9C0\uD0A4\uC2A4\uD0C4",
    "Kazakhstan": "\uCE74\uC790\uD750\uC2A4\uD0C4",
    "Afghanistan": "\uC544\uD504\uAC00\uB2C8\uC2A4\uD0C4",
    "Maldives": "\uBAB0\uB514\uBE0C",
    "Nepal": "\uB124\uD314",
    "Sri Lanka": "\uC2A4\uB9AC\uB791\uCE74",
    "Bangladesh": "\uBC29\uAE00\uB77C\uB370\uC2DC",
    "Kyrgyzstan": "\uD0A4\uB974\uAE30\uC2A4\uC2A4\uD0C4",
    "Japan": "\uC77C\uBCF8",
    "Korea Republic": "\uB300\uD55C\uBBFC\uAD6D",
    "China PR": "\uC911\uAD6D",
    "Australia": "\uD638\uC8FC",
    "Indonesia": "\uC778\uB3C4\uB124\uC2DC\uC544",
    "Malaysia": "\uB9D0\uB808\uC774\uC2DC\uC544",
    "Thailand": "\uD0DC\uAD6D",
    "Vietnam": "\uBCA0\uD2B8\uB0A8",
    "Philippines": "\uD544\uB9AC\uD540",
    "Singapore": "\uC2F1\uAC00\uD3EC\uB974",
    "Hong Kong": "\uD64D\uCF69",
    "Chinese Taipei": "\uC911\uD654 \uD0C0\uC774\uBCA0\uC774",
    "Myanmar": "\uBBF8\uC580\uB9C8",
    "Cambodia": "\uCE84\uBCF4\uB514\uC544",
    "Laos": "\uB77C\uC624\uC2A4",
    "Brunei": "\uBE0C\uB8E8\uB098\uC774",
    "North Korea": "\uBD81\uD55C",
    "India": "\uC778\uB3C4",
    "Pakistan": "\uD30C\uD0A4\uC2A4\uD0C4",
    "Bhutan": "\uBD80\uD0C4",
    "Mongolia": "\uBABD\uACE8",
    "Macau": "\uB9C8\uCE74\uC624",
    "Palau": "\uD314\uB77C\uC6B0",
    "Timor-Leste": "\uB3D9\uD2F0\uBAA8\uB974",
    "Guam": "\uAD0C",
    "Northern Mariana Islands": "\uBD81\ub9c8\ub9ac\uc544\ub098 \uc81c\ub3c4",
}
COUNTRY_NAME_EN = {value: key for key, value in COUNTRY_NAME_KO.items()}


def display_country_name(country: str) -> str:
    return COUNTRY_NAME_KO.get(str(country), str(country))


def country_pool_key(country: str) -> str:
    value = str(country)
    return COUNTRY_NAME_EN.get(value, value)


def _association_ranking_path(region: str) -> Path:
    return ACL_WEST_RANKING_PATH if region == "west" else ACL_EAST_RANKING_PATH


def _parse_points(value: object) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError, AttributeError):
        return 0.0


CITY_COLUMN_NAMES = [f"도시명{i}" for i in range(1, 11)]


def _parse_city_names(raw: dict[str, object]) -> tuple[str, ...]:
    city_names = []
    for column in CITY_COLUMN_NAMES:
        value = str(raw.get(column, "")).strip()
        if value:
            city_names.append(value)
    return tuple(city_names)


@lru_cache(maxsize=1)
def _load_association_city_pools() -> dict[str, tuple[str, ...]]:
    pools: dict[str, tuple[str, ...]] = {}
    for region in ("east", "west"):
        path = _association_ranking_path(region)
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for raw in reader:
                source_country = str(raw.get("country", "")).strip()
                if not source_country:
                    continue
                city_names = _parse_city_names(raw)
                if city_names:
                    pools[country_pool_key(source_country)] = city_names
    return pools


def association_city_pool(country: str) -> list[str]:
    pool = _load_association_city_pools().get(country_pool_key(country))
    if pool:
        return list(pool)
    fallback = CITY_POOLS.get(country_pool_key(country))
    if fallback:
        return list(fallback)
    return [display_country_name(country)]


def _load_association_ranking_rows(region: str) -> list[dict[str, object]]:
    path = _association_ranking_path(region)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: list[dict[str, object]] = []
        for raw in reader:
            source_country = str(raw.get("country", "")).strip()
            if not source_country:
                continue
            rows.append(
                {
                    "source_slot": str(raw.get("slot_letter", "")).strip(),
                    "source_country": source_country,
                    "country_code": str(raw.get("code", "")).strip(),
                    "country": display_country_name(source_country),
                    "region": region,
                    "base_score": _parse_points(raw.get("base_points")),
                    "point_delta": _parse_points(raw.get("point_delta")),
                    "source_points": _parse_points(raw.get("points")),
                    "city_names": _parse_city_names(raw),
                }
            )
    return rows

_TEAM_ID_RE = re.compile(r"^(?P<country>.+)_(?P<slot>[A-Z])_FC(?P<index>\d+)?$")


def _looks_like_code(name: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_]+", name)) or "_FC" in name or name.startswith("T")


def _display_city_name(country: str, team_id: str, team_name: str) -> str:
    if team_name and team_name != team_id and not _looks_like_code(team_name):
        return team_name
    pool = association_city_pool(country)
    if pool:
        match = _TEAM_ID_RE.match(team_id)
        if match:
            index = int(match.group("index") or 1) - 1
            return pool[index % len(pool)]
        return pool[0]
    return team_name if team_name and team_name != team_id else team_id

ACL_TICKET_PLAN = {
    "ACL1": {
        "direct": {"A": 4, "B": 3, "C": 2, "D": 2, "E": 1, "F": 1},
        "po": {"B": 1, "C": 1, "E": 1},
    },
    "ACL2": {
        "direct": {"A": 1, "B": 1, "C": 1, "D": 1, "E": 1, "F": 1, "G": 2, "H": 1, "I": 1, "J": 1},
        "po": {"G": 1, "H": 1, "I": 1, "K": 1},
    },
    "ACL3": {
        "direct": {"H": 1, "J": 1, "K": 1, "L": 1, "M": 1, "N": 1, "O": 1, "P": 1, "Q": 1, "R": 1, "S": 1, "T": 1, "U": 1, "V": 1},
        "po": {},
    },
}


def _load_previous_acl_winner(seasons_dir: Path, year: int, league: str) -> str | None:
    path = seasons_dir / str(year - 1) / "acl.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    value = data.get("champions", {}).get(league)
    return str(value) if value else None


def _load_previous_acl_champion(
    seasons_dir: Path,
    year: int,
    league: str,
    region: str,
) -> dict[str, object] | None:
    for prev_year in range(year - 1, 1969, -1):
        path = seasons_dir / str(prev_year) / "acl.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        regional = data.get("regional_champions", {})
        if isinstance(regional, dict):
            region_entry = regional.get(league, {})
            if isinstance(region_entry, dict):
                team_id = region_entry.get(region)
                if team_id:
                    participants = data.get("participants", {}).get(league, [])
                    if isinstance(participants, list):
                        for row in participants:
                            if isinstance(row, dict) and str(row.get("team_id")) == str(team_id):
                                return {
                                    "team_id": str(row.get("team_id", team_id)),
                                    "team_name": _display_city_name(
                                        str(row.get("country", "Unknown")),
                                        str(row.get("team_id", team_id)),
                                        str(row.get("team_name", team_id)),
                                    ),
                                    "slot": "Z",
                                    "country": str(row.get("country", "Unknown")),
                                    "region": str(row.get("region", region)),
                                }
                    return {
                        "team_id": str(team_id),
                        "team_name": _display_city_name("Unknown", str(team_id), str(team_id)),
                        "slot": "Z",
                        "country": "Unknown",
                        "region": region,
                    }

        matches = data.get("matches", [])
        if isinstance(matches, list):
            region_matches = [
                row
                for row in matches
                if isinstance(row, dict)
                and str(row.get("stage", "")).lower() == f"{league}_sf".lower()
                and str(row.get("region", "")) == region
            ]
            region_matches.sort(key=lambda row: (int(row.get("match_no", 0)), int(row.get("leg", 0)), str(row.get("id", ""))))
            if len(region_matches) >= 2:
                leg1, leg2 = region_matches[:2]
                home_agg = int(leg1.get("home_score", 0) or 0) + int(leg2.get("away_score", 0) or 0)
                away_agg = int(leg1.get("away_score", 0) or 0) + int(leg2.get("home_score", 0) or 0)
                if home_agg > away_agg:
                    team_id = str(leg1.get("home_team_id", ""))
                elif away_agg > home_agg:
                    team_id = str(leg1.get("away_team_id", ""))
                else:
                    team_id = str(leg2.get("winner_team_id") or leg2.get("home_team_id") or leg2.get("away_team_id") or "")
                participants = data.get("participants", {}).get(league, [])
                if isinstance(participants, list):
                    for row in participants:
                        if isinstance(row, dict) and str(row.get("team_id")) == team_id:
                            return {
                                "team_id": str(row.get("team_id", team_id)),
                                "team_name": _display_city_name(
                                    str(row.get("country", "Unknown")),
                                    str(row.get("team_id", team_id)),
                                    str(row.get("team_name", team_id)),
                                ),
                                "slot": "Z",
                                "country": str(row.get("country", "Unknown")),
                                "region": str(row.get("region", region)),
                            }
                if team_id:
                    return {
                        "team_id": team_id,
                        "team_name": _display_city_name("Unknown", team_id, team_id),
                        "slot": "Z",
                        "country": "Unknown",
                        "region": region,
                    }
    return None


def _fallback_acl_champion(
    region_rows: Sequence[dict[str, object]],
    factory: "TeamFactory",
    rng: random.Random,
) -> dict[str, object] | None:
    weighted_rows: list[dict[str, object]] = []
    weights: list[int] = []
    for row in region_rows:
        if bool(row.get("reserve")):
            continue
        weight = int(round(float(row.get("base_score", 0.0)) * 1000))
        if weight <= 0:
            continue
        weighted_rows.append(dict(row))
        weights.append(weight)

    if not weighted_rows:
        return None

    row = rng.choices(weighted_rows, weights=weights, k=1)[0]
    team_id = factory.next_team(
        "Z",
        str(row["country"]),
        str(row["region"]),
        source_country=str(row.get("country_code", row["country"])),
    )
    return {
        "team_id": team_id,
        "team_name": factory.name(team_id),
        "slot": factory.slot(team_id),
        "country": factory.country(team_id),
        "region": factory.region(team_id),
    }


def _region_seed(seed: int, region: str) -> int:
    return seed if region == "west" else seed + 1


def _build_region_rankings(seed: int, region: str, include_korea: bool = True) -> list[dict[str, object]]:
    rng = random.Random(_region_seed(seed, region))
    rows: list[dict[str, object]] = []
    for row in _load_association_ranking_rows(region):
        if region == "east" and not include_korea and str(row["country"]) == "대한민국":
            continue
        ranked_row = dict(row)
        ranked_row["adjusted_score"] = float(ranked_row["base_score"]) + rng.randint(-5, 5)
        rows.append(ranked_row)

    rows.sort(
        key=lambda row: (
            1 if row.get("reserve") else 0,
            -float(row["adjusted_score"]),
            str(row["country"]),
            str(row["source_slot"]),
        ),
    )

    if len(rows) > len(RANKING_SLOTS):
        raise ValueError(f"{region} ranking needs more than {len(RANKING_SLOTS)} slots: {len(rows)}")

    for idx, row in enumerate(rows, start=1):
        row["slot"] = RANKING_SLOTS[idx - 1]
        row["regional_rank"] = idx
    return rows


def rank_countries(seed: int, include_korea: bool = True) -> list[dict[str, object]]:
    west = _build_region_rankings(seed, "west", include_korea=True)
    east = _build_region_rankings(seed, "east", include_korea=include_korea)
    ranked = west + east
    for idx, row in enumerate(ranked, start=1):
        row["rank"] = idx
    return ranked


def _ranked_countries(rankings: Sequence[dict[str, object]], region: str) -> list[dict[str, object]]:
    rows = [row for row in rankings if row["region"] == region]
    rows.sort(key=lambda row: int(row["regional_rank"]))
    return rows


def _expand_slot_quotas(
    region_rows: Sequence[dict[str, object]],
    factory: "TeamFactory",
    quotas: dict[str, int],
    exclude_team_ids: set[str] | None = None,
) -> list[str]:
    teams: list[str] = []
    rows_by_slot = {str(row["slot"]): row for row in region_rows}
    excluded = exclude_team_ids or set()
    for slot in REGIONAL_SLOTS:
        count = int(quotas.get(slot, 0))
        if count <= 0:
            continue
        row = rows_by_slot.get(slot)
        if row is None:
            continue
        while sum(1 for team in teams if factory.slot(team) == slot) < count:
            team_id = factory.next_team(
                str(row["slot"]),
                str(row["country"]),
                str(row["region"]),
                source_country=str(row.get("country_code", row["country"])),
            )
            if team_id in excluded:
                continue
            teams.append(team_id)
    return teams


def _normalize_region_team_list(
    region_rows: Sequence[dict[str, object]],
    factory: "TeamFactory",
    teams: Sequence[str],
    target_count: int,
) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()

    for team in teams:
        if team in seen:
            continue
        normalized.append(team)
        seen.add(team)

    attempts = 0
    max_attempts = max(len(region_rows) * 4, target_count * 2)
    while len(normalized) < target_count and attempts < max_attempts:
        attempts += 1
        for row in reversed(region_rows):
            candidate = factory.next_team(
                str(row["slot"]),
                str(row["country"]),
                str(row["region"]),
                source_country=str(row.get("country_code", row["country"])),
            )
            if candidate in seen:
                continue
            normalized.append(candidate)
            seen.add(candidate)
            if len(normalized) >= target_count:
                return normalized[:target_count]

    if len(normalized) < target_count:
        for row in reversed(region_rows):
            country = str(row["country"])
            slot = str(row["slot"])
            region = str(row["region"])
            source_country = str(row.get("source_country", row["country"]))
            source_country = str(row.get("country_code", source_country))
            base = factory._team_base(country, slot, source_country)
            candidate = base
            suffix = 1
            while candidate in seen or candidate in factory.used_team_ids:
                suffix += 1
                candidate = f"{base}{suffix}"
            factory.register(candidate, slot, country, region, factory._claim_country_team_name(country))
            normalized.append(candidate)
            seen.add(candidate)
            if len(normalized) >= target_count:
                break

    return normalized[:target_count]


def _super_cup_acl_candidates(super_cup: dict[str, object] | None, teams: Sequence[Team]) -> list[dict[str, object]]:
    names = {team.id: team.name for team in teams}
    if not super_cup or not super_cup.get("held"):
        return []
    entrants_by_id = {
        str(entrant.get("team_id")): entrant
        for entrant in super_cup.get("entrants", [])
        if isinstance(entrant, dict) and entrant.get("team_id")
    }
    standings = super_cup.get("standings")
    source_rows = standings if isinstance(standings, list) and standings else super_cup.get("entrants", [])
    rows = []
    for source in source_rows:
        if not isinstance(source, dict):
            continue
        team_id = str(source["team_id"])
        entrant = entrants_by_id.get(team_id, {})
        base_points = int(entrant.get("points", 0))
        final_points = int(source.get("points", base_points))
        table_points = int(source.get("super_cup_table_points", final_points - base_points))
        rows.append(
            {
                "team_id": team_id,
                "team_name": names.get(team_id, str(source.get("team_name", entrant.get("team_name", team_id)))),
                "slot": "B",
                "country": "대한민국",
                "region": "east",
                "league_rank": entrant.get("league_rank"),
                "super_cup_points": base_points,
                "super_cup_table_points": table_points,
                "acl_score": final_points,
            }
        )
    rows.sort(key=lambda row: (-int(row["acl_score"]), -int(row["super_cup_table_points"]), str(row["team_name"])))
    return rows


class TeamFactory:
    def __init__(self, korean_candidates: Sequence[dict[str, object]]):
        self.korean_candidates = list(korean_candidates)
        self.country_index: dict[tuple[str, str], int] = {}
        self.country_city_index: dict[str, int] = {}
        self.team_slot: dict[str, str] = {}
        self.team_country: dict[str, str] = {}
        self.team_region: dict[str, str] = {}
        self.team_name: dict[str, str] = {}
        self.used_team_ids: set[str] = set()
        self.used_team_names: set[str] = set()
        self.country_used_team_names: dict[str, set[str]] = {}

    def _team_base(self, country: str, slot: str, source_country: str | None = None) -> str:
        source = str(source_country or country)
        english_country = COUNTRY_NAME_EN.get(source, source)
        safe = "".join(ch if ch.isalnum() else "_" for ch in english_country).strip("_")
        return f"{safe}_{slot}_FC"

    def _team_name(self, country: str, index: int) -> str:
        pool = association_city_pool(country)
        return pool[index % len(pool)]

    def _claim_country_team_name(self, country: str, preferred: str | None = None) -> str:
        country_key = country_pool_key(country)
        used = self.country_used_team_names.setdefault(country_key, set())
        pool = association_city_pool(country)

        if preferred and preferred not in used and preferred not in self.used_team_names:
            used.add(preferred)
            self.used_team_names.add(preferred)
            return preferred

        if not pool:
            fallback = display_country_name(country)
            used.add(fallback)
            self.used_team_names.add(fallback)
            return fallback

        start = self.country_city_index.get(country_key, 0)
        for offset in range(len(pool)):
            candidate = pool[(start + offset) % len(pool)]
            if candidate in used or candidate in self.used_team_names:
                continue
            self.country_city_index[country_key] = (start + offset + 1) % len(pool)
            used.add(candidate)
            self.used_team_names.add(candidate)
            return candidate

        candidate = preferred if preferred and preferred in pool else pool[start % len(pool)]
        self.country_city_index[country_key] = (start + 1) % len(pool)
        used.add(candidate)
        self.used_team_names.add(candidate)
        return candidate

    def next_team(self, slot: str, country: str, region: str, source_country: str | None = None) -> str:
        index = self.country_index.get((region, slot), 0)
        self.country_index[(region, slot)] = index + 1
        source = source_country or country

        if region == "east" and slot == "B" and index < len(self.korean_candidates):
            candidate = self.korean_candidates[index]
            team_id = str(candidate["team_id"])
            team_name = self._claim_country_team_name(country, preferred=str(candidate.get("team_name", team_id)))
        else:
            team_id = self._team_base(country, slot, source)
            if index > 0:
                team_id = f"{team_id}{index + 1}"
            team_name = self._claim_country_team_name(country)
        while team_id in self.used_team_ids:
            team_id = f"{team_id}2"
        self.used_team_ids.add(team_id)
        self.team_slot[team_id] = slot
        self.team_country[team_id] = display_country_name(country)
        self.team_region[team_id] = region
        self.team_name[team_id] = team_name
        return team_id

    def register(
        self,
        team_id: str,
        slot: str,
        country: str,
        region: str,
        team_name: str | None = None,
    ) -> str:
        if team_id in self.used_team_ids:
            suffix = 2
            base = team_id
            while f"{base}{suffix}" in self.used_team_ids:
                suffix += 1
            team_id = f"{base}{suffix}"
        self.used_team_ids.add(team_id)
        self.team_slot[team_id] = slot
        self.team_country[team_id] = display_country_name(country)
        self.team_region[team_id] = region
        team_name = self._claim_country_team_name(country, preferred=team_name) if team_name else self._claim_country_team_name(country)
        self.team_name[team_id] = team_name or self.team_name.get(team_id, team_id)
        return team_id

    def slot(self, team_id: str) -> str:
        return self.team_slot.get(team_id, "Z")

    def country(self, team_id: str) -> str:
        return self.team_country.get(team_id, "Unknown")

    def region(self, team_id: str) -> str:
        return self.team_region.get(team_id, "west")

    def name(self, team_id: str) -> str:
        return self.team_name.get(team_id, team_id)


def _pick_winner(home: str, away: str, rng: random.Random, mode: str) -> str:
    return home if mode == "higher_seed" else rng.choice([home, away])


def _po_pair_penalty(home: str, away: str, factory: "TeamFactory") -> tuple[int, int, int, str]:
    return (
        1000 if factory.country(home) == factory.country(away) else 0,
        100 if factory.slot(home) == factory.slot(away) else 0,
        10 if factory.region(home) == factory.region(away) else 0,
        "".join(sorted([home, away])),
    )


def _best_po_pairings(teams: Sequence[str], factory: "TeamFactory", rng: random.Random) -> list[tuple[str, str]]:
    pool = list(teams)
    rng.shuffle(pool)
    if len(pool) < 2:
        return []

    best_pairs: list[tuple[str, str]] | None = None
    best_score: tuple[int, tuple[str, ...]] | None = None

    def recurse(remaining: list[str], pairs: list[tuple[str, str]], penalty: int) -> None:
        nonlocal best_pairs, best_score
        if not remaining:
            signature = tuple("::".join(pair) for pair in pairs)
            score = (penalty, signature)
            if best_score is None or score < best_score:
                best_score = score
                best_pairs = list(pairs)
            return

        first = remaining[0]
        for idx in range(1, len(remaining)):
            second = remaining[idx]
            pair_penalty = _po_pair_penalty(first, second, factory)
            next_remaining = remaining[1:idx] + remaining[idx + 1 :]
            recurse(
                next_remaining,
                pairs + [(first, second)],
                penalty + pair_penalty[0] + pair_penalty[1] + pair_penalty[2],
            )

    recurse(pool, [], 0)
    if best_pairs is None:
        return [(pool[idx], pool[idx + 1]) for idx in range(0, len(pool) - 1, 2)]
    return best_pairs


def _po_match(
    league: str,
    match_no: int,
    home: str,
    away: str,
    winner: str,
    loser: str,
    region: str,
    winner_to: str,
    loser_to: str,
    leg: int = 1,
    home_score: int | None = None,
    away_score: int | None = None,
) -> dict[str, object]:
    return {
        "league": league,
        "stage": f"{league}_po",
        "round": "PO",
        "week": 3,
        "region": region,
        "match_no": match_no,
        "leg": leg,
        "home_team_id": home,
        "away_team_id": away,
        "home_score": home_score,
        "away_score": away_score,
        "winner": winner,
        "loser": loser,
        "winner_to": winner_to,
        "loser_to": loser_to,
    }


def _po_match_object(
    league: str,
    match_no: int,
    home: str,
    away: str,
    region: str,
    leg: int = 1,
) -> Match:
    return Match(
        id=f"{league}-{region}-PO-{match_no:03d}",
        competition="acl",
        stage=f"{league}_po",
        round="PO",
        week=3,
        match_no=match_no,
        home_team_id=home,
        away_team_id=away,
        region=region,
        day="수",
        leg=leg,
    )


def _group_draw(
    teams: Sequence[str],
    labels: Sequence[str],
    factory: TeamFactory,
    rng: random.Random,
    max_retry: int = 10000,
) -> dict[str, list[str]]:
    country_buckets: dict[str, list[str]] = {}
    for team in teams:
        country_buckets.setdefault(factory.country(team), []).append(team)

    countries = list(country_buckets.keys())
    rng.shuffle(countries)
    countries.sort(key=lambda country: (len(country_buckets[country]), country), reverse=True)
    for members in country_buckets.values():
        rng.shuffle(members)

    groups = {group: [] for group in labels}
    group_countries = {group: set() for group in labels}
    group_slots = {group: set() for group in labels}

    for country in countries:
        for team in country_buckets[country]:
            available_groups = [group for group in labels if len(groups[group]) < 4]
            if not available_groups:
                raise RuntimeError(f"ACL group draw failed: {labels}")

            team_slot = factory.slot(team)

            def _score(group: str) -> tuple[int, int, int, float]:
                return (
                    1 if country in group_countries[group] else 0,
                    1 if team_slot in group_slots[group] else 0,
                    len(groups[group]),
                    rng.random(),
                )

            chosen = min(available_groups, key=_score)
            groups[chosen].append(team)
            group_countries[chosen].add(country)
            group_slots[chosen].add(team_slot)

    if not all(len(members) == 4 for members in groups.values()):
        raise RuntimeError(f"ACL group draw failed: {labels}")
    return groups


def _group_rounds(members: Sequence[str]) -> list[list[tuple[str, str]]]:
    a, b, c, d = members
    return [
        [(a, b), (c, d)],
        [(d, a), (b, c)],
        [(a, c), (b, d)],
        [(b, a), (d, c)],
        [(c, a), (d, b)],
        [(a, d), (c, b)],
    ]


def _group_schedule(groups: dict[str, list[str]], league: str, factory: TeamFactory) -> list[Match]:
    matches = []
    match_no = 1
    for group_name, members in groups.items():
        region = "west" if group_name in WEST_GROUPS else "east"
        for round_no, round_matches in enumerate(_group_rounds(members), start=1):
            for home, away in round_matches:
                matches.append(
                    Match(
                        id=f"{league}-G{group_name}-R{round_no}-{match_no:03d}",
                        competition="acl",
                        stage=f"{league}_group",
                        round=round_no,
                        week=GROUP_WEEKS[round_no],
                        match_no=match_no,
                        group=group_name,
                        home_team_id=home,
                        away_team_id=away,
                        region=region,
                    )
                )
                match_no += 1
    return matches


def _regional_slots(label: str, region: str, count: int) -> list[str]:
    prefix = "west" if region == "west" else "east"
    return [f"{prefix}_{label}_{idx}" for idx in range(1, count + 1)]


def _two_leg_matches(
    league: str,
    stage: str,
    label: str,
    weeks: Sequence[int],
    region: str,
    slots: Sequence[str],
) -> list[Match]:
    rows = []
    for idx in range(0, len(slots), 2):
        home = slots[idx]
        away = slots[idx + 1]
        match_no = (idx // 2) + 1
        rows.append(
            Match(
                id=f"{league}-{region}-{label}-{match_no:03d}-1",
                competition="acl",
                stage=f"{league}_{stage}",
                round=label,
                week=weeks[0],
                match_no=match_no,
                home_team_id=home,
                away_team_id=away,
                leg=1,
                region=region,
            )
        )
        rows.append(
            Match(
                id=f"{league}-{region}-{label}-{match_no:03d}-2",
                competition="acl",
                stage=f"{league}_{stage}",
                round=label,
                week=weeks[1],
                match_no=match_no,
                home_team_id=away,
                away_team_id=home,
                leg=2,
                region=region,
            )
        )
    return rows


def _knockout_matches(league: str, year: int) -> list[Match]:
    rows = []
    for region in ["west", "east"]:
        rows.extend(_two_leg_matches(league, "r16", "R16", [19, 20], region, _regional_slots("R16", region, 8)))
        rows.extend(_two_leg_matches(league, "qf", "QF", [23, 24], region, _regional_slots("QF", region, 4)))
        rows.extend(_two_leg_matches(league, "sf", "SF", [27, 28], region, _regional_slots("SF", region, 2)))

    west_home = year % 2 == 1
    home = "west_SF_1" if west_home else "east_SF_1"
    away = "east_SF_1" if west_home else "west_SF_1"
    rows.append(
        Match(
            id=f"{league}-FINAL-001",
            competition="acl",
            stage=f"{league}_final",
            round="Final",
            week=32,
            match_no=1,
            home_team_id=home,
            away_team_id=away,
            region="final",
        )
    )
    return rows


def _make_region_teams(entries: Sequence[dict[str, object]], factory: TeamFactory, count: int) -> list[str]:
    teams = []
    idx = 0
    while len(teams) < count:
        row = entries[idx % len(entries)]
        teams.append(
            factory.next_team(
                str(row["slot"]),
                str(row["country"]),
                str(row["region"]),
                source_country=str(row.get("country_code", row["country"])),
            )
        )
        idx += 1
    return teams


def _make_po_rows(
    league: str,
    teams: Sequence[str],
    factory: TeamFactory,
    rng: random.Random,
    mode: str,
    region: str,
    winner_to: str,
    loser_to: str,
) -> tuple[list[dict[str, object]], list[str], list[str], list[Match]]:
    rows = []
    winners = []
    losers = []
    matches: list[Match] = []
    pairings = _best_po_pairings(teams, factory, rng)
    if not pairings and teams:
        pairings = [(teams[0], "")]
    for idx, (home, away) in enumerate(pairings, start=1):
        if not away:
            winners.append(home)
            rows.append(
                _po_match(
                    league,
                    idx,
                    home,
                    "",
                    home,
                    "",
                    region,
                    winner_to,
                    loser_to,
                    leg=1,
                    home_score=0,
                    away_score=0,
                )
            )
            continue
        match = _po_match_object(league, idx, home, away, region, leg=1)
        simulate_match(match, rng, decisive=True)
        winner = match.winner_team_id or home
        loser = match.loser_team_id or (away if winner == home else home)
        winners.append(winner)
        losers.append(loser)
        rows.append(
            _po_match(
                league,
                idx,
                home,
                away,
                winner,
                loser,
                region,
                winner_to,
                loser_to,
                leg=1,
                home_score=int(match.home_score or 0),
                away_score=int(match.away_score or 0),
            )
        )
        matches.append(match)
    return rows, winners, losers, matches


def generate_acl(
    teams: Sequence[Team],
    super_cup: dict[str, object] | None,
    seasons_dir: Path,
    year: int,
    seed: int = 7,
    po_winner_mode: str = "random",
) -> dict[str, object]:
    super_cup_held = bool(super_cup and super_cup.get("held"))
    korean_candidates = _super_cup_acl_candidates(super_cup, teams) if super_cup_held else []
    if super_cup_held and len(korean_candidates) < 5:
        return {
            "held": False,
            "reason": "ACL requires at least 5 Super Cup Korea qualifiers.",
            "matches": [],
        }

    rng = random.Random(seed)
    rankings = rank_countries(seed, include_korea=super_cup_held)
    factory = TeamFactory(korean_candidates)
    previous_acl_path = seasons_dir / str(year - 1) / "acl.json"
    previous_acl_payload: dict[str, object] | None = None
    if previous_acl_path.exists():
        try:
            loaded = json.loads(previous_acl_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            loaded = None
        if isinstance(loaded, dict):
            previous_acl_payload = loaded
    previous_acl_held = bool(previous_acl_payload and previous_acl_payload.get("held"))

    league_regions: dict[str, dict[str, list[str]]] = {
        "ACL1": {"west": [], "east": []},
        "ACL2": {"west": [], "east": []},
        "ACL3": {"west": [], "east": []},
    }
    po_rows: list[dict[str, object]] = []
    po_matches: list[Match] = []

    for region in ["west", "east"]:
        region_rows = _ranked_countries(rankings, region)

        if previous_acl_held:
            previous_acl1_champion = _load_previous_acl_champion(seasons_dir, year, "ACL1", region)
            previous_acl2_champion = _load_previous_acl_champion(seasons_dir, year, "ACL2", region)
            previous_acl3_champion = _load_previous_acl_champion(seasons_dir, year, "ACL3", region)
        else:
            previous_acl1_champion = _fallback_acl_champion(region_rows, factory, rng)
            previous_acl2_champion = _fallback_acl_champion(region_rows, factory, rng)
            previous_acl3_champion = _fallback_acl_champion(region_rows, factory, rng)

        region_champions = [champion for champion in [previous_acl1_champion, previous_acl2_champion, previous_acl3_champion] if champion is not None]
        champion_ids = {str(champion["team_id"]) for champion in region_champions}

        if previous_acl_held:
            for champion in region_champions:
                    factory.register(
                        str(champion["team_id"]),
                        str(champion["slot"]),
                        str(champion["country"]),
                        str(champion["region"]),
                        str(champion.get("team_name", champion["team_id"])),
                    )

        acl1_direct = _expand_slot_quotas(
            region_rows,
            factory,
            ACL_TICKET_PLAN["ACL1"]["direct"],
            exclude_team_ids=champion_ids,
        )
        if (
            previous_acl1_champion
            and str(previous_acl1_champion["region"]) == region
            and str(previous_acl1_champion["team_id"]) not in acl1_direct
        ):
            acl1_direct.append(str(previous_acl1_champion["team_id"]))
        acl1_po_pool = _expand_slot_quotas(
            region_rows,
            factory,
            ACL_TICKET_PLAN["ACL1"]["po"],
            exclude_team_ids=champion_ids,
        )
        if (
            previous_acl2_champion
            and str(previous_acl2_champion["region"]) == region
            and str(previous_acl2_champion["team_id"]) not in acl1_po_pool
        ):
            acl1_po_pool.append(str(previous_acl2_champion["team_id"]))
        acl1_po_rows, acl1_winners, acl1_losers, acl1_po_matches = _make_po_rows(
            "ACL1",
            acl1_po_pool,
            factory,
            rng,
            po_winner_mode,
            region,
            "ACL1",
            "ACL2",
        )

        acl2_direct = _expand_slot_quotas(
            region_rows,
            factory,
            ACL_TICKET_PLAN["ACL2"]["direct"],
            exclude_team_ids=champion_ids,
        )
        if (
            previous_acl3_champion
            and str(previous_acl3_champion["region"]) == region
            and str(previous_acl3_champion["team_id"]) not in acl2_direct
        ):
            acl2_direct.append(str(previous_acl3_champion["team_id"]))
        acl2_po_pool = _expand_slot_quotas(
            region_rows,
            factory,
            ACL_TICKET_PLAN["ACL2"]["po"],
            exclude_team_ids=champion_ids,
        )
        acl2_po_team_ids = set(acl2_po_pool)
        acl2_po_rows, acl2_winners, acl2_losers, acl2_po_matches = _make_po_rows(
            "ACL2",
            acl2_po_pool,
            factory,
            rng,
            po_winner_mode,
            region,
            "ACL2",
            "ACL3",
        )

        upper_league_team_ids = {
            *acl1_direct,
            *acl1_winners,
            *acl1_losers,
            *acl2_direct,
            *acl2_winners,
            *acl2_losers,
        }
        acl3_direct = _expand_slot_quotas(
            region_rows,
            factory,
            ACL_TICKET_PLAN["ACL3"]["direct"],
            exclude_team_ids=champion_ids | acl2_po_team_ids | upper_league_team_ids,
        )

        po_rows.extend(acl1_po_rows)
        po_rows.extend(acl2_po_rows)
        po_matches.extend(acl1_po_matches)
        po_matches.extend(acl2_po_matches)

        league_regions["ACL1"][region] = _normalize_region_team_list(region_rows, factory, acl1_direct + acl1_winners, 16)
        league_regions["ACL2"][region] = _normalize_region_team_list(region_rows, factory, acl2_direct + acl1_losers + acl2_winners, 16)
        league_regions["ACL3"][region] = _normalize_region_team_list(
            region_rows,
            factory,
            acl3_direct + acl2_losers,
            16,
        )

    leagues: dict[str, list[str]] = {}
    for league in ["ACL1", "ACL2", "ACL3"]:
        league_teams = league_regions[league]["west"] + league_regions[league]["east"]
        if len(league_teams) != 32 or len(set(league_teams)) != 32:
            raise ValueError(f"{league} participants must be 32 unique teams: {league_teams}")
        leagues[league] = league_teams

    groups = {}
    for league, league_teams in leagues.items():
        groups[league] = {
            **_group_draw(league_regions[league]["west"], WEST_GROUPS, factory, rng),
            **_group_draw(league_regions[league]["east"], EAST_GROUPS, factory, rng),
        }

    matches: list[Match] = []
    matches.extend(po_matches)
    for league, league_groups in groups.items():
        matches.extend(_group_schedule(league_groups, league, factory))
        matches.extend(_knockout_matches(league, year))

    participants: dict[str, list[dict[str, object]]] = {}
    for league in ["ACL1", "ACL2", "ACL3"]:
        rows: list[dict[str, object]] = []
        for region in ["west", "east"]:
            for team in league_regions[league][region]:
                rows.append(
                    {
                        "team_id": team,
                        "team_name": factory.name(team),
                        "slot": factory.slot(team),
                        "country": factory.country(team),
                        "region": region,
                    }
                )
        participants[league] = rows

    return {
        "held": True,
        "country_rankings": rankings,
        "korea_slot": "B",
        "korea_country": "\uB300\uD55C\uBBFC\uAD6D",
        "korean_qualifiers": korean_candidates[:5],
        "last_champions": {
            "ACL2": _load_previous_acl_winner(seasons_dir, year, "ACL2") or "Previous ACL2 champion",
            "ACL3": _load_previous_acl_winner(seasons_dir, year, "ACL3") or "Previous ACL3 champion",
        },
        "participants": participants,
        "po": po_rows,
        "groups": groups,
        "matches": matches,
        "final_home_region": "west" if year % 2 == 1 else "east",
        "champions": {},
    }
