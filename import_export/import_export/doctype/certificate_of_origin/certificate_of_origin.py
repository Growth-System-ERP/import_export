import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, add_months, today, getdate, flt
from datetime import datetime, timedelta


class CertificateofOrigin(Document):
    def validate(self):
        self.validate_commercial_invoice()
        self.calculate_validity()
        self.set_status()
    
    def on_submit(self):
        self.status = "Submitted"
    
    def on_cancel(self):
        self.status = "Cancelled"
    
    def validate_commercial_invoice(self):
        """Validate that commercial invoice exists"""
        if not self.commercial_invoice:
            frappe.throw(_("Commercial Invoice is required"))
        
        ci_status = frappe.db.get_value(
            "Commercial Invoice Export", 
            self.commercial_invoice, 
            "docstatus"
        )
        
        if ci_status != 1:
            frappe.throw(_("Commercial Invoice must be submitted"))
    
    def calculate_validity(self):
        """Calculate validity period based on type of certificate and destination country"""

        # Default validity periods (in days)
        validity_periods = {
            # Non-preferential COO
            "Non-Preferential": 180,  # 6 months standard
            "Chamber of Commerce": 180,

            # Preferential COO (varies by agreement)
            "GSP": 365,  # Generalized System of Preferences - 1 year
            "FTA": 365,  # Free Trade Agreement - typically 1 year
            "SAFTA": 365,  # South Asian FTA
            "ASEAN": 365,
            "India-UAE CEPA": 365,
            "India-Japan CEPA": 365,
            "India-Korea CEPA": 365,
            "India-Singapore CECA": 365,

            # Special types
            "EUR.1": 120,  # EU certificate - 4 months
            "Form A": 365,  # GSP Form A
            "APTA": 365,  # Asia-Pacific Trade Agreement
            "MERCOSUR": 180,
            "Certificate of Indian Origin": 180,

            # Self-certification (under certain FTAs)
            "Self-Certification": 730  # 2 years for some agreements
        }

        # Get base validity period
        cert_type = self.certificate_type or "Non-Preferential"
        base_validity_days = validity_periods.get(cert_type, 180)

        # Adjust based on destination country requirements
        country_adjustments = {
            # Countries requiring shorter validity
            "Saudi Arabia": 120,  # 4 months for KSA
            "UAE": 180,
            "Egypt": 120,
            "Iran": 90,

            # Countries accepting longer validity
            "United States": 365,
            "Canada": 365,
            "Mexico": 365,
            "European Union": 120  # EUR.1 specific
        }

        # Check if destination country has specific requirements
        if self.destination_country in country_adjustments:
            base_validity_days = min(base_validity_days, country_adjustments[self.destination_country])

        # Special cases for preferential certificates
        if self.preferential_certificate:
            if self.agreement_type:
                # Check specific FTA requirements
                fta_validity = self.get_fta_specific_validity()
                if fta_validity:
                    base_validity_days = fta_validity

        # Calculate dates
        issue_date = getdate(self.issue_date) if self.issue_date else getdate(today())

        # Set validity start date (usually issue date)
        self.validity_start_date = issue_date

        # Calculate expiry date
        self.validity_end_date = add_days(issue_date, base_validity_days)

        # For some certificates, validity might be aligned to calendar year or quarter
        if cert_type in ["GSP", "Form A"]:
            # GSP certificates often valid till year-end
            self.validity_end_date = self.align_to_year_end(self.validity_end_date)

        # Set validity period in months for display
        self.validity_period_months = base_validity_days // 30

        # Set certificate status based on dates
        self.update_certificate_status()

        # Add remarks about validity
        self.add_validity_remarks()

    def get_fta_specific_validity(self):
        """Get FTA-specific validity period"""
        fta_validity_map = {
            "India-ASEAN FTA": 365,
            "India-Japan CEPA": 365,
            "India-Korea CEPA": 365,
            "India-Singapore CECA": 365,
            "India-Malaysia CECA": 365,
            "India-Thailand FTA": 365,
            "India-Sri Lanka FTA": 365,
            "India-MERCOSUR PTA": 180,
            "India-Chile PTA": 365,
            "India-UAE CEPA": 365,
            "India-Australia ECTA": 730,  # 2 years for self-certification
            "India-UK FTA": 365,  # When implemented
            "India-EU FTA": 120,  # EUR.1 movement certificate
            "SAFTA": 365,
            "APTA": 365
        }

        return fta_validity_map.get(self.agreement_type)

    def align_to_year_end(self, date):
        """Align validity to year-end for certain certificates"""
        from frappe.utils import getdate
        date_obj = getdate(date)

        # If the date is in the last quarter, extend to year-end
        if date_obj.month >= 10:
            return f"{date_obj.year}-12-31"

        return date

    def update_certificate_status(self):
        """Update certificate status based on validity and usage"""
        from frappe.utils import today, getdate

        current_date = getdate(today())

        if not self.validity_end_date:
            self.certificate_status = "Draft"
            return

        end_date = getdate(self.validity_end_date)

        # Check if expired
        if current_date > end_date:
            self.certificate_status = "Expired"
        # Check if expiring soon (within 30 days)
        elif (end_date - current_date).days <= 30:
            self.certificate_status = "Expiring Soon"
        # Check if used
        elif self.linked_shipping_bill:
            self.certificate_status = "Used"
        # Otherwise active
        else:
            self.certificate_status = "Active"

    def add_validity_remarks(self):
        """Add automated remarks about validity requirements"""
        remarks = []

        # Add type-specific remarks
        if self.certificate_type == "EUR.1":
            remarks.append("EUR.1 certificate valid for 4 months from issue date")
            remarks.append("Must be used for customs clearance within validity period")

        elif self.certificate_type == "GSP":
            remarks.append("GSP certificate valid till year-end")
            remarks.append("Renewal required for shipments in next calendar year")

        elif self.preferential_certificate and self.agreement_type:
            remarks.append(f"Issued under {self.agreement_type}")
            remarks.append("Preferential tariff treatment applicable within validity")

        # Add destination-specific remarks
        if self.destination_country == "Saudi Arabia":
            remarks.append("KSA requires COO to be attested by Saudi Embassy")
            remarks.append("Validity reduced to 4 months for Saudi shipments")

        # Add expiry warning
        if self.certificate_status == "Expiring Soon":
            remarks.append("⚠️ Certificate expiring soon - arrange renewal if needed")

        # Update remarks field
        if remarks:
            existing_remarks = self.remarks or ""
            self.remarks = existing_remarks + "\n" + "\n".join(remarks) if existing_remarks else "\n".join(remarks)
    
    def set_status(self):
        """Set document status"""
        if self.docstatus == 0:
            self.status = "Draft"
        elif self.docstatus == 1:
            # Check if attested
            if self.attestation_status == "Attested":
                self.status = "Attested"
            else:
                self.status = "Submitted"
            
            # Check if expired
            if self.valid_until and getdate(self.valid_until) < getdate():
                self.status = "Expired"
        elif self.docstatus == 2:
            self.status = "Cancelled"


@frappe.whitelist()
def get_products_from_commercial_invoice(commercial_invoice):
    """Fetch products from Commercial Invoice"""
    if not commercial_invoice:
        return []
    
    ci = frappe.get_doc("Commercial Invoice Export", commercial_invoice)
    products = []
    
    for item in ci.items:
        products.append({
            "item_code": item.item_code,
            "item_name": item.item_name,
            "description": item.description,
            "hs_code": item.hs_code,
            "quantity": item.qty,
            "uom": item.uom,
            "country_of_origin": item.country_of_origin,
            "value": item.amount
        })
    
    return products


@frappe.whitelist()
def update_attestation_status(certificate_name, status, attestation_number=None, attested_date=None):
    """Update attestation status from external system or manual entry"""
    doc = frappe.get_doc("Certificate of Origin", certificate_name)
    
    if status not in ["Submitted", "Attested", "Rejected"]:
        frappe.throw(_("Invalid status"))
    
    doc.attestation_status = status
    
    if status == "Attested":
        doc.attestation_number = attestation_number
        doc.attested_date = attested_date or frappe.utils.today()
    
    doc.save()
    
    return {"message": "Attestation status updated successfully"}

@frappe.whitelist()
def create_from_commercial_invoice(commercial_invoice):
    """Auto-create COO from CI"""

    ci = frappe.get_doc("Commercial Invoice Export", commercial_invoice)

    coo = frappe.new_doc("Certificate of Origin")
    coo.commercial_invoice = ci.name
    coo.company = ci.company
    coo.certificate_type = "Generic"

    # Copy exporter details
    coo.exporter_name = ci.exporter_name
    coo.exporter_address = ci.exporter_address
    coo.iec_code = ci.iec_code
    coo.country_of_export = ci.country_of_origin
    coo.port_of_loading = ci.port_of_loading

    # Copy consignee
    coo.consignee_name = ci.customer_name
    coo.consignee_address = ci.consignee_address
    coo.destination_country = ci.consignee_country
    coo.port_of_discharge = ci.port_of_discharge

    # Auto-populate products from CI items
    for item in ci.items:
        coo.append("products", {
            "item_code": item.item_code,
            "item_name": item.item_name,
            "description": item.description,
            "hs_code": item.hs_code,
            "quantity": item.qty,
            "uom": item.uom,
            "country_of_origin": item.country_of_origin or ci.country_of_origin,
            "value": item.amount
        })

    coo.insert()
    return coo.name
