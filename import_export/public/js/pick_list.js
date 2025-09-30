// Updated pick_list.js with Three.js integration

// frappe.require("packing_visualizer.bundle.js");

frappe.ui.form.on("Pick List", {
    refresh: function (frm) {
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
    }
});


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

// function suggest_cartons(frm) {
//     frappe.call({
//         method: "import_export.packing_system.main_controller.suggest_cartons",
//         args: {
//             doc_data: JSON.stringify(frm.doc),
//         },
//         callback: r => {
//             console.log(r);
//             if (!r.exc) {
//                 frappe.show_alert({
//                     message: __("Packing Completed!"),
//                                   indicator: 'green'
//                 });
//
//                 frm.set_value("carton_assignments", r.message.carton_assignments);
//                 frm.set_value("locations", r.message.locations);
//                 frm.dirty();
//
//                 // Auto-show 3D visualization if available
//                 setTimeout(() => {
//                     check_and_show_3d(frm);
//                 }, 1000);
//             }
//         }
//     });
// }
//
// function check_and_show_3d(frm) {
//     frappe.call({
//         method: 'import_export.packing_system.utils.visualize.get_threejs_visualization',
//         args: { docname: frm.doc.name },
//         callback: function(r) {
//             if (r.message && r.message.success && r.message.has_3d) {
//                 // Ask user if they want to see 3D view
//                 frappe.confirm(
//                     __('3D visualization is available. Would you like to view it?'),
//                                () => show_threejs_visualization(frm)
//                 );
//             }
//         }
//     });
// }
//
// function show_threejs_visualization(frm) {
//     frappe.call({
//         method: 'import_export.packing_system.utils.visualize.get_threejs_visualization',
//         args: { docname: frm.doc.name },
//         callback: function(r) {
//             if (r.message.success) {
//                 // Use the class
//                 const viz = new import_export.utils.visualizer();
//                 viz.init(r.message.data);
//             }
//         }
//     });
// }
//
// // Your existing 2D visualization (keep as fallback)
// function show_stored_packing_viz(frm) {
//     frappe.call({
//         method: 'import_export.packing_system.utils.visualize.show_carton_visualization',
//         args: { docname: frm.doc.name },
//         callback: function(r) {
//             if (r.message.success) {
//                 let d = new frappe.ui.Dialog({
//                     title: __('📦 Packing Visualization (2D)'),
//                                              fields: [{
//                                                  fieldtype: 'HTML',
//                                                  fieldname: 'viz_html',
//                                                  options: r.message.html
//                                              }],
//                                              size: 'extra-large'
//                 });
//                 d.show();
//             } else {
//                 frappe.msgprint(r.message.message);
//             }
//         }
//     });
// }
