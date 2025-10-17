// Chart of Account Tree UI logic (tree rendering, expand/collapse, color, inline edit, quick create, drag-and-drop, feedback)
let treeData = [];
function fetchTree(params={}) {
  fetch('/accounting/chart-of-accounts/tree/api/?' + new URLSearchParams(params))
    .then(r => r.json()).then(data => { treeData = data.tree; renderTree(); });
}
function renderTree() {
  const container = document.getElementById('chart-tree');
  container.innerHTML = '';
  function renderNode(node, level=0) {
    const li = document.createElement('li');
    li.style.marginLeft = (level * 20) + 'px';
    li.draggable = true;
    // Color by type
    let color = '#222';
    if (node.type === 'asset') color = 'blue';
    if (node.type === 'liability') color = 'red';
    if (node.type === 'equity') color = 'purple';
    if (node.type === 'income') color = 'green';
    if (node.type === 'expense') color = 'orange';
    // Inline edit
    const nameSpan = document.createElement('span');
    nameSpan.textContent = node.name;
    nameSpan.style.cursor = 'pointer';
    nameSpan.onclick = function() {
      const input = document.createElement('input');
      input.value = node.name;
      input.onblur = function() {
        if (input.value !== node.name) {
          fetch(`/accounting/chart-of-accounts/tree/inline-edit/${node.id}/`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCSRFToken()},
            body: JSON.stringify({name: input.value})
          })
          .then(r => r.json())
          .then(data => {
            if (data.success) {
              showToast('Name updated!', 'success');
              fetchTree();
            } else {
              showToast('Error: ' + (data.error || 'Could not update'), 'error');
              nameSpan.textContent = node.name;
            }
          });
        } else {
          nameSpan.textContent = node.name;
        }
        nameSpan.style.display = '';
        input.remove();
      };
      input.onkeydown = function(e) {
        if (e.key === 'Enter') input.blur();
        if (e.key === 'Escape') { nameSpan.style.display = ''; input.remove(); }
      };
      nameSpan.style.display = 'none';
      li.insertBefore(input, nameSpan);
      input.focus();
    };
    li.innerHTML = `<span style="color:${color};font-weight:bold;">${node.code}</span> `;
    li.appendChild(nameSpan);
    li.innerHTML += ` <span style="font-size:0.9em;color:#888;">(${node.account_type})</span>`;
    // Quick create
    const quickBtn = document.createElement('button');
    quickBtn.textContent = '+';
    quickBtn.title = 'Quick Create Child';
    quickBtn.onclick = function(e) {
      e.stopPropagation();
      showQuickCreateModal(node);
    };
    li.appendChild(quickBtn);
    // Drag-and-drop
    li.ondragstart = function(e) {
      e.dataTransfer.setData('text/plain', node.id);
      li.classList.add('dragging');
    };
    li.ondragend = function() {
      li.classList.remove('dragging');
    };
    li.ondragover = function(e) {
      e.preventDefault();
      li.classList.add('drag-over');
    };
    li.ondragleave = function() {
      li.classList.remove('drag-over');
    };
    li.ondrop = function(e) {
      e.preventDefault();
      li.classList.remove('drag-over');
      const draggedId = e.dataTransfer.getData('text/plain');
      if (draggedId && draggedId !== node.id) {
        fetch(`/accounting/chart-of-accounts/tree/reorder/`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCSRFToken()},
          body: JSON.stringify({moved_id: draggedId, new_parent_id: node.id})
        })
        .then(r => r.json())
        .then(data => {
          if (data.success) {
            showToast('Account moved!', 'success');
            fetchTree();
          } else {
            showToast('Error: ' + (data.error || 'Could not move'), 'error');
          }
        });
      }
    };
    // Expand/collapse
    if (node.children && node.children.length) {
      const btn = document.createElement('button');
      btn.textContent = '-';
      btn.style.marginRight = '6px';
      let expanded = true;
      btn.onclick = function() {
        expanded = !expanded;
        ul.style.display = expanded ? '' : 'none';
        btn.textContent = expanded ? '-' : '+';
      };
      li.prepend(btn);
      const ul = document.createElement('ul');
      ul.style.listStyle = 'none';
      ul.style.paddingLeft = '16px';
      node.children.forEach(child => ul.appendChild(renderNode(child, level+1)));
      li.appendChild(ul);
    }
    return li;
  }
  const ul = document.createElement('ul');
  ul.style.listStyle = 'none';
  treeData.forEach(node => ul.appendChild(renderNode(node)));
  container.appendChild(ul);
}
// Quick Create Modal
function showQuickCreateModal(parentNode) {
  const modal = document.getElementById('quick-create-modal');
  modal.style.display = 'block';
  document.getElementById('qc-parent').textContent = parentNode.name + ' (' + parentNode.code + ')';
  document.getElementById('qc-name').value = '';
  document.getElementById('qc-type').value = parentNode.type;
  document.getElementById('qc-code').value = '';
  document.getElementById('qc-save').onclick = function() {
    const name = document.getElementById('qc-name').value.trim();
    const type = document.getElementById('qc-type').value;
    const code = document.getElementById('qc-code').value.trim();
    if (!name) { showToast('Name required', 'error'); return; }
    fetch(`/accounting/chart-of-accounts/tree/quick-create/`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCSRFToken()},
      body: JSON.stringify({parent_id: parentNode.id, name, type, code})
    })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        showToast('Account created!', 'success');
        modal.style.display = 'none';
        fetchTree();
      } else {
        showToast('Error: ' + (data.error || 'Could not create'), 'error');
      }
    });
  };
  document.getElementById('qc-cancel').onclick = function() {
    modal.style.display = 'none';
  };
}
// Toast feedback
function showToast(msg, type='info') {
  let toast = document.getElementById('toast-msg');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'toast-msg';
    toast.style.position = 'fixed';
    toast.style.bottom = '30px';
    toast.style.right = '30px';
    toast.style.padding = '12px 24px';
    toast.style.borderRadius = '6px';
    toast.style.zIndex = 9999;
    toast.style.fontWeight = 'bold';
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.style.background = type === 'success' ? '#4caf50' : (type === 'error' ? '#f44336' : '#333');
  toast.style.color = '#fff';
  toast.style.display = 'block';
  setTimeout(() => { toast.style.display = 'none'; }, 2500);
}
// CSRF helper
function getCSRFToken() {
  const name = 'csrftoken';
  if (document.cookie) {
    const cookies = document.cookie.split(';');
    for (let c of cookies) {
      c = c.trim();
      if (c.startsWith(name + '=')) return decodeURIComponent(c.substring(name.length + 1));
    }
  }
  return '';
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
    if (data.valid) {
      showToast('Hierarchy OK', 'success');
    } else {
      showToast('Issues: ' + data.errors.join(', '), 'error');
    }
  });
};
fetchTree();
// Modal HTML injection if not present
if (!document.getElementById('quick-create-modal')) {
  const modal = document.createElement('div');
  modal.id = 'quick-create-modal';
  modal.style.display = 'none';
  modal.style.position = 'fixed';
  modal.style.left = '0';
  modal.style.top = '0';
  modal.style.width = '100vw';
  modal.style.height = '100vh';
  modal.style.background = 'rgba(0,0,0,0.2)';
  modal.style.zIndex = 10000;
  modal.innerHTML = `
    <div style="background:#fff;padding:24px 32px;max-width:400px;margin:10vh auto;border-radius:8px;box-shadow:0 2px 16px #0002;position:relative;">
      <h3>Quick Create Account</h3>
      <div>Parent: <span id="qc-parent"></span></div>
      <div style="margin:10px 0;">
        <input id="qc-name" placeholder="Account Name" style="width:100%;margin-bottom:8px;" />
        <input id="qc-code" placeholder="Account Code (optional)" style="width:100%;margin-bottom:8px;" />
        <select id="qc-type" style="width:100%;">
          <option value="asset">Asset</option>
          <option value="liability">Liability</option>
          <option value="equity">Equity</option>
          <option value="income">Income</option>
          <option value="expense">Expense</option>
        </select>
      </div>
      <div style="text-align:right;">
        <button id="qc-cancel" style="margin-right:8px;">Cancel</button>
        <button id="qc-save">Create</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);
}
