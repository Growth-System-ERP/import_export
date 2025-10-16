// File: import_export/import_export/doctype/commercial_invoice_export/commercial_invoice_export.js
// Enhanced with status workflow display

frappe.ui.form.on('Commercial Invoice Export', {
    refresh: function(frm) {
        if (frm.doc.docstatus === 1) {
            // Show export readiness status
            show_export_readiness(frm);

            // Add create buttons for child documents
            add_create_buttons(frm);
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
    },

    sales_order: function(frm) {
        // Auto-populate items when sales order is selected
        if (frm.doc.sales_order && !frm.doc.items.length) {
            frappe.call({
                method: 'import_export.import_export.doctype.commercial_invoice_export.commercial_invoice_export.get_items_from_sales_order',
                args: {
                    sales_order: frm.doc.sales_order
                },
                callback: function(r) {
                    if (r.message && r.message.length > 0) {
                        frm.clear_table('items');
                        r.message.forEach(function(item) {
                            let row = frm.add_child('items');
                            Object.assign(row, item);
                        });
                        frm.refresh_field('items');
                        frappe.show_alert({
                            message: __('Items loaded from Sales Order'),
                                          indicator: 'green'
                        }, 3);
                    }
                }
            });
        }
    }
});


// ==================== EXPORT READINESS INDICATOR ====================

function show_export_readiness(frm) {
    frappe.call({
        method: 'import_export.import_export.doctype.commercial_invoice_export.commercial_invoice_export.get_export_readiness',
        args: { name: frm.doc.name },
        callback: function(r) {
            if (r.message) {
                let data = r.message;
                let completion = data.completion_percentage;

                // Add indicator to dashboard
                let indicator_color = completion === 100 ? 'green' :
                completion >= 75 ? 'blue' :
                completion >= 50 ? 'orange' : 'red';

                frm.dashboard.add_indicator(
                    __('Export Documents Ready: {0}%', [completion.toFixed(0)]),
                                            indicator_color
                );

                // Show detailed status
                let status_html = build_status_html(data.status, data.missing_documents);
                frm.dashboard.add_section(status_html, __('Export Documentation Status'));

                // Show completion message
                if (completion === 100) {
                    frappe.show_alert({
                        message: __('All export documents are ready for shipment!'),
                                      indicator: 'green'
                    }, 5);
                } else if (data.missing_documents.length > 0) {
                    frappe.msgprint({
                        title: __('Pending Documents'),
                                    message: __('Missing: {0}', [data.missing_documents.join(', ')]),
                                    indicator: 'orange'
                    });
                }
            }
        }
    });
}


function build_status_html(status, missing_documents) {
    let html = `
    <div class="row">
    <div class="col-md-12">
    <h5 style="margin-bottom: 15px;">Document Checklist</h5>
    <table class="table table-bordered" style="margin-bottom: 0;">
    <thead>
    <tr>
    <th width="40%">Document</th>
    <th width="15%">Status</th>
    <th width="15%">Submitted</th>
    <th width="30%">Action</th>
    </tr>
    </thead>
    <tbody>
    `;

    // Document order
    let doc_order = [
        'commercial_invoice',
        'packing_list',
        'certificate_of_origin',
        'shipping_bill',
        'bill_of_lading'
    ];

    let doc_labels = {
        'commercial_invoice': 'Commercial Invoice',
        'packing_list': 'Packing List',
        'certificate_of_origin': 'Certificate of Origin',
        'shipping_bill': 'Shipping Bill',
        'bill_of_lading': 'Bill of Lading'
    };

    doc_order.forEach(function(doc_key) {
        let doc_status = status[doc_key];
        let label = doc_labels[doc_key];

        let status_badge = doc_status.exists ?
        (doc_status.submitted ?
        '<span class="indicator-pill green">Submitted</span>' :
        '<span class="indicator-pill yellow">Draft</span>') :
        '<span class="indicator-pill red">Not Created</span>';

        let submitted_check = doc_status.submitted ?
        '<i class="fa fa-check text-success"></i>' :
        '<i class="fa fa-times text-muted"></i>';

        let action_html = '';
        if (doc_status.exists && doc_status.name) {
            let doctype_route = doc_key.replace(/_/g, '-');
            action_html = `<a href="/app/${doctype_route}/${doc_status.name}" target="_blank">View ${label}</a>`;
        } else {
            action_html = '<span class="text-muted">Not created yet</span>';
        }

        html += `
        <tr>
        <td><strong>${label}</strong></td>
        <td>${status_badge}</td>
        <td class="text-center">${submitted_check}</td>
        <td>${action_html}</td>
        </tr>
        `;
    });

    html += `
    </tbody>
    </table>
    </div>
    </div>
    `;

    return html;
}


// ==================== CREATE BUTTONS ====================

function add_create_buttons(frm) {
    let docs_to_create = [
        {
            doctype: 'Packing List Export',
            label: 'Packing List',
            filter_field: 'commercial_invoice',
            create_fn: create_packing_list
        },
        {
            doctype: 'Certificate of Origin',
            label: 'Certificate of Origin',
            filter_field: 'commercial_invoice',
            create_fn: create_certificate_of_origin
        },
        {
            doctype: 'Shipping Bill',
            label: 'Shipping Bill',
            filter_field: 'commercial_invoice',
            create_fn: create_shipping_bill
        },
        {
            doctype: 'Bill of Lading',
            label: 'Bill of Lading',
            filter_field: 'commercial_invoice',
            create_fn: create_bill_of_lading
        }
    ];

    docs_to_create.forEach(function(doc_info) {
        check_and_add_button(frm, doc_info);
    });
}


function check_and_add_button(frm, doc_info) {
    let filters = {};
    filters[doc_info.filter_field] = frm.doc.name;

    frappe.call({
        method: 'frappe.client.get_count',
        args: {
            doctype: doc_info.doctype,
            filters: filters
        },
        callback: function(r) {
            if (r.message === 0) {
                frm.add_custom_button(
                    __(doc_info.label),
                                      function() {
                                          doc_info.create_fn(frm);
                                      },
                                      __('Create')
                );
            } else {
                // Document exists, add view button
                frappe.call({
                    method: 'frappe.client.get_value',
                    args: {
                        doctype: doc_info.doctype,
                        filters: filters,
                        fieldname: 'name'
                    },
                    callback: function(r) {
                        if (r.message) {
                            frm.add_custom_button(
                                __('View {0}', [doc_info.label]),
                                                  function() {
                                                      frappe.set_route('Form', doc_info.doctype, r.message.name);
                                                  },
                                                  __('View')
                            );
                        }
                    }
                });
            }
        }
    });
}


// ==================== CREATE FUNCTIONS ====================

function create_packing_list(frm) {
    frappe.confirm(
        __('Create Packing List from this Commercial Invoice?'),
                   function() {
                       frappe.call({
                           method: 'import_export.import_export.doctype.commercial_invoice_export.commercial_invoice_export.create_next_document',
                           args: {
                               commercial_invoice: frm.doc.name,
                               doctype: 'Packing List Export'
                           },
                           freeze: true,
                           freeze_message: __('Creating Packing List...'),
                                   callback: function(r) {
                                       if (r.message) {
                                           frappe.show_alert({
                                               message: __('Packing List {0} created', [r.message]),
                                                             indicator: 'green'
                                           }, 3);
                                           frappe.set_route('Form', 'Packing List Export', r.message);
                                       }
                                   }
                       });
                   }
    );
}


function create_certificate_of_origin(frm) {
    frappe.confirm(
        __('Create Certificate of Origin from this Commercial Invoice?'),
                   function() {
                       frappe.call({
                           method: 'import_export.import_export.doctype.commercial_invoice_export.commercial_invoice_export.create_next_document',
                           args: {
                               commercial_invoice: frm.doc.name,
                               doctype: 'Certificate of Origin'
                           },
                           freeze: true,
                           freeze_message: __('Creating Certificate of Origin...'),
                                   callback: function(r) {
                                       if (r.message) {
                                           frappe.show_alert({
                                               message: __('Certificate of Origin {0} created', [r.message]),
                                                             indicator: 'green'
                                           }, 3);
                                           frappe.set_route('Form', 'Certificate of Origin', r.message);
                                       }
                                   }
                       });
                   }
    );
}


function create_shipping_bill(frm) {
    frappe.confirm(
        __('Create Shipping Bill from this Commercial Invoice?'),
                   function() {
                       frappe.call({
                           method: 'import_export.import_export.doctype.commercial_invoice_export.commercial_invoice_export.create_next_document',
                           args: {
                               commercial_invoice: frm.doc.name,
                               doctype: 'Shipping Bill'
                           },
                           freeze: true,
                           freeze_message: __('Creating Shipping Bill...'),
                                   callback: function(r) {
                                       if (r.message) {
                                           frappe.show_alert({
                                               message: __('Shipping Bill {0} created', [r.message]),
                                                             indicator: 'green'
                                           }, 3);
                                           frappe.set_route('Form', 'Shipping Bill', r.message);
                                       }
                                   }
                       });
                   }
    );
}


function create_bill_of_lading(frm) {
    // Check if Packing List exists first
    frappe.call({
        method: 'frappe.client.get_value',
        args: {
            doctype: 'Packing List Export',
            filters: {
                commercial_invoice: frm.doc.name,
                docstatus: 1
            },
            fieldname: 'name'
        },
        callback: function(r) {
            if (!r.message || !r.message.name) {
                frappe.msgprint({
                    title: __('Packing List Required'),
                                message: __('Bill of Lading requires Packing List to be created and submitted first. Please create Packing List.'),
                                indicator: 'orange'
                });
                return;
            }

            // Packing List exists, proceed with B/L creation
            frappe.confirm(
                __('Create Bill of Lading from Packing List?'),
                           function() {
                               frappe.call({
                                   method: 'import_export.import_export.doctype.commercial_invoice_export.commercial_invoice_export.create_next_document',
                                   args: {
                                       commercial_invoice: frm.doc.name,
                                       doctype: 'Bill of Lading'
                                   },
                                   freeze: true,
                                   freeze_message: __('Creating Bill of Lading...'),
                                           callback: function(r) {
                                               if (r.message) {
                                                   frappe.show_alert({
                                                       message: __('Bill of Lading {0} created', [r.message]),
                                                                     indicator: 'green'
                                                   }, 3);
                                                   frappe.set_route('Form', 'Bill of Lading', r.message);
                                               }
                                           }
                               });
                           }
            );
        }
    });
}
