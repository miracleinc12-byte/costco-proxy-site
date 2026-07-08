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
from datetime import datetime, timedelta
from pathlib import Path

# ──────────────────────────── 설정 ────────────────────────────
MARGIN_RATE = 0.15        # 대행 수수료율 (코스트코가 대비 15%)
ROUND_UNIT = 100          # 판매가 반올림 단위 (100원)
PRODUCT_COUNT = 0         # 사이트에 올릴 상품 수 (0 = 전부)
MIN_PRICE = 5000          # 이 금액 미만 상품 제외 (대행 실익 없음)
MAX_PRICE = 150000        # 이 금액 초과 상품 제외
DEADLINE_WEEKDAY = 2      # 주문 마감 요일 (0=월 ... 2=수)
DEADLINE_HOUR = 15        # 주문 마감 시각 (15시)

BASE = "https://www.costco.co.kr"
# '스페셜 할인'(SpecialPriceOffers) 카테고리 = 현재 할인 중인 상품 전체
API = (BASE + "/rest/v2/korea/products/search"
       "?query=%3Arelevance%3AallCategories%3ASpecialPriceOffers"
       "&pageSize=100&currentPage={page}"
       "&fields=products(code,name,englishName,price(FULL),basePrice(FULL),"
       "as400Discount,discountPrice(FULL),images(DEFAULT),maxOrderQuantity,"
       "stock(DEFAULT),url,purchasable),pagination&lang=ko&curr=KRW")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "data" / "products.json"

# 카테고리 자동 분류 키워드 (위에서부터 먼저 매칭)
CATEGORY_KEYWORDS = [
    ("생활용품", ["화장지", "티슈", "물티슈", "키친타월", "세제", "섬유유연제", "샴푸",
                "바디워시", "치약", "칫솔", "랩", "호일", "지퍼백", "종이컵", "수세미",
                "장갑", "건전지"]),
    ("냉장·냉동", ["냉동", "냉장", "신선", "아이스", "만두", "피자", "치즈", "우유",
                 "요거트", "요구르트", "버터", "베이컨", "소시지", "햄 ", "생연어",
                 "삼겹", "목살", "등심", "닭가슴", "새우", "굴비", "장어"]),
    ("뷰티", ["크림", "세럼", "로션", "에센스", "마스크팩", "선크림", "클렌징", "토너"]),
    ("베이커리", ["크루아상", "베이글", "머핀", "케이크", "식빵", "빵", "타르트", "파이"]),
    ("건강기능식품", ["비타민", "오메가", "유산균", "프로바이오틱", "루테인", "홍삼",
                    "콜라겐", "밀크씨슬", "글루코사민", "칼슘", "마그네슘", "아연",
                    "영양제", "캡슐", "드시모네"]),
    ("간식·건과", ["너트", "아몬드", "캐슈", "피스타치오", "호두", "땅콩", "과자",
                 "초콜릿", "쿠키", "젤리", "칩", "크래커", "시리얼", "그래놀라", "건포도", "망고"]),
    ("음료·커피", ["커피", "원두", "카누", "티백", "녹차", "주스", "탄산", "음료", "생수", "우유"]),
    ("식품", ["쌀", "김치", "라면", "국수", "파스타", "소스", "기름", "올리브", "간장",
             "된장", "고추장", "참치", "햇반", "김 ", "미역", "통조림", "꿀", "잼"]),
]
COLD_KEYWORDS = ["냉동", "냉장", "신선", "아이스", "만두", "피자", "치즈", "우유",
                 "요거트", "요구르트", "버터", "베이컨", "소시지", "생연어", "삼겹",
                 "목살", "등심", "닭가슴", "새우", "장어", "횟감"]
# 대행 부적합 상품 제외 키워드 (설치·대형·주류 등)
EXCLUDE_KEYWORDS = ["설치", "타이어", "가구", "매트리스", "소파", "냉장고", "세탁기",
                    "TV", "텔레비전", "에어컨", "와인", "위스키", "맥주", "소주", "양주"]


def fetch_page(page: int) -> dict:
    req = urllib.request.Request(API.format(page=page), headers={"User-Agent": UA})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=30, context=ctx) as res:
        return json.load(res)


def pick_image(images: list) -> str:
    for fmt in ("product", "results", "thumbnail"):
        for img in images or []:
            if img.get("format") == fmt and img.get("url", "").endswith(".jpg"):
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
    """다음 주문 마감 시각 (다가오는 수요일 15:00)"""
    days_ahead = (DEADLINE_WEEKDAY - now.weekday()) % 7
    candidate = (now + timedelta(days=days_ahead)).replace(
        hour=DEADLINE_HOUR, minute=0, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=7)
    return candidate


def week_label(now: datetime) -> str:
    week_no = (now.day - 1) // 7 + 1
    return f"{now.year}년 {now.month}월 {week_no}주차"


def to_site_product(p: dict, pid: int) -> dict:
    base_price = int(p["basePrice"]["value"])
    discount = int(p.get("discountPrice", {}).get("value") or 0)
    costco_price = base_price - discount  # 실제 결제될 코스트코 가격
    sale_price = round(costco_price * (1 + MARGIN_RATE) / ROUND_UNIT) * ROUND_UNIT
    name = p["name"].strip()
    return {
        "id": pid,
        "name": name,
        "category": classify(name),
        "costco_price": costco_price,
        "sale_price": sale_price,
        "unit": extract_unit(name),
        "max_qty": min(int(p.get("maxOrderQuantity") or 3), 3),
        "badge": f"{discount:,}원 할인" if discount else "이번 주 특가",
        "cold": is_cold(name),
        "description": f"코스트코 정가 {base_price:,}원에서 {discount:,}원 할인 중인 상품입니다.",
        "image": pick_image(p.get("images")),
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

    now = datetime.now()
    deadline = next_deadline(now)
    result = {
        "week": week_label(now),
        "updated": now.strftime("%Y-%m-%d"),
        "order_deadline": deadline.strftime("%Y-%m-%dT%H:%M:%S"),
        "pickup_day": (deadline + timedelta(days=1)).strftime("%Y-%m-%d"),
        "notice": "이번 주 냉장·냉동 제품은 목요일 발송 기준으로 금·토 도착 예정입니다.",
        "products": [to_site_product(p, i + 1) for i, p in enumerate(selected)],
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
