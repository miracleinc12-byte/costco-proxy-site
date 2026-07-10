/* ─────────────────────────────────────────────
   장바구니 공용 모듈 (localStorage 기반, 로그인 불필요)
   상품이 매주 갱신되므로 주차(week)가 바뀌면 자동으로 비워짐
   ───────────────────────────────────────────── */
const Cart = {
  KEY: 'cart',

  _load() {
    try { return JSON.parse(localStorage.getItem(this.KEY)) || { week: '', items: [] }; }
    catch { return { week: '', items: [] }; }
  },
  _save(data) {
    localStorage.setItem(this.KEY, JSON.stringify(data));
    this.renderBadge();
  },

  /** 현재 주차와 다르면 장바구니 초기화. 페이지에서 products.json 로드 후 호출 */
  syncWeek(week) {
    const data = this._load();
    if (data.week && data.week !== week && data.items.length) {
      this._save({ week, items: [] });
      return true; // 초기화됐음을 알림
    }
    if (data.week !== week) this._save({ week, items: data.items });
    return false;
  },

  items() { return this._load().items; },
  count() { return this.items().reduce((n, it) => n + it.qty, 0); },

  add(product, qty = 1) {
    const data = this._load();
    const found = data.items.find(it => it.id === product.id);
    const max = product.max_qty || 3;
    if (found) found.qty = Math.min(found.qty + qty, max);
    else data.items.push({ id: product.id, name: product.name, price: product.sale_price, qty: Math.min(qty, max) });
    this._save(data);
  },

  remove(id) {
    const data = this._load();
    data.items = data.items.filter(it => it.id !== id);
    this._save(data);
  },

  clear() {
    const data = this._load();
    this._save({ week: data.week, items: [] });
  },

  /** 장바구니 전체 교체 (주문서·장바구니 페이지와 동기화용) */
  setAll(items) {
    const data = this._load();
    this._save({ week: data.week, items });
  },

  /** 네비게이션 '주문하기' 버튼에 담긴 수량 배지 표시 */
  renderBadge() {
    const badge = document.getElementById('cart-badge');
    if (!badge) return;
    const n = this.count();
    badge.textContent = n > 0 ? n : '';
    badge.style.display = n > 0 ? 'inline-flex' : 'none';
  },

  /** 담기 완료 토스트 */
  toast(msg) {
    let el = document.getElementById('cart-toast');
    if (!el) {
      el = document.createElement('div');
      el.id = 'cart-toast';
      el.style.cssText = 'position:fixed;bottom:90px;left:50%;transform:translateX(-50%);' +
        'background:#0F2B57;color:#fff;padding:12px 22px;border-radius:30px;font-size:14px;' +
        'font-weight:700;z-index:999;opacity:0;transition:opacity .25s;box-shadow:0 8px 24px rgba(0,0,0,.3);' +
        'display:flex;gap:12px;align-items:center;white-space:nowrap;';
      el.innerHTML = '<span id="cart-toast-msg"></span><a href="cart.html" style="color:#93C5FD;font-weight:900">장바구니 보기 →</a>';
      document.body.appendChild(el);
    }
    document.getElementById('cart-toast-msg').textContent = msg;
    el.style.opacity = '1';
    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => { el.style.opacity = '0'; }, 2500);
  }
};

document.addEventListener('DOMContentLoaded', () => Cart.renderBadge());

/* HTML 이스케이프 (products.json 렌더링, Firestore 데이터 렌더링 공용) */
function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c =>
    ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' })[c]);
}
