"""
price_model_v2.py — 分區域 AI 房價估價模型
==========================================
每個行政區各有一個專屬模型，大幅提升精準度。

使用方式：
  訓練：python price_model_v2.py --train
  估價：python price_model_v2.py
  引用：from price_model_v2 import DistrictPriceModel
"""

import pandas as pd
import numpy as np
import os, re, pickle, argparse

current_dir = os.path.dirname(os.path.abspath(__file__))
DB_PATH     = os.path.join(current_dir, 'real_estate_market_pro.csv')
MODEL_PATH  = os.path.join(current_dir, 'price_model_v2.pkl')
MIN_SAMPLES = 100   # 低於此筆數的區用全局模型備援

C_BOLD  = '\033[1m'
C_GREEN = '\033[92m'
C_YELLOW= '\033[93m'
C_RED   = '\033[91m'
C_CYAN  = '\033[96m'
C_BLUE  = '\033[94m'
C_END   = '\033[0m'


# ==========================================
# 🔧 特徵工程（單區專用，地段特徵更細緻）
# ==========================================
def extract_floor_number(s) -> float:
    s = str(s)
    m = re.search(r'(\d+)', s)
    return float(m.group(1)) if m else 5.0

def extract_total_floors(s) -> float:
    nums = re.findall(r'\d+', str(s))
    return float(nums[1]) if len(nums) >= 2 else (float(nums[0]) if nums else 12.0)

def floor_ratio(fn, tf) -> float:
    return min(fn / tf, 1.0) if tf > 0 else 0.5

def build_features(df: pd.DataFrame, global_mean: float) -> pd.DataFrame:
    df = df.copy()
    k = 3  # 小樣本用更小的平滑係數

    def smooth_enc(col):
        stats = df.groupby(col)['單價'].agg(['mean','count'])
        s = (stats['count']*stats['mean'] + k*global_mean) / (stats['count']+k)
        return df[col].map(s).fillna(global_mean)

    # 地段特徵（區內更細緻）
    df['street_enc']     = smooth_enc('街道')
    df['age_bin']        = pd.cut(df['屋齡_num'], bins=[-1,3,8,15,25,80],
                                   labels=['新','次新','中古','舊','老'])
    df['street_age']     = df['街道'] + '_' + df['age_bin'].astype(str)
    df['street_age_enc'] = smooth_enc('street_age')
    df['type_enc']       = smooth_enc('型態')

    # 屋齡特徵
    df['age_log']     = np.log1p(df['屋齡_num'].clip(0))
    df['age_sq']      = df['屋齡_num'] ** 2
    df['is_new']      = (df['屋齡_num'] <= 3).astype(int)
    df['is_mid_new']  = ((df['屋齡_num'] > 3)  & (df['屋齡_num'] <= 8)).astype(int)
    df['is_mid']      = ((df['屋齡_num'] > 8)  & (df['屋齡_num'] <= 15)).astype(int)
    df['is_old']      = ((df['屋齡_num'] > 15) & (df['屋齡_num'] <= 25)).astype(int)
    df['is_very_old'] = (df['屋齡_num'] > 25).astype(int)

    # 樓層特徵
    df['floor_num']    = df['樓層'].apply(extract_floor_number)
    df['total_floors'] = df['樓層'].apply(extract_total_floors)
    df['floor_ratio']  = df.apply(lambda r: floor_ratio(r['floor_num'], r['total_floors']), axis=1)
    df['is_top']       = (df['floor_num'] == df['total_floors']).astype(int)
    df['is_low']       = (df['floor_num'] <= 2).astype(int)
    df['is_high']      = (df['floor_ratio'] >= 0.7).astype(int)

    # 型態特徵
    df['is_apt']   = df['型態'].str.contains('公寓', na=False).astype(int)
    df['is_bld']   = df['型態'].str.contains('大樓|華廈|電梯', na=False).astype(int)
    df['is_town']  = df['型態'].str.contains('透天', na=False).astype(int)

    # 互動特徵
    df['age_x_apt']   = df['屋齡_num'] * df['is_apt']
    df['floor_x_bld'] = df['floor_ratio'] * df['is_bld']
    df['new_x_bld']   = df['is_new'] * df['is_bld']

    return df

FEAT = [
    'street_enc', 'street_age_enc', 'type_enc',
    'age_log', 'age_sq', 'is_new', 'is_mid_new', 'is_mid', 'is_old', 'is_very_old',
    'floor_num', 'total_floors', 'floor_ratio', 'is_top', 'is_low', 'is_high',
    'is_apt', 'is_bld', 'is_town',
    'age_x_apt', 'floor_x_bld', 'new_x_bld',
]


# ==========================================
# 🤖 分區模型
# ==========================================
class DistrictPriceModel:

    def __init__(self):
        self.models       = {}   # district → sklearn model
        self.global_model = None
        self.lookup       = {}   # district → {street_map, street_age_map, type_map, global_mean}
        self.global_mean  = 0.0
        self.global_lookup= {}
        self.df_ref       = None  # 用於相似案例查詢

    def _train_one(self, df_dist, district, global_mean, plot=False):
        from sklearn.ensemble import GradientBoostingRegressor
        from sklearn.metrics import mean_absolute_error, r2_score
        from sklearn.model_selection import train_test_split

        n = len(df_dist)
        df_dist = df_dist.copy()
        df_dist['屋齡_num'] = pd.to_numeric(df_dist['屋齡'], errors='coerce').fillna(15).clip(0,80)

        # ── 修正 Data Leakage：先分割，再做 Target Encoding ──────────
        # 樣本不足 50 筆時不分割（避免測試集過小），直接用訓練集評估
        if n >= 50:
            df_train, df_test = train_test_split(df_dist, test_size=0.2, random_state=42)
        else:
            df_train, df_test = df_dist.copy(), df_dist.copy()

        # ── 只用訓練集建立 encoding maps ──────────────────────────────
        k = 3
        def smap_from(df_src, col):
            """只用 df_src（訓練集）計算平滑 Target Encoding，回傳 dict"""
            s = df_src.groupby(col)['單價'].agg(['mean', 'count'])
            return ((s['count'] * s['mean'] + k * global_mean) / (s['count'] + k)).to_dict()

        # 訓練集的屋齡段（street_age 需要先算）
        df_train['age_bin']    = pd.cut(df_train['屋齡_num'], bins=[-1,3,8,15,25,80],
                                         labels=['新','次新','中古','舊','老'])
        df_train['street_age'] = df_train['街道'] + '_' + df_train['age_bin'].astype(str)

        street_map     = smap_from(df_train, '街道')
        street_age_map = smap_from(df_train, 'street_age')
        type_map       = smap_from(df_train, '型態')

        def apply_enc(df_src):
            """把訓練集算好的 map 套用到任意 DataFrame（未知值填 global_mean）"""
            df_src = df_src.copy()
            df_src['屋齡_num'] = pd.to_numeric(df_src['屋齡'], errors='coerce').fillna(15).clip(0,80)
            df_src['age_bin']    = pd.cut(df_src['屋齡_num'], bins=[-1,3,8,15,25,80],
                                           labels=['新','次新','中古','舊','老'])
            df_src['street_age'] = df_src['街道'] + '_' + df_src['age_bin'].astype(str)
            df_src['street_enc']     = df_src['街道'].map(street_map).fillna(global_mean)
            df_src['street_age_enc'] = df_src['street_age'].map(street_age_map).fillna(global_mean)
            df_src['type_enc']       = df_src['型態'].map(type_map).fillna(global_mean)
            return df_src

        # 套用 encoding 並做其餘特徵工程
        df_train_f = build_features(apply_enc(df_train), global_mean)
        df_test_f  = build_features(apply_enc(df_test),  global_mean)

        X_train = df_train_f[FEAT].fillna(global_mean)
        y_train = df_train_f['單價']
        X_test  = df_test_f[FEAT].fillna(global_mean)
        y_test  = df_test_f['單價']

        # ── 訓練模型（只用訓練集）────────────────────────────────────
        depth   = 4 if n >= 500 else 3
        n_est   = 400 if n >= 500 else 200
        min_smp = max(5, n // 50)

        model = GradientBoostingRegressor(
            n_estimators=n_est, learning_rate=0.04,
            max_depth=depth, min_samples_leaf=min_smp,
            subsample=0.8, max_features=0.85, random_state=42
        )
        model.fit(X_train, y_train)

        # ── 評估（用測試集，無 Leakage）──────────────────────────────
        y_pred = model.predict(X_test)
        mae  = mean_absolute_error(y_test, y_pred)
        mape = np.mean(np.abs((y_test - y_pred) / y_test)) * 100
        r2   = r2_score(y_test, y_pred)

        # ── 視覺化（可選）────────────────────────────────────────────
        if plot is not None:
            import matplotlib.pyplot as plt
            import matplotlib.font_manager as fm
            # Windows 中文字型設定
            for fname in ['Microsoft JhengHei', 'Microsoft YaHei', 'SimHei', 'DFKai-SB']:
                if any(fname.lower() in f.name.lower() for f in fm.fontManager.ttflist):
                    plt.rcParams['font.family'] = fname
                    break
            plt.rcParams['axes.unicode_minus'] = False

            fig, axes = plt.subplots(1, 3, figsize=(18, 5))
            fig.suptitle(f'【{district}】訓練視覺化', fontsize=14, fontweight='bold')

            # 圖1：損失曲線
            train_errors, test_errors = [], []
            for yp_tr in model.staged_predict(X_train):
                train_errors.append(mean_absolute_error(y_train, yp_tr))
            for yp_te in model.staged_predict(X_test):
                test_errors.append(mean_absolute_error(y_test, yp_te))
            axes[0].plot(train_errors, label='Train MAE', color='steelblue')
            axes[0].plot(test_errors,  label='Test MAE',  color='orange')
            axes[0].set_xlabel('樹的數量')
            axes[0].set_ylabel('MAE（萬/坪）')
            axes[0].set_title('訓練損失曲線')
            axes[0].legend()

            # 圖2：特徵重要性
            feat_df = pd.DataFrame({
                'feature':    FEAT,
                'importance': model.feature_importances_
            }).sort_values('importance', ascending=True)
            axes[1].barh(feat_df['feature'], feat_df['importance'], color='steelblue')
            axes[1].set_xlabel('重要性')
            axes[1].set_title('特徵重要性')

            # 圖3：預測 vs 實際
            axes[2].scatter(y_test, y_pred, alpha=0.4, color='steelblue', s=20)
            mn, mx = y_test.min(), y_test.max()
            axes[2].plot([mn, mx], [mn, mx], 'r--', label='完美預測線')
            axes[2].set_xlabel('實際單價（萬/坪）')
            axes[2].set_ylabel('預測單價（萬/坪）')
            axes[2].set_title(f'預測 vs 實際　MAE={mae:.2f} MAPE={mape:.1f}% R²={r2:.3f}')
            axes[2].legend()

            plt.tight_layout()
            plot.savefig(fig)   # plot 是 PdfPages 物件
            plt.close(fig)

        # ── 建立 lookup maps（用全部資料，供預測時查詢）──────────────
        # 注意：lookup 用全部資料是正確的，因為這是給「未來預測」用的統計
        # Data Leakage 只發生在「評估指標」階段，lookup 本身不影響評估
        df_dist['age_bin']    = pd.cut(df_dist['屋齡_num'], bins=[-1,3,8,15,25,80],
                                        labels=['新','次新','中古','舊','老'])
        df_dist['street_age'] = df_dist['街道'] + '_' + df_dist['age_bin'].astype(str)

        def smap(col):
            s = df_dist.groupby(col)['單價'].agg(['mean', 'count'])
            return ((s['count'] * s['mean'] + k * global_mean) / (s['count'] + k)).to_dict()

        lookup = {
            'street_map':     smap('街道'),
            'street_age_map': smap('street_age'),
            'type_map':       smap('型態'),
            'global_mean':    global_mean,
            'district_mean':  df_dist['單價'].mean(),
        }

        return model, lookup, mae, mape, r2

    def train(self, db_path=DB_PATH, plot=False):
        from sklearn.ensemble import GradientBoostingRegressor
        from sklearn.metrics import mean_absolute_error, r2_score
        from sklearn.model_selection import train_test_split

        # 開啟 PDF（若要視覺化）
        pdf = None
        if plot:
            import matplotlib
            matplotlib.use('Agg')
            from matplotlib.backends.backend_pdf import PdfPages
            pdf_path = os.path.join(current_dir, 'training_report.pdf')
            pdf = PdfPages(pdf_path)
            print(f"{C_CYAN}📊 視覺化報告將儲存至：{pdf_path}{C_END}")

        print(f"{C_CYAN}📂 載入資料庫...{C_END}")
        # 嘗試多種編碼
        for enc in ['utf-8-sig', 'utf-8', 'cp950']:
            try:
                df = pd.read_csv(db_path, encoding=enc)
                if '行政區' in df.columns:
                    break
            except:
                continue
        print(f"  欄位：{df.columns.tolist()}")
        df['單價'] = pd.to_numeric(df['單價'], errors='coerce')
        if '來源' in df.columns:
            df = df[df['來源'] == '實價登錄'].copy()
        df = df[(df['單價'] >= 15) & (df['單價'] <= 120)].copy()
        df = df.dropna(subset=['單價','行政區','街道'])

        # 各區 P5~P95 過濾
        def iqr_filter(g):
            Q1, Q3 = g['單價'].quantile(0.05), g['單價'].quantile(0.95)
            return g[(g['單價'] >= Q1) & (g['單價'] <= Q3)]
        df = df.groupby('行政區', group_keys=False).apply(iqr_filter).reset_index(drop=True)

        self.global_mean = df['單價'].mean()
        df_ref_copy = df[['行政區','街道','型態','屋齡','單價']].copy()
        # 相似案例顯示用：修正負數屋齡（負數為建築月數偏移）
        neg = df_ref_copy['屋齡'] < 0
        df_ref_copy.loc[neg, '屋齡'] = (-df_ref_copy.loc[neg, '屋齡'] / 12).round(1)
        df_ref_copy['屋齡'] = df_ref_copy['屋齡'].clip(0, 80)
        self.df_ref = df_ref_copy

        print(f"  ✅ 有效樣本：{len(df)} 筆，共 {df['行政區'].nunique()} 個行政區\n")

        districts = df['行政區'].value_counts()
        results = []

        print(f"{C_BOLD}{'行政區':<8} {'樣本':>6} {'MAE':>7} {'MAPE':>7} {'R²':>7} {'模型'}{C_END}")
        print(f"{C_BLUE}{'─'*50}{C_END}")

        for district, count in districts.items():
            df_d = df[df['行政區'] == district].copy()

            if count >= MIN_SAMPLES:
                model, lookup, mae, mape, r2 = self._train_one(df_d, district, self.global_mean, plot=pdf)
                self.models[district]  = model
                self.lookup[district]  = lookup
                tag = '專屬'
                color = C_GREEN if mape < 10 else (C_YELLOW if mape < 15 else C_RED)
                print(f"  {district:<8} {count:>6} {mae:>6.2f}萬 {color}{mape:>6.1f}%{C_END} {r2:>6.3f}  [{tag}]")
                results.append((district, count, mae, mape, r2))
            else:
                tag = '全局備援'
                print(f"  {district:<8} {count:>6} {'─':>7} {'─':>7} {'─':>7}  [{tag}]")

        # 全局備援模型
        print(f"\n{C_CYAN}🌐 訓練全局備援模型...{C_END}")
        df['屋齡_num'] = pd.to_numeric(df['屋齡'], errors='coerce').fillna(15).clip(0,80)
        df_g = build_features(df, self.global_mean)

        df_g['district_enc'] = df_g.groupby(df['行政區'])['單價'].transform('mean')
        feat_g = FEAT + ['district_enc'] if 'district_enc' not in FEAT else FEAT
        Xg = df_g[FEAT].fillna(self.global_mean)
        yg = df_g['單價']
        Xtr, Xte, ytr, yte = train_test_split(Xg, yg, test_size=0.2, random_state=42)
        self.global_model = GradientBoostingRegressor(
            n_estimators=400, learning_rate=0.04, max_depth=4,
            min_samples_leaf=15, subsample=0.8, random_state=42
        )
        self.global_model.fit(Xtr, ytr)
        yp = self.global_model.predict(Xte)
        g_mae  = mean_absolute_error(yte, yp)
        g_mape = np.mean(np.abs((yte-yp)/yte))*100
        g_r2   = r2_score(yte, yp)
        print(f"  全局模型：MAE={g_mae:.2f}萬，MAPE={g_mape:.1f}%，R²={g_r2:.4f}")

        # 統計摘要
        if results:
            maes  = [r[2] for r in results]
            mapes = [r[3] for r in results]
            r2s   = [r[4] for r in results]
            print(f"\n{C_BOLD}📊 分區模型整體表現{C_END}")
            print(f"{C_BLUE}{'─'*40}{C_END}")
            print(f"  專屬模型數量：  {len(results)} 個行政區")
            print(f"  平均 MAE：      {C_GREEN}{np.mean(maes):.2f} 萬/坪{C_END}")
            print(f"  平均 MAPE：     {C_GREEN}{np.mean(mapes):.1f}%{C_END}")
            print(f"  平均 R²：       {C_GREEN}{np.mean(r2s):.4f}{C_END}")
            good = sum(1 for m in mapes if m < 10)
            print(f"  MAPE < 10% 區數：{C_GREEN}{good}/{len(results)}{C_END}")
            print(f"{C_BLUE}{'─'*40}{C_END}")

        # 全局備援模型視覺化
        if pdf is not None:
            import matplotlib.pyplot as plt
            import matplotlib.font_manager as fm
            for fname in ['Microsoft JhengHei', 'Microsoft YaHei', 'SimHei', 'DFKai-SB']:
                if any(fname.lower() in f.name.lower() for f in fm.fontManager.ttflist):
                    plt.rcParams['font.family'] = fname
                    break
            plt.rcParams['axes.unicode_minus'] = False

            fig, axes = plt.subplots(1, 3, figsize=(18, 5))
            fig.suptitle('【全局備援模型】訓練視覺化', fontsize=14, fontweight='bold')

            # 圖1：損失曲線
            tr_err, te_err = [], []
            for yp_tmp in self.global_model.staged_predict(Xtr):
                tr_err.append(mean_absolute_error(ytr, yp_tmp))
            for yp_tmp in self.global_model.staged_predict(Xte):
                te_err.append(mean_absolute_error(yte, yp_tmp))
            axes[0].plot(tr_err, label='Train MAE', color='steelblue')
            axes[0].plot(te_err, label='Test MAE',  color='orange')
            axes[0].set_xlabel('樹的數量')
            axes[0].set_ylabel('MAE（萬/坪）')
            axes[0].set_title('訓練損失曲線')
            axes[0].legend()

            # 圖2：特徵重要性
            feat_df = pd.DataFrame({
                'feature':    FEAT,
                'importance': self.global_model.feature_importances_
            }).sort_values('importance', ascending=True)
            axes[1].barh(feat_df['feature'], feat_df['importance'], color='steelblue')
            axes[1].set_xlabel('重要性')
            axes[1].set_title('特徵重要性')

            # 圖3：預測 vs 實際
            axes[2].scatter(yte, yp, alpha=0.3, color='steelblue', s=10)
            mn, mx = yte.min(), yte.max()
            axes[2].plot([mn, mx], [mn, mx], 'r--', label='完美預測線')
            axes[2].set_xlabel('實際單價（萬/坪）')
            axes[2].set_ylabel('預測單價（萬/坪）')
            axes[2].set_title(f'預測 vs 實際　MAE={g_mae:.2f} MAPE={g_mape:.1f}% R²={g_r2:.3f}')
            axes[2].legend()

            plt.tight_layout()
            pdf.savefig(fig)
            plt.close(fig)

            pdf.close()
            print(f"{C_GREEN}📄 視覺化報告已儲存：{pdf_path}{C_END}")

    def predict(self, district, street, house_type, age, floor, area=None):
        age = float(age) if age else 10
        floor_num   = extract_floor_number(floor)
        total_floors= extract_total_floors(floor)
        f_ratio     = floor_ratio(floor_num, total_floors)

        # 判斷用哪個模型
        use_district = district if district in self.models else None
        lk = self.lookup.get(use_district, {})
        gm = lk.get('global_mean', self.global_mean)

        # 屋齡段
        age_bins = [(-1,3,'新'),(3,8,'次新'),(8,15,'中古'),(15,25,'舊'),(25,80,'老')]
        age_label = next((l for a,b,l in age_bins if a < age <= b), '老')
        street_age_key = f"{street}_{age_label}"

        row = {
            'street_enc':     lk.get('street_map', {}).get(street, gm),
            'street_age_enc': lk.get('street_age_map', {}).get(street_age_key, gm),
            'type_enc':       lk.get('type_map', {}).get(house_type, gm),
            'age_log':        np.log1p(age),
            'age_sq':         age**2,
            'is_new':         int(age<=3),
            'is_mid_new':     int(3<age<=8),
            'is_mid':         int(8<age<=15),
            'is_old':         int(15<age<=25),
            'is_very_old':    int(age>25),
            'floor_num':      floor_num,
            'total_floors':   total_floors,
            'floor_ratio':    f_ratio,
            'is_top':         int(floor_num==total_floors),
            'is_low':         int(floor_num<=2),
            'is_high':        int(f_ratio>=0.7),
            'is_apt':         int('公寓' in house_type),
            'is_bld':         int(any(k in house_type for k in ['大樓','華廈','電梯'])),
            'is_town':        int('透天' in house_type),
        }
        row['age_x_apt']   = age * row['is_apt']
        row['floor_x_bld'] = f_ratio * row['is_bld']
        row['new_x_bld']   = row['is_new'] * row['is_bld']

        X = pd.DataFrame([row])[FEAT].fillna(gm)

        model = self.models.get(use_district, self.global_model)
        if model is None:
            raise RuntimeError("模型未訓練")
        estimated = float(model.predict(X)[0])
        model_tag = f"{use_district}專屬" if use_district else "全局備援"

        # 信心區間
        if self.df_ref is not None:
            mask = (
                (self.df_ref['行政區'] == district) &
                (self.df_ref['街道'] == street) &
                (self.df_ref['型態'].str.contains(
                    '公寓' if '公寓' in house_type else '大樓|華廈|電梯', na=False))
            )
            ref = self.df_ref[mask]
            ref = ref[(ref['屋齡'] >= age-5) & (ref['屋齡'] <= age+5)] if not ref.empty else ref
            if ref.empty:
                ref = self.df_ref[self.df_ref['行政區'] == district]
        else:
            ref = pd.DataFrame()

        sample_count = len(ref)
        if sample_count >= 10:
            q25, q75 = ref['單價'].quantile(0.25), ref['單價'].quantile(0.75)
            std = max((q75-q25)/2, estimated*0.05)
            confidence = '高'
        elif sample_count >= 3:
            std = min(ref['單價'].std(), estimated*0.12)
            confidence = '中'
        else:
            std = estimated * 0.10
            confidence = '低'

        # 相似案例
        comparable = []
        if not ref.empty:
            for _, r in ref.sample(min(5,len(ref)), random_state=42).iterrows():
                t = str(r['型態'])
                if '公寓' in t: t='公寓'
                elif '大樓' in t or '電梯' in t or '華廈' in t: t='大樓'
                elif '透天' in t: t='透天厝'
                comparable.append({'街道':r['街道'],'型態':t,'屋齡':r['屋齡'],'單價':round(r['單價'],1)})

        return {
            'estimated_price':  round(estimated, 1),
            'price_range_low':  round(estimated - std, 1),
            'price_range_high': round(estimated + std, 1),
            'confidence':       confidence,
            'sample_count':     sample_count,
            'comparable_cases': comparable,
            'total_estimate':   round(estimated * area, 0) if area else None,
            'model_used':       model_tag,
        }

    def save(self, path=MODEL_PATH):
        with open(path, 'wb') as f:
            pickle.dump(self, f)
        print(f"{C_GREEN}💾 模型已儲存：{path}{C_END}")

    @classmethod
    def load(cls, path=MODEL_PATH):
        if not os.path.exists(path):
            raise FileNotFoundError(f"找不到模型：{path}\n請先執行：python price_model_v2.py --train")
        with open(path, 'rb') as f:
            return pickle.load(f)


# ==========================================
# 🖥️ 互動估價介面
# ==========================================
def interactive_mode():
    import time
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"\n{C_CYAN}╔{'═'*62}╗{C_END}")
    print(f"{C_CYAN}║  🏠  AI 房價估價引擎 v2.0  —  分區精準版              ║{C_END}")
    print(f"{C_CYAN}╚{'═'*62}╝{C_END}\n")

    try:
        model = DistrictPriceModel.load()
        print(f"{C_GREEN}✅ 模型載入成功！（{len(model.models)} 個專屬區域模型）{C_END}\n")
    except FileNotFoundError as e:
        print(f"{C_RED}❌ {e}{C_END}")
        return

    try:
        df_db = pd.read_csv(DB_PATH, encoding='utf-8-sig')
        districts = sorted(df_db['行政區'].dropna().unique().tolist())
    except:
        df_db = None
        districts = []

    while True:
        print(f"{C_BLUE}{'═'*64}{C_END}")
        try:
            if districts:
                print(f"\n{C_CYAN}可用行政區：{C_END}")
                for i, d in enumerate(districts, 1):
                    print(f"  [{i:2d}] {d}", end='\n' if i % 5 == 0 else '  ')
                print()
            raw = input(f"{C_YELLOW}📍 行政區 (名稱或編號): {C_END}").strip()
            if raw.isdigit() and 1 <= int(raw) <= len(districts):
                district_in = districts[int(raw)-1]
                print(f"     → {district_in}")
            else:
                district_in = raw

            if df_db is not None and district_in in df_db['行政區'].values:
                streets = (df_db[df_db['行政區']==district_in]['街道']
                           .value_counts().head(20).index.tolist())
                print(f"\n{C_CYAN}{district_in} 常見路段：{C_END}")
                for i, s in enumerate(streets, 1):
                    print(f"  [{i:2d}] {s}", end='\n' if i % 4 == 0 else '  ')
                print()
                raw2 = input(f"{C_YELLOW}🛣️  路段 (名稱或編號): {C_END}").strip()
                street_in = streets[int(raw2)-1] if raw2.isdigit() and 1<=int(raw2)<=len(streets) else raw2
                if raw2.isdigit() and 1<=int(raw2)<=len(streets):
                    print(f"     → {street_in}")
            else:
                street_in = input(f"{C_YELLOW}🛣️  路段: {C_END}").strip()

            type_in    = input(f"{C_YELLOW}🏠 型態 (1.大樓 2.公寓 3.透天): {C_END}").strip()
            house_type = {'1':'大樓','2':'公寓','3':'透天厝'}.get(type_in, type_in)
            age        = float(input(f"{C_YELLOW}📅 屋齡(年): {C_END}"))
            floor_in   = input(f"{C_YELLOW}🏢 樓層 (如: 8 或 8/12): {C_END}").strip()
            area_in    = input(f"{C_YELLOW}📐 坪數(可空白): {C_END}").strip()
            area       = float(area_in) if area_in else None
        except (ValueError, KeyboardInterrupt):
            print(f"\n{C_RED}⚠️  中斷。{C_END}")
            break

        print(f"\n{C_CYAN}⚡ 模型估算中...{C_END}")
        time.sleep(0.3)

        try:
            r = model.predict(district_in, street_in, house_type, age, floor_in, area)
        except Exception as e:
            print(f"{C_RED}❌ 估價失敗：{e}{C_END}")
            continue

        conf_c = C_GREEN if r['confidence']=='高' else (C_YELLOW if r['confidence']=='中' else C_RED)
        print(f"\n{C_CYAN}{'─'*64}{C_END}")
        print(f"{C_BOLD}  📊 AI 估價報告（{r['model_used']}）{C_END}")
        print(f"{C_CYAN}{'─'*64}{C_END}")
        print(f"  物件：{district_in}{street_in}  {house_type}  {age}年  {floor_in}樓")
        print(f"\n  {'─'*30}")
        print(f"  💰 AI 估算單價：{C_BOLD}{C_GREEN}{r['estimated_price']} 萬/坪{C_END}")
        print(f"  📉 合理區間：   {r['price_range_low']} ～ {r['price_range_high']} 萬/坪")
        if r['total_estimate']:
            print(f"  🏷️  估算總價：   約 {C_BOLD}{r['total_estimate']:.0f} 萬{C_END}  ({area} 坪)")
        print(f"  🎯 信心等級：   {conf_c}{r['confidence']}{C_END}  (參考 {r['sample_count']} 筆)")

        if r['comparable_cases']:
            print(f"\n  相似成交案例：")
            print(f"  {'─'*30}")
            print(f"  {'街道':<12} {'型態':<6} {'屋齡':>4}年  {'單價':>6} 萬/坪")
            for c in r['comparable_cases']:
                print(f"  {str(c['街道']):<12} {str(c['型態']):<6} {str(c['屋齡']):>5}    {c['單價']:>6}")
        print(f"{C_CYAN}{'─'*64}{C_END}\n")

        if input("繼續估價? (Enter) / 離開 (q): ").strip().lower() == 'q':
            break


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--train', action='store_true')
    args = parser.parse_args()

    if args.train:
        try:
            from sklearn.ensemble import GradientBoostingRegressor
        except ImportError:
            print(f"{C_RED}❌ 請先安裝：pip install scikit-learn{C_END}")
            exit(1)
        model = DistrictPriceModel()
        model.train(DB_PATH, plot=True)
        model.save()
        print(f"\n{C_GREEN}✅ 訓練完成！執行估價：python price_model_v2.py{C_END}\n")
    else:
        interactive_mode()