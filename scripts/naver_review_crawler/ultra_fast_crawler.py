"""
네이버 플레이스 리뷰 크롤러 엔진 (Playwright, 이미지·폰트 차단으로 고속화)
"""
import re
import time
import random
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple
from playwright.sync_api import BrowserContext, Page, sync_playwright
from playwright.sync_api import Error as PlaywrightError


class CrawlBlocked(Exception):
    """네이버 차단(보안 확인 화면, 403/429). 점포 상태를 바꾸지 말고 실행을 멈춰야 한다."""


class CrawlTransient(Exception):
    """타임아웃·로딩 실패 등 일시 오류. 점포를 PENDING으로 두고 다음 실행에서 재시도한다."""


REVIEW_LIST_TIMEOUT = "review_list_timeout"


class UltraFastCrawler:
    """초고속 네이버 플레이스 리뷰 크롤러"""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    def start(self):
        """브라우저 실행 및 리소스 차단 컨텍스트 초기화"""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--no-first-run",
                "--no-zygote",
                "--disable-gpu",
            ],
        )
        self._new_context()

    def _new_context(self):
        """컨텍스트 재생성 (메모리 정리 및 리소스 필터 적용)"""
        if self.context:
            try:
                self.context.close()
            except Exception:
                pass

        self.context = self.browser.new_context(
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "Version/16.6 Mobile/15E148 Safari/604.1"
            ),
            viewport={"width": 390, "height": 844},
            locale="ko-KR",
            timezone_id="Asia/Seoul",
        )
        self.context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        # 🚀 이미지, 미디어, 폰트 차단 (HTML, JS, API 패킷만 고속 다운로드)
        self.context.route(
            "**/*.{png,jpg,jpeg,gif,svg,webp,ico,woff,woff2,ttf,otf,eot,mp4,avi,mov}",
            lambda route: route.abort()
        )
        self.page = self.context.new_page()

    def stop(self):
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def random_sleep(self, min_s: float = 0.8, max_s: float = 1.6):
        time.sleep(random.uniform(min_s, max_s))

    def check_anti_bot(self) -> bool:
        if not self.page:
            return False
        try:
            title = self.page.title()
            if any(k in title for k in ["봇 확인", "자동입력", "보안 확인", "서비스 이용 제한"]):
                print(f"🚨 [경고] 네이버 차단 화면 감지! (타이틀: {title})")
                return True
            if "captcha" in self.page.url.lower():
                return True
        except Exception:
            pass
        return False

    def _goto(self, url: str, timeout: int):
        """페이지 이동. 차단이면 CrawlBlocked, 로딩 실패면 CrawlTransient."""
        try:
            resp = self.page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        except PlaywrightError as e:
            raise CrawlTransient(f"goto_failed: {str(e)[:120]}")
        if resp is not None and resp.status in (403, 429):
            raise CrawlBlocked(f"http_{resp.status}: {url}")
        if resp is not None and resp.status >= 500:
            raise CrawlTransient(f"http_{resp.status}: {url}")
        if self.check_anti_bot():
            raise CrawlBlocked(f"anti_bot_page: {url}")

    def generate_candidates(self, store: Dict[str, Any]) -> List[str]:
        raw_name = store.get("rt_name") or store.get("name") or ""
        clean_name = re.sub(r"[()]", " ", raw_name).strip()
        base_name = re.sub(r"\s*[가-힣\d]+(?:점|호점|본점|직영점)\b", "", clean_name).strip()
        # 띄어쓰기 없는 상호는 지점 토큰과 함께 상호까지 지워진다
        # ("갓텐갓텐스시롯데월드몰점 코리아" → "코리아"). 원래 이름의 앞부분이 아니면 쓰지 않는다.
        if len(base_name) < 2 or not clean_name.startswith(base_name):
            base_name = clean_name

        area_name = store.get("area_name", "").split("(")[0].strip()
        district = store.get("area_district", "")
        admin = store.get("area_admin", "")

        candidates = []
        # 1. [상호] [상권명]
        if area_name and area_name not in clean_name:
            candidates.append(f"{clean_name} {area_name}".strip())
        else:
            candidates.append(clean_name)

        # 2. [상호] [자치구] [행정동]
        if district and admin:
            q2 = f"{clean_name} {district} {admin}".strip()
            if q2 not in candidates:
                candidates.append(q2)

        # 3. [순수 브랜드] [상권명]
        if base_name != clean_name and area_name:
            q3 = f"{base_name} {area_name}".strip()
            if q3 not in candidates:
                candidates.append(q3)

        return candidates

    def find_place_id(self, store: Dict[str, Any]) -> Optional[Tuple[str, str, str]]:
        """None은 '모든 검색어가 정상 로딩됐는데 결과 없음'일 때만 반환한다.
        차단이면 CrawlBlocked, 한 검색어라도 로딩 실패면 CrawlTransient."""
        candidates = self.generate_candidates(store)
        load_errors = []

        for attempt, query in enumerate(candidates, start=1):
            url = f"https://m.search.naver.com/search.naver?query={urllib.parse.quote(query)}"
            try:
                self._goto(url, timeout=10000)
                self.random_sleep(0.5, 0.9)

                content = self.page.content()
                matches = re.findall(r'place\.naver\.com/(?:restaurant|place)/(\d+)', content)
                if matches:
                    place_id = matches[0]
                    place_link = self.page.query_selector(f'a[href*="{place_id}"]')
                    place_name = place_link.inner_text().strip().split("\n")[0] if place_link else ""
                    return place_id, place_name, f"STEP_{attempt}:{query}"

            except CrawlTransient as e:
                load_errors.append(str(e))
            except PlaywrightError as e:
                load_errors.append(f"page_error: {str(e)[:120]}")

        if load_errors:
            raise CrawlTransient("; ".join(load_errors)[:300])
        return None

    def scrape_reviews(self, store_id: str, place_id: str, max_reviews: int = 20) -> List[Dict[str, Any]]:
        """방문자 리뷰 본문 수집 (사진 갤러리 이탈 방지 및 텍스트 파싱)"""
        reviews: List[Dict[str, Any]] = []
        review_url = f"https://m.place.naver.com/restaurant/{place_id}/review/visitor"

        try:
            self._goto(review_url, timeout=12000)
            self.random_sleep(0.8, 1.2)

            # 리뷰 카드 대기 (최대 5초). 안 뜨면 차단인지 다시 보고, 리뷰 없음과 구분할 수 없으므로 일시 오류로 올린다.
            # 실행기는 같은 점포에서 이 오류가 두 번 연속 나면 NO_REVIEWS로 확정한다.
            try:
                self.page.wait_for_selector("li.place_apply_pui, li.EjjAW", timeout=5000)
            except PlaywrightError:
                if self.check_anti_bot():
                    raise CrawlBlocked(f"anti_bot_page: {review_url}")
                raise CrawlTransient(REVIEW_LIST_TIMEOUT)

            # 1. 안전한 리뷰 더보기 버튼 클릭 (사진 링크 절대 제외!)
            # '펼쳐서 더보기' 또는 'a.fvwqf' 만 클릭
            clicks_needed = (max_reviews // 10)
            for _ in range(clicks_needed):
                cards = self.page.query_selector_all("li.place_apply_pui, li.EjjAW")
                if len(cards) >= max_reviews:
                    break

                # 정확한 리뷰 더보기 버튼
                more_btn = self.page.query_selector("a.fvwqf, a:has-text('펼쳐서 더보기')")
                if more_btn and more_btn.is_visible():
                    try:
                        more_btn.click()
                        self.random_sleep(0.8, 1.2)
                        # 혹시라도 URL이 변경되었으면 뒤로가기
                        if "/photo" in self.page.url:
                            self.page.go_back(wait_until="domcontentloaded")
                            break
                    except Exception:
                        break
                else:
                    break

            # 2. 접힌 본문('펼쳐보기' / 본문 내 더보기) 클릭
            expand_btns = self.page.query_selector_all("li.place_apply_pui a.pui__wF7ZqM, li.place_apply_pui a:has-text('펼쳐보기')")
            for btn in expand_btns:
                try:
                    if btn.is_visible():
                        btn.click()
                        time.sleep(0.03)
                except Exception:
                    pass

            # 3. 리뷰 카드 파싱
            cards = self.page.query_selector_all("li.place_apply_pui, li.EjjAW")
            for card in cards:
                if len(reviews) >= max_reviews:
                    break

                card_text = card.inner_text().strip()
                if not card_text or len(card_text) < 5:
                    continue

                lines = [l.strip() for l in card_text.split("\n") if l.strip()]
                author_name = lines[0] if lines else ""

                # 별점
                rating = ""
                rm = re.search(r"별점\s*\n*\s*(\d+(?:\.\d+)?)", card_text)
                if rm:
                    rating = rm.group(1)

                # 방문일
                visit_date = ""
                dm = re.search(r"방문일\s*\n*([^\n]+)", card_text)
                if dm:
                    visit_date = dm.group(1).strip()

                # 방문 횟수
                visit_count = ""
                cm = re.search(r"(\d+번째\s*방문)", card_text)
                if cm:
                    visit_count = cm.group(1).strip()

                # 본문 추출: DOM 요소 우선 시도, 실패 시 텍스트 파싱
                body_el = card.query_selector(".pui__vn15t2, a.pui__GStJHb:not(.pui__hvyFHZ)")
                if body_el and len(body_el.inner_text().strip()) > 0:
                    body = body_el.inner_text().strip()
                    # 키워드 태그들
                    k_els = card.query_selector_all(".pui__jhpEyP, .pui__eug4Uq, .tag")
                    keywords = [k.inner_text().strip() for k in k_els if k.inner_text().strip()]
                else:
                    # 텍스트 라인 파싱 폴백
                    skip_words = ["팔로우", "별점", "반응 남기기", "방문일", "인증 수단", "영수증", "결제내역", "더보기", "접기", "사진"]
                    known_tags = ["맛있어요", "친절해요", "좋아요", "넓어요", "신선해요", "깔끔해요", "가성비", "분위기", "아늑해요", "청결해요"]
                    body_lines = []
                    keywords = []
                    in_header = True

                    for line in lines[1:]:
                        if any(k in line for k in ["팔로우", "별점", "점", "리뷰 "]) and in_header:
                            continue
                        if any(k in line for k in ["방문예약", "대기 시간", "입장", "에 방문"]) and in_header:
                            in_header = False
                            continue
                        if any(k in line for k in ["반응 남기기", "방문일", "인증 수단", "번째 방문"]):
                            break
                        if any(t in line for t in known_tags) and len(line) <= 20:
                            keywords.append(line)
                        else:
                            if not any(k in line for k in skip_words) and line != rating:
                                body_lines.append(line)

                    body = " ".join(body_lines)

                reviews.append({
                    "store_id": store_id,
                    "place_id": place_id,
                    "author_name": author_name,
                    "rating": rating,
                    "review_text": body,
                    "visit_date": visit_date,
                    "visit_count": visit_count,
                    "keywords": ", ".join(keywords),
                })

            return reviews

        except (CrawlBlocked, CrawlTransient):
            raise
        except PlaywrightError as e:
            # 중간 실패 시 일부만 저장하면 '리뷰 n건' 점포로 굳어지므로 전체를 재시도한다.
            raise CrawlTransient(f"scrape_error: {str(e)[:120]}")
