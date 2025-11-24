# docs/EXCEL_IMPORT_EXPORT_GUIDE.md
# Excel Import/Export Guide

## Overview

Comprehensive bulk import/export functionality for Inventory, Pricing, and Manufacturing data using Excel files (.xlsx format).

## Features

### Import Capabilities
- ✅ **Product Master Data** - Bulk create/update products with categories
- ✅ **Price Lists** - Import multi-tier pricing structures
- ✅ **Inventory Adjustments** - Physical counts and stock adjustments
- ✅ **Bill of Materials (BOM)** - Multi-level product structures

### Export Capabilities
- ✅ **Excel Templates** - Pre-formatted import templates with instructions
- ✅ **Data Export** - Export existing data for review/editing
- ✅ **Stock Reports** - Current inventory levels with valuation
- ✅ **Physical Count Sheets** - Pre-filled templates for cycle counting

## API Endpoints

### Import Endpoints

#### Import Products
```http
POST /api/inventory/import/products/
Content-Type: multipart/form-data

Body:
  file: <Excel file>
```

**Response:**
```json
{
  "success_count": 45,
  "error_count": 2,
  "errors": [
    {
      "row": 12,
      "field": "Category Code",
      "message": "Category not found: CAT99"
    }
  ],
  "warnings": [
    {
      "row": 5,
      "message": "Product PROD001 updated (already existed)"
    }
  ]
}
```

#### Import Price List
```http
POST /api/inventory/import/price-list/
Content-Type: multipart/form-data

Body:
  file: <Excel file>
```

#### Import Inventory Adjustments
```http
POST /api/inventory/import/adjustments/?adjustment_type=count
Content-Type: multipart/form-data

Body:
  file: <Excel file>

Query Parameters:
  - adjustment_type: "count" (physical count) or "adjustment" (add/subtract)
```

#### Import BOM
```http
POST /api/inventory/import/bom/
Content-Type: multipart/form-data

Body:
  file: <Excel file>
```

### Export Endpoints

#### Download Product Template
```http
GET /api/inventory/export/product-template/

Returns: Excel file with headers and example row
```

#### Export Products
```http
GET /api/inventory/export/products/?category_id=5

Query Parameters:
  - category_id (optional): Filter by category

Returns: Excel file with all products
```

#### Download Price List Template
```http
GET /api/inventory/export/price-list-template/

Returns: Excel file template
```

#### Export Price List
```http
GET /api/inventory/export/price-list/{price_list_id}/

Returns: Excel file with price list items
```

#### Download Count Template
```http
GET /api/inventory/export/count-template/?warehouse_id=3

Query Parameters:
  - warehouse_id (optional): Filter by warehouse

Returns: Physical count sheet with current quantities
```

#### Export Stock Report
```http
GET /api/inventory/export/stock-report/?warehouse_id=3

Returns: Stock levels report with valuation
```

#### Download BOM Template
```http
GET /api/inventory/export/bom-template/

Returns: BOM import template
```

#### Export BOM
```http
GET /api/inventory/export/bom/{bom_id}/

Returns: Excel file with BOM structure
```

## Excel File Formats

### Product Import Format

**Required Columns:**
- `Code` - Unique product identifier
- `Name` - Product name
- `Category Code` - Must match existing category

**Optional Columns:**
- `Description` - Product description
- `Sale Price` - Selling price (decimal)
- `Cost Price` - Cost/purchase price (decimal)
- `Barcode` - Barcode number
- `SKU` - Stock keeping unit
- `Unit of Measure` - EA, KG, L, etc.
- `Is Inventory Item` - Yes/No
- `Reorder Level` - Minimum stock level
- `Reorder Quantity` - Reorder quantity

**Example:**
```
| Code    | Name           | Category Code | Sale Price | Cost Price | Reorder Level |
|---------|----------------|---------------|------------|------------|---------------|
| PROD001 | Widget A       | CAT01         | 99.99      | 50.00      | 10            |
| PROD002 | Widget B       | CAT01         | 149.99     | 75.00      | 5             |
```

### Price List Import Format

**Required Columns:**
- `Price List Code` - Must match existing price list
- `Product Code` - Must match existing product
- `Price` - Price for this item

**Optional Columns:**
- `Valid From` - Start date (YYYY-MM-DD)
- `Valid To` - End date (YYYY-MM-DD)
- `Min Quantity` - Minimum order quantity

**Example:**
```
| Price List Code | Product Code | Price  | Valid From | Valid To   | Min Quantity |
|-----------------|--------------|--------|------------|------------|--------------|
| RETAIL-2025     | PROD001      | 99.99  | 2025-01-01 | 2025-12-31 | 1            |
| WHOLESALE-2025  | PROD001      | 79.99  | 2025-01-01 |            | 10           |
```

### Inventory Adjustment Format

**Required Columns:**
- `Product Code` - Product to adjust
- `Warehouse Code` - Warehouse location
- `Quantity` - Count/adjustment quantity

**Optional Columns:**
- `Location Code` - Specific bin/location
- `Batch Number` - Batch/lot number
- `Notes` - Adjustment notes

**Example (Physical Count):**
```
| Product Code | Warehouse Code | Location Code | Quantity | Notes              |
|--------------|----------------|---------------|----------|--------------------|
| PROD001      | WH-MAIN        | A-01-01       | 47       | Cycle count Jan 15 |
| PROD002      | WH-MAIN        | A-01-02       | 123      | Physical count     |
```

### BOM Import Format

**Required Columns:**
- `Parent Code` - Finished good product code
- `Component Code` - Component/raw material code
- `Quantity` - Quantity per unit of parent

**Optional Columns:**
- `Unit of Measure` - Component UOM
- `Scrap %` - Expected scrap percentage
- `Notes` - Assembly notes

**Example:**
```
| Parent Code | Component Code | Quantity | Unit of Measure | Scrap % | Notes            |
|-------------|----------------|----------|-----------------|---------|------------------|
| FG-001      | RM-001         | 2.5      | KG              | 5.0     | Main ingredient  |
| FG-001      | RM-002         | 1.0      | L               | 2.0     | Liquid component |
| FG-001      | PKG-001        | 1.0      | EA              | 0.0     | Packaging        |
```

## Usage Examples

### Python Client Example

```python
import requests

API_URL = "http://localhost:8000/api/inventory"
TOKEN = "your-auth-token"

headers = {
    "Authorization": f"Token {TOKEN}"
}

# 1. Download product template
response = requests.get(
    f"{API_URL}/export/product-template/",
    headers=headers
)
with open("product_template.xlsx", "wb") as f:
    f.write(response.content)

# 2. Fill in the template with your data, then import
with open("products_to_import.xlsx", "rb") as f:
    files = {"file": f}
    response = requests.post(
        f"{API_URL}/import/products/",
        headers=headers,
        files=files
    )
    result = response.json()
    print(f"Imported {result['success_count']} products")
    print(f"Errors: {result['error_count']}")

# 3. Export current products
response = requests.get(
    f"{API_URL}/export/products/",
    headers=headers
)
with open("products_export.xlsx", "wb") as f:
    f.write(response.content)

# 4. Generate physical count sheet
response = requests.get(
    f"{API_URL}/export/count-template/?warehouse_id=1",
    headers=headers
)
with open("physical_count.xlsx", "wb") as f:
    f.write(response.content)

# 5. Import count results
with open("physical_count_completed.xlsx", "rb") as f:
    files = {"file": f}
    response = requests.post(
        f"{API_URL}/import/adjustments/?adjustment_type=count",
        headers=headers,
        files=files
    )
```

### cURL Examples

```bash
# Download product template
curl -H "Authorization: Token YOUR_TOKEN" \
  http://localhost:8000/api/inventory/export/product-template/ \
  -o product_template.xlsx

# Import products
curl -X POST \
  -H "Authorization: Token YOUR_TOKEN" \
  -F "file=@products.xlsx" \
  http://localhost:8000/api/inventory/import/products/

# Export stock report
curl -H "Authorization: Token YOUR_TOKEN" \
  "http://localhost:8000/api/inventory/export/stock-report/?warehouse_id=1" \
  -o stock_report.xlsx
```

## Workflow Best Practices

### Initial Data Load

1. **Prepare Master Data**
   - Export templates for products, price lists, BOM
   - Fill in templates with data from existing systems
   - Validate all codes and references

2. **Import in Order**
   ```
   1. Product Categories (via admin or API)
   2. Products (bulk import)
   3. Warehouses & Locations (via admin or API)
   4. Price Lists (bulk import)
   5. BOM structures (bulk import)
   6. Initial inventory counts (bulk import)
   ```

3. **Verify Results**
   - Check import results for errors
   - Export data to verify imports
   - Run stock reports to validate

### Regular Operations

**Monthly Price Updates:**
```python
# 1. Export current price list
response = requests.get(f"{API_URL}/export/price-list/{price_list_id}/")

# 2. Update prices in Excel
# 3. Re-import with updates

response = requests.post(
    f"{API_URL}/import/price-list/",
    files={"file": updated_file}
)
```

**Cycle Counting:**
```python
# 1. Generate count sheet for warehouse
response = requests.get(
    f"{API_URL}/export/count-template/?warehouse_id={warehouse_id}"
)

# 2. Perform physical count (update Excel)
# 3. Import count results

response = requests.post(
    f"{API_URL}/import/adjustments/?adjustment_type=count",
    files={"file": count_file}
)
```

**Product Updates:**
```python
# 1. Export current products
response = requests.get(f"{API_URL}/export/products/")

# 2. Update product data in Excel
# 3. Re-import (will update existing products)

response = requests.post(
    f"{API_URL}/import/products/",
    files={"file": updated_file}
)
```

## Error Handling

### Common Errors

**Missing Category:**
```json
{
  "row": 12,
  "field": "Category Code",
  "message": "Category not found: CAT99"
}
```
**Solution:** Create category first or use existing category code

**Invalid Price:**
```json
{
  "row": 8,
  "field": "Sale Price",
  "message": "Invalid decimal value: abc"
}
```
**Solution:** Use numeric format (e.g., 99.99)

**Duplicate Product Code:**
```json
{
  "row": 15,
  "message": "Product PROD001 updated (already existed)"
}
```
**Note:** This is a warning, not an error. Existing products are updated.

### Validation Tips

- **Codes:** Keep codes alphanumeric, avoid special characters
- **Decimals:** Use proper decimal format (99.99, not $99.99)
- **Dates:** Use YYYY-MM-DD format
- **Booleans:** Use Yes/No, True/False, or 1/0
- **References:** Ensure referenced items exist before import

## Performance

### Large File Import

For imports > 1000 rows:
- Import runs in database transaction (all-or-nothing)
- Errors in any row will rollback entire import
- Consider splitting large files into smaller batches
- Use background task queue for very large imports (future enhancement)

### Recommended Batch Sizes

- Products: 500-1000 rows
- Price Lists: 1000-2000 rows
- Inventory Adjustments: 500-1000 rows
- BOM: 200-500 rows (components)

## Security

- ✅ All endpoints require authentication (`IsAuthenticated`)
- ✅ Organization filtering enforced (`IsOrganizationMember`)
- ✅ Users can only import/export their organization's data
- ✅ File uploads use secure temporary storage
- ✅ Files deleted after processing

## Future Enhancements

- [ ] Background task processing for large imports
- [ ] Email notification on completion
- [ ] Import preview/validation before commit
- [ ] Import templates with data validation rules
- [ ] CSV format support
- [ ] Import history tracking
- [ ] Scheduled exports

---

**Last Updated:** November 24, 2025  
**Version:** 1.0
