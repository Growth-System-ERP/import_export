# Export Document Flow Diagram

## Overview
This document provides a visual representation of the export documentation flow in the Import/Export Frappe app.

---

## Main Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         EXPORT DOCUMENTATION FLOW                    │
└─────────────────────────────────────────────────────────────────────┘

    ┌──────────────────┐
    │  Sales Order     │  (1. Create manually or via quotation)
    │  (Overseas)      │      - Set gst_category = "Overseas"
    └────────┬─────────┘      - Add items with HS codes
             │
             │ create_from_sales_order()
             ▼
    ┌──────────────────────────┐
    │ Commercial Invoice Export │  (2. Core export document)
    │  (CINV-EXP-YYYY-XXXXX)   │      - Auto-populated from SO
    └────────┬─────────────────┘      - Must be submitted first
             │
             │ Status: Submitted
             │
             ├─────────────────────────┬──────────────────────┬────────────────────┐
             │                         │                      │                    │
             ▼                         ▼                      ▼                    ▼
    ┌────────────────┐        ┌───────────────┐     ┌─────────────────┐  ┌──────────────┐
    │ Packing List   │        │ Certificate   │     │ Shipping Bill   │  │ LC           │
    │ Export         │        │ of Origin     │     │                 │  │ Application  │
    │ (PACK-EXP)     │        │ (COO-YYYY)    │     │ (SB-YYYY)       │  │ (Optional)   │
    └───────┬────────┘        └───────────────┘     └─────────────────┘  └──────────────┘
            │                         │                      │
            │                         │                      │
            │ (Must be submitted)     │ (For customs)        │ (For customs)
            │                         │                      │
            ▼                         │                      │
    ┌────────────────┐               │                      │
    │ Bill of Lading │               │                      │
    │ (B/L or AWB)   │               │                      │
    └────────────────┘               │                      │
                                      │                      │
                                      └──────────┬───────────┘
                                                 │
                                                 ▼
                                        ┌────────────────┐
                                        │ EXPORT READY   │
                                        │ FOR SHIPMENT   │
                                        └────────────────┘
```

---

## Detailed Document Creation Methods

### 1. Commercial Invoice Export
```
Source: Sales Order
Method: create_from_sales_order(sales_order)
File: commercial_invoice_export.py

Creates:
  ├─ Basic Info (date, currency, company)
  ├─ Exporter Details (from Company)
  ├─ Consignee Details (from Customer)
  ├─ Items (from SO items with HS codes, weights, volumes)
  ├─ Shipping Details (ports, incoterm)
  ├─ Payment Terms (LC, TT, etc.)
  └─ Bank Details (for payment)

Must Fill:
  ✓ Country of Origin
  ✓ Port of Loading
  ✓ Port of Discharge
  ✓ Incoterm (FOB, CIF, etc.)
```

### 2. Packing List Export
```
Source: Commercial Invoice Export (+ Pick List if available)
Method: create_from_commercial_invoice(commercial_invoice)
File: packing_list_export.py

Creates:
  ├─ Shipper/Exporter Details (from CI)
  ├─ Consignee Details (from CI)
  ├─ Shipping Information (ports, vessel)
  ├─ Carton Details (from Pick List or manual entry)
  │   ├─ Carton ID
  │   ├─ Carton Count
  │   ├─ Items per Carton
  │   ├─ Dimensions (L x W x H)
  │   └─ Weight
  └─ Totals (cartons, weight, volume)

Note: If Pick List exists with packing data, cartons auto-populate
```

### 3. Certificate of Origin
```
Source: Commercial Invoice Export
Method: create_from_commercial_invoice(commercial_invoice)
File: certificate_of_origin.py

Creates:
  ├─ Certificate Info (type, date)
  ├─ Validity Period (auto-calculated based on type)
  ├─ Exporter Details (from CI)
  ├─ Consignee Details (from CI)
  └─ Products (from CI items with origin country)

Certificate Types & Validity:
  • Generic: 180 days
  • GSP Form A: 365 days
  • SAPTA/SAFTA/ASEAN: 365 days
  • Country-Specific: 180 days
```

### 4. Shipping Bill
```
Source: Commercial Invoice Export
Method: create_from_commercial_invoice(commercial_invoice)
File: shipping_bill.py

Creates:
  ├─ Exporter Details (from CI)
  ├─ Consignee Details (from CI)
  ├─ Items with FOB Values (INR and FC)
  ├─ Shipping Details (port, vessel, container)
  └─ Export Incentives (RoDTEP, Duty Drawback)

Must Fill After Creation:
  ✓ Port Code (6-digit Indian customs code)
  ✓ Shipping Bill Number (from customs)
  ✓ AD Code (Authorized Dealer Code)

Incentive Calculations:
  • RoDTEP: % of FOB value (if claimed)
  • Duty Drawback: Item-level calculation
```

### 5. Bill of Lading
```
Source: Packing List Export (requires PL to be submitted)
Method: create_from_packing_list(packing_list_name)
File: bill_of_lading.py

Prerequisites:
  ✓ Packing List must be submitted

Creates:
  ├─ Shipper Details (exporter)
  ├─ Consignee Details (buyer)
  ├─ Notify Party (usually same as consignee)
  ├─ Routing (ports, vessel)
  ├─ Container Details (from PL and CI)
  ├─ Cargo Description (from CI items)
  └─ Freight Terms (based on incoterm)

Must Fill After Creation:
  ✓ B/L Number
  ✓ Carrier Name
  ✓ Vessel/Flight Name
```

---

## Document Dependencies

```
┌─────────────────────────────────────────────────────────────┐
│ DEPENDENCY CHAIN                                            │
└─────────────────────────────────────────────────────────────┘

Sales Order (Submitted)
    └─→ Required for: Commercial Invoice Export

Commercial Invoice Export (Submitted)
    ├─→ Required for: Packing List Export
    ├─→ Required for: Certificate of Origin
    ├─→ Required for: Shipping Bill
    └─→ Required for: LC Application

Packing List Export (Submitted)
    └─→ Required for: Bill of Lading

Pick List (Optional, Submitted)
    └─→ Enhances: Packing List Export (auto-carton data)
```

---

## Field Mappings Between Documents

### Commercial Invoice → Packing List
```
CI Field                    →  PL Field
─────────────────────────────────────────────────
exporter_name               →  shipper_name
exporter_address            →  shipper_address
customer_name               →  consignee_name
consignee_address           →  consignee_address
port_of_loading             →  port_of_loading
port_of_discharge           →  port_of_discharge
vessel_flight_no            →  vessel_flight_no
shipping_marks              →  shipping_marks
container_nos               →  (parsed for containers)
total_cartons               →  total_cartons
total_gross_weight          →  total_gross_weight
total_volume_cbm            →  total_volume_cbm
```

### Commercial Invoice → Certificate of Origin
```
CI Field                    →  COO Field
─────────────────────────────────────────────────
exporter_name               →  exporter_name
exporter_address            →  exporter_address
iec_code                    →  iec_code
country_of_origin           →  country_of_export
port_of_loading             →  port_of_loading
customer_name               →  consignee_name
consignee_address           →  consignee_address
consignee_country           →  destination_country
port_of_discharge           →  port_of_discharge
items                       →  products
```

### Commercial Invoice → Shipping Bill
```
CI Field                    →  SB Field
─────────────────────────────────────────────────
exporter_name               →  exporter_name
exporter_address            →  exporter_address
iec_code                    →  iec_code
exporter_gstin              →  exporter_gstin
exporter_pan                →  exporter_pan
customer_name               →  consignee_name
consignee_address           →  consignee_address
consignee_country           →  destination_country
port_of_discharge           →  port_of_discharge
port_of_loading             →  port_of_loading
vessel_flight_no            →  vessel_flight_no
container_nos               →  container_nos
currency                    →  currency
conversion_rate             →  exchange_rate
items                       →  items (with FOB values)
```

### Packing List → Bill of Lading
```
PL Field                    →  B/L Field
─────────────────────────────────────────────────
shipper_name                →  shipper_name
shipper_address             →  shipper_address
consignee_name              →  consignee_name
consignee_address           →  consignee_address
port_of_loading             →  port_of_loading
port_of_discharge           →  port_of_discharge
container_size              →  containers.container_size
total_cartons               →  total_packages
total_gross_weight          →  total_gross_weight
total_volume_cbm            →  total_volume
```

---

## Status Flow

```
┌─────────────────────────────────────────────────────────────┐
│ DOCUMENT STATUS PROGRESSION                                 │
└─────────────────────────────────────────────────────────────┘

Sales Order
  Draft → Submitted → Closed/Completed

Commercial Invoice Export
  Draft → Submitted → Shipped

Packing List Export
  Draft → Packed (Submitted)

Certificate of Origin
  Draft → Submitted → Attested → (can become) Expired

Shipping Bill
  Draft → Submitted → Filed → Assessed → Cleared

Bill of Lading
  Draft → Issued (Submitted) → (can be) Surrendered
```

---

## API Methods Reference

### Commercial Invoice Export
```python
# Create from Sales Order
frappe.call({
    method: 'import_export.import_export.doctype.commercial_invoice_export.commercial_invoice_export.create_from_sales_order',
    args: { sales_order: 'SO-2025-00001' }
})

# Get items from Sales Order
frappe.call({
    method: 'import_export.import_export.doctype.commercial_invoice_export.commercial_invoice_export.get_items_from_sales_order',
    args: { sales_order: 'SO-2025-00001' }
})

# Check export readiness
frappe.call({
    method: 'import_export.import_export.doctype.commercial_invoice_export.commercial_invoice_export.get_export_readiness',
    args: { name: 'CINV-EXP-2025-00001' }
})

# Create next document
frappe.call({
    method: 'import_export.import_export.doctype.commercial_invoice_export.commercial_invoice_export.create_next_document',
    args: { 
        commercial_invoice: 'CINV-EXP-2025-00001',
        doctype: 'Packing List Export'  // or 'Certificate of Origin', 'Shipping Bill', 'Bill of Lading'
    }
})
```

### Packing List Export
```python
# Create from Commercial Invoice
frappe.call({
    method: 'import_export.import_export.doctype.packing_list_export.packing_list_export.create_from_commercial_invoice',
    args: { commercial_invoice: 'CINV-EXP-2025-00001' }
})

# Create from Pick List
frappe.call({
    method: 'import_export.import_export.doctype.packing_list_export.packing_list_export.create_from_pick_list',
    args: { 
        pick_list_name: 'MAT-PICK-2025-00001',
        commercial_invoice: 'CINV-EXP-2025-00001'
    }
})
```

### Certificate of Origin
```python
# Create from Commercial Invoice
frappe.call({
    method: 'import_export.import_export.doctype.certificate_of_origin.certificate_of_origin.create_from_commercial_invoice',
    args: { commercial_invoice: 'CINV-EXP-2025-00001' }
})

# Update attestation status
frappe.call({
    method: 'import_export.import_export.doctype.certificate_of_origin.certificate_of_origin.update_attestation_status',
    args: {
        certificate_name: 'COO-2025-00001',
        status: 'Attested',
        attestation_number: 'ATT-123456',
        attested_date: '2025-01-15'
    }
})
```

### Shipping Bill
```python
# Create from Commercial Invoice
frappe.call({
    method: 'import_export.import_export.doctype.shipping_bill.shipping_bill.create_from_commercial_invoice',
    args: { commercial_invoice: 'CINV-EXP-2025-00001' }
})

# Update customs status
frappe.call({
    method: 'import_export.import_export.doctype.shipping_bill.shipping_bill.update_customs_status',
    args: {
        shipping_bill_name: 'SB-2025-00001',
        sb_status: 'Cleared',
        leo_date: '2025-01-20',
        shipping_bill_no: 'SB123456',
        assessment_date: '2025-01-18'
    }
})
```

### Bill of Lading
```python
# Create from Packing List
frappe.call({
    method: 'import_export.import_export.doctype.bill_of_lading.bill_of_lading.create_from_packing_list',
    args: { packing_list_name: 'PACK-EXP-2025-00001' }
})

# Surrender B/L (for telex release)
frappe.call({
    method: 'import_export.import_export.doctype.bill_of_lading.bill_of_lading.surrender_bl',
    args: { bl_name: 'MAEU123456789' }
})
```

---

## Error Prevention Checklist

### Before Creating Commercial Invoice
- [ ] Sales Order is submitted
- [ ] Sales Order has `gst_category = "Overseas"`
- [ ] All items have HS codes (8-digit)
- [ ] Customer address exists and has country
- [ ] Company has necessary export details

### Before Creating Packing List
- [ ] Commercial Invoice is submitted
- [ ] All required CI fields are filled

### Before Creating Certificate of Origin
- [ ] Commercial Invoice is submitted
- [ ] Items have country of origin
- [ ] Destination country is set

### Before Creating Shipping Bill
- [ ] Commercial Invoice is submitted
- [ ] Port code is available (6-digit)
- [ ] IEC code is set

### Before Creating Bill of Lading
- [ ] Packing List is submitted
- [ ] Commercial Invoice has container numbers
- [ ] Carrier details are available
- [ ] B/L number is ready

---

## Quick Reference: Document Purposes

| Document | Purpose | Required For | Issued By |
|----------|---------|--------------|-----------|
| Commercial Invoice | Proof of sale, customs value | Customs clearance | Exporter |
| Packing List | Cargo details, packing info | Shipping, customs | Exporter |
| Certificate of Origin | Prove goods origin, get duty benefits | Customs (importing country) | Chamber of Commerce |
| Shipping Bill | Customs declaration for export | Export clearance | Exporter (to customs) |
| Bill of Lading | Receipt of goods, title document | Shipping, payment release | Shipping line/Carrier |
| LC Application | Request LC opening | Bank financing | Exporter (beneficiary) |

---

## Notes

1. **Document Order Matters**: Create in sequence to maintain data consistency
2. **Submission Required**: Parent documents must be submitted before creating children
3. **Field Validation**: Ensure all mandatory fields are filled before submission
4. **Data Flow**: Later documents inherit data from earlier ones
5. **Amendments**: Use Frappe's amendment feature if changes needed after submission

---

## Support & Maintenance

- All field mappings verified as of January 2025
- Python code aligned with JSON schemas
- No field name mismatches remain
- All creation methods tested and working