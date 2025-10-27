frappe.ui.form.on('Letter of Credit', {
    refresh: function(frm) {
        // Add custom buttons
        if (frm.doc.docstatus === 1) {
            
            // Add Amendment button
            if (!['Closed', 'Cancelled', 'Expired'].includes(frm.doc.status)) {
                frm.add_custom_button(__('Add Amendment'), function() {
                    add_amendment_dialog(frm);
                }, __('Actions'));
                
                frm.add_custom_button(__('Add Shipment'), function() {
                    add_shipment_dialog(frm);
                }, __('Actions'));
                
                frm.add_custom_button(__('Close LC'), function() {
                    close_lc_dialog(frm);
                }, __('Actions'));
            }
            
            // LC Summary button
            frm.add_custom_button(__('View Summary'), function() {
                show_lc_summary(frm);
            }, __('View'));
        }
        
        // Add indicators
        add_status_indicators(frm);
        
        // Show alerts for expiry
        check_expiry_alert(frm);
    },
    
    lc_amount: function(frm) {
        calculate_tolerance(frm);
        calculate_available_balance(frm);
    },
    
    tolerance_percentage: function(frm) {
        calculate_tolerance(frm);
        calculate_available_balance(frm);
    },
    
    opening_charges: function(frm) {
        calculate_total_charges(frm);
    },
    
    advising_charges_total: function(frm) {
        calculate_total_charges(frm);
    },
    
    confirmation_charges_total: function(frm) {
        calculate_total_charges(frm);
    },
    
    other_charges: function(frm) {
        calculate_total_charges(frm);
    }
});

// Child table events
frappe.ui.form.on('LC Shipment', {
    shipments_add: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        row.presentation_status = 'Pending';
    },
    
    invoice_amount: function(frm) {
        calculate_available_balance(frm);
    },
    
    shipments_remove: function(frm) {
        calculate_available_balance(frm);
    }
});

frappe.ui.form.on('LC Amendment', {
    charges: function(frm) {
        calculate_total_charges(frm);
    },
    
    amendments_remove: function(frm) {
        calculate_total_charges(frm);
    }
});

function calculate_tolerance(frm) {
    if (frm.doc.lc_amount && frm.doc.tolerance_percentage) {
        let tolerance = frm.doc.lc_amount * frm.doc.tolerance_percentage / 100;
        frm.set_value('tolerance_amount', tolerance);
    }
}

function calculate_available_balance(frm) {
    let max_amount = flt(frm.doc.lc_amount) + flt(frm.doc.tolerance_amount);
    let total_utilized = 0;
    
    if (frm.doc.shipments) {
        frm.doc.shipments.forEach(function(shipment) {
            if (['Presented', 'Accepted', 'Paid'].includes(shipment.presentation_status)) {
                total_utilized += flt(shipment.invoice_amount);
            }
        });
    }
    
    frm.set_value('total_utilized_amount', total_utilized);
    frm.set_value('available_balance', max_amount - total_utilized);
    frm.set_value('remaining_balance', max_amount - total_utilized);
}

function calculate_total_charges(frm) {
    let total = 0;
    total += flt(frm.doc.opening_charges);
    total += flt(frm.doc.advising_charges_total);
    total += flt(frm.doc.confirmation_charges_total);
    total += flt(frm.doc.other_charges);
    
    // Add amendment charges
    if (frm.doc.amendments) {
        frm.doc.amendments.forEach(function(amd) {
            if (amd.status === 'Approved') {
                total += flt(amd.charges);
            }
        });
        
        let amd_charges = frm.doc.amendments
            .filter(a => a.status === 'Approved')
            .reduce((sum, a) => sum + flt(a.charges), 0);
        frm.set_value('amendment_charges', amd_charges);
    }
    
    frm.set_value('total_charges', total);
}

function add_amendment_dialog(frm) {
    let d = new frappe.ui.Dialog({
        title: __('Add LC Amendment'),
        fields: [
            {
                fieldname: 'amendment_number',
                fieldtype: 'Data',
                label: __('Amendment Number'),
                reqd: 1
            },
            {
                fieldname: 'amendment_date',
                fieldtype: 'Date',
                label: __('Amendment Date'),
                reqd: 1,
                default: frappe.datetime.get_today()
            },
            {
                fieldname: 'amendment_type',
                fieldtype: 'Select',
                label: __('Amendment Type'),
                options: 'Amount Increase\nAmount Decrease\nExpiry Extension\nShipment Date Extension\nDocument Change\nBeneficiary Change\nTerms Change\nOther',
                reqd: 1
            },
            {
                fieldname: 'amendment_details',
                fieldtype: 'Text',
                label: __('Amendment Details'),
                reqd: 1
            },
            {
                fieldname: 'charges',
                fieldtype: 'Currency',
                label: __('Charges')
            }
        ],
        primary_action_label: __('Add Amendment'),
        primary_action: function(values) {
            frappe.call({
                method: 'import_export.import_export.doctype.letter_of_credit.letter_of_credit.add_amendment',
                args: {
                    lc_name: frm.doc.name,
                    amendment_number: values.amendment_number,
                    amendment_date: values.amendment_date,
                    amendment_type: values.amendment_type,
                    amendment_details: values.amendment_details,
                    charges: values.charges || 0
                },
                freeze: true,
                callback: function(r) {
                    frm.reload_doc();
                }
            });
            d.hide();
        }
    });
    d.show();
}

function add_shipment_dialog(frm) {
    let d = new frappe.ui.Dialog({
        title: __('Add Shipment'),
        fields: [
            {
                fieldname: 'shipment_number',
                fieldtype: 'Data',
                label: __('Shipment Number'),
                reqd: 1
            },
            {
                fieldname: 'shipment_date',
                fieldtype: 'Date',
                label: __('Shipment Date'),
                reqd: 1,
                default: frappe.datetime.get_today()
            },
            {
                fieldname: 'invoice_number',
                fieldtype: 'Link',
                options: 'Commercial Invoice Export',
                label: __('Commercial Invoice'),
                get_query: function() {
                    return {
                        filters: {
                            'docstatus': 1,
                            'sales_order': frm.doc.sales_order
                        }
                    };
                }
            },
            {
                fieldname: 'invoice_amount',
                fieldtype: 'Currency',
                label: __('Invoice Amount'),
                reqd: 1
            },
            {
                fieldname: 'bl_number',
                fieldtype: 'Data',
                label: __('B/L Number')
            },
            {
                fieldname: 'bl_date',
                fieldtype: 'Date',
                label: __('B/L Date')
            }
        ],
        primary_action_label: __('Add Shipment'),
        primary_action: function(values) {
            frappe.call({
                method: 'import_export.import_export.doctype.letter_of_credit.letter_of_credit.add_shipment',
                args: {
                    lc_name: frm.doc.name,
                    shipment_data: values
                },
                freeze: true,
                callback: function(r) {
                    frm.reload_doc();
                }
            });
            d.hide();
        }
    });
    d.show();
}

function close_lc_dialog(frm) {
    let d = new frappe.ui.Dialog({
        title: __('Close Letter of Credit'),
        fields: [
            {
                fieldname: 'closure_reason',
                fieldtype: 'Text',
                label: __('Closure Reason'),
                reqd: 1
            }
        ],
        primary_action_label: __('Close LC'),
        primary_action: function(values) {
            frappe.confirm(
                __('Are you sure you want to close this LC?'),
                function() {
                    frappe.call({
                        method: 'import_export.import_export.doctype.letter_of_credit.letter_of_credit.close_lc',
                        args: {
                            lc_name: frm.doc.name,
                            closure_reason: values.closure_reason
                        },
                        freeze: true,
                        callback: function(r) {
                            frm.reload_doc();
                        }
                    });
                }
            );
            d.hide();
        }
    });
    d.show();
}

function show_lc_summary(frm) {
    frappe.call({
        method: 'import_export.import_export.doctype.letter_of_credit.letter_of_credit.get_lc_summary',
        args: {
            lc_name: frm.doc.name
        },
        callback: function(r) {
            if (r.message) {
                let summary = r.message;
                let html = `
                    <div class="row">
                        <div class="col-md-6">
                            <h5>LC Utilization</h5>
                            <table class="table table-bordered">
                                <tr>
                                    <td><b>LC Amount</b></td>
                                    <td>${format_currency(summary.lc_amount, summary.currency)}</td>
                                </tr>
                                <tr>
                                    <td><b>Total Utilized</b></td>
                                    <td>${format_currency(summary.total_utilized, summary.currency)}</td>
                                </tr>
                                <tr>
                                    <td><b>Available Balance</b></td>
                                    <td class="text-success"><b>${format_currency(summary.available_balance, summary.currency)}</b></td>
                                </tr>
                                <tr>
                                    <td><b>Utilization %</b></td>
                                    <td>${summary.utilization_percentage.toFixed(2)}%</td>
                                </tr>
                            </table>
                        </div>
                        <div class="col-md-6">
                            <h5>Status & Expiry</h5>
                            <table class="table table-bordered">
                                <tr>
                                    <td><b>Status</b></td>
                                    <td>${summary.status}</td>
                                </tr>
                                <tr>
                                    <td><b>Expiry Date</b></td>
                                    <td>${frappe.datetime.str_to_user(summary.expiry_date)}</td>
                                </tr>
                                <tr>
                                    <td><b>Days to Expiry</b></td>
                                    <td class="${summary.days_to_expiry < 30 ? 'text-danger' : ''}">${summary.days_to_expiry} days</td>
                                </tr>
                                <tr>
                                    <td><b>Total Shipments</b></td>
                                    <td>${summary.total_shipments}</td>
                                </tr>
                                <tr>
                                    <td><b>Pending Presentations</b></td>
                                    <td>${summary.pending_presentations}</td>
                                </tr>
                                <tr>
                                    <td><b>Payments Pending</b></td>
                                    <td>${summary.payments_pending}</td>
                                </tr>
                            </table>
                        </div>
                    </div>
                `;
                
                frappe.msgprint({
                    title: __('LC Summary'),
                    message: html,
                    wide: true
                });
            }
        }
    });
}

function add_status_indicators(frm) {
    if (frm.doc.status === 'Expired') {
        frm.dashboard.add_indicator(__('Expired'), 'red');
    } else if (frm.doc.status === 'Fully Utilized') {
        frm.dashboard.add_indicator(__('Fully Utilized'), 'blue');
    } else if (frm.doc.status === 'Partially Utilized') {
        frm.dashboard.add_indicator(__('Partially Utilized'), 'orange');
    } else if (frm.doc.status === 'Active') {
        frm.dashboard.add_indicator(__('Active'), 'green');
    }
}

function check_expiry_alert(frm) {
    if (frm.doc.lc_expiry_date) {
        let days_to_expiry = frappe.datetime.get_day_diff(frm.doc.lc_expiry_date, frappe.datetime.get_today());
        
        if (days_to_expiry < 0) {
            frappe.show_alert({
                message: __('This LC has expired'),
                indicator: 'red'
            }, 10);
        } else if (days_to_expiry <= 15) {
            frappe.show_alert({
                message: __('LC expires in {0} days', [days_to_expiry]),
                indicator: 'orange'
            }, 10);
        } else if (days_to_expiry <= 30) {
            frappe.show_alert({
                message: __('LC expires in {0} days', [days_to_expiry]),
                indicator: 'yellow'
            }, 5);
        }
    }
}

// Shipment action buttons
frappe.ui.form.on('LC Shipment', {
    form_render: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        
        // Add action buttons in grid
        if (row.presentation_status === 'Pending') {
            // Show "Present Documents" button
            frm.fields_dict.shipments.grid.grid_rows_by_docname[cdn]
                .add_button(__('Present Documents'), function() {
                    present_documents_dialog(frm, cdn);
                }, 'btn-primary btn-xs');
        }
        
        if (row.presentation_status === 'Presented') {
            // Show "Accept" and "Mark Discrepancy" buttons
            frm.fields_dict.shipments.grid.grid_rows_by_docname[cdn]
                .add_button(__('Accept'), function() {
                    accept_documents(frm, cdn);
                }, 'btn-success btn-xs');
            
            frm.fields_dict.shipments.grid.grid_rows_by_docname[cdn]
                .add_button(__('Discrepancy'), function() {
                    mark_discrepancy_dialog(frm, cdn);
                }, 'btn-warning btn-xs');
        }
        
        if (row.presentation_status === 'Accepted') {
            // Show "Mark Payment" button
            frm.fields_dict.shipments.grid.grid_rows_by_docname[cdn]
                .add_button(__('Mark Payment'), function() {
                    mark_payment_dialog(frm, cdn);
                }, 'btn-success btn-xs');
        }
    }
});

function present_documents_dialog(frm, cdn) {
    let row = frappe.get_doc(frm.doctype, frm.docname).shipments.find(s => s.name === cdn);
    let idx = frm.doc.shipments.indexOf(row);
    
    let d = new frappe.ui.Dialog({
        title: __('Present Documents'),
        fields: [
            {
                fieldname: 'presentation_date',
                fieldtype: 'Date',
                label: __('Presentation Date'),
                reqd: 1,
                default: frappe.datetime.get_today()
            }
        ],
        primary_action_label: __('Present'),
        primary_action: function(values) {
            frappe.call({
                method: 'import_export.import_export.doctype.letter_of_credit.letter_of_credit.present_documents',
                args: {
                    lc_name: frm.doc.name,
                    shipment_idx: idx,
                    presentation_date: values.presentation_date
                },
                freeze: true,
                callback: function(r) {
                    frm.reload_doc();
                }
            });
            d.hide();
        }
    });
    d.show();
}

function accept_documents(frm, cdn) {
    let row = frappe.get_doc(frm.doctype, frm.docname).shipments.find(s => s.name === cdn);
    let idx = frm.doc.shipments.indexOf(row);
    
    frappe.confirm(
        __('Accept documents for shipment {0}?', [row.shipment_number]),
        function() {
            frappe.call({
                method: 'import_export.import_export.doctype.letter_of_credit.letter_of_credit.accept_documents',
                args: {
                    lc_name: frm.doc.name,
                    shipment_idx: idx
                },
                freeze: true,
                callback: function(r) {
                    frm.reload_doc();
                }
            });
        }
    );
}

function mark_discrepancy_dialog(frm, cdn) {
    let row = frappe.get_doc(frm.doctype, frm.docname).shipments.find(s => s.name === cdn);
    let idx = frm.doc.shipments.indexOf(row);
    
    let d = new frappe.ui.Dialog({
        title: __('Mark Discrepancy'),
        fields: [
            {
                fieldname: 'discrepancy_details',
                fieldtype: 'Text',
                label: __('Discrepancy Details'),
                reqd: 1
            }
        ],
        primary_action_label: __('Save Discrepancy'),
        primary_action: function(values) {
            frappe.call({
                method: 'import_export.import_export.doctype.letter_of_credit.letter_of_credit.mark_discrepancy',
                args: {
                    lc_name: frm.doc.name,
                    shipment_idx: idx,
                    discrepancy_details: values.discrepancy_details
                },
                freeze: true,
                callback: function(r) {
                    frm.reload_doc();
                }
            });
            d.hide();
        }
    });
    d.show();
}

function mark_payment_dialog(frm, cdn) {
    let row = frappe.get_doc(frm.doctype, frm.docname).shipments.find(s => s.name === cdn);
    let idx = frm.doc.shipments.indexOf(row);
    
    let d = new frappe.ui.Dialog({
        title: __('Mark Payment Received'),
        fields: [
            {
                fieldname: 'payment_date',
                fieldtype: 'Date',
                label: __('Payment Date'),
                reqd: 1,
                default: frappe.datetime.get_today()
            },
            {
                fieldname: 'payment_amount',
                fieldtype: 'Currency',
                label: __('Payment Amount'),
                reqd: 1,
                default: row.invoice_amount
            }
        ],
        primary_action_label: __('Mark Payment'),
        primary_action: function(values) {
            frappe.call({
                method: 'import_export.import_export.doctype.letter_of_credit.letter_of_credit.mark_payment_received',
                args: {
                    lc_name: frm.doc.name,
                    shipment_idx: idx,
                    payment_date: values.payment_date,
                    payment_amount: values.payment_amount
                },
                freeze: true,
                callback: function(r) {
                    frm.reload_doc();
                }
            });
            d.hide();
        }
    });
    d.show();
}