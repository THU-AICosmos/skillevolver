"""
Test suite for grocery delivery department trend analysis (training variant).

Priority Tiers:
- P0 (50%): Core functionality - files exist, basic structure correct
- P1 (35%): Quality & methodology - cleaning quality, statistical validity
- P2 (15%): Advanced requirements - robustness, edge cases
"""

import json
import os
import pytest
import pandas as pd

RESULTS_DIR = os.environ.get("OUTPUT_DIR", "/app/output")


def read_csv(fname: str) -> pd.DataFrame:
    fpath = os.path.join(RESULTS_DIR, fname)
    assert os.path.exists(fpath), f"Required output file not found: {fname}"
    return pd.read_csv(fpath)


def read_json(fname: str) -> dict:
    fpath = os.path.join(RESULTS_DIR, fname)
    assert os.path.exists(fpath), f"Required output file not found: {fname}"
    with open(fpath, 'r') as f:
        return json.load(f)


@pytest.mark.p0
@pytest.mark.parametrize("file_config", [
    {
        "filename": "demographics_cleaned.csv",
        "required_columns": ["CustomerID"],
        "min_rows": 3500,
        "unique_key": "CustomerID"
    },
    {
        "filename": "grocery_orders_filtered.csv",
        "required_columns": ["CustomerID", "Order Date", "Department"],
        "min_rows": 50000,
        "unique_key": None,
        "price_column_aliases": [
            "Unit Price", "unit_price", "UnitPrice",
            "Price", "price", "Item Total", "item_total"
        ]
    }
])
def test_cleaned_data(file_config):
    """Verify data cleaning produces valid datasets with required structure."""
    df = read_csv(file_config["filename"])

    for col in file_config["required_columns"]:
        assert col in df.columns, f"{file_config['filename']}: Missing column '{col}'"

    if "price_column_aliases" in file_config:
        price_col = None
        for alias in file_config["price_column_aliases"]:
            if alias in df.columns:
                price_col = alias
                break
        assert price_col is not None, \
            f"{file_config['filename']}: Missing price column (expected one of: {file_config['price_column_aliases']})"

    assert len(df) >= file_config["min_rows"], \
        f"{file_config['filename']}: Expected ≥{file_config['min_rows']} rows, got {len(df)}"

    if file_config["unique_key"]:
        n_unique = df[file_config["unique_key"]].nunique()
        assert n_unique == len(df), \
            f"{file_config['filename']}: Found {len(df) - n_unique} duplicate {file_config['unique_key']} values"


@pytest.mark.p1
def test_demographics_cleaning_correctness():
    """Verify demographics cleaning actually removed issues."""
    df = read_csv("demographics_cleaned.csv")

    assert df.duplicated().sum() == 0, "Found duplicate rows after cleaning"
    assert df["CustomerID"].notna().all(), "Found null CustomerID"
    assert df["CustomerID"].str.startswith("C_").all(), "CustomerID should start with 'C_'"

    demo_cols = ["D-age-bracket", "D-gender", "D-education", "D-income-level", "D-region"]
    for col in demo_cols:
        if col in df.columns:
            missing = df[col].isna().sum()
            assert missing == 0, f"Column '{col}' has {missing} missing values after cleaning"

    assert 3500 <= len(df) <= 5000, f"Expected 3500-5000 rows after cleaning, got {len(df)}"


@pytest.mark.p1
def test_order_cleaning_correctness():
    """Verify order data cleaning removed issues."""
    df = read_csv("grocery_orders_filtered.csv")

    df["Order Date"] = pd.to_datetime(df["Order Date"], errors='coerce')
    assert df["Order Date"].notna().all(), "Found unparseable dates"
    assert df["Order Date"].min() >= pd.Timestamp("2020-01-01"), \
        f"Found dates before 2020: {df['Order Date'].min()}"
    assert df["Order Date"].max() <= pd.Timestamp("2020-12-31"), \
        f"Found dates after 2020: {df['Order Date'].max()}"

    assert df["Department"].isna().sum() == 0, "Found missing Department after cleaning"
    assert df["CustomerID"].notna().all(), "Found null CustomerID"

    assert 150000 <= len(df) <= 350000, \
        f"Expected 150k-350k rows after cleaning, got {len(df)}"


@pytest.mark.p0
def test_anomaly_detection():
    """Verify anomaly detection produces valid scores in [-100, 100]."""
    df = read_csv("department_anomaly_scores.csv")

    assert "Department" in df.columns, "Missing 'Department' column"
    score_aliases = ["Anomaly_Score", "Anomaly Score", "anomaly_score", "Anomaly_Index", "anomaly_index"]
    score_col = None
    for alias in score_aliases:
        if alias in df.columns:
            score_col = alias
            break
    assert score_col is not None, f"Missing anomaly score column (expected one of: {score_aliases})"

    assert df[score_col].min() >= -100, f"Score below -100: {df[score_col].min()}"
    assert df[score_col].max() <= 100, f"Score above 100: {df[score_col].max()}"
    assert (df[score_col] > 0).any(), "No surge departments detected"
    assert (df[score_col] < 0).any(), "No slump departments detected"
    assert len(df) >= 10, f"Need ≥10 departments for top-8 analysis, got {len(df)}"


@pytest.mark.p1
def test_anomaly_detection_correctness():
    """Verify anomaly results are statistically meaningful."""
    anomaly = read_csv("department_anomaly_scores.csv")
    orders = read_csv("grocery_orders_filtered.csv")

    score_aliases = ["Anomaly_Score", "Anomaly Score", "anomaly_score", "Anomaly_Index", "anomaly_index"]
    score_col = next((c for c in score_aliases if c in anomaly.columns), None)
    assert score_col is not None

    order_depts = set(orders["Department"].unique())
    anomaly_depts = set(anomaly["Department"].unique())
    invalid = anomaly_depts - order_depts
    assert len(invalid) == 0, f"Anomaly contains {len(invalid)} departments not in orders"

    orders["Order Date"] = pd.to_datetime(orders["Order Date"])
    assert orders["Order Date"].min() <= pd.Timestamp("2020-01-15")
    assert orders["Order Date"].max() >= pd.Timestamp("2020-11-15")

    assert len(anomaly) >= 16, f"Need ≥16 departments for top-8 analysis, got {len(anomaly)}"

    anomaly_sorted = anomaly.sort_values(score_col, ascending=False)
    assert anomaly[score_col].tolist() == anomaly_sorted[score_col].tolist(), \
        "department_anomaly_scores.csv must be sorted by score descending"

    extreme = (anomaly[score_col].abs() > 80).sum()
    assert extreme <= len(anomaly) * 0.3, f"Too many extreme scores ({extreme}/{len(anomaly)})"

    surge_depts = anomaly[anomaly[score_col] > 0]
    slump_depts = anomaly[anomaly[score_col] < 0]
    assert len(surge_depts) >= 8, f"Only {len(surge_depts)} surge departments"
    assert len(slump_depts) >= 8, f"Only {len(slump_depts)} slump departments"

    std_score = anomaly[score_col].std()
    assert std_score > 5, f"Score spread too low (std={std_score:.2f})"

    top_surge_mean = anomaly.nlargest(8, score_col)[score_col].mean()
    top_slump_mean = anomaly.nsmallest(8, score_col)[score_col].mean()
    gap = top_surge_mean - top_slump_mean
    assert gap > 10, f"Surge/slump poorly separated (gap={gap:.2f})"

    p75 = anomaly[score_col].quantile(0.75)
    p25 = anomaly[score_col].quantile(0.25)
    top_surge_min = anomaly.nlargest(8, score_col)[score_col].min()
    top_slump_max = anomaly.nsmallest(8, score_col)[score_col].max()
    assert top_surge_min > p75, f"Top 8 surge not in upper tail (min={top_surge_min:.2f}, p75={p75:.2f})"
    assert top_slump_max < p25, f"Top 8 slump not in lower tail (max={top_slump_max:.2f}, p25={p25:.2f})"


@pytest.mark.p0
def test_feature_engineering():
    """Verify feature engineering produces numeric features."""
    df = read_csv("demographics_features.csv")

    assert "CustomerID" in df.columns, "Missing 'CustomerID'"
    n_feats = len(df.columns) - 1
    assert n_feats >= 15, f"Expected ≥15 features, got {n_feats}"

    feat_cols = [c for c in df.columns if c != "CustomerID"]
    for col in feat_cols:
        assert pd.api.types.is_numeric_dtype(df[col]), \
            f"Feature '{col}' is not numeric (dtype: {df[col].dtype})"


@pytest.mark.p1
def test_feature_engineering_correctness():
    """Verify feature values are reasonable."""
    fe_df = read_csv("demographics_features.csv")
    demo_df = read_csv("demographics_cleaned.csv")

    assert len(fe_df) == len(demo_df), \
        f"Feature data has {len(fe_df)} rows, demographics has {len(demo_df)}"

    feat_cols = [c for c in fe_df.columns if c != "CustomerID"]

    for col in feat_cols:
        assert fe_df[col].nunique() > 1, f"Feature '{col}' is constant"

    for col in feat_cols:
        if fe_df[col].isna().all():
            continue
        assert not fe_df[col].isin([float('inf'), float('-inf')]).any(), \
            f"Feature '{col}' has infinite values"
        col_std = fe_df[col].std()
        if col_std > 0:
            col_mean = fe_df[col].mean()
            outliers = ((fe_df[col] - col_mean).abs() > 10 * col_std).sum()
            assert outliers < len(fe_df) * 0.01, f"Feature '{col}' has {outliers} extreme outliers"

    non_zero_var = sum(fe_df[col].std() > 0.01 for col in feat_cols)
    assert non_zero_var >= len(feat_cols) * 0.95, \
        f"Only {non_zero_var}/{len(feat_cols)} features have meaningful variance"


@pytest.mark.p0
def test_customer_dept_period_aggregated():
    """Verify aggregated data has correct structure for DID analysis."""
    intensive = read_csv("customer_dept_period_intensive.csv")

    def find_col(df, aliases):
        for a in aliases:
            if a in df.columns:
                return a
        return None

    id_col = find_col(intensive, ["CustomerID", "customerid", "customer_id"])
    dept_col = find_col(intensive, ["Department", "department"])
    period_col = find_col(intensive, ["Period", "period"])
    rev_col = find_col(intensive, ["Total_Revenue", "total_revenue", "Total_Spend", "total_spend"])

    assert id_col, "Missing CustomerID in intensive"
    assert dept_col, "Missing Department in intensive"
    assert period_col, "Missing Period in intensive"
    assert rev_col, "Missing revenue column in intensive"

    assert intensive[id_col].notna().all(), "Null CustomerID in intensive"
    assert intensive[dept_col].notna().all(), "Null Department in intensive"
    assert intensive[period_col].notna().all(), "Null Period in intensive"

    valid_periods = {"baseline", "treatment", "Baseline", "Treatment"}
    assert set(intensive[period_col].unique()).issubset(valid_periods), \
        f"Invalid periods in intensive: {set(intensive[period_col].unique()) - valid_periods}"

    assert (intensive[rev_col] > 0).all(), "Non-positive revenue in intensive"

    dups = intensive.groupby([id_col, dept_col, period_col]).size()
    assert (dups > 1).sum() == 0, "Duplicate customer-dept-period in intensive"

    extensive = read_csv("customer_dept_period_extensive.csv")

    ext_id = find_col(extensive, ["CustomerID", "customerid", "customer_id"])
    ext_dept = find_col(extensive, ["Department", "department"])
    ext_period = find_col(extensive, ["Period", "period"])
    has_order_col = find_col(extensive, ["Has_Order", "has_order", "Has_Purchase", "has_purchase"])

    assert ext_id, "Missing CustomerID in extensive"
    assert ext_dept, "Missing Department in extensive"
    assert ext_period, "Missing Period in extensive"
    assert has_order_col, "Missing Has_Order in extensive"

    assert extensive[ext_id].notna().all()
    assert extensive[ext_dept].notna().all()
    assert extensive[ext_period].notna().all()

    assert set(extensive[ext_period].unique()).issubset(valid_periods)
    assert set(extensive[has_order_col].unique()).issubset({0, 1})

    ext_dups = extensive.groupby([ext_id, ext_dept, ext_period]).size()
    assert (ext_dups > 1).sum() == 0, "Duplicate customer-dept-period in extensive"
    assert len(extensive) >= len(intensive), "Extensive should have >= rows than intensive"


@pytest.mark.p0
@pytest.mark.parametrize("section,keys", [
    ("metadata", ["baseline_start", "baseline_end", "treatment_start", "treatment_end", "total_features_analyzed"]),
    ("surge_departments", None),
    ("slump_departments", None),
    ("summary", ["surge", "slump"])
])
def test_did_report_structure(section, keys):
    """Verify DID report has complete structure."""
    report = read_json("did_results.json")

    assert section in report, f"Missing section '{section}'"

    if keys:
        for key in keys:
            assert key in report[section], f"Missing key '{key}' in '{section}'"

            if section == "metadata":
                if key in ["baseline_start", "baseline_end", "treatment_start", "treatment_end"]:
                    val = report[section][key]
                    assert isinstance(val, str)
                    try:
                        pd.to_datetime(val)
                    except:
                        raise AssertionError(f"metadata.{key} = '{val}' is not a valid date")
                elif key == "total_features_analyzed":
                    assert isinstance(report[section][key], int)
                    assert report[section][key] > 0

            if section == "summary" and key in ["surge", "slump"]:
                for nested in ["total_departments", "total_intensive_drivers", "total_extensive_drivers"]:
                    assert nested in report[section][key], f"Missing '{nested}' in summary.{key}"


@pytest.mark.p1
def test_did_baseline_period():
    """Verify DID uses correct baseline period (Sep-Oct 2020)."""
    report = read_json("did_results.json")
    meta = report["metadata"]

    assert "2020" in meta["baseline_start"], f"Baseline should be 2020, got: {meta['baseline_start']}"
    assert "2020" in meta["baseline_end"]
    assert ("09" in meta["baseline_start"] or "9-" in meta["baseline_start"]), \
        f"Baseline should start in Sep 2020, got: {meta['baseline_start']}"
    assert ("10" in meta["baseline_end"]), f"Baseline should end in Oct 2020, got: {meta['baseline_end']}"
    assert ("11" in meta["treatment_start"] or "Nov" in meta["treatment_start"]), \
        f"Treatment should be Nov 2020, got: {meta['treatment_start']}"


@pytest.mark.p1
def test_did_report_departments():
    """Verify top-8 surge/slump departments are identified with DID results."""
    report = read_json("did_results.json")

    surge = report["surge_departments"]
    slump = report["slump_departments"]

    assert len(surge) == 8, f"Expected 8 surge departments, got {len(surge)}"
    assert len(slump) == 8, f"Expected 8 slump departments, got {len(slump)}"

    for i, dept in enumerate(surge + slump):
        label = "surge" if i < 8 else "slump"
        assert "department" in dept, f"{label}[{i%8}]: Missing 'department'"
        assert "anomaly_score" in dept, f"{label}[{i%8}]: Missing 'anomaly_score'"
        assert "baseline_avg_revenue" in dept, f"{label}[{i%8}]: Missing 'baseline_avg_revenue'"
        assert "treatment_avg_revenue" in dept, f"{label}[{i%8}]: Missing 'treatment_avg_revenue'"
        assert "n_buyers_baseline" in dept, f"{label}[{i%8}]: Missing 'n_buyers_baseline'"
        assert "n_buyers_treatment" in dept, f"{label}[{i%8}]: Missing 'n_buyers_treatment'"
        assert "baseline_order_rate" in dept, f"{label}[{i%8}]: Missing 'baseline_order_rate'"
        assert "treatment_order_rate" in dept, f"{label}[{i%8}]: Missing 'treatment_order_rate'"
        assert "n_eligible" in dept, f"{label}[{i%8}]: Missing 'n_eligible'"

        assert dept["baseline_avg_revenue"] >= 0
        assert dept["treatment_avg_revenue"] >= 0
        assert dept["n_buyers_baseline"] >= 0
        assert dept["n_buyers_treatment"] >= 0
        assert 0 <= dept["baseline_order_rate"] <= 1
        assert 0 <= dept["treatment_order_rate"] <= 1
        assert dept["n_eligible"] > 0

        assert "intensive_margin" in dept or "extensive_margin" in dept, \
            f"{label}[{i%8}]: No DID results"


@pytest.mark.p1
def test_did_report_correctness():
    """Verify DID results have valid statistical properties."""
    report = read_json("did_results.json")

    all_depts = report["surge_departments"] + report["slump_departments"]

    cats_int = 0
    cats_ext = 0

    for dept in all_depts:
        name = dept["department"]

        if "intensive_margin" in dept:
            im = dept["intensive_margin"]
            assert isinstance(im, list)
            assert len(im) > 0, f"{name}: intensive_margin empty"
            assert len(im) <= 3, f"{name}: intensive_margin has {len(im)} drivers"
            for i, d in enumerate(im):
                assert "feature" in d
                assert "did_estimate" in d
                assert "method" in d
                assert "p_value" in d
                assert isinstance(d["did_estimate"], (int, float))
                assert d["p_value"] is None or isinstance(d["p_value"], (int, float))
                if d["p_value"] is not None:
                    assert 0 <= d["p_value"] <= 1
            cats_int += 1

        if "extensive_margin" in dept:
            em = dept["extensive_margin"]
            assert isinstance(em, list)
            assert len(em) > 0
            assert len(em) <= 3
            for i, d in enumerate(em):
                assert "feature" in d
                assert "did_estimate" in d
                assert "method" in d
                assert "p_value" in d
                assert isinstance(d["did_estimate"], (int, float))
                assert d["p_value"] is None or isinstance(d["p_value"], (int, float))
                if d["p_value"] is not None:
                    assert 0 <= d["p_value"] <= 1
            cats_ext += 1

    assert cats_int == 16, f"Only {cats_int}/16 departments have intensive_margin"
    assert cats_ext == 16, f"Only {cats_ext}/16 departments have extensive_margin"

    all_p, all_est = [], []
    for dept_list in [report["surge_departments"], report["slump_departments"]]:
        for dept in dept_list:
            for margin in ["intensive_margin", "extensive_margin"]:
                if margin in dept:
                    for d in dept[margin]:
                        if d.get("p_value") is not None:
                            all_p.append(d["p_value"])
                        all_est.append(d["did_estimate"])

    sig_count = sum(1 for p in all_p if p < 0.1)
    sig_rate = sig_count / len(all_p) if all_p else 0
    assert sig_rate >= 0.15, \
        f"Only {sig_count}/{len(all_p)} ({sig_rate:.1%}) significant (p<0.1), expected ≥15%"

    import numpy as np
    median_p = np.median(all_p) if all_p else 1.0
    assert 0.05 < median_p < 0.8, f"Suspicious p-value distribution (median={median_p:.3f})"

    pos_eff = sum(1 for e in all_est if e > 0)
    neg_eff = sum(1 for e in all_est if e < 0)
    assert pos_eff > 0 and neg_eff > 0, f"Effects lack variation: {pos_eff} pos, {neg_eff} neg"

    # Check sorting
    for dept in report["surge_departments"]:
        if "intensive_margin" in dept and len(dept["intensive_margin"]) > 1:
            est = [d["did_estimate"] for d in dept["intensive_margin"]]
            assert est == sorted(est, reverse=True), f"Surge {dept['department']}: intensive not sorted desc"
        if "extensive_margin" in dept and len(dept["extensive_margin"]) > 1:
            est = [d["did_estimate"] for d in dept["extensive_margin"]]
            assert est == sorted(est, reverse=True), f"Surge {dept['department']}: extensive not sorted desc"

    for dept in report["slump_departments"]:
        if "intensive_margin" in dept and len(dept["intensive_margin"]) > 1:
            est = [d["did_estimate"] for d in dept["intensive_margin"]]
            assert est == sorted(est), f"Slump {dept['department']}: intensive not sorted asc"
        if "extensive_margin" in dept and len(dept["extensive_margin"]) > 1:
            est = [d["did_estimate"] for d in dept["extensive_margin"]]
            assert est == sorted(est), f"Slump {dept['department']}: extensive not sorted asc"

    # Verify surge/slump match anomaly index
    anomaly_df = pd.read_csv(os.path.join(RESULTS_DIR, "department_anomaly_scores.csv"))
    score_aliases = ["Anomaly_Score", "Anomaly Score", "anomaly_score", "Anomaly_Index", "anomaly_index"]
    sc = next((c for c in score_aliases if c in anomaly_df.columns), None)

    top_8_surge = set(anomaly_df.nlargest(8, sc)["Department"].tolist())
    top_8_slump = set(anomaly_df.nsmallest(8, sc)["Department"].tolist())

    report_surge = set(d["department"] for d in report["surge_departments"])
    report_slump = set(d["department"] for d in report["slump_departments"])

    assert report_surge == top_8_surge, f"Surge mismatch. Expected: {top_8_surge}, Got: {report_surge}"
    assert report_slump == top_8_slump, f"Slump mismatch. Expected: {top_8_slump}, Got: {report_slump}"

    surge_scores = [d["anomaly_score"] for d in report["surge_departments"]]
    slump_scores = [d["anomaly_score"] for d in report["slump_departments"]]
    assert all(s > 0 for s in surge_scores), "Non-positive surge score"
    assert all(s < 0 for s in slump_scores), "Non-negative slump score"


@pytest.mark.p2
def test_cross_file_consistency():
    """Verify CustomerID consistency across outputs."""
    demo_clean = read_csv("demographics_cleaned.csv")
    demo_fe = read_csv("demographics_features.csv")
    intensive = read_csv("customer_dept_period_intensive.csv")
    extensive = read_csv("customer_dept_period_extensive.csv")

    clean_ids = set(demo_clean["CustomerID"])
    fe_ids = set(demo_fe["CustomerID"])
    assert clean_ids == fe_ids, f"ID mismatch: cleaned={len(clean_ids)}, features={len(fe_ids)}"

    int_ids = set(intensive["CustomerID"])
    invalid_int = int_ids - clean_ids
    assert len(invalid_int) == 0, f"Intensive has {len(invalid_int)} IDs not in cleaned demographics"

    ext_ids = set(extensive["CustomerID"])
    assert ext_ids == clean_ids, \
        f"Extensive should have all demo IDs. Missing: {len(clean_ids - ext_ids)}, Extra: {len(ext_ids - clean_ids)}"


@pytest.mark.p2
def test_order_aggregation_correctness():
    """Verify aggregated data correctly represents filtered transactions for top 16 departments."""
    orders = read_csv("grocery_orders_filtered.csv")
    intensive = read_csv("customer_dept_period_intensive.csv")
    demo_fe = read_csv("demographics_features.csv")
    anomaly = read_csv("department_anomaly_scores.csv")

    score_aliases = ["Anomaly_Score", "Anomaly Score", "anomaly_score", "Anomaly_Index", "anomaly_index"]
    sc = next((c for c in score_aliases if c in anomaly.columns), None)
    assert sc is not None

    sorted_anom = anomaly.sort_values(sc, ascending=False)
    top_surge = sorted_anom.head(8)['Department'].tolist()
    top_slump = sorted_anom.tail(8)['Department'].tolist()
    top_16 = set(top_surge + top_slump)

    orders["Order Date"] = pd.to_datetime(orders["Order Date"])
    orders['Period'] = pd.cut(
        orders['Order Date'],
        bins=[pd.Timestamp('2020-09-01'), pd.Timestamp('2020-10-31'), pd.Timestamp('2020-11-30')],
        labels=['baseline', 'treatment'],
        include_lowest=True
    )
    orders_period = orders.dropna(subset=['Period'])
    orders_period = orders_period[orders_period['Department'].isin(top_16)]
    orders_period['Total_Revenue'] = orders_period['Quantity'] * orders_period['Unit Price']

    manual = orders_period.groupby(['CustomerID', 'Department', 'Period'], observed=True).agg(
        {'Total_Revenue': 'sum'}).reset_index()
    manual_merged = manual.merge(demo_fe[['CustomerID']], on='CustomerID', how='inner')

    int_cats = set(intensive['Department'].unique())
    assert int_cats == top_16, f"Intensive should have top 16 departments. Found {len(int_cats)}"

    rev_col = "Total_Revenue" if "Total_Revenue" in intensive.columns else "Total_Spend"
    row_diff = abs(len(intensive) - len(manual_merged)) / len(manual_merged)
    assert row_diff < 0.05, \
        f"Intensive has {len(intensive)} rows, expected ~{len(manual_merged)} (±5%)"

    int_total = intensive[rev_col].sum()
    man_total = manual_merged['Total_Revenue'].sum()
    spend_diff = abs(int_total - man_total) / man_total if man_total > 0 else 0
    assert spend_diff < 0.10, \
        f"Revenue differs by {spend_diff:.1%}. Intensive: ${int_total:,.0f}, Manual: ${man_total:,.0f}"


@pytest.mark.p2
def test_did_aggregation_independence():
    """Verify DID data is aggregated to customer-department-period level."""
    intensive = read_csv("customer_dept_period_intensive.csv")
    extensive = read_csv("customer_dept_period_extensive.csv")
    orders = read_csv("grocery_orders_filtered.csv")
    demo_fe = read_csv("demographics_features.csv")

    rev_col = "Total_Revenue" if "Total_Revenue" in intensive.columns else "Total_Spend"
    assert rev_col in intensive.columns
    assert {"CustomerID", "Department", "Period"}.issubset(intensive.columns)

    has_col = "Has_Order" if "Has_Order" in extensive.columns else "Has_Purchase"
    assert has_col in extensive.columns
    assert {"CustomerID", "Department", "Period"}.issubset(extensive.columns)

    int_dups = intensive.groupby(['CustomerID', 'Department', 'Period']).size()
    assert (int_dups > 1).sum() == 0, "Duplicates in intensive"

    ext_dups = extensive.groupby(['CustomerID', 'Department', 'Period']).size()
    assert (ext_dups > 1).sum() == 0, "Duplicates in extensive"

    orders["Order Date"] = pd.to_datetime(orders["Order Date"])
    orders['Period'] = pd.cut(
        orders['Order Date'],
        bins=[pd.Timestamp('2020-09-01'), pd.Timestamp('2020-10-31'), pd.Timestamp('2020-11-30')],
        labels=['Baseline', 'Treatment'],
        include_lowest=True
    )
    txn_level = orders.dropna(subset=['Period'])
    txn_level['Total_Revenue'] = txn_level['Quantity'] * txn_level['Unit Price']

    survey_ids = set(demo_fe['CustomerID'])
    txn_level = txn_level[txn_level['CustomerID'].isin(survey_ids)]

    import random
    sample_n = min(20, len(intensive))
    sample_rows = intensive.sample(n=sample_n, random_state=42)

    for _, row in sample_rows.iterrows():
        cid = row["CustomerID"]
        dept = row["Department"]
        period = row["Period"]

        matching = txn_level[
            (txn_level["CustomerID"] == cid) &
            (txn_level["Department"] == dept) &
            (txn_level["Period"].str.lower() == period.lower())
        ]
        expected = matching['Total_Revenue'].sum()
        actual = row[rev_col]
        assert abs(actual - expected) < 0.01, \
            f"Aggregation error for {cid}, {dept}, {period}: expected {expected:.2f}, got {actual:.2f}"

    anomaly = read_csv("department_anomaly_scores.csv")
    score_aliases = ["Anomaly_Score", "Anomaly Score", "anomaly_score", "Anomaly_Index", "anomaly_index"]
    sc = next((c for c in score_aliases if c in anomaly.columns), None)
    sorted_a = anomaly.sort_values(sc, ascending=False)
    top_16 = set(sorted_a.head(8)['Department'].tolist() + sorted_a.tail(8)['Department'].tolist())

    txn_level = txn_level[txn_level['Department'].isin(top_16)]

    total_int = intensive[rev_col].sum()
    total_txn = txn_level['Total_Revenue'].sum()
    assert abs(total_int - total_txn) < 1.0, \
        f"Revenue not conserved (diff: ${abs(total_int - total_txn):,.2f})"
