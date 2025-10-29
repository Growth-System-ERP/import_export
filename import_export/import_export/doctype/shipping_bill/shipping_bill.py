import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class ShippingBill(Document):
    def validate(self):
        if self.port_code and len(self.port_code) != 6:
            frappe.msgprint(
                _("Port Code should be 6 digits as per Indian customs format"),
                indicator="orange",
                alert=True,
            )

        self.validate_commercial_invoice()
        self.calculate_totals()
        self.calculate_incentives()
        self.set_status()

    def on_submit(self):
        self.status = "Submitted"

        if self.commercial_invoice:
            frappe.db.set_value(
                "Commercial Invoice Export",
                self.commercial_invoice,
                "custom_shipping_bill_no",
                self.name,
            )

    def on_cancel(self):
        self.status = "Cancelled"
        if self.commercial_invoice:
            frappe.db.set_value(
                "Commercial Invoice Export",
                self.commercial_invoice,
                "custom_shipping_bill_no",
                "",
            )

    def validate_commercial_invoice(self):
        """Validate commercial invoice exists and is submitted"""
        if not self.commercial_invoice:
            frappe.throw(_("Commercial Invoice is required"))

        ci_status = frappe.db.get_value(
            "Commercial Invoice Export", self.commercial_invoice, "docstatus"
        )

        if ci_status != 1:
            frappe.throw(_("Commercial Invoice must be submitted"))

    def calculate_totals(self):
        """Calculate FOB values from items"""
        self.total_fob_value_inr = 0
        self.total_fob_value_fc = 0

        for item in self.items:
            if not item.fob_value_inr:
                item.fob_value_inr = flt(item.fob_value_fc) * flt(self.exchange_rate)

            self.total_fob_value_inr += flt(item.fob_value_inr)
            self.total_fob_value_fc += flt(item.fob_value_fc)

            # Calculate drawback for each item
            if item.drawback_rate and item.assessable_value:
                item.drawback_amount = (
                    flt(item.assessable_value) * flt(item.drawback_rate) / 100
                )

    def calculate_incentives(self):
        """Calculate export incentives based on FOB value and incentive schemes"""
        if not self.total_fob_value_inr:
            return

        total_incentives = 0

        # RoDTEP (Remission of Duties and Taxes on Exported Products)
        if self.rodtep_claimed and self.rodtep_rate:
            rodtep_amount = flt(self.total_fob_value_inr) * flt(self.rodtep_rate) / 100
            self.rodtep_amount = rodtep_amount
            total_incentives += rodtep_amount

        # RoSCTL (Rebate of State and Central Taxes and Levies)
        if self.rosctl_claimed and self.rosctl_rate:
            rosctl_amount = flt(self.total_fob_value_inr) * flt(self.rosctl_rate) / 100
            self.rosctl_amount = rosctl_amount
            total_incentives += rosctl_amount

        # MEIS (Merchandise Exports from India Scheme) - legacy scheme
        if self.meis_claimed and self.meis_rate:
            meis_amount = flt(self.total_fob_value_inr) * flt(self.meis_rate) / 100
            self.meis_amount = meis_amount
            total_incentives += meis_amount

        # Duty Drawback - sum from items
        if self.duty_drawback_claimed:
            total_drawback = sum(flt(item.drawback_amount) for item in self.items)
            self.drawback_amount = total_drawback
            total_incentives += total_drawback

        # Advance Authorization benefit (if applicable)
        if self.advance_authorization_no and self.aa_benefit_rate:
            aa_benefit = flt(self.total_fob_value_inr) * flt(self.aa_benefit_rate) / 100
            self.aa_benefit_amount = aa_benefit
            total_incentives += aa_benefit

        # EPCG benefit calculation (if applicable)
        if self.epcg_license_no and self.epcg_duty_saved:
            self.epcg_benefit_amount = flt(self.epcg_duty_saved)
            total_incentives += flt(self.epcg_duty_saved)

        # Interest Subvention (if applicable for certain sectors)
        if self.interest_subvention_applicable and self.interest_subvention_rate:
            interest_subvention = (
                flt(self.total_fob_value_inr) * flt(self.interest_subvention_rate) / 100
            )
            self.interest_subvention_amount = interest_subvention
            total_incentives += interest_subvention

        # TMA (Transport and Marketing Assistance) for specified agriculture products
        if self.tma_applicable and self.tma_amount:
            # TMA amount is usually manually entered based on product and destination
            # or calculated separately based on freight
            total_incentives += flt(self.tma_amount)

        # Set total incentives
        self.total_incentive_amount = total_incentives

        # Calculate net realization
        self.net_foreign_exchange_realization = (
            flt(self.total_fob_value_inr) + total_incentives
        )

    def set_status(self):
        """Set document status"""
        if self.docstatus == 0:
            self.status = "Draft"
        elif self.docstatus == 1:
            if self.sb_status == "Cleared":
                self.status = "Cleared"
            elif self.sb_status == "Filed":
                self.status = "Filed"
            else:
                self.status = "Submitted"
        elif self.docstatus == 2:
            self.status = "Cancelled"


@frappe.whitelist()
def get_items_from_commercial_invoice(commercial_invoice):
    """Fetch items from Commercial Invoice for Shipping Bill"""
    if not commercial_invoice:
        return []

    ci = frappe.get_doc("Commercial Invoice Export", commercial_invoice)

    items = []
    for item in ci.items:
        items.append(
            {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "description": item.description,
                "hs_code": item.hs_code,
                "quantity": item.qty,
                "uom": item.uom,
                "fob_value_fc": item.amount,
                "fob_value_inr": flt(item.amount) * flt(ci.conversion_rate),
                "assessable_value": flt(item.amount) * flt(ci.conversion_rate),
            }
        )

    return items


@frappe.whitelist()
def update_customs_status(
    shipping_bill_name,
    sb_status,
    leo_date=None,
    shipping_bill_no=None,
    assessment_date=None,
):
    """Update customs processing status"""
    doc = frappe.get_doc("Shipping Bill", shipping_bill_name)

    if sb_status not in ["Filed", "Assessed", "Cleared", "Shipped", "Rejected"]:
        frappe.throw(_("Invalid status"))

    doc.sb_status = sb_status

    if shipping_bill_no:
        doc.shipping_bill_no = shipping_bill_no

    if leo_date:
        doc.leo_date = leo_date

    if assessment_date:
        doc.assessment_date = assessment_date

    doc.save()

    return {"message": "Status updated successfully"}


@frappe.whitelist()
def create_from_commercial_invoice(commercial_invoice):
    """Create Shipping Bill from Commercial Invoice"""

    ci = frappe.get_doc("Commercial Invoice Export", commercial_invoice)

    # Check if CI is submitted
    if ci.docstatus != 1:
        frappe.throw(_("Commercial Invoice must be submitted first"))

    # Check if already exists
    existing = frappe.db.exists(
        "Shipping Bill",
        {"commercial_invoice": commercial_invoice, "docstatus": ["!=", 2]},
    )

    if existing:
        frappe.throw(_("Shipping Bill already exists: {0}").format(existing))

    # Create Shipping Bill
    sb = frappe.new_doc("Shipping Bill")
    sb.commercial_invoice = ci.name
    sb.company = ci.company
    sb.shipping_bill_date = frappe.utils.today()
    sb.shipping_bill_type = "Free Shipping Bill"  # Default, user can change

    # Port code - needs to be set by user (6-digit Indian customs code)
    # sb.port_code = ""  # User must enter

    # Exporter details
    sb.exporter_name = ci.exporter_name
    sb.exporter_address = ci.exporter_address
    sb.iec_code = ci.iec_code
    sb.exporter_gstin = ci.exporter_gstin
    sb.exporter_pan = ci.exporter_pan

    # Consignee details
    sb.consignee_name = ci.customer_name
    sb.consignee_address = ci.consignee_address
    sb.destination_country = ci.consignee_country
    sb.port_of_discharge = ci.port_of_discharge
    sb.final_destination = ci.final_destination

    # Shipping details
    sb.port_of_loading = ci.port_of_loading
    sb.mode_of_shipment = "Sea"  # Default, user can change
    sb.vessel_flight_no = ci.vessel_flight_no
    sb.container_nos = ci.container_nos

    # Currency details
    sb.currency = ci.currency
    sb.exchange_rate = ci.conversion_rate

    # Copy items
    for item in ci.items:
        sb.append(
            "items",
            {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "description": item.description,
                "hs_code": item.hs_code,
                "quantity": item.qty,
                "uom": item.uom,
                "fob_value_fc": item.amount,
                "fob_value_inr": flt(item.amount) * flt(ci.conversion_rate),
                "assessable_value": flt(item.amount) * flt(ci.conversion_rate),
            },
        )

    # Calculate totals
    sb.total_fob_value_fc = ci.total_fob_value
    sb.total_fob_value_inr = flt(ci.total_fob_value) * flt(ci.conversion_rate)
    sb.freight_charges = ci.freight_charges
    sb.insurance_charges = ci.insurance_charges

    sb.insert()

    frappe.msgprint(
        _("Shipping Bill created. Please update Port Code and customs details."),
        indicator="blue",
        alert=True,
    )

    return sb.name
