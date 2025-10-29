import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class BillofLading(Document):
    def validate(self):
        if self.bl_no and not self.bl_no.strip():
            frappe.throw(_("B/L Number cannot be empty"))

        self.validate_commercial_invoice()
        self.calculate_totals()
        self.set_status()

    def on_submit(self):
        self.bl_status = "Issued"

        if self.commercial_invoice:
            ci = frappe.get_doc("Commercial Invoice Export", self.commercial_invoice)
            ci.db_set("bill_of_lading_no", self.bl_no)
            ci.db_set("bl_date", self.bl_date)

    def on_cancel(self):
        self.bl_status = "Cancelled"

        if self.commercial_invoice:
            ci = frappe.get_doc("Commercial Invoice Export", self.commercial_invoice)
            ci.db_set("bill_of_lading_no", "")
            ci.db_set("bl_date", "")

    def validate_commercial_invoice(self):
        """Validate commercial invoice exists"""
        if not self.commercial_invoice:
            frappe.throw(_("Commercial Invoice is required"))

        ci_status = frappe.db.get_value(
            "Commercial Invoice Export", self.commercial_invoice, "docstatus"
        )

        if ci_status != 1:
            frappe.throw(_("Commercial Invoice must be submitted"))

    def calculate_totals(self):
        """Calculate totals from containers"""
        if not self.containers:
            return

        self.total_packages = sum(
            flt(container.no_of_packages) for container in self.containers
        )

        self.total_gross_weight = sum(
            flt(container.gross_weight) for container in self.containers
        )

    def set_status(self):
        """Set document status"""
        if self.docstatus == 0:
            self.bl_status = "Draft"
        elif self.docstatus == 1:
            self.bl_status = "Issued"
        elif self.docstatus == 2:
            self.bl_status = "Cancelled"


@frappe.whitelist()
def get_containers_from_packing_list(commercial_invoice):
    """Get container details from Packing List"""
    if not commercial_invoice:
        return []

    # Find packing list linked to this commercial invoice
    packing_lists = frappe.get_all(
        "Packing List Export",
        filters={"commercial_invoice": commercial_invoice, "docstatus": 1},
        limit=1,
    )

    if not packing_lists:
        return []

    packing_list = frappe.get_doc("Packing List Export", packing_lists[0].name)

    # Get container info from Commercial Invoice
    ci = frappe.get_doc("Commercial Invoice Export", commercial_invoice)

    containers = []
    if ci.container_nos:
        # Parse container numbers (comma-separated)
        container_numbers = [c.strip() for c in ci.container_nos.split(",")]

        for container_no in container_numbers:
            containers.append(
                {
                    "container_no": container_no,
                    "seal_no": "",  # To be filled manually
                    "container_size": packing_list.container_size or "40ft",
                    "container_type": "Dry",
                    "no_of_packages": int(packing_list.total_cartons)
                    if packing_list.total_cartons
                    else 0,
                    "gross_weight": flt(packing_list.total_gross_weight),
                }
            )

    return containers


@frappe.whitelist()
def surrender_bl(bl_name):
    """Mark B/L as surrendered (for telex release)"""
    doc = frappe.get_doc("Bill of Lading", bl_name)

    if doc.docstatus != 1:
        frappe.throw(_("Only submitted B/L can be surrendered"))

    doc.bl_status = "Surrendered"
    doc.save()

    return {"message": "B/L surrendered successfully"}


@frappe.whitelist()
def create_from_packing_list(packing_list_name):
    """
    Create Bill of Lading from Packing List
    This ensures we have accurate container and carton data
    """

    pl = frappe.get_doc("Packing List Export", packing_list_name)

    # Validate Packing List is submitted
    if pl.docstatus != 1:
        frappe.throw(_("Packing List must be submitted first"))

    # Get Commercial Invoice
    if not pl.commercial_invoice:
        frappe.throw(_("Packing List must be linked to a Commercial Invoice"))

    ci = frappe.get_doc("Commercial Invoice Export", pl.commercial_invoice)

    # Check if B/L already exists for this CI
    existing = frappe.db.exists(
        "Bill of Lading", {"commercial_invoice": ci.name, "docstatus": ["!=", 2]}
    )

    if existing:
        frappe.throw(_("Bill of Lading already exists: {0}").format(existing))

    # Create Bill of Lading
    bl = frappe.new_doc("Bill of Lading")
    bl.commercial_invoice = ci.name
    bl.company = ci.company
    bl.bl_date = frappe.utils.today()
    bl.bl_type = "Ocean Bill of Lading"  # Default

    # Carrier details - user must enter
    bl.vessel_flight_no = ci.vessel_flight_no

    # Shipper (Exporter) details
    bl.shipper_name = ci.exporter_name
    bl.shipper_address = ci.exporter_address
    bl.shipper_email = ci.exporter_email
    bl.shipper_contact = ci.exporter_phone

    # Consignee details
    bl.consignee_name = ci.customer_name
    bl.consignee_address = ci.consignee_address
    bl.consignee_email = ci.consignee_email
    bl.consignee_contact = ci.consignee_phone

    # Notify party
    if ci.notify_party_name:
        bl.notify_party_name = ci.notify_party_name
        bl.notify_party_address = ci.notify_party_address
        bl.notify_party_email = ci.notify_party_email
        bl.notify_party_contact = ci.notify_party_phone
    else:
        bl.notify_party_name = ci.customer_name
        bl.notify_party_address = ci.consignee_address

    # Routing details
    bl.port_of_loading = ci.port_of_loading
    bl.port_of_discharge = ci.port_of_discharge
    bl.place_of_receipt = ci.place_of_receipt
    bl.final_destination = ci.final_destination
    bl.place_of_delivery = ci.final_destination or ci.port_of_discharge

    # Cargo description from items
    cargo_items = []
    for item in ci.items[:5]:  # First 5 items
        cargo_items.append(f"{item.item_name} ({item.qty} {item.uom})")

    cargo_desc = "Export of " + ", ".join(cargo_items)
    if len(ci.items) > 5:
        cargo_desc += f" and {len(ci.items) - 5} more items"

    bl.goods_description = cargo_desc
    bl.marks_and_numbers = ci.shipping_marks

    # Package details from Packing List
    bl.total_packages = int(pl.total_cartons) if pl.total_cartons else 0
    bl.package_type = pl.packing_method or "Cartons"
    bl.total_gross_weight = pl.total_gross_weight
    bl.total_volume = pl.total_volume_cbm

    # Container details from Packing List and CI
    if ci.container_nos:
        container_numbers = [c.strip() for c in ci.container_nos.split(",")]
        seal_numbers = []
        if ci.seal_nos:
            seal_numbers = [s.strip() for s in ci.seal_nos.split(",")]

        packages_per_container = (
            int(pl.total_cartons / len(container_numbers))
            if len(container_numbers) > 0
            else pl.total_cartons
        )
        weight_per_container = (
            pl.total_gross_weight / len(container_numbers)
            if len(container_numbers) > 0
            else pl.total_gross_weight
        )

        for idx, container_no in enumerate(container_numbers):
            bl.append(
                "containers",
                {
                    "container_no": container_no,
                    "seal_no": seal_numbers[idx] if idx < len(seal_numbers) else "",
                    "container_size": pl.container_size or "40ft",
                    "container_type": "Dry",  # Default
                    "no_of_packages": packages_per_container,
                    "gross_weight": weight_per_container,
                },
            )

    # Freight details
    bl.freight_terms = (
        "Prepaid" if ci.incoterm in ["CIF", "CFR", "CPT", "CIP"] else "Collect"
    )
    bl.freight_charges = ci.freight_charges
    bl.currency = ci.currency

    # Originals
    bl.no_of_originals = "3"  # Standard

    bl.insert()

    frappe.msgprint(
        _(
            "Bill of Lading created from Packing List. Please update B/L Number and Carrier details."
        ),
        indicator="green",
        alert=True,
    )

    return bl.name
