// RelayAI Admin Dashboard — Single-page app
// No framework, no build step.

(function () {
  'use strict';

  const $app = document.getElementById('app');
  const $toast = document.getElementById('toast');

  // ── Utilities ──────────────────────────────────────────────────────

  function escapeHtml(str) {
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
  }

  function formatRelativeTime(iso) {
    if (!iso) return '—';
    const diff = Date.now() - new Date(iso).getTime();
    const seconds = Math.floor(diff / 1000);
    if (seconds < 60) return 'just now';
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days < 30) return `${days}d ago`;
    return new Date(iso).toLocaleDateString();
  }

  function formatNumber(n) {
    if (n == null) return '0';
    return Number(n).toLocaleString();
  }

  function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(
      () => showToast('Copied to clipboard', 'success'),
      () => showToast('Failed to copy', 'error')
    );
  }

  let toastTimer;
  function showToast(message, type) {
    $toast.textContent = message;
    $toast.className = `toast toast-${type} show`;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { $toast.classList.remove('show'); }, 3000);
  }

  // ── API Client ─────────────────────────────────────────────────────

  function getApiKey() {
    return sessionStorage.getItem('admin_api_key');
  }

  function setApiKey(key) {
    sessionStorage.setItem('admin_api_key', key);
  }

  function clearApiKey() {
    sessionStorage.removeItem('admin_api_key');
  }

  async function api(method, path, body) {
    const key = getApiKey();
    const opts = {
      method,
      headers: { 'X-API-Key': key || '' },
    };
    if (body !== undefined) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(path, opts);
    if (res.status === 403) {
      clearApiKey();
      navigate('#/');
      showToast('Session expired — please log in again', 'error');
      throw new Error('Unauthorized');
    }
    if (!res.ok) {
      const detail = await res.text();
      throw new Error(detail || `HTTP ${res.status}`);
    }
    if (res.status === 204) return null;
    return res.json();
  }

  const API = {
    listTenants: () => api('GET', '/admin/tenants'),
    createTenant: (data) => api('POST', '/admin/tenants', data),
    getTenant: (id) => api('GET', `/admin/tenants/${id}`),
    updateTenant: (id, data) => api('PUT', `/admin/tenants/${id}`, data),
    getUsage: (id) => api('GET', `/admin/tenants/${id}/usage`),
    getConversations: (id) => api('GET', `/admin/tenants/${id}/conversations`),
  };

  // ── Router ─────────────────────────────────────────────────────────

  function navigate(hash) {
    window.location.hash = hash;
  }

  function getRoute() {
    const hash = window.location.hash || '#/';
    if (hash === '#/' || hash === '#') return { view: 'list' };
    const newMatch = hash.match(/^#\/tenants\/new$/);
    if (newMatch) return { view: 'create' };
    const detailMatch = hash.match(/^#\/tenants\/([a-f0-9-]+)$/);
    if (detailMatch) return { view: 'detail', id: detailMatch[1] };
    return { view: 'list' };
  }

  function onRouteChange() {
    if (!getApiKey()) {
      renderLogin();
      return;
    }
    const route = getRoute();
    switch (route.view) {
      case 'list': renderTenantList(); break;
      case 'create': renderTenantForm(); break;
      case 'detail': renderTenantDetail(route.id); break;
      default: renderTenantList();
    }
  }

  // ── Shell ──────────────────────────────────────────────────────────

  function renderShell(content) {
    $app.innerHTML = `
      <div class="header">
        <a href="#/" class="header-brand">RelayAI <span>Admin</span></a>
        <div class="header-actions">
          <button class="btn-logout" id="btn-logout">Log out</button>
        </div>
      </div>
      <div class="container" id="content">${content}</div>
    `;
    document.getElementById('btn-logout').addEventListener('click', () => {
      clearApiKey();
      navigate('#/');
    });
  }

  // ── Views ──────────────────────────────────────────────────────────

  // ---- Login ----
  function renderLogin() {
    $app.innerHTML = `
      <div class="login-wrapper">
        <div class="login-card">
          <h1>RelayAI</h1>
          <p>Enter your admin API key to continue.</p>
          <div id="login-error" class="alert alert-error"></div>
          <form id="login-form">
            <div class="form-group">
              <label for="api-key">API Key</label>
              <input type="password" id="api-key" placeholder="Enter admin API key" required autocomplete="off">
            </div>
            <button type="submit" class="btn btn-primary" style="width:100%">Sign in</button>
          </form>
        </div>
      </div>
    `;

    document.getElementById('login-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const key = document.getElementById('api-key').value.trim();
      if (!key) return;
      const errEl = document.getElementById('login-error');
      errEl.textContent = '';
      const btn = e.target.querySelector('button');
      btn.disabled = true;
      btn.textContent = 'Verifying...';
      try {
        setApiKey(key);
        await API.listTenants();
        navigate('#/');
        onRouteChange();
      } catch (err) {
        clearApiKey();
        errEl.textContent = 'Invalid API key';
        btn.disabled = false;
        btn.textContent = 'Sign in';
      }
    });
  }

  // ---- Tenant List ----
  async function renderTenantList() {
    renderShell('<div class="loading-center"><div class="spinner"></div></div>');
    try {
      const tenants = await API.listTenants();
      const content = document.getElementById('content');

      if (!tenants.length) {
        content.innerHTML = `
          <div class="page-header">
            <h2>Tenants</h2>
            <a href="#/tenants/new" class="btn btn-primary">New Tenant</a>
          </div>
          <div class="empty-state">
            <p>No tenants yet</p>
            <a href="#/tenants/new" class="btn btn-primary">Create your first tenant</a>
          </div>
        `;
        return;
      }

      let rows = '';
      for (const t of tenants) {
        const statusBadge = t.is_active
          ? '<span class="badge badge-active">Active</span>'
          : '<span class="badge badge-inactive">Inactive</span>';
        const crmBadge = t.crm_type !== 'none'
          ? `<span class="badge badge-crm">${escapeHtml(t.crm_type)}</span>`
          : '<span class="badge" style="color:var(--text-muted)">none</span>';
        const calBadge = t.calendar_type !== 'none'
          ? `<span class="badge badge-crm">${escapeHtml(t.calendar_type)}</span>`
          : '<span class="badge" style="color:var(--text-muted)">none</span>';
        rows += `
          <tr class="clickable" data-id="${t.id}">
            <td><strong>${escapeHtml(t.name)}</strong></td>
            <td>${crmBadge}</td>
            <td>${calBadge}</td>
            <td>${statusBadge}</td>
            <td>${formatRelativeTime(t.updated_at)}</td>
          </tr>`;
      }

      content.innerHTML = `
        <div class="page-header">
          <h2>Tenants</h2>
          <a href="#/tenants/new" class="btn btn-primary">New Tenant</a>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>CRM</th>
                <th>Calendar</th>
                <th>Status</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      `;

      content.querySelectorAll('tr.clickable').forEach(row => {
        row.addEventListener('click', () => navigate(`#/tenants/${row.dataset.id}`));
      });
    } catch (err) {
      // handled by api() auto-logout
    }
  }

  // ---- Create Tenant Form ----
  function renderTenantForm() {
    renderShell(buildTenantFormHtml(null));
    attachTenantFormHandlers(null);
  }

  function buildToolCheckboxes(current) {
    const allTools = [
      'echo', 'escalate_to_human', 'create_lead',
      'update_lead', 'search_contacts', 'check_availability',
      'book_appointment'
    ];
    // If current has enabled list, use it; otherwise all checked
    const enabled = current && current.tools_config && current.tools_config.enabled
      ? current.tools_config.enabled
      : null;

    return allTools.map(t => {
      const checked = enabled === null || enabled.includes(t) ? 'checked' : '';
      return `<label class="checkbox-label"><input type="checkbox" name="tool" value="${t}" ${checked}> ${t}</label>`;
    }).join('');
  }

  function buildTenantFormHtml(tenant) {
    const isEdit = !!tenant;
    const title = isEdit ? 'Edit Tenant' : 'New Tenant';
    const btnLabel = isEdit ? 'Save Changes' : 'Create Tenant';

    const v = tenant || {};
    const crmType = v.crm_type || 'none';
    const calType = v.calendar_type || 'none';
    const credPlaceholder = isEdit ? 'Enter new value to update' : '';
    const showCreds = crmType !== 'none' ? '' : 'style="display:none"';
    const showCalCreds = calType !== 'none' ? '' : 'style="display:none"';
    const escConfig = v.escalation_config ? JSON.stringify(v.escalation_config, null, 2) : '';

    return `
      <a href="${isEdit ? `#/tenants/${v.id}` : '#/'}" class="back-link">&larr; ${isEdit ? 'Back to tenant' : 'Back to tenants'}</a>
      <div class="page-header"><h2>${title}</h2></div>
      <div id="form-error" class="alert alert-error"></div>
      <form id="tenant-form">
        <div class="form-section">
          <h3>Basic</h3>
          <div class="form-row">
            <div class="form-group">
              <label for="f-name">Name *</label>
              <input type="text" id="f-name" value="${escapeHtml(v.name || '')}" required>
            </div>
            <div class="form-group">
              <label for="f-max-conv">Max conversations / month</label>
              <input type="number" id="f-max-conv" value="${v.max_conversations_per_month ?? 100}" min="1">
            </div>
          </div>
        </div>

        <div class="form-section">
          <h3>System Prompt</h3>
          <div class="form-group">
            <textarea id="f-prompt" class="mono" rows="8" placeholder="Enter the system prompt for this tenant's agent...">${escapeHtml(v.system_prompt || '')}</textarea>
          </div>
        </div>

        <div class="form-section">
          <h3>Tools</h3>
          <div class="form-group">
            <div class="checkbox-group">${buildToolCheckboxes(v)}</div>
            <p class="form-hint">Unchecking all enables all tools by default.</p>
          </div>
        </div>

        <div class="form-section">
          <h3>CRM</h3>
          <div class="form-row">
            <div class="form-group">
              <label for="f-crm-type">Type</label>
              <select id="f-crm-type">
                <option value="none" ${crmType === 'none' ? 'selected' : ''}>None</option>
                <option value="hubspot" ${crmType === 'hubspot' ? 'selected' : ''}>HubSpot</option>
                <option value="google_sheets" ${crmType === 'google_sheets' ? 'selected' : ''}>Google Sheets</option>
                <option value="splose" ${crmType === 'splose' ? 'selected' : ''}>Splose</option>
              </select>
            </div>
          </div>
          <div class="form-group" id="crm-creds-group" ${showCreds}>
            <label for="f-crm-creds">CRM Credentials (JSON or API key)</label>
            <textarea id="f-crm-creds" class="mono" rows="4" placeholder="${credPlaceholder}"></textarea>
          </div>
        </div>

        <div class="form-section">
          <h3>Calendar</h3>
          <div class="form-row">
            <div class="form-group">
              <label for="f-cal-type">Type</label>
              <select id="f-cal-type">
                <option value="none" ${calType === 'none' ? 'selected' : ''}>None</option>
                <option value="google_calendar" ${calType === 'google_calendar' ? 'selected' : ''}>Google Calendar</option>
                <option value="calendly" ${calType === 'calendly' ? 'selected' : ''}>Calendly</option>
              </select>
            </div>
          </div>
          <div class="form-group" id="cal-creds-group" ${showCalCreds}>
            <label for="f-cal-creds">Calendar Credentials (JSON)</label>
            <textarea id="f-cal-creds" class="mono" rows="4" placeholder="${credPlaceholder}"></textarea>
          </div>
        </div>

        <div class="form-section">
          <h3>WhatsApp (Twilio)</h3>
          <div class="form-group">
            <label for="f-phone">Phone Number</label>
            <input type="text" id="f-phone" value="${escapeHtml(v.twilio_phone_number || '')}" placeholder="+614xxxxxxxx">
          </div>
          <div class="form-row">
            <div class="form-group">
              <label for="f-twilio-sid">Account SID</label>
              <input type="text" id="f-twilio-sid" value="${escapeHtml(isEdit ? '' : '')}" placeholder="${isEdit ? credPlaceholder : ''}">
            </div>
            <div class="form-group">
              <label for="f-twilio-token">Auth Token</label>
              <input type="password" id="f-twilio-token" placeholder="${isEdit ? credPlaceholder : ''}">
            </div>
          </div>
        </div>

        <div class="form-section">
          <h3>Escalation Config</h3>
          <div class="form-group">
            <textarea id="f-esc-config" class="mono" rows="4" placeholder='{"slack_webhook": "...", "email": "..."}'>${escapeHtml(escConfig)}</textarea>
          </div>
        </div>

        ${isEdit ? `
        <div class="form-section">
          <h3>Status</h3>
          <div class="toggle-wrap">
            <label class="toggle">
              <input type="checkbox" id="f-active" ${v.is_active ? 'checked' : ''}>
              <span class="toggle-slider"></span>
            </label>
            <span>${v.is_active ? 'Active' : 'Inactive'}</span>
          </div>
        </div>` : ''}

        <button type="submit" class="btn btn-primary" id="btn-submit">${btnLabel}</button>
      </form>
    `;
  }

  function collectFormData(isEdit) {
    const data = {};

    const name = document.getElementById('f-name').value.trim();
    if (name) data.name = name;

    const maxConv = document.getElementById('f-max-conv').value;
    if (maxConv) data.max_conversations_per_month = parseInt(maxConv, 10);

    const prompt = document.getElementById('f-prompt').value;
    if (prompt || !isEdit) data.system_prompt = prompt || null;

    // Tools
    const checked = Array.from(document.querySelectorAll('input[name="tool"]:checked')).map(c => c.value);
    const allTools = Array.from(document.querySelectorAll('input[name="tool"]')).map(c => c.value);
    if (checked.length > 0 && checked.length < allTools.length) {
      data.tools_config = { enabled: checked };
    } else if (!isEdit) {
      data.tools_config = null;
    }

    // CRM
    const crmType = document.getElementById('f-crm-type').value;
    data.crm_type = crmType;
    const crmCreds = document.getElementById('f-crm-creds').value.trim();
    if (crmCreds) data.crm_credentials = crmCreds;

    // Calendar
    const calType = document.getElementById('f-cal-type').value;
    data.calendar_type = calType;
    const calCreds = document.getElementById('f-cal-creds').value.trim();
    if (calCreds) data.calendar_credentials = calCreds;

    // WhatsApp
    const phone = document.getElementById('f-phone').value.trim();
    if (phone) data.twilio_phone_number = phone;
    const sid = document.getElementById('f-twilio-sid').value.trim();
    if (sid) data.twilio_account_sid = sid;
    const token = document.getElementById('f-twilio-token').value.trim();
    if (token) data.twilio_auth_token = token;

    // Escalation
    const escConfig = document.getElementById('f-esc-config').value.trim();
    if (escConfig) {
      try {
        data.escalation_config = JSON.parse(escConfig);
      } catch {
        throw new Error('Invalid JSON in escalation config');
      }
    } else if (!isEdit) {
      data.escalation_config = null;
    }

    // Active toggle (edit only)
    const activeEl = document.getElementById('f-active');
    if (activeEl) {
      data.is_active = activeEl.checked;
    }

    return data;
  }

  function attachTenantFormHandlers(tenant) {
    const isEdit = !!tenant;

    // Toggle CRM credentials visibility
    document.getElementById('f-crm-type').addEventListener('change', (e) => {
      document.getElementById('crm-creds-group').style.display =
        e.target.value !== 'none' ? '' : 'none';
    });

    // Toggle Calendar credentials visibility
    document.getElementById('f-cal-type').addEventListener('change', (e) => {
      document.getElementById('cal-creds-group').style.display =
        e.target.value !== 'none' ? '' : 'none';
    });

    // Active toggle label update
    const activeEl = document.getElementById('f-active');
    if (activeEl) {
      activeEl.addEventListener('change', () => {
        activeEl.parentElement.nextElementSibling.textContent =
          activeEl.checked ? 'Active' : 'Inactive';
      });
    }

    document.getElementById('tenant-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const errEl = document.getElementById('form-error');
      errEl.textContent = '';
      const btn = document.getElementById('btn-submit');
      btn.disabled = true;
      btn.textContent = isEdit ? 'Saving...' : 'Creating...';

      try {
        const data = collectFormData(isEdit);
        if (!data.name && !isEdit) throw new Error('Name is required');

        if (isEdit) {
          await API.updateTenant(tenant.id, data);
          showToast('Tenant updated', 'success');
          navigate(`#/tenants/${tenant.id}`);
        } else {
          const created = await API.createTenant(data);
          showToast('Tenant created', 'success');
          navigate(`#/tenants/${created.id}`);
        }
      } catch (err) {
        errEl.textContent = err.message;
        btn.disabled = false;
        btn.textContent = isEdit ? 'Save Changes' : 'Create Tenant';
      }
    });
  }

  // ---- Tenant Detail ----
  async function renderTenantDetail(id) {
    renderShell('<div class="loading-center"><div class="spinner"></div></div>');
    try {
      const tenant = await API.getTenant(id);
      const content = document.getElementById('content');

      const statusBadge = tenant.is_active
        ? '<span class="badge badge-active">Active</span>'
        : '<span class="badge badge-inactive">Inactive</span>';

      const baseUrl = window.location.origin;
      const widgetSnippet = `<script src="${baseUrl}/static/widget.js"
  data-relay-tenant="${tenant.api_key}"
  data-relay-url="${baseUrl}"><\/script>`;

      content.innerHTML = `
        <a href="#/" class="back-link">&larr; Back to tenants</a>
        <div class="detail-header">
          <h2>${escapeHtml(tenant.name)}</h2>
          ${statusBadge}
        </div>

        <div class="snippet-section">
          <h4>Tenant ID</h4>
          <div class="copy-field">
            <input type="text" value="${escapeHtml(tenant.id || '')}" readonly>
            <button class="btn btn-secondary btn-sm" id="copy-id">Copy</button>
          </div>
        </div>

        <div class="snippet-section">
          <h4>API Key</h4>
          <div class="copy-field">
            <input type="text" value="${escapeHtml(tenant.api_key || '')}" readonly>
            <button class="btn btn-secondary btn-sm" id="copy-key">Copy</button>
          </div>
        </div>

        <div class="snippet-section">
          <h4>Widget Embed Code</h4>
          <div class="copy-field">
            <pre id="widget-snippet">${escapeHtml(widgetSnippet)}</pre>
            <button class="btn btn-secondary btn-sm" id="copy-widget">Copy</button>
          </div>
        </div>

        <div class="tabs">
          <button class="tab-btn active" data-tab="config">Configuration</button>
          <button class="tab-btn" data-tab="usage">Usage</button>
          <button class="tab-btn" data-tab="conversations">Conversations</button>
        </div>

        <div id="tab-config" class="tab-content active">
          ${buildTenantFormHtml(tenant)}
        </div>
        <div id="tab-usage" class="tab-content"></div>
        <div id="tab-conversations" class="tab-content"></div>
      `;

      // Copy buttons
      document.getElementById('copy-id').addEventListener('click', () => {
        copyToClipboard(tenant.id || '');
      });
      document.getElementById('copy-key').addEventListener('click', () => {
        copyToClipboard(tenant.api_key || '');
      });
      document.getElementById('copy-widget').addEventListener('click', () => {
        copyToClipboard(widgetSnippet);
      });

      // Tab switching
      const tabs = content.querySelectorAll('.tab-btn');
      const tabContents = content.querySelectorAll('.tab-content');
      tabs.forEach(tab => {
        tab.addEventListener('click', () => {
          tabs.forEach(t => t.classList.remove('active'));
          tabContents.forEach(tc => tc.classList.remove('active'));
          tab.classList.add('active');
          const target = tab.dataset.tab;
          document.getElementById(`tab-${target}`).classList.add('active');
          if (target === 'usage') loadUsage(id);
          if (target === 'conversations') loadConversations(id);
        });
      });

      // Attach form handlers for the config tab
      attachTenantFormHandlers(tenant);
    } catch (err) {
      // handled by api() auto-logout or shown via console
    }
  }

  async function loadUsage(id) {
    const container = document.getElementById('tab-usage');
    if (container.dataset.loaded) return;
    container.innerHTML = '<div class="loading-center"><div class="spinner"></div></div>';
    try {
      const usage = await API.getUsage(id);
      container.dataset.loaded = '1';
      container.innerHTML = `
        <div class="stat-grid">
          <div class="stat-card">
            <div class="stat-label">Input Tokens</div>
            <div class="stat-value">${formatNumber(usage.total_input_tokens)}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Output Tokens</div>
            <div class="stat-value">${formatNumber(usage.total_output_tokens)}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Estimated Cost</div>
            <div class="stat-value">$${Number(usage.total_estimated_cost_usd).toFixed(2)}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Conversations</div>
            <div class="stat-value">${formatNumber(usage.conversation_count)}</div>
          </div>
        </div>
      `;
    } catch (err) {
      container.innerHTML = '<div class="alert alert-error">Failed to load usage data</div>';
    }
  }

  async function loadConversations(id) {
    const container = document.getElementById('tab-conversations');
    if (container.dataset.loaded) return;
    container.innerHTML = '<div class="loading-center"><div class="spinner"></div></div>';
    try {
      const convos = await API.getConversations(id);
      container.dataset.loaded = '1';

      if (!convos.length) {
        container.innerHTML = '<div class="empty-state"><p>No conversations yet</p></div>';
        return;
      }

      let rows = '';
      for (const c of convos) {
        const statusClass = `badge-status-${c.status}`;
        rows += `
          <tr>
            <td>${escapeHtml(c.external_identifier)}</td>
            <td><span class="badge badge-channel">${escapeHtml(c.channel)}</span></td>
            <td><span class="badge ${statusClass}">${escapeHtml(c.status)}</span></td>
            <td>${c.message_count}</td>
            <td>${formatRelativeTime(c.last_message_at)}</td>
          </tr>`;
      }

      container.innerHTML = `
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Sender</th>
                <th>Channel</th>
                <th>Status</th>
                <th>Messages</th>
                <th>Last Activity</th>
              </tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      `;
    } catch (err) {
      container.innerHTML = '<div class="alert alert-error">Failed to load conversations</div>';
    }
  }

  // ── Init ───────────────────────────────────────────────────────────

  window.addEventListener('hashchange', onRouteChange);
  onRouteChange();
})();
