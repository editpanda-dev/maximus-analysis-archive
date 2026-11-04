# 모현 연구용 추가 데이터 후보

조사: 2026-10-29 · 분야 7개 탐색 167건 중 추림. 교통 분야는 별도 검증을 거쳤고, 나머지는 탐색 단계에서 페이지를 직접 열어 확인한 내용이다. ✔ = 모현읍·오포 행을 직접 확인, △ = 경기 전역이라 포함이 유력하지만 행은 미확인.

## A. 바로 핵심

| 데이터 | 주는 것 | 모현 | 받는 법 | 라이선스 |
|---|---|---|---|---|
| 경기도_데이터분석 카드매출 행정동 집계 ([data.go.kr 15151650](https://www.data.go.kr/data/15151650/fileData.do)) | 행정동 × 업종 중분류 월 카드매출. 2022-01~2025-06 중 일부 월 | ✔ 모현읍 4146125300, 업종 70개 행 (2025-01 시트) | 경기데이터드림 파일(zip 15MB), 키 불필요 | 공공누리 1유형 |
| 경기도 지역화폐 업종별 매출·행정동 소비 ([15151643](https://www.data.go.kr/data/15151643/fileData.do), [15151652](https://www.data.go.kr/data/15151652/fileData.do), [15151617](https://www.data.go.kr/data/15151617/fileData.do)) | 읍면동 × 업종 지역화폐 매출·순위·비율 | △ | 파일 | 공공누리 1유형 |
| 경기도_정류소 별 승하차 인원 집계 ([경기데이터드림](https://data.gg.go.kr/portal/data/service/selectServicePage.do?infId=MZCREO5CKHZM6PJEA55P37391662&infSeq=1)) | 정류소별 일별 승차·하차·환승. 월간 갱신(2026-08-27) | ✔ 외대사거리·외국어대입구·기숙사·왕곡마을, 오포 신현리·문형·추자동 | 파일, 키 불필요 | 상업 이용·변경 허용 |
| GBIS 기반정보 엑셀 ([gbis.go.kr](https://www.gbis.go.kr/gbis2014/publicService.action?cmd=mBaseInfo)) + 노선 API ([15080662](https://www.data.go.kr/data/15080662/openapi.do)) | 정류소 좌표, 노선별 경유정류소 / 요일별 첫차·막차·배차 | ✔ 같은 정류소ID 체계 | 엑셀은 키 불필요, API는 data.go.kr 키 | 제한 없음 |
| 경기 광주시 버스지선정보·노선정보 ([3079775](https://www.data.go.kr/data/3079775/fileData.do)) | 회차별 출발 시각(사실상 시간표), 첫막차·배차 | ✔ 오포 기점 노선 | 파일 | 제한 없음 |
| 행안부 일반음식점·휴게음식점 인허가 ([15096283](https://www.data.go.kr/data/15096283/openapi.do), [15154921](https://www.data.go.kr/data/15154921/openapi.do)) | 인허가일자·영업상태·폐업일 → 노포 태그 | △ 전국 | 파일 CSV(약 213만 행) 또는 API | 제한 없음. 좌표 EPSG:5174 |
| admdongkor ([GitHub](https://github.com/vuski/admdongkor)) | 행정동 경계 2026-10판. 2022년 오포 분동 반영 | ✔ | 파일, 키 불필요 | CC BY 4.0 |
| 한국외대 통학버스·광역버스 무료탑승 ([e-book](https://e-book.hufs.ac.kr/global_bus_stu/), [공지](https://builder.hufs.ac.kr/user/hufs/campusMap/map_pop02_a.html)) | 판교·서현·경기광주역 노선(평일만). 1005·1117·1150·1303 모현사거리~캠퍼스 무료 | ✔ | 웹 열람만 | 학교 저작물: 사실만 인용 |

## B. 보조

| 데이터 | 쓸모 | 주의 |
|---|---|---|
| 경기 유동인구 행정동 시간대·요일 ([15151641](https://www.data.go.kr/data/15151641/fileData.do), [15151616](https://www.data.go.kr/data/15151616/fileData.do)) | 시간 리듬 태그(저녁형·주말형) 대체 | 모현·오포 행 미확인. 공공누리 1유형 |
| KT 유동인구 행정동(경기데이터드림), 경기 카드 소비 데이터 ([15128475](https://www.data.go.kr/data/15128475/fileData.do)) | 성·연령·시간대까지 세분 | 공공누리 2유형(상업 이용 금지). 카드 소비는 광주시 빠졌을 수 있음 |
| 용인 모범음식점 115 ([3078133](https://www.data.go.kr/data/3078133/fileData.do)), 착한가격업소 용인 118 / 광주 38 | 신뢰·가성비 태그 | 모현·오포 해당 건수 미확인 |
| 경기 지역화폐 가맹점 API ([15058640](https://www.data.go.kr/data/15058640/openapi.do)), 용인와이페이 가맹점 34,453 ([15155472](https://www.data.go.kr/data/15155472/fileData.do)) | 점포별 지역화폐 가맹 여부 | |
| TourAPI ([15101578](https://www.data.go.kr/data/15101578/openapi.do)), 인허가 문화·관광 업종(야영장·영화관 등), 산림청 등산로, 도시공원 표준, 광주시 공간정보 SHP(관광지·등산로·체육시설) | 여가·자연 명소 후보 | 키 필요한 것은 data.go.kr 키 하나로 됨 |
| STCIS 대중교통 통합정보 | 모현읍·능평동·신현동 선택 가능한 정류장 이용량·O/D | 별도 인증키 |
| 국토부 정류장평균이용량 ([15162142](https://www.data.go.kr/data/15162142/fileData.do)) | 서울과 같은 척도의 정류장 하차량 | 연간, 처인구 행 미확인 |
| Geofabrik OSM 한국 pbf ([링크](https://download.geofabrik.de/asia/south-korea.html), 276MB) | Overpass 대신 보행망 | ODbL 출처 표기 |
| 경기도교통정보센터 교통DB | 노선별 시간대 이용객, 시군 간 O/D | 월 대표일 1일 표본, 이용조건 불명 |

## C. 쓰지 않음

- 서울 수도권 생활이동(KT): 경기 쪽은 시군구 단위라 모현읍 분석 불가
- TAGO 버스 정보: 경기는 GBIS로 넘겨 미연계
- 경기도 버스정류소 현황: 2018년 자료, 정류소명 바뀜
- 용인 행복택시(모현 마을 없음), 킥보드 주차구역(캠퍼스 8km 안 0곳)
- ~~똑버스 모현 미확인~~ → GBIS 2026-10-29판에 용인똑버스02(모현읍행정복지센터↔힐스테이트몬테로이1단지, 06:30~23:00) 있음. 수요응답형이라 시간표 대신 호출 방식
- 한국관광 데이터랩: 공식 다운로드만 허용(스크래핑 금지)

## 키
- data.go.kr 서비스키 하나로 GBIS·용인 정류장·인허가·TourAPI 등 대부분 자동승인
- 경기데이터드림 인증키는 API에만 필요. 파일은 키 없이 받음 (2026-10-29 접속 시 "사이트 점검 중")
