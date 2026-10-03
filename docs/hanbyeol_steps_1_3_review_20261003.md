# 카페·공부 선행 작업 1~3 실행 및 재검토

기준일: 2026-10-03. 재현: 저장소 루트에서 `python -m scripts.prepare_hanbyeol_steps_1_3`.
분석 모집단은 접근성 25% 기준 공식 상권 786개이며, 점포·매출은 서울시 상권분석서비스 2025년 4분기 원천 ZIP을 사용한다. 카카오 키워드 장소는 2026-09-18, 공공시설의 OSM 대형카페 후보는 2026-09-21 스냅샷이다. 시간대가 달라 2025년 예측 성능으로 해석하지 않는다.

## 1. 제과점 식사→카페 경계

- `CS100005=제과점`을 **카페 C2**로 두는 버전별 매핑을 만들었다. PATH-v0 공통 코드는 그대로 두고 `cafe_study_v1_transfer_proposal_2026-10-03`의 코드·상권별 차이를 명시한다. 서울시 점포 `svc_induty_cd`, `svc_induty_cd_nm`, `stor_co`, `trdar_cd`, `stdr_yyqu_cd` 및 매출 `서비스_업종_코드`, `서비스_업종_코드_명`, `당월_매출_금액`, `상권_코드`, `기준_년분기_코드`를 사용한다. 원천 경로는 `data/raw/commercial_area/commercial_store_2025.zip`과 `commercial_sales_2025.zip`이다.
- 제과점 점포 행이 있는 상권 581개, 매출 공개 행이 있는 상권 228개에서 `식사_v1 = 식사_PATH-v0 − 제과점`, `카페_v1 = 카페_PATH-v0 + 제과점`을 각각 검산했다. 매출 미공개 행을 관측 0으로 바꾸지 않는다. 두 표는 입력량 감사이며 점수·순위가 아니다.
- 팀 공통 분류/점수 코드에는 아직 이관하지 않았다. 김건우 담당 식사 점수 및 식사+카페 조합은 동일 버전 매핑을 적용한 뒤 재산출해야 한다. 현재 PATH-v0 식사와 카페 C2 초안을 그대로 조합하면 중복이다. 다른 업종(주점의 여가 이관 등)은 이 변경에 포함하지 않는다.

## 2. S3a/S3b 중복 방지

- S3a는 2026-09-18 카카오 `study_cafe` 장소 후보의 상권별 백분위, S3b는 2025Q4 서울시 `CS200038=독서실` 점포 수의 백분위다. 하나는 장소 검색 결과, 하나는 업종 집계여서 동일 시설의 중복 여부를 개별 점포 수준에서 확인할 수 없다. **둘을 더해 고유 학습시설 수라 부르지 않는다.**
- v1 우선 설계는 S3a를 공급 후보로 유지하고 S3b를 **검증 전용**으로 별도 보존한다. `s3_primary_and_validation_786.csv`에 두 값과 종전 30%+15%, S3a 45%, max 45% 비교 점수를 `proxy_sensitivity`로 남기되 어느 것도 최종 공부점수로 승격하지 않는다. 기존 비교에서 스피어만 0.491, 종전안 대비 대안 Top 10 공통률은 각각 70%·50%다. 이 상관은 지역 집계의 상관이며 실제 같은 점포의 매칭 비율이 아니다. S3a에 45%를 주는 값도 검증 전 가정이다.
- `study_v1_score`는 786행 전부 결측, `v1_status=incomplete_stay_evidence`다. S4 및 보행거리 미검증 상태에서 나머지 가중치를 조용히 재배분하지 않는다.

## 3. C_stay/S4 근거 검토

- 기존 키워드 검색 스타벅스 414건과 OSM 대형카페 13건을 합친 **427개 검토 후보**를 유지했다. 카카오 `place_id`로 만드는 `https://place.map.kakao.com/{place_id}` 및 OSM `candidate_source_url`은 검토 시작점이다. **후보 링크 자체는 증거가 아니다.** 카카오 주소상 서울 393건, 서울 외 21건이며 후자도 경계 근접 가능성을 거리 확인 전 자동 탈락시키지 않는다. 이 목록은 전체 카페 모집단도, 786개 상권의 유효 시설도 아니다.
- 필수 기록: `place_id / place_name / evidence_source_url / evidence_quote / seat_verified / study_allowed_verified / mandatory_purchase / reviewer / reviewed_at / decision`. 추가로 `source_dataset`, `candidate_source_url`, `source_address_name`, `address_in_seoul`, `evidence_type`, `validation_status`를 기록한다.
- `C_stay`는 좌석 존재와 장시간 체류·노트북·학습 이용 중 하나의 **명시된 이용 근거**를 확인해야 한다. `S4`는 좌석과 장시간 이용·노트북 이용·학습 허용 중 명시된 근거가 있어야 한다. 검토 URL, 짧은 인용, 검토자·일자도 요구한다. 좌석만, Wi-Fi만, 브랜드만, 대형 매장이라는 사실만으로 확인 처리하지 않는다. 테이크아웃 전용은 좌석 없음의 명시 근거가 있어야 한다. 구매 의무 미확인은 `unknown`이다.
- 검토 상태는 `unknown`, `c_stay_verified`, `s4_verified`, `takeout_verified`, `excluded`이며 좌석·이용 가능·구매 의무는 `yes/no/unknown`이다. `validate_review()`가 누락 증거, 모순된 판정, 근거 유형을 확인한다. 현재 427건은 **전부 unknown, 확인 0건**이다. 전수 확인 전 S4 점수와 최종 공부 순위는 산출하지 않는다. 검토자가 실제 페이지를 확인하고 출처의 정보 날짜/영업 상태 및 동일 매장 여부까지 기록해야 한다.

## 재검토 결과와 열린 조건

| 검사 | 결과 |
| --- | --- |
| 상권 행·고유 코드 | 786 / 786 |
| 제과점 코드명, 분기×상권×업종 중복 | 점포·매출 코드명 일치, 중복 0 |
| 제과점 이관 전후 보존량 | 공개 원천 행에서 식사 감소량과 카페 증가량이 각각 제과점 수량과 일치 |
| S3a/S3b 상권 행 및 최종 공부 점수 | 786 / 공부 v1 채점 0 |
| C_stay/S4 검토 후보·확인 | 427 / 확인 0 / `unknown` 427 |
| 후보 ID 중복 | 원천+ID 기준 0; 원천 간 ID 일치 0. **실제 동일 매장 여부는 확인되지 않음** |

자동 단위검사 2개를 별도 실행해 통과했다. 기존 회귀검사 모음은 현재 런타임에 `pytest`, `geopandas`가 없어 실행되지 않았다. 실제 보행거리와 상권별 카페 검토 대상 선별은 후속 4단계, 시설 개별 출처 확인은 검토자 작업으로 남는다. 업종 이관은 팀 공통 코드 반영 전이라 최종 조합 추천을 발표할 수 없다.

산출물: `data/processed/cafe_study_taxonomy/steps_1_3/` 아래 `industry_transfer_mapping_v1.csv`, `bakery_transfer_area_audit_786.csv`, `s3_primary_and_validation_786.csv`, `c_stay_s4_review_queue_v1.csv`, `steps_1_3_counts_qa.csv`.
