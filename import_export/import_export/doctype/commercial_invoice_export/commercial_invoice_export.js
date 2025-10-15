frappe.ui.form.on('Commercial Invoice Export', {
    refresh: function(frm) {
        if (frm.doc.docstatus === 1) {

            // Create Packing List button
            check_and_add_button(frm, 'Packing List Export', 'commercial_invoice',
                                 'Packing List', create_packing_list);

            // Create Certificate of Origin button
            check_and_add_button(frm, 'Certificate of Origin', 'commercial_invoice',
                                 'Certificate of Origin', create_coo);

            // Create Shipping Bill button
            check_and_add_button(frm, 'Shipping Bill', 'commercial_invoice',
                                 'Shipping Bill', create_shipping_bill);

            // Create Bill of Lading button
            check_and_add_button(frm, 'Bill of Lading', 'bl_no',
                                 'Bill of Lading', create_bill_of_lading);

            // Show related documents section
            show_related_documents(frm);
        }
    },

    validate: function(frm) {
        // Validate that all items have HS codes
        let missing_hs = false;
        frm.doc.items.forEach(function(item) {
            if (!item.hs_code || item.hs_code.length < 6) {
                frappe.msgprint(__('Row {0}: HS Code is required and must be at least 6 digits', [item.idx]));
                missing_hs = true;
            }
        });

        if (missing_hs) {
            frappe.validated = false;
        }

        // Validate country of origin
        if (!frm.doc.country_of_origin) {
            frappe.msgprint(__('Country of Origin is required'));
            frappe.validated = false;
        }

        // Validate ports
        if (!frm.doc.port_of_loading || !frm.doc.port_of_discharge) {
            frappe.msgprint(__('Port of Loading and Port of Discharge are required'));
            frappe.validated = false;
        }
    }
});

function check_and_add_button(frm, doctype, filter_field, button_label, callback) {
    let filters = {};
    filters[filter_field] = frm.doc.name;

    frappe.call({
        method: 'frappe.client.get_count',
        args: {
            doctype: doctype,
            filters: filters
        },
        callback: function(r) {
            if (r.message === 0) {
                frm.add_custom_button(__(button_label), function() {
                    callback(frm);
                }, __('Create'));
            } else {
                // Show count and link to list
                frm.add_custom_button(__('{0} ({1})', [doctype, r.message]), function() {
                    frappe.set_route('List', doctype, filters);
                }, __('View'));
            }
        }
    });
}

function create_packing_list(frm) {
    // Check if Pick List exists
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Pick List',
            filters: {
                sales_order: frm.doc.sales_order,
                docstatus: 1
            },
            fields: ['name', 'total_cartons'],
            order_by: 'creation desc',
            limit: 1
        },
        callback: function(r) {
            if (r.message && r.message.length > 0) {
                let pick_list = r.message[0];

                // Check if packing calculation is done
                if (!pick_list.total_cartons || pick_list.total_cartons === 0) {
                    frappe.msgprint({
                        title: __('Packing Not Calculated'),
                                    message: __('Pick List {0} exists but packing calculation is not done. Please run packing calculation first.',
                                                [pick_list.name]),
                                                indicator: 'orange'
                    });
                    return;
                }

                // Create from Pick List
                frappe.call({
                    method: 'import_export.packing_list_export.create_from_pick_list',
                    args: {
                        pick_list_name: pick_list.name,
                        commercial_invoice: frm.doc.name
                    },
                    freeze: true,
                    freeze_message: __('Creating Packing List...'),
                            callback: function(r) {
                                if (r.message) {
                                    frappe.msgprint(__('Packing List {0} created successfully', [r.message]));
                                    frappe.set_route('Form', 'Packing List Export', r.message);
                                }
                            }
                });
            } else {
                frappe.msgprint({
                    title: __('No Pick List Found'),
                                message: __('Please create and pack a Pick List first from Sales Order {0}',
                                            [frm.doc.sales_order]),
                                            indicator: 'red'
                });
            }
        }
    });
}

function create_coo(frm) {
    let coo = frappe.model.get_new_doc('Certificate of Origin');
    coo.commercial_invoice = frm.doc.name;
    coo.certificate_type = 'Generic';
    coo.country_of_export = frm.doc.country_of_origin;
    coo.destination_country = frm.doc.consignee_country;

    frappe.set_route('Form', 'Certificate of Origin', coo.name);
}

function create_shipping_bill(frm) {
    let sb = frappe.model.get_new_doc('Shipping Bill');
    sb.commercial_invoice = frm.doc.name;
    sb.shipping_bill_type = 'Free Shipping Bill';
    sb.currency = frm.doc.currency;
    sb.exchange_rate = frm.doc.conversion_rate;

    frappe.set_route('Form', 'Shipping Bill', sb.name);
}

function create_bill_of_lading(frm) {
    let bl = frappe.model.get_new_doc('Bill of Lading');
    bl.commercial_invoice = frm.doc.name;
    bl.bl_type = 'Ocean Bill of Lading';

    frappe.set_route('Form', 'Bill of Lading', bl.name);
}

function show_related_documents(frm) {
    // Show related documents in a nice format
    let related_html = `
    <div class="row">
    <div class="col-md-12">
    <h5>Related Export Documents</h5>
    <div id="related-docs-container"></div>
    </div>
    </div>
    `;

    frm.dashboard.add_section(related_html, __('Related Documents'));

    // Fetch and display related docs
    let doctypes = [
        'Packing List Export',
        'Certificate of Origin',
        'Shipping Bill',
        'Bill of Lading'
    ];

    doctypes.forEach(function(doctype) {
        frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: doctype,
                filters: {
                    commercial_invoice: frm.doc.name
                },
                fields: ['name', 'status', 'creation'],
                order_by: 'creation desc'
            },
            callback: function(r) {
                if (r.message && r.message.length > 0) {
                    let html = `<strong>${doctype}:</strong> `;
                    r.message.forEach(function(doc) {
                        html += `<a href="/app/${doctype.toLowerCase().replace(/ /g, '-')}/${doc.name}">${doc.name}</a> `;
                    });
                    $('#related-docs-container').append(`<p>${html}</p>`);
                }
            }
        });
    });
}
