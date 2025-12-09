const templateHtml = `{{ template_html|escapejs }}`;
const starter = templateHtml && templateHtml.trim() ? templateHtml : `
    <section style="padding:24px;">
        <header style="border-bottom:1px solid #e5e7eb;margin-bottom:16px;">
            <h2 style="margin:0 0 4px;font-size:20px;">{{ title }}</h2>
            <div style="color:#6b7280;font-size:13px;">Organization: {{ organization }} • Generated: {{ generated_at }}</div>
        </header>
        <div style="margin-bottom:12px;font-weight:600;">Journal Lines</div>
        <table style="width:100%;border-collapse:collapse;font-size:13px;">
            <thead>
                <tr>
                    <th style="text-align:left;border-bottom:1px solid #e5e7eb;padding:6px;">Date</th>
                    <th style="text-align:left;border-bottom:1px solid #e5e7eb;padding:6px;">Journal #</th>
                    <th style="text-align:left;border-bottom:1px solid #e5e7eb;padding:6px;">Account</th>
                    <th style="text-align:right;border-bottom:1px solid #e5e7eb;padding:6px;">Debit</th>
                    <th style="text-align:right;border-bottom:1px solid #e5e7eb;padding:6px;">Credit</th>
                </tr>
            </thead>
            <tbody>
                {% templatetag openblock %} for line in flat_rows {% templatetag closeblock %}
                <tr>
                    <td style="padding:6px;border-bottom:1px solid #f1f5f9;">{{ line.0 }}</td>
                    <td style="padding:6px;border-bottom:1px solid #f1f5f9;">{{ line.1 }}</td>
                    <td style="padding:6px;border-bottom:1px solid #f1f5f9;">{{ line.4 }}</td>
                    <td style="padding:6px;text-align:right;border-bottom:1px solid #f1f5f9;">{{ line.6 }}</td>
                    <td style="padding:6px;text-align:right;border-bottom:1px solid #f1f5f9;">{{ line.7 }}</td>
                </tr>
                {% templatetag openblock %} endfor {% templatetag closeblock %}
            </tbody>
        </table>
    </section>`;
const initialTemplateHtml = starter;
const fields = JSON.parse(document.getElementById("designer-fields").textContent || "[]");
let previewRows = JSON.parse(document.getElementById("designer-preview").textContent || "[]");
const fieldListEl = document.getElementById("field-list");
const previewContainer = document.getElementById("preview-list");
const templatePicker = document.getElementById("template-picker");

function renderPreview(rows) {
    previewContainer.innerHTML = "";
    rows.forEach(row => {
        const card = document.createElement("div");
        card.className = "preview-card";
        const label = row.journal_number || row.account_code || row.account_name || row.journal_type || "Row";
        card.innerHTML = `<div class="fw-semibold">${label}</div>
            <div class="small text-muted mb-1">${row.journal_date || row.period || ""}</div>
            <div class="small">Values: ${Object.keys(row).length}</div>`;
        previewContainer.appendChild(card);
    });
}

const openVar = "{% templatetag openvariable %}";
const closeVar = "{% templatetag closevariable %}";
function renderFields(filterText = "") {
    fieldListEl.innerHTML = "";
    const normalized = filterText.toLowerCase();
    const matching = fields.filter(f => !normalized || f.toLowerCase().includes(normalized));
    matching.forEach(f => {
        const badge = document.createElement("div");
        badge.className = "field-badge";
        badge.textContent = `${openVar} ${f} ${closeVar}`;
        badge.title = "Click to copy";
        badge.addEventListener("click", () => {
            navigator.clipboard?.writeText(`${openVar} ${f} ${closeVar}`);
        });
        fieldListEl.appendChild(badge);
    });
    document.getElementById("field-count").textContent = matching.length;
}

renderFields();
document.getElementById("field-filter").addEventListener("input", (e) => renderFields(e.target.value));
renderPreview(previewRows);

const designer = initReportDesigner({
    container: "#report-designer",
    templateHtml: starter,
    availableFields: fields,
    blockContainer: "#gjs-blocks",
    styleContainer: "#gjs-styles",
    height: "80vh",
});

const csrfToken = document.querySelector('input[name="csrfmiddlewaretoken"]')?.value || "{{ csrf_token }}";

function loadGallery() {
    const url = "{% url 'reporting:report_template_api' %}?code={{ definition.code }}&include_gallery=1";
    fetch(url, { credentials: "same-origin" })
        .then(resp => resp.json())
        .then(data => {
            if (data.gallery) {
                templatePicker.innerHTML = '<option value=\"\">Load gallery template…</option>';
                data.gallery.forEach(t => {
                    const opt = document.createElement("option");
                    opt.value = t.id;
                    opt.textContent = t.name;
                    templatePicker.appendChild(opt);
                });
            }
        })
        .catch(() => {});
}
loadGallery();

templatePicker.addEventListener("change", () => {
    const id = templatePicker.value;
    if (!id) return;
    const url = "{% url 'reporting:report_template_api' %}?code={{ definition.code }}&template_id=" + id;
    fetch(url, { credentials: "same-origin" })
        .then(resp => resp.json())
        .then(data => {
            if (data.template_html) {
                designer.setComponents(data.template_html);
            }
        });
});

document.getElementById("reset-template").addEventListener("click", () => {
    designer.setComponents(initialTemplateHtml);
});

const blocksPanel = document.getElementById("blocks-panel");
const stylesPanel = document.getElementById("styles-panel");
document.getElementById("toggle-blocks").addEventListener("click", () => {
    blocksPanel.classList.toggle("active");
    stylesPanel.classList.remove("active");
});
document.getElementById("toggle-styles").addEventListener("click", () => {
    stylesPanel.classList.toggle("active");
    blocksPanel.classList.remove("active");
});

document.getElementById("refresh-sample").addEventListener("click", () => {
    fetch("{% url 'reporting:report_sample_api' %}?code={{ definition.code }}", { credentials: "same-origin" })
        .then(resp => resp.json())
        .then(data => {
            if (data.rows) {
                previewRows = data.rows;
                renderPreview(previewRows);
            }
        });
});

document.getElementById("save-template").addEventListener("click", function() {
    const payload = {
        code: "{{ definition.code }}",
        template_html: designer.getHtml() + "<style>" + designer.getCss() + "</style>",
        template_json: {},
        engine: "django",
        is_custom_enabled: true
    };
    fetch("{% url 'reporting:report_template_api' %}", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken
        },
        body: JSON.stringify(payload)
    }).then(resp => resp.json().then(data => ({ status: resp.status, body: data })))
      .then(result => {
          if (result.status >= 200 && result.status < 300) {
              alert("Template saved.");
              loadGallery();
          } else {
              alert("Save failed: " + (result.body.detail || result.status));
          }
      })
      .catch(err => alert("Save failed: " + err));
});