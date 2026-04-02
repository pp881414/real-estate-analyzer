[![Demo](https://img.shields.io/badge/🚀%20Live%20Demo-house--diagnosis.streamlit.app-ff4b4b?style=for-the-badge)](https://house-diagnosis.streamlit.app/)
> ⚠️ 本系統資料範圍僅涵蓋**新北市**，請輸入新北市的地址或行政區進行查詢。
# 🏠 智慧房價診斷系統 — 使用說明

## 📁 檔案結構

```
專案資料夾/
├── app.py                  # 主網頁介面
├── daily_alert.py          # LINE 每日警報
├── Spider.py               # 591 爬蟲
├── Data_Center.py          # 資料整合
├── price_model_v2.py       # AI 估價模型
├── .env                    # 🔐 LINE Token（勿外傳）
├── 啟動系統.bat            # Windows 一鍵啟動
├── 啟動系統.sh             # Mac/Linux 一鍵啟動
├── raw_data/               # 放實價登錄 CSV
├── real_estate_market_pro.csv   # 整合後資料庫
└── price_model_v2.pkl      # 訓練好的模型
```

---

## 🚀 第一次使用（環境設定）

### 1. 設定 LINE Token（填入 .env）
打開 `.env`，把兩行填入你的真實資料：
```
LINE_CHANNEL_TOKEN=你的Token
LINE_USER_ID=你的UserID
```

### 2. 準備資料庫
```bash
# 先爬 591 掛牌資料
python Spider.py

# 再合併整合（需先把實價登錄 CSV 放進 raw_data/）
python Data_Center.py
```

### 3. 訓練 AI 模型（可選）
```bash
python price_model_v2.py --train
```

---

## 🖥️ 每次啟動

### Windows
直接雙擊 `啟動系統.bat`

### Mac / Linux
```bash
chmod +x 啟動系統.sh
./啟動系統.sh
```

### 手動啟動
```bash
streamlit run app.py
```

---

## 🌐 讓外部電腦連線（報告用）

啟動時選 `y` 開啟 ngrok，會產生類似這樣的網址：
```
✅ 外部連線網址：https://xxxx-xx-xx-xx.ngrok-free.app
```
把網址傳給其他人，他們用瀏覽器打開即可。

> ⚠️ ngrok 免費版每次重啟網址會改變，報告當天啟動後不要關閉。

---

## 📊 資料流程

```
591 網站 → Spider.py → 591_live_data.csv
實價登錄 CSV → raw_data/
                        ↓
                 Data_Center.py
                        ↓
          real_estate_market_pro.csv
                        ↓
         price_model_v2.py --train
                        ↓
           price_model_v2.pkl  ←  app.py 讀取
```
