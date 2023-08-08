// Copyright (c) 2023, MIMIZA and contributors
// For license information, please see license.txt

frappe.ui.form.on("Network Activity", {
  setup: (frm) => {
    frm.set_query("content", function (doc, cdt, cdn) {
      let d = locals[cdt][cdn];
      return {
        filters: {
          mechanism: d.mechanism,
        },
      };
    });
  },
});
