"""P5. 네이버 키워드(칩) → 테마 사전 v0.

입력: 데이터/가공/naver_reviews/dining_reviews_clean.csv (로컬 전용, 분석/build_naver_reviews.py 출력)
      keywords + extra_tags 열의 공식 키워드만 쓴다. 본문·닉네임은 읽지 않는다.
출력: data/processed/store_level/keyword_theme_map_v0.csv (공개 가능: 키워드 문구는 일반 표현)
      열: keyword, n_stores, total_count, themes, purpose_hint, note

테마는 설계 docs/store_level/recommendation_options.md 6.3절의 10개에서 출발했다.
2026-11-12 1차 검수(김건우) 반영:
  - 한 키워드가 여러 테마에 들 수 있다. themes 열은 '|'로 잇고 앞이 주 테마다.
  - 서비스·청결을 서비스·친절과 청결로 나눴다.
  - 애견동반 태그를 더했다(반려동물과 가기 좋아요).
'음악이 좋아요'는 검수에서 정하지 않아 검토필요로 남긴다.

실행 (저장소 루트):
    ~/.venvs/maximus/bin/python scripts/store_level/build_keyword_theme_map_v0.py
"""
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT.parent / "데이터/가공/naver_reviews/dining_reviews_clean.csv"
OUT = ROOT / "data/processed/store_level/keyword_theme_map_v0.csv"

REVIEW = "검토필요"
THEMES = ["맛", "가성비·양", "조용·아늑", "감성·인테리어·뷰", "오래 머물기·공부", "혼자",
          "대화·모임", "특별함", "서비스·친절", "청결", "편의", "애견동반"]
# keyword: (themes, purpose_hint, note)  themes 앞쪽이 주 테마
THEME_MAP = {
    "음식이 맛있어요": (["맛"], "식사", ""),
    "재료가 신선해요": (["맛"], "식사", ""),
    "고기 질이 좋아요": (["맛"], "식사", ""),
    "건강한 맛이에요": (["맛"], "식사", ""),
    "잡내가 적어요": (["맛"], "식사", ""),
    "현지 맛에 가까워요": (["맛"], "식사", ""),
    "향신료가 강하지 않아요": (["맛", "가성비·양"], "식사", ""),
    "기본 안주가 좋아요": (["맛", "가성비·양"], "식사", "주점"),
    "커피가 맛있어요": (["맛"], "카페", ""),
    "디저트가 맛있어요": (["맛"], "카페", ""),
    "빵이 맛있어요": (["맛"], "카페", ""),
    "차가 맛있어요": (["맛"], "카페", ""),
    "음료가 맛있어요": (["맛"], "카페", ""),
    "가성비가 좋아요": (["가성비·양"], "식사", ""),
    "양이 많아요": (["가성비·양"], "식사", ""),
    "반찬이 잘 나와요": (["가성비·양"], "식사", ""),
    "가격이 합리적이에요": (["가성비·양"], "식사", ""),
    "샐러드바가 잘 되어있어요": (["가성비·양"], "식사", ""),
    "메뉴 구성이 알차요": (["가성비·양"], "식사", ""),
    "세트 구성이 알차요": (["가성비·양"], "식사", ""),
    "품질이 좋아요": (["가성비·양"], "쇼핑", "식사 업종엔 드묾"),
    "아늑해요": (["조용·아늑"], "카페", ""),
    "차분한 분위기예요": (["조용·아늑"], "카페", ""),
    "분위기가 편안해요": (["조용·아늑"], "카페", ""),
    "인테리어가 멋져요": (["감성·인테리어·뷰"], "카페", ""),
    "뷰가 좋아요": (["감성·인테리어·뷰"], "카페", ""),
    "사진이 잘 나와요": (["감성·인테리어·뷰"], "카페", ""),
    "야외공간이 멋져요": (["감성·인테리어·뷰"], "카페", ""),
    "비주얼이 좋아요": (["감성·인테리어·뷰"], "카페", "음식 모양 칭찬이라 맛 후보"),
    "컨셉이 독특해요": (["감성·인테리어·뷰", "특별함"], "카페", ""),
    "라이브공연이 훌륭해요": (["감성·인테리어·뷰", "특별함"], "여가문화", ""),
    "음악이 좋아요": ([REVIEW], "카페", "감성·인테리어·뷰 또는 조용·아늑"),
    "오래 머무르기 좋아요": (["오래 머물기·공부"], "공부", "카페 겸용"),
    "집중하기 좋아요": (["오래 머물기·공부"], "공부", ""),
    "좌석이 편해요": (["오래 머물기·공부"], "카페", "편의 후보"),
    "혼밥하기 좋아요": (["혼자"], "식사", ""),
    "혼술하기 좋아요": (["혼자", "감성·인테리어·뷰"], "식사", "주점"),
    "대화하기 좋아요": (["대화·모임"], "카페", ""),
    "단체모임 하기 좋아요": (["대화·모임"], "식사", ""),
    "파티하기 좋아요": (["대화·모임"], "식사", ""),
    "룸이 잘 되어있어요": (["대화·모임", "편의"], "식사", ""),
    "특별한 날 가기 좋아요": (["특별함", "감성·인테리어·뷰"], "식사", ""),
    "특별한 메뉴가 있어요": (["특별함"], "식사", ""),
    "비싼 만큼 가치있어요": (["특별함"], "식사", ""),
    "코스요리가 알차요": (["특별함"], "식사", ""),
    "선물하기 좋아요": (["특별함"], "쇼핑", "포장·선물용"),
    "술이 다양해요": (["특별함"], "식사", "주점"),
    "친절해요": (["서비스·친절"], "식사", ""),
    "직접 잘 구워줘요": (["서비스·친절"], "식사", ""),
    "아이와 가기 좋아요": (["서비스·친절"], "식사", ""),
    "포장이 깔끔해요": (["서비스·친절", "특별함"], "식사", ""),
    "매장이 청결해요": (["청결"], "식사", ""),
    "화장실이 깨끗해요": (["청결"], "식사", ""),
    "시설이 깔끔해요": (["청결"], "식사", ""),
    "환기가 잘 돼요": (["청결"], "식사", ""),
    "매장이 넓어요": (["편의"], "식사", "대화·모임 후보"),
    "주차하기 편해요": (["편의"], "식사", ""),
    "음식이 빨리 나와요": (["편의"], "식사", ""),
    "종류가 다양해요": (["편의"], "식사", ""),
    "반려동물과 가기 좋아요": (["편의", "애견동반"], "카페", ""),
}


def count_keywords(df: pd.DataFrame) -> pd.DataFrame:
    """리뷰마다 고른 키워드를 세어 키워드별 점포 수·선택 수를 낸다."""
    total, stores = Counter(), {}
    for sid, kw, extra in zip(df.store_id, df.keywords, df.extra_tags):
        for k in {x.strip() for x in f"{kw}, {extra}".split(", ") if x.strip()}:
            total[k] += 1
            stores.setdefault(k, set()).add(sid)
    return pd.DataFrame(
        [{"keyword": k, "n_stores": len(stores[k]), "total_count": total[k]} for k in total]
    )


def build(df: pd.DataFrame) -> pd.DataFrame:
    out = count_keywords(df)
    meta = out.keyword.map(lambda k: THEME_MAP.get(k, ([REVIEW], "", "사전에 없는 새 키워드")))
    out["themes"] = meta.map(lambda m: "|".join(m[0]))
    out["purpose_hint"], out["note"] = meta.str[1], meta.str[2]
    return out.sort_values(["total_count", "keyword"], ascending=[False, True]).reset_index(drop=True)


def main(src: Path = SRC, out_path: Path = OUT):
    df = pd.read_csv(src, dtype=str, keep_default_na=False, encoding="utf-8-sig",
                     usecols=["store_id", "keywords", "extra_tags"])
    out = build(df)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False, encoding="utf-8-sig")
    unmapped = set(THEME_MAP) - set(out.keyword)
    print(f"리뷰 {len(df)} · 가게 {df.store_id.nunique()} → 키워드 {len(out)}개 → {out_path}")
    per_theme = out.assign(theme=out.themes.str.split("|")).explode("theme")
    print(per_theme.groupby("theme").agg(n_keywords=("keyword", "size"), total_count=("total_count", "sum")).to_string())
    if unmapped:
        print(f"사전엔 있으나 데이터에 없는 키워드: {sorted(unmapped)}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else SRC)
