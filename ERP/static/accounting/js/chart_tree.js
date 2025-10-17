// Chart of Account Tree UI logic (stub)
let treeData = [];
function fetchTree(params={}) {
  fetch('/accounting/chart-of-accounts/tree/api/?' + new URLSearchParams(params))
    .then(r => r.json()).then(data => { treeData = data.tree; renderTree(); });
}
function renderTree() {
  // TODO: Render treeData as nested <ul>, color-code by type, add edit/quick-create/drag-drop controls
  document.getElementById('chart-tree').innerHTML = '<pre>' + JSON.stringify(treeData, null, 2) + '</pre>';
}
document.getElementById('quick-search').oninput = e => fetchTree({q: e.target.value});
document.getElementById('advanced-filter-btn').onclick = () => {
  document.getElementById('advanced-filter-modal').style.display = 'block';
};
document.getElementById('apply-filter').onclick = () => {
  fetchTree({
    name: document.getElementById('filter-name').value,
    code: document.getElementById('filter-code').value,
    type: document.getElementById('filter-type').value
  });
  document.getElementById('advanced-filter-modal').style.display = 'none';
};
document.getElementById('validate-hierarchy-btn').onclick = () => {
  fetch('/accounting/chart-of-accounts/tree/validate/').then(r => r.json()).then(data => {
    alert(data.valid ? 'Hierarchy OK' : 'Issues: ' + data.errors.join(', '));
  });
};
fetchTree();
