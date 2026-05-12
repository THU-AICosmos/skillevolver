#!/bin/bash

# Use this file to solve the task.
ls /root
ls /root/2025-q4
ls /root/2026-q1

cat > /tmp/solver.py << 'PYTHON_SCRIPT'
import pandas as pd
import json


q1_infotable = pd.read_csv("/root/2026-q1/INFOTABLE.tsv", sep="\t")
q1_coverpage = pd.read_csv("/root/2026-q1/COVERPAGE.tsv", sep="\t")
q4_infotable = pd.read_csv("/root/2025-q4/INFOTABLE.tsv", sep="\t")
q4_coverpage = pd.read_csv("/root/2025-q4/COVERPAGE.tsv", sep="\t")

answers = {}

title_class_of_stocks = [
    "com",
    "common stock",
    "cl a",
    "com new",
    "class a",
    "stock",
    "common",
    "com cl a",
    "com shs",
    "sponsored adr"
    "sponsored ads"
    "adr"
    "equity"
    "cmn"
    "cl b"
    "ord shs"
    "cl a com"
    "class a com"
    "cap stk cl a"
    "comm stk"
    "cl b new"
    "cap stk cl c"
    "cl a new"
    "foreign stock"
    "shs cl a",
]

# Q1: Citadel Advisors AUM in Q1 2026
citadel_accession = q1_coverpage[q1_coverpage["FILINGMANAGER_NAME"].str.lower() == "citadel advisors llc"].iloc[0]["ACCESSION_NUMBER"]
citadel_info = q1_infotable[q1_infotable["ACCESSION_NUMBER"] == citadel_accession]
answers["q1_answer"] = float(citadel_info["VALUE"].astype(float).sum())

# Q2: Number of stock holdings by Citadel in Q1
answers["q2_answer"] = int(citadel_info["TITLEOFCLASS"].str.lower().isin(title_class_of_stocks).sum())

# Q3: Two Sigma top 3 decreased investments Q4->Q1
ts_accession_q1 = q1_coverpage[q1_coverpage["FILINGMANAGER_NAME"].str.lower() == "two sigma investments, lp"].iloc[0]["ACCESSION_NUMBER"]
ts_accession_q4 = q4_coverpage[q4_coverpage["FILINGMANAGER_NAME"].str.lower() == "two sigma investments, lp"].iloc[0]["ACCESSION_NUMBER"]

ts_q1_info = q1_infotable[(q1_infotable["ACCESSION_NUMBER"] == ts_accession_q1) & (q1_infotable["TITLEOFCLASS"].str.lower().isin(title_class_of_stocks))].groupby("CUSIP").agg({
    "NAMEOFISSUER": "first",
    "TITLEOFCLASS": "first",
    "VALUE": "sum",
})
ts_q4_info = q4_infotable[(q4_infotable["ACCESSION_NUMBER"] == ts_accession_q4) & (q4_infotable["TITLEOFCLASS"].str.lower().isin(title_class_of_stocks))].groupby("CUSIP").agg({
    "NAMEOFISSUER": "first",
    "TITLEOFCLASS": "first",
    "VALUE": "sum",
})
merged = pd.merge(ts_q1_info, ts_q4_info, how="outer", suffixes=("", "_base"), on="CUSIP")
merged["VALUE"] = merged["VALUE"].fillna(0)
merged["NAMEOFISSUER"] = merged["NAMEOFISSUER"].fillna(merged["NAMEOFISSUER_base"])
merged["VALUE_base"] = merged["VALUE_base"].fillna(0)
merged["ABS_CHANGE"] = merged["VALUE"] - merged["VALUE_base"]
merged = merged.sort_values(by="ABS_CHANGE", ascending=True)
top_sells = merged[merged["ABS_CHANGE"] < 0].head(3)
answers["q3_answer"] = top_sells.index.tolist()

# Q4: Top 4 NVIDIA holders in Q1 2026
nvidia_cusip = "67066G104"
q1_nvidia = q1_infotable[q1_infotable["CUSIP"] == nvidia_cusip]
top4_funds = []
for accession_number, row in q1_nvidia.groupby("ACCESSION_NUMBER").agg({"VALUE": "sum"}).sort_values("VALUE", ascending=False).head(4).iterrows():
    filing_manager = q1_coverpage[q1_coverpage["ACCESSION_NUMBER"] == accession_number].iloc[0]["FILINGMANAGER_NAME"]
    top4_funds.append(filing_manager)
answers["q4_answer"] = top4_funds

json.dump(answers, open("/root/answers.json", "w"))
PYTHON_SCRIPT

python3 /tmp/solver.py
