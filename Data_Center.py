import pandas as pd
import os
import glob
import re

def clean_and_combine():
    # --- 自動路徑偵測 ---
    current_dir = os.path.dirname(os.path.abspath(__file__))
    raw_data_path = os.path.join(current_dir, 'raw_data')
    output_path = os.path.join(current_dir, 'real_estate_market_pro.csv')
    spider_path = os.path.join(current_dir, '591_live_data.csv')  # ✅ 新增：Spider 輸出路徑

    if not os.path.exists(raw_data_path):
        os.makedirs(raw_data_path)
        print(f"📂 已自動建立 raw_data 資料夾：{raw_data_path}")
        print(f"👉 請將實價登錄 CSV 放入該資料夾後重新執行。")

    all_files = glob.glob(os.path.join(raw_data_path, "*.csv"))
    combined_list = []

    # ==========================================
    # 📥 Part 1：解析實價登錄 CSV
    # ==========================================
    def simplify_street(addr):
        if not isinstance(addr, str): return addr
        match = re.search(r'([^,]+?([路街巷弄]|大道))', addr)
        if match:
            res = match.group(1)
            res = re.sub(r'.+?[縣市]', '', res)
            res = re.sub(r'.+?[區市鎮鄉]', '', res)
            return res
        return addr

    if all_files:
        print(f"📦 正在提取實價登錄資料並淨化路段資料...")
        for file in all_files:
            try:
                try:
                    temp_df = pd.read_csv(file, skiprows=[1], encoding='utf-8', low_memory=False)
                except:
                    temp_df = pd.read_csv(file, skiprows=[1], encoding='big5', low_memory=False)

                cols = temp_df.columns.tolist()
                col_dist   = next((c for c in cols if '鄉鎮市區' in c), None)
                col_street = next((c for c in cols if '土地區段位置' in c or '門牌' in c), None)
                col_type   = next((c for c in cols if '建物型態' in c), None)
                col_price  = next((c for c in cols if '單價元' in c), None)
                col_age    = next((c for c in cols if '建築完成年月' in c), None)
                col_floor  = next((c for c in cols if '移轉層次' in c), None)
                col_total  = next((c for c in cols if '總價元' in c), None)

                if all([col_dist, col_street, col_type, col_price]):
                    mask = temp_df[col_street].str.contains('路|街|巷|大道', na=False)
                    new_df = temp_df[mask].copy()
                    new_df = new_df[[col_dist, col_street, col_type, col_price, col_age, col_floor, col_total]]
                    new_df[col_dist]   = new_df[col_dist].astype(str).str.replace('新北市', '').str.strip()
                    new_df[col_street] = new_df[col_street].astype(str).apply(simplify_street)
                    new_df['單價']     = (pd.to_numeric(new_df[col_price], errors='coerce') / 0.3025) / 10000

                    def calc_age(finish_date):
                        try:
                            val = str(finish_date).strip()
                            # 過濾無效值
                            if val in ('', 'nan', 'None', '0', '00', '000'):
                                return None
                            # 先轉成整數字串，去掉浮點數小數點（如 841208.0 → '841208'）
                            val = str(int(float(val)))
                            # 民國年月格式：
                            #   7碼 (1120908) → 前3碼為民國年（民國100年以後）
                            #   6碼 (841208)  → 前2碼為民國年（民國99年以前）
                            if len(val) == 7:
                                roc_year = int(val[:3])
                            elif len(val) == 6:
                                roc_year = int(val[:2])
                            else:
                                return None
                            # 民國年應在 40~120 之間（西元1951~2031）
                            if roc_year < 40 or roc_year > 120:
                                return None
                            age = 115 - roc_year
                            # 屋齡應在 0~80 之間
                            return age if 0 <= age <= 80 else None
                        except:
                            return None

                    new_df['屋齡'] = new_df[col_age].apply(calc_age)
                    new_df = new_df.rename(columns={
                        col_dist: '行政區', col_street: '街道', col_type: '型態',
                        col_floor: '樓層', col_total: '總價'
                    })
                    new_df = new_df.dropna(subset=['單價', '街道', '行政區'])
                    new_df['來源'] = '實價登錄'
                    combined_list.append(new_df[['行政區', '街道', '型態', '樓層', '屋齡', '總價', '單價', '來源']])
                    print(f"  ✅ 已成功解析：{os.path.basename(file)}")
            except Exception as e:
                print(f"  ⚠️ 錯誤：{os.path.basename(file)} -> {e}")
    else:
        print(f"⚠️  raw_data 資料夾中無 CSV，跳過實價登錄部分。")

    # ==========================================
    # 🕷️ Part 2：整合 591 Spider 爬蟲資料
    # ==========================================
    if os.path.exists(spider_path):
        print(f"\n🕷️  正在整合 591 爬蟲資料：{spider_path}")
        try:
            spider_df = pd.read_csv(spider_path, encoding='utf-8-sig')

            # 確保必要欄位存在
            required_cols = ['行政區', '街道', '型態', '單價']
            missing = [c for c in required_cols if c not in spider_df.columns]
            if missing:
                print(f"  ❌ 591 資料缺少欄位：{missing}，請確認 Spider.py 版本。")
            else:
                spider_df = spider_df.dropna(subset=['單價', '街道', '行政區'])
                spider_df = spider_df[spider_df['單價'] > 0]

                # 補齊缺失欄位
                if '來源'  not in spider_df.columns: spider_df['來源'] = '591'
                if '樓層'  not in spider_df.columns: spider_df['樓層'] = ''
                if '屋齡'  not in spider_df.columns: spider_df['屋齡'] = None
                if '總價'  not in spider_df.columns: spider_df['總價'] = None

                # 型態正規化
                def normalize_type(t):
                    t = str(t)
                    if '大樓' in t: return '大樓'
                    if '公寓' in t: return '公寓'
                    if '透天' in t or '別墅' in t: return '透天厝'
                    return t

                spider_df['型態'] = spider_df['型態'].apply(normalize_type)

                combined_list.append(
                    spider_df[['行政區', '街道', '型態', '樓層', '屋齡', '總價', '單價', '來源']]
                )
                print(f"  ✅ 已整合 {len(spider_df)} 筆 591 掛牌資料。")
        except Exception as e:
            print(f"  ⚠️ 讀取 591 資料失敗：{e}")
    else:
        print(f"\n💡 未找到 591 爬蟲資料（{spider_path}），若需要請先執行 Spider.py。")

    # ==========================================
    # 💾 合併輸出
    # ==========================================
    if combined_list:
        final_df = pd.concat(combined_list, ignore_index=True)
        final_df = final_df[final_df['行政區'].str.len() > 0]
        final_df['單價'] = pd.to_numeric(final_df['單價'], errors='coerce')
        final_df = final_df.dropna(subset=['單價'])
        final_df.to_csv(output_path, index=False, encoding='utf-8-sig')

        src_counts = final_df['來源'].value_counts().to_dict()
        print(f"\n🚀 【數據中心完成】資料庫路徑：{output_path}")
        print(f"📈 總計產出 {len(final_df)} 筆資料。")
        for src, cnt in src_counts.items():
            print(f"   └─ {src}：{cnt} 筆")
    else:
        print("❌ 失敗：無有效資料（請確認 raw_data 或 591 資料來源）。")

if __name__ == "__main__":
    clean_and_combine()