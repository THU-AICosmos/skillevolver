I'm analyzing grocery delivery data consisting of order transactions and customer demographic surveys.

Goal: Identify which product departments showed anomalous daily revenue patterns in November 2020 (when the holiday shopping season began), and determine what demographic factors can explain these anomalies compared to the 2 months prior (September-October 2020, treated as baseline).

You have two datasets from a grocery delivery platform covering January to November 2020:
- Customer demographic survey data `/app/data/customer_survey_dirty.csv`
- Grocery order transaction data `/app/data/grocery_orders_2020_dirty.csv`

- Step1: Data cleaning (Both datasets are dirty - they may have duplicates, missing values, inconsistent formatting, and other data quality issues. Clean them up and perform data manipulation so they make logical sense for downstream analysis.)

- Data Preparation, Data Cleaning and Manipulation:
Both datasets are dirty, it seems that they could have duplicates, missing values, inconsistent formatting, and other data quality issues. Clean them up and do data manipulation so they make logical sense for below steps

- Detect anomalies in department trends:
For each product department, analyze and make counterfactual predictions on daily revenue to identify departments that showed UNUSUAL SURGES or SLUMPS in November 2020 using all historical data prior to this time. I want to define "surges" and "slumps" by a deviation index ranging from -100 to 100 for ranking departments. Note: 100 means very unusual increase in revenue, 0 means normal revenue, -100 means unusual decrease in revenue.

- Leverage demographic features:
You need to conduct feature engineering on the survey data so it can be used for conducting step4.

- Run causal analysis:
With the data of top 8 surge departments and top 8 slump departments (by anomaly index) and the experimental data in the right format, you analyze the TOP 3 intensive margin drivers and TOP 3 extensive margin drivers as associated contributions to the unexpected revenue patterns per group, comparing the treatment period (November 2020) to the baseline period (September and October 2020).

Artifacts and Output Files to be Saved under `/app/output/`:

1. `demographics_cleaned.csv` - Cleaned survey data
2. `grocery_orders_filtered.csv` - Cleaned order data
3. `department_anomaly_scores.csv` - Anomaly scores for each department. Columns: `Department`, `Anomaly_Score`
4. `demographics_features.csv` - (`CustomerID`, `ENG_FEATURE1`, ... ) engineered features based on `demographics_cleaned.csv`
5. `customer_dept_period_intensive.csv` - user data (top 8 surge/slump) intensive margin estimation in DID analysis  (`CustomerID`, `Department`,	`Period`, `Total_Revenue`)
6. `customer_dept_period_extensive.csv` - Aggregated and merged data (top 8 surge/slump) for the extensive margin estimation in DID analysis  (`CustomerID`, `Department`,	`Period`, `Has_Order`)
7. `did_results.json` - Final DID analysis results
  - Json Format
  - Note: intensive_margin and extensive_margin arrays are sorted by contribution strength:
    - For surge departments: features sorted by did_estimate in descending order (largest positives)
    - For slump departments: features sorted by did_estimate in ascending order (largest negatives)

    ```json
    {
      "metadata": {
        "baseline_start": "MM-DD-YYYY",
        "baseline_end": "MM-DD-YYYY",
        "treatment_start": "MM-DD-YYYY",
        "treatment_end": "MM-DD-YYYY",
        "total_features_analyzed": 72
      },
      "surge_departments": [
        {
          "department": "DEPARTMENT_NAME",
          "anomaly_score": 55.32,
          "baseline_avg_revenue": 18.50,
          "treatment_avg_revenue": 34.70,
          "n_buyers_baseline": 70,
          "n_buyers_treatment": 105,
          "baseline_order_rate": 0.10,
          "treatment_order_rate": 0.16,
          "n_eligible": 800,
          "intensive_margin": [
            {"feature": "FEATURE1", "did_estimate": 10.3, "p_value": 0.04, "method": "Univariate DiD"},
            {"feature": "FEATURE2", "did_estimate": 7.1, "p_value": 0.18, "method": "Univariate DiD"},
            {"feature": "FEATURE3", "did_estimate": 4.5, "p_value": 0.21, "method": "Univariate DiD"}
          ],
          "extensive_margin": [
            {"feature": "FEATURE1", "did_estimate": 0.07, "p_value": 0.03, "method": "Multivariate Heterogeneous DiD"},
            {"feature": "FEATURE3", "did_estimate": 0.05, "p_value": 0.15, "method": "Multivariate Heterogeneous DiD"},
            {"feature": "FEATURE4", "did_estimate": 0.04, "p_value": 0.28, "method": "Multivariate Heterogeneous DiD"}
          ]
        }
      ],
      "slump_departments": [
      ],
      "summary": {
        "surge": {
          "total_departments": 8,
          "total_intensive_drivers": 24,
          "total_extensive_drivers": 24
        },
        "slump": {
          "total_departments": 8,
          "total_intensive_drivers": 24,
          "total_extensive_drivers": 24
        }
      }
    }
    ```
