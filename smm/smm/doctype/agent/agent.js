// Copyright (c) 2023, MIMIZA and contributors
// For license information, please see license.txt

function authorize_oauth_callback(response = {}) {
  const { authorization_url } = response.message;
  window.location = authorization_url;
}

frappe.ui.form.on("Agent", {
  authorize_oauth1: (form) => {
    frappe.call({
      method: "smm.libs.agent.authorize",
      args: {
        version: "oauth1",
        ...form.selected_doc,
      },
      callback: authorize_oauth_callback,
    });
  },
  authorize_oauth2: (form) => {
    frappe.call({
      method: "smm.libs.agent.authorize",
      args: {
        version: "oauth2",
        ...form.selected_doc,
      },
      callback: authorize_oauth_callback,
    });
  },
  profile: (form) => {
    frappe.call({
      method: "smm.libs.agent.profile",
      args: form.selected_doc,
    });
  },
  refresh_access_token: (form) => {
    frappe.call({
      method: "smm.libs.agent.refresh_access_token",
      args: form.selected_doc,
    });
  },
});
