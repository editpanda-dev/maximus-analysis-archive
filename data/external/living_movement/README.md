# 원천 다운로드 안내

원천 대용량 CSV는 저장소에 넣지 않는다. 서울 열린데이터광장의 `수도권 생활이동 (성 연령별, 도착지 기준)-내국인`에서 월별 ZIP을 내려받아 압축을 푼 뒤 아래처럼 실행한다.

```bash
python3 scripts/build_living_movement_features.py \
  --input-glob '/path/to/seoul_purpose_admdong1_in_YYYYMM/*.csv'
```

현재 기준 스냅샷은 2026-08이며, 출처·목적코드·집계 단위는 `docs/living_movement_data_dictionary.md`에 기록한다.
