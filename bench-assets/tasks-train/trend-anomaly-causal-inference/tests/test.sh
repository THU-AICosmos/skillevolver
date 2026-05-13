#!/bin/bash

# Test runner for grocery delivery department trend analysis (training variant)

echo "=== Installing test dependencies ==="
pip install --quiet pytest==8.4.1 pytest-json-ctrf==0.3.5 pytest-json-report==1.5.0

echo "=== Running tests ==="
pytest /tests/test_outputs.py \
    --ctrf /logs/verifier/ctrf.json \
    --json-report \
    --json-report-file=/logs/verifier/report.json \
    -rA \
    -v \
    --tb=short

# Calculate weighted reward based on test priorities
python3 << 'EOF'
import json
import sys

P0_TESTS = [
    "test_cleaned_data[file_config0]",
    "test_cleaned_data[file_config1]",
    "test_anomaly_detection",
    "test_feature_engineering",
    "test_customer_dept_period_aggregated",
    "test_did_report_structure[metadata-keys0]",
    "test_did_report_structure[surge_departments-None]",
    "test_did_report_structure[slump_departments-None]",
    "test_did_report_structure[summary-keys3]",
]

P1_TESTS = [
    "test_demographics_cleaning_correctness",
    "test_order_cleaning_correctness",
    "test_anomaly_detection_correctness",
    "test_feature_engineering_correctness",
    "test_did_baseline_period",
    "test_did_report_departments",
    "test_did_report_correctness",
]

P2_TESTS = [
    "test_cross_file_consistency",
    "test_order_aggregation_correctness",
    "test_did_aggregation_independence",
]

try:
    with open('/logs/verifier/report.json', 'r') as f:
        report = json.load(f)

    passed_tests = set()
    for test in report.get('tests', []):
        if test.get('outcome') == 'passed':
            nodeid = test.get('nodeid', '')
            test_name = nodeid.split('::')[-1] if '::' in nodeid else nodeid.split('/')[-1]
            passed_tests.add(test_name)

    p0_passed = sum(1 for t in P0_TESTS if t in passed_tests)
    p1_passed = sum(1 for t in P1_TESTS if t in passed_tests)
    p2_passed = sum(1 for t in P2_TESTS if t in passed_tests)

    score = (p0_passed / len(P0_TESTS) * 0.50) + \
            (p1_passed / len(P1_TESTS) * 0.35) + \
            (p2_passed / len(P2_TESTS) * 0.15)

    with open('/logs/verifier/reward.txt', 'w') as f:
        f.write(f"{score:.4f}\n")

    print(f"P0: {p0_passed}/{len(P0_TESTS)} (50%), P1: {p1_passed}/{len(P1_TESTS)} (35%), P2: {p2_passed}/{len(P2_TESTS)} (15%)")
    print(f"=== Tests completed with reward: {score:.4f} ===")

except Exception as e:
    print(f"Error calculating reward: {e}", file=sys.stderr)
    with open('/logs/verifier/reward.txt', 'w') as f:
        f.write("0.0\n")
    sys.exit(1)
EOF

echo "=== Keeping container alive for inspection ==="
echo "Container will sleep for 10 minutes. Press Ctrl+C to exit."
exit 0
