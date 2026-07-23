# -*- coding: utf-8 -*-
"""
코스트코 온라인몰 할인 상품 자동 수집 → data/products.json 생성
매주 실행하면 사이트의 상품 목록이 자동으로 갱신됩니다.

사용법:
    python scripts/update_products.py            # products.json 생성만
    python scripts/update_products.py --push     # 생성 후 git commit + push (GitHub Pages 자동 배포)

표준 라이브러리만 사용하므로 별도 설치가 필요 없습니다.
"""
import json
import re
import ssl
import subprocess
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

# ──────────────────────────── 설정 ────────────────────────────
MARGIN_RATE = 0.15        # 대행 수수료율 (코스트코가 대비 15%)
LOW_DISCOUNT_SHARE = 0.5  # 할인율<15%라 정가 초과 시: 수수료 = 할인액 × 이 비율 (반반)
MIN_MARGIN_WON = 2000     # 반반 적용 시 최소 마진 — 미만이면 상품 제외
POPULAR_COUNT = 30        # 비할인 인기 상품 수집 개수 (0 = 안 함)
ROUND_UNIT = 100          # 판매가 반올림 단위 (100원)
PRODUCT_COUNT = 0         # 사이트에 올릴 상품 수 (0 = 전부)
MIN_PRICE = 5000          # 이 금액 미만 상품 제외 (대행 실익 없음)
MAX_PRICE = 150000        # 이 금액 초과 상품 제외
BEST_REVIEW_MIN = 300     # 이 이상 리뷰면 '베스트' 배지
SUMMER_MONTHS = (6, 7, 8, 9)  # 이 기간엔 냉장·냉동 상품 목록에서 제외 (배송 중 변질 위험)
DEADLINE_WEEKDAY = 1      # 주문 마감 요일 (0=월 ... 1=화)
DEADLINE_HOUR = 21        # 주문 마감 시각 (21시)

BASE = "https://www.costco.co.kr"
_FIELDS = ("&fields=products(code,name,englishName,price(FULL),basePrice(FULL),"
           "as400Discount,discountPrice(FULL),images(DEFAULT),maxOrderQuantity,"
           "stock(DEFAULT),url,purchasable,averageRating,numberOfReviews)"
           ",pagination&lang=ko&curr=KRW")
# '스페셜 할인'(SpecialPriceOffers) 카테고리 = 현재 할인 중인 상품 전체
API = (BASE + "/rest/v2/korea/products/search"
       "?query=%3Arelevance%3AallCategories%3ASpecialPriceOffers"
       "&pageSize=100&currentPage={page}" + _FIELDS)
# 전체 검색 기본 정렬 = 인기/노출 순 → 비할인 인기 상품 수집용
POPULAR_API = (BASE + "/rest/v2/korea/products/search"
               "?query=%3Arelevance&pageSize=100&currentPage={page}" + _FIELDS)
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
# 상품 상세 API (실제 제품 설명 + 갤러리 이미지)
DETAIL_API = (BASE + "/rest/v2/korea/products/{code}"
              "?fields=description,images(FULL)&lang=ko&curr=KRW")
DETAIL_WORKERS = 8        # 상세정보 동시 요청 수
GALLERY_MAX = 5           # 갤러리 이미지 최대 장수
DETAIL_IMG_MAX = 8        # 상세컷 이미지 최대 장수

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "data" / "products.json"

# 카테고리 자동 분류 키워드 (위에서부터 먼저 매칭 — 순서가 중요)
CATEGORY_KEYWORDS = [
    ("생활용품", ["화장지", "티슈", "물티슈", "키친타월", "행주타월", "메가롤", "슈퍼롱",
                "마이비데", "세제", "섬유유연제", "샴푸", "바디워시", "치약", "칫솔",
                "랩", "호일", "지퍼백", "종이컵", "수세미", "장갑", "건전지", "면도",
                "알카라인", "듀라셀", "탈취제", "클리너", "기피", "복사지", "문구"]),
    ("주방·가전", ["프라이팬", "웍", "냄비", "뚝배기", "쿡웨어", "그리들", "압력솥",
                 "오븐", "그릴", "밥솥", "전자레인지", "에어프라이어", "커피머신",
                 "커피메이커", "블렌더", "믹서", "착즙기", "토스터", "인덕션",
                 "전기포트", "정수", "식기", "밀폐용기", "텀블러", "보온병", "도마",
                 "냉면기", "접시", "그릇", "다리미", "스티머", "청소기", "공기청정기",
                 "공기순환기", "서큘레이터", "선풍기", "제습기", "가습기", "드라이어",
                 "비데", "구강세정기", "안마", "마사지", "쿠커"]),
    ("홈·리빙", ["인조잔디", "잔디깎기", "가드닝", "호스", "워터건", "삽", "보관함",
               "수납", "선반", "행거", "의자", "테이블", "책상", "침대", "매트리스",
               "매트", "이불", "베개", "쿠션", "침구", "커튼", "타월", "수건", "러그",
               "카펫", "램프", "조명", "스탠드", "LED", "사다리", "공구", "드릴",
               "핸드트럭", "카트", "우산", "정리함", "필로우", "원예", "세면대"]),
    ("스포츠·레저", ["골프", "서프보드", "패들", "자전거", "킥보드", "캠핑", "텐트",
                  "타프", "쉐이드", "침낭", "아이스박스", "쿨러", "등산", "낚시",
                  "수영", "물놀이", "튜브", "보트", "공기주입", "덤벨", "아령", "요가",
                  "트램폴린", "헬멧", "스포츠", "러닝"]),
    ("완구·취미", ["레고", "장난감", "인형", "블록", "보드게임", "퍼즐", "피규어"]),
    ("반려동물", ["개집", "강아지", "고양이", "반려", "사료", "캣", "배변", "발도장",
                "포포몽", "냥스푼"]),
    ("패션·잡화", ["백팩", "더플백", "메신저백", "슬링", "가방", "캐리어", "신발",
                 "운동화", "슬리퍼", "샌들", "모자", "양말", "티셔츠", "팬츠", "자켓",
                 "셔츠", "벨트", "지갑", "선글라스"]),
    ("자동차용품", ["엔진오일", "워셔액", "와이퍼", "세차", "블랙박스", "주차"]),
    ("뷰티", ["크림", "세럼", "로션", "에센스", "마스크팩", "선크림", "클렌징",
            "토너", "앰플", "토닉", "두피", "헤어", "선패치", "선쉴드", "데오드란트",
            "미스트", "제모", "선 스프레이"]),
    ("베이커리", ["크루아상", "베이글", "머핀", "케이크", "식빵", "빵", "타르트", "파이"]),
    ("건강기능식품", ["비타민", "바이타민", "오메가", "유산균", "프로바이오틱", "루테인",
                    "홍삼", "콜라겐", "밀크씨슬", "글루코사민", "칼슘", "마그네슘",
                    "아연", "영양제", "캡슐", "드시모네", "효소", "이뮨", "진액",
                    "프로틴", "단백질", "프리바이오틱", "에레키반"]),
    ("냉장·냉동", ["냉동", "냉장", "신선", "아이스", "만두", "피자", "치즈", "우유",
                 "요거트", "요구르트", "버터", "베이컨", "소시지", "햄 ", "생연어",
                 "삼겹", "목살", "등심", "닭가슴", "새우", "굴비", "장어"]),
    ("과일·신선", ["사과", "키위", "오렌지", "포도", "수박", "바나나", "체리",
                 "블루베리", "아보카도", "파인애플", "애플망고", "딸기", "감귤",
                 "레몬", "복숭아", "토마토", "버섯"]),
    ("간식·건과", ["너트", "아몬드", "캐슈", "피스타치오", "호두", "땅콩", "과자",
                 "초콜릿", "쿠키", "젤리", "칩", "크래커", "시리얼", "그래놀라",
                 "건포도", "망고"]),
    ("음료·커피", ["커피", "원두", "카누", "티백", "녹차", "주스", "탄산", "음료", "생수"]),
    ("식품", ["쌀", "김치", "라면", "국수", "파스타", "소스", "기름", "올리브", "간장",
             "된장", "고추장", "참치", "햇반", "김 ", "미역", "통조림", "꿀", "잼",
             "스팸", "비비고", "설렁탕", "갈비탕", "곰탕", "꼬리곰탕", "육수", "카레",
             "죽", "비빔면", "짬뽕", "우동", "스파게티", "라볶이", "떡볶이", "유부초밥",
             "무국", "자반", "오뚜기밥", "큰밥", "작은밥", "밀면", "탕면", "어묵",
             "야채사각", "짜슐랭"]),
]
COLD_KEYWORDS = ["냉동", "냉장", "신선", "아이스", "만두", "피자", "치즈", "우유",
                 "요거트", "요구르트", "버터", "베이컨", "소시지", "생연어", "삼겹",
                 "목살", "등심", "닭가슴", "새우", "장어", "횟감"]
# 대행 부적합 상품 제외 키워드 (설치·대형·주류 등)
EXCLUDE_KEYWORDS = ["설치", "타이어", "가구", "매트리스", "소파", "냉장고", "세탁기",
                    "TV", "텔레비전", "에어컨", "와인", "위스키", "맥주", "소주", "양주"]


def fetch_page(page: int, api: str = API) -> dict:
    req = urllib.request.Request(api.format(page=page), headers={"User-Agent": UA})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=30, context=ctx) as res:
        return json.load(res)


def fetch_detail(code: str) -> dict:
    """상품 상세: 상세컷 이미지(설명 HTML 속 <img>) + 갤러리 이미지. 실패 시 빈 값"""
    try:
        req = urllib.request.Request(DETAIL_API.format(code=code),
                                     headers={"User-Agent": UA})
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=20, context=ctx) as res:
            data = json.load(res)
        # 상세 설명 HTML 안의 이미지 = 쇼핑몰식 상세컷
        srcs = re.findall(r"<img[^>]+src=[\"']([^\"']+)[\"']",
                          data.get("description", ""))
        detail_images = []
        for s in srcs:
            u = s if s.startswith("http") else BASE + s
            if u not in detail_images:
                detail_images.append(u)
        gallery = [BASE + i["url"] for i in data.get("images", [])
                   if i.get("imageType") == "GALLERY" and i.get("format") == "product"]
        return {"detail_images": detail_images[:DETAIL_IMG_MAX],
                "gallery": gallery[:GALLERY_MAX]}
    except Exception:
        return {"detail_images": [], "gallery": []}


def pick_image(images: list) -> str:
    for fmt in ("product", "results", "thumbnail"):
        for img in images or []:
            if img.get("format") == fmt and img.get("url", "").endswith(".jpg"):
                return BASE + img["url"]
    # jpg가 없는 상품은 포맷 무관 첫 이미지라도 사용 (webp/png 등)
    for fmt in ("product", "results", "thumbnail"):
        for img in images or []:
            if img.get("format") == fmt and img.get("url"):
                return BASE + img["url"]
    return ""


def classify(name: str) -> str:
    for category, keywords in CATEGORY_KEYWORDS:
        if any(k in name for k in keywords):
            return category
    return "기타"


def is_cold(name: str) -> bool:
    return any(k in name for k in COLD_KEYWORDS)


def extract_unit(name: str) -> str:
    """상품명 끝의 용량/수량 표기를 추출 (예: '1.13kg', '400캡슐', '100매 x 9팩')"""
    m = re.search(r"[\d,.]+\s?(?:kg|g|ml|L|매|입|개|정|캡슐|팩|롤|병|캔|포|미)"
                  r"(?:\s?[x×]\s?\d+\s?\S*)?$", name, re.IGNORECASE)
    return m.group(0).strip() if m else "1개"


def next_deadline(now: datetime) -> datetime:
    """다음 주문 마감 시각 (다가오는 화요일 21:00)"""
    days_ahead = (DEADLINE_WEEKDAY - now.weekday()) % 7
    candidate = (now + timedelta(days=days_ahead)).replace(
        hour=DEADLINE_HOUR, minute=0, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=7)
    return candidate


def week_label(now: datetime) -> str:
    week_no = (now.day - 1) // 7 + 1
    return f"{now.year}년 {now.month}월 {week_no}주차"


def to_site_product(p: dict, pid: int, detail: dict) -> dict | None:
    """가격 정책:
    - 할인율 ≥ 수수료율: 대행가 = 할인가 × 1.15 (정가보다 낮음이 보장됨)
    - 할인율 < 수수료율: 수수료 = 할인액의 절반 → 고객·대행 모두 이득, 정가 초과 없음
      (이때 마진이 MIN_MARGIN_WON 미만이면 실익이 없어 None 반환 = 목록 제외)
    - 비할인 인기 상품: 판매가 × 1.15
    """
    base_price = int(p["basePrice"]["value"])
    discount = int(p.get("discountPrice", {}).get("value") or 0)
    costco_price = base_price - discount  # 실제 결제될 코스트코 가격 (할인 적용가)
    fee = costco_price * MARGIN_RATE
    sale_price = round((costco_price + fee) / ROUND_UNIT) * ROUND_UNIT
    if discount and sale_price >= base_price:  # 저할인 상품: 할인 반반 나누기
        fee = discount * LOW_DISCOUNT_SHARE
        sale_price = round((costco_price + fee) / ROUND_UNIT) * ROUND_UNIT
        if sale_price >= base_price:  # 반올림 경계 방어: 정가보다 최소 100원 낮게
            sale_price = base_price - ROUND_UNIT
        if sale_price - costco_price < MIN_MARGIN_WON:
            return None
    name = p["name"].strip()
    reviews = int(p.get("numberOfReviews") or 0)
    main_image = pick_image(p.get("images"))
    gallery = detail.get("gallery") or []
    if main_image and main_image not in gallery:
        gallery = [main_image] + gallery
    return {
        "id": pid,
        "name": name,
        "category": classify(name),
        "origin_price": base_price,
        "costco_price": costco_price,
        "sale_price": sale_price,
        "unit": extract_unit(name),
        "max_qty": min(int(p.get("maxOrderQuantity") or 3), 3),
        "badge": f"{discount:,}원 할인" if discount else "인기 상품",
        "rating": round(float(p.get("averageRating") or 0), 1),
        "reviews": reviews,
        "best": reviews >= BEST_REVIEW_MIN,
        "cold": is_cold(name),
        "description": (f"코스트코 정가 {base_price:,}원에서 {discount:,}원 할인 중인 상품입니다."
                        if discount else "코스트코에서 꾸준히 사랑받는 인기 상품입니다."),
        "image": main_image,
        "gallery": gallery[:GALLERY_MAX + 1],
        "detail_images": detail.get("detail_images") or [],
        "costco_url": BASE + p.get("url", ""),
    }


def main():
    print("코스트코 할인 상품 수집 중...")
    candidates = []
    page, total_pages = 0, 1
    while page < total_pages:
        data = fetch_page(page)
        total_pages = data.get("pagination", {}).get("totalPages", 0)
        for p in data.get("products", []):
            if not p.get("as400Discount"):
                continue
            if not p.get("purchasable", True):
                continue
            if p.get("stock", {}).get("stockLevelStatus") != "inStock":
                continue
            price = p.get("basePrice", {}).get("value")
            discount = p.get("discountPrice", {}).get("value")
            if not price or not discount:
                continue
            if not (MIN_PRICE <= price <= MAX_PRICE):
                continue
            if any(k in p.get("name", "") for k in EXCLUDE_KEYWORDS):
                continue
            candidates.append(p)
        page += 1
        print(f"  페이지 {page}/{total_pages} — 누적 후보 {len(candidates)}개")

    # 할인액 큰 순으로 정렬 (중복 상품코드 제거)
    seen = set()
    unique = []
    for p in sorted(candidates, key=lambda x: x["discountPrice"]["value"], reverse=True):
        if p["code"] in seen:
            continue
        seen.add(p["code"])
        unique.append(p)
    selected = unique[:PRODUCT_COUNT] if PRODUCT_COUNT else unique

    if not selected:
        print("!! 할인 상품을 찾지 못했습니다. API 응답 구조가 바뀌었을 수 있습니다.")
        sys.exit(1)

    # 비할인 인기 상품 수집 (전체 검색 상위 노출 순)
    if POPULAR_COUNT:
        print(f"\n인기 상품(비할인) 수집 중... (목표 {POPULAR_COUNT}개)")
        pool_ = []
        page = 0
        while page < 5:
            data = fetch_page(page, POPULAR_API)
            for p in data.get("products", []):
                if p.get("as400Discount"):
                    continue  # 할인 상품은 이미 수집됨
                if p.get("code") in seen:
                    continue
                if not p.get("purchasable", True):
                    continue
                if p.get("stock", {}).get("stockLevelStatus") != "inStock":
                    continue
                price = p.get("basePrice", {}).get("value")
                if not price or not (MIN_PRICE <= price <= MAX_PRICE):
                    continue
                if any(k in p.get("name", "") for k in EXCLUDE_KEYWORDS):
                    continue
                seen.add(p["code"])
                pool_.append(p)
            page += 1
        # 리뷰 수 내림차순 → 상위 POPULAR_COUNT개
        pool_.sort(key=lambda x: int(x.get("numberOfReviews") or 0), reverse=True)
        popular = pool_[:POPULAR_COUNT]
        top = int(popular[0].get("numberOfReviews") or 0) if popular else 0
        print(f"  인기 상품 {len(popular)}개 확보 (리뷰 최다: {top:,}개)")
        selected = selected + popular

    # 상세정보(실제 설명 + 갤러리) 병렬 수집
    print(f"\n상세정보 수집 중... ({len(selected)}개, 동시 {DETAIL_WORKERS}건)")
    with ThreadPoolExecutor(max_workers=DETAIL_WORKERS) as pool:
        details = list(pool.map(lambda p: fetch_detail(p["code"]), selected))
    ok = sum(1 for d in details if d["detail_images"])
    print(f"  상세컷 이미지 확보: {ok}/{len(selected)}개")

    # 가격 정책 적용 (마진 미달 상품은 제외됨)
    site_products = []
    excluded = 0
    for p, d in zip(selected, details):
        sp = to_site_product(p, 0, d)
        if sp is None:
            excluded += 1
            continue
        sp["id"] = len(site_products) + 1
        site_products.append(sp)
    if excluded:
        print(f"  마진 {MIN_MARGIN_WON:,}원 미만으로 제외된 상품: {excluded}개")

    # 여름철(6~9월) 냉장·냉동 상품 제외 — 배송 중 변질 위험
    summer = datetime.now().month in SUMMER_MONTHS
    if summer:
        before = len(site_products)
        site_products = [p for p in site_products if not p.get("cold")]
        print(f"  여름철 냉장·냉동 제외: {before - len(site_products)}개")

    # 매장 전용 인기템(수동 큐레이션) 병합 — 맨 앞에 배치 후 id 일괄 재부여
    store_only_path = ROOT / "data" / "store_only.json"
    if store_only_path.exists():
        try:
            store_data = json.loads(store_only_path.read_text(encoding="utf-8"))
            # enabled: false 면 사이트에 노출하지 않음 (데이터는 보존)
            enabled = store_data.get("enabled", True)
            store_items = []
            for it in (store_data.get("items", []) if enabled else []):
                if summer and it.get("cold"):
                    continue  # 여름철 냉장·냉동 제외
                cp = it["costco_price"]
                store_items.append({
                    "id": 0,
                    "name": it["name"],
                    "category": it["category"],
                    "origin_price": cp,
                    "costco_price": cp,
                    "sale_price": round(cp * (1 + MARGIN_RATE) / ROUND_UNIT) * ROUND_UNIT,
                    "unit": it["unit"],
                    "max_qty": it["max_qty"],
                    "badge": "매장 전용",
                    "store_only": True,
                    "cold": it["cold"],
                    "description": it["description"],
                    "image": it["image"],
                    "gallery": [],
                    "detail_images": [],
                    "costco_url": "",
                })
            site_products = store_items + site_products
            print(f"  매장 전용 인기템 {len(store_items)}개 병합"
                  + ("" if enabled else "  (enabled=false — 숨김 상태)"))
        except Exception as e:
            print(f"!! store_only.json 병합 실패 (건너뜀): {e}")

    # id 일괄 재부여 (제외·병합 후 최종 순서 기준)
    for i, sp in enumerate(site_products, 1):
        sp["id"] = i

    now = datetime.now()
    deadline = next_deadline(now)
    result = {
        "week": week_label(now),
        "updated": now.strftime("%Y-%m-%d"),
        "order_deadline": deadline.strftime("%Y-%m-%dT%H:%M:%S"),
        "pickup_day": (deadline + timedelta(days=1)).strftime("%Y-%m-%d"),
        "notice": "이번 주 냉장·냉동 제품은 수요일 발송 기준으로 목~금 도착 예정입니다.",
        "products": site_products,
    }

    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n생성 완료: {OUTPUT} — 총 {len(result['products'])}개 상품")
    print("할인액 상위 10개:")
    for prod in result["products"][:10]:
        print(f"  [{prod['category']}] {prod['name']} — "
              f"코스트코가 {prod['costco_price']:,}원 → 대행가 {prod['sale_price']:,}원"
              f" ({prod['badge']})")

    if "--push" in sys.argv:
        print("\nGitHub에 push 중...")
        subprocess.run(["git", "add", "data/products.json"], cwd=ROOT, check=True)
        subprocess.run(["git", "commit", "-m", f"상품 업데이트: {result['week']}"],
                       cwd=ROOT, check=True)
        subprocess.run(["git", "push"], cwd=ROOT, check=True)
        print("push 완료 — GitHub Pages에 몇 분 내 반영됩니다.")


if __name__ == "__main__":
    main()
