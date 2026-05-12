You are a quantitative researcher at a hedge fund. Your task is to analyze hedge fund portfolio changes in Q1 2026 by comparing with Q4 2025. The dataset is downloaded to `/root/2025-q4` and `/root/2026-q1` folders respectively.

Questions to be answered in this task:

1. In Q1 2026, what's the total portfolio value (AUM) of Citadel Advisors, the hedge fund founded by Ken Griffin?

To answer this question, first you need to fuzzy search COVERPAGE using search term "citadel advisors" and find the best match. This gives you the accession_number.

Then, use this accession_number to obtain fund details including AUM.


2. How many stock positions does Citadel Advisors hold in Q1 2026?

Similar to question 1, you need to first obtain the accession_number and then analyze the fund details.


3. From Q4 2025 to Q1 2026, what are the top 3 stocks that received decreased investment by Two Sigma Investments, ranked by dollar value decrease (most decreased first)? Answer stock CUSIPs.

First, you need to obtain two accession numbers for Two Sigma Investments, one for Q4 and one for Q1 (accession numbers will change in reporting seasons). Next, you need to load the holdings in between two quarters and compare the change of holdings.

4. List top-4 fund managers (name) which have invested in NVIDIA in terms of share value in Q1 2026.

First, you need to search the CUSIP for NVIDIA and then find out the answer.


Format your answer to the above questions in json file called `answers.json` in `/root` folder, follow the file schema:
```json
{
    "q1_answer": number,
    "q2_answer": number,
    "q3_answer": ["stock_cusip1", "stock_cusip2", "stock_cusip3"],
    "q4_answer": ["fund1", "fund2", "fund3", "fund4"]
}
```
