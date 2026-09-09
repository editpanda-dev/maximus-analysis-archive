# 막시무스 | 동대문구 출발 상권·목적지 분석 아카이브

동대문구의 버스정류장·지하철역 334개를 출발지로 두고, 대중교통 30분 이내에 접근 가능한 서울 상권을 찾은 분석 기록이다. 후보를 행정동에서 멈추지 않고 서울시 공식 상권 폴리곤(골목상권·발달상권·전통시장·관광특구)까지 세분화한다.

## 이번 스냅샷의 핵심 결과

- 출발지: 동대문구 버스정류장·지하철역 334개
- 시간대: 08시·14시·19시, 30분 이내 대중교통 네트워크
- 행정동 탐색 기준: 세 시간대 모두 출발지 25% 이상 접근
- 공식 상권 기준: 도달 정류장이 상권 경계 400m 이내에 있는 출발지 비율을 시간대별로 계산
- 최종 상권 후보: 26개 (25% 이상), 14개 (50% 이상), 5개 (80% 이상)

## 공간 단위

`행정동 생활권 → 공식 상권 폴리곤 → 점포/POI`의 3단계 구조를 사용한다. 행정동은 넓은 후보 범위를 고르는 역할이며, 실제 추천 및 분석 단위는 공식 상권이다. 상권이 여러 행정동을 가로지르면 폴리곤 교집합 면적을 보존하며, `primary_admin_*`은 표시 편의를 위한 대표 행정동일 뿐이다.

상세 정의: [docs/commercial_area_definition.md](docs/commercial_area_definition.md)

## 구성

| 경로 | 내용 |
|---|---|
| `docs/` | 프로젝트 맥락, EDA, 선행연구, 데이터 접근 전략, 분석 로드맵 |
| `scripts/` | 정류장 출발지 구축, 정적 대중교통 그래프, 상권·매출 결합, 검증 코드 |
| `data/processed/commercial_area_accessibility/` | 공식 상권 25% 후보·지도 GeoJSON·행정동 교차 관계 |
| `data/processed/local_transit_30min/` | 시간대 안정성 기준 행정동 결과와 모델 가정 |
| `data/processed/transit_validation/` | 정적 네트워크와 ODsay 등시권 결과의 겹침 검증 |
| `data/processed/flow_sales_gap/` | 유동인구–추정매출 괴리 후보 및 EDA 집계 |

## 재현 순서

원본 데이터와 API 키는 재배포하지 않는다. 서울시 공공데이터·서울 열린데이터광장·ODsay에서 각 이용 조건에 따라 내려받은 뒤, 아래 순서로 실행한다.

```bash
python -m pip install -r requirements-local-transit.txt
python -m scripts.build_odsay_origins
python -m scripts.build_seoul_transit_network
python -m scripts.static_multimodal_accessibility --hour 8
python -m scripts.static_multimodal_accessibility --hour 14
python -m scripts.static_multimodal_accessibility --hour 19
python -m scripts.compare_accessibility_periods
python -m scripts.download_seoul_commercial_area_sources
python -m scripts.build_commercial_area_accessibility
```

ODsay 호출은 `ODSAY_API_KEY` 환경변수로만 수행한다. API 키와 원본 이동·카드 데이터는 커밋하지 않는다.

## 해석 유의사항

- 정적 대중교통 모델은 시간대별 평균 배차·노선 정보에 기반한 후보 생성용 모델이다. 실제 이용자 추천에는 요청 시점의 길찾기 API로 최종 30분 조건을 다시 확인해야 한다.
- `400m` 상권 접근 버퍼는 하차 후 도보 연결을 위한 모델 가정이다. 300m·500m 민감도 분석을 병행할 예정이다.
- 서울시 상권분석서비스는 2024년 이후 공간 단위 체계가 변경되었으므로, 이전 단위와 새 공식 상권 단위를 단순 코드 기준으로 시계열 결합하지 않는다.

## 팀

막시무스 — 장한별 · 지우진 · 최시현
