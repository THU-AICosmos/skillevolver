You need to analyze the following files to find any potential expense report fraud:
- `/root/invoices.pdf`: One expense report per page.
- `/root/vendors.xlsx`: Approved employees with corresponding Employee ID, Name, and authorized bank Account number.
- `/root/purchase_orders.csv`: Valid travel authorizations with corresponding TA Number, Budget, and Employee ID.

An expense report is considered fraudulent if it meets ANY of the following criteria:
- Unknown Vendor: The employee name doesn't exist in `vendors.xlsx`. Employee names can have minor typos or variations, such as "Inc" vs. "Inc.". To handle this, you can use fuzzy matching.
- IBAN Mismatch: The employee exists, but the expense report's bank account doesn't match the one of the employee.
- Invalid PO: The TA number doesn't exist in `purchase_orders.csv`.
- Amount Mismatch: The TA exists, but the budget doesn't match the claimed amount on the expense report, which exceeds a 0.01 difference.
- Vendor Mismatch: The TA is valid, but it is linked to a different Employee ID than the one on the expense report.

Save the findings to `/root/fraud_report.json`. Only include flagged expense reports. Use 1-based page indexing. If the TA number is missing, set it to `null`. Set the reason to one of the above criteria. If multiple apply, pick the first one in the order listed above.

Required JSON structure:
```json
[
  {
    "invoice_page_number": 1,
    "vendor_name": "John Doe",
    "invoice_amount": 5000.00,
    "iban": "ACCT123456",
    "po_number": "TA-2001",
    "reason": "IBAN Mismatch"
  },
  {
    "invoice_page_number": 3,
    "vendor_name": "Unknown Person",
    "invoice_amount": 1000.00,
    "iban": "ACCTXX0000",
    "po_number": null,
    "reason": "Unknown Vendor"
  }
]
```
