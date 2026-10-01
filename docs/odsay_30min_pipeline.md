# ODsay 30분 대중교통 도달권 파이프라인

## 분석 정의

동대문구의 여러 출발 대표점에서 ODsay가 반환하는 버스·지하철 통합 30분 접근성 영역을 만들고, 서울 행정동 경계와 겹치는 면적을 집계한다. 기존의 일부 노선·무환승 계산을 대체하는 현실 교통망 후보 생성 단계다.

ODsay 공식 사양은 `searchTime=30`, `searchMethod=4`를 각각 30분과 버스+지하철로 정의한다. 응답은 Polygon 또는 MultiPolygon GeoJSON이다. 접근성 폴리곤만으로는 개별 후보의 환승 횟수와 도보시간을 알 수 없으므로, 최종 후보는 별도의 출발지-상권 중심점 경로 조회로 재검증해야 한다.

## 입력

- 출발점 CSV: `origin_id, origin_name, longitude, latitude` 필수
- 서울시 최신 행정동 경계 GeoJSON: 법정동 경계를 사용하지 않는다.
- ODsay API 키: 코드나 CSV가 아닌 환경변수 `ODSAY_API_KEY`에만 저장

정류소 331개를 같은 가중치로 사용하면 정류소 밀집지역이 과대 반영된다. 본 분석의 기본 출발점은 동대문구 행정동별 대표점이며, 정류소 전체 결과는 강건성 검사로 분리한다.

## 실행

```bash
python3 -m pip install -r requirements-odsay.txt
export ODSAY_API_KEY='발급받은_키'  # 등호 앞뒤에 공백을 넣지 않는다
python3 scripts/odsay_accessibility.py \
  --origins data/external/odsay_origins.csv \
  --districts data/external/seoul_administrative_dongs.geojson \
  --minutes 30 \
  --min-area-coverage 0.10
```

API 응답은 `data/interim/odsay_30min/raw/`에 캐시된다. 재실행 시 저장된 응답을 우선 사용하므로 호출량과 시점 차이를 줄일 수 있다.

## 판정 규칙

행정동 면적의 10% 이상이 한 출발점의 도달권과 겹치면 해당 출발점에서 접근 가능하다고 본다. 최종 CSV에는 도달 가능한 출발점 수, 전체 출발점 수, 도달 비율, 평균 면적 포함률을 기록한다. 10%는 확정값이 아니며 5%, 10%, 20% 민감도 분석을 수행한다.

## 검증 게이트

1. 회기역 등 알려진 출발점 3곳을 지도 서비스와 수동 비교한다.
2. 20분 도달권이 30분 도달권 내부에 포함되는지 확인한다.
3. 버스 전용, 지하철 전용, 통합 결과의 크기와 누락 지역을 비교한다.
4. 후보 상위 행정동은 상권 중심점까지 개별 경로를 조회해 총시간·도보·환승 횟수를 확인한다.
5. 기존 147개 잠정 후보와 편입·탈락 행정동을 비교하되 어느 쪽도 실제 방문량으로 해석하지 않는다.

## 아직 필요한 파일

- 검증된 동대문구 출발점 목록
- 최신 서울시 행정동 경계
- ODsay API 키

템플릿 `data/external/odsay_origins_template.csv`의 회기역 좌표는 실행 형식 확인용이며, 본 분석 전에 공식 좌표로 교체한다.

학교망에서 `CERTIFICATE_VERIFY_FAILED`가 발생하면 인증서 검증을 끄지 말고 `truststore`를 설치한다. 이 파이프라인은 설치되어 있을 때 macOS 시스템 신뢰 저장소를 사용한다.
