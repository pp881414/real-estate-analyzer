#!/bin/bash

echo ""
echo " ╔══════════════════════════════════════╗"
echo " ║   🏠  智慧房價診斷系統  啟動中...    ║"
echo " ╚══════════════════════════════════════╝"
echo ""

# 確認 Python
if ! command -v python3 &>/dev/null; then
    echo "❌ 找不到 Python3，請先安裝 Python 3.10+"
    exit 1
fi

# 安裝依賴
echo "📦 確認套件安裝中..."
pip3 install streamlit pandas requests beautifulsoup4 plotly scikit-learn pyngrok -q

echo ""
echo "✅ 套件確認完成！"
echo ""

# 詢問是否 ngrok
read -p "是否要讓外部電腦也能連線？(y/n): " USE_NGROK

if [ "$USE_NGROK" = "y" ] || [ "$USE_NGROK" = "Y" ]; then
    echo ""
    echo "🌐 正在建立公開網址（ngrok）..."
    python3 -c "
from pyngrok import ngrok
t = ngrok.connect(8501)
print('\n  ✅ 外部連線網址：' + t.public_url)
print('  （把這個網址傳給其他人即可開啟）\n')
" &
    sleep 3
fi

streamlit run app.py --server.headless false
