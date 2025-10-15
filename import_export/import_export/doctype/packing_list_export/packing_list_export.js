frappe.ui.form.on('Packing List Export', {
    refresh: function(frm) {
        if (frm.doc.cartons && frm.doc.cartons.length > 0) {
            frm.add_custom_button(__('View 3D Packing'), function() {
                show_3d_visualization(frm);
            }, __('Tools'));
        }
    }
});

function show_3d_visualization(frm) {
    let d = new frappe.ui.Dialog({
        title: __('3D Packing Visualization'),
                                 size: 'extra-large',
                                 fields: [
                                     {
                                         fieldtype: 'HTML',
                                         fieldname: 'visualization_html'
                                     }
                                 ]
    });

    // Get 3D data for first carton
    frappe.call({
        method: 'import_export.packing_list_export.get_3d_visualization_data',
        args: {
            packing_list_name: frm.doc.name,
            carton_idx: 0
        },
        callback: function(r) {
            if (r.message) {
                // Render 3D visualization
                // (Reuse your existing 3D viewer component)
                let html = `
                <div id="packing-3d-viewer" style="width: 100%; height: 600px;">
                <p>Loading 3D visualization...</p>
                <p>Carton: ${r.message.carton.carton_name}</p>
                <p>Total Patterns: ${r.message.total_patterns}</p>
                </div>
                `;
                d.fields_dict.visualization_html.$wrapper.html(html);

                // Initialize your 3D viewer here with r.message data
                // window.render3DPacking(r.message);
            }
        }
    });

    d.show();
}
