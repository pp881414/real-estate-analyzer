@echo off
chcp 65001 >nul
title 智慧房價診斷系統

echo.
echo  ╔══════════════════════════════════════╗
echo  ║   🏠  智慧房價診斷系統  啟動中...    ║
echo  ╚══════════════════════════════════════╝
echo.

:: 檢查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 找不到 Python，請先安裝 Python 3.10+
    pause
    exit /b
)

:: 安裝依賴（首次執行）
echo 📦 確認套件安裝中...
pip install streamlit pandas requests beautifulsoup4 plotly scikit-learn pyngrok -q

:: 啟動 Streamlit
echo.
echo ✅ 套件確認完成，正在啟動網頁...
echo.

:: 詢問是否要開放外部連線（ngrok）
set /p USE_NGROK="是否要讓外部電腦也能連線？(y/n): "

if /i "%USE_NGROK%"=="y" (
    echo.
    echo 🌐 正在建立公開網址（ngrok）...
    echo    請稍候，網址將顯示在下方
    echo.
    start /b python -c "from pyngrok import ngrok; t = ngrok.connect(8501); print('\n\n  ✅ 外部連線網址：' + t.public_url + '\n'); input('按 Enter 關閉...')"
    timeout /t 3 >nul
)

streamlit run app.py --server.headless false

pause
