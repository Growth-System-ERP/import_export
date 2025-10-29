# Testing Guide - Export Document Flow

## Overview
This guide provides step-by-step testing procedures for the complete export documentation flow in the Import/Export Frappe app.

---

## Prerequisites

### 1. Master Data Setup
Before testing, ensure the following master data exists:

#### Company Setup
```python
# Ensure company has export details
company = frappe.get_doc("Company", "Your Company")
company.country = "India"  # Or your export country
# Add custom fields if needed:
# - iec_code
# - default_port_of_export
# - default_bank_account
```

#### Customer Setup
```python
# Create/verify international customer
customer = frappe.new_doc("Customer")
customer.customer_name = "Test International Buyer"
customer.customer_group = "Commercial"
customer.territory = "Rest Of The World"
customer.save()

# Add customer address
address = frappe.new_doc("Address")
address.address_title = "Buyer Address"
address.address_type = "Billing"
address.address_line1 = "123 Foreign St"
address.city = "Dubai"
address.country = "United Arab Emirates"
address.append("links", {
    "link_doctype": "Customer",
    "link_name": customer.name
})
address.save()
```

#### Item Setup
```python
# Create export items with HS codes
item = frappe.new_doc("Item")
item.item_code = "EXPORT-ITEM-001"
item.item_name = "Export Product 1"
item.item_group = "Products"
item.stock_uom = "Nos"
item.gst_hsn_code = "84145990"  # 8-digit HS code
item.weight_per_unit = 5  # kg
item.country_of_origin = "India"
# Add dimensions if needed
item.length = 30  # cm
item.width = 20   # cm
item.height = 15  # cm
item.save()
```

### 2. Sales Order Creation
```python
# Create export sales order
so = frappe.new_doc("Sales Order")
so.customer = "Test International Buyer"
so.transaction_date = frappe.utils.today()
so.delivery_date = frappe.utils.add_days(frappe.utils.today(), 30)
so.gst_category = "Overseas"  # Important for exports
so.currency = "USD"
so.conversion_rate = 83.0  # Example rate

# Add items
so.append("items", {
    "item_code": "EXPORT-ITEM-001",
    "qty": 100,
    "rate": 50.00,
    "delivery_date": so.delivery_date
})

so.insert()
so.submit()
```

---

## Testing Flow

### Test 1: Commercial Invoice Export Creation

#### Method 1: Auto-create from Sales Order
```python
# Using whitelisted method
ci_name = frappe.call(
    "import_export.import_export.doctype.commercial_invoice_export.commercial_invoice_export.create_from_sales_order",
    sales_order="SO-2025-00001"
)

ci = frappe.get_doc("Commercial Invoice Export", ci_name)
```

#### Method 2: Manual Creation
1. Go to: **Commercial Invoice Export > New**
2. Select Sales Order
3. Click on Sales Order field - items auto-populate
4. Fill required fields:
   - Invoice Date
   - Country of Origin
   - Port of Loading
   - Port of Discharge
   - Incoterm (FOB/CIF/etc)

#### Validation Checklist
- [ ] Exporter details auto-filled from Company
- [ ] Consignee details auto-filled from Customer
- [ ] Items populated with HS codes
- [ ] Weights and volumes calculated
- [ ] Totals calculated correctly
- [ ] Currency conversion applied
- [ ] Submit succeeds without errors

---

### Test 2: Packing List Export Creation

#### From Commercial Invoice
```python
# Auto-create packing list
pl_name = frappe.call(
    "import_export.import_export.doctype.packing_list_export.packing_list_export.create_from_commercial_invoice",
    commercial_invoice="CINV-EXP-2025-00001"
)

pl = frappe.get_doc("Packing List Export", pl_name)
```

#### Validation Checklist
- [ ] Commercial Invoice linked correctly
- [ ] Shipper/Consignee details copied from CI
- [ ] Shipping info copied correctly
- [ ] If Pick List with packing data exists, cartons populated
- [ ] If no Pick List, basic structure created
- [ ] Total calculations work
- [ ] Submit succeeds

#### Manual Carton Entry (if no Pick List)
```python
# Add carton details manually
pl.append("cartons", {
    "carton_id": "CARTON-001",
    "carton_count": 10,
    "items_per_carton": 10,
    "length": 50,  # cm
    "width": 40,
    "height": 30,
    "weight_limit": 25,  # kg
})
pl.save()
```

---

### Test 3: Certificate of Origin Creation

#### From Commercial Invoice
```python
# Auto-create COO
coo_name = frappe.call(
    "import_export.import_export.doctype.certificate_of_origin.certificate_of_origin.create_from_commercial_invoice",
    commercial_invoice="CINV-EXP-2025-00001"
)

coo = frappe.get_doc("Certificate of Origin", coo_name)
```

#### Validation Checklist
- [ ] Certificate type set correctly
- [ ] Certificate date populated
- [ ] Validity period calculated (default 180 days)
- [ ] Valid until date set correctly
- [ ] Exporter details copied
- [ ] Consignee details copied
- [ ] Products table populated from CI items
- [ ] Country of origin set for each product
- [ ] Submit succeeds

#### Test Certificate Types
Test with different certificate types:
- Generic (default)
- GSP Form A (365 days validity)
- SAPTA
- SAFTA
- ASEAN
- Country-Specific

```python
coo.certificate_type = "GSP Form A"
coo.save()
# Check validity_period is 365
assert coo.validity_period == 365
```

---

### Test 4: Shipping Bill Creation

#### From Commercial Invoice
```python
# Auto-create Shipping Bill
sb_name = frappe.call(
    "import_export.import_export.doctype.shipping_bill.shipping_bill.create_from_commercial_invoice",
    commercial_invoice="CINV-EXP-2025-00001"
)

sb = frappe.get_doc("Shipping Bill", sb_name)
```

#### Required Manual Fields
After creation, fill these fields:
- Port Code (6-digit Indian customs code, e.g., "040047" for Nhava Sheva)
- Shipping Bill Number (from customs)
- Shipping Bill Date

#### Test Incentive Calculations

##### RoDTEP Calculation
```python
sb.rodtep_claimed = 1
sb.rodtep_rate = 2.5  # 2.5%
sb.save()

# Verify calculation
expected_rodtep = sb.total_fob_value_inr * 2.5 / 100
assert sb.rodtep_amount == expected_rodtep
```

##### Duty Drawback (Item-level)
```python
# Set drawback rate for each item
for item in sb.items:
    item.drawback_rate = 2.0  # 2%
    item.assessable_value = item.fob_value_inr

sb.duty_drawback_claimed = 1
sb.save()

# Verify calculation
total_drawback = sum(item.drawback_amount for item in sb.items)
assert sb.drawback_amount == total_drawback
```

#### Validation Checklist
- [ ] Exporter details copied
- [ ] Consignee details copied
- [ ] Items table populated with FOB values
- [ ] Total FOB values calculated (INR and FC)
- [ ] Currency and exchange rate set
- [ ] Freight and insurance charges copied
- [ ] RoDTEP calculation works if enabled
- [ ] Duty drawback calculation works if enabled
- [ ] Submit succeeds

---

### Test 5: Bill of Lading Creation

**Important:** Bill of Lading requires Packing List to be submitted first.

#### From Packing List
```python
# Ensure Packing List is submitted
pl = frappe.get_doc("Packing List Export", "PACK-EXP-2025-00001")
if pl.docstatus == 0:
    pl.submit()

# Create Bill of Lading
bl_name = frappe.call(
    "import_export.import_export.doctype.bill_of_lading.bill_of_lading.create_from_packing_list",
    packing_list_name=pl.name
)

bl = frappe.get_doc("Bill of Lading", bl_name)
```

#### Required Manual Fields
- B/L Number (e.g., "MAEU123456789")
- Carrier Name (Shipping line, e.g., "Maersk Line")
- Vessel Name (e.g., "MV EVER GIVEN")

#### Validation Checklist
- [ ] Commercial Invoice linked
- [ ] Shipper details (exporter) copied
- [ ] Shipper contact field populated (not shipper_phone)
- [ ] Consignee details (buyer) copied
- [ ] Consignee contact field populated (not consignee_phone)
- [ ] Notify party details copied
- [ ] Notify party contact field populated (not notify_party_phone)
- [ ] Port of loading/discharge set
- [ ] Container details populated from Packing List
- [ ] Package count matches Packing List
- [ ] Gross weight copied
- [ ] Volume copied
- [ ] Freight terms set based on Incoterm
- [ ] Submit succeeds

---

## Complete End-to-End Test

### Test Script
```python
def test_complete_export_flow():
    """Test complete export documentation flow"""
    
    # 1. Create Sales Order
    so = frappe.new_doc("Sales Order")
    so.customer = "Test International Buyer"
    so.transaction_date = frappe.utils.today()
    so.delivery_date = frappe.utils.add_days(frappe.utils.today(), 30)
    so.gst_category = "Overseas"
    so.currency = "USD"
    so.conversion_rate = 83.0
    so.append("items", {
        "item_code": "EXPORT-ITEM-001",
        "qty": 100,
        "rate": 50.00
    })
    so.insert()
    so.submit()
    print(f"✓ Sales Order created: {so.name}")
    
    # 2. Create Commercial Invoice
    ci_name = frappe.call(
        "import_export.import_export.doctype.commercial_invoice_export.commercial_invoice_export.create_from_sales_order",
        sales_order=so.name
    )
    ci = frappe.get_doc("Commercial Invoice Export", ci_name)
    ci.country_of_origin = "India"
    ci.port_of_loading = "Mumbai (INMUN1)"
    ci.port_of_discharge = "Dubai (AEDXB1)"
    ci.incoterm = "FOB"
    ci.save()
    ci.submit()
    print(f"✓ Commercial Invoice created: {ci.name}")
    
    # 3. Create Packing List
    pl_name = frappe.call(
        "import_export.import_export.doctype.packing_list_export.packing_list_export.create_from_commercial_invoice",
        commercial_invoice=ci.name
    )
    pl = frappe.get_doc("Packing List Export", pl_name)
    # Add carton if not auto-populated
    if not pl.cartons:
        pl.append("cartons", {
            "carton_id": "CTN-001",
            "carton_count": 10,
            "items_per_carton": 10,
            "length": 50,
            "width": 40,
            "height": 30
        })
    pl.save()
    pl.submit()
    print(f"✓ Packing List created: {pl.name}")
    
    # 4. Create Certificate of Origin
    coo_name = frappe.call(
        "import_export.import_export.doctype.certificate_of_origin.certificate_of_origin.create_from_commercial_invoice",
        commercial_invoice=ci.name
    )
    coo = frappe.get_doc("Certificate of Origin", coo_name)
    coo.certificate_type = "Generic"
    coo.save()
    coo.submit()
    print(f"✓ Certificate of Origin created: {coo.name}")
    
    # 5. Create Shipping Bill
    sb_name = frappe.call(
        "import_export.import_export.doctype.shipping_bill.shipping_bill.create_from_commercial_invoice",
        commercial_invoice=ci.name
    )
    sb = frappe.get_doc("Shipping Bill", sb_name)
    sb.port_code = "040047"  # Nhava Sheva
    sb.save()
    sb.submit()
    print(f"✓ Shipping Bill created: {sb.name}")
    
    # 6. Create Bill of Lading
    bl_name = frappe.call(
        "import_export.import_export.doctype.bill_of_lading.bill_of_lading.create_from_packing_list",
        packing_list_name=pl.name
    )
    bl = frappe.get_doc("Bill of Lading", bl_name)
    bl.bl_no = "TEST-BL-001"
    bl.carrier_name = "Test Shipping Line"
    bl.vessel_flight_name = "MV TEST VESSEL"
    bl.save()
    bl.submit()
    print(f"✓ Bill of Lading created: {bl.name}")
    
    print("\n✅ Complete export flow test PASSED")
    return {
        "sales_order": so.name,
        "commercial_invoice": ci.name,
        "packing_list": pl.name,
        "certificate_of_origin": coo.name,
        "shipping_bill": sb.name,
        "bill_of_lading": bl.name
    }

# Run test
result = test_complete_export_flow()
print("\nCreated Documents:")
print(frappe.as_json(result, indent=2))
```

---

## Common Errors & Solutions

### Error: AttributeError - Field not found

#### Symptom
```
AttributeError: 'CertificateofOrigin' object has no attribute 'issue_date'
```

#### Solution
Field name mismatch. Check JSON schema and use correct field name.
- ❌ `issue_date` → ✅ `certificate_date`
- ❌ `shipper_phone` → ✅ `shipper_contact`

### Error: Commercial Invoice must be submitted

#### Symptom
When creating child documents, error says CI must be submitted.

#### Solution
```python
ci = frappe.get_doc("Commercial Invoice Export", ci_name)
ci.submit()
```

### Error: Packing List required for Bill of Lading

#### Symptom
Cannot create B/L without Packing List.

#### Solution
```python
# Create and submit Packing List first
pl = frappe.get_doc("Packing List Export", pl_name)
pl.submit()

# Then create Bill of Lading
bl_name = create_from_packing_list(pl.name)
```

### Error: Missing required field

#### Symptom
```
frappe.exceptions.ValidationError: Row 1: HS Code is required
```

#### Solution
Ensure item master has `gst_hsn_code` field populated with 8-digit HS code.

---

## Verification Checklist

After completing the flow, verify:

### Document Linkages
```python
ci = frappe.get_doc("Commercial Invoice Export", "CINV-EXP-2025-00001")

# Check child documents exist
pl = frappe.get_all("Packing List Export", 
    filters={"commercial_invoice": ci.name})
assert len(pl) == 1

coo = frappe.get_all("Certificate of Origin",
    filters={"commercial_invoice": ci.name})
assert len(coo) == 1

sb = frappe.get_all("Shipping Bill",
    filters={"commercial_invoice": ci.name})
assert len(sb) == 1

bl = frappe.get_all("Bill of Lading",
    filters={"commercial_invoice": ci.name})
assert len(bl) == 1
```

### Data Consistency
- [ ] All documents have same company
- [ ] All documents link to same Commercial Invoice
- [ ] Exporter details consistent across documents
- [ ] Consignee details consistent across documents
- [ ] Port of loading/discharge consistent
- [ ] Currency and amounts match
- [ ] Item details consistent

### Submission Status
```python
def check_submission_status(ci_name):
    docs = {
        "Commercial Invoice": frappe.get_doc("Commercial Invoice Export", ci_name),
        "Packing List": frappe.get_value("Packing List Export", 
            {"commercial_invoice": ci_name}, "docstatus"),
        "COO": frappe.get_value("Certificate of Origin",
            {"commercial_invoice": ci_name}, "docstatus"),
        "Shipping Bill": frappe.get_value("Shipping Bill",
            {"commercial_invoice": ci_name}, "docstatus"),
        "Bill of Lading": frappe.get_value("Bill of Lading",
            {"commercial_invoice": ci_name}, "docstatus")
    }
    
    for doc_name, status in docs.items():
        print(f"{doc_name}: {'Submitted' if status == 1 else 'Draft'}")
```

---

## Performance Testing

### Test with Large Dataset
```python
def test_large_order():
    """Test with sales order having many items"""
    so = frappe.new_doc("Sales Order")
    so.customer = "Test International Buyer"
    so.gst_category = "Overseas"
    
    # Add 50 items
    for i in range(1, 51):
        so.append("items", {
            "item_code": f"EXPORT-ITEM-{i:03d}",
            "qty": 100,
            "rate": 50.00
        })
    
    so.insert()
    so.submit()
    
    # Time the CI creation
    import time
    start = time.time()
    ci_name = create_from_sales_order(so.name)
    end = time.time()
    
    print(f"Created CI with 50 items in {end-start:.2f} seconds")
    
    ci = frappe.get_doc("Commercial Invoice Export", ci_name)
    assert len(ci.items) == 50
```

---

## Troubleshooting Commands

### Reset Test Data
```python
def cleanup_test_data(so_name):
    """Delete all export documents for a sales order"""
    # Get Commercial Invoice
    ci = frappe.get_value("Commercial Invoice Export",
        {"sales_order": so_name}, "name")
    
    if ci:
        # Delete child documents first
        for doctype in ["Bill of Lading", "Shipping Bill", 
                        "Certificate of Origin", "Packing List Export"]:
            docs = frappe.get_all(doctype, 
                filters={"commercial_invoice": ci})
            for doc in docs:
                frappe.delete_doc(doctype, doc.name, force=1)
        
        # Delete Commercial Invoice
        frappe.delete_doc("Commercial Invoice Export", ci, force=1)
    
    # Delete Sales Order
    frappe.delete_doc("Sales Order", so_name, force=1)
    frappe.db.commit()
    print("Test data cleaned up")
```

### Check Field Existence
```python
def check_fields(doctype, fields):
    """Verify fields exist in doctype"""
    meta = frappe.get_meta(doctype)
    for field in fields:
        exists = meta.has_field(field)
        print(f"{field}: {'✓' if exists else '✗'}")

# Example
check_fields("Certificate of Origin", [
    "certificate_date", "validity_period", "valid_until"
])
```

---

## Next Steps

After successful testing:
1. Configure Print Formats for each document
2. Set up email templates for sending documents
3. Configure workflows if approval required
4. Set up custom scripts for client-side validations
5. Create reports for export tracking
6. Integrate with shipping carrier APIs if needed

---

## Support

For issues or questions:
- Check FIELD_FIXES_SUMMARY.md for field name mappings
- Review Python files in doctype folders
- Check JSON schemas in doctype folders
- Refer to Frappe documentation: https://frappeframework.com/docs