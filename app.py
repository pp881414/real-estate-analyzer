"""
app.py — 智慧房價診斷與議價輔助系統 Streamlit 介面
執行方式：streamlit run app.py
"""

import streamlit as st
import pandas as pd
import re
import requests
import os
import sys
import pickle
import json
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
st.set_page_config(page_title="智慧房價診斷系統", page_icon="🏠", layout="wide", initial_sidebar_state="collapsed")

# ==========================================
# 🎨 全域樣式
# ==========================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;600;700;800;900&display=swap');
:root {
    --orange:#f07c3e; --orange-light:#f9a06a; --orange-pale:#fef3ea;
    --orange-deep:#e8623a; --warm-bg:#faf8f5; --card-bg:#ffffff;
    --text-dark:#2d2016; --text-mid:#7a6555; --text-light:#b8a898; --border:#ede8e2;
}
html,body,[data-testid="stAppViewContainer"]{background-color:var(--warm-bg)!important;color:var(--text-dark);font-family:'Noto Sans TC','Segoe UI',sans-serif;}
[data-testid="stHeader"]{background:transparent;}
#MainMenu,footer,header{visibility:hidden;}
[data-testid="stToolbar"],[data-testid="stDecoration"],[data-testid="stStatusWidget"]{display:none!important;}
[data-testid="stMainBlockContainer"]{max-width:1100px;padding:0 2rem 2rem;}

.hero-wrap{position:relative;border-radius:20px;overflow:hidden;margin-bottom:28px;height:400px;background:linear-gradient(180deg,#fdf5e6 0%,#fde8c0 55%,#f0e8d8 100%);box-shadow:0 4px 24px rgba(200,140,60,0.10);}
.hero-wrap::before{content:'';position:absolute;top:-80px;left:50%;transform:translateX(-50%);width:560px;height:400px;background:radial-gradient(ellipse at 50% 30%,rgba(255,220,100,0.38) 0%,rgba(255,190,80,0.18) 40%,transparent 68%);pointer-events:none;}
.hero-ground{position:absolute;bottom:0;left:0;right:0;height:56px;background:linear-gradient(180deg,#e8e0d4 0%,#ddd5c8 100%);}
.hero-ground::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,rgba(180,155,120,0.5),transparent);}
.hero-content{position:absolute;top:28px;left:0;right:0;z-index:20;display:flex;flex-direction:column;align-items:center;}
.hero-badge-warm{display:inline-flex;align-items:center;gap:6px;background:rgba(240,124,62,0.12);border:1px solid rgba(240,124,62,0.35);color:var(--orange-deep);font-size:0.68rem;font-weight:700;padding:4px 13px;border-radius:20px;margin-bottom:10px;letter-spacing:2px;text-transform:uppercase;}
.hero-badge-warm::before{content:'●';font-size:0.45rem;animation:pulse-warm 2s ease-in-out infinite;}
@keyframes pulse-warm{0%,100%{opacity:1;}50%{opacity:0.25;}}
.hero-title-warm{font-size:2rem;font-weight:900;color:var(--text-dark);margin:0 0 4px;text-align:center;letter-spacing:-0.5px;}
.hero-title-warm span{color:var(--orange);}
.hero-subtitle-warm{font-size:0.9rem;color:var(--text-mid);margin:0 0 20px;text-align:center;}
.hero-main-building{position:absolute;bottom:56px;left:50%;transform:translateX(-50%);z-index:6;animation:float-building 4.5s ease-in-out infinite;}
@keyframes float-building{0%,100%{transform:translateX(-50%) translateY(0);}50%{transform:translateX(-50%) translateY(-10px);}}
.price-bubble{position:absolute;top:-10px;left:50%;transform:translateX(-38%);background:white;border-radius:14px;padding:10px 20px;box-shadow:0 6px 28px rgba(0,0,0,0.13);font-size:1.4rem;font-weight:900;color:var(--text-dark);white-space:nowrap;animation:bubble-in 0.7s 0.4s cubic-bezier(0.34,1.56,0.64,1) both;}
.price-bubble::after{content:'';position:absolute;bottom:-12px;left:50%;transform:translateX(-50%);border:7px solid transparent;border-top-color:white;}
@keyframes bubble-in{from{opacity:0;transform:translateX(-38%) scale(0.4);}to{opacity:1;transform:translateX(-38%) scale(1);}}
.hero-walker{position:absolute;bottom:56px;right:12%;z-index:7;animation:walker-in 0.9s 0.2s ease-out both;}
@keyframes walker-in{from{opacity:0;transform:translateX(50px);}to{opacity:1;transform:translateX(0);}}

[data-testid="stMetric"]{background:var(--card-bg);border:1px solid var(--border);border-radius:14px;padding:18px 22px!important;position:relative;overflow:hidden;transition:box-shadow 0.2s,transform 0.2s;}
[data-testid="stMetric"]:hover{box-shadow:0 6px 20px rgba(240,124,62,0.10);transform:translateY(-2px);}
[data-testid="stMetric"]::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,var(--orange),var(--orange-light));border-radius:14px 14px 0 0;}
[data-testid="stMetricLabel"]{color:var(--text-mid)!important;font-size:0.76rem!important;font-weight:600!important;}
[data-testid="stMetricValue"]{color:var(--text-dark)!important;font-weight:800!important;font-size:1.55rem!important;}
[data-testid="stDataFrame"]{border-radius:10px;overflow:hidden;}

.stButton>button{background:#f0ede8!important;color:var(--text-mid)!important;font-weight:600!important;border:none!important;border-radius:8px!important;padding:9px 20px!important;font-size:0.9rem!important;width:100%;transition:all 0.18s ease!important;}
.stButton>button:hover{background:#e8e0d8!important;color:var(--text-dark)!important;transform:translateY(-1px);}
button[kind="primary"]{background:linear-gradient(135deg,var(--orange) 0%,var(--orange-deep) 100%)!important;color:#ffffff!important;box-shadow:0 3px 12px rgba(240,124,62,0.30)!important;}
button[kind="primary"]:hover{filter:brightness(1.07)!important;transform:translateY(-1px)!important;box-shadow:0 5px 18px rgba(240,124,62,0.38)!important;}

.card{background:var(--card-bg);border:1px solid var(--border);border-radius:14px;padding:22px 26px;margin-bottom:18px;transition:box-shadow 0.2s,transform 0.2s;}
.card:hover{box-shadow:0 6px 20px rgba(240,124,62,0.08);transform:translateY(-1px);}
.card-title{font-size:0.72rem;font-weight:700;color:var(--text-light);letter-spacing:1.4px;text-transform:uppercase;margin-bottom:8px;}
.card-value{font-size:1.9rem;font-weight:800;color:var(--text-dark);line-height:1.2;}
.card-unit{font-size:0.9rem;color:var(--text-light);font-weight:400;}
.card-sub{font-size:0.78rem;color:var(--text-light);margin-top:6px;}
.card-blue{border-left:4px solid #5b9cf7;} .card-gold{border-left:4px solid var(--orange);}
.card-judge{border-left:4px solid #a78bfa;} .card-ai{border-left:4px solid #34d399;}

.tag-high{display:inline-flex;align-items:center;gap:6px;background:linear-gradient(135deg,#fff1f1,#ffe4e4);border:1.5px solid #fca5a5;color:#dc2626;font-size:0.9rem;font-weight:700;padding:8px 16px;border-radius:10px;box-shadow:0 2px 8px rgba(220,38,38,0.12);}
.tag-mid{display:inline-flex;align-items:center;gap:6px;background:linear-gradient(135deg,#fffbeb,#fef3c7);border:1.5px solid #fcd34d;color:#d97706;font-size:0.9rem;font-weight:700;padding:8px 16px;border-radius:10px;box-shadow:0 2px 8px rgba(217,119,6,0.12);}
.tag-ok{display:inline-flex;align-items:center;gap:6px;background:linear-gradient(135deg,#f0fdf4,#dcfce7);border:1.5px solid #86efac;color:#16a34a;font-size:0.9rem;font-weight:700;padding:8px 16px;border-radius:10px;box-shadow:0 2px 8px rgba(22,163,74,0.12);}

.ai-box{background:linear-gradient(135deg,#f8f9ff,#f3f4ff);border:1px solid #c7d2fe;border-left:4px solid #4f46e5;border-radius:12px;padding:22px 26px;font-size:0.91rem;line-height:1.9;color:#2d3250;white-space:pre-wrap;box-shadow:0 2px 12px rgba(79,70,229,0.06);}
.local-box{background:linear-gradient(135deg,#f0fdf4,#ecfdf5);border:1px solid #bbf7d0;border-left:4px solid #16a34a;border-radius:12px;padding:22px 26px;font-size:0.91rem;line-height:1.9;color:#14532d;white-space:pre-wrap;box-shadow:0 2px 12px rgba(22,163,74,0.06);}

.info-row{display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid #f0ede8;font-size:0.88rem;}
.info-row:last-child{border-bottom:none;}
.info-label{color:var(--text-light);} .info-value{color:var(--text-dark);font-weight:600;}
.divider{border:none;border-top:1px solid var(--border);margin:28px 0;}

[data-testid="stTextInput"] input,[data-testid="stNumberInput"] input{background-color:#fdfaf7!important;border:1.5px solid #ddd5c8!important;border-radius:8px!important;color:var(--text-dark)!important;transition:border-color 0.15s,box-shadow 0.15s!important;}
[data-testid="stTextInput"] input:focus,[data-testid="stNumberInput"] input:focus{border-color:var(--orange)!important;box-shadow:0 0 0 3px rgba(240,124,62,0.14)!important;}
[data-testid="stSelectbox"]>div>div{background-color:#fdfaf7!important;border:1.5px solid #ddd5c8!important;border-radius:8px!important;color:var(--text-dark)!important;}

.detect-ok{background:linear-gradient(135deg,#f0fdf4,#ecfdf5);border:1px solid #86efac;border-left:4px solid #22c55e;border-radius:8px;padding:12px 16px;font-size:0.84rem;color:#15803d;margin:8px 0 14px;}
.detect-err{background:linear-gradient(135deg,#fff1f1,#fef2f2);border:1px solid #fca5a5;border-left:4px solid #ef4444;border-radius:8px;padding:12px 16px;font-size:0.84rem;color:#dc2626;margin:8px 0 14px;}

.stMarkdown p:empty{display:none!important;margin:0!important;padding:0!important;}
div:empty{min-height:0!important;}
[data-testid="stVerticalBlockBorderWrapper"]{padding:0!important;}
.block-container{padding-top:0!important;}
[data-testid="stColumn"]{padding:0 4px!important;}
[data-testid="stMarkdown"]:has(>div:empty),[data-testid="stMarkdown"]:has(>p:empty){display:none!important;}

.footer-wrap{text-align:center;padding:36px 0 20px;border-top:1px solid var(--border);margin-top:40px;}
.footer-logo{font-size:1.05rem;font-weight:900;color:var(--text-dark);margin-bottom:8px;}
.footer-logo span{color:var(--orange);}
.footer-meta{font-size:0.78rem;color:var(--text-light);line-height:1.9;}
.footer-tag{display:inline-block;background:var(--orange-pale);border:1px solid rgba(240,124,62,0.2);color:var(--orange-deep);font-size:0.7rem;padding:2px 10px;border-radius:6px;margin:3px 2px;}
</style>
""", unsafe_allow_html=True)


# ==========================================
# 🔧 工具函式
# ==========================================
current_dir = os.path.dirname(os.path.abspath(__file__))

@st.cache_data(show_spinner=False)
def load_database():
    df = pd.read_csv(os.path.join(current_dir, 'real_estate_market_pro.csv'), encoding='utf-8-sig')
    df['單價'] = pd.to_numeric(df['單價'], errors='coerce')
    return df.dropna(subset=['單價'])

@st.cache_resource(show_spinner=False)
def load_model():
    for path, mod_name, cls_name, ver in [
        ('price_model_v2.pkl', 'price_model_v2', 'DistrictPriceModel', 'v2'),
        ('price_model.pkl',    'price_model',    'PriceModel',          'v1'),
    ]:
        full = os.path.join(current_dir, path)
        if os.path.exists(full):
            try:
                mod = __import__(mod_name)
                sys.modules['__main__'].__dict__[cls_name] = getattr(mod, cls_name)
                with open(full, 'rb') as f:
                    return pickle.load(f), ver
            except Exception:
                pass
    return None, None


def parse_address(addr_raw: str):
    """從完整地址解析 (行政區, 路段)"""
    dist_m = re.search(
        r'(?:新北市|台北市|臺北市|桃園市|台中市|臺中市|高雄市|台南市|臺南市|'
        r'基隆市|新竹市|嘉義市|新竹縣|苗栗縣|彰化縣|南投縣|雲林縣|嘉義縣|'
        r'屏東縣|宜蘭縣|花蓮縣|台東縣|臺東縣|澎湖縣|金門縣|連江縣)?'
        r'([^\s市縣]{2,4}[區鎮鄉市])', addr_raw)
    road_m = re.search(
        r'([^\s,，、／/（(【\[市縣區鎮鄉0-9０-９]+?(?:路|街|大道|巷|弄)(?:[一二三四五六七八九十百\d]+段)?)',
        addr_raw)
    return (dist_m.group(1) if dist_m else ''), (road_m.group(1) if road_m else '')


def is_valid_591_url(url: str) -> bool:
    return bool(re.search(r'sale\.591\.com\.tw.*?/detail/2/\d+', url))


def fetch_591_detail(url: str):
    m = re.search(r'/detail/2/(\d+)', url)
    if not m:
        return None, "無法識別網址格式"
    house_id = m.group(1)

    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://sale.591.com.tw/",
        "device": "pc",
    }
    try:
        r = session.get("https://sale.591.com.tw/", headers=headers, timeout=10, verify=False)
        try:
            from bs4 import BeautifulSoup
            meta = BeautifulSoup(r.text, "html.parser").find("meta", {"name": "csrf-token"})
            if meta:
                headers["X-CSRF-TOKEN"] = meta["content"]
        except Exception:
            pass
    except Exception:
        pass

    try:
        res = session.get(f"https://bff-house.591.com.tw/v1/web/sale/detail?id={house_id}", headers=headers, timeout=12, verify=False)
        if res.status_code != 200:
            return None, f"API 錯誤 {res.status_code}"
        raw = res.json()
        data = raw.get("ware") or raw.get("data", {})
        gtm  = raw.get("gtm_detail_data") or {}
    except Exception as e:
        return None, str(e)

    def sf(val):
        try: return float(re.findall(r'[\d.]+', str(val))[0])
        except: return None

    unit_price = sf(gtm.get('unit_price_name'))
    if unit_price is None:
        for k in ['perprice', 'unitprice', 'unit_price', 'show_unitprice']:
            if data.get(k):
                unit_price = sf(data[k]); break

    total_price = sf(data.get('price') or data.get('show_price'))
    area = sf(gtm.get('area_name') or data.get('area') or data.get('showarea'))
    if unit_price is None and total_price and area:
        unit_price = round(total_price / area, 1)
    if unit_price is None:
        return None, "無法取得單價，物件可能已下架"

    age_raw = gtm.get('house_age_name') if gtm.get('house_age_name') is not None else data.get('houseage')
    age = float(age_raw) if age_raw is not None else 0

    shape = str(gtm.get('shape_name') or data.get('shape_name') or '')
    btype = ('大樓' if any(k in shape for k in ['大樓', '電梯', '華廈']) else
             '公寓' if '公寓' in shape else
             '透天厝' if any(k in shape for k in ['透天', '別墅']) else shape or '大樓')

    floor_raw = gtm.get('floor_name') or data.get('floor') or ''
    region    = str(gtm.get('region_name') or data.get('region_name') or '新北市')
    try:
        addr_raw = raw.get('info', {}).get('2', {}).get('zAddress', {}).get('value', '')
    except Exception:
        addr_raw = ''
    if not addr_raw:
        addr_raw = str(data.get('street_name') or data.get('address') or '')

    district, street = parse_address(addr_raw)
    if not district:
        district = str(gtm.get('section_name') or data.get('section_name') or '').replace(region, '').strip()
    if not street:
        street = addr_raw

    return {
        'title': str(gtm.get('item_name') or data.get('title') or data.get('address') or ''),
        'region': region, 'district': district, 'street': street, 'full_addr': addr_raw,
        'type': btype, 'floor': str(floor_raw), 'age': age,
        'total': total_price, 'area': area, 'unit_price': unit_price, 'url': url,
    }, None


def run_diagnosis(df, district, street, age, floor, target_type, my_unit):
    def filter_df(d, s):
        return df[(df['行政區'] == d) & (df['街道'] == s) & (df['型態'].str.contains(target_type, na=False))].copy()

    matches = filter_df(district, street)
    fallback_street = None
    if matches.empty and len(street) >= 2:
        short = street[:3]
        matches = df[(df['行政區'] == district) & (df['街道'].str.startswith(short)) & (df['型態'].str.contains(target_type, na=False))].copy()
        if not matches.empty:
            fallback_street = short

    if matches.empty:
        return None, f"查無「{district}{street}」的成交紀錄"

    actual_data  = matches[matches['來源'] == '實價登錄'] if '來源' in matches.columns else matches
    listing_data = matches[matches['來源'] == '591']     if '來源' in matches.columns else pd.DataFrame()

    ref_data = actual_data if not actual_data.empty else matches
    sim = ref_data[(ref_data['屋齡'] >= age - 5) & (ref_data['屋齡'] <= age + 5)]
    ref = sim if not sim.empty else ref_data

    final_p = ref['單價'].mean()
    return {
        'final_p': final_p, 'count': len(ref),
        'diff': round(((my_unit - final_p) / final_p) * 100, 1),
        'listing_avg': round(listing_data['單價'].mean(), 1) if not listing_data.empty else None,
        'fallback_street': fallback_street, 'ref': ref,
    }, None


def get_ai_advice(diff, addr, age, floor, target_type, my_unit, final_p, count, listing_avg, api_key):
    listing_ctx = f"591掛牌均價：{listing_avg}萬/坪。" if listing_avg else ""
    prompt = (
        f"你是台灣房產專家。物件：{addr}，樓層：{floor}樓，型態：{target_type}，屋齡：{age}年。"
        f"目前報價：{my_unit}萬/坪，實價登錄相似均價：{round(final_p,1)}萬/坪（樣本{count}筆），"
        f"價差：{diff}%。{listing_ctx}"
        f"請提供犀利的議價策略，包含：①開價切入點 ②心理戰術 ③停損建議。"
    )
    try:
        res = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={api_key}",
            json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=60
        )
        if res.status_code == 200:
            return res.json()['candidates'][0]['content']['parts'][0]['text'], None
        err_map = {429: "API 額度已用完（429）\n請至 https://aistudio.google.com 設定帳單或更換 Key"}
        return None, err_map.get(res.status_code, f"API 錯誤 {res.status_code}" if res.status_code not in (400, 403) else f"API Key 無效（{res.status_code}）")
    except requests.exceptions.Timeout:
        return None, "逾時（60秒），請重試"
    except Exception as e:
        return None, str(e)


def get_local_advice(diff, final_p, age, listing_avg=None):
    tag   = "新成屋" if age <= 5 else "中古屋"
    point = f"屋齡 {age} 年" + ("，建議請建商說明建材規格。" if age <= 5 else "，請注意後續修繕成本。")
    ln    = f"\n3. 591 掛牌均價：{listing_avg} 萬/坪，可作為議價參考上限。" if listing_avg else ""
    return (
        f"【{tag}議價策略】價差 {diff}%\n\n"
        f"1. {point}\n"
        f"2. 銀行鑑價：市場均價約 {round(final_p,1)} 萬/坪，報價高於行情，具議價空間。{ln}"
    )


# ==========================================
# 🏠 Hero Banner SVG
# ==========================================
_hero_city_svg = (
    '<svg viewBox="0 0 1100 290" preserveAspectRatio="xMidYMax meet"'
    ' style="position:absolute;bottom:56px;left:0;right:0;width:100%;height:290px;">'
    '<rect x="0" y="180" width="52" height="110" rx="4" fill="#f5c870" opacity="0.45"/>'
    '<rect x="8" y="155" width="40" height="138" rx="3" fill="#f0b045" opacity="0.40"/>'
    '<rect x="60" y="145" width="38" height="148" rx="3" fill="#e8a840" opacity="0.38"/>'
    '<rect x="55" y="185" width="55" height="108" rx="3" fill="#f5c870" opacity="0.32"/>'
    '<rect x="115" y="165" width="33" height="128" rx="3" fill="#eda840" opacity="0.36"/>'
    '<rect x="155" y="95" width="62" height="198" rx="5" fill="#e89030" opacity="0.50"/>'
    '<rect x="163" y="75" width="46" height="220" rx="4" fill="#f0a035" opacity="0.46"/>'
    '<rect x="170" y="95" width="10" height="14" rx="2" fill="white" opacity="0.55"/>'
    '<rect x="186" y="95" width="10" height="14" rx="2" fill="white" opacity="0.55"/>'
    '<rect x="170" y="117" width="10" height="14" rx="2" fill="white" opacity="0.55"/>'
    '<rect x="186" y="117" width="10" height="14" rx="2" fill="white" opacity="0.55"/>'
    '<rect x="170" y="139" width="10" height="14" rx="2" fill="white" opacity="0.55"/>'
    '<rect x="186" y="139" width="10" height="14" rx="2" fill="white" opacity="0.55"/>'
    '<rect x="170" y="161" width="10" height="14" rx="2" fill="white" opacity="0.55"/>'
    '<rect x="186" y="161" width="10" height="14" rx="2" fill="white" opacity="0.55"/>'
    '<rect x="222" y="125" width="50" height="168" rx="4" fill="#f5b040" opacity="0.46"/>'
    '<rect x="278" y="155" width="46" height="138" rx="4" fill="#f0a0a0" opacity="0.52"/>'
    '<rect x="286" y="170" width="10" height="14" rx="2" fill="white" opacity="0.65"/>'
    '<rect x="302" y="170" width="10" height="14" rx="2" fill="white" opacity="0.65"/>'
    '<rect x="286" y="192" width="10" height="14" rx="2" fill="white" opacity="0.65"/>'
    '<rect x="302" y="192" width="10" height="14" rx="2" fill="white" opacity="0.65"/>'
    '<rect x="335" y="248" width="7" height="45" rx="3" fill="#8B6A40"/>'
    '<circle cx="339" cy="228" r="26" fill="#5a9e5a" opacity="0.85"/>'
    '<circle cx="324" cy="238" r="20" fill="#6ab46a" opacity="0.75"/>'
    '<circle cx="354" cy="238" r="20" fill="#4a8e4a" opacity="0.80"/>'
    '<rect x="398" y="255" width="6" height="38" rx="3" fill="#8B6A40"/>'
    '<circle cx="401" cy="237" r="22" fill="#5a9e5a" opacity="0.80"/>'
    '<circle cx="388" cy="246" r="16" fill="#6ab46a" opacity="0.70"/>'
    '<circle cx="414" cy="246" r="16" fill="#4a8e4a" opacity="0.75"/>'
    '<rect x="660" y="250" width="7" height="43" rx="3" fill="#8B6A40"/>'
    '<circle cx="664" cy="230" r="26" fill="#5a9e5a" opacity="0.85"/>'
    '<circle cx="649" cy="240" r="20" fill="#6ab46a" opacity="0.75"/>'
    '<circle cx="679" cy="240" r="20" fill="#4a8e4a" opacity="0.80"/>'
    '<rect x="720" y="255" width="6" height="38" rx="3" fill="#8B6A40"/>'
    '<circle cx="723" cy="237" r="22" fill="#5a9e5a" opacity="0.80"/>'
    '<circle cx="710" cy="246" r="16" fill="#6ab46a" opacity="0.70"/>'
    '<circle cx="736" cy="246" r="16" fill="#4a8e4a" opacity="0.75"/>'
    '<rect x="770" y="165" width="52" height="128" rx="4" fill="#f5c870" opacity="0.45"/>'
    '<rect x="826" y="135" width="42" height="158" rx="3" fill="#e8a845" opacity="0.42"/>'
    '<rect x="872" y="148" width="55" height="145" rx="4" fill="#f0b855" opacity="0.38"/>'
    '<rect x="930" y="100" width="48" height="193" rx="4" fill="#e8952a" opacity="0.48"/>'
    '<rect x="940" y="120" width="10" height="14" rx="2" fill="white" opacity="0.52"/>'
    '<rect x="956" y="120" width="10" height="14" rx="2" fill="white" opacity="0.52"/>'
    '<rect x="940" y="142" width="10" height="14" rx="2" fill="white" opacity="0.52"/>'
    '<rect x="956" y="142" width="10" height="14" rx="2" fill="white" opacity="0.52"/>'
    '<rect x="982" y="155" width="50" height="138" rx="3" fill="#f5b040" opacity="0.40"/>'
    '<rect x="1036" y="185" width="64" height="108" rx="3" fill="#f7c855" opacity="0.36"/>'
    '<rect x="770" y="88" width="66" height="205" rx="5" fill="#e89030" opacity="0.50"/>'
    '<rect x="778" y="106" width="11" height="15" rx="2" fill="white" opacity="0.55"/>'
    '<rect x="795" y="106" width="11" height="15" rx="2" fill="white" opacity="0.55"/>'
    '<rect x="778" y="130" width="11" height="15" rx="2" fill="white" opacity="0.55"/>'
    '<rect x="795" y="130" width="11" height="15" rx="2" fill="white" opacity="0.55"/>'
    '<rect x="778" y="154" width="11" height="15" rx="2" fill="white" opacity="0.55"/>'
    '<rect x="795" y="154" width="11" height="15" rx="2" fill="white" opacity="0.55"/>'
    '<ellipse cx="450" cy="283" rx="6" ry="4" fill="#c0b0a0" opacity="0.35" transform="rotate(-18,450,283)"/>'
    '<ellipse cx="485" cy="279" rx="6" ry="4" fill="#c0b0a0" opacity="0.35" transform="rotate(18,485,279)"/>'
    '<ellipse cx="520" cy="283" rx="6" ry="4" fill="#c0b0a0" opacity="0.35" transform="rotate(-18,520,283)"/>'
    '<ellipse cx="555" cy="279" rx="6" ry="4" fill="#c0b0a0" opacity="0.35" transform="rotate(18,555,279)"/>'
    '<ellipse cx="590" cy="283" rx="6" ry="4" fill="#c0b0a0" opacity="0.35" transform="rotate(-18,590,283)"/>'
    '<ellipse cx="625" cy="279" rx="6" ry="4" fill="#c0b0a0" opacity="0.35" transform="rotate(18,625,279)"/>'
    '</svg>'
)

_hero_building_svg = (
    '<svg viewBox="0 0 200 255" width="168" style="display:block;">'
    '<rect x="28" y="28" width="144" height="227" rx="6" fill="#f2f0ee" stroke="#e0dcd6" stroke-width="1.5"/>'
    '<rect x="150" y="28" width="22" height="227" rx="0" fill="#e6e0d8" opacity="0.9"/>'
    '<rect x="28" y="28" width="144" height="20" fill="#eae6e0"/>'
    '<rect x="42" y="60" width="20" height="26" rx="3" fill="#b8d8f2" opacity="0.9"/>'
    '<rect x="68" y="60" width="20" height="26" rx="3" fill="#c8e4f8" opacity="0.9"/>'
    '<rect x="94" y="60" width="20" height="26" rx="3" fill="#b8d8f2" opacity="0.9"/>'
    '<rect x="120" y="60" width="20" height="26" rx="3" fill="#b8d8f2" opacity="0.9"/>'
    '<rect x="42" y="95" width="20" height="26" rx="3" fill="#b8d8f2" opacity="0.80"/>'
    '<rect x="68" y="95" width="20" height="26" rx="3" fill="#b8d8f2" opacity="0.80"/>'
    '<rect x="94" y="95" width="20" height="26" rx="3" fill="#c8e4f8" opacity="0.80"/>'
    '<rect x="120" y="95" width="20" height="26" rx="3" fill="#b8d8f2" opacity="0.80"/>'
    '<rect x="42" y="130" width="20" height="26" rx="3" fill="#b8d8f2" opacity="0.70"/>'
    '<rect x="68" y="130" width="20" height="26" rx="3" fill="#c8e4f8" opacity="0.70"/>'
    '<rect x="94" y="130" width="20" height="26" rx="3" fill="#b8d8f2" opacity="0.70"/>'
    '<rect x="120" y="130" width="20" height="26" rx="3" fill="#b8d8f2" opacity="0.70"/>'
    '<rect x="42" y="165" width="20" height="26" rx="3" fill="#b8d8f2" opacity="0.60"/>'
    '<rect x="68" y="165" width="20" height="26" rx="3" fill="#b8d8f2" opacity="0.60"/>'
    '<rect x="94" y="165" width="20" height="26" rx="3" fill="#b8d8f2" opacity="0.60"/>'
    '<rect x="120" y="165" width="20" height="26" rx="3" fill="#c8e4f8" opacity="0.60"/>'
    '<rect x="78" y="207" width="44" height="48" rx="4" fill="#d4d0ca"/>'
    '<rect x="84" y="213" width="14" height="42" rx="2" fill="#a8b5be" opacity="0.8"/>'
    '<rect x="102" y="213" width="14" height="42" rx="2" fill="#a8b5be" opacity="0.8"/>'
    '<rect x="4" y="235" width="6" height="20" rx="2" fill="#8B6A40"/>'
    '<circle cx="7" cy="224" r="14" fill="#5a9e5a" opacity="0.90"/>'
    '<circle cx="0" cy="230" r="9" fill="#6ab46a" opacity="0.80"/>'
    '<rect x="190" y="235" width="6" height="20" rx="2" fill="#8B6A40"/>'
    '<circle cx="193" cy="224" r="14" fill="#5a9e5a" opacity="0.90"/>'
    '<circle cx="200" cy="230" r="9" fill="#4a8e4a" opacity="0.80"/>'
    '</svg>'
)

_hero_walker_svg = (
    '<svg class="hero-walker" viewBox="0 0 78 138" width="78">'
    '<circle cx="39" cy="21" r="15" fill="#f5d5b0"/>'
    '<ellipse cx="39" cy="11" rx="15" ry="10" fill="#2d2016"/>'
    '<circle cx="33" cy="21" r="2" fill="#2d2016"/>'
    '<circle cx="45" cy="21" r="2" fill="#2d2016"/>'
    '<path d="M35 28 Q39 32 43 28" stroke="#c08060" stroke-width="1.5" fill="none" stroke-linecap="round"/>'
    '<path d="M21 40 Q19 78 23 108 L35 106 L35 64 L43 64 L43 106 L55 108 Q59 78 57 40 Q49 34 39 36 Q29 34 21 40Z" fill="#e8762a"/>'
    '<path d="M31 40 L39 47 L47 40" stroke="#f8e8d8" stroke-width="2" fill="none"/>'
    '<path d="M55 46 Q69 57 67 71" stroke="#e8762a" stroke-width="11" stroke-linecap="round" fill="none"/>'
    '<path d="M55 46 Q69 57 67 71" stroke="#f08840" stroke-width="7" stroke-linecap="round" fill="none"/>'
    '<rect x="59" y="67" width="13" height="20" rx="3" fill="#2d2016"/>'
    '<rect x="61" y="70" width="9" height="14" rx="1" fill="#60a8e0" opacity="0.9"/>'
    '<path d="M23 46 Q11 58 15 70" stroke="#e8762a" stroke-width="11" stroke-linecap="round" fill="none"/>'
    '<path d="M23 46 Q11 58 15 70" stroke="#f08840" stroke-width="7" stroke-linecap="round" fill="none"/>'
    '<path d="M23 106 L27 138 L39 136 L39 116 L39 136 L51 138 L55 106Z" fill="#2d3a4a"/>'
    '<ellipse cx="30" cy="137" rx="9" ry="4" fill="#3a8a80"/>'
    '<ellipse cx="48" cy="137" rx="9" ry="4" fill="#3a8a80"/>'
    '</svg>'
)

st.markdown(f"""
<div class="hero-wrap">
  <div class="hero-content">
    <div class="hero-badge-warm">AI POWERED · NEW TAIPEI</div>
    <div class="hero-title-warm">智慧房價 <span>診斷</span> 系統</div>
    <div class="hero-subtitle-warm">Smart House Price Diagnosis System</div>
  </div>
  {_hero_city_svg}
  <div class="hero-main-building">
    <div class="price-bubble">55 萬/坪</div>
    {_hero_building_svg}
  </div>
  {_hero_walker_svg}
  <div class="hero-ground"></div>
</div>
""", unsafe_allow_html=True)


# ==========================================
# 📊 資料庫載入
# ==========================================
with st.spinner("載入資料庫..."):
    try:
        df = load_database()
        model, model_ver = load_model()
    except Exception as e:
        st.error(f"❌ 資料庫載入失敗：{e}")
        st.stop()

src_info = df['來源'].value_counts().to_dict() if '來源' in df.columns else {}
c1, c2, c3, c4 = st.columns(4)
with c1: st.metric("📦 資料庫總筆數", f"{len(df):,}")
with c2: st.metric("🏛️ 實價登錄", f"{src_info.get('實價登錄', len(df)):,}")
with c3: st.metric("🕷️ 591 掛牌", f"{src_info.get('591', 0):,}")
with c4: st.metric("🤖 AI 模型", f"{len(model.models) if model else 0} 區專屬")

st.markdown("<hr class='divider'>", unsafe_allow_html=True)

# ==========================================
# 📋 輸入區（自製 Tab）
# ==========================================
if 'active_tab' not in st.session_state:
    st.session_state['active_tab'] = 'url'

col_t1, col_t2, col_t3 = st.columns([2, 2, 8])
with col_t1:
    if st.button("🔗  貼上 591 網址", key="tab_btn_url",
                 type="primary" if st.session_state['active_tab'] == 'url' else "secondary"):
        st.session_state['active_tab'] = 'url'
        st.rerun()
with col_t2:
    if st.button("✏️  手動輸入", key="tab_btn_manual",
                 type="primary" if st.session_state['active_tab'] == 'manual' else "secondary"):
        st.session_state['active_tab'] = 'manual'
        st.rerun()

tab_choice = st.session_state['active_tab']

# ─────────────── Tab 1：URL ───────────────
if tab_choice == 'url':
    st.caption("貼上 591 房屋詳細頁網址，系統將**自動偵測**行政區與路段")

    def on_url_change():
        url = st.session_state.get('url_input_field', '').strip()
        for k in ['fetched_info', 'auto_fetch_error', 'show_result', 'diag_params']:
            st.session_state[k] = None
        st.session_state['show_result'] = False
        if not url or not is_valid_591_url(url):
            return
        info, err = fetch_591_detail(url)
        if err:
            st.session_state['auto_fetch_error'] = err
        else:
            st.session_state['fetched_info'] = info
            st.session_state['mode'] = 'url'

    st.text_input(
        "591 房屋詳細頁網址",
        placeholder="https://sale.591.com.tw/home/house/detail/2/XXXXXXXX.html",
        key="url_input_field", on_change=on_url_change, label_visibility="collapsed",
    )

    if st.button("🔍  按我搜尋591網址資訊", key="btn_fetch_url", type="primary"):
        url = st.session_state.get('url_input_field', '').strip()
        for k in ['fetched_info', 'auto_fetch_error', 'show_result', 'diag_params']:
            st.session_state[k] = None
        st.session_state['show_result'] = False
        if not url:
            st.warning("請先貼上網址")
        elif not is_valid_591_url(url):
            st.session_state['auto_fetch_error'] = "網址格式不符，請確認是 591 房屋詳細頁網址"
        else:
            with st.spinner("偵測中..."):
                info, err = fetch_591_detail(url)
            if err:
                st.session_state['auto_fetch_error'] = err
            else:
                st.session_state['fetched_info'] = info
                st.session_state['mode'] = 'url'
            st.rerun()

    if st.session_state.get('auto_fetch_error'):
        st.markdown(f'<div class="detect-err">❌ 自動偵測失敗：{st.session_state["auto_fetch_error"]}</div>', unsafe_allow_html=True)
    elif st.session_state.get('fetched_info') and st.session_state.get('mode') == 'url':
        info = st.session_state['fetched_info']
        st.markdown(
            f'<div class="detect-ok">✅ 已自動偵測 → 行政區：<b>{info["district"]}</b>　路段：<b>{info["street"]}</b>'
            f'　<span style="color:#6b7280;font-size:0.78rem">（{info["full_addr"]}）</span></div>',
            unsafe_allow_html=True
        )

    if st.session_state.get('mode') == 'url' and st.session_state.get('fetched_info'):
        info = st.session_state['fetched_info']
        st.markdown("#### 📋 物件資訊確認")
        rows = [
            ('標題', info['title']), ('地址', f"{info['region']}{info['district']}{info['street']}"),
            ('型態', info['type']), ('樓層', info['floor']), ('屋齡', f"{info['age']} 年"),
            ('總價', f"{info['total']} 萬"), ('坪數', f"{info['area']} 坪"),
        ]
        rows_html = ''.join(f'<div class="info-row"><span class="info-label">{k}</span><span class="info-value">{v}</span></div>' for k, v in rows)
        rows_html += f'<div class="info-row"><span class="info-label">單價</span><span class="info-value" style="color:#e8a020">{info["unit_price"]} 萬/坪</span></div>'
        st.markdown(f'<div class="card">{rows_html}</div>', unsafe_allow_html=True)

        col_a, col_b = st.columns(2)
        with col_a:
            dist_confirmed = st.text_input("行政區（可修改）", value=info['district'], key="dist_url")
        with col_b:
            road_confirmed = st.text_input("路段（可修改）", value=info['street'], key="road_url")

        if st.button("📊  開始診斷", key="btn_diag_url"):
            st.session_state['diag_params'] = {
                'district': dist_confirmed, 'street': road_confirmed,
                'age': info['age'], 'floor': info['floor'],
                'target_type': info['type'], 'my_unit': info['unit_price'],
            }
            st.session_state['show_result'] = True

# ─────────────── Tab 2：手動 ───────────────
if tab_choice == 'manual':
    st.markdown('<div class="card">', unsafe_allow_html=True)
    districts = sorted([str(x) for x in df['行政區'].unique() if str(x) not in ('nan', '')])
    sel_dist = st.selectbox("行政區", districts, key="manual_dist")
    streets  = sorted([str(x) for x in df[df['行政區'] == sel_dist]['街道'].unique()])
    sel_road = st.selectbox("路段", streets, key="manual_road")

    col1, col2, col3 = st.columns(3)
    with col1:
        man_total = st.number_input("總價（萬）", min_value=100.0, max_value=99999.0, value=1500.0, step=50.0)
        man_size  = st.number_input("坪數（坪）", min_value=5.0,   max_value=999.0,  value=30.0,  step=0.5)
    with col2:
        man_age   = st.number_input("屋齡（年）", min_value=0.0,   max_value=80.0,   value=15.0,  step=1.0)
        man_floor = st.text_input("樓層（如：8 或 8/12）", value="8")
    with col3:
        man_type  = st.selectbox("型態", ["大樓", "公寓", "透天厝"])
        st.text_input("門牌（選填）", value="")
    st.markdown('</div>', unsafe_allow_html=True)

    if st.button("📊  開始診斷", key="btn_diag_manual") and man_size > 0:
        st.session_state['diag_params'] = {
            'district': sel_dist, 'street': sel_road,
            'age': man_age, 'floor': man_floor,
            'target_type': man_type, 'my_unit': round(man_total / man_size, 1),
        }
        st.session_state['mode'] = 'manual'
        st.session_state['show_result'] = True


# ==========================================
# 📊 診斷結果
# ==========================================
if st.session_state.get('show_result') and st.session_state.get('diag_params'):
    p = st.session_state['diag_params']
    st.markdown("<hr class='divider'>", unsafe_allow_html=True)
    st.markdown("## 📊 診斷報告")

    result, err = run_diagnosis(df, p['district'], p['street'], p['age'], p['floor'], p['target_type'], p['my_unit'])
    if err:
        st.error(f"❌ {err}")
    else:
        final_p, count, diff, listing_avg, ref = result['final_p'], result['count'], result['diff'], result['listing_avg'], result['ref']

        if result['fallback_street']:
            st.info(f"⚠️ 找不到「{p['street']}」完整路段，以「{result['fallback_street']}」開頭路段替代比對。")

        # AI 模型估價
        ai_model_price = ai_model_low = ai_model_high = ai_model_conf = ai_model_tag = None
        if model:
            try:
                r = model.predict(district=p['district'], street=p['street'], house_type=p['target_type'],
                                  age=float(p['age']) if p['age'] else 10, floor=p['floor'])
                ai_model_price, ai_model_low, ai_model_high = r['estimated_price'], r['price_range_low'], r['price_range_high']
                ai_model_conf, ai_model_tag = r['confidence'], r.get('model_used', model_ver)
            except Exception:
                pass

        # 指標卡片
        tag_html = (
            f'<span class="tag-high">🚨 明顯偏高 {diff:+.1f}%</span>' if diff > 10 else
            f'<span class="tag-mid">⚠️ 略高 {diff:+.1f}%</span>' if diff > 0 else
            f'<span class="tag-ok">✅ 合理 {diff:+.1f}%</span>'
        )
        lst_html = f'<div class="card-sub">591掛牌均價：{listing_avg} 萬/坪</div>' if listing_avg else ''

        cols = st.columns(4 if ai_model_price else 3)
        with cols[0]:
            st.markdown(f'<div class="card card-blue"><div class="card-title">📈 實價行情均價</div><div class="card-value">{round(final_p,1)} <span class="card-unit">萬/坪</span></div><div class="card-sub">樣本 {count} 筆</div></div>', unsafe_allow_html=True)
        with cols[1]:
            st.markdown(f'<div class="card card-gold"><div class="card-title">💰 該物件單價</div><div class="card-value">{p["my_unit"]} <span class="card-unit">萬/坪</span></div><div class="card-sub">{p["district"]}{p["street"]} · {p["target_type"]}</div></div>', unsafe_allow_html=True)
        with cols[2]:
            st.markdown(f'<div class="card card-judge"><div class="card-title">📢 價格判定</div><div style="margin:8px 0">{tag_html}</div>{lst_html}</div>', unsafe_allow_html=True)
        if ai_model_price and len(cols) == 4:
            conf_color = "#22c55e" if ai_model_conf == '高' else ("#f59e0b" if ai_model_conf == '中' else "#ef4444")
            with cols[3]:
                st.markdown(f'<div class="card card-ai"><div class="card-title">🤖 AI 模型估價</div><div class="card-value">{ai_model_price} <span class="card-unit">萬/坪</span></div><div class="card-sub">區間 {ai_model_low}～{ai_model_high} · <span style="color:{conf_color}">信心{ai_model_conf}</span></div><div class="card-sub" style="font-size:0.72rem;margin-top:4px">{ai_model_tag}</div></div>', unsafe_allow_html=True)

        # 分佈圖
        import plotly.express as px
        if not ref.empty:
            st.markdown("#### 📍 區域成交價分佈 (相對於報價)")
            fig = px.histogram(ref, x="單價", nbins=20,
                               title=f"{p['street']} 周邊成交單價分佈",
                               labels={'單價': '成交單價 (萬/坪)', 'count': '成交筆數'},
                               color_discrete_sequence=['#9aa0b0'], opacity=0.7)
            buf = 5
            fig.update_xaxes(range=[min(ref['單價'].min(), p['my_unit']) - buf, max(ref['單價'].max(), p['my_unit']) + buf])
            fig.add_vline(x=p['my_unit'], line_dash="dash", line_color="#ef4444", line_width=3,
                          annotation_text=f"物件報價: {p['my_unit']} 萬",
                          annotation_position="top right", annotation_font=dict(size=14, color="#ef4444"))
            fig.update_layout(plot_bgcolor='rgba(240,242,246,0.5)', paper_bgcolor='rgba(0,0,0,0)',
                              margin=dict(t=40, b=40, l=20, r=20), height=350,
                              xaxis_title="單價 (萬/坪)", yaxis_title="成交筆數", bargap=0.1)
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("#### 📋 相似成交案例")
            show_ref = ref[['街道', '型態', '屋齡', '單價']].copy()
            show_ref['單價'] = show_ref['單價'].round(1)
            show_ref['屋齡'] = show_ref['屋齡'].apply(lambda x: round(float(x), 1) if __import__('pandas').notna(x) else '-')
            show_ref.columns = ['街道', '型態', '屋齡(年)', '單價(萬/坪)']
            st.dataframe(show_ref.head(10).reset_index(drop=True), use_container_width=True, hide_index=True)

        # 議價建議
        st.markdown("<hr class='divider'>", unsafe_allow_html=True)
        st.markdown("## 💡 議價建議")
        advice_choice = st.radio("", ["🚀   雲端 AI 顧問", "🤖   本地引擎"],
                                 horizontal=True, label_visibility="collapsed", key="advice_radio")

        if advice_choice == "🚀   雲端 AI 顧問":
            api_key = st.text_input("Gemini API Key", type="password", placeholder="AIzaSy...", help="至 Google AI Studio 取得 Key")
            if st.button("🚀   生成 AI 議價建議", key="btn_ai"):
                if not api_key.strip():
                    st.warning("請輸入 API Key")
                else:
                    with st.spinner("正在串接雲端 AI..."):
                        advice, err2 = get_ai_advice(diff, f"{p['district']}{p['street']}", p['age'], p['floor'],
                                                     p['target_type'], p['my_unit'], final_p, count, listing_avg, api_key.strip())
                    if err2:
                        st.error(f"⚠️ {err2}")
                        st.markdown("**自動切換至本地引擎：**")
                        st.markdown(f'<div class="local-box">{get_local_advice(diff, final_p, p["age"], listing_avg)}</div>', unsafe_allow_html=True)
                    else:
                        st.success("🚀 雲端 AI 顧問連線成功")
                        st.markdown(f'<div class="ai-box">{advice}</div>', unsafe_allow_html=True)

        if advice_choice == "🤖   本地引擎":
            st.markdown(f'<div class="local-box">{get_local_advice(diff, final_p, p["age"], listing_avg)}</div>', unsafe_allow_html=True)


# ==========================================
# 🔔 每日警報訂閱設定
# ==========================================
ALERT_CONFIG_PATH = os.path.join(current_dir, 'alert_config.json')
DISTRICT_OPTIONS = {
    "板橋區": 37, "三重區": 46, "中和區": 39, "永和區": 52,
    "新莊區": 55, "新店區": 54, "土城區": 49, "蘆洲區": 53,
    "樹林區": 48, "汐止區": 44, "淡水區": 47, "泰山區": 50,
    "林口區": 41, "五股區": 51, "鶯歌區": 57, "三峽區": 45,
}

def load_alert_config():
    if os.path.exists(ALERT_CONFIG_PATH):
        with open(ALERT_CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"districts": ["板橋區"], "threshold": -10, "max_alerts": 10, "house_types": ["大樓"]}

def save_alert_config(cfg):
    with open(ALERT_CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

st.markdown("<hr class='divider'>", unsafe_allow_html=True)
with st.expander("🔔 每日 LINE 警報設定", expanded=False):
    cfg = load_alert_config()
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        sel_districts = st.multiselect("監控行政區（可多選）", options=list(DISTRICT_OPTIONS.keys()),
                                       default=cfg.get("districts", ["板橋區"]), key="alert_districts")
        sel_types = st.multiselect("房屋類型", options=["大樓", "公寓", "透天厝"],
                                   default=cfg.get("house_types", ["大樓"]), key="alert_types")
    with col_s2:
        threshold_default = cfg.get("threshold", [-20, -10])
        if isinstance(threshold_default, int):
            threshold_default = [threshold_default, -5]
        sel_threshold = st.slider("行情門檻範圍：通知低於行情幾% 的物件",
                                  min_value=-30, max_value=30, value=(threshold_default[0], threshold_default[1]),
                                  step=1, format="%d%%", key="alert_threshold")
        sel_max = st.number_input("每次最多通知幾筆", min_value=1, max_value=30,
                                  value=cfg.get("max_alerts", 10), step=1, key="alert_max")

    def build_cfg():
        return {
            "districts": sel_districts,
            "threshold": [int(sel_threshold[0]), int(sel_threshold[1])],
            "max_alerts": int(sel_max),
            "house_types": sel_types,
        }

    col_save, col_push = st.columns([2, 3])
    with col_save:
        if st.button("💾  儲存設定", key="btn_save_alert", use_container_width=True):
            if not sel_districts:
                st.warning("請至少選一個行政區")
            elif not sel_types:
                st.warning("請至少選一種房屋類型")
            else:
                save_alert_config(build_cfg())
                st.success("✅ 設定已儲存！")

    with col_push:
        st.image("https://qr-official.line.me/sid/L/761zjrzc.png", width=120, caption="掃碼加入官方帳號")
        RENDER_URL = "https://real-estate-analyzer-72i6.onrender.com"
        nickname = st.text_input("輸入你的暱稱", placeholder="請輸入綁定時設定的暱稱")
        if st.button("📲  推播給我", key="btn_push_line", use_container_width=True, type="primary"):
            if not nickname.strip():
                st.warning("請輸入暱稱")
            elif not sel_districts:
                st.warning("請至少選一個行政區")
            elif not sel_types:
                st.warning("請至少選一種房屋類型")
            else:
                save_alert_config(build_cfg())
                with st.spinner("🔍 搜尋並推播中，請稍候..."):
                    try:
                        # 確認暱稱是否存在
                        check = requests.get(f"{RENDER_URL}/check/{nickname.strip()}", timeout=10)
                        if check.json().get("exists"):
                            import daily_alert
                            message = daily_alert.run_alert_and_return()
                            resp = requests.post(
                                f"{RENDER_URL}/push",
                                json={"nickname": nickname.strip(), "message": message},
                                timeout=60
                            )
                            if resp.status_code == 200:
                                st.success(f"✅ 已成功推播給「{nickname.strip()}」！")
                            else:
                                st.error("❌ 推播失敗，請稍後再試")
                        else:
                            st.error("❌ 找不到此暱稱，請確認是否已加入官方帳號並完成綁定")
                    except Exception as e:
                        st.error(f"❌ 推播失敗：{e}")

# ==========================================
# Footer
# ==========================================
st.markdown("""
<div class="footer-wrap">
  <div class="footer-logo">智慧房價<span>診斷</span>系統</div>
  <div class="footer-meta">
    <span class="footer-tag">🏛️ 內政部實價登錄</span>
    <span class="footer-tag">🕷️ 591 房屋交易網</span>
    <span class="footer-tag">🤖 機器學習模型</span>
    <br>本系統資料僅供參考，不構成任何投資建議
  </div>
</div>
""", unsafe_allow_html=True)