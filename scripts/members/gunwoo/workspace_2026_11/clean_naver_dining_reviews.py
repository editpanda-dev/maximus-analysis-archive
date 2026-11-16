"""네이버 지도 식사 리뷰(maximus_dining_naver_reviews_v1.csv) 정제.

실행:
    ~/.venvs/maximus/bin/python 분석/clean_naver_dining_reviews.py <원본.csv> [출력폴더]

출력 (기본 데이터/가공/naver_reviews/):
    dining_reviews_clean.csv    분석용 정제본
    dining_reviews_excluded.csv 제외 행 + 사유
    place_store_conflicts.csv   한 place_id에 여러 store_id가 붙은 목록 (수동 검토용)
"""
import re
import sys
from pathlib import Path

import pandas as pd

COLLECT_YEAR = 2026  # 연도 없는 방문일 = 수집 연도 (요일 검증 100% 일치)
WEEKDAYS = "월화수목금토일"
ERROR_TEXT = "일시적인 오류가 발생했습니다"
UI_TEXT = "표정을 눌러 반응을 남겨 보세요!"
# 네이버가 본문 끝에 붙이는 음식점 추가 태그. 본문이 실제로 이 문장으로 끝나도 태그로 떼어진다.
EXTRA_TAGS = [
    "양이 많아요", "특별한 메뉴가 있어요", "인테리어가 멋져요", "메뉴 구성이 알차요",
    "음식이 빨리 나와요", "건강한 맛이에요", "반찬이 잘 나와요", "직접 잘 구워줘요",
    "잡내가 적어요", "술이 다양해요", "화장실이 깨끗해요", "현지 맛에 가까워요",
    "컨셉이 독특해요", "비싼 만큼 가치있어요", "주차하기 편해요", "야외공간이 멋져요",
    "좌석이 편해요", "코스요리가 알차요", "룸이 잘 되어있어요", "향신료가 강하지 않아요",
    "종류가 다양해요", "환기가 잘 돼요", "가격이 합리적이에요", "샐러드바가 잘 되어있어요",
    "세트 구성이 알차요", "라이브공연이 훌륭해요",
]
TAG_RE = re.compile(r"(?:^|\s)(" + "|".join(map(re.escape, EXTRA_TAGS)) + r")$")
# 키워드 칸에 들어오는 네이버 공식 키워드(방문자가 고르는 칩). 크롤러 폴백 파서가 '맛있어요'·'좋아요'가 든
# 20자 이하 본문 줄도 키워드로 넣기 때문에, 이 목록과 EXTRA_TAGS에 없는 항목은 본문 조각으로 돌려보낸다.
# 목록은 2026-11-12 DB에서 여러 가게에 같은 문구로 반복되는 항목을 보고 정했다.
KEYWORD_CHIPS = [
    "음식이 맛있어요", "친절해요", "가성비가 좋아요", "재료가 신선해요", "매장이 청결해요",
    "혼밥하기 좋아요", "매장이 넓어요", "단체모임 하기 좋아요", "고기 질이 좋아요", "아늑해요",
    "대화하기 좋아요", "차분한 분위기예요", "음악이 좋아요", "특별한 날 가기 좋아요", "뷰가 좋아요",
    "기본 안주가 좋아요", "음료가 맛있어요", "혼술하기 좋아요", "아이와 가기 좋아요", "포장이 깔끔해요",
    "오래 머무르기 좋아요", "디저트가 맛있어요", "커피가 맛있어요", "집중하기 좋아요",
    "반려동물과 가기 좋아요", "빵이 맛있어요", "선물하기 좋아요", "비주얼이 좋아요",
    "분위기가 편안해요", "시설이 깔끔해요", "품질이 좋아요", "차가 맛있어요", "파티하기 좋아요",
    "사진이 잘 나와요",
]
CHIPS = set(KEYWORD_CHIPS) | set(EXTRA_TAGS)
VALID_RATINGS = {x / 2 for x in range(1, 11)}  # 0.5 ~ 5.0, 0.5 단위


def parse_visit_date(s: str):
    m = re.fullmatch(r"(?:(\d{2})\.)?(\d{1,2})\.(\d{1,2})\.([월화수목금토일])", s)
    if not m:
        return pd.NaT
    yy, mm, dd, wd = m.groups()
    year = 2000 + int(yy) if yy else COLLECT_YEAR
    try:
        d = pd.Timestamp(year, int(mm), int(dd))
    except ValueError:
        return pd.NaT
    return d if WEEKDAYS[d.weekday()] == wd else pd.NaT


def split_text(text: str):
    """본문에서 오류·UI 문구를 지우고 끝에 붙은 추가 태그를 떼어낸다."""
    text = text.replace(UI_TEXT, " ")
    text = re.sub(rf"^(?:{ERROR_TEXT}\s*)?동영상\s*", "", text.strip())
    text = text.replace(ERROR_TEXT, " ")
    text = re.sub(r"\s+", " ", text).strip()
    tags = []
    while (m := TAG_RE.search(text)):
        tags.insert(0, m.group(1))
        text = text[: m.start()].strip()
    return text, ", ".join(tags)


def clean_keywords(s: str):
    """키워드 칸을 공식 키워드와 본문 조각으로 나눈다. (키워드, 본문 조각)"""
    chips, frags = [], []
    for k in s.split(", "):  # 본문 조각 안의 쉼표는 공백이 없어 깨지지 않는다
        k = k.strip()
        if k in CHIPS:
            if k not in chips:
                chips.append(k)
        elif k:
            frags.append(k)
    return ", ".join(chips), " ".join(frags)


def parse_rating(s: str):
    try:
        v = float(s)
    except ValueError:
        return None
    return v if v in VALID_RATINGS else None


def main(src: Path, out_dir: Path):
    df = pd.read_csv(src, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    n0 = len(df)

    # 1) 제외 대상: 상권 메타 없는 비식당 행(semas 외 ID), 같은 가게 안 완전 중복
    reason = pd.Series("", index=df.index)
    reason[~df.store_id.str.startswith("semas:")] = "non_semas_store_no_meta"
    content = ["store_id", "place_id", "author_name", "visit_date", "visit_count", "keywords", "review_text"]
    reason[(reason == "") & df.duplicated(content)] = "duplicate_in_store"
    excluded = df[reason != ""].assign(exclude_reason=reason[reason != ""])
    df = df[reason == ""].copy()

    # 2) 필드 정제
    df["naver_place_name"] = df.naver_place_name.replace(ERROR_TEXT, "")
    df["visit_date_raw"] = df.visit_date
    df["visit_date"] = df.visit_date.map(parse_visit_date)
    df["row_shifted"] = df.visit_date.isna()  # 방문일 칸에 동행 태그·본문 조각이 들어간 행
    df["visit_count"] = df.visit_count.str.extract(r"(\d+)\s*번째")[0].astype("Int64")
    df["rating"] = df.rating.map(parse_rating).astype("Float64")
    kw = df.keywords.map(clean_keywords)
    df["keywords"] = kw.str[0]
    df["review_text"] = (kw.str[1] + " " + df.review_text).str.strip()  # 키워드 칸에 잘못 간 본문 줄을 앞에 붙임
    split = df.review_text.map(split_text)
    df["review_text"] = split.str[0]
    df["extra_tags"] = split.str[1]

    # 3) place 공유 플래그 + 검토 목록
    n_store = df.groupby("place_id").store_id.transform("nunique")
    df["place_shared"] = n_store > 1
    conflicts = (
        df[df.place_shared]
        .groupby(["place_id", "store_id"], as_index=False)
        .agg(store_name=("store_name", "first"), address=("address", "first"),
             area_name=("area_name", "first"), naver_place_name=("naver_place_name", "max"),
             n_reviews=("review_id", "size"))
        .sort_values(["place_id", "store_id"])
    )

    # 4) 매칭 판정으로 틀린 가게 쪽 리뷰 제외.
    #    judge_naver_match.py 판정(가게 전체, 네이버 주소·이름 기준)이 있으면 그것을, 없으면 옛 공유 판정을 쓴다.
    #    conflicts 목록은 위에서 제외 전 기준으로 만들어 재판정 때 전체가 유지된다.
    judge_path = out_dir / "store_match_judgment.csv"
    res_path = out_dir / "place_store_resolution.csv"
    if judge_path.exists():
        j = pd.read_csv(judge_path, dtype=str, keep_default_na=False)[["store_id", "match_status", "keep"]]
        df = df.merge(j, on="store_id", how="left").fillna({"match_status": "not_judged", "keep": "True"})
        mask = df.keep == "False"
        excluded = pd.concat([excluded, df[mask].assign(exclude_reason="match_" + df.match_status[mask])])
        df = df[~mask].drop(columns="keep").copy()
        df["place_shared"] = df.groupby("place_id").store_id.transform("nunique") > 1
    elif res_path.exists():
        res = pd.read_csv(res_path, dtype=str, keep_default_na=False)
        drop = set(zip(res.place_id[res.keep == "False"], res.store_id[res.keep == "False"]))
        mask = pd.Series([(p, s) in drop for p, s in zip(df.place_id, df.store_id)], index=df.index)
        excluded = pd.concat([excluded, df[mask].assign(exclude_reason="place_mismatch")])
        df = df[~mask].copy()
        df["place_shared"] = df.groupby("place_id").store_id.transform("nunique") > 1

    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / "dining_reviews_clean.csv", index=False, encoding="utf-8-sig")
    excluded.to_csv(out_dir / "dining_reviews_excluded.csv", index=False, encoding="utf-8-sig")
    conflicts.to_csv(out_dir / "place_store_conflicts.csv", index=False, encoding="utf-8-sig")

    print(f"원본 {n0}행 → 정제 {len(df)}행 (제외 {len(excluded)}: {excluded.exclude_reason.value_counts().to_dict()})")
    print(f"방문일 파싱 실패(row_shifted) {int(df.row_shifted.sum())}행")
    print(f"유효 별점 {int(df.rating.notna().sum())}행, 결측/이상 {int(df.rating.isna().sum())}행")
    print(f"추가 태그 분리 {int((df.extra_tags != '').sum())}행, 본문 빈 행 {int((df.review_text == '').sum())}")
    print(f"place 공유 {df[df.place_shared].place_id.nunique()} place / {int(df.place_shared.sum())}행 → {out_dir}")


if __name__ == "__main__":
    src = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parent.parent / "데이터/가공/naver_reviews"
    main(src, out)
