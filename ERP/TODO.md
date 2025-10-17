TODO – Accounting Module & Journal Entry (Production Ready)

Scope: Fix Journal Entry UI (formset/HTMX), harden backend, add tests (unit/integration/e2e), wire CI, and prep deployment.

0) Ground Rules

IDs must be unique. No duplicate id="form-2-row" and no visible __prefix__ in live rows.

Never swap <body>. Target scoped containers only.

Formset indices are source of truth. Update lines-TOTAL_FORMS when adding. Use can_delete for removals.

1) Frontend: Formset/DOM Hygiene

 Introduce single empty form template

Add a <template id="line-empty-form"> containing the full <tr> with __prefix__ placeholders and a hidden lines-__prefix__-DELETE.

Remove all visible __prefix__ rows from DOM.

Acceptance: On initial render, only indexed rows (0..N-1) exist. No __prefix__ in DOM.

 Fix management form counts

Ensure hidden fields: lines-TOTAL_FORMS, lines-INITIAL_FORMS, lines-MIN_NUM_FORMS, lines-MAX_NUM_FORMS are present and correct.

Acceptance: Server accepts POST without “missing form” errors when adding/removing rows.

 Add Row (client-side or server-side)

Option A (client clone): JS clones <template>, replaces __prefix__ with current TOTAL_FORMS, appends row, increments TOTAL_FORMS.

Option B (server render): Button uses hx-post="/accounting/journals/add-line/" with hx-vals='js:{index: TOTAL_FORMS}', server returns one row; after swap, increment TOTAL_FORMS in htmx:afterOnLoad.

Acceptance: Add Row works repeatedly; TOTAL_FORMS increments each time.

 Remove Row (can_delete)

Include hidden lines-<i>-DELETE.

On trash click, set value to on and add .d-none on row (keep indices stable).

Acceptance: Removed rows are excluded server-side; no renumbering is required.

2) HTMX Contracts

 Form submit target

Change <form id="journal-form" hx-target="#page-content-wrapper" hx-swap="innerHTML">.

Acceptance: Submitting does not reload the full page or kill scripts.

 Validation panel

Keep a single <div id="validation-panel">.

Set hx-post="/accounting/journal/validate/" hx-trigger="load, change from:#journal-form" hx-include="#journal-form" hx-target="#validation-panel" hx-swap="innerHTML".

Change “Reference” field to hit validate, not create.

Acceptance: Changes anywhere in form re-render validation results; no duplicate IDs.

 Preview/aux actions

Any preview (e.g., ledger preview) should return a partial into a modal container (#modal-container).

Acceptance: No full-page swaps for previews.

3) Totals, UX & Accessibility

 Totals recalculation

JS listener on input[type="number"] inside tbody; sum debit/credit, compute imbalance.

Ignore rows with .d-none (deleted).

Acceptance: Totals update instantly on every change; imbalance style toggles correctly.

 Currency columns

Short-term: Either render a real <select name="lines-<i>-currency"> + auto exchange_rate=1 for base, or hide both columns if not ready.

Acceptance: No required field warnings for invisible/unused currency cells.

 Header badges

Remove the duplicate static “New” badge; keep only one status badge container updated by server.

Acceptance: Single, accurate badge.

 Side panel toggle

Implement .panel-collapsed toggle for both header button and mobile FAB.

Acceptance: Panel opens/closes consistently on desktop & mobile.

 A11y quick wins

One aria-live region for totals.

Keep <legend class="visually-hidden"> on fieldsets.

Ensure resize handles aren’t focus traps.

Acceptance: Keyboard users can traverse and operate the grid; screen readers announce totals.

4) Server: Views/Services/Validation

 /accounting/journals/add-line/

Accept index, return a single <tr> with correct names/ids.

Acceptance: Works with HTMX Option A.

 /accounting/journal/validate/

Bind form + formset; return rendered validation partial.

List field-specific errors per row and non-field errors (e.g., imbalance).

Acceptance: Server validation converges with client; no mismatch.

 /accounting/journals/create/

Accept full post; validate:

balanced debit/credit

period/fiscal checks

permissions

can_delete removals

On success:

persist draft or post per workflow

return redirect via HX-Redirect to detail page or success partial

Acceptance: Clean round trips; descriptive errors surface in validation panel.

 Posting rules

Lock journal type numbering (select_for_update) during post.

Deny posts into closed periods and raise user-facing errors.

Acceptance: No duplicate numbers; no illegal posts.

5) Testing (must-have)

 Unit tests

Posting service: balanced, unbalanced, period closed, permission denied.

Formset clean: add/remove, delete flags respected.

Currency: base vs non-base (if enabled).

Acceptance: Coverage ≥ 80% for accounting services/models.

 Integration tests

Full UI flow with Django test client: create → validate → submit → post.

HTMX endpoints: add-line, validate return correct fragments.

Acceptance: End-to-end passes with realistic payloads.

 E2E smoke (optional but ideal)

Playwright/Cypress: Add rows, edit amounts, see totals update, submit, view ledger impact.

Acceptance: Works in headless CI.

6) Performance

 Seed large dataset

≥ 20k GL rows, ≥ 500 accounts.

 Benchmarks

Journal post ≤ 1s for ≤ 50 lines.

Trial balance ≤ 2s for 10k rows.

 Indexes

Ensure GL, account, period fields are indexed.

 Acceptance: Meets or beats targets; document slow paths.

7) CI/CD & Linting

 GitHub Actions

Jobs: lint (flake8/ruff), test, coverage report, optional e2e.

 Enforce coverage threshold

Fail under 80% (configurable).

 Artifacts

Upload HTML coverage, test logs.

 Acceptance: PRs must be green to merge.

8) Definition of Done (this feature)

 No duplicate IDs or visible __prefix__ rows.

 Add/remove works repeatedly; TOTAL_FORMS is correct.

 Validation panel reflects live form state; server & client in sync.

 Totals accurate; “Balanced” state obvious.

 Submit does not nuke page state; redirects or fragments only.

 All tests pass; coverage ≥ 80%.

 Performance thresholds met.

 QA sign-off on a11y & responsiveness.

9) Drop-in Snippets (ready to paste)
Add Row (client – no round trip)
<template id="line-empty-form">… __prefix__ …</template>
<button type="button" id="add-row" class="btn btn-sm btn-light"><i class="fas fa-plus"></i> Add Row</button>
<script>
(() => {
  const tbody = document.querySelector("#journal-grid-body");
  const totalForms = document.querySelector("#id_lines-TOTAL_FORMS");
  const tpl = document.querySelector("#line-empty-form");
  document.getElementById("add-row")?.addEventListener("click", () => {
    const idx = parseInt(totalForms.value, 10);
    const html = tpl.innerHTML.replaceAll("__prefix__", idx);
    tbody.insertAdjacentHTML("beforeend", html);
    totalForms.value = idx + 1;
    document.dispatchEvent(new Event("recalc-totals"));
  });
})();
</script>

Remove Row (can_delete)
document.querySelector("#journal-grid-body").addEventListener("click", (e) => {
  const btn = e.target.closest(".remove-row");
  if (!btn) return;
  const tr = btn.closest("tr.journal-line-row");
  const del = tr.querySelector('[name$="-DELETE"]');
  if (del) del.value = "on";
  tr.classList.add("d-none");
  document.dispatchEvent(new Event("recalc-totals"));
});

Totals
(() => {
  const tbody = document.querySelector("#journal-grid-body");
  const td = document.getElementById("total-debit");
  const tc = document.getElementById("total-credit");
  const im = document.querySelector("#imbalance-container span");
  function recalc() {
    let d=0,c=0;
    tbody.querySelectorAll("tr.journal-line-row:not(.d-none)").forEach(tr=>{
      d += parseFloat(tr.querySelector('[name$="-debit_amount"]')?.value||0);
      c += parseFloat(tr.querySelector('[name$="-credit_amount"]')?.value||0);
    });
    td.textContent=d.toFixed(2); tc.textContent=c.toFixed(2);
    const diff=d-c; im.textContent= diff===0 ? "Balanced" : `Imbalance: ${diff.toFixed(2)}`;
    im.classList.toggle("text-danger", diff!==0); im.classList.toggle("text-success", diff===0);
  }
  document.addEventListener("input", e => { if (e.target.matches('input[type="number"]')) recalc(); });
  document.addEventListener("recalc-totals", recalc);
  recalc();
})();

Validation Panel (single)
<div id="validation-panel"
     hx-post="/accounting/journal/validate/"
     hx-trigger="load, change from:#journal-form"
     hx-include="#journal-form"
     hx-target="#validation-panel"
     hx-swap="innerHTML"></div>

10) Prompts for your AI agent (copy/paste)

Render empty form row (server)

“Create a Django view /accounting/journals/add-line/ that reads index from POST and returns a single <tr> HTML for a journal line, replacing __prefix__ with the index. Include hidden lines-<i>-DELETE input.”

Validate partial

“Implement /accounting/journal/validate/ to bind the main form + formset and return an HTML partial listing non-field and per-row errors, grouped under a single #validation-panel.”

Posting service tests

“Write unit tests for posting: balanced success, unbalanced fail, closed period fail, permission fail. Assert GL rows and account balances update correctly.”

HTMX integration tests

“Add tests to hit add-line and validate endpoints and assert the returned fragments contain correctly indexed inputs and expected error lists.”

11) Nice-to-haves (after MVP)

Keyboard shortcuts cheat-sheet overlay.

Duplicate / Reverse entry buttons.

Bank reconciliation stub (UI + service shell).

Budget vs Actual report skeleton.

When you start, hit section 1 → 2 → 4 in that order. That sequence removes 90% of your current breakage. If you want me to tailor the server fragments, drop your current views and I’ll return the exact HTML they should emit.