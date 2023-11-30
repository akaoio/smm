// Copyright (c) 2023, MIMIZA and contributors
// For license information, please see license.txt

frappe.ui.form.on("API", {
  refresh: (form) => {
    website = frappe.urllib.get_base_url();

    fields = {
      website: website,
      //   redirect_uri: website + "/api/method/smm.libs.x.callback",
      terms_of_services: website + "/terms-of-services",
      privacy_policy: website + "/privacy-policy",
    };

    modules = {
      'X': 'x',
      'Facebook': 'facebook'
    }

    const toggleFields = (item) => {
      provider = item ? item?.target?.value : form.doc.provider;
      visibility = ['X', 'Facebook'].includes(provider) ? true : false;
      fields['redirect_uri'] = ['X', 'Facebook'].includes(provider) ? `${website}/api/method/smm.libs.${modules[provider]}.callback` : null
      for (let field in fields) {
        // Toggle field visibility
        form.fields_dict[field].$wrapper.toggle(visibility);
        // Set field data
        form.doc[field] = fields[field];
        // Rerender field
        form.fields_dict[field].refresh();
      }
    };

    toggleFields();

    form.fields_dict["provider"].$input.on("change", toggleFields);
  },
});
