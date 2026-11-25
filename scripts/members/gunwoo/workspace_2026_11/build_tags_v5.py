# -*- coding: utf-8 -*-
"""태그 v5 (2026-11-23): v4와 같은 피처·방법에 5회차 라벨을 더하고 단체 회식 기준선을 다시 잡는다.

v4와 달라진 점
  1) 학습 라벨에 5회차 건우 답(애매 45 · 무작위 25 · 단체 경계 20)을 더한다. 다시 찍기 15곳(r5retest)은 넣지 않는다.
     v4가 0.3~0.7로 본 애매 가게 라벨이 늘어난 것이 핵심이다(능동 학습 첫 회).
  2) 단체 회식 규칙 점수 기준선: 새 정의 라벨 44곳(예 26)에서 점수 AUC 0.81.
     v4 기준(아님 ≤ 0.6)으로는 '아님' 28곳 중 12곳이 실제 '예'였다. → 해당 ≥ 0.65 & 면적 ≥ 50㎡, 아님 ≤ 0.4.
     이 기준에서 해당 15곳 중 예 87%, 아님 13곳 중 예 15%. 표본이 단체 후보 위주라 임시값이다.
  3) 새 피처(재방문·주말 비율, 리뷰 본문 TF-IDF)는 넣지 않았다. 5회차 시험셋 가중 AUC가 v3 0.823, +본문 0.827,
     +행동 0.815로 차이가 없었다(분석/eval_tags_v5.py). 방문 정보(동행·목적) 수집이 끝나면 다시 비교한다.
출력: 데이터/가공/store_level/store_tags_v5.csv
실행: ~/.venvs/maximus/bin/python 분석/build_tags_v5.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import build_tags_v4 as v4  # noqa: E402
from eval_tags_pooled import labels as labels_r1_r4_team  # noqa: E402
from eval_tags_v5 import r5_labels  # noqa: E402


def labels_with_r5():
    r5 = r5_labels().assign(labeler="gunwoo")
    return pd.concat([labels_r1_r4_team(), r5], ignore_index=True)


v4.labels = labels_with_r5
v4.GROUP_HI, v4.GROUP_LO, v4.GROUP_M2 = 0.65, 0.4, 50
v4.OUT = v4.STORE / "store_tags_v5.csv"

if __name__ == "__main__":
    v4.main()
