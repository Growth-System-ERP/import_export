# Fields Restored - Business Analysis & Justification

## Executive Summary

After initial analysis, several fields were removed from the Python code because they didn't exist in the JSON schemas. However, upon deeper business analysis of import/export operations in India, these fields represent **critical real-world export incentive schemes and certificate requirements**. Therefore, they have been **properly added to the JSON schemas** and the Python code has been **fully restored**.

---

## Certificate of Origin - Restored Fields

### Why These Fields Are Critical

Certificate of Origin is not just a formality - it determines **duty rates** in the importing country. The difference between a generic COO and a preferential COO can save **10-40% in import duties** for the buyer.

### Fields Added to JSON Schema

#### 1. `preferential_certificate` (Check field)
**Business Purpose:**
- Distinguishes between generic COO (no duty benefits) and preferential COO (duty concessions under FTA)
- Critical for customs clearance in importing country
- Buyers specifically request preferential certificates to avail FTA benefits

**Real-world Example:**
- Generic COO: Importer pays 10% duty on Indian textiles in UAE
- Preferential COO (India-UAE CEPA): Importer pays 0% duty
- **Direct cost impact:** $10,000 duty saved on $100,000 shipment

**Implementation:**
```json
{
  "fieldname": "preferential_certificate",
  "fieldtype": "Check",
  "label": "Preferential Certificate",
  "description": "Check if this is a preferential certificate under an FTA"
}
```

#### 2. `agreement_type` (Select field)
**Business Purpose:**
- Specifies which Free Trade Agreement provides the preferential treatment
- Different FTAs have different rules of origin and validity periods
- Required for customs to verify tariff concession eligibility

**Active Indian FTAs:**
- India-ASEAN FTA (covers 10 countries)
- India-Japan CEPA
- India-Korea CEPA
- India-Singapore CECA
- India-UAE CEPA (2022 - very popular)
- India-Australia ECTA (2022)
- SAFTA (South Asian Free Trade Area)
- SAPTA, APTA
- Many more

**Validity Impact:**
- India-ASEAN FTA: 365 days validity
- India-Australia ECTA: 730 days (self-certification)
- Generic COO: 180 days validity

**Implementation:**
```json
{
  "fieldname": "agreement_type",
  "fieldtype": "Select",
  "label": "Agreement Type",
  "options": "India-ASEAN FTA\nIndia-Japan CEPA\nIndia-Korea CEPA\n...",
  "depends_on": "preferential_certificate"
}
```

#### 3. `certificate_status` (Select field)
**Business Purpose:**
- Track certificate usage lifecycle: Draft → Active → Used → Expiring Soon → Expired
- Prevent using expired certificates (causes customs rejection)
- Alert exporters to renew expiring certificates
- Track which certificates have been utilized

**Operational Impact:**
- Expired certificate = shipment held at customs
- Expiring soon alert = proactive renewal
- Used status = audit trail for claims

**Implementation:**
```json
{
  "fieldname": "certificate_status",
  "fieldtype": "Select",
  "label": "Certificate Status",
  "options": "Draft\nActive\nUsed\nExpiring Soon\nExpired",
  "read_only": 1
}
```

### Python Logic Restored

```python
def get_fta_specific_validity(self):
    """Get FTA-specific validity period"""
    fta_validity_map = {
        "India-ASEAN FTA": 365,
        "India-Japan CEPA": 365,
        "India-Korea CEPA": 365,
        "India-Singapore CECA": 365,
        "India-UAE CEPA": 365,
        "India-Australia ECTA": 730,  # Self-certification
        "SAFTA": 365,
        # ... more FTAs
    }
    return fta_validity_map.get(self.agreement_type)

def update_certificate_status(self):
    """Auto-update status based on validity dates"""
    if current_date > end_date:
        self.certificate_status = "Expired"
    elif (end_date - current_date).days <= 30:
        self.certificate_status = "Expiring Soon"
    else:
        self.certificate_status = "Active"
```

---

## Shipping Bill - Restored Incentive Fields

### Why These Fields Are Critical

Export incentives can represent **5-15% additional revenue** on top of FOB value. For a ₹1 crore export, this means **₹5-15 lakhs in government incentives**. Proper tracking is essential for:
- Claiming benefits from government
- Financial reporting and forecasting
- Compliance and audit trails

### Fields Added to JSON Schema

#### 1. RoSCTL (Rebate of State and Central Taxes and Levies)
**Scheme Details:**
- Launched: March 2019 (replaced RoSL)
- Sector: Textiles and Apparel
- Benefit: 0.5% to 4.3% of FOB value
- Purpose: Rebate embedded state and central taxes

**Real Numbers:**
- Garment export worth ₹50 lakh
- RoSCTL rate: 2.5%
- Benefit: ₹1.25 lakh

**Fields Added:**
```json
{
  "fieldname": "rosctl_claimed",
  "fieldtype": "Check",
  "label": "RoSCTL Claimed"
},
{
  "fieldname": "rosctl_rate",
  "fieldtype": "Percent",
  "label": "RoSCTL Rate (%)"
},
{
  "fieldname": "rosctl_amount",
  "fieldtype": "Currency",
  "label": "RoSCTL Amount",
  "read_only": 1
}
```

#### 2. MEIS (Merchandise Exports from India Scheme)
**Scheme Details:**
- Status: **Legacy scheme** (closed Dec 2020, replaced by RoDTEP)
- Still relevant for: Old claims, historical records
- Benefit: 2% to 5% of FOB value (transferred as duty credit scrips)

**Why Keep It:**
- Historical exports still have pending claims
- Audit trails require tracking
- Some exporters filing retrospective claims

**Fields Added:**
```json
{
  "fieldname": "meis_claimed",
  "fieldtype": "Check",
  "label": "MEIS Claimed",
  "description": "Merchandise Exports from India Scheme (legacy)"
}
```

#### 3. Advance Authorization Scheme
**Scheme Details:**
- Allows **duty-free import** of inputs used in exported goods
- No duty paid on raw materials if export obligation fulfilled
- Major benefit for manufacturing exporters

**Example:**
- Import raw materials worth $100,000 (duty-free)
- Normal duty would be 10% = $10,000 saved
- Export finished goods worth $200,000
- Net benefit: $10,000 duty saved

**Fields Added:**
```json
{
  "fieldname": "advance_authorization_no",
  "fieldtype": "Data",
  "label": "Advance Authorization No"
},
{
  "fieldname": "aa_benefit_rate",
  "fieldtype": "Percent",
  "label": "AA Benefit Rate (%)"
},
{
  "fieldname": "aa_benefit_amount",
  "fieldtype": "Currency",
  "label": "AA Benefit Amount"
}
```

#### 4. EPCG (Export Promotion Capital Goods)
**Scheme Details:**
- Allows import of capital goods at **zero/reduced duty**
- Condition: Export 6x the duty saved over 6 years
- Critical for capacity expansion with foreign machinery

**Example:**
- Import machinery worth ₹1 crore
- Normal duty: 15% = ₹15 lakh
- Under EPCG: Zero duty
- Export obligation: ₹90 lakh over 6 years

**Fields Added:**
```json
{
  "fieldname": "epcg_license_no",
  "fieldtype": "Data",
  "label": "EPCG License No"
},
{
  "fieldname": "epcg_duty_saved",
  "fieldtype": "Currency",
  "label": "EPCG Duty Saved"
},
{
  "fieldname": "epcg_benefit_amount",
  "fieldtype": "Currency",
  "label": "EPCG Benefit Amount"
}
```

#### 5. Interest Subvention
**Scheme Details:**
- Government subsidizes **2-3% interest** on export credit
- Available for: Pre-shipment and post-shipment credit
- Target: MSMEs and specified sectors
- Purpose: Reduce cost of export finance

**Example:**
- Export finance: ₹50 lakh at 9% interest
- With subvention: Effective rate becomes 6%
- Annual saving: ₹1.5 lakh

**Fields Added:**
```json
{
  "fieldname": "interest_subvention_applicable",
  "fieldtype": "Check",
  "label": "Interest Subvention Applicable"
},
{
  "fieldname": "interest_subvention_rate",
  "fieldtype": "Percent",
  "label": "Interest Subvention Rate (%)"
},
{
  "fieldname": "interest_subvention_amount",
  "fieldtype": "Currency",
  "label": "Interest Subvention Amount"
}
```

#### 6. TMA (Transport and Marketing Assistance)
**Scheme Details:**
- Supports exports of **specified agriculture products**
- Offsets freight and marketing costs
- Rate: Varies by product and destination
- Typical: 3-10% of freight cost

**Products Covered:**
- Fresh fruits and vegetables
- Floriculture
- Certain processed foods

**Example:**
- Export mangoes to Europe
- Freight cost: ₹2 lakh
- TMA rate: 7%
- Benefit: ₹14,000

**Fields Added:**
```json
{
  "fieldname": "tma_applicable",
  "fieldtype": "Check",
  "label": "TMA Applicable"
},
{
  "fieldname": "tma_amount",
  "fieldtype": "Currency",
  "label": "TMA Amount"
}
```

#### 7. Summary Fields
**Business Purpose:**
- Track total incentive earnings
- Calculate net foreign exchange realization
- Used for financial reporting and forecasting

**Fields Added:**
```json
{
  "fieldname": "total_incentive_amount",
  "fieldtype": "Currency",
  "label": "Total Incentive Amount",
  "read_only": 1,
  "description": "Sum of all export incentives claimed"
},
{
  "fieldname": "net_foreign_exchange_realization",
  "fieldtype": "Currency",
  "label": "Net Foreign Exchange Realization",
  "read_only": 1,
  "description": "Total FOB Value + Total Incentives"
}
```

### Python Calculation Logic Restored

```python
def calculate_incentives(self):
    """Calculate all export incentives"""
    total_incentives = 0
    
    # RoDTEP
    if self.rodtep_claimed and self.rodtep_rate:
        self.rodtep_amount = flt(self.total_fob_value_inr) * flt(self.rodtep_rate) / 100
        total_incentives += self.rodtep_amount
    
    # RoSCTL
    if self.rosctl_claimed and self.rosctl_rate:
        self.rosctl_amount = flt(self.total_fob_value_inr) * flt(self.rosctl_rate) / 100
        total_incentives += self.rosctl_amount
    
    # MEIS (legacy)
    if self.meis_claimed and self.meis_rate:
        self.meis_amount = flt(self.total_fob_value_inr) * flt(self.meis_rate) / 100
        total_incentives += self.meis_amount
    
    # Duty Drawback (item-level)
    if self.duty_drawback_claimed:
        self.drawback_amount = sum(flt(item.drawback_amount) for item in self.items)
        total_incentives += self.drawback_amount
    
    # Advance Authorization
    if self.advance_authorization_no and self.aa_benefit_rate:
        self.aa_benefit_amount = flt(self.total_fob_value_inr) * flt(self.aa_benefit_rate) / 100
        total_incentives += self.aa_benefit_amount
    
    # EPCG
    if self.epcg_license_no and self.epcg_duty_saved:
        self.epcg_benefit_amount = flt(self.epcg_duty_saved)
        total_incentives += self.epcg_benefit_amount
    
    # Interest Subvention
    if self.interest_subvention_applicable and self.interest_subvention_rate:
        self.interest_subvention_amount = flt(self.total_fob_value_inr) * flt(self.interest_subvention_rate) / 100
        total_incentives += self.interest_subvention_amount
    
    # TMA
    if self.tma_applicable and self.tma_amount:
        total_incentives += flt(self.tma_amount)
    
    # Totals
    self.total_incentive_amount = total_incentives
    self.net_foreign_exchange_realization = flt(self.total_fob_value_inr) + total_incentives
```

---

## Financial Impact Examples

### Example 1: Textile Exporter
**Export Details:**
- FOB Value: ₹1 crore
- Product: Garments to USA

**Incentives:**
- RoDTEP (2%): ₹2 lakh
- RoSCTL (2.5%): ₹2.5 lakh
- Duty Drawback (1.5%): ₹1.5 lakh
- Interest Subvention (2%): ₹2 lakh
- **Total: ₹8 lakh (8% of FOB)**
- **Net Realization: ₹1.08 crore**

### Example 2: Machinery Exporter with EPCG
**Export Details:**
- FOB Value: ₹5 crore
- Product: Industrial machinery to Middle East
- EPCG License: Imported capital goods duty-free

**Incentives:**
- RoDTEP (0.8%): ₹4 lakh
- EPCG Duty Saved: ₹75 lakh (one-time, amortized)
- **Net Benefit: ₹79 lakh**

### Example 3: Agricultural Exporter
**Export Details:**
- FOB Value: ₹50 lakh
- Product: Fresh fruits to Europe

**Incentives:**
- RoDTEP (3%): ₹1.5 lakh
- TMA (7% of freight): ₹1.4 lakh
- **Total: ₹2.9 lakh (5.8% of FOB)**

---

## Compliance & Audit Trail

### Why Proper Field Tracking is Mandatory

1. **Government Audit Requirements:**
   - All incentive claims must be backed by shipping bills
   - DGFT (Director General of Foreign Trade) conducts audits
   - Mismatch = penalties, blacklisting

2. **Bank Documentation:**
   - Export finance linked to shipping bills
   - Banks verify FOB values and incentives
   - Required for realization certificate (BRC/FIRC)

3. **GST Refunds:**
   - IGST refund on exports requires shipping bill
   - LUT (Letter of Undertaking) tracked via shipping bill
   - Mismatch = GST notice, refund denial

4. **Income Tax Benefits:**
   - Section 80HHC deductions based on export incentives
   - Requires proper documentation in books
   - Incentive amount must match shipping bill

---

## Comparison: Before vs After

### Before (Fields Removed)
```python
# Certificate of Origin
- No FTA tracking
- No preferential certificate flag
- Fixed 180-day validity for all
- No lifecycle status tracking
❌ Cannot claim FTA duty benefits
❌ No expiry alerts
❌ Manual tracking required

# Shipping Bill
- Only RoDTEP and basic drawback
- No other incentive schemes
- No total realization tracking
❌ Incomplete financial picture
❌ Cannot track major schemes
❌ Compliance gaps
```

### After (Fields Restored)
```python
# Certificate of Origin
+ Preferential certificate tracking
+ FTA-specific validity periods
+ Automatic status updates
+ Expiry alerts
✅ Full FTA compliance
✅ Automated validity management
✅ Audit-ready

# Shipping Bill
+ All major incentive schemes
+ Total incentive calculation
+ Net forex realization
+ Complete audit trail
✅ Comprehensive financial tracking
✅ Government compliance ready
✅ Bank documentation complete
```

---

## Implementation Notes

### JSON Schema Changes

1. **Certificate of Origin:**
   - Added: Preferential Section (3 fields)
   - Modified: Validity calculation logic
   - Enhanced: Status tracking

2. **Shipping Bill:**
   - Added: 18 new incentive fields
   - Added: 2 summary fields
   - Organized: Collapsible sections for clarity

### Database Migration

When deploying, run:
```bash
bench migrate
```

This will:
- Add new columns to database tables
- Set default values for existing records
- Update meta cache

### Backward Compatibility

- All new fields have defaults
- Existing records won't break
- Fields are collapsible (don't clutter UI)
- Depends_on logic prevents mandatory issues

---

## Conclusion

The restored fields are not optional "nice-to-haves" - they represent:

1. **Legal Requirements:** FTA certificates, incentive documentation
2. **Financial Benefits:** 5-15% additional revenue through incentives
3. **Operational Efficiency:** Automated validity tracking, status updates
4. **Compliance:** Government audits, bank requirements, tax documentation

**Recommendation:** Keep all restored fields. They represent real-world export operations in India and are essential for a complete, production-ready import/export system.

---

## References

- [DGFT Foreign Trade Policy](https://www.dgft.gov.in/)
- [RoDTEP Scheme Guidelines](https://www.cbic.gov.in/resources//htdocs-cbec/customs/cs-circulars/cs-circulars-2021/Circular-No-43-2021.pdf)
- [RoSCTL Scheme for Textiles](https://texmin.nic.in/)
- [Advance Authorization Guidelines](https://www.dgft.gov.in/CP/?opt=aa)
- [EPCG Scheme Details](https://www.dgft.gov.in/CP/?opt=epcg)
- [India FTA Agreements](https://commerce.gov.in/international-trade/trade-agreements/)