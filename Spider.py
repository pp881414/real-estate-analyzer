import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import json
import re

# ── 設定區 ──────────────────────────────────────────────
REGION_ID   = 3    # 新北市
SECTION_ID  = 37   # 板橋區（可修改）
MAX_PAGES   = 5    # 最多抓幾頁（每頁約 30 筆）
DELAY_SEC   = 2    # 每次請求間隔（秒），避免被封鎖
# ────────────────────────────────────────────────────────


def build_session() -> tuple[requests.Session, dict, str | None]:
    s = requests.Session()
    base_url = f"https://sale.591.com.tw/?shType=list&regionid={REGION_ID}"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Deviceid": "591_web_pc",
        "Referer": base_url,
        "Origin": "https://sale.591.com.tw",
        "device": "pc",
    }

    print("🚀 步驟 1：正在進入 591 首頁獲取金鑰 (Token)...")
    try:
        r = s.get(base_url, headers=headers, timeout=15)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"❌ 首頁連線失敗：{e}")
        return s, headers, None

    soup = BeautifulSoup(r.text, "html.parser")
    meta = soup.find("meta", {"name": "csrf-token"})

    if not meta:
        print("❌ 無法取得 CSRF Token，591 防爬機制可能已升級。")
        return s, headers, None

    token = meta["content"]
    headers["X-CSRF-TOKEN"] = token
    print(f"✅ 取得 Token：{token[:12]}…")
    return s, headers, token


def fetch_page(s: requests.Session, headers: dict, page: int) -> list[dict]:
    first_row = page * 30
    api_url = (
        "https://bff-house.591.com.tw/v1/web/sale/list"
        f"?type=2&shType=list&regionid={REGION_ID}"
        f"&sectionid={SECTION_ID}&firstRow={first_row}&totalRows=3000"
        "&recom_community=1&category=1"
    )

    print(f"      🔗 請求 URL：{api_url}")
    try:
        time.sleep(DELAY_SEC)
        res = s.get(api_url, headers=headers, timeout=15)
        if res.status_code != 200:
            print(f"  ⚠️  HTTP {res.status_code}，回應前 300 字：\n{res.text[:300]}")
        res.raise_for_status()
    except requests.RequestException as e:
        print(f"  ⚠️  第 {page+1} 頁請求失敗：{e}")
        return []

    try:
        payload = res.json()
    except json.JSONDecodeError:
        print(f"  ⚠️  第 {page+1} 頁回傳非 JSON。")
        print("      前 200 字：", res.text[:200])
        return []

    data_block = payload.get("data", {})
    house_list = (
        data_block.get("house_list")
        or data_block.get("data", {}).get("house_list")
        or []
    )
    return house_list


def parse_unit_price(raw_price: str | None) -> float | None:
    """
    將 '58~63 萬元/坪' 或 '60 萬元/坪' 轉為數值（取區間平均）。
    回傳 float 或 None。
    """
    if not raw_price:
        return None
    nums = re.findall(r'[\d.]+', str(raw_price))
    if not nums:
        return None
    vals = [float(n) for n in nums]
    return round(sum(vals) / len(vals), 1)


def parse_total_price(raw_price: str | None, unit: str = "萬") -> float | None:
    """將總價字串轉為數值（萬元）。"""
    if not raw_price:
        return None
    nums = re.findall(r'[\d.]+', str(raw_price))
    if not nums:
        return None
    val = float(nums[0])
    # 若原始單位是億，換算成萬
    if "億" in str(unit):
        val = val * 10000
    return round(val, 1)


def parse_area(raw_area) -> float | None:
    """將坪數字串轉為數值，支援 '32.5坪'、'32.5' 等格式。"""
    if not raw_area:
        return None
    nums = re.findall(r'[\d.]+', str(raw_area))
    return float(nums[0]) if nums else None


def parse_house(h: dict) -> dict:
    """把單筆原始資料轉成統一欄位（與 Data_Center 相容）。"""
    # ── 總價（數值，萬）──────────────────────────────
    raw_price = h.get("show_price") or h.get("price")
    price_unit = h.get("show_price_unit", "萬")
    total_price_num = parse_total_price(raw_price, price_unit)

    # ── 坪數（數值）──────────────────────────────────
    raw_area = h.get("showarea") or h.get("area")
    area_num = parse_area(raw_area)

    # ── 單價（萬/坪）：多管齊下，找最可靠的來源 ──────
    # 優先級：unitprice（數值字串）> show_unitprice > unit_price（含單位字串）> 總價÷坪數
    unit_price_num = None
    if h.get("unitprice"):
        unit_price_num = parse_unit_price(str(h["unitprice"]))
    if unit_price_num is None and h.get("show_unitprice"):
        unit_price_num = parse_unit_price(str(h["show_unitprice"]))
    if unit_price_num is None and h.get("unit_price"):
        unit_price_num = parse_unit_price(str(h["unit_price"]))
    if unit_price_num is None and total_price_num and area_num and area_num > 0:
        unit_price_num = round(total_price_num / area_num, 1)

    # ── 型態正規化：build_purpose 優先，為空改用 shape_name ──
    # 實際欄位值範例：build_purpose='住宅大樓'、shape_name='電梯大樓'
    purpose_raw = str(h.get("build_purpose") or h.get("shape_name") or "")
    if "大樓" in purpose_raw or "華廈" in purpose_raw or "電梯" in purpose_raw:
        btype = "大樓"
    elif "公寓" in purpose_raw:
        btype = "公寓"
    elif "透天" in purpose_raw or "別墅" in purpose_raw:
        btype = "透天厝"
    elif "套房" in purpose_raw:
        btype = "套房"
    elif purpose_raw:
        btype = purpose_raw
    else:
        # 最後備用：type 數字對照
        type_map = {"1": "公寓", "2": "大樓", 1: "公寓", 2: "大樓",
                    "3": "華廈", 3: "華廈", "4": "透天厝", 4: "透天厝",
                    "8": "大樓", 8: "大樓", "9": "套房", 9: "套房"}
        btype = type_map.get(h.get("type"), "其他")

    # ── 屋齡（數值）──────────────────────────────────
    age_raw = h.get("houseage")
    if age_raw is None:
        age_raw = h.get("showhouseage", "")
    age_nums = re.findall(r'\d+', str(age_raw))
    age_num = float(age_nums[0]) if age_nums else None

    # ── 行政區 / 街道 ─────────────────────────────────
    # street_name 可能為 None，改用 address 欄位作為備援
    # 實際範例：street_name='成泰路三段173號對面'、address='中平路377巷'
    raw_addr = h.get("street_name") or h.get("address") or ""
    district = str(h.get("section_name") or "").replace("新北市", "").strip()

    street_match = re.search(
        r'([^\s,，、／/（(【\[]+?[路街巷弄](?:[一二三四五六七八九十\d]+段)?)',
        str(raw_addr)
    )
    if street_match:
        street = street_match.group(1)
    elif raw_addr:
        street = re.sub(r'\d+號.*$', '', str(raw_addr)).strip() or str(raw_addr)
    else:
        street = ""

    return {
        # ── Data_Center 相容欄位 ──
        "行政區":   district,
        "街道":     street,
        "型態":     btype,
        "樓層":     h.get("floor", ""),
        "屋齡":     age_num,
        "總價":     total_price_num,
        "單價":     unit_price_num,       # 數值，萬/坪（已對齊 Data_Center）
        # ── 591 額外資訊 ──────────
        "來源":     "591",
        "houseid":  h.get("houseid"),
        "坪數":     area_num,
        "格局":     h.get("room"),
        "完整地址": raw_addr,
        "標籤":     "、".join(h.get("tag", [])),
        "連結":     "https://sale.591.com.tw/home/house/detail/2/" + str(h.get("houseid", "")),
    }


def get_591_real_data(debug: bool = False) -> pd.DataFrame | None:
    s, headers, token = build_session()
    if not token:
        return None

    all_results = []
    print(f"\n🚀 步驟 2：開始抓取最多 {MAX_PAGES} 頁的資料…")

    for page in range(MAX_PAGES):
        print(f"  📄 第 {page + 1} 頁…", end=" ", flush=True)
        house_list = fetch_page(s, headers, page)

        if not house_list:
            print("沒有更多資料，停止。")
            break

        if debug and page == 0 and house_list:
            # 印出前5筆的 build_purpose 和 type，找出「其他」的原因
            print(f"\n🔍 [DEBUG] 前5筆的型態相關欄位：")
            for i, item in enumerate(house_list[:5]):
                print(f"  [{i+1}] build_purpose={item.get('build_purpose')!r:20}  type={item.get('type')!r:5}  street_name={item.get('street_name')!r}")
            print(f"\n🔍 [DEBUG] 第2筆完整欄位（街道為空的物件）：")
            for k, v in sorted(house_list[1].items()):
                print(f"     {k}: {v!r}")
            print()

        all_results.extend(parse_house(h) for h in house_list)
        print(f"取得 {len(house_list)} 筆（累計 {len(all_results)} 筆）")

        if len(house_list) < 30:
            print("  ✅ 已到最後一頁。")
            break

    if not all_results:
        print("\n❌ 未取得任何資料。")
        return None

    df = pd.DataFrame(all_results)
    total_raw = len(df)

    # 去除重複物件（同一 houseid）
    if 'houseid' not in df.columns:
        # 用關鍵欄位組合去重
        df = df.drop_duplicates(subset=['行政區', '街道', '型態', '屋齡', '總價', '坪數'])
    else:
        df = df.drop_duplicates(subset=['houseid']) if 'houseid' in df.columns else df

    # 只保留有效單價
    df_valid = df[df['單價'].notna() & (df['單價'] > 0)].copy()

    print(f"\n📊 單價覆蓋率：{len(df_valid)}/{total_raw} 筆（{round(len(df_valid)/total_raw*100)}%）")
    if total_raw - len(df_valid) > 0:
        print(f"   └─ {total_raw - len(df_valid)} 筆因無法計算單價（缺總價或坪數）而排除")

    print(f"\n🎊 共保留 {len(df_valid)} 筆有效房屋資料！")
    print(df_valid[['行政區', '街道', '型態', '屋齡', '單價', '總價', '坪數']].head(10).to_string(index=False))

    out_path = "591_live_data.csv"
    df_valid.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\n💾 已儲存至：{out_path}")
    return df_valid


if __name__ == "__main__":
    # 將 debug=True 可印出第一筆完整原始欄位，協助診斷 API 結構
    df = get_591_real_data(debug=False)