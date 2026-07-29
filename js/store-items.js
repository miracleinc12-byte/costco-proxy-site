/* ─────────────────────────────────────────────
   매장(오프라인) 상품 공용 로더
   관리자가 admin.html에서 등록한 Firestore `store_products`를
   스토어프론트(products/order/cart)가 온라인 상품과 병합해 쓴다.
   어떤 실패에도 빈 배열 반환 → 사이트가 절대 안 깨지게.
   ───────────────────────────────────────────── */
async function loadStoreItems() {
  if (typeof db === 'undefined' || !db) return [];   // firebase 없으면 조용히 빈 배열
  try {
    const snap = await db.collection('store_products').get();
    const m = new Date().getMonth() + 1;
    const summer = m >= 6 && m <= 9;
    return snap.docs.map(d => ({ docId: d.id, ...d.data() }))
      .filter(x => x.active !== false)
      .filter(x => !(summer && x.cold))          // 여름철 냉장 제외 (기존 정책)
      .sort((a, b) => (b.createdAt?.seconds || 0) - (a.createdAt?.seconds || 0))  // 최신 먼저
      .map(x => ({
        id: 'S' + x.docId,                        // 문자열 id (온라인 int와 충돌 없음)
        name: x.name, category: x.category || '매장 인기템',
        costco_price: x.costcoPrice, origin_price: x.costcoPrice, sale_price: x.salePrice,
        unit: x.unit || '', max_qty: x.maxQty || 3,
        badge: '매장 전용', store_only: true, cold: !!x.cold,
        description: x.description || '', image: x.imageData || '',
        gallery: [], detail_images: [], costco_url: ''
      }));
  } catch (e) { console.warn('매장 상품 로드 실패:', e); return []; }  // 실패해도 사이트 안 깨짐
}
