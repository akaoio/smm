// Copyright (c) 2023, MIMIZA and contributors
// For license information, please see license.txt

frappe.ui.form.on("Agent", {
  authorize_x: (form) => {
    frappe.call({
      method: "smm.libs.x.authorize",
      args: form.selected_doc,
      callback: (response) => {
        const { authorization_url } = response.message;
        window.location = authorization_url;
      },
    });
  },
  profile: (form) => {
    frappe.call({
      method: "smm.libs.x.authorize",
      args: form.selected_doc,
      callback: (response) => {
        const { authorization_url } = response.message;
        window.location = authorization_url;
      },
    });
  },
  refresh_access_token: (form) => {
    frappe.call({
      method: "smm.libs.x.authorize",
      args: form.selected_doc,
      callback: (response) => {
        const { authorization_url } = response.message;
        window.location = authorization_url;
      },
    });
  }
});
