"""
daily_alert.py — 每日 CP 值房源警報（改善版）
執行方式：python daily_alert.py
改善項目：
  1. regionid 改為可設定，支援多縣市
  2. MAX_PAGES 調高為 10，最多爬 300 筆/區
  3. 無法識別型態不再預設大樓，改標記為「其他」並跳過比對
  4. 無符合物件時靜默，不發 LINE，改用摘要通知
"""

import requests
import io
import sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
import pandas as pd
import re
import os
import time
import json
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from datetime import datetime

# ── 自動載入 .env（若存在）──
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.exists(_env_path):
    with open(_env_path, encoding='utf-8') as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _v = _line.split('=', 1)
                os.environ.setdefault(_k.strip(), _v.strip())

# ==========================================
# ⚙️  使用者設定區
# ==========================================

LINE_CHANNEL_TOKEN = os.environ.get("LINE_CHANNEL_TOKEN", "")
LINE_USER_ID       = os.environ.get("LINE_USER_ID", "")

# ── 改善1：縣市 regionid 對照表，不再寫死 ──
REGION_MAP = {
    "台北市": 1,
    "新北市": 3,
    "桃園市": 6,
    "台中市": 8,
    "台南市": 20,
    "高雄市": 22,
}
DEFAULT_REGION = "新北市"   # 預設縣市

# ── 改善2：大幅提高爬取頁數上限 ──
MAX_PAGES  = 10    # 每區最多 10 頁 × 30 筆 = 300 筆
DELAY_SEC  = 2

DB_PATH     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "real_estate_market_pro.csv")
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alert_config.json")

DISTRICT_MAP = {
    "板橋區": 37, "三重區": 46, "中和區": 39, "永和區": 52,
    "新莊區": 55, "新店區": 54, "土城區": 49, "蘆洲區": 53,
    "樹林區": 48, "汐止區": 44, "淡水區": 47, "泰山區": 50,
    "林口區": 41, "五股區": 51, "鶯歌區": 57, "三峽區": 45,
}

# ==========================================
# ⚙️  設定讀取
# ==========================================

def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        print(f"[OK] 讀取設定：{CONFIG_PATH}")
        return cfg
    print("[WARN] 找不到 alert_config.json，使用預設值")
    return {
        "districts":  ["板橋區"],
        "threshold":  [-20, -10],
        "max_alerts": 10,
        "house_types": ["大樓"],
        "region":     DEFAULT_REGION,   # 新增縣市欄位
    }

# ==========================================
# 📡 爬蟲模組
# ==========================================

def build_session(region_id: int, section_id: int):
    from bs4 import BeautifulSoup
    s = requests.Session()
    base_url = (
        f"https://sale.591.com.tw/?shType=list"
        f"&regionid={region_id}&sectionid={section_id}"
    )
    headers = {
        "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
        "Accept":          "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With":"XMLHttpRequest",
        "Deviceid":        "591_web_pc",
        "Referer":         base_url,
        "Origin":          "https://sale.591.com.tw",
        "device":          "pc",
    }
    try:
        r = s.get(base_url, headers=headers, timeout=15, verify=False)
        soup = BeautifulSoup(r.text, "html.parser")
        meta = soup.find("meta", {"name": "csrf-token"})
        if meta:
            headers["X-CSRF-TOKEN"] = meta["content"]
    except Exception:
        pass
    return s, headers


def fetch_listings(district_name: str, section_id: int, region_id: int) -> pd.DataFrame:
    """
    爬指定行政區的 591 掛牌物件。
    改善：傳入 region_id，支援多縣市；MAX_PAGES 提高到 10。
    """
    print(f"  📡 爬取 {district_name}（最多 {MAX_PAGES} 頁）...")
    s, headers = build_session(region_id, section_id)
    results = []

    for page in range(MAX_PAGES):
        first_row = page * 30
        api_url = (
            f"https://bff-house.591.com.tw/v1/web/sale/list"
            f"?type=2&shType=list&regionid={region_id}"
            f"&sectionid={section_id}&firstRow={first_row}&totalRows=3000"
            f"&recom_community=1&category=1"
        )
        try:
            time.sleep(DELAY_SEC)
            res = s.get(api_url, headers=headers, timeout=15, verify=False)
            if res.status_code != 200:
                print(f"    ⚠️ 第 {page+1} 頁 HTTP {res.status_code}，停止")
                break
            payload   = res.json()
            data_block = payload.get("data", {})
            house_list = (
                data_block.get("house_list")
                or data_block.get("data", {}).get("house_list")
                or []
            )
            if not house_list:
                print(f"    ℹ️ 第 {page+1} 頁無資料，停止")
                break

            before = len(results)
            for h in house_list:
                parsed = parse_house(h, district_name)
                if parsed:
                    results.append(parsed)
            print(f"    第 {page+1} 頁：+{len(results)-before} 筆（有效），共 {len(results)} 筆")

            if len(house_list) < 30:
                print(f"    ℹ️ 已到最後一頁")
                break

        except Exception as e:
            print(f"    ⚠️ 第 {page+1} 頁失敗：{e}")
            break

    print(f"    ✅ {district_name} 共取得 {len(results)} 筆有效物件")
    return pd.DataFrame(results) if results else pd.DataFrame()


def sf(val):
    try:
        return float(re.findall(r'[\d.]+', str(val))[0])
    except Exception:
        return None


# ── 改善3：型態無法識別時回傳 None，不再強制預設「大樓」 ──
BTYPE_KEYWORDS = {
    "大樓":  ["大樓", "華廈", "電梯大廈"],
    "公寓":  ["公寓"],
    "透天厝": ["透天", "別墅", "透天厝"],
}

def classify_btype(raw: str) -> str | None:
    """
    明確分類建物型態。
    無法識別 → 回傳 None（呼叫端應跳過此筆，避免錯誤比對）。
    """
    for btype, keywords in BTYPE_KEYWORDS.items():
        if any(kw in raw for kw in keywords):
            return btype
    return None   # 無法識別，不猜測


def parse_house(h: dict, district_name: str) -> dict | None:
    # 總價 / 坪數 / 單價
    total      = sf(h.get("show_price") or h.get("price"))
    area       = sf(h.get("showarea")   or h.get("area"))
    unit_price = sf(h.get("unitprice")  or h.get("show_unitprice") or h.get("unit_price"))
    if unit_price is None and total and area and area > 0:
        unit_price = round(total / area, 1)
    if not unit_price or unit_price <= 0:
        return None

    # 型態 — 改善3：無法識別直接跳過
    raw_purpose = str(h.get("build_purpose") or h.get("shape_name") or "")
    btype = classify_btype(raw_purpose)
    if btype is None:
        return None   # 捨棄無法分類的物件

    # 屋齡
    age_nums = re.findall(r'\d+', str(h.get("houseage") or h.get("showhouseage") or ""))
    age = float(age_nums[0]) if age_nums else None

    # 街道
    raw_addr = h.get("street_name") or h.get("address") or ""
    street_m = re.search(
        r'([^\s,，、／/（(【\[]+?[路街巷弄](?:[一二三四五六七八九十\d]+段)?)',
        str(raw_addr)
    )
    street = street_m.group(1) if street_m else str(raw_addr)

    house_id = h.get("houseid", "")
    return {
        "行政區": district_name,
        "街道":   street,
        "型態":   btype,
        "屋齡":   age,
        "單價":   unit_price,
        "總價":   total,
        "坪數":   area,
        "樓層":   str(h.get("floor", "")),
        "標題":   str(h.get("title") or raw_addr),
        "連結":   f"https://sale.591.com.tw/home/house/detail/2/{house_id}.html",
        "houseid": str(house_id),
    }


# ==========================================
# 🔍 行情比對
# ==========================================

def load_market_db() -> pd.DataFrame | None:
    if not os.path.exists(DB_PATH):
        print(f"[ERR] 找不到資料庫：{DB_PATH}")
        return None
    df = pd.read_csv(DB_PATH, encoding="utf-8-sig")
    df["單價"] = pd.to_numeric(df["單價"], errors="coerce")
    df = df[df["來源"] == "實價登錄"].dropna(subset=["單價", "行政區", "街道"])
    return df


MIN_SAMPLES  = 5
AGE_WINDOW   = 3
AGE_FALLBACK = 8

def get_market_price(
    db: pd.DataFrame,
    district: str,
    street: str,
    btype: str,
    age: float | None,
) -> tuple[float | None, str]:
    """
    三層 fallback 查詢行情中位數。
    回傳 (市場均價, 使用的比對層級描述)，便於 debug。
    """
    def age_filter(ref, window):
        if age is not None and not ref.empty:
            sim = ref[(ref["屋齡"] >= age - window) & (ref["屋齡"] <= age + window)]
            return sim if not sim.empty else pd.DataFrame()
        return ref

    base_mask = (db["行政區"] == district) & (db["型態"].str.contains(btype, na=False))

    # 層級1：同路段 + 嚴格屋齡
    ref = age_filter(db[base_mask & (db["街道"] == street)], AGE_WINDOW)
    if len(ref) >= MIN_SAMPLES:
        return round(ref["單價"].median(), 1), f"同路段±{AGE_WINDOW}年({len(ref)}筆)"

    # 層級1b：路段前3字模糊
    if len(street) >= 3:
        ref = age_filter(db[base_mask & db["街道"].str.startswith(street[:3])], AGE_WINDOW)
        if len(ref) >= MIN_SAMPLES:
            return round(ref["單價"].median(), 1), f"模糊路段±{AGE_WINDOW}年({len(ref)}筆)"

    # 層級2：同行政區 + 嚴格屋齡
    ref = age_filter(db[base_mask], AGE_WINDOW)
    if len(ref) >= MIN_SAMPLES:
        return round(ref["單價"].median(), 1), f"同區±{AGE_WINDOW}年({len(ref)}筆)"

    # 層級3：同行政區 + 放寬屋齡
    ref = age_filter(db[base_mask], AGE_FALLBACK)
    if not ref.empty:
        return round(ref["單價"].median(), 1), f"同區±{AGE_FALLBACK}年({len(ref)}筆)"

    # 最終備用：整個行政區
    ref = db[base_mask]
    if not ref.empty:
        return round(ref["單價"].median(), 1), f"同區全部({len(ref)}筆)"

    return None, "無比對資料"


def find_cp_listings(
    listings: pd.DataFrame,
    db: pd.DataFrame,
    threshold,
    max_alerts: int,
) -> pd.DataFrame:
    t_low, t_high = (
        (threshold[0], threshold[1])
        if isinstance(threshold, (list, tuple))
        else (threshold, 0)
    )
    results = []
    for _, row in listings.iterrows():
        market_p, ref_note = get_market_price(
            db, row["行政區"], row["街道"], row["型態"], row["屋齡"]
        )
        if market_p is None:
            continue
        diff = round(((row["單價"] - market_p) / market_p) * 100, 1)
        if t_low <= diff <= t_high:
            results.append({**row.to_dict(), "行情均價": market_p, "價差": diff, "比對依據": ref_note})

    if not results:
        return pd.DataFrame()
    return pd.DataFrame(results).sort_values("價差").head(max_alerts)


# ==========================================
# 📲 LINE 發送
# ==========================================

def send_line(message: str) -> bool:
    try:
        res = requests.post(
            "https://api.line.me/v2/bot/message/push",
            headers={
                "Authorization": f"Bearer {LINE_CHANNEL_TOKEN}",
                "Content-Type":  "application/json",
            },
            json={"to": LINE_USER_ID, "messages": [{"type": "text", "text": message}]},
            timeout=180,
        )
        if res.status_code == 200:
            return True
        print(f"[ERR] LINE 發送失敗 HTTP {res.status_code}：{res.text[:200]}")
        return False
    except Exception as e:
        print(f"[ERR] LINE 發送失敗：{e}")
        return False


def format_line_message(cp_df: pd.DataFrame, district_name: str, threshold) -> str:
    now = datetime.now().strftime("%m/%d %H:%M")
    t_low, t_high = (
        (threshold[0], threshold[1])
        if isinstance(threshold, (list, tuple))
        else (threshold, 0)
    )
    lines = [
        f"\n🏠【{district_name} CP值警報】{now}",
        f"門檻：行情偏離 {t_low}%～{t_high}%，共 {len(cp_df)} 筆\n",
    ]
    for i, (_, row) in enumerate(cp_df.iterrows(), 1):
        age_str = f"{row['屋齡']:.0f}年" if pd.notna(row.get("屋齡")) else "屋齡不詳"
        lines.append(
            f"{'─'*25}\n"
            f"[{i}] {row['街道']} {row['型態']} {age_str}\n"
            f"  單價：{row['單價']} 萬/坪（行情 {row['行情均價']}，{row['價差']:+.1f}%）\n"
            f"  比對：{row.get('比對依據','')}\n"
            f"  總價：{row['總價']} 萬 / {row['坪數']} 坪\n"
            f"  🔗 {row['連結']}"
        )
    return "\n".join(lines)


# ==========================================
# 🚀 主程式
# ==========================================

def main():
    cfg         = load_config()
    districts   = cfg.get("districts",  ["板橋區"])
    threshold   = cfg.get("threshold",  [-20, -10])
    max_alerts  = cfg.get("max_alerts", 10)
    house_types = cfg.get("house_types", ["大樓"])
    # 改善1：從設定讀縣市，找對應 region_id
    region_name = cfg.get("region", DEFAULT_REGION)
    region_id   = REGION_MAP.get(region_name, 3)

    print("=" * 55)
    print("[INFO] 每日 CP 值房源警報系統（改善版）")
    print(f"  縣市：{region_name}（regionid={region_id}）")
    print(f"  監控：{', '.join(districts)}")
    print(f"  門檻：{threshold}，最多 {max_alerts} 筆/區")
    print(f"  類型：{', '.join(house_types)}")
    print("=" * 55)

    db = load_market_db()
    if db is None:
        return
    print(f"[OK] 實價登錄 {len(db):,} 筆")

    # ── 改善4：收集各區結果，最後統一摘要通知 ──
    summary_hits   = []   # 有找到物件的區
    summary_nohits = []   # 無物件的區（靜默，不個別發 LINE）
    total_sent     = 0

    for district_name in districts:
        section_id = DISTRICT_MAP.get(district_name)
        if section_id is None:
            print(f"[WARN] 找不到 {district_name} 的 section_id，跳過")
            continue

        print(f"\n{'─'*40}")
        print(f"[INFO] 處理：{district_name}")

        listings = fetch_listings(district_name, section_id, region_id)
        if listings.empty:
            print(f"[WARN] 無法取得 {district_name} 的物件")
            summary_nohits.append(f"{district_name}（爬蟲失敗）")
            continue

        # 依房屋類型過濾
        listings = listings[listings["型態"].isin(house_types)]
        if listings.empty:
            print(f"[WARN] {district_name} 過濾類型後無資料")
            summary_nohits.append(f"{district_name}（無符合類型）")
            continue

        print(f"[INFO] 過濾後剩 {len(listings)} 筆，開始比對行情...")

        cp_df = find_cp_listings(listings, db, threshold, max_alerts)

        if cp_df.empty:
            # 改善4：無符合物件 → 靜默，不單獨發通知
            print(f"[INFO] {district_name} 今日無符合門檻物件（靜默）")
            summary_nohits.append(district_name)
            continue

        print(f"[OK] {district_name} 找到 {len(cp_df)} 筆 CP 值物件")
        msg = format_line_message(cp_df, district_name, threshold)
        if send_line(msg):
            print("[OK] LINE 通知已發送")
            total_sent += len(cp_df)
            summary_hits.append(f"{district_name}（{len(cp_df)}筆）")
        else:
            print("[ERR] LINE 通知發送失敗")

    # ── 改善4：發送整體執行摘要（只有一則） ──
    now = datetime.now().strftime("%m/%d %H:%M")
    t_low, t_high = (
        (threshold[0], threshold[1])
        if isinstance(threshold, (list, tuple))
        else (threshold, 0)
    )
    summary_lines = [
        f"\n📊【執行摘要】{now}",
        f"縣市：{region_name}　門檻：{t_low}%～{t_high}%",
        f"共通知 {total_sent} 筆 CP 值物件",
    ]
    if summary_hits:
        summary_lines.append(f"\n✅ 有物件：{'、'.join(summary_hits)}")
    if summary_nohits:
        summary_lines.append(f"⭕ 無符合：{'、'.join(summary_nohits)}")

    send_line("\n".join(summary_lines))

    print(f"\n{'='*55}")
    print(f"[OK] 完成！共通知 {total_sent} 筆 CP 值物件")
    print(f"{'='*55}")
def run_alert_and_return(cfg_override: dict = None) -> str:
    cfg         = cfg_override or load_config()
    districts   = cfg.get("districts",  ["板橋區"])
    threshold   = cfg.get("threshold",  [-20, -10])
    max_alerts  = cfg.get("max_alerts", 10)
    house_types = cfg.get("house_types", ["大樓"])
    region_name = cfg.get("region", DEFAULT_REGION)
    region_id   = REGION_MAP.get(region_name, 3)

    db = load_market_db()
    if db is None:
        return "❌ 無法載入資料庫"

    summary_hits    = []
    summary_nohits  = []
    total_sent      = 0
    detail_messages = []

    for district_name in districts:
        section_id = DISTRICT_MAP.get(district_name)
        if section_id is None:
            continue
        listings = fetch_listings(district_name, section_id, region_id)
        if listings.empty:
            summary_nohits.append(f"{district_name}（爬蟲失敗）")
            continue
        listings = listings[listings["型態"].isin(house_types)]
        if listings.empty:
            summary_nohits.append(f"{district_name}（無符合類型）")
            continue
        cp_df = find_cp_listings(listings, db, threshold, max_alerts)
        if cp_df.empty:
            summary_nohits.append(district_name)
            continue
        total_sent += len(cp_df)
        summary_hits.append(f"{district_name}（{len(cp_df)}筆）")
        detail_messages.append(format_line_message(cp_df, district_name, threshold))

    from zoneinfo import ZoneInfo
    now = datetime.now(tz=ZoneInfo('Asia/Taipei')).strftime("%m/%d %H:%M")
    t_low, t_high = (
        (threshold[0], threshold[1])
        if isinstance(threshold, (list, tuple))
        else (threshold, 0)
    )
    lines = [
        f"📊【執行摘要】{now}",
        f"縣市：{region_name}　門檻：{t_low}%～{t_high}%",
        f"共通知 {total_sent} 筆 CP 值物件",
    ]
    if summary_hits:
        lines.append(f"✅ 有物件：{'、'.join(summary_hits)}")
    if summary_nohits:
        lines.append(f"⭕ 無符合：{'、'.join(summary_nohits)}")

    all_messages = detail_messages + ["\n".join(lines)]
    return "\n\n".join(all_messages)

if __name__ == "__main__":
    main()