# 막시무스 팀 시작 안내

## 최신 기준선

- 동대문구 버스정류장·지하철역 334개를 출발지로 둔다.
- 08·14·19시, 30분 이내 도달 정류장을 정적 대중교통 그래프로 계산한다.
- 공식 상권 1,650개를 도달 정류장 좌표와 직접 결합한다.
- 세 시간대 모두 출발지 25% 이상이 접근 가능한 상권은 786개다.
- 786개는 최종 추천 목록이 아니라 교통 접근성 탐색 풀이다.

## 꼭 알아둘 정정 사항

이전 문서의 `26개 공식 상권 후보`는 행정동 코드 체계 불일치로 생긴 잘못된 사전 필터 결과다. 이동·상권 통계용 행정동 코드와 경계 GeoJSON의 공간 코드가 달랐기 때문에, 현재는 행정동 코드를 후보 제외에 사용하지 않는다.

## 현재 재현 가능한 산출물

1. `data/processed/commercial_area_accessibility/`
   - 786개 접근성 후보, 시간대별 접근률, GeoJSON
2. `data/processed/commercial_area_purpose_features/`
   - 2025년 공식 상권별 식사·카페·공부·쇼핑·여가문화 PATH-v0 기준선
3. `data/processed/flow_sales_gap/`
   - 행정동 단위 유동–매출 괴리 EDA. 공식 상권 추천 점수와 혼동하지 않는다.
4. `data/processed/commercial_area_sales_gap/`
   - 786개 공식 상권을 대상으로 점포 수·면적·점포 업종 다양성·상권 유형으로 기대매출을 만들고, 2025년 4개 분기 잔차를 진단한 결과다.
   - 공식 상권 유동인구를 대체하지 않았으므로 유동–매출 괴리 결과가 아니다. 현재는 후속 조사 상권을 고르는 보조 지표로만 쓴다.

## 실행 순서

```bash
python -m pip install -r requirements-local-transit.txt
python -m scripts.build_commercial_area_accessibility
python -m scripts.build_commercial_area_purpose_features
python -m scripts.build_commercial_area_sales_gap
```

`data/raw/README.md`에 있는 공개 원본은 공유하지만, B078·B079 원본과 ODsay API 키는 커밋하거나 공유하지 않는다.

## Google Colab

`notebooks/README.md`의 순서를 따른다. 먼저 `01_transit_official_commercial_candidates_colab.ipynb`을 실행하면 786개 공식 상권 접근성 후보를 재산출한다. 이후 Colab 코드 셀에서 `python -m scripts.build_commercial_area_purpose_features`를 실행하면 목적별 PATH-v0 기준선을 생성한다.
