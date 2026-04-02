import pandas as pd
import re
import requests
import time
import sys
import threading
import os
import json

# ==========================================
# ⚙️ 系統設定區
# ==========================================
MY_API_KEY = ""   # 每次執行時由用戶輸入

C_BOLD   = '\033[1m'
C_GREEN  = '\033[92m'
C_YELLOW = '\033[93m'
C_RED    = '\033[91m'
C_CYAN   = '\033[96m'
C_BLUE   = '\033[94m'
C_END    = '\033[0m'
BG_RED   = '\033[41m'


def typewriter_print(text, speed=0.002):
    for char in text:
        sys.stdout.write(char); sys.stdout.flush(); time.sleep(speed)
    print()


def show_welcome_banner():
    os.system('cls' if os.name == 'nt' else 'clear')
    line1 = "Smart House Price Diagnosis System"
    line2 = "智慧房價診斷與議價輔助系統 (V2.2 Professional)"
    line3 = "數據驅動 . AI 賦能 . 貼網址秒速診斷"
    w = 64

    def get_display_len(text):
        return sum(2 if '\u4e00' <= c <= '\u9fff' else 1 for c in text)

    def print_border_line(text):
        padding = w - get_display_len(text) - 6
        print(f"{C_CYAN}║  {C_END}{C_BOLD if 'System' in text else ''}{text}{C_END}{' ' * padding}{C_CYAN}  ║{C_END}")

    print(f"\n{C_CYAN}╔{'═' * (w - 2)}╗{C_END}")
    print_border_line(line1); print_border_line(line2); print_border_line(line3)
    print(f"{C_CYAN}╚{'═' * (w - 2)}╝{C_END}")
    time.sleep(0.5)


# ==========================================
# ⏳ 倒數計時動畫
# ==========================================
class LoadingAnimation:
    def __init__(self, message="分析中", seconds=60):
        self.message = message
        self.remaining = seconds
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._animate, daemon=True)

    def _animate(self):
        chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        idx = 0
        start_time = time.time()
        total_seconds = self.remaining
        while not self.stop_event.is_set():
            elapsed = time.time() - start_time
            current_remaining = max(0, int(total_seconds - elapsed))
            sys.stdout.write(f'\r{C_CYAN}{chars[idx % len(chars)]} {self.message} {C_YELLOW}(剩餘 {current_remaining} 秒)...{C_END}')
            sys.stdout.flush()
            idx += 1
            time.sleep(0.1)
        sys.stdout.write('\r' + ' ' * 75 + '\r')

    def start(self): self.thread.start()
    def stop(self):  self.stop_event.set(); time.sleep(0.2)


# ==========================================
# 🕷️ 591 單筆物件爬取
# ==========================================
def fetch_591_detail(url: str) -> dict | None:
    house_id = None
    new_house_id = None

    m = re.search(r'/detail/2/(\d+)', url)
    if m:
        house_id = m.group(1)

    m2 = re.search(r'newhouse\.591\.com\.tw/(\d+)', url)
    if m2:
        new_house_id = m2.group(1)

    if not house_id and not new_house_id:
        print(f"{C_RED}❌ 無法識別網址格式，請貼上 591 房屋詳細頁網址。{C_END}")
        print(f"   範例：https://sale.591.com.tw/home/house/detail/2/19780465.html")
        return None

    print(f"{C_CYAN}🔍 正在抓取物件資料...{C_END}")

    session = requests.Session()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://sale.591.com.tw/",
        "device": "pc",
    }

    try:
        r = session.get("https://sale.591.com.tw/", headers=headers, timeout=15)
        soup_meta = __import__('bs4').BeautifulSoup(r.text, "html.parser")
        meta = soup_meta.find("meta", {"name": "csrf-token"})
        if meta:
            headers["X-CSRF-TOKEN"] = meta["content"]
    except Exception:
        pass

    try:
        if house_id:
            api_url = f"https://bff-house.591.com.tw/v1/web/sale/detail?id={house_id}"
        else:
            api_url = f"https://newhouse.591.com.tw/api/v1/detail/{new_house_id}"

        res = session.get(api_url, headers=headers, timeout=15)
        if res.status_code != 200:
            print(f"{C_RED}❌ API 回應錯誤 {res.status_code}，嘗試直接解析網頁...{C_END}")
            return _parse_591_page(url, session, headers)

        raw_json = res.json()
        data = raw_json.get("ware") or raw_json.get("data", {})
        gtm = raw_json.get("gtm_detail_data") or {}

    except Exception as e:
        print(f"{C_RED}❌ API 請求失敗：{e}，嘗試直接解析網頁...{C_END}")
        return _parse_591_page(url, session, headers)

    def safe_float(val):
        try: return float(re.findall(r'[\d.]+', str(val))[0])
        except: return None

    unit_price = safe_float(gtm.get('unit_price_name'))
    if unit_price is None:
        for key in ['perprice', 'unitprice', 'unit_price', 'show_unitprice']:
            raw = data.get(key)
            if raw:
                unit_price = safe_float(raw)
                break

    total_price = safe_float(data.get('price') or data.get('show_price'))
    area = safe_float(gtm.get('area_name') or data.get('area') or data.get('showarea'))

    if unit_price is None and total_price and area and area > 0:
        unit_price = round(total_price / area, 1)

    age_raw = gtm.get('house_age_name') if gtm.get('house_age_name') is not None else data.get('houseage')
    age = float(age_raw) if age_raw is not None else 0

    shape_raw = str(gtm.get('shape_name') or data.get('shape_name') or '')
    if not shape_raw:
        try: shape_raw = raw_json.get('info', {}).get('3', {}).get('Shape', {}).get('value', '')
        except: shape_raw = ''
    if '大樓' in shape_raw or '電梯' in shape_raw or '華廈' in shape_raw:
        btype = '大樓'
    elif '公寓' in shape_raw:
        btype = '公寓'
    elif '透天' in shape_raw or '別墅' in shape_raw:
        btype = '透天厝'
    elif '套房' in shape_raw:
        btype = '套房'
    else:
        btype = shape_raw or '大樓'

    floor_raw = gtm.get('floor_name') or data.get('floor') or ''
    floor = str(floor_raw)

    district = str(gtm.get('section_name') or data.get('section_name') or '').replace('新北市', '').strip()
    region   = str(gtm.get('region_name')  or data.get('region_name')  or '新北市')

    try:
        addr_raw = raw_json.get('info', {}).get('2', {}).get('zAddress', {}).get('value', '')
    except:
        addr_raw = ''
    if not addr_raw:
        addr_raw = str(data.get('street_name') or data.get('address') or '')

    street_match = re.search(
        r'([^\s,，、／/（(【\[市縣區鎮鄉]+?[路街巷弄](?:[一二三四五六七八九十\d]+段)?)',
        addr_raw
    )
    street = street_match.group(1) if street_match else addr_raw

    title = str(gtm.get('item_name') or data.get('title') or data.get('address') or '')

    if unit_price is None:
        print(f"{C_RED}❌ 無法取得單價資訊，可能需要登入或物件已下架。{C_END}")
        return None

    result = {
        'title':      title,
        'region':     region,
        'district':   district,
        'street':     street,
        'full_addr':  addr_raw,
        'type':       btype,
        'floor':      floor,
        'age':        age if age is not None else 0,
        'total':      total_price,
        'area':       area,
        'unit_price': unit_price,
        'url':        url,
    }

    print(f"{C_GREEN}✅ 物件資料取得成功！{C_END}")
    return result


def _parse_591_page(url: str, session, headers) -> dict | None:
    try:
        res = session.get(url, headers=headers, timeout=15)
        text = res.text

        m = re.search(r'window\.__NUXT__\s*=\s*(\{.+?\});\s*</script>', text, re.DOTALL)
        if not m:
            m = re.search(r'window\.detailData\s*=\s*(\{.+?\});', text, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(1))
                def find_key(d, key):
                    if isinstance(d, dict):
                        if key in d: return d[key]
                        for v in d.values():
                            r = find_key(v, key)
                            if r is not None: return r
                    elif isinstance(d, list):
                        for i in d:
                            r = find_key(i, key)
                            if r is not None: return r
                    return None

                unit_price_raw = find_key(data, 'unitprice') or find_key(data, 'unit_price')
                price_raw      = find_key(data, 'price')
                area_raw       = find_key(data, 'area')

                def safe_float(val):
                    try: return float(re.findall(r'[\d.]+', str(val))[0])
                    except: return None

                unit_p = safe_float(unit_price_raw)
                total  = safe_float(price_raw)
                area   = safe_float(area_raw)
                if unit_p is None and total and area:
                    unit_p = round(total / area, 1)
                if unit_p:
                    return {'unit_price': unit_p, 'total': total, 'area': area,
                            'district': '', 'street': '', 'type': '大樓',
                            'floor': '', 'age': 0, 'title': '', 'url': url,
                            'region': '新北市', 'full_addr': ''}
            except Exception:
                pass

        print(f"{C_RED}❌ 無法從網頁解析物件資料，可能需要登入。{C_END}")
        return None
    except Exception as e:
        print(f"{C_RED}❌ 網頁請求失敗：{e}{C_END}")
        return None


# ==========================================
# 💬 AI 議價 & 本地引擎
# ==========================================
def get_backup_advice(diff_percent, final_p, house_age, listing_avg=None):
    tag = "[新成屋策略]" if house_age <= 5 else "[中古屋策略]"
    point = f"此物件屋齡 {house_age} 年。" if house_age <= 5 else f"此物件屋齡 {house_age} 年，應注意後續修繕成本。"
    listing_note = f"\n3. 目前 591 掛牌均價：{round(listing_avg, 1)} 萬/坪（可作為議價參考上限）。" if listing_avg else ""
    return (f"【⚠️ 專家診斷】價差達 {diff_percent}%。 🎯 策略 {tag}：\n"
            f"1. 屋齡分析：{point}\n"
            f"2. 銀行鑑價：市場行情平均約為 {round(final_p, 1)} 萬/坪，報價明顯高於行情。"
            f"{listing_note}")


def get_ai_negotiation_master(diff_percent, addr, age, floor, target_type,
                               my_unit_price, final_price, sample_count,
                               listing_avg=None):
    global MY_API_KEY
    model_name = "gemini-flash-latest"
    listing_context = f"目前 591 掛牌均價：{round(listing_avg, 1)} 萬/坪。" if listing_avg else ""
    prompt_text = (
        f"你是台灣房產專家。"
        f"物件：{addr}，樓層：{floor}樓，型態：{target_type}，屋齡：{age}年。"
        f"目前報價：{my_unit_price}萬/坪，"
        f"實價登錄相似均價：{round(final_price, 1)}萬/坪（樣本{sample_count}筆），"
        f"價差：{diff_percent}%。{listing_context}"
        f"請提供犀利的議價策略，包含：①開價切入點 ②心理戰術 ③停損建議。"
    )
    data = {"contents": [{"parts": [{"text": prompt_text}]}]}
    loader = LoadingAnimation(message="正在串接雲端 AI 生成建議", seconds=60)
    loader.start()
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={MY_API_KEY}"
        response = requests.post(url, json=data, timeout=60)
        loader.stop()
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        elif response.status_code == 429:
            print(f"\n{C_RED}⚠️ API 額度已用完（錯誤 429）{C_END}")
            print(f"{C_YELLOW}   → 請更換 API Key 或至 https://aistudio.google.com 設定帳單{C_END}")
            return "FORCE_LOCAL_BACKUP"
        elif response.status_code in (400, 403):
            print(f"\n{C_RED}⚠️ API Key 無效（錯誤 {response.status_code}）{C_END}")
            return "FORCE_LOCAL_BACKUP"
        else:
            print(f"\n{C_RED}⚠️ AI API 錯誤 {response.status_code}{C_END}")
            return "FORCE_LOCAL_BACKUP"
    except requests.exceptions.Timeout:
        loader.stop()
        print(f"\n{C_RED}⚠️ 已達 60 秒回應上限，切換至本地引擎。{C_END}")
        return "FORCE_LOCAL_BACKUP"
    except Exception as e:
        loader.stop()
        print(f"\n{C_RED}⚠️ AI 連線例外：{e}{C_END}")
        return "FORCE_LOCAL_BACKUP"


# ==========================================
# 📊 診斷核心（共用）
# ==========================================
def run_diagnosis(df, district, street, age, floor, target_type, my_unit, door=""):
    mask    = (df['行政區'] == district) & (df['街道'] == street) & (df['型態'].str.contains(target_type, na=False))
    matches = df[mask].copy()

    if matches.empty and len(street) >= 2:
        short = street[:3]
        mask2 = (df['行政區'] == district) & (df['街道'].str.startswith(short)) & (df['型態'].str.contains(target_type, na=False))
        matches = df[mask2].copy()
        if not matches.empty:
            print(f"{C_YELLOW}⚠️ 找不到「{street}」完整路段，以「{short}」開頭路段替代比對。{C_END}")

    if matches.empty:
        print(f"{C_RED}❌ 查無「{district}{street}」的成交或掛牌紀錄。{C_END}")
        return False

    if '來源' in matches.columns:
        actual_data  = matches[matches['來源'] == '實價登錄']
        listing_data = matches[matches['來源'] == '591']
    else:
        actual_data  = matches
        listing_data = pd.DataFrame()

    ref_data = actual_data if not actual_data.empty else matches
    sim = ref_data[(ref_data['屋齡'] >= age - 5) & (ref_data['屋齡'] <= age + 5)]
    ref = sim if not sim.empty else ref_data

    final_p = ref['單價'].mean()
    count   = len(ref)
    diff    = round(((my_unit - final_p) / final_p) * 100, 1)

    listing_avg = round(listing_data['單價'].mean(), 1) if not listing_data.empty else None

    print(f"\n{C_CYAN}🔍 [ 診斷報告 ]{C_END}")
    print(f"{C_BLUE}{'─' * 64}{C_END}")
    print(f"🏠 地址：{district}{street}{door} ({target_type}/{floor}樓)")
    print(f"📈 實價行情：{C_GREEN}{round(final_p, 1)} 萬/坪{C_END} (樣本: {count} 筆)")
    if listing_avg:
        print(f"🏷️  591掛牌均價：{C_YELLOW}{listing_avg} 萬/坪{C_END} (掛牌參考，非成交價)")

    # ── AI 模型估價（優先用 v2 分區模型）──────────────
    try:
        import pickle, os as _os
        v2_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'price_model_v2.pkl')
        v1_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'price_model.pkl')

        if _os.path.exists(v2_path):
            import price_model_v2 as _pm2_module
            import sys as _sys
            _sys.modules['__main__'].DistrictPriceModel = _pm2_module.DistrictPriceModel
            with open(v2_path, 'rb') as _f:
                _pm = pickle.load(_f)
            model_ver = 'v2分區'
        elif _os.path.exists(v1_path):
            import price_model as _pm_module
            import sys as _sys
            _sys.modules['__main__'].PriceModel = _pm_module.PriceModel
            with open(v1_path, 'rb') as _f:
                _pm = pickle.load(_f)
            model_ver = 'v1'
        else:
            _pm = None

        if _pm:
            _r  = _pm.predict(district=district, street=street,
                              house_type=target_type, age=float(age) if age else 10,
                              floor=floor)
            ai_price = _r['estimated_price']
            ai_low   = _r['price_range_low']
            ai_high  = _r['price_range_high']
            ai_conf  = _r['confidence']
            used     = _r.get('model_used', model_ver)
            conf_c   = C_GREEN if ai_conf == '高' else (C_YELLOW if ai_conf == '中' else C_RED)
            print(f"🤖 AI模型估價：{C_CYAN}{ai_price} 萬/坪{C_END} "
                  f"(區間 {ai_low}～{ai_high}，{used}，信心:{conf_c}{ai_conf}{C_END})")
    except Exception:
        pass

    print(f"💰 該物件單價：{my_unit} 萬/坪")
    is_high = diff > 10
    color = BG_RED if is_high else C_GREEN
    label = '🚨 價格明顯偏高' if is_high else ('⚠️ 略高於行情' if diff > 0 else '✅ 價格合理或低於行情')
    print(f"📢 判定：{color}{label}{C_END} ({diff:+.1f}%)")
    print(f"{C_BLUE}{'─' * 64}{C_END}")

    print(f"\n選擇議價建議來源: [1] 🚀 雲端 AI  [2] 🤖 本地引擎")
    choice = input("👉 選項: ").strip()
    print(f"\n{C_YELLOW}💡 [ 顧問建議 ]{C_END}")
    print(f"{C_YELLOW}{'=' * 64}{C_END}")

    if choice == "1":
        # ── 每次重新輸入 API Key ───────────────────────
        global MY_API_KEY
        print(f"\n{C_YELLOW}┌──────────────────────────────────────────────────┐{C_END}")
        print(f"{C_YELLOW}│  🔑 請輸入 Gemini API Key                         │{C_END}")
        print(f"{C_YELLOW}│  取得免費 Key：https://aistudio.google.com/apikey  │{C_END}")
        print(f"{C_YELLOW}└──────────────────────────────────────────────────┘{C_END}")
        key = input(f"  {C_CYAN}請貼上 API Key（留空改用本地引擎）: {C_END}").strip()

        if not key:
            print(f"\n{C_YELLOW}⚠️ 未輸入 Key，改用本地引擎。{C_END}\n")
            typewriter_print(get_backup_advice(diff, final_p, age, listing_avg))
        else:
            MY_API_KEY = key
            ai_res = get_ai_negotiation_master(diff, f"{district}{street}", age, floor,
                                                target_type, my_unit, final_p, count, listing_avg)
            if ai_res == "FORCE_LOCAL_BACKUP":
                print(f"\n{C_YELLOW}🔄 自動切換至本地引擎：{C_END}\n")
                typewriter_print(get_backup_advice(diff, final_p, age, listing_avg))
            else:
                print(f"{C_GREEN}🚀 [雲端 AI 顧問連線成功]{C_END}\n")
                typewriter_print(ai_res)
    else:
        typewriter_print(get_backup_advice(diff, final_p, age, listing_avg))

    print(f"{C_YELLOW}{'=' * 64}{C_END}")
    return True


def select_from_menu(options, title):
    print(f"\n{C_BOLD}{C_CYAN}➤ {title}{C_END}")
    for i, option in enumerate(options[:15], 1):
        print(f"  [{i:2d}] {option}")
    if len(options) > 15:
        print(f"  ... (還有 {len(options) - 15} 項)")
    while True:
        choice = input(f"\n{C_YELLOW}👉 請輸入編號或關鍵字: {C_END}").strip()
        if not choice: continue
        if choice.isdigit() and 0 < int(choice) <= len(options):
            return options[int(choice) - 1]
        matches = [o for o in options if choice in o]
        if matches: return matches[0]
        print(f"{C_RED}❌ 無效選擇。{C_END}")


# ==========================================
# 🚀 主程式入口
# ==========================================
def start_app():
    show_welcome_banner()
    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(current_dir, 'real_estate_market_pro.csv')

    try:
        df = pd.read_csv(db_path, encoding='utf-8-sig')
        df['單價'] = pd.to_numeric(df['單價'], errors='coerce')
        df = df.dropna(subset=['單價'])
    except FileNotFoundError:
        print(f"{C_RED}❌ 找不到資料庫：{db_path}\n   👉 請先執行 Spider.py 再執行 Data_Center.py。{C_END}")
        return
    except Exception as e:
        print(f"{C_RED}❌ 資料庫讀取失敗：{e}{C_END}")
        return

    if '來源' in df.columns:
        src_info = df['來源'].value_counts().to_dict()
        src_str = "、".join([f"{k}:{v}筆" for k, v in src_info.items()])
        print(f"\n{C_CYAN}📊 資料庫載入成功！共 {len(df)} 筆（{src_str}）{C_END}")

    print(f"\n{C_BOLD}{C_CYAN}➤ 請選擇輸入方式{C_END}")
    print(f"  [ 1] 🔗 貼上 591 網址（自動抓取物件資訊）")
    print(f"  [ 2] ✏️  手動輸入物件資訊")
    mode = input(f"\n{C_YELLOW}👉 選項: {C_END}").strip()

    if mode == "1":
        url = input(f"\n{C_YELLOW}🔗 請貼上 591 房屋網址: {C_END}").strip()
        if not url:
            print(f"{C_RED}❌ 未輸入網址。{C_END}")
            return

        info = fetch_591_detail(url)
        if not info:
            return

        print(f"\n{C_BLUE}{'─' * 64}{C_END}")
        print(f"{C_BOLD}📋 物件資訊確認{C_END}")
        print(f"  標題：{info['title']}")
        print(f"  地址：{info['region']}{info['district']}{info['street']}")
        print(f"  型態：{info['type']}  樓層：{info['floor']}  屋齡：{info['age']}年")
        print(f"  總價：{info['total']}萬  坪數：{info['area']}坪  單價：{info['unit_price']}萬/坪")
        print(f"{C_BLUE}{'─' * 64}{C_END}")

        print(f"\n{C_YELLOW}⚠️  請確認以下資訊是否正確（直接 Enter 保留自動值）{C_END}")
        dist_input = input(f"   行政區 [{info['district']}]: ").strip()
        road_input = input(f"   路段   [{info['street']}]: ").strip()

        district = dist_input or info['district']
        street   = road_input or info['street']

        if not district or not street:
            print(f"{C_RED}❌ 行政區或路段不能為空，請手動輸入。{C_END}")
            return

        run_diagnosis(df, district, street,
                      info['age'], info['floor'], info['type'],
                      info['unit_price'])

    else:
        dist = select_from_menu(
            sorted([str(x) for x in df['行政區'].unique() if str(x) not in ('nan', '')]),
            "第一階段：選擇行政區"
        )
        road = select_from_menu(
            sorted([str(x) for x in df[df['行政區'] == dist]['街道'].unique()]),
            f"第二階段：確認路段 ({dist})"
        )

        print(f"\n{C_BLUE}{'═' * 64}{C_END}")
        print(f"{C_BOLD}{C_CYAN} 第三階段：請輸入「新北市{dist}{road}」的詳細資訊{C_END}")
        print(f"{C_BLUE}{'═' * 64}{C_END}")

        door = input("📍 門牌資訊: ")
        try:
            total   = float(input("💰 總價(萬): "))
            size    = float(input("📏 坪數(坪): "))
            age     = float(input("📅 屋齡(年): "))
            floor   = input("🏢 樓層: ")
            type_in = input("🏠 型態 (1.大樓 2.公寓): ")
            target_type = "大樓" if type_in == "1" else "公寓"
        except ValueError:
            print(f"{C_RED}⚠️ 輸入錯誤，請輸入數字。{C_END}")
            return

        my_unit = round(total / size, 1)
        run_diagnosis(df, dist, road, age, floor, target_type, my_unit, door)


if __name__ == "__main__":
    try:
        while True:
            start_app()
            if input(f"\n按 (Enter) 繼續 / (q) 退出: ").lower().strip() == 'q':
                break
    except KeyboardInterrupt:
        pass