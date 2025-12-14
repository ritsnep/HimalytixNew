# UI/UX Consistency Plan

This plan aligns Himalytix screens to a consistent layout system, with a focus on mobile usability, field placement, sidebars, and worst-case data handling.

## Current Layout & Components (key findings)
- Shell: `templates/base.html` extends `partials/base.html`; messages + `page_header`/`page_content` slots.
- Navigation: `templates/partials/left-sidebar.html` (metismenu, deep tree; no explicit mobile collapse tweaks beyond plugin defaults); `partials/header.html` provides topbar.
- List shell: `accounting/templates/accounting/_list_base.html` (DataTables, optional smart filters, breadcrumb+actions row, overlay loader). JS setup is inline plus `static/js/list-base.js` (shortcuts, search routing, expand toggle).
- Assets: core CSS in `static/css/app.css` + `custom.css`; DataTables skin from BS4 bundle.
- Patterns: list pages vary between inline DataTables init (accounting) and `ListBase.mount` (generic shell). Forms and detail pages differ in spacing and header patterns across apps.

## Risks / Inconsistencies
- Mobile: long metismenu tree risks overflow; tables rely on `nowrap` responsive extension but lack small-screen controls (no column-priority or card view); toolbar wrapping not tuned.
- Field layout: forms not standardized on grid widths/gaps; action bars (save/cancel) vary placement.
- Smart list: checkbox/action columns need consistent disabling of sort/search; bulk UI duplicated per template.
- Worst-case data: long text/IDs can break table width; no ellipsis helpers; filter area can overgrow.
- Accessibility: keyboard shortcuts exist but not advertised; focus rings overridden inconsistently.

## Standards to Apply
- **Breakpoints:** target mobile-first up to 576px, then md, lg; ensure sidebars collapse below md and table toolbars stack with 100% width.
- **Spacing:** use `.row` + `.col-md-*` with `.gy-3`/`.gx-3`; cards `.p-3` list pages `.p-3` forms `.p-4` for modal body; avoid zero-padding tables—keep `.p-2` minimum.
- **Typography:** keep current font; enforce heading scale `h5` page title, `small` breadcrumbs; table header uppercase-sm muted.
- **Buttons:** primary actions right-aligned, secondary/link left; size `.btn-sm`; icon + label with `me-1`.
- **Forms:** group related fields in rows of 2 columns on md+, single column on xs; date/number inputs get suffix icons aligned via `input-group-sm`.
- **Tables:** first column reserve for selection when bulk enabled; last column for row actions; apply `data-default-visible` and `data-searchable` consistently; set `columnDefs` to disable sort/search on checkbox/actions.
- **Feedback:** use `toast` for success/info; inline `.invalid-feedback` for filters/forms; maintain overlay spinner for async loads.

## Implementation Tasks (by area)
1) **Navigation / Sidebar (mobile + consistency)**
- Add explicit mobile collapse: ensure hamburger toggles metismenu; constrain height with `max-height: calc(100vh - 64px)` and overflow-y auto.
- Add active/section highlighting tokens; reduce icon clutter on xs.
- Files: `templates/partials/left-sidebar.html`, `static/css/custom.css`, maybe `static/js/main.js`.

2) **List Shell Harmonization**
- Move inline DataTables init from `accounting/_list_base.html` into `static/js/list-base.js` with per-page JSON config; keep template lean.
- Standardize toolbar: title + breadcrumbs left, actions + bulk + search/export right; stack vertically on <768px.
- Add responsive column priorities (`columnDefs` with `responsivePriority`), ellipsis helpers, and optional card view fallback for xs.
- Files: `accounting/templates/accounting/_list_base.html`, `static/js/list-base.js`, `static/css/custom.css`.

3) **Smart Filters + Bulk**
- Provide shared partial for bulk control/checkbox column (reuse pattern from `Docs/SMART_LIST_AND_BULK.md`); ensure `select-all` accessible, disables sort/search.
- Add filter drawer collapse on mobile with sticky apply/reset bar.
- Files: `accounting/partials/smart_filters.html`, list templates using bulk (accounting inventory billing service_management list pages).

4) **Forms / Detail Pages**
- Apply consistent header with title + subtle breadcrumb + action bar sticky on mobile.
- Standardize grid: `.row gy-3` with `.col-12 col-md-6` pairs; use `.form-text` for helper text; align validations.
- Files: representative forms under `accounting/templates/accounting/`, `inventory/templates/Inventory/`, `purchasing/templates/purchasing/` (identify top-used forms and refactor progressively).

5) **Worst-Case Data Handling**
- Add utility classes: `.text-ellipsis` with max-width clamp, `.table-wrap` with `word-break: break-word` in cells; set `min-width` for key columns (code, name, amount) and use `white-space: nowrap` selectively.
- Test DataTables with 100+ rows and long strings; ensure horizontal scroll on xs while keeping header sticky.
- Files: `static/css/custom.css`, DataTables config in list shell.

6) **Accessibility & Shortcuts**
- Expose shortcut legend (e.g., `/` to search, `Ctrl+Shift+F` filters, `Ctrl+Shift+E` expand) via a small help popover in list header.
- Ensure focus outlines consistent (use `:focus-visible` tokens); add `aria-expanded` toggles for filter collapses and sidebar.
- Files: list templates, `static/js/list-base.js`, `static/css/custom.css`.

## Validation Checklist (per page before sign-off)
- Mobile (<576px): sidebar collapses; toolbar stacks; table horizontally scrollable or cardified; actions reachable without horizontal scroll.
- Fields: logical grouping; labels above inputs on mobile; helper/error text aligned; save/cancel visible without scroll (sticky footer in modals).
- Filters/bulk: filter apply/reset works; select-all updates state; bulk disabled when no selection.
- Worst case: long names/IDs wrap or ellipsize without breaking layout; numbers/currency right-aligned; date ranges usable.
- Performance: no layout shift when loading; spinner overlays centered; tooltips/icons keyboard focusable.

## Next Execution Steps
- Implement navigation/mobile adjustments and toolbar stacking (Tasks 1 + 2) first, then refactor list shell to `ListBase.mount` pattern and update 2–3 representative list pages as templates for the rest.
- After list shell, refactor top 3 high-traffic forms with the grid standard and sticky actions, then replicate.
