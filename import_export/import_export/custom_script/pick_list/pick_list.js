
frappe.ui.form.on('Pick List', {
    refresh: function(frm) {
        if (frm.doc.docstatus == 0) {
            frm.add_custom_button(__("Suggest Cartons"), function () {
                // suggest_cartons(frm);
                calculate_packing(frm);
            }, 'Packing');
        }

        if (frm.doc.carton_assignments?.length) {
            // 2D Visualization button (your existing one)
            frm.add_custom_button('Packing Visualization', function() {
                frappe.set_route('packing-visualize', frm.doc.name);
            }, 'Packing');
        }

        if (frm.doc.docstatus === 1 && frm.doc.carton_assignments && frm.doc.carton_assignments.length > 0) {
            
            // Check if this is linked to an export order
            if (frm.doc.work_order) return; // Skip if manufacturing
            
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Sales Order',
                    filters: { name: frm.doc.sales_order },
                    fieldname: 'gst_category'
                },
                callback: function(r) {
                    if (r.message && r.message.gst_category == "Overseas") {
                        
                        // Find Commercial Invoice
                        frappe.call({
                            method: 'frappe.client.get_list',
                            args: {
                                doctype: 'Commercial Invoice Export',
                                filters: {
                                    sales_order: frm.doc.sales_order,
                                    docstatus: 1
                                },
                                fields: ['name'],
                                limit: 1
                            },
                            callback: function(r) {
                                if (r.message && r.message.length > 0) {
                                    let ci_name = r.message[0].name;
                                    
                                    // Check if Packing List already exists
                                    frappe.call({
                                        method: 'frappe.client.get_count',
                                        args: {
                                            doctype: 'Packing List Export',
                                            filters: {
                                                delivery_note: frm.doc.name
                                            }
                                        },
                                        callback: function(r) {
                                            if (r.message === 0) {
                                                frm.add_custom_button(__('Create Export Packing List'), function() {
                                                    create_export_packing_list(frm, ci_name);
                                                }, __('Create'));
                                            }
                                        }
                                    });
                                }
                            }
                        });
                    }
                }
            });
        }
    }
});

function create_export_packing_list(frm, commercial_invoice) {
    frappe.confirm(
        __('Create Export Packing List from this Pick List?'),
        function() {
            frappe.call({
                method: 'import_export.import_export.doctype.packing_list_export.packing_list_export.create_from_pick_list',
                args: {
                    pick_list_name: frm.doc.name,
                    commercial_invoice: commercial_invoice
                },
                freeze: true,
                freeze_message: __('Creating Export Packing List...'),
                callback: function(r) {
                    if (r.message) {
                        frappe.msgprint({
                            title: __('Success'),
                            message: __('Packing List {0} created successfully', [r.message]),
                            indicator: 'green'
                        });
                        frappe.set_route('Form', 'Packing List Export', r.message);
                    }
                }
            });
        }
    );
}

function calculate_packing(frm) {
    frappe.prompt([
        {
            label: 'Packing Strategy',
            fieldname: 'strategy',
            fieldtype: 'Select',
            options: 'minimize_cartons\nminimize_waste\nmaximize_efficiency',
            default: 'minimize_cartons'
        }
    ], function(values) {
        frappe.call({
            method: 'import_export.packing_system.pick_list_packing.calculate_pick_list_packing',
            args: {
                pick_list_name: frm.doc.name,
                strategy: values.strategy,
                enable_3d: true
            },
            callback: function(r) {
                if (r.message && r.message.success) {
                    frm.reload_doc();
                    frappe.show_alert({
                        message: r.message.message,
                        indicator: 'green'
                    });
                }
            }
        });
    }, 'Select Packing Strategy', 'Calculate');
}
