from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, Frame, PageBreak, PageTemplate, Paragraph, Spacer

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output/pdf/week1_topic_selection_report_maximus.pdf"
TEAM_PHOTO = ROOT / "assets/team/maximus_team_meeting.png"
FONT = "/System/Library/Fonts/Supplemental/AppleGothic.ttf"

pdfmetrics.registerFont(TTFont("Korean", FONT))

doc = BaseDocTemplate(
    str(OUTPUT),
    pagesize=letter,
    leftMargin=27 * mm,
    rightMargin=27 * mm,
    topMargin=20 * mm,
    bottomMargin=18 * mm,
    title="[1주차] 프로젝트 주제 선정 보고서",
    author="팀 막시무스",
)
def add_team_photo(canvas, current_doc):
    if current_doc.page != 3 or not TEAM_PHOTO.exists():
        return
    canvas.saveState()
    photo_w = 72 * mm
    photo_h = photo_w * 1964 / 3024
    photo_x = (letter[0] - photo_w) / 2
    photo_y = 16 * mm
    canvas.drawImage(
        ImageReader(str(TEAM_PHOTO)), photo_x, photo_y,
        width=photo_w, height=photo_h, preserveAspectRatio=True, mask="auto",
    )
    canvas.restoreState()


doc.addPageTemplates(PageTemplate(
    id="report",
    frames=[Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")],
    onPage=add_team_photo,
))

INK = colors.HexColor("#202020")
MUTED = colors.HexColor("#505050")

title = ParagraphStyle(
    "title", fontName="Korean", fontSize=22, leading=29, textColor=INK,
    alignment=TA_CENTER, spaceAfter=10 * mm,
)
meta = ParagraphStyle(
    "meta", fontName="Korean", fontSize=9.5, leading=17, textColor=INK,
    alignment=TA_RIGHT, spaceAfter=8 * mm,
)
h1 = ParagraphStyle(
    "h1", fontName="Korean", fontSize=16, leading=22, textColor=INK,
    spaceBefore=1 * mm, spaceAfter=5 * mm,
)
h2 = ParagraphStyle(
    "h2", fontName="Korean", fontSize=10.8, leading=16, textColor=INK,
    spaceBefore=3.2 * mm, spaceAfter=1.4 * mm,
)
body = ParagraphStyle(
    "body", fontName="Korean", fontSize=8.9, leading=15.2, textColor=INK,
    wordWrap="CJK", spaceAfter=2.7 * mm,
)
body_dense = ParagraphStyle(
    "body_dense", parent=body, fontSize=8.35, leading=13.8, spaceAfter=2.2 * mm,
)
caption = ParagraphStyle(
    "caption", parent=body, fontSize=8, leading=12, textColor=MUTED,
    alignment=TA_CENTER, spaceAfter=2 * mm,
)
footer_note = ParagraphStyle(
    "footer_note", parent=body, fontSize=7.5, leading=11.5, textColor=MUTED,
)


def P(text, style=body):
    return Paragraph(text, style)


story = [
    Spacer(1, 3 * mm),
    P("[1주차] 프로젝트 주제 선정 보고서", title),
    P("2026년 8월 9일<br/><br/>막시무스(MAXIMUS) | 장한별 지우진 최시현", meta),
    P("1. 프로젝트 개요 및 주제 선정 배경", h1),
    P("프로젝트명", h2),
    P("<b>Where Do We Go? - 수도권 생활이동·카드소비·상권 데이터를 활용한 소비 목적지 선택 요인 분석 및 추천 모델</b>"),
    P("프로젝트 개요", h2),
    P("본 프로젝트는 수도권 생활자를 대상으로, 사용자가 실제로 이동할 수 있는 여러 지역 중 특정 상권을 목적지로 선택하고 소비하는 이유를 분석한다. 출발지, 요일, 시간대, 이동 목적과 같은 이동 조건에 수도권 생활이동 데이터, 카드소비 데이터, 상권 특성 데이터를 결합하여 이동시간을 통제한 뒤에도 목적지 선택에 영향을 주는 요인을 찾는다. 최종적으로 사용자의 출발 권역, 최대 이동 가능 시간, 시간대, 목적을 입력하면 도달 가능한 후보 상권을 선별하고, 실제 이동과 소비 행동에 근거한 상위 목적지와 추천 이유를 제시하는 모델 기반 프로토타입을 구축한다."),
    P("주제 선정 동기 및 문제의식", h2),
    P("기존 장소 추천은 가까운 곳이나 전체 인기 장소를 나열하는 경우가 많아 사용자의 현실적인 이동 제약과 방문 목적을 함께 반영하기 어렵다. 또한 유동인구가 많다는 사실만으로 해당 지역이 실제 소비 목적지로 선택되었다고 단정하기 어렵다. 본 프로젝트는 ‘어디가 인기 있는가’가 아니라 ‘갈 수 있는 범위 안에서 어떤 목적지가 왜 더 선택되는가’를 묻는다. 생활이동 데이터로 실제 유입을, 카드 데이터로 실제 소비를, 상권 데이터로 목적지의 구체적인 특성을 측정함으로써 단순 인기순이나 거리순 분석의 한계를 보완하고자 한다."),
    P("연구 질문", h2),
    P("첫째, 이동시간이 길어질수록 목적지 유입과 소비는 감소하는가를 확인한다. 둘째, 이동시간이 비슷한 후보 중에서도 더 많이 선택되는 상권은 어떤 특성을 갖는지 분석한다. 셋째, 음식점·카페 밀도와 업종 다양성 같은 상권 특성의 영향이 연령, 요일, 시간대, 이동 목적에 따라 달라지는지 검증한다. 넷째, 생활이동에서 관측된 유입이 실제 외부 카드소비로 이어지는지 확인한다. 마지막으로 이러한 패턴을 학습한 모델이 단순 거리순이나 인기순보다 실제 목적지 선택을 더 잘 재현하는지 평가한다."),
    PageBreak(),
    P("2. 핵심 목표 및 분석 방향", h1),
    P("필요 데이터와 분석 단위", h2),
    P("핵심 데이터는 서울특별시 빅데이터캠퍼스의 B078 수도권 생활이동 데이터와 B079 서울시민 업종별 카드소비 데이터, 서울 열린데이터광장과 서울신용보증재단의 서울시 상권분석서비스 자료다. B078에서는 출·도착 250m 격자, 시간, 이동 목적, 이동거리와 이동시간, 성·연령별 이동량을 활용한다. B079에서는 고객과 가맹점 지역, 업종, 카드 이용건수와 이용금액을 사용하며, 상권분석서비스에서는 점포·매출·인구·집객시설과 업종 구성을 가져온다. 서로 다른 공간 단위를 연결하기 위해 행정동 경계와 지역코드 자료도 함께 사용한다.", body_dense),
    P("B078과 B079는 폐쇄망 및 반출심사 대상이므로 공개 자료로 코드를 개발하는 Open Pipeline과 빅데이터캠퍼스에서 실제 자료를 처리하는 Secure Pipeline을 분리한다. 최초 분석 데이터마트는 ‘날짜 × 시간 × 출발 행정동 × 도착 행정동 × 연령대 × 목적’을 한 행의 단위로 삼는다. 다만 분석에 앞서 파일별 grain과 key, 코드 체계, 결측과 이상치를 점검하고 250m 격자를 행정동에 공간 매칭한다. 모든 JOIN 전후에는 행 수, 이동량과 소비액 보존율, 미매칭률을 기록하여 결합 과정에서 발생하는 손실을 확인한다.", body_dense),
    P("기술통계와 탐색적 분석", h2),
    P("초기 분석에서는 목적·연령·요일·시간대별 이동시간과 유입량의 분포를 확인하고, 목적지별 외부 소비 비중과 업종 구성을 비교한다. 업종 다양성은 Shannon entropy로, 업종 집중도는 HHI로 측정한다. 집단 차이는 자료의 분포와 등분산성에 따라 Welch ANOVA 또는 Kruskal-Wallis 검정을 사용하고, 사후검정과 효과크기, bootstrap 95% 신뢰구간을 함께 보고한다. 여러 집단과 변수를 반복 검정할 때는 Benjamini-Hochberg 방식으로 FDR을 보정하여 우연한 유의성을 줄인다.", body_dense),
    P("핵심 가설 검증", h2),
    P("목적지 유입량과 카드 이용건수는 0 이상의 count 자료이므로 Poisson 회귀를 기준선으로 적합한 뒤 과산포가 확인되면 Negative Binomial 회귀를 주 모형으로 사용한다. 이동시간의 효과가 직선 형태가 아닐 가능성은 spline 또는 이동시간 구간항으로 검증한다. 카드 이용금액은 log-선형 모형과 Gamma 또는 Tweedie GLM을 비교하여 분포에 가장 적합한 모형을 선택한다. 외부 소비 비율은 값의 분포에 따라 fractional logit이나 beta regression을 검토한다. 모든 모형에는 출발지, 날짜, 시간대 등의 고정효과와 목적지 규모·인구 같은 통제변수를 포함하고, 목적지 또는 자치구 단위 군집 강건 표준오차를 사용한다.", body_dense),
    P("연령과 상황에 따른 차이는 카페 밀도와 주말, 업종 다양성과 연령, 음식점 밀도와 저녁 시간대, 이동시간과 목적의 상호작용항으로 검증한다. 결과는 상호작용항의 p-value만 제시하지 않고 조건별 예측값과 한계효과로 해석한다. 목적지와 자치구에 반복 관측이 쌓이는 구조를 반영하기 위해 random intercept를 둔 혼합효과모형도 고정효과모형과 비교한다. 모형의 신뢰성은 VIF, 잔차, 과산포, 영향점과 대안 사양을 통해 진단한다.", body_dense),
    P("목적지 선택·공간 분석 및 추천 평가", h2),
    P("목적지 선택 분석에서는 각 출발 조건에서 최대 이동시간 이내의 모든 목적지를 후보군으로 만들고, 선택된 목적지와 선택되지 않은 후보를 함께 포함한 long table을 구축한다. 이동시간과 목적지 속성이 선택확률에 미치는 영향은 조건부 로짓으로 추정하며, 자료가 충분하면 mixed logit으로 선호 이질성을 확장한다. 목적지별 모형 잔차에는 Moran’s I를 적용하고 공간 자기상관이 확인될 때만 Spatial Lag 또는 Spatial Error 모형을 검토한다. 실제 유입과 기준모형의 기대 유입 간 잔차가 반복적으로 큰 지역은 Hidden Destination 후보로 정의한다.", body_dense),
    P("Destination Attraction Score는 임의 가중치로 만들지 않고 변수 표준화와 상관구조 확인 후 PCA 또는 요인분석으로 구성 가능성을 검토한다. 예측 단계에서는 로지스틱 계열 모형을 해석 기준선으로 두고 LightGBM과 CatBoost를 비교한다. 학습·검증·테스트는 시간 순으로 분리하고 rolling-origin 검증을 사용한다. 추천 성능은 Recall@5, NDCG@5, MRR, Coverage로 평가하며, 거리순·전체 인기순·과거 유입순 기준선과의 차이는 strata 단위 paired bootstrap 95% 신뢰구간으로 판단한다. 최종 추천 근거는 SHAP과 통계모형의 한계효과를 이용해 설명한다.", body_dense),
    PageBreak(),
    P("3. 기대 효과 및 활용 방안", h1),
    P("학술적 가치", h2),
    P("본 프로젝트는 이동비용과 목적지 속성을 함께 고려하는 소비자 공간 선택 관점에서 생활이동·카드소비·상권 자료를 결합한다. 단순 유동인구나 매출 순위가 아니라 이동시간을 통제한 목적지의 추가적인 흡인력을 분석하고, 연령·시간·목적에 따른 이질성을 검증할 수 있다. 또한 실제 유입이 기대 유입보다 큰 Hidden Destination을 탐색함으로써 접근성만으로 설명되지 않는 상권 매력에 관한 후속 가설을 제시할 수 있다. 다만 집계 관측자료의 특성을 고려하여 개인 수준의 선택이나 인과관계로 확대 해석하지 않는다."),
    P("실무적·서비스적 활용 방안", h2),
    P("사용자는 제한된 시간 안에서 자신의 목적과 조건에 맞는 후보 상권과 추천 근거를 확인할 수 있다. 상권과 소상공인은 어떤 업종 구성과 시간대가 외부 고객 유입과 관련되는지 파악할 수 있으며, 지자체는 잠재력이 있지만 덜 알려진 상권을 탐색하고 지역 활성화 정책의 기초자료로 활용할 수 있다. 장기적으로는 여러 사용자의 공통 도달 가능 지역, 세부 음식·활동 의도, 실시간 교통, 매장 및 코스 추천을 결합한 서비스로 확장할 수 있다."),
    P("기술적 역량", h2),
    P("본 프로젝트를 통해 팀원들은 대규모 외부 데이터 전처리, SQL과 pandas 기반 집계 및 JOIN, GeoPandas와 QGIS를 활용한 공간 단위 변환, 가설검정과 회귀·상호작용·혼합효과·선택 및 카운트 모형, 공간 자기상관 분석, 시간 기반 예측 검증, 랭킹 평가, SHAP 기반 설명 가능성, Streamlit 프로토타이핑을 단계적으로 경험한다. 데이터 감사, 전처리, 통계 분석, 공간 시각화와 비즈니스 해석을 역할별로 수행하되 분석 결과는 팀 전체가 공동 검토한다."),
    P("연구 범위 및 주요 제약", h2),
    P("B078과 B079는 폐쇄망 데이터이므로 접근 승인과 반출심사가 필요하며, 250m 격자·행정동·상권 코드 사이의 공간 단위 불일치가 핵심 위험이다. B078의 이동시간은 실시간 경로시간이 아니라 관측 평균이고, 이동 목적도 쇼핑·관광 등 비교적 큰 범주에 머문다. 따라서 초기에는 행정동 단위의 핵심 가설을 검증하고, 상권 단위 선택모형과 세부 목적 추천은 데이터 품질과 표본 규모가 확보될 때 확장한다. 특정 기법에서 유의한 결과가 나오지 않더라도 이를 숨기지 않고, 이동비용이나 목적지 고정효과가 대부분을 설명했는지 또는 공간 단위와 측정오차가 추가 설명력을 제한했는지를 분석 결과로 보고한다."),
    P("팀명과 프로젝트 지향점", h2),
    P("막시무스(MAXIMUS)는 라틴어로 ‘가장 큰’, ‘가장 위대한’이라는 뜻을 지닌 이름이다. 우리는 이 이름에 단순히 가장 인기 있는 장소가 아니라, 사용자가 실제로 갈 수 있는 범위 안에서 가장 가치 있는 목적지를 발견하겠다는 의미를 담았다. <b>갈 수 있는 범위 안에서, 가장 가치 있는 선택을.</b>"),
    Spacer(1, 2 * mm),
    P("팀 막시무스 온라인 회의", caption),
]

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
doc.build(story)
print(OUTPUT)
