(function () {
  'use strict';

  // 입장 코드 — 여기만 바꾸면 됨
  const ACCESS_CODE = 'wc2026';
  const KEY = 'wc_invite';

  // 링크 공유 자동입장: ?code=XXX 가 일치하면 저장
  const urlCode = new URLSearchParams(location.search).get('code');
  if (urlCode && urlCode.trim() === ACCESS_CODE) {
    localStorage.setItem(KEY, ACCESS_CODE);
  }

  // 이미 통과한 상태면 아무것도 안 함
  if (localStorage.getItem(KEY) === ACCESS_CODE) return;

  // 콘텐츠 번쩍임 방지
  document.documentElement.style.visibility = 'hidden';

  const CART_SVG =
    '<svg viewBox="0 0 24 24" width="30" height="30" fill="none" stroke="#2563EB" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="8" cy="21" r="1"/><circle cx="19" cy="21" r="1"/><path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12"/></svg>';

  function buildGate() {
    document.body.innerHTML =
      '<div style="position:fixed;inset:0;background:#0F2B57;display:flex;align-items:center;justify-content:center;padding:24px;box-sizing:border-box;font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,\'Helvetica Neue\',sans-serif;z-index:2147483647;">' +
        '<div style="background:#fff;border-radius:16px;padding:40px 32px;max-width:380px;width:100%;box-sizing:border-box;text-align:center;box-shadow:0 20px 50px rgba(0,0,0,.35);">' +
          '<div style="display:flex;align-items:center;justify-content:center;gap:8px;margin-bottom:6px;">' +
            CART_SVG +
            '<span style="font-size:26px;font-weight:900;color:#0F2B57;">위클리<span style="color:#2563EB;">카트</span></span>' +
          '</div>' +
          '<p style="color:#475569;font-size:15px;margin:0 0 24px;">초대 코드를 입력해주세요</p>' +
          '<input id="wc-gate-input" type="text" autocomplete="off" placeholder="초대 코드" ' +
            'style="width:100%;box-sizing:border-box;text-align:center;font-size:20px;letter-spacing:2px;padding:14px;border:2px solid #CBD5E1;border-radius:10px;outline:none;margin-bottom:6px;">' +
          '<p id="wc-gate-error" style="color:#DC2626;font-size:13px;margin:0 0 12px;min-height:18px;visibility:hidden;">코드가 올바르지 않습니다</p>' +
          '<button id="wc-gate-btn" style="width:100%;background:#0F2B57;color:#fff;font-size:16px;font-weight:800;padding:14px;border:none;border-radius:10px;cursor:pointer;">입장하기</button>' +
          '<p style="color:#94A3B8;font-size:12px;line-height:1.6;margin:20px 0 0;">초대받은 분만 이용할 수 있는 테스트 기간입니다 · ' +
            '<a href="https://pf.kakao.com/_xgVywX/chat" target="_blank" rel="noopener" style="color:#94A3B8;">문의: 카카오톡 채널</a></p>' +
        '</div>' +
      '</div>';

    const input = document.getElementById('wc-gate-input');
    const error = document.getElementById('wc-gate-error');
    const btn = document.getElementById('wc-gate-btn');

    function submit() {
      if (input.value.trim() === ACCESS_CODE) {
        localStorage.setItem(KEY, ACCESS_CODE);
        location.reload();
      } else {
        input.style.borderColor = '#DC2626';
        error.style.visibility = 'visible';
        input.value = '';
        input.focus();
      }
    }

    btn.addEventListener('click', submit);
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') submit();
    });
    input.focus();
  }

  function init() {
    buildGate();
    document.documentElement.style.visibility = 'visible';
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
