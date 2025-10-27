frappe.ui.form.on('Sales Order', {
    refresh: function(frm) {
        // Only show for export customers
        if (frm.doc.docstatus === 1 && frm.doc.gst_category === "Overseas") {
            
            // Check if Commercial Invoice already exists
            frappe.call({
                method: 'frappe.client.get_list',
                args: {
                    doctype: 'Commercial Invoice Export',
                    filters: {
                        sales_order: frm.doc.name,
                        docstatus: ["<", 2],
                    },
                    fields: ['name'],
                    limit: 1
                },
                callback: function(r) {
                    if (r.message && r.message.length > 0) {
                        frm.add_custom_button(__('View Export Invoice'), function() {
                            frappe.set_route('Form', 'Commercial Invoice Export', r.message[0].name);
                        }, __('View'));
                    } else {
                        frm.add_custom_button(__('Create Export Invoice'), function() {
                            create_commercial_invoice(frm);
                        }, __('Create'));
                    }
                }
            });
        }
    },
    
    // Validation: Check if export customer has all required fields
    validate: function(frm) {
        if (frm.doc.gst_category === "Overseas") {
            // Check incoterm
            if (!frm.doc.incoterm) {
                frappe.msgprint(__('Incoterm is required for export orders'));
                frappe.validated = false;
            }
            
            // Check payment method
            // if (!frm.doc.payment_method) {
            //     frappe.msgprint(__('Payment Method is required for export orders'));
            //     frappe.validated = false;
            // }
            
            // Check if all items have HS codes
            let missing_hs_codes = [];
            frm.doc.items.forEach(function(item) {
                if (!item.gst_hsn_code) {
                    missing_hs_codes.push(item.item_code);
                }
            });
            
            if (missing_hs_codes.length > 0) {
                frappe.msgprint({
                    title: __('Missing HS Codes'),
                    message: __('Following items are missing HS codes: {0}', [missing_hs_codes.join(', ')]),
                    indicator: 'red'
                });
                frappe.validated = false;
            }
        }
    }
});

function create_commercial_invoice(frm) {
    frappe.confirm(
        __('Create Commercial Invoice Export from this Sales Order?'),
        function() {
            frappe.call({
                method: 'import_export.import_export.doctype.commercial_invoice_export.commercial_invoice_export.create_from_sales_order',
                args: {
                    sales_order: frm.doc.name
                },
                freeze: true,
                freeze_message: __('Creating Commercial Invoice...'),
                callback: function(r) {
                    if (r.message) {
                        frappe.msgprint({
                            title: __('Success'),
                            message: __('Commercial Invoice {0} created successfully', [r.message]),
                            indicator: 'green'
                        });
                        frappe.set_route('Form', 'Commercial Invoice Export', r.message);
                    }
                }
            });
        }
    );
}
