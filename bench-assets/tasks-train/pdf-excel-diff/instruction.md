You are helping a warehouse manager identify discrepancies between an archived product catalog and the current inventory database. The warehouse previously exported its full inventory as a PDF file (`/root/inventory_archive.pdf`). Since then, various updates were made to the current Excel inventory (`/root/inventory_current.xlsx`), but no changelog was kept.

Your task is to:

1. Extract the product table from the archived PDF file.
2. Compare it with the current Excel inventory file.
3. Identify: (1) which products (by Code) were removed from the inventory, and (2) which product records were modified (include the product Code, the field that changed, and both the old and new values).

Write the results to `/root/inventory_diff.json` in the following format:
```json
{
  "deleted_products": ["PROD0101", "PROD0250"],
  "modified_products": [
    {
      "id": "PROD0300",
      "field": "UnitPrice",
      "old_value": 29.99,
      "new_value": 34.99
    }
  ]
}
```

Notes:
- The PDF contains the original (older) version of the data.
- The Excel file contains the current (newer) version of the data.
- Product codes are in the format "PROD0001", "PROD0002", etc. (4 digits)
- For numeric fields (UnitPrice, Quantity), output values as numbers (UnitPrice as float, Quantity as integer)
- For text fields (ProductName, Category, Warehouse), output values as strings
- Sort `deleted_products` and `modified_products` by Code for consistency
