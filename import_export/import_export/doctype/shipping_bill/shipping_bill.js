frappe.ui.form.on('Shipping Bill', {
    onload: function(frm) {
        // Set filters
        frm.set_query('commercial_invoice', function() {
            return {
                filters: {
                    'docstatus': 1
                }
            };
        });

        // Color code based on status
        if (frm.doc.sb_status) {
            const status_colors = {
                'Draft': 'gray',
                'Filed': 'blue',
                'Registered': 'orange',
                'LEO Granted': 'green',
                'EGM Filed': 'green',
                'Closed': 'gray',
                'Cancelled': 'red'
            };

            frm.dashboard.add_indicator(
                __('Customs Status: {0}', [frm.doc.sb_status]),
                                        status_colors[frm.doc.sb_status] || 'gray'
            );
        }

        // Show customs processing timeline
        if (frm.doc.docstatus === 1) {
            frm.trigger('show_customs_timeline');
        }
    },

    refresh: function(frm) {
        // Add action buttons based on status
        if (frm.doc.docstatus === 1) {
            // File with customs
            if (!frm.doc.filing_date) {
                frm.add_custom_button(__('File with Customs'), function() {
                    frm.trigger('file_with_customs');
                }, __('Customs'));
            }

            // Get LEO
            if (frm.doc.filing_date && !frm.doc.leo_date) {
                frm.add_custom_button(__('Record LEO'), function() {
                    frm.trigger('record_leo');
                }, __('Customs'));
            }

            // Update EGM
            if (frm.doc.leo_date && !frm.doc.egm_filed) {
                frm.add_custom_button(__('Update EGM'), function() {
                    frm.trigger('update_egm');
                }, __('Customs'));
            }

            // Calculate incentives button
            frm.add_custom_button(__('Calculate Incentives'), function() {
                frm.call('calculate_incentives').then(() => {
                    frm.refresh();
                    frappe.show_alert({
                        message: __('Incentives calculated'),
                                      indicator: 'green'
                    });
                });
            });

            // Show incentive summary
            if (frm.doc.total_incentive_amount) {
                frm.dashboard.add_comment(
                    __('Total Incentives: ₹ {0}', [format_currency(frm.doc.total_incentive_amount)]),
                                          'green'
                );
            }
        }

        // Show LEO countdown if filed but LEO not received
        if (frm.doc.filing_date && !frm.doc.leo_date) {
            frm.trigger('show_leo_countdown');
        }
    },

    commercial_invoice: function(frm) {
        if (frm.doc.commercial_invoice) {
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'Commercial Invoice Export',
                    name: frm.doc.commercial_invoice
                },
                callback: function(r) {
                    if (r.message) {
                        // Auto-populate from commercial invoice
                        frm.set_value('exporter_name', r.message.exporter_name);
                        frm.set_value('exporter_address', r.message.exporter_address);
                        frm.set_value('iec_code', r.message.iec_code);
                        frm.set_value('exporter_gstin', r.message.gstin);
                        frm.set_value('consignee_name', r.message.customer_name);
                        frm.set_value('consignee_address', r.message.consignee_address);
                        frm.set_value('destination_country', r.message.consignee_country);
                        frm.set_value('port_of_loading', r.message.port_of_loading);
                        frm.set_value('port_of_discharge', r.message.port_of_discharge);
                        frm.set_value('currency', r.message.currency);
                        frm.set_value('exchange_rate', r.message.conversion_rate);

                        // Copy items
                        frm.clear_table('items');
                        (r.message.items || []).forEach(item => {
                            let row = frm.add_child('items');
                            row.item_code = item.item_code;
                            row.description = item.description;
                            row.hs_code = item.hs_code;
                            row.quantity = item.qty;
                            row.uom = item.uom;
                            row.fob_value_fc = item.amount;
                            row.assessable_value = item.amount * frm.doc.exchange_rate;
                        });
                        frm.refresh_field('items');

                        // Calculate totals
                        frm.trigger('calculate_totals');
                    }
                }
            });
        }
    },

    file_with_customs: function(frm) {
        frappe.prompt([
            {
                label: 'Filing Date',
                fieldname: 'filing_date',
                fieldtype: 'Date',
                default: frappe.datetime.nowdate(),
                    reqd: 1
            },
            {
                label: 'Customs Reference',
                fieldname: 'reference',
                fieldtype: 'Data',
                reqd: 1
            },
            {
                label: 'Port Code',
                fieldname: 'port_code',
                fieldtype: 'Data',
                description: '6-digit Indian customs port code',
                reqd: 1
            }
        ], function(values) {
            frappe.call({
                method: 'frappe.client.set_value',
                args: {
                    doctype: frm.doctype,
                    name: frm.docname,
                    fieldname: {
                        'filing_date': values.filing_date,
                        'shipping_bill_no': values.reference,
                        'port_code': values.port_code,
                        'sb_status': 'Filed'
                    }
                },
                callback: function() {
                    frm.reload_doc();
                    frappe.show_alert({
                        message: __('Shipping Bill filed with customs'),
                                      indicator: 'green'
                    });
                }
            });
        }, __('File with Customs'), __('Submit'));
    },

    record_leo: function(frm) {
        frappe.prompt([
            {
                label: 'LEO Date',
                fieldname: 'leo_date',
                fieldtype: 'Datetime',
                default: frappe.datetime.now_datetime(),
                    reqd: 1,
                    description: 'Let Export Order date and time'
            },
            {
                label: 'LEO Number',
                fieldname: 'leo_number',
                fieldtype: 'Data',
                reqd: 1
            },
            {
                label: 'Customs Officer',
                fieldname: 'officer',
                fieldtype: 'Data'
            }
        ], function(values) {
            frappe.call({
                method: 'frappe.client.set_value',
                args: {
                    doctype: frm.doctype,
                    name: frm.docname,
                    fieldname: {
                        'leo_date': values.leo_date,
                        'leo_number': values.leo_number,
                        'customs_officer': values.officer,
                        'sb_status': 'LEO Granted'
                    }
                },
                callback: function() {
                    frm.reload_doc();
                    frappe.show_alert({
                        message: __('LEO (Let Export Order) recorded successfully'),
                                      indicator: 'green'
                    });
                }
            });
        }, __('Record LEO'), __('Submit'));
    },

    update_egm: function(frm) {
        frappe.prompt([
            {
                label: 'EGM Filing Date',
                fieldname: 'egm_date',
                fieldtype: 'Date',
                default: frappe.datetime.nowdate(),
                    reqd: 1,
                    description: 'Export General Manifest filing date'
            },
            {
                label: 'EGM Number',
                fieldname: 'egm_number',
                fieldtype: 'Data',
                reqd: 1
            },
            {
                label: 'IGM Number (at destination)',
                      fieldname: 'igm_number',
                      fieldtype: 'Data',
                      description: 'Import General Manifest at destination port'
            }
        ], function(values) {
            frappe.call({
                method: 'frappe.client.set_value',
                args: {
                    doctype: frm.doctype,
                    name: frm.docname,
                    fieldname: {
                        'egm_filed': 1,
                        'egm_date': values.egm_date,
                        'egm_number': values.egm_number,
                        'igm_number': values.igm_number,
                        'sb_status': 'EGM Filed'
                    }
                },
                callback: function() {
                    frm.reload_doc();
                    frappe.show_alert({
                        message: __('EGM updated successfully'),
                                      indicator: 'green'
                    });
                }
            });
        }, __('Update EGM'), __('Submit'));
    },

    show_customs_timeline: function(frm) {
        let html = '<div class="customs-timeline">';

        const steps = [
            {
                name: 'Filed',
                done: frm.doc.filing_date,
                date: frm.doc.filing_date,
                ref: frm.doc.shipping_bill_no
            },
            {
                name: 'LEO Granted',
                done: frm.doc.leo_date,
                date: frm.doc.leo_date,
                ref: frm.doc.leo_number
            },
            {
                name: 'Goods Exported',
                done: frm.doc.departure_date,
                date: frm.doc.departure_date
            },
            {
                name: 'EGM Filed',
                done: frm.doc.egm_filed,
                date: frm.doc.egm_date,
                ref: frm.doc.egm_number
            }
        ];

        steps.forEach((step, idx) => {
            const status_class = step.done ? 'completed' : 'pending';
            html += `
            <div class="timeline-item ${status_class}">
            <div class="timeline-badge">${idx + 1}</div>
            <div class="timeline-content">
            <h5>${step.name}</h5>
            ${step.done ? `
                <p>Date: ${step.date || 'N/A'}</p>
                ${step.ref ? `<p>Ref: ${step.ref}</p>` : ''}
                ` : '<p>Pending</p>'}
                </div>
                </div>
                `;
        });

        html += '</div>';

        // Add CSS
        html += `
        <style>
        .customs-timeline {
            display: flex;
            justify-content: space-between;
            margin: 20px 0;
            padding: 15px;
            background: #f5f5f5;
            border-radius: 8px;
        }
        .timeline-item {
            flex: 1;
            text-align: center;
            position: relative;
        }
        .timeline-badge {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 16px;
        }
        .timeline-item.completed .timeline-badge {
            background: #28a745;
            color: white;
        }
        .timeline-item.pending .timeline-badge {
            background: #e0e0e0;
            color: #666;
        }
        .timeline-content {
            margin-top: 10px;
        }
        .timeline-content h5 {
            margin: 5px 0;
            font-size: 14px;
            font-weight: 600;
        }
        .timeline-content p {
            margin: 2px 0;
            font-size: 11px;
            color: #666;
        }
        </style>
        `;

        // Add to form
        if (!frm.fields_dict['customs_timeline_html']) {
            frm.add_custom_button(__('Show Timeline'), function() {
                frappe.msgprint(html, __('Customs Processing Timeline'));
            });
        }
    },

    show_leo_countdown: function(frm) {
        if (frm.doc.filing_date) {
            const filed_date = frappe.datetime.str_to_obj(frm.doc.filing_date);
            const now = new Date();
            const hours_passed = Math.floor((now - filed_date) / (1000 * 60 * 60));
            const hours_remaining = Math.max(0, 24 - hours_passed);

            if (hours_remaining > 0) {
                frm.dashboard.add_comment(
                    __('LEO expected within {0} hours', [hours_remaining]),
                                          hours_remaining < 6 ? 'orange' : 'blue'
                );
            } else {
                frm.dashboard.add_comment(
                    __('LEO is overdue by {0} hours', [Math.abs(hours_remaining)]),
                                          'red'
                );
            }
        }
    },

    calculate_totals: function(frm) {
        let total_fc = 0;
        let total_inr = 0;

        frm.doc.items.forEach(item => {
            item.fob_value_inr = flt(item.fob_value_fc) * flt(frm.doc.exchange_rate);
            total_fc += flt(item.fob_value_fc);
            total_inr += flt(item.fob_value_inr);
        });

        frm.set_value('total_fob_value_fc', total_fc);
        frm.set_value('total_fob_value_inr', total_inr);
        frm.refresh_field('items');
    },

    // Incentive rate handlers
    rodtep_rate: function(frm) {
        if (frm.doc.rodtep_claimed) {
            frm.call('calculate_incentives');
        }
    },

    duty_drawback_claimed: function(frm) {
        if (frm.doc.duty_drawback_claimed) {
            frappe.show_alert({
                message: __('Enter drawback rates for each item'),
                              indicator: 'blue'
            });
        }
    }
});// Copyright (c) 2025, gws and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Shipping Bill", {
// 	refresh(frm) {

// 	},
// });
