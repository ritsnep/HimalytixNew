/* global grapesjs */
(function () {
  function withStyles(editor) {
    const html = editor.getHtml();
    const css = editor.getCss();
    return `${html}<style>${css}</style>`;
  }

  function addBlocks(editor, fields = []) {
    const bm = editor.BlockManager;
    bm.add("text-block", {
      label: "Text",
      category: "Basics",
      attributes: { class: "gjs-fonts gjs-f-text" },
      content: "<p class='lead'>Editable text</p>",
    });
    bm.add("field-block", {
      label: "Field",
      category: "Data",
      attributes: { class: "gjs-fonts gjs-f-b1" },
      content: "<span>{{ field_name }}</span>",
    });
    bm.add("table-block", {
      label: "Lines Table",
      category: "Data",
      attributes: { class: "gjs-fonts gjs-f-table" },
      content:
        "<table class='table table-sm w-100'><thead><tr><th>Account</th><th>Debit</th><th>Credit</th></tr></thead><tbody><tr><td>{{ line.account_name }}</td><td>{{ line.debit }}</td><td>{{ line.credit }}</td></tr></tbody></table>",
    });
    bm.add("badge-block", {
      label: "Badge",
      category: "Decor",
      content: "<span class='badge bg-success'>Status</span>",
    });
    bm.add("image-block", {
      label: "Logo",
      category: "Decor",
      content: "<img src='https://dummyimage.com/140x40/111827/ffffff&text=Logo' alt='Logo' />",
    });
    bm.add("chart-block", {
      label: "Chart",
      category: "Data",
      attributes: { class: "gjs-fonts gjs-f-graph" },
      content:
        "<div class='chart-card' style='padding:12px;border:1px solid #e5e7eb;border-radius:10px;background:#0f172a;color:#e5e7eb;'>"
        + "<div style='font-weight:700;margin-bottom:6px;'>Chart</div>"
        + "<div class='chart-bars'>"
        + "{% templatetag openblock %} for bucket in chart_data {% templatetag closeblock %}"
        + "<div style='display:flex;align-items:center;gap:8px;margin-bottom:6px;'>"
        + "<span style='min-width:80px;'>{{ bucket.label }}</span>"
        + "<div style='flex:1;height:10px;background:#1f2937;border-radius:6px;overflow:hidden;'>"
        + "<div style='height:10px;background:#22c55e;width:{{ bucket.value }}%;'></div>"
        + "</div>"
        + "<span style='min-width:40px;text-align:right;'>{{ bucket.value }}</span>"
        + "</div>"
        + "{% templatetag openblock %} endfor {% templatetag closeblock %}"
        + "</div>"
        + "<div style='font-size:12px;color:#94a3b8;'>Chart renders as bars in PDF/HTML (no JS required).</div>"
        + "</div>",
    });
    if (fields.length) {
      bm.add("fields-list", {
        label: "Fields palette",
        category: "Data",
        content:
          "<ul class='list-unstyled'>" +
          fields
            .map((f) => `<li style=\"padding:4px 0;\">{{ ${f} }}</li>`)
            .join("") +
          "</ul>",
      });
    }
  }

  window.initReportDesigner = function initReportDesigner(options) {
    const editor = grapesjs.init({
      container: options.container || "#report-designer",
      height: options.height || "85vh",
      fromElement: false,
      storageManager: false,
      noticeOnUnload: true,
      panels: { defaults: [] },
      blockManager: {
        appendTo: options.blockContainer || null,
      },
      styleManager: {
        appendTo: options.styleContainer || null,
      },
      canvas: {
        styles: [
          "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css",
          "https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap",
          options.previewStyle || "",
        ].filter(Boolean),
      },
    });

    addBlocks(editor, options.availableFields || []);
    if (options.templateHtml) {
      editor.setComponents(options.templateHtml);
    }
    // Ensure a white canvas background
    const css = ".gjs-cv-canvas, .gjs-frame { background: #ffffff !important; }";
    editor.addComponents(`<style>${css}</style>`);

    editor.Commands.add("save-report-template", {
      run: function () {
        const payload = {
          html: withStyles(editor),
          css: editor.getCss(),
          components: editor.getComponents(),
        };
        if (typeof options.onSave === "function") {
          options.onSave(payload);
        } else {
          console.warn("No onSave handler supplied to initReportDesigner");
        }
      },
    });

    editor.Panels.addButton("options", {
      id: "save-report-template",
      className: "fa fa-save",
      command: "save-report-template",
      attributes: { title: "Save template" },
    });

    return editor;
  };
})();
