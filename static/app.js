const $ = (id) => document.getElementById(id);
const dialog = $('editor');
const form = $('application-form');
let editingId = null;
let offset = 0;
let requestVersion = 0;
let today = '';
const limit = 25;

async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { 'Content-Type': 'application/json', 'X-ApplyFlow-Request': '1', ...options.headers },
  });
  if (!response.ok) {
    let message = `Request failed (${response.status}). Please retry.`;
    try {
      const data = await response.json();
      message = typeof data.detail === 'string' ? data.detail : data.detail.map(error => `${error.loc.slice(1).join('.')}: ${error.msg}`).join('; ');
      if (data.errors) message += '\n' + data.errors.map(error => `Row ${error.row}${error.field ? `, ${error.field}` : ''}: ${error.message}`).join('\n');
    } catch { /* Keep a useful fallback for non-JSON responses. */ }
    throw new Error(message);
  }
  return response.status === 204 ? null : response.json();
}

function node(tag, className = '', value = '') {
  const el = document.createElement(tag);
  el.className = className;
  el.textContent = value;
  return el;
}

function dateLabel(value) {
  return value ? new Date(`${value}T12:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : 'No deadline';
}

function render(items, total) {
  const body = $('rows');
  body.replaceChildren();
  if (!items.length) {
    const row = node('tr');
    const cell = node('td', 'empty', total ? 'No more results.' : 'No applications match. Add an application or change your filters.');
    cell.colSpan = 5;
    row.append(cell);
    body.append(row);
  }
  for (const item of items) {
    const row = node('tr');
    const title = node('td');
    title.dataset.label = 'Company / position';
    title.append(node('div', 'company', item.company), node('div', 'role', item.role));
    if (item.url) {
      const link = node('a', 'link', 'View job ↗');
      link.href = item.url; link.target = '_blank'; link.rel = 'noopener noreferrer';
      link.setAttribute('aria-label', `View ${item.company} job (opens a new tab)`);
      title.append(link);
    }
    const location = node('td', '', item.location || 'Not specified');
    location.dataset.label = 'Location';
    const deadline = node('td', '', dateLabel(item.deadline));
    deadline.dataset.label = 'Deadline';
    if (item.status === 'Saved' && item.deadline && item.deadline < today) {
      deadline.classList.add('late');
      deadline.append(node('small', 'overdue-label', 'Overdue · not yet applied'));
    }
    const status = node('td');
    status.dataset.label = 'Status';
    status.append(node('span', `chip ${item.status}`, item.status));
    const actions = node('td', 'row-actions');
    actions.dataset.label = 'Manage';
    const edit = node('button', 'action', 'Edit');
    edit.type = 'button'; edit.setAttribute('aria-label', `Edit ${item.company}: ${item.role}`);
    edit.addEventListener('click', () => openDialog(item));
    const remove = node('button', 'action danger', 'Remove');
    remove.type = 'button'; remove.setAttribute('aria-label', `Remove ${item.company}: ${item.role}`);
    remove.addEventListener('click', async () => {
      if (!confirm(`Permanently remove ${item.company} — ${item.role} from this local tracker?`)) return;
      remove.disabled = true;
      try {
        await request(`/api/applications/${item.id}`, { method: 'DELETE' });
        await refresh();
        $('message').textContent = 'Application removed.';
      } catch (error) { $('message').textContent = error.message; remove.disabled = false; }
    });
    actions.append(edit, remove);
    row.append(title, location, deadline, status, actions);
    body.append(row);
  }
  $('page-label').textContent = total ? `${offset + 1}–${Math.min(offset + limit, total)} of ${total} applications` : '0 applications';
  $('previous').disabled = offset === 0;
  $('next').disabled = offset + limit >= total;
}

async function refresh() {
  const version = ++requestVersion;
  const params = new URLSearchParams({ q: $('query').value.trim(), limit, offset });
  if ($('status-filter').value) params.set('status', $('status-filter').value);
  if ($('deadline-filter').value) params.set('deadline', $('deadline-filter').value);
  $('results').setAttribute('aria-busy', 'true');
  try {
    const [page, stats] = await Promise.all([request(`/api/applications?${params}`), request('/api/stats')]);
    if (version !== requestVersion) return;
    if (offset >= page.total && offset > 0) {
      offset = Math.max(0, Math.ceil(page.total / limit) - 1) * limit;
      return refresh();
    }
    today = stats.today;
    $('total').textContent = stats.total;
    $('offers').textContent = stats.by_status.Offer;
    $('in-progress').textContent = ['Applied', 'Assessment', 'Interview'].reduce((n, key) => n + stats.by_status[key], 0);
    $('due-soon').textContent = stats.due_soon;
    $('overdue-count').textContent = stats.overdue;
    $('overdue-banner').hidden = stats.overdue === 0;
    $('message').textContent = '';
    render(page.items, page.total);
  } catch (error) {
    if (version === requestVersion) $('message').textContent = `${error.message} Your saved data has not been cleared.`;
  } finally {
    if (version === requestVersion) $('results').setAttribute('aria-busy', 'false');
  }
}

function openDialog(item = null) {
  editingId = item?.id ?? null;
  $('dialog-title').textContent = item ? 'Edit application' : 'New application';
  $('form-error').textContent = '';
  form.reset();
  for (const name of ['company', 'role', 'location', 'url', 'deadline', 'status', 'notes']) {
    form.elements.namedItem(name).value = item?.[name] ?? (name === 'status' ? 'Saved' : '');
  }
  dialog.showModal();
  form.elements.namedItem('company').focus();
}

$('open-modal').addEventListener('click', () => openDialog());
$('close-dialog').addEventListener('click', () => dialog.close());
$('cancel-dialog').addEventListener('click', () => dialog.close());
let debounce;
$('query').addEventListener('input', () => {
  clearTimeout(debounce); ++requestVersion; offset = 0;
  debounce = setTimeout(refresh, 180);
});
for (const id of ['status-filter', 'deadline-filter']) {
  $(id).addEventListener('change', () => { offset = 0; refresh(); });
}
$('previous').addEventListener('click', () => { offset = Math.max(0, offset - limit); refresh(); });
$('next').addEventListener('click', () => { offset += limit; refresh(); });
$('show-overdue').addEventListener('click', () => {
  $('deadline-filter').value = 'overdue'; $('status-filter').value = ''; $('query').value = ''; offset = 0; refresh();
});
$('retry').addEventListener('click', refresh);

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = $('save-application');
  if (button.disabled) return;
  const data = Object.fromEntries(new FormData(form));
  data.url ||= null; data.deadline ||= null;
  button.disabled = true; $('form-error').textContent = '';
  try {
    await request(editingId ? `/api/applications/${editingId}` : '/api/applications', {
      method: editingId ? 'PATCH' : 'POST', body: JSON.stringify(data),
    });
    dialog.close(); await refresh();
    $('message').textContent = 'Application saved.';
    $('open-modal').focus();
  } catch (error) { $('form-error').textContent = error.message; }
  finally { button.disabled = false; }
});

const importDialog = $('import-dialog');
$('open-import').addEventListener('click', () => {
  $('import-form').reset(); $('import-error').textContent = ''; importDialog.showModal();
});
$('cancel-import').addEventListener('click', () => importDialog.close());
$('import-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const file = $('csv-file').files[0];
  if (!file) return;
  const button = $('import-submit');
  if (button.disabled) return;
  if (file.size > 1_000_000) { $('import-error').textContent = 'Choose a CSV no larger than 1 MB.'; return; }
  button.disabled = true; $('import-error').textContent = '';
  try {
    const result = await request('/api/import.csv', { method: 'POST', body: file, headers: { 'Content-Type': 'text/csv' } });
    importDialog.close(); offset = 0; await refresh();
    $('message').textContent = `Imported ${result.imported} applications.`;
    $('open-import').focus();
  } catch (error) { $('import-error').textContent = error.message; }
  finally { button.disabled = false; }
});
refresh();
