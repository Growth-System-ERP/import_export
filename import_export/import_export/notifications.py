# File: import_export/import_export/notifications.py
# Notification configuration for export documents

import frappe
from frappe import _


def get_notification_config():
	"""Return notification configuration for export documents"""
	return {
		"for_doctype": {
			"Commercial Invoice Export": {
				"status": "Submitted",
				"docstatus": 1
			},
			"Shipping Bill": {
				"sb_status": ["Filed", "Assessed"],
				"docstatus": 1
			},
			"Certificate of Origin": {
				"attestation_status": ["Pending", "Submitted"],
				"docstatus": 1
			},
			"Bill of Entry": {
				"docstatus": 1
			}
		}
	}


@frappe.whitelist()
def send_certificate_expiry_alerts():
	"""Send alerts for certificates expiring soon (scheduled daily)"""
	from frappe.utils import add_days, today

	# Get certificates expiring in next 30 days
	expiring_certificates = frappe.get_all(
		"Certificate of Origin",
		filters={
			"docstatus": 1,
			"valid_until": ["between", [today(), add_days(today(), 30)]],
			"attestation_status": "Attested"
		},
		fields=["name", "certificate_no", "valid_until", "company"]
	)

	if not expiring_certificates:
		return

	# Group by company
	company_certs = {}
	for cert in expiring_certificates:
		if cert.company not in company_certs:
			company_certs[cert.company] = []
		company_certs[cert.company].append(cert)

	# Send notifications
	for company, certificates in company_certs.items():
		# Get export documentation managers for this company
		users = get_export_users(company)

		if not users:
			continue

		message = _("Following Certificates of Origin are expiring soon:\n")
		for cert in certificates:
			days_left = (cert.valid_until - frappe.utils.getdate(today())).days
			message += f"\n• {cert.certificate_no} (expires in {days_left} days)"

		# Send email and notification
		for user in users:
			create_notification(
				user=user,
				subject=_("Certificate of Origin Expiry Alert"),
				message=message,
				doctype="Certificate of Origin"
			)


@frappe.whitelist()
def send_lc_expiry_alerts():
	"""Send alerts for LCs expiring soon"""
	# TODO: Implement when LC Management doctype is created
	pass


def get_export_users(company=None):
	"""Get users with export documentation roles"""
	filters = {"role": ["in", ["Export Documentation Manager", "Shipping Coordinator", "System Manager"]]}

	if company:
		# Get users assigned to this company
		company_users = frappe.get_all(
			"User",
			filters={"company": company},
			pluck="name"
		)
		if company_users:
			filters["parent"] = ["in", company_users]

	users = frappe.get_all("Has Role", filters=filters, pluck="parent")
	return list(set(users))  # Remove duplicates


def create_notification(user, subject, message, doctype=None, document_name=None):
	"""Create notification log entry"""
	notification = frappe.get_doc({
		"doctype": "Notification Log",
		"for_user": user,
		"type": "Alert",
		"document_type": doctype,
		"document_name": document_name,
		"subject": subject,
		"email_content": message
	})
	notification.insert(ignore_permissions=True)

	# Optionally send email
	try:
		frappe.sendmail(
			recipients=[user],
			subject=subject,
			message=message,
			reference_doctype=doctype,
			reference_name=document_name
		)
	except Exception as e:
		frappe.log_error(f"Failed to send notification email: {str(e)}")


@frappe.whitelist()
def notify_customs_clearance(doctype, docname):
	"""Notify customs team about new submission"""
	doc = frappe.get_doc(doctype, docname)

	# Get customs users
	customs_users = frappe.get_all(
		"Has Role",
		filters={"role": "Customs User"},
		pluck="parent"
	)

	if not customs_users:
		frappe.msgprint(_("No customs users found to notify"), indicator="orange")
		return

	message = _("{0} {1} has been submitted and requires customs clearance.").format(
		doctype, docname
	)

	for user in customs_users:
		create_notification(
			user=user,
			subject=_("New {0} for Customs Clearance").format(doctype),
			message=message,
			doctype=doctype,
			document_name=docname
		)

	frappe.msgprint(_("Customs team notified successfully"), indicator="green")
