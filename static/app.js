const $ = (id) => document.getElementById(id);
const dialog = $('editor');
const form = $('application-form');
let editingId = null;
let cached = [];

async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers },
  });
  if (!response.ok) {
    let detail = 'Something went wrong';
    try {
      const data = await response.json();
      detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
    } catch { /* no JSON body */ }
    throw new Error(detail);
  }
  return response.status === 204 ? null : response.json();
}

function showError(message) { $('message').textContent = message; }
function node(tag, className = '', value = '') {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (value !== '') el.textContent = value;
  return el;
}

function dateLabel(date) {
  if (!date) return '—';
  return new Date(`${date}T12:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

function render(rows) {
  const tbody = $('rows');
  tbody.replaceChildren();
  if (!rows.length) {
    const tr = node('tr'); const td = node('td', 'empty', 'Nothing here yet. Add your first internship application above.');
    td.colSpan = 5; tr.append(td); tbody.append(tr); return;
  }
  for (const item of rows) {
    const tr = node('tr');
    const title = node('td');
    title.append(node('div', 'company', item.company), node('div', 'role', item.role));
    if (item.url) {
      const a = node('a', 'link', 'View job ↗');
      a.href = item.url; a.target = '_blank'; a.rel = 'noopener noreferrer'; title.append(a);
    }
    const location = node('td', '', item.location || '—');
    const deadline = node('td', '', dateLabel(item.deadline));
    if (item.deadline && item.deadline < [new Date().getFullYear(), String(new Date().getMonth() + 1).padStart(2, '0'), String(new Date().getDate()).padStart(2, '0')].join('-')) deadline.classList.add('late');
    const status = node('td'); status.append(node('span', `chip ${item.status}`, item.status));
    const actions = node('td');
    const edit = node('button', 'action', 'Edit'); edit.type = 'button'; edit.addEventListener('click', () => openDialog(item));
    const remove = node('button', 'action danger', 'Remove'); remove.type = 'button';
    remove.addEventListener('click', async () => {
      if (!confirm(`Delete ${item.company} — ${item.role}?`)) return;
      try { await request(`/api/applications/${item.id}`, { method: 'DELETE' }); await refresh(); }
      catch (error) { showError(error.message); }
    });
    actions.append(edit, remove); tr.append(title, location, deadline, status, actions); tbody.append(tr);
  }
}

async function refresh() {
  try {
    showError('');
    const [all, stats] = await Promise.all([request('/api/applications'), request('/api/stats')]);
    cached = all;
    $('total').textContent = stats.total;
    $('offers').textContent = stats.by_status.Offer;
    $('in-progress').textContent = ['Applied', 'Assessment', 'Interview'].reduce((n, k) => n + stats.by_status[k], 0);
    $('due-soon').textContent = stats.due_soon;
    applyFilters();
  } catch (error) { showError(error.message); }
}

function applyFilters() {
  const q = $('query').value.toLowerCase().trim();
  const s = $('status-filter').value;
  render(cached.filter(item => (!s || item.status === s) &&
    (!q || [item.company, item.role, item.location].some(v => v.toLowerCase().includes(q)))));
}
function openDialog(item = null) {
  editingId = item?.id ?? null;
  $('dialog-title').textContent = item ? 'Edit application' : 'New application';
  form.reset();
  for (const name of ['company', 'role', 'location', 'url', 'deadline', 'status', 'notes']) {
    form.elements[name].value = item?.[name] ?? (name === 'status' ? 'Saved' : '');
  }
  dialog.showModal();
  form.elements.company.focus();
}
$('open-modal').addEventListener('click', () => openDialog());
$('close-dialog').addEventListener('click', () => dialog.close());
$('cancel-dialog').addEventListener('click', () => dialog.close());
$('query').addEventListener('input', applyFilters);
$('status-filter').addEventListener('change', applyFilters);
form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(form));
  if (!data.url) data.url = null;
  if (!data.deadline) data.deadline = null;
  try {
    await request(editingId ? `/api/applications/${editingId}` : '/api/applications', {
      method: editingId ? 'PATCH' : 'POST', body: JSON.stringify(data),
    });
    dialog.close(); await refresh();
  } catch (error) { alert(error.message); }
});
refresh();
