// Copyright (c) 2023, MIMIZA and contributors
// For license information, please see license.txt

frappe.ui.form.on("Feed", {
  refresh: function (frm) {
    frm.events.check_provider_value(frm);
  },

  provider: function (frm) {
    frm.events.check_provider_value(frm);
  },

  check_provider_value: function (frm) {
    if (frm.doc.provider) {
      frappe.db.get_value(
        "Feed Provider",
        frm.doc.provider,
        "type",
        function (r) {
          if (r && r.type === "RSS") {
            frm.toggle_display(["description", "url"], true);
            frm.toggle_reqd(["description"], true);
          } else {
            frm.toggle_display(["description", "url"], false);
            frm.toggle_display(["preview", "image_url"], true);
          }
        }
      );
    } else {
      frm.toggle_display(["description", "url"], false);
    }
  },
});
