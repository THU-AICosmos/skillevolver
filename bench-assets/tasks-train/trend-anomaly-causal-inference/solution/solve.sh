#!/bin/bash
set -e

echo "=== Grocery Delivery Department Trend Analysis: solve.sh ==="
echo "Pipeline: Clean → Detect Anomalies → Engineer Features → DiD Causal Inference"

python3 <<'PYEOF'
import sys, os, json
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

RESULTS_DIR = os.environ.get('OUTPUT_DIR', '/app/output')
os.makedirs(RESULTS_DIR, exist_ok=True)

# Suppress prophet/cmdstanpy logging
os.environ['CMDSTAN_VERBOSE'] = 'false'
import logging
for logger_name in ['cmdstanpy', 'prophet']:
    lg = logging.getLogger(logger_name)
    lg.setLevel(logging.CRITICAL)
    lg.handlers = []
    lg.addHandler(logging.NullHandler())
    lg.propagate = False

# Add skill module paths
candidate_roots = [
    '/app/.claude/skills', '/app/.codex/skills', '/app/.opencode/skills',
    '/app/.goose/skills', '/app/.factory/skills', '/app/.agents/skills',
    '/app/skills', '.'
]
for root in candidate_roots:
    if os.path.exists(root):
        sys.path.append(os.path.join(root, 'data_cleaning/scripts'))
        sys.path.append(os.path.join(root, 'time_series_anomaly_detection/scripts'))
        sys.path.append(os.path.join(root, 'feature_engineering/scripts'))
        sys.path.append(os.path.join(root, 'did_causal_analysis/scripts'))
        break

from data_cleaning import CleaningStrategies, DataCleaningPipeline
from anomaly_detection import TimeSeriesAnomalyDetector
from feature_engineering import FeatureEngineeringStrategies, FeatureEngineeringPipeline
from did_analysis import DIDAnalyzer

# ================================================================
# PHASE 1: DATA CLEANING
# ================================================================
print("=" * 70)
print("PHASE 1: CLEANING RAW DATA")
print("=" * 70)

orders_raw = pd.read_csv('/app/data/grocery_orders_2020_dirty.csv')
demo_raw = pd.read_csv('/app/data/customer_survey_dirty.csv')
print(f"Loaded orders: {orders_raw.shape}, demographics: {demo_raw.shape}")

# Clean orders
order_cleaner = DataCleaningPipeline(name="Grocery Orders")
order_cleaner.add_step(
    CleaningStrategies.drop_missing,
    columns=['CustomerID', 'Order Date', 'Unit Price', 'Quantity', 'Department', 'Delivery Region'],
    description="Remove rows missing critical fields"
)
orders_clean = order_cleaner.execute(orders_raw, verbose=True)

# Clean demographics
demo_cleaner = DataCleaningPipeline(name="Customer Demographics")
demo_cleaner.add_step(
    CleaningStrategies.remove_duplicates,
    subset=['CustomerID'],
    description="Deduplicate by CustomerID"
).add_step(
    CleaningStrategies.drop_missing,
    columns=['CustomerID'],
    description="Remove null CustomerID rows"
).add_step(
    CleaningStrategies.impute_mode,
    columns=['D-cooking-frequency', 'D-gender', 'D-income-level', 'D-diet-type'],
    description="Mode-fill categorical columns with missing values"
).add_step(
    CleaningStrategies.impute_knn,
    target_features={
        'D-has-allergies': {
            'features': ['D-age-bracket', 'D-gender', 'D-income-level',
                         'D-education', 'D-region', 'D-diet-type',
                         'D-exercise-frequency', 'D-pet-owner', 'D-has-children',
                         'D-uses-coupons', 'D-owns-car', 'D-shops-organic',
                         'D-household-size', 'D-cooking-frequency'],
            'type': 'binary'
        }
    },
    n_neighbors=5,
    description="KNN impute D-has-allergies"
).add_step(
    CleaningStrategies.process_text,
    columns=['D-household-size'],
    operation='extract_numbers',
    description="Extract numbers from household size text"
).add_step(
    CleaningStrategies.cap_outliers_iqr,
    columns=['D-household-size'],
    multiplier=1.5,
    description="Cap household size outliers via IQR"
)
demo_clean = demo_cleaner.execute(demo_raw, verbose=True)

demo_clean.to_csv(f'{RESULTS_DIR}/demographics_cleaned.csv', index=False)
print(f"✓ Cleaned demographics: {RESULTS_DIR}/demographics_cleaned.csv ({len(demo_clean)} rows)")

orders_clean['Order Date'] = pd.to_datetime(orders_clean['Order Date'])
orders_clean.to_csv(f'{RESULTS_DIR}/grocery_orders_filtered.csv', index=False)
print(f"✓ Cleaned orders: {RESULTS_DIR}/grocery_orders_filtered.csv ({len(orders_clean)} rows)")

txn_data = orders_clean.copy()

# ================================================================
# PHASE 2: ANOMALY DETECTION WITH PROPHET
# ================================================================
print("\n" + "=" * 70)
print("PHASE 2: DEPARTMENT-LEVEL ANOMALY DETECTION")
print("=" * 70)

txn_data['Total_Revenue'] = txn_data['Quantity'] * txn_data['Unit Price']

# Filter departments with enough data points
dept_tx_counts = txn_data.groupby('Department').size()
MIN_TXN = 30
eligible_depts = dept_tx_counts[dept_tx_counts >= MIN_TXN].index.tolist()
txn_data = txn_data[txn_data['Department'].isin(eligible_depts)].copy()
print(f"Departments with >= {MIN_TXN} transactions: {len(eligible_depts)}")

print("\nRunning Prophet forecasting per department...")
prophet_detector = TimeSeriesAnomalyDetector(
    min_training_days=120,
    confidence_interval=0.68,
    changepoint_prior_scale=0.05,
    seasonality_prior_scale=10.0
)

detection_output = prophet_detector.detect_anomalies(
    df=txn_data,
    date_col='Order Date',
    category_col='Department',
    value_col='Total_Revenue',
    cutoff_date='2020-11-01',
    prediction_start='2020-11-01',
    prediction_end='2020-11-30',
    agg_func='sum'
)

dept_scores = detection_output['anomaly_summary']
TOP_K = 8
surge_dept_names = dept_scores.head(TOP_K)['Department'].tolist()
slump_dept_names = dept_scores.tail(TOP_K)['Department'].tolist()[::-1]

print(f"\n✓ Anomaly detection complete: {len(dept_scores)} departments")
print(f"  Top {TOP_K} surge: {surge_dept_names}")
print(f"  Top {TOP_K} slump: {slump_dept_names}")

dept_anomaly_df = dept_scores[['Department', 'Anomaly_Index']].copy()
dept_anomaly_df.columns = ['Department', 'Anomaly_Score']
dept_anomaly_df.to_csv(f'{RESULTS_DIR}/department_anomaly_scores.csv', index=False)
print(f"✓ Anomaly scores saved: {RESULTS_DIR}/department_anomaly_scores.csv")

# ================================================================
# PHASE 3: FEATURE ENGINEERING
# ================================================================
print("\n" + "=" * 70)
print("PHASE 3: DEMOGRAPHIC FEATURE ENGINEERING")
print("=" * 70)

num_feats, cat_feats, bin_feats = [], [], []
for col in demo_clean.columns:
    if col == 'CustomerID':
        continue
    nuniq = demo_clean[col].nunique()
    dt = demo_clean[col].dtype
    if nuniq == 2:
        bin_feats.append(col)
    elif pd.api.types.is_numeric_dtype(dt) and nuniq > 2:
        num_feats.append(col)
    elif nuniq <= 10 and nuniq > 2:
        cat_feats.append(col)
    else:
        cat_feats.append(col)

print(f"Feature types: numerical={len(num_feats)}, categorical={len(cat_feats)}, binary={len(bin_feats)}")

encode_cols = [
    'D-age-bracket', 'D-gender', 'D-income-level', 'D-education',
    'D-region', 'D-diet-type', 'D-cooking-frequency', 'D-exercise-frequency',
    'D-pet-owner', 'D-has-children', 'D-uses-coupons', 'D-owns-car',
    'D-has-allergies', 'D-shops-organic'
]
encode_cols = [c for c in encode_cols if c in demo_clean.columns]

feat_pipe = FeatureEngineeringPipeline(name="Demographics Features")
feat_pipe.add_step(
    FeatureEngineeringStrategies.encode_categorical,
    columns=encode_cols,
    method='onehot',
    max_categories=53,
    description="One-hot encode demographic columns"
)
feat_pipe.add_step(
    FeatureEngineeringStrategies.convert_to_binary,
    columns=bin_feats,
    description="Binary encode Yes/No columns"
)
feat_pipe.add_step(
    FeatureEngineeringStrategies.select_features_variance,
    columns=[],
    threshold=0.01,
    description="Drop low-variance features"
)

demo_all_cols = feat_pipe.execute(demo_clean, verbose=True)
eng_names = feat_pipe.get_engineered_features()
demo_eng = demo_all_cols[['CustomerID'] + eng_names].copy()

# Remove redundant "_No" columns
no_suffix_cols = [c for c in demo_eng.columns if c.endswith('_No')]
if no_suffix_cols:
    demo_eng = demo_eng.drop(columns=no_suffix_cols)
    print(f"Dropped {len(no_suffix_cols)} redundant '_No' columns")

demo_eng.to_csv(f'{RESULTS_DIR}/demographics_features.csv', index=False)
print(f"\n✓ Engineered features: {RESULTS_DIR}/demographics_features.csv ({len(demo_eng.columns)} cols)")

# ================================================================
# PHASE 4: DIFFERENCE-IN-DIFFERENCES CAUSAL ANALYSIS
# ================================================================
print("\n" + "=" * 70)
print("PHASE 4: DiD CAUSAL ANALYSIS")
print("=" * 70)

print("\nPreparing DiD panel data...")
did_orders = pd.read_csv(f'{RESULTS_DIR}/grocery_orders_filtered.csv')
did_orders['Order Date'] = pd.to_datetime(did_orders['Order Date'])

# Assign periods: Sep-Oct 2020 = baseline, Nov 2020 = treatment
did_orders['Period'] = pd.cut(
    did_orders['Order Date'],
    bins=[pd.Timestamp('2020-09-01'), pd.Timestamp('2020-10-31'), pd.Timestamp('2020-11-30')],
    labels=['baseline', 'treatment'],
    include_lowest=True
)
did_orders = did_orders.dropna(subset=['Period'])
did_orders['Period'] = did_orders['Period'].astype(str)
did_orders['Total_Revenue'] = did_orders['Quantity'] * did_orders['Unit Price']
did_orders = did_orders[['CustomerID', 'Department', 'Period', 'Total_Revenue']].copy()
print(f"DiD-period transactions: {len(did_orders)}")

# Aggregate to customer-department-period level
grp_keys = ['CustomerID', 'Department', 'Period']
agg_revenue = did_orders.groupby(grp_keys)['Total_Revenue'].sum().reset_index()
print(f"Aggregated panel rows: {agg_revenue.shape}")

# Merge with engineered features
panel_merged = agg_revenue.merge(demo_eng, on='CustomerID', how='inner')
print(f"Merged panel: {panel_merged.shape}")

# Restrict to top K surge + slump departments
focal_depts = surge_dept_names + slump_dept_names
panel_merged = panel_merged[panel_merged['Department'].isin(focal_depts)].copy()
print(f"Filtered to {len(focal_depts)} focal departments: {panel_merged.shape}")

# Save intensive margin input
panel_merged[['CustomerID', 'Department', 'Period', 'Total_Revenue']].to_csv(
    f'{RESULTS_DIR}/customer_dept_period_intensive.csv', index=False
)
print(f"✓ Intensive data saved ({len(panel_merged)} rows)")

# Identify binary features for DiD
skip_cols = {'CustomerID', 'Order Date', 'Department', 'Total_Revenue', 'Unnamed: 0', 'index', 'Period'}
binary_feat_list = []
for col in panel_merged.columns:
    if col in skip_cols:
        continue
    uvals = panel_merged[col].dropna().unique()
    if len(uvals) == 2 and set(uvals).issubset({0, 1, 0.0, 1.0}):
        binary_feat_list.append(col)
print(f"Binary features for DiD: {len(binary_feat_list)}")

for feat in binary_feat_list:
    panel_merged[feat] = panel_merged[feat].astype(float)

# Create anomaly lookup
score_lookup = dict(zip(dept_anomaly_df['Department'], dept_anomaly_df['Anomaly_Score']))

# DiD analyzers
did_intensive = DIDAnalyzer(min_sample_ratio=10, significance_level=0.1, min_group_size=2)
did_extensive = DIDAnalyzer(min_sample_ratio=200, significance_level=0.1, min_group_size=2)

def run_did_per_dept(dept_list, int_panel, raw_agg, demo_data, feats, did_int, did_ext, direction='positive', id_col='CustomerID'):
    """Run DiD analysis for a list of departments."""
    dept_reports = []

    # Build extensive panel: all customers × all departments × 2 periods
    all_custs = demo_data[[id_col]].drop_duplicates()
    depts_df = pd.DataFrame({'Department': dept_list})
    periods_df = pd.DataFrame({'Period': ['baseline', 'treatment']})
    ext_base = all_custs.merge(depts_df, how='cross').merge(periods_df, how='cross')

    order_keys = raw_agg[[id_col, 'Department', 'Period']].drop_duplicates()
    order_keys['Has_Order'] = 1
    ext_panel = ext_base.merge(order_keys, on=[id_col, 'Department', 'Period'], how='left')
    ext_panel['Has_Order'] = ext_panel['Has_Order'].fillna(0).astype(int)
    print(f"Extensive panel: {len(ext_panel)} rows ({len(all_custs)} customers × {len(dept_list)} depts × 2)")

    for pos, dept in enumerate(dept_list, 1):
        dept_int = int_panel[int_panel['Department'] == dept].copy()
        if len(dept_int) == 0:
            print(f"  [{pos}/{len(dept_list)}] {dept}: skipped (no data)")
            continue

        anom_val = score_lookup.get(dept, 0.0)
        bl_cnt = len(dept_int[dept_int['Period'] == 'baseline'])
        tr_cnt = len(dept_int[dept_int['Period'] == 'treatment'])
        print(f"  [{pos}/{len(dept_list)}] {dept}: {len(dept_int)} rows (bl={bl_cnt}, tr={tr_cnt})")

        # Intensive margin
        int_drivers = did_int.intensive_margin(
            df=dept_int, features=feats, value_col='Total_Revenue',
            top_n=3, sort_by='estimate', asc=(direction == 'negative')
        )
        if len(int_drivers) == 0:
            bl_sub = dept_int[dept_int['Period'] == 'baseline']
            tr_sub = dept_int[dept_int['Period'] == 'treatment']
            fallback = []
            for ft in feats[:10]:
                try:
                    if ft in bl_sub.columns and ft in tr_sub.columns:
                        bm = bl_sub[bl_sub[ft] == 1]['Total_Revenue'].mean()
                        tm = tr_sub[tr_sub[ft] == 1]['Total_Revenue'].mean()
                        if pd.notna(bm) and pd.notna(tm):
                            fallback.append({'feature': ft, 'did_estimate': float(tm - bm), 'p_value': None, 'method': 'Simple Difference'})
                except:
                    continue
            if fallback:
                fallback.sort(key=lambda x: x['did_estimate'], reverse=(direction == 'positive'))
                int_drivers = fallback[:3]

        # Extensive margin
        dept_ext = ext_panel[ext_panel['Department'] == dept].copy()
        ext_with_feats = dept_ext.merge(demo_data, on=id_col, how='inner')
        ext_with_feats = ext_with_feats.rename(columns={'Has_Order': 'has_purchase'})

        ext_drivers = did_ext.extensive_margin(
            df=ext_with_feats, features=feats, value_col='has_purchase',
            top_n=3, sort_by='estimate', asc=(direction == 'negative')
        )
        if len(ext_drivers) == 0:
            bl_ext = ext_with_feats[ext_with_feats['Period'] == 'baseline']
            tr_ext = ext_with_feats[ext_with_feats['Period'] == 'treatment']
            fb_ext = []
            for ft in feats[:10]:
                try:
                    if ft in bl_ext.columns and ft in tr_ext.columns:
                        br = bl_ext[bl_ext[ft] == 1]['has_purchase'].mean()
                        tr_r = tr_ext[tr_ext[ft] == 1]['has_purchase'].mean()
                        if pd.notna(br) and pd.notna(tr_r):
                            fb_ext.append({'feature': ft, 'did_estimate': float(tr_r - br), 'p_value': None, 'method': 'Simple Difference'})
                except:
                    continue
            if fb_ext:
                fb_ext.sort(key=lambda x: x['did_estimate'], reverse=(direction == 'positive'))
                ext_drivers = fb_ext[:3]

        # Compute descriptive stats
        bl_buyers = dept_int[dept_int['Period'] == 'baseline']
        tr_buyers = dept_int[dept_int['Period'] == 'treatment']
        bl_ext_d = dept_ext[dept_ext['Period'] == 'baseline']
        tr_ext_d = dept_ext[dept_ext['Period'] == 'treatment']

        dept_reports.append({
            'department': dept,
            'anomaly_score': float(anom_val),
            'baseline_avg_revenue': float(bl_buyers['Total_Revenue'].mean()) if len(bl_buyers) > 0 else 0.0,
            'treatment_avg_revenue': float(tr_buyers['Total_Revenue'].mean()) if len(tr_buyers) > 0 else 0.0,
            'n_buyers_baseline': int(len(bl_buyers)),
            'n_buyers_treatment': int(len(tr_buyers)),
            'baseline_order_rate': float(bl_ext_d['Has_Order'].mean()) if len(bl_ext_d) > 0 else 0.0,
            'treatment_order_rate': float(tr_ext_d['Has_Order'].mean()) if len(tr_ext_d) > 0 else 0.0,
            'n_eligible': int(len(all_custs)),
            'intensive_margin': int_drivers,
            'extensive_margin': ext_drivers,
        })
        print(f"    → {len(int_drivers)} intensive, {len(ext_drivers)} extensive drivers")

    return dept_reports, ext_panel

# Merge intensive data with features for analysis
int_with_feats = pd.read_csv(f'{RESULTS_DIR}/customer_dept_period_intensive.csv')
int_with_feats = int_with_feats.merge(demo_eng, on='CustomerID', how='inner')
print(f"Intensive panel with features: {int_with_feats.shape}")

print("\nAnalyzing surge departments...")
surge_report, surge_ext = run_did_per_dept(
    surge_dept_names, int_with_feats, agg_revenue, demo_eng,
    binary_feat_list, did_intensive, did_extensive, direction='positive'
)

print("\nAnalyzing slump departments...")
slump_report, slump_ext = run_did_per_dept(
    slump_dept_names, int_with_feats, agg_revenue, demo_eng,
    binary_feat_list, did_intensive, did_extensive, direction='negative'
)

# Save extensive output
ext_combined = pd.concat([surge_ext, slump_ext], ignore_index=True)
ext_combined.to_csv(f'{RESULTS_DIR}/customer_dept_period_extensive.csv', index=False)
print(f"\n✓ Extensive data saved: {len(ext_combined)} rows")

# Build final report
n_int_surge = sum(len(r['intensive_margin']) for r in surge_report)
n_ext_surge = sum(len(r['extensive_margin']) for r in surge_report)
n_int_slump = sum(len(r['intensive_margin']) for r in slump_report)
n_ext_slump = sum(len(r['extensive_margin']) for r in slump_report)

# Sort: surge descending by score, slump ascending
surge_report.sort(key=lambda x: x['anomaly_score'], reverse=True)
slump_report.sort(key=lambda x: x['anomaly_score'])

final_report = {
    "metadata": {
        "baseline_start": "09-01-2020",
        "baseline_end": "10-31-2020",
        "treatment_start": "11-01-2020",
        "treatment_end": "11-30-2020",
        "total_features_analyzed": len([c for c in demo_eng.columns if c != 'CustomerID'])
    },
    "surge_departments": surge_report,
    "slump_departments": slump_report,
    "summary": {
        "surge": {
            "total_departments": len(surge_report),
            "total_intensive_drivers": n_int_surge,
            "total_extensive_drivers": n_ext_surge
        },
        "slump": {
            "total_departments": len(slump_report),
            "total_intensive_drivers": n_int_slump,
            "total_extensive_drivers": n_ext_slump
        }
    }
}

with open(f'{RESULTS_DIR}/did_results.json', 'w') as fout:
    json.dump(final_report, fout, indent=2)

print(f"\n✓ DiD report saved: {RESULTS_DIR}/did_results.json")
print(f"  Surge: {final_report['summary']['surge']}")
print(f"  Slump: {final_report['summary']['slump']}")

print("\n" + "=" * 70)
print("PIPELINE FINISHED SUCCESSFULLY")
print("=" * 70)
print(f"\nOutputs in {RESULTS_DIR}:")
for fname in ["demographics_cleaned.csv", "grocery_orders_filtered.csv",
              "department_anomaly_scores.csv", "demographics_features.csv",
              "customer_dept_period_intensive.csv", "customer_dept_period_extensive.csv",
              "did_results.json"]:
    print(f"  - {fname}")

PYEOF

echo "=== solve.sh completed successfully ==="
