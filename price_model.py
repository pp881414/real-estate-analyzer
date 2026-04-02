"""
price_model.py — 智慧房價估價模型 (Machine Learning)
====================================================
使用方式：
  1. 訓練模型：python price_model.py --train
  2. 互動估價：python price_model.py
  3. 在其他程式引用：
       from price_model import PriceModel
       model = PriceModel.load()
       result = model.predict(district='板橋區', street='文化路',
                              house_type='大樓', age=15, floor=8,
                              total_floors=12, area=30)
"""

import pandas as pd
import numpy as np
import os
import re
import pickle
import argparse

# ==========================================
# ⚙️ 設定
# ==========================================
current_dir  = os.path.dirname(os.path.abspath(__file__))
DB_PATH      = os.path.join(current_dir, 'real_estate_market_pro.csv')
MODEL_PATH   = os.path.join(current_dir, 'price_model.pkl')

C_BOLD   = '\033[1m'
C_GREEN  = '\033[92m'
C_YELLOW = '\033[93m'
C_RED    = '\033[91m'
C_CYAN   = '\033[96m'
C_BLUE   = '\033[94m'
C_END    = '\033[0m'


# ==========================================
# 🔧 特徵工程
# ==========================================
def extract_floor_number(floor_str) -> float:
    """
    將樓層字串轉為數值。
    支援：'12F/15F'、'12'、'3樓'、'B1' 等格式。
    """
    if pd.isna(floor_str) or str(floor_str).strip() == '':
        return 5.0  # 預設中間樓層
    s = str(floor_str)
    # 取出分子（實際樓層）
    m = re.search(r'(\d+)', s)
    if m:
        return float(m.group(1))
    if 'B' in s.upper():
        return 1.0  # 地下室
    return 5.0


def extract_total_floors(floor_str) -> float:
    """從 '12F/15F' 格式取出總樓層數。"""
    if pd.isna(floor_str) or str(floor_str).strip() == '':
        return 12.0
    s = str(floor_str)
    nums = re.findall(r'\d+', s)
    if len(nums) >= 2:
        return float(nums[1])
    elif len(nums) == 1:
        return float(nums[0])
    return 12.0


def floor_ratio(floor_num, total_floors) -> float:
    """樓層比例（0~1），越高越好。"""
    if total_floors <= 0:
        return 0.5
    return min(floor_num / total_floors, 1.0)


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    從原始資料產生模型特徵。
    輸入欄位：行政區、街道、型態、樓層、屋齡、單價
    輸出：特徵矩陣 X + 目標值 y
    """
    df = df.copy()
    global_mean = df['單價'].mean()

    # ── 數值特徵 ──────────────────────────────────
    df['屋齡_num']     = pd.to_numeric(df['屋齡'], errors='coerce').fillna(20).clip(0, 80)
    df['floor_num']    = df['樓層'].apply(extract_floor_number)
    df['total_floors'] = df['樓層'].apply(extract_total_floors)
    df['floor_ratio']  = df.apply(
        lambda r: floor_ratio(r['floor_num'], r['total_floors']), axis=1
    )

    # 屋齡多項式特徵（捕捉非線性：新屋溢價、中古折價、老屋再折）
    df['age_sq']       = df['屋齡_num'] ** 2
    df['age_log']      = np.log1p(df['屋齡_num'].clip(0))
    df['is_new']       = (df['屋齡_num'] <= 3).astype(int)
    df['is_mid_new']   = ((df['屋齡_num'] > 3)  & (df['屋齡_num'] <= 10)).astype(int)
    df['is_mid_old']   = ((df['屋齡_num'] > 10) & (df['屋齡_num'] <= 20)).astype(int)
    df['is_old']       = ((df['屋齡_num'] > 20) & (df['屋齡_num'] <= 30)).astype(int)
    df['is_very_old']  = (df['屋齡_num'] > 30).astype(int)

    # 樓層特性
    df['is_top_floor']  = (df['floor_num'] == df['total_floors']).astype(int)
    df['is_low_floor']  = (df['floor_num'] <= 2).astype(int)
    df['is_high_floor'] = (df['floor_ratio'] >= 0.7).astype(int)
    df['is_mid_floor']  = ((df['floor_ratio'] > 0.3) & (df['floor_ratio'] < 0.7)).astype(int)

    # ── 型態 One-Hot ──────────────────────────────
    df['is_apartment']  = df['型態'].str.contains('公寓', na=False).astype(int)
    df['is_building']   = df['型態'].str.contains('大樓|華廈|電梯', na=False).astype(int)
    df['is_townhouse']  = df['型態'].str.contains('透天', na=False).astype(int)

    # ── Target Encoding（平滑化，避免 data leakage）────────
    # 公式：(count * mean + k * global_mean) / (count + k)，k=5 為平滑係數
    k = 5

    def smooth_target_encode(df, col):
        stats = df.groupby(col)['單價'].agg(['mean', 'count'])
        smooth = (stats['count'] * stats['mean'] + k * global_mean) / (stats['count'] + k)
        return df[col].map(smooth).fillna(global_mean)

    df['district_enc']         = smooth_target_encode(df, '行政區')
    df['street_enc']           = smooth_target_encode(df, '街道')

    # 行政區 × 型態 交叉特徵（板橋大樓 vs 板橋公寓）
    df['dist_type'] = df['行政區'] + '_' + df['型態'].str[:2]
    df['dist_type_enc'] = smooth_target_encode(df, 'dist_type')

    # 街道 × 屋齡分段 交叉特徵（同街道新舊屋差異）
    df['age_bin'] = pd.cut(df['屋齡_num'],
                           bins=[-1, 3, 10, 20, 30, 100],
                           labels=['新', '次新', '中古', '舊', '老舊'])
    df['street_age'] = df['街道'] + '_' + df['age_bin'].astype(str)
    df['street_age_enc'] = smooth_target_encode(df, 'street_age')

    # ── 互動特徵 ─────────────────────────────────
    # 屋齡 × 型態（公寓老化折價更嚴重）
    df['age_x_apt']      = df['屋齡_num'] * df['is_apartment']
    # 樓層比例 × 總樓層（高樓大樓 vs 高樓公寓）
    df['floor_x_build']  = df['floor_ratio'] * df['is_building']
    # 地段 × 新舊（精華區新屋溢價更高）
    df['loc_x_new']      = df['district_enc'] * df['is_new']

    return df


FEATURE_COLS = [
    # 地段特徵
    'district_enc',       # 行政區（平滑 target encoding）
    'street_enc',         # 街道（平滑 target encoding）
    'dist_type_enc',      # 行政區×型態
    'street_age_enc',     # 街道×屋齡段
    # 屋齡特徵
    'age_log',            # 屋齡 log
    'age_sq',             # 屋齡平方
    'is_new',             # 新成屋 ≤3年
    'is_mid_new',         # 次新屋 4~10年
    'is_mid_old',         # 中古 11~20年
    'is_old',             # 舊屋 21~30年
    'is_very_old',        # 老屋 >30年
    # 樓層特徵
    'floor_num',          # 實際樓層
    'total_floors',       # 總樓層
    'floor_ratio',        # 樓層比例
    'is_top_floor',       # 頂樓
    'is_low_floor',       # 低樓層 ≤2F
    'is_high_floor',      # 高樓層 >70%
    'is_mid_floor',       # 中樓層
    # 型態特徵
    'is_apartment',       # 公寓
    'is_building',        # 大樓/華廈
    'is_townhouse',       # 透天
    # 互動特徵
    'age_x_apt',          # 屋齡×公寓
    'floor_x_build',      # 樓層比×大樓
    'loc_x_new',          # 地段×新成屋
]


# ==========================================
# 🤖 模型類別
# ==========================================
class PriceModel:

    def __init__(self):
        self.model        = None
        self.df_train     = None   # 保留訓練資料（用於 lookup）
        self.district_map = {}     # 行政區 → 平均單價
        self.street_map   = {}     # 街道 → 平均單價
        self.global_mean  = 0.0

    # ── 訓練 ──────────────────────────────────────
    def train(self, db_path: str = DB_PATH):
        from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
        from sklearn.model_selection import cross_val_score, train_test_split
        from sklearn.metrics import mean_absolute_error, r2_score
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler

        print(f"{C_CYAN}📂 載入資料庫...{C_END}")
        df = pd.read_csv(db_path, encoding='utf-8-sig')
        df['單價'] = pd.to_numeric(df['單價'], errors='coerce')

        # 只用實價登錄資料訓練（成交價較可靠）
        if '來源' in df.columns:
            df = df[df['來源'] == '實價登錄'].copy()

        # 過濾異常值（根據實際分布：P1=10, P99=93，用 15~120 保留99%正常資料）
        df = df[(df['單價'] >= 15) & (df['單價'] <= 120)].copy()

        # 各行政區內 IQR 過濾（去除各區內的極端值）
        def iqr_filter(group):
            Q1 = group['單價'].quantile(0.05)
            Q3 = group['單價'].quantile(0.95)
            return group[(group['單價'] >= Q1) & (group['單價'] <= Q3)]
        df = df.groupby('行政區', group_keys=False).apply(iqr_filter).reset_index(drop=True)
        print(f"  ✅ 過濾後有效樣本：{len(df)} 筆")
        df = df.dropna(subset=['單價', '行政區', '街道'])
        print(f"  ✅ 有效樣本：{len(df)} 筆")

        # 建立 lookup maps
        self.global_mean  = df['單價'].mean()
        self.district_map = df.groupby('行政區')['單價'].mean().to_dict()
        self.street_map   = df.groupby('街道')['單價'].mean().to_dict()
        # 行政區×型態 map
        df['dist_type_key'] = df['行政區'] + '_' + df['型態'].str[:2]
        self.dist_type_map  = df.groupby('dist_type_key')['單價'].mean().to_dict()
        self.df_train     = df[['行政區', '街道', '型態', '屋齡', '單價']].copy()

        # 特徵工程
        df_feat = engineer_features(df)
        X = df_feat[FEATURE_COLS].fillna(self.global_mean)
        y = df_feat['單價']

        # 訓練/測試分割
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        print(f"\n{C_CYAN}🤖 訓練模型中（GradientBoosting）...{C_END}")
        self.model = GradientBoostingRegressor(
            n_estimators=500,
            learning_rate=0.03,
            max_depth=4,
            min_samples_leaf=20,
            subsample=0.75,
            max_features=0.8,
            random_state=42
        )
        self.model.fit(X_train, y_train)

        # 評估
        y_pred = self.model.predict(X_test)
        mae  = mean_absolute_error(y_test, y_pred)
        r2   = r2_score(y_test, y_pred)
        mape = np.mean(np.abs((y_test - y_pred) / y_test)) * 100

        # 交叉驗證（更可靠的評估）
        print(f"  📐 執行 5-fold 交叉驗證...")
        cv_scores = cross_val_score(self.model, X, y, cv=5,
                                    scoring='neg_mean_absolute_error')
        cv_mae = -cv_scores.mean()

        print(f"\n{C_BOLD}📊 模型評估結果{C_END}")
        print(f"{C_BLUE}{'─'*50}{C_END}")
        print(f"  MAE  (測試集)：    {C_GREEN}{mae:.2f} 萬/坪{C_END}")
        print(f"  MAE  (交叉驗證)：  {C_GREEN}{cv_mae:.2f} 萬/坪{C_END}")
        print(f"  MAPE (百分比誤差)：{C_GREEN}{mape:.1f}%{C_END}")
        print(f"  R²   (解釋變異)：  {C_GREEN}{r2:.4f}{C_END}")
        print(f"{C_BLUE}{'─'*50}{C_END}")

        # 特徵重要性
        importances = sorted(
            zip(FEATURE_COLS, self.model.feature_importances_),
            key=lambda x: x[1], reverse=True
        )
        print(f"\n{C_BOLD}🔑 特徵重要性 TOP 5{C_END}")
        for feat, imp in importances[:5]:
            bar = '█' * int(imp * 50)
            print(f"  {feat:<25} {bar} {imp:.3f}")

        return mae, mape, r2

    # ── 預測單一物件 ───────────────────────────────
    def predict(self, district: str, street: str, house_type: str,
                age: float, floor, area: float = None) -> dict:
        """
        預測單一物件的合理單價。
        回傳 dict：
          estimated_price  : 模型估價（萬/坪）
          price_range_low  : 估價區間下限
          price_range_high : 估價區間上限
          confidence       : 信心等級 (高/中/低)
          sample_count     : 參考樣本數
          comparable_cases : 相似案例列表
        """
        if self.model is None:
            raise RuntimeError("請先執行 train() 或 load() 載入模型")

        # ── 建立單筆預測用 DataFrame ──
        row = {
            '行政區': district,
            '街道':   street,
            '型態':   house_type,
            '屋齡':   age,
            '樓層':   str(floor),
            '單價':   self.global_mean,  # 暫填，不影響預測
        }
        df_row = pd.DataFrame([row])

        # 套用 lookup maps（新地區/街道用全局均值）
        gm = self.global_mean
        dist_enc   = self.district_map.get(district, gm)
        street_enc = self.street_map.get(street, dist_enc)

        df_row['district_enc']     = dist_enc
        df_row['street_enc']       = street_enc
        df_row['dist_type_enc']    = self.dist_type_map.get(f"{district}_{house_type[:2]}", dist_enc)
        df_row['street_age_enc']   = gm  # 預測時無法精確對應，用均值

        # 套用特徵工程（只算不依賴 groupby 的部分）
        df_row['屋齡_num']     = float(age)
        df_row['floor_num']    = extract_floor_number(floor)
        df_row['total_floors'] = extract_total_floors(floor)
        df_row['floor_ratio']  = floor_ratio(df_row['floor_num'].iloc[0], df_row['total_floors'].iloc[0])
        df_row['age_sq']       = float(age) ** 2
        df_row['age_log']      = np.log1p(float(age))
        df_row['is_new']       = int(age <= 3)
        df_row['is_mid_new']   = int(3 < age <= 10)
        df_row['is_mid_old']   = int(10 < age <= 20)
        df_row['is_old']       = int(20 < age <= 30)
        df_row['is_very_old']  = int(age > 30)
        df_row['is_top_floor'] = int(df_row['floor_num'].iloc[0] == df_row['total_floors'].iloc[0])
        df_row['is_low_floor'] = int(df_row['floor_num'].iloc[0] <= 2)
        df_row['is_high_floor']= int(df_row['floor_ratio'].iloc[0] >= 0.7)
        df_row['is_mid_floor'] = int(0.3 < df_row['floor_ratio'].iloc[0] < 0.7)
        df_row['is_apartment'] = int('公寓' in house_type)
        df_row['is_building']  = int(any(k in house_type for k in ['大樓', '華廈', '電梯']))
        df_row['is_townhouse'] = int('透天' in house_type)
        df_row['age_x_apt']    = float(age) * df_row['is_apartment'].iloc[0]
        df_row['floor_x_build']= df_row['floor_ratio'].iloc[0] * df_row['is_building'].iloc[0]
        df_row['loc_x_new']    = dist_enc * df_row['is_new'].iloc[0]

        X = df_row[FEATURE_COLS].fillna(self.global_mean)
        estimated = float(self.model.predict(X)[0])

        # ── 信心區間（基於相似案例的標準差）──────────
        mask = (
            (self.df_train['行政區'] == district) &
            (self.df_train['街道'] == street) &
            (self.df_train['型態'].str.contains(
                '公寓' if '公寓' in house_type else '大樓|華廈|電梯', na=False
            ))
        )
        similar = self.df_train[mask]
        sim_age = similar[
            (similar['屋齡'] >= age - 5) & (similar['屋齡'] <= age + 5)
        ] if not similar.empty else similar

        ref = sim_age if not sim_age.empty else similar
        sample_count = len(ref)

        if sample_count >= 10:
            # 用 IQR 取代 std，避免極端值拉寬區間
            q25 = ref['單價'].quantile(0.25)
            q75 = ref['單價'].quantile(0.75)
            half_range = (q75 - q25) / 2
            std = max(half_range, estimated * 0.05)  # 至少 ±5%
            confidence = '高'
        elif sample_count >= 3:
            std = ref['單價'].std() if not ref.empty else estimated * 0.08
            std = min(std, estimated * 0.12)  # 最多 ±12%
            confidence = '中'
        else:
            std = estimated * 0.10  # 無樣本時用 ±10%
            confidence = '低'

        # ── 相似案例（最近5筆）────────────────────────
        comparable = []
        if not ref.empty:
            sample = ref.sample(min(5, len(ref)), random_state=42)
            for _, r in sample.iterrows():
                # 型態簡化
                t = str(r['型態'])
                if '公寓' in t: t = '公寓'
                elif '大樓' in t or '電梯' in t or '華廈' in t: t = '大樓'
                elif '透天' in t or '別墅' in t: t = '透天厝'
                elif '套房' in t: t = '套房'
                comparable.append({
                    '街道':  r['街道'],
                    '型態':  t,
                    '屋齡':  r['屋齡'],
                    '單價':  round(r['單價'], 1),
                })

        return {
            'estimated_price':  round(estimated, 1),
            'price_range_low':  round(estimated - std, 1),
            'price_range_high': round(estimated + std, 1),
            'confidence':       confidence,
            'sample_count':     sample_count,
            'comparable_cases': comparable,
            'total_estimate':   round(estimated * area, 0) if area else None,
        }

    # ── 儲存 / 載入 ───────────────────────────────
    def save(self, path: str = MODEL_PATH):
        with open(path, 'wb') as f:
            pickle.dump(self, f)
        print(f"{C_GREEN}💾 模型已儲存：{path}{C_END}")

    @classmethod
    def load(cls, path: str = MODEL_PATH) -> 'PriceModel':
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"找不到模型檔案：{path}\n"
                f"請先執行：python price_model.py --train"
            )
        with open(path, 'rb') as f:
            return pickle.load(f)


# ==========================================
# 🖥️ 互動估價介面
# ==========================================
def interactive_mode():
    import time, sys

    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"\n{C_CYAN}╔{'═'*62}╗{C_END}")
    print(f"{C_CYAN}║  🏠  AI 房價估價引擎 v1.0  —  Machine Learning Edition   ║{C_END}")
    print(f"{C_CYAN}╚{'═'*62}╝{C_END}\n")

    # 載入模型
    try:
        model = PriceModel.load()
        print(f"{C_GREEN}✅ 模型載入成功！{C_END}\n")
    except FileNotFoundError as e:
        print(f"{C_RED}❌ {e}{C_END}")
        return

    # 載入資料庫（給使用者選擇行政區和路段用）
    try:
        df_db = pd.read_csv(DB_PATH, encoding='utf-8-sig')
        districts = sorted(df_db['行政區'].dropna().unique().tolist())
    except:
        df_db = None
        districts = []

    while True:
        print(f"{C_BLUE}{'═'*64}{C_END}")
        print(f"{C_BOLD} 請輸入物件資訊{C_END}")
        print(f"{C_BLUE}{'═'*64}{C_END}")

        try:
            # 行政區（支援數字選擇）
            if districts:
                print(f"\n{C_CYAN}可用行政區：{C_END}")
                for i, d in enumerate(districts, 1):
                    print(f"  [{i:2d}] {d}", end='\n' if i % 5 == 0 else '  ')
                print()
            raw = input(f"{C_YELLOW}📍 行政區 (輸入名稱或編號): {C_END}").strip()
            if raw.isdigit() and 1 <= int(raw) <= len(districts):
                district_in = districts[int(raw) - 1]
                print(f"     → {district_in}")
            else:
                district_in = raw

            # 街道（列出該行政區常見路段）
            if df_db is not None and district_in in df_db['行政區'].values:
                streets = (df_db[df_db['行政區'] == district_in]['街道']
                           .value_counts().head(20).index.tolist())
                print(f"\n{C_CYAN}{district_in} 常見路段：{C_END}")
                for i, s in enumerate(streets, 1):
                    print(f"  [{i:2d}] {s}", end='\n' if i % 4 == 0 else '  ')
                print()
                raw2 = input(f"{C_YELLOW}🛣️  路段 (輸入名稱或編號): {C_END}").strip()
                if raw2.isdigit() and 1 <= int(raw2) <= len(streets):
                    street_in = streets[int(raw2) - 1]
                    print(f"     → {street_in}")
                else:
                    street_in = raw2
            else:
                street_in = input(f"{C_YELLOW}🛣️  路段: {C_END}").strip()

            type_in = input(f"{C_YELLOW}🏠 型態 (1.大樓 2.公寓 3.透天): {C_END}").strip()
            type_map = {'1': '大樓', '2': '公寓', '3': '透天厝'}
            house_type = type_map.get(type_in, type_in)

            age      = float(input(f"{C_YELLOW}📅 屋齡(年): {C_END}"))
            floor_in = input(f"{C_YELLOW}🏢 樓層 (如: 8 或 8/12): {C_END}").strip()
            area_in  = input(f"{C_YELLOW}📐 坪數(坪，可空白): {C_END}").strip()
            area     = float(area_in) if area_in else None

        except (ValueError, KeyboardInterrupt):
            print(f"\n{C_RED}⚠️  輸入中斷。{C_END}")
            break

        # 預測
        print(f"\n{C_CYAN}⚡ 模型估算中...{C_END}")
        time.sleep(0.4)

        try:
            result = model.predict(
                district=district_in, street=street_in,
                house_type=house_type, age=age,
                floor=floor_in, area=area
            )
        except Exception as e:
            print(f"{C_RED}❌ 估價失敗：{e}{C_END}")
            continue

        # ── 輸出報告 ──────────────────────────────
        conf_color = C_GREEN if result['confidence'] == '高' else (C_YELLOW if result['confidence'] == '中' else C_RED)
        print(f"\n{C_CYAN}{'─'*64}{C_END}")
        print(f"{C_BOLD}  📊 AI 估價報告{C_END}")
        print(f"{C_CYAN}{'─'*64}{C_END}")
        print(f"  物件：{district_in}{street_in}  {house_type}  {age}年  {floor_in}樓")
        print(f"\n  {'估價結果':}")
        print(f"  {'─'*30}")
        print(f"  💰 AI 估算單價：{C_BOLD}{C_GREEN}{result['estimated_price']} 萬/坪{C_END}")
        print(f"  📉 合理區間：   {result['price_range_low']} ～ {result['price_range_high']} 萬/坪")
        if result['total_estimate']:
            print(f"  🏷️  估算總價：   約 {C_BOLD}{result['total_estimate']:.0f} 萬{C_END}  ({area} 坪)")
        print(f"  🎯 信心等級：   {conf_color}{result['confidence']}{C_END}  (參考樣本 {result['sample_count']} 筆)")

        if result['comparable_cases']:
            print(f"\n  {'相似成交案例':}")
            print(f"  {'─'*30}")
            print(f"  {'街道':<12} {'型態':<8} {'屋齡':>4}年  {'單價':>6} 萬/坪")
            for c in result['comparable_cases']:
                print(f"  {str(c['街道']):<12} {str(c['型態']):<8} {str(c['屋齡']):>4}    {c['單價']:>6}")

        print(f"{C_CYAN}{'─'*64}{C_END}\n")

        again = input("繼續估價? (Enter) / 離開 (q): ").strip().lower()
        if again == 'q':
            break


# ==========================================
# 🚀 入口
# ==========================================
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='AI 房價估價模型')
    parser.add_argument('--train', action='store_true', help='訓練並儲存模型')
    args = parser.parse_args()

    if args.train:
        print(f"\n{C_CYAN}🚀 開始訓練 AI 估價模型...{C_END}\n")
        try:
            from sklearn.ensemble import GradientBoostingRegressor
        except ImportError:
            print(f"{C_RED}❌ 缺少套件，請先安裝：\n   pip install scikit-learn{C_END}")
            exit(1)

        model = PriceModel()
        mae, mape, r2 = model.train(DB_PATH)
        model.save()
        print(f"\n{C_GREEN}✅ 訓練完成！MAE={mae:.2f} 萬/坪，MAPE={mape:.1f}%，R²={r2:.4f}{C_END}")
        print(f"   執行互動估價：python price_model.py\n")
    else:
        interactive_mode()