// Copyright (c) 2023, MIMIZA and contributors
// For license information, please see license.txt

frappe.ui.form.on("Content", {
	refresh: (form) => {
        const length = (item) => {
            description = item ? item?.target?.value : form.doc.description;
            // Set field data
            form.doc["length"] = description.length;
            // Rerender field
            form.fields_dict["length"].refresh();
        };

        length();

        form.fields_dict["description"].$input.on("change", length);
	},
});
