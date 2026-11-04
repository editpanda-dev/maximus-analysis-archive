# [도움 요청] 서울캠 ODsay 호출 한도 부족

## 상황 (2026-10-31)
- 서울캠(한국외대 이문동) 출발 30분 추천은 상권 786곳 중 직선 12km 안 773곳까지 ODsay `searchPubTransPathT`로 시간을 잰다.
- 우리 키는 하루 약 **30건**에서 `429 Daily quota exceeded`가 난다(10-30, 10-31 모두 30건 뒤 멈춤). 지금 **89/773건**만 쟀다.
- 그래서 매일 30건씩 자동으로 이어서 부르고 있다. 불확실한 직선 4~8km 217곳을 먼저 부르는데, 이것만 해도 약 7일이 걸린다.
- 아직 못 잰 곳은 `reach_status`로 추정 표시한다.
  - 직선 4km 안: 30분 안으로 추정
  - 직선 8km 밖: 30분 밖으로 추정(받아둔 8~10km 12곳은 모두 38분 이상)
  - 결과 파일: `data/processed/campus_seoulcampus/seoulcampus_areas_reach_v1.csv`

## 부탁
ODsay 키에 여유가 있는 사람은 아래 둘 중 하나로 도와주면 고맙겠다.

1. **직접 돌려주기**
   - 작업 폴더 구조: 이 저장소를 품은 폴더 아래에 `데이터/`가 있어야 한다. 아니면 `MAXIMUS_WORKSPACE`로 지정한다.
   - 응답은 `<작업 폴더>/데이터/캐시/서울캠_odsay/*.json`에 쌓인다. 그 json 폴더를 비공개로 공유해 주면 이어서 쓴다.
   - 실행:
     ```bash
     MAXIMUS_WORKSPACE=<작업 폴더> ODSAY_API_KEY=<본인 키> python scripts/campus/서울캠/build_seoulcampus_recommendations_v1.py
     ```
   - 키가 IP에 묶여 있으면 `ODSAY_IP_KEYS="<IP>=ODSAY_API_KEY"` 형식으로 지정하면 된다.
   - 먼저 `scripts/campus/서울캠/build_seoulcampus_area_tags_v1.py`가 만든 `seoulcampus_area_tags_v1.csv`가 필요하다. 저장소의 `data/processed/campus_seoulcampus/`에 있는 파일을 `<작업 폴더>/데이터/가공/서울캠/`로 복사하면 된다.
2. **이미 있는 결과 공유**
   - 이문동 출발 ODsay 경로 결과(같은 상권 대표점)를 갖고 있으면 공유해 주기.

ODsay 응답 캐시와 키는 공개 저장소에 올리지 않는다.
