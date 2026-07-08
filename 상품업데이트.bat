@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ════════════════════════════════════
echo   코스트코 대행 — 이번 주 상품 업데이트
echo ════════════════════════════════════
"C:\Users\gkwls\AppData\Local\Programs\Python\Python314\python.exe" -X utf8 scripts\update_products.py %*
echo.
if %errorlevel%==0 (
  echo 완료! 사이트에 새 상품이 반영되었습니다.
) else (
  echo 오류가 발생했습니다. 위 메시지를 확인해주세요.
)
pause
