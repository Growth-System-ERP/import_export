frappe.ui.form.on('Purchase Invoice', {
    refresh: function(frm) {
        if (frm.doc.docstatus === 1 && frm.doc.is_return === 0) {
            
            // Check if this is an import (supplier is from another country)
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Supplier',
                    filters: { name: frm.doc.supplier },
                    fieldname: 'country'
                },
                callback: function(r) {
                    if (r.message && r.message.country !== 'India') {
                        
                        // Check if Bill of Entry already exists
                        frappe.call({
                            method: 'frappe.client.get_count',
                            args: {
                                doctype: 'Bill of Entry',
                                filters: {
                                    purchase_invoice: frm.doc.name
                                }
                            },
                            callback: function(r) {
                                if (r.message === 0) {
                                    frm.add_custom_button(__('Create Bill of Entry'), function() {
                                        create_bill_of_entry(frm);
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

function create_bill_of_entry(frm) {
    let be = frappe.model.get_new_doc('Bill of Entry');
    be.purchase_invoice = frm.doc.name;
    be.be_type = 'For Home Consumption';
    
    frappe.set_route('Form', 'Bill of Entry', be.name);
}