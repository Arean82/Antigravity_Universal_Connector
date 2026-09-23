// Google Accounts management logic (100% self-contained)

const API_BASE = 'http://127.0.0.1:8888';

document.addEventListener('DOMContentLoaded', () => {
  loadAccounts();
  setInterval(loadAccounts, 5000);
});

async function loadAccounts() {
  const container = document.getElementById('accountsContainer');
  const headerActive = document.getElementById('activeAccountHeader');
  const countBadge = document.getElementById('accountCountBadge');
  if (!container) return;

  try {
    const res = await fetch(`${API_BASE}/api/accounts`);
    if (!res.ok) return;
    const accounts = await res.json();

    if (countBadge) {
      countBadge.textContent = `${accounts.length} Account${accounts.length === 1 ? '' : 's'} Registered`;
    }

    if (!accounts || accounts.length === 0) {
      if (headerActive) headerActive.textContent = 'None';
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
              <circle cx="12" cy="7" r="4"></circle>
            </svg>
          </div>
          <h3 class="empty-title">No Google Accounts Registered</h3>
          <p class="empty-desc">Link your Google account to automatically track daily Gemini quotas and enable 1-click token rotation.</p>
          <button onclick="startOAuth()" class="btn btn-primary">
            Sign In with Google
          </button>
        </div>
      `;
      return;
    }

    const activeAccount = accounts.find((a) => a.is_active);
    if (headerActive) {
      headerActive.textContent = activeAccount ? `${activeAccount.name || activeAccount.email}` : 'None';
    }

    container.innerHTML = '';
    accounts.forEach((acc) => {
      const card = document.createElement('div');
      const isActive = acc.is_active;

      card.className = `account-card ${isActive ? 'active' : ''}`;

      // Build Quota Bars
      const quota = acc.quota || {};
      const models = quota.models || [];
      let quotaBarsHtml = '';

      if (models.length > 0) {
        models.forEach((m) => {
          quotaBarsHtml += renderQuotaBar(m.display_name || m.name, m.percentage, m.reset_time);
        });
      } else {
        quotaBarsHtml = `
          <div style="padding: 12px; text-align: center; color: var(--text-dim); font-size: 12px; background: rgba(14, 20, 36, 0.4); border-radius: 8px; border: 1px solid var(--border-color); margin-top: 8px;">
            Quota metrics refreshing...
          </div>
        `;
      }

      const isPro = acc.subscription_tier === 'PRO' || acc.subscription_tier === 'ULTRA';
      const tierBadge = isPro
        ? '<span class="tier-badge pro">PRO TIER</span>'
        : '<span class="tier-badge free">FREE TIER</span>';

      card.innerHTML = `
        <div>
          <!-- Account Top Row -->
          <div class="account-top">
            <div class="account-identity">
              <div class="avatar">
                ${acc.picture ? `<img src="${acc.picture}">` : acc.email[0].toUpperCase()}
              </div>
              <div>
                <div class="account-name-row">
                  <span class="account-name">${acc.name || acc.email}</span>
                  ${tierBadge}
                </div>
                <div class="account-email">${acc.email}</div>
              </div>
            </div>

            ${
              isActive
                ? `<div class="active-pill">
                    <span style="width: 6px; height: 6px; border-radius: 50%; background: #34d399;"></span> ACTIVE IN IDE
                   </div>`
                : ''
            }
          </div>

          <!-- Quota Section -->
          <div class="quota-section">
            <div class="quota-header">
              <span>Daily Quota Status</span>
              <span style="color: var(--text-dim); font-size: 10px;">${acc.last_refreshed ? 'Auto-synced' : ''}</span>
            </div>
            ${quotaBarsHtml}
          </div>
        </div>

        <!-- Footer Actions -->
        <div class="card-footer">
          <button onclick="refreshSingleQuota('${acc.email}')" class="btn-text-subtle">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"></path>
              <path d="M3 3v5h5"></path>
              <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"></path>
              <path d="M16 21h5v-5"></path>
            </svg>
            <span>Check Quota</span>
          </button>

          <div class="footer-actions">
            ${
              !isActive
                ? `<button onclick="switchActive('${acc.email}')" class="btn btn-outline-blue" style="padding: 6px 12px; font-size: 12px;">
                     Switch Active
                   </button>`
                : ''
            }
            <button onclick="deleteAccount('${acc.email}')" class="btn-icon-danger" title="Remove Account">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="3 6 5 6 21 6"></polyline>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
              </svg>
            </button>
          </div>
        </div>
      `;
      container.appendChild(card);
    });
  } catch (e) {
    console.error('Failed to load accounts:', e);
  }
}

async function startOAuth() {
  try {
    const res = await fetch(`${API_BASE}/api/auth/login-url`);
    const data = await res.json();
    if (data.url) {
      window.open(data.url, '_blank');
    }
  } catch (e) {
    alert(`Could not start login: ${e}`);
  }
}

async function switchActive(email) {
  try {
    const res = await fetch(`${API_BASE}/api/accounts/switch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    });
    const data = await res.json();
    if (data.success) {
      await loadAccounts();
    } else {
      alert(`Switch failed: ${data.error}`);
    }
  } catch (e) {
    alert(`Network error: ${e}`);
  }
}

async function refreshSingleQuota(email) {
  try {
    await fetch(`${API_BASE}/api/accounts/refresh-quota`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    });
    await loadAccounts();
  } catch (e) {
    alert(`Quota refresh failed: ${e}`);
  }
}

async function refreshAllQuotas() {
  const btn = document.getElementById('refreshBtn');
  if (btn) btn.classList.add('opacity-50', 'pointer-events-none');
  try {
    await fetch(`${API_BASE}/api/accounts/refresh-all`, { method: 'POST' });
    await loadAccounts();
  } catch (e) {
    alert(`Refresh all failed: ${e}`);
  } finally {
    if (btn) btn.classList.remove('opacity-50', 'pointer-events-none');
  }
}

async function deleteAccount(email) {
  if (confirm(`Remove ${email} from registered accounts?`)) {
    try {
      await fetch(`${API_BASE}/api/accounts/delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      await loadAccounts();
    } catch (e) {
      alert(`Delete error: ${e}`);
    }
  }
}
