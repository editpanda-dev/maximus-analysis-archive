from copy import deepcopy
from pathlib import Path

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt


SOURCE = Path('/tmp/maximus-plan-gI953k/source.docx')
OUTPUT = Path('/Users/woojin/Documents/막시무스/output/막시무스_학생창업동아리_신청서_양식3_5페이지_서식유지.docx')


def clear_cell(cell):
    tc = cell._tc
    old_ppr = deepcopy(cell.paragraphs[0]._p.pPr) if cell.paragraphs[0]._p.pPr is not None else None
    for child in list(tc):
        if child.tag == qn('w:p') or child.tag == qn('w:tbl'):
            tc.remove(child)
    p = OxmlElement('w:p')
    if old_ppr is not None:
        p.append(old_ppr)
    tc.append(p)


def first_run_props(cell):
    for paragraph in cell.paragraphs:
        for run in paragraph.runs:
            if run.text:
                return deepcopy(run._element.rPr) if run._element.rPr is not None else None
    return None


def apply_run_props(run, rpr):
    if rpr is not None:
        run._element.insert(0, deepcopy(rpr))


def set_cell_text(cell, text, bold_prefix=None):
    rpr = first_run_props(cell)
    clear_cell(cell)
    lines = text.split('\n\n')
    for i, line in enumerate(lines):
        p = cell.paragraphs[0] if i == 0 else cell.add_paragraph()
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.line_spacing = 1.15
        if bold_prefix and line.startswith(bold_prefix):
            lead, rest = line.split(' ', 1)
            r = p.add_run(lead + ' ')
            apply_run_props(r, rpr)
            r.bold = True
            r = p.add_run(rest)
            apply_run_props(r, rpr)
        else:
            r = p.add_run(line)
            apply_run_props(r, rpr)


def shade(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:fill'), fill)
    tc_pr.append(shd)


def set_repeat_table_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement('w:tblHeader')
    tbl_header.set(qn('w:val'), 'true')
    tr_pr.append(tbl_header)


def set_allow_row_break(row):
    tr_pr = row._tr.get_or_add_trPr()
    cant_split = tr_pr.find(qn('w:cantSplit'))
    if cant_split is not None:
        tr_pr.remove(cant_split)


def style_schedule(table, rpr):
    widths = [1.35, 2.05, 11.2]
    for ri, row in enumerate(table.rows):
        set_allow_row_break(row)
        for ci, cell in enumerate(row.cells):
            cell.width = Pt(widths[ci] * 28.35)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            for p in cell.paragraphs:
                p.paragraph_format.space_after = Pt(0)
                p.paragraph_format.line_spacing = 1.0
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER if ci < 2 else WD_ALIGN_PARAGRAPH.LEFT
                for run in p.runs:
                    apply_run_props(run, rpr)
                    if ri == 0:
                        run.bold = True
            if ri == 0:
                shade(cell, 'D9E1F2')
            elif ri % 2 == 0:
                shade(cell, 'F3F5FA')
    set_repeat_table_header(table.rows[0])


doc = Document(SOURCE)
plan = doc.tables[7]

overview = """1. 컨셉 및 특징

‘어디가지’는 사용자의 현재 위치, 방문 목적, 가용 이동시간을 바탕으로 목적지 자체를 추천하는 iOS 기반 서비스이다. 기존 지도 및 장소 검색 서비스는 사용자가 방문할 지역이나 장소를 어느 정도 결정한 뒤 점포 정보와 이동 경로를 찾는 방식에 최적화되어 있다. 그러나 실제 일상에서는 “돈카츠를 먹고 싶다”, “색다른 동네의 카페에서 공부하고 싶다”, “잠깐 리프레시할 곳에 가고 싶다”처럼 하고 싶은 행동과 사용할 수 있는 시간은 정해졌지만 어느 지역으로 갈지는 결정하지 못한 상황이 자주 발생한다. ‘어디가지’는 이처럼 목적지가 정해지지 않은 상태에서 여러 지역과 점포를 반복 검색해야 하는 과정을 줄이는 데 목적이 있다.

사용자는 현재 위치 또는 장소 검색·지도 핀을 통해 출발지를 설정하고, 식사·카페·데이트·쇼핑·문화·휴식 등 방문 목적과 20·30·40·60분의 이동 가능 시간을 선택한다. 서비스는 입력 조건에 맞는 상권과 행정동을 먼저 추천하고, 사용자가 특정 지역을 선택하면 목적에 맞는 점포를 확인한 뒤 지도와 대중교통 경로까지 연결한다. 즉, ‘조건 입력 → 목적지 발견 → 점포 선택 → 실제 이동’으로 이어지는 하나의 탐색 경험을 제공한다. 추천 결과는 단순 거리순이나 인기순이 아니라 방문 목적에 대한 지역별 적합도를 바탕으로 산정하며, 목적별 점포 구성, 업종 다양성, 시간대 특성, 상권 특성을 함께 반영한다.

현재 프로젝트에서는 동대문구의 버스정류장·지하철역 334개를 출발지로 설정하고, 오전 8시·오후 2시·오후 7시의 대중교통 30분 접근성을 분석했다. 서울시 공식 상권 1,650개 중 세 시간대 모두 출발지의 25% 이상에서 접근 가능한 786개 공식 상권을 1차 탐색 후보군으로 정의했으며, 실제 서비스에서는 사용자의 개별 출발지와 시간 조건에 맞춰 후보를 다시 제한한다. 출발지 설정, 목적·이동시간 입력, 상권·행정동 추천, 점포 탐색, 지도 및 대중교통 경로 확인으로 이어지는 iOS MVP의 핵심 흐름도 구현한 상태이다."""

competitive = """2. 아이템의 경쟁력

막시무스의 경쟁력은 이미 알려진 장소를 더 잘 검색하는 데 있지 않고, 목적지가 없는 사용자가 어디로 갈지를 결정하도록 돕는 데 있다. 사용자는 일반적으로 인스타그램·블로그에서 장소를 탐색하고, 네이버지도나 카카오맵에서 리뷰와 경로를 검증한다. 막시무스는 이러한 서비스를 대체하기보다 사용자가 기존 지도 서비스로 들어가기 전 “어느 지역을 먼저 볼 것인가”를 결정하게 하는 서비스를 지향한다. 따라서 기존 플랫폼의 축적된 리뷰와 지도 기능을 활용하면서도, 목적지 미결정 상태의 탐색 부담을 줄이는 역할을 수행한다.

추천 후보군을 실제 대중교통 접근성에 기반해 구성했다는 점도 차별점이다. 단순히 직선거리상 가까운 지역이나 리뷰가 많은 점포를 추천하는 방식은 이동시간, 환승 부담, 방문 목적의 차이를 반영하기 어렵다. 막시무스는 동대문구 출발 생활권의 교통 접근성을 분석해 후보 상권을 정의하고, 상권별 점포·업종·시간대 특성을 결합한 룰 기반 기준선으로 목적별 순위를 산정한다. 이를 통해 사용자는 “가장 유명한 곳”보다 자신의 현재 조건에서 목적을 수행하기 적합한 지역을 추천받을 수 있으며, 추천 사유도 함께 확인할 수 있다.

생성형 AI는 자연어 질문에 따라 후보와 설명을 만들 수 있지만, 막시무스는 동일한 기준 아래 출발지별 교통 접근성, 상권 특성, 추천 이후의 상권 선택·점포 조회·경로 확인·재방문 데이터를 축적한다. 사용자의 자연어 입력은 목적·분위기·시간 조건으로 구조화하고, LLM은 이를 해석하거나 리뷰의 분위기 키워드를 정리하는 보조 기술로 활용한다. 핵심 추천은 생활권·이동·선택 데이터와 자체 추천 로직을 기반으로 고도화해 나갈 계획이다."""

market = """1. 아이템에 대한 시장분석

최근 로컬 탐색 시장은 네이버지도·카카오맵과 같은 지도 서비스, 인스타그램·블로그와 같은 콘텐츠 서비스, 그리고 생성형 AI 서비스가 함께 형성하고 있다. 사용자는 식사·카페·데이트·산책 등 일상적인 외출을 계획할 때 인스타그램이나 블로그에서 장소를 발견하고, 네이버지도와 카카오맵에서 리뷰·영업시간·혼잡도·대중교통 경로를 확인하는 방식으로 여러 플랫폼을 오간다. 생성형 AI에는 “외대에서 30분 안에 갈 수 있는 조용한 카페를 추천해줘”와 같은 질문을 던져 후보를 얻을 수도 있다.

그러나 기존 서비스는 사용자가 ‘성수 카페’, ‘홍대 맛집’처럼 방문할 지역이나 목적지를 먼저 정해야 효율적으로 작동한다. 인스타그램과 블로그는 새로운 장소를 발견하는 데 유용하지만, 콘텐츠의 최신성·광고성·실제 이동 가능 시간은 사용자가 직접 판단해야 한다. 생성형 AI도 자연어 질문에 대한 아이디어를 제공할 수 있으나, 실제 출발지·시간대·교통 상황·장소 정보와 사용자의 선택 이력을 일관된 기준으로 축적해 반영하는 서비스 구조와는 차이가 있다.

‘어디가지’는 목적지를 정하지 못한 이용자에게 출발 위치, 방문 목적, 이동 가능 시간을 바탕으로 행정동을 먼저 추천하고 점포와 경로 확인까지 연결한다. 초기에는 동대문구 대학 생활권에서 대중교통 접근성·업종 구성·방문 목적을 반영하는 추천을 검증한 뒤 서울 주요 대학가로 확장한다. 추천 결과 클릭, 행정동 선택, 점포 조회, 지도 열기, 경로 확인, 재방문 데이터를 축적해 개인화 추천과 리뷰 감정 분석을 단계적으로 고도화할 계획이다. 이를 통해 인기 상권에 집중된 수요를 다양한 생활권으로 분산시키고, 인지도가 낮더라도 특정 목적에 적합한 지역과 점포가 발견될 기회를 넓히고자 한다."""



business = """2. 사업성

초기 수요자는 식사·카페·스터디·산책·데이트 등 일상적인 외출을 계획할 때 새로운 장소를 찾고 싶지만 목적지를 정하지 못하는 서울 소재 대학생이다. 이들은 공강 시간, 수업 이후, 시험이 끝난 뒤, 주말 등 비교적 유연한 시간대에 대중교통으로 생활권을 이동한다. 외대·경희대·고려대·서울시립대 등이 밀집한 동대문구 대학 생활권에서 추천이 실제 행정동 선택·점포 조회·경로 확인·방문으로 이어지는지를 우선 검증한다.

시장 규모는 단계적으로 설정했다. 장기 잠재시장(TAM)은 국내 20~39세 인구 약 1,339만 명이며, 일상적인 외출과 여가를 위해 새로운 지역과 장소를 탐색할 가능성이 높은 생활 이동 수요층이다. 서비스 가능 시장(SAM)은 전국 고등교육기관 재적학생 약 300만 7천 명으로 설정했다. 대학생은 대중교통 이용 빈도가 높고, 식사·카페·학습·여가 목적의 외출이 반복되며 새로운 장소 탐색에 익숙하다는 점에서 초기 서비스와 가장 적합한 고객군이다. 초기 확보시장(SOM)은 서울 소재 고등교육기관 재적학생 약 91만 1천 명이며, 이 가운데 동대문구 대학 생활권을 첫 실증 범위로 설정한다.

팀은 데이터 전처리와 룰 기반 추천 알고리즘 설계, iOS MVP 구현, 자연어 처리와 사용자 검증 역량을 보유하고 있다. 초기에는 서비스 이용을 무료로 제공하며 사용자 선택 데이터를 축적하고, 이후 점포 상세 페이지와 지도·예약·구매 채널 이동을 기반으로 로컬 점포 제휴 및 전환 수수료 모델을 검증한다. 스폰서드 노출은 일반 추천 결과와 구분해 이용자 신뢰를 유지하며, 장기적으로는 사용자 동의를 전제로 비식별·집계된 목적·시간대·지역 선택 데이터를 활용한 상권 분석과 B2B·B2G 서비스로 확장할 계획이다."""

commercialization = """1. 아이템 사업화 계획

막시무스는 동대문구 대학 생활권을 초기 실증지역으로 설정하고, 목적지가 정해지지 않은 이용자에게 행정동과 점포를 추천하는 iOS 기반 MVP를 고도화한다. 현재 구현된 출발지 설정, 방문 목적·이동시간 입력, 행정동 추천, 점포 탐색, 지도 및 대중교통 경로 확인 흐름을 바탕으로 실제 이용 환경에서 추천 결과가 출발지와 이동 조건에 따라 달라지도록 개선한다. 상세 위치를 직접 지정했을 때에도 추천이 정상 작동하도록 보완하고, 목적별 추천 결과에 실제 대중교통 이동 경로와 예상 소요 시간을 함께 제시할 계획이다.

추천 로직은 대중교통 접근성, 행정동별 업종 구성, 방문 목적, 이동시간을 반영한 룰 기반 방식으로 운영한다. 동대문구 내 버스·지하철 출발지 334개와 접근성 기준을 충족한 786개 상권 후보군을 기반으로, 이용자의 출발지·시간대·이동 가능 시간에 따라 후보 지역을 다시 산출한다. 사용자 인터뷰와 사용성 테스트를 통해 추천 결과의 적합도를 점검하고, 추천 확인·행정동 선택·점포 조회·지도 열기·경로 확인·재방문 데이터를 수집한다. 이후 축적된 데이터는 개인화 추천, 리뷰 감정 분석, 자연어 기반 조건 입력 기능 개발의 기반으로 활용한다.

초기 사용자는 동대문구 대학생 커뮤니티와 SNS 콘텐츠를 통해 모집한다. ‘회기에서 30분, 오늘 공부하기 좋은 동네’, ‘정류장 기준으로 갈 수 있는 식사 동네’와 같은 콘텐츠로 서비스 경험을 제시하고 베타테스트를 반복한다. 지원금은 카카오맵·대중교통·LLM API 사용료, 서버·데이터베이스 운영비, 사용자 검증, 정류장 기반 콘텐츠 제작과 초기 홍보에 우선 활용한다. 이후 점포 제휴와 예약·구매 전환 수수료를 검증하고, 장기적으로 상권 분석 서비스로 확장한다."""

set_cell_text(plan.rows[0].cells[1], overview)
set_cell_text(plan.rows[1].cells[1], competitive)
set_cell_text(plan.rows[2].cells[1], market)
set_cell_text(plan.rows[3].cells[1], business)
set_cell_text(plan.rows[4].cells[1], commercialization)

schedule_cell = plan.rows[5].cells[1]
schedule_rpr = first_run_props(schedule_cell)
clear_cell(schedule_cell)
title = schedule_cell.paragraphs[0]
title.paragraph_format.space_after = Pt(4)
r = title.add_run('2. 일정표')
apply_run_props(r, schedule_rpr)
r.bold = True

schedule = schedule_cell.add_table(rows=1, cols=3)
headers = ['기간', '추진 내용', '주요 산출물']
for cell, value in zip(schedule.rows[0].cells, headers):
    cell.text = value
rows = [
    ('2026.09', '데이터·MVP 점검', '334개 출발지·786개 후보군 정비, 상세 위치와 추천 흐름 보완'),
    ('2026.10', '지도·교통 연동 고도화', '예상 이동시간·교통수단·경로 확인 기능 개선'),
    ('2026.10~11', '사용자 검증', '대학생 인터뷰·사용성 테스트, 추천 실패 사례와 개선 요구 정리'),
    ('2026.11~12', '베타 운영·콘텐츠 유입', '정류장 기반 SNS 콘텐츠, 선택·조회·경로 확인 데이터 수집'),
    ('2026.12', '추천 로직 보완', '목적별 적합도 조정, 추천 이유 표시, MVP 개선 보고서'),
    ('2027.01~02', '성과 정리·확장 설계', '핵심 지표 분석, 개인화·자연어 기능 및 서울 대학가 확장 계획')
]
for values in rows:
    cells = schedule.add_row().cells
    for cell, value in zip(cells, values):
        cell.text = value
style_schedule(schedule, schedule_rpr)

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
doc.save(OUTPUT)
print(OUTPUT)
