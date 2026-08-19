let currentFindings = [];
let currentEmailInfo = null;
let currentPhoneInfo = null;
let currentBriefingData = null;
let graphVisualizer = null;
let currentEventSource = null;
let activeCategoryFilter = 'all';
let activePlatformFilter = 'all';
let isAIOnline = false;

const FALLBACK_GROQ_MODELS = [
  { id: 'openai/gpt-oss-20b', name: 'OpenAI GPT-OSS 20B (Primary - Ultra-Fast)' },
  { id: 'openai/gpt-oss-120b', name: 'OpenAI GPT-OSS 120B (Secondary - Deep Reasoning)' },
  { id: 'llama-3.1-8b-instant', name: 'Llama 3.1 8B Instant' },
  { id: 'llama-3.3-70b-versatile', name: 'Llama 3.3 70B Versatile' }
];

const LOCAL_MODELS = [
  { id: 'llama3.2', name: 'Llama 3.2 (Primary)' },
  { id: 'llama3.1', name: 'Llama 3.1 (Secondary)' },
  { id: 'mistral', name: 'Mistral 7B (Fallback)' }
];

document.addEventListener('DOMContentLoaded', () => {
  graphVisualizer = new IntelligenceGraph('graphCanvas');
  setupNavigation();
  setupPermutationPreview();
  setupFormSubmit();
  setupCategoryFilterChips();
  setupDismissControls();
  setupSettingsModal();
  initLiveHealthCheck();
});

function setupNavigation() {
  document.querySelectorAll('.nav-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.nav-tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.view-section').forEach(s => s.style.display = 'none');
      btn.classList.add('active');
      const targetView = document.getElementById(btn.dataset.target);
      if (targetView) targetView.style.display = 'block';

      if (btn.dataset.target === 'view-graph' && graphVisualizer) {
        setTimeout(() => {
          graphVisualizer.resize();
          const target = document.getElementById('input-username').value || document.getElementById('input-name').value || 'Target';
          if (currentFindings.length > 0 || currentEmailInfo || currentPhoneInfo) {
            graphVisualizer.buildFromScan(target, currentFindings, currentEmailInfo, currentPhoneInfo);
          }
        }, 60);
      }
      if (btn.dataset.target === 'view-history') {
        loadHistory();
      }
    });
  });
}

function setupCategoryFilterChips() {
  document.querySelectorAll('#filter-row .filter-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      document.querySelectorAll('#filter-row .filter-chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      activeCategoryFilter = chip.dataset.filter;
      activePlatformFilter = 'all';
      updateSubFilterBar();
      renderFindingsGrid();
    });
  });
}

function updateSubFilterBar() {
  const subBar = document.getElementById('sub-filter-row');
  if (!subBar) return;

  if (['Social', 'Developer', 'Gaming', 'Media'].includes(activeCategoryFilter)) {
    const categoryFindings = currentFindings.filter(f => f.category === activeCategoryFilter);
    const uniqueSites = Array.from(new Set(categoryFindings.map(f => f.site)));

    if (uniqueSites.length > 0) {
      subBar.style.display = 'flex';
      subBar.innerHTML = `
        <button class="sub-chip ${activePlatformFilter === 'all' ? 'active' : ''}" data-site="all">
          All ${activeCategoryFilter} (${categoryFindings.length})
        </button>
      ` + uniqueSites.map(site => {
        const count = categoryFindings.filter(f => f.site === site).length;
        return `
          <button class="sub-chip ${activePlatformFilter === site ? 'active' : ''}" data-site="${site}">
            ${site} (${count})
          </button>
        `;
      }).join('');

      subBar.querySelectorAll('.sub-chip').forEach(btn => {
        btn.addEventListener('click', () => {
          subBar.querySelectorAll('.sub-chip').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          activePlatformFilter = btn.dataset.site;
          renderFindingsGrid();
        });
      });
      return;
    }
  }

  subBar.style.display = 'none';
  subBar.innerHTML = '';
}

function setupDismissControls() {
  const dismissBtn = document.getElementById('btn-dismiss-scan');
  const resetBtn = document.getElementById('btn-reset-results');

  const doDismiss = () => {
    if (currentEventSource) {
      currentEventSource.close();
      currentEventSource = null;
    }
    document.getElementById('progress-panel').style.display = 'none';
    document.getElementById('progress-bar-fill').style.width = '0%';
    document.getElementById('progress-percent').innerText = '0%';
  };

  if (dismissBtn) dismissBtn.addEventListener('click', doDismiss);
  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      doDismiss();
      currentFindings = [];
      currentEmailInfo = null;
      currentPhoneInfo = null;
      currentBriefingData = null;
      document.getElementById('findings-count').innerText = '0 Findings';
      document.getElementById('ai-briefing-card').style.display = 'none';
      updateSubFilterBar();
      renderFindingsGrid();
      resetBtn.style.display = 'none';
    });
  }
}

async function checkAIHealth() {
  const statusPill = document.getElementById('ai-global-status');
  const statusText = document.getElementById('ai-status-text');
  const collisionBadge = document.getElementById('collision-mode-badge');
  const offlineDigitContainer = document.getElementById('offline-digit-container');
  if (!statusPill || !statusText) return;

  try {
    const res = await fetch('/api/settings/health').then(r => r.json());
    statusText.innerText = res.label;
    statusPill.className = 'ai-status-pill ' + (res.online ? 'online' : 'offline');
    isAIOnline = res.online;

    if (res.online) {
      if (collisionBadge) {
        collisionBadge.innerText = `AI REASONING & CONTEXT ENGINE: ACTIVE (${res.provider.toUpperCase()})`;
        collisionBadge.style.color = 'var(--status-found)';
      }
      if (offlineDigitContainer) offlineDigitContainer.style.display = 'none';
    } else {
      if (collisionBadge) {
        collisionBadge.innerText = 'CONTEXT & SYLLABLE MATRIX: ACTIVE (LOCAL CORE)';
        collisionBadge.style.color = 'var(--status-searching)';
      }
      if (offlineDigitContainer) offlineDigitContainer.style.display = 'block';
    }
  } catch (e) {
    statusText.innerText = 'AI: OFFLINE (SERVER UNREACHABLE)';
    statusPill.className = 'ai-status-pill offline';
    isAIOnline = false;
    if (offlineDigitContainer) offlineDigitContainer.style.display = 'block';
  }
}

function initLiveHealthCheck() {
  checkAIHealth();
  setInterval(checkAIHealth, 45000);

  const statusPill = document.getElementById('ai-global-status');
  if (statusPill) {
    statusPill.addEventListener('click', () => {
      const modal = document.getElementById('settings-modal');
      if (modal) modal.style.display = 'flex';
    });
  }
}

async function setupSettingsModal() {
  const modal = document.getElementById('settings-modal');
  const openBtn = document.getElementById('btn-open-settings');
  const closeBtn = document.getElementById('btn-close-settings');
  const form = document.getElementById('settings-form');
  const providerSelect = document.getElementById('setting-provider');
  const keyInput = document.getElementById('setting-api-key');
  const modelSelect = document.getElementById('setting-model-select');
  const hostInput = document.getElementById('setting-host');
  const enableAiChk = document.getElementById('setting-enable-ai');
  const groupKey = document.getElementById('group-api-key');
  const groupHost = document.getElementById('group-ollama-host');
  const toggleKeyBtn = document.getElementById('btn-toggle-key');
  const testBtn = document.getElementById('btn-test-ai');
  const testStatus = document.getElementById('test-status-box');

  const populateModels = async (provider, chosenModel) => {
    if (provider === 'groq') {
      const enteredKey = keyInput.value.trim();
      let liveList = [];
      if (enteredKey) {
        try {
          const r = await fetch(`/api/models/live?key=${encodeURIComponent(enteredKey)}`).then(x => x.json());
          if (r.models && r.models.length > 0) {
            liveList = r.models;
          }
        } catch (e) {}
      }
      
      const modelsToUse = liveList.length > 0 ? liveList : FALLBACK_GROQ_MODELS;
      modelSelect.innerHTML = modelsToUse.map(m => `<option value="${m.id}">${m.name}</option>`).join('');

      let target = chosenModel || modelsToUse[0].id;
      if (['llama-3.1-70b-versatile', 'llama-3.1-70b', 'gemma2-9b-it'].includes(target)) {
        target = modelsToUse[0].id;
      }
      const matched = modelsToUse.find(m => m.id === target);
      modelSelect.value = matched ? target : modelsToUse[0].id;
    } else {
      modelSelect.innerHTML = LOCAL_MODELS.map(m => `<option value="${m.id}">${m.name}</option>`).join('');
      const matched = LOCAL_MODELS.find(m => m.id === chosenModel);
      modelSelect.value = matched ? chosenModel : LOCAL_MODELS[0].id;
    }
  };

  const updateVisibility = () => {
    if (providerSelect.value === 'groq') {
      groupKey.style.display = 'flex';
      groupHost.style.display = 'none';
      populateModels('groq', modelSelect.value);
    } else {
      groupKey.style.display = 'none';
      groupHost.style.display = 'flex';
      populateModels('local', modelSelect.value);
    }
  };

  // Load Initial Settings from Server API
  try {
    const serverSettings = await fetch('/api/settings').then(r => r.json());
    if (serverSettings.ai_provider) providerSelect.value = serverSettings.ai_provider;
    if (serverSettings.ai_api_key) keyInput.value = serverSettings.ai_api_key;
    if (serverSettings.ai_host) hostInput.value = serverSettings.ai_host;
    enableAiChk.checked = serverSettings.enable_ai !== false;
    await populateModels(providerSelect.value, serverSettings.ai_model);
  } catch (e) {}

  providerSelect.addEventListener('change', updateVisibility);
  updateVisibility();

  let keyDebounce;
  keyInput.addEventListener('input', () => {
    clearTimeout(keyDebounce);
    keyDebounce = setTimeout(() => {
      if (providerSelect.value === 'groq') {
        populateModels('groq', modelSelect.value);
      }
    }, 400);
  });

  openBtn.addEventListener('click', () => {
    modal.style.display = 'flex';
    testStatus.style.display = 'none';
    if (providerSelect.value === 'groq') {
      populateModels('groq', modelSelect.value);
    }
  });

  closeBtn.addEventListener('click', () => {
    modal.style.display = 'none';
  });

  toggleKeyBtn.addEventListener('click', () => {
    if (keyInput.type === 'password') {
      keyInput.type = 'text';
      toggleKeyBtn.innerText = 'Hide';
    } else {
      keyInput.type = 'password';
      toggleKeyBtn.innerText = 'Show';
    }
  });

  testBtn.addEventListener('click', async () => {
    testStatus.style.display = 'block';
    testStatus.style.color = 'var(--text-secondary)';
    testStatus.innerText = 'Testing AI connection...';

    const payload = {
      ai_provider: providerSelect.value,
      ai_api_key: keyInput.value.trim(),
      ai_model: modelSelect.value,
      ai_host: hostInput.value.trim(),
      enable_ai: enableAiChk.checked
    };

    const res = await fetch('/api/settings/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(r => r.json());

    if (res.success) {
      testStatus.style.color = 'var(--status-found)';
      testStatus.innerText = res.message || 'AI: Online';
    } else {
      testStatus.style.color = 'var(--status-error)';
      testStatus.innerText = `Failed: ${res.error || 'Connection failed'}`;
    }
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const payload = {
      ai_provider: providerSelect.value,
      ai_api_key: keyInput.value.trim(),
      ai_model: modelSelect.value,
      ai_host: hostInput.value.trim(),
      enable_ai: enableAiChk.checked
    };

    localStorage.setItem('argos_ai_settings', JSON.stringify(payload));
    await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    testStatus.style.display = 'block';
    testStatus.style.color = 'var(--status-found)';
    testStatus.innerText = 'Settings saved permanently!';
    checkAIHealth();
    setTimeout(() => { modal.style.display = 'none'; }, 800);
  });
}

function setupPermutationPreview() {
  const usernameInput = document.getElementById('input-username');
  const nameInput = document.getElementById('input-name');
  const locationInput = document.getElementById('input-location');
  const previewBar = document.getElementById('permutation-preview-bar');
  const chkFuzzy = document.getElementById('chk-fuzzy');
  const chkDigits = document.getElementById('chk-digits');

  let debounceTimer;
  const updatePreview = () => {
    clearTimeout(debounceTimer);
    const val = usernameInput.value.trim();
    if (!val || !chkFuzzy.checked) {
      previewBar.innerHTML = '';
      return;
    }
    debounceTimer = setTimeout(async () => {
      const resp = await fetch('/api/permutations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: val,
          real_name: nameInput ? nameInput.value.trim() : '',
          location: locationInput ? locationInput.value.trim() : '',
          max_permutations: 35,
          include_digits: chkDigits ? chkDigits.checked : true
        })
      });
      const data = await resp.json();
      if (data.permutations) {
        previewBar.innerHTML = data.permutations.map(p => `
          <span class="perm-chip ${p.is_seed ? 'seed' : ''}">
            ${p.username} <span style="opacity:0.5;">(${Math.round(p.similarity*100)}%)</span>
          </span>
        `).join('');
      }
    }, 200);
  };

  usernameInput.addEventListener('input', updatePreview);
  if (nameInput) nameInput.addEventListener('input', updatePreview);
  if (locationInput) locationInput.addEventListener('input', updatePreview);
  chkFuzzy.addEventListener('change', updatePreview);
  if (chkDigits) chkDigits.addEventListener('change', updatePreview);
}

function setupFormSubmit() {
  const form = document.getElementById('scan-form');
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    startReconScan();
  });

  document.getElementById('btn-export-json').addEventListener('click', () => {
    const target = document.getElementById('input-username').value || 'Target';
    Exporter.exportJSON(target, currentFindings, currentEmailInfo, currentPhoneInfo, currentBriefingData);
  });

  document.getElementById('btn-export-html').addEventListener('click', () => {
    const target = document.getElementById('input-username').value || 'Target';
    Exporter.exportHTML(target, currentFindings, currentBriefingData);
  });
}

function startReconScan() {
  const username = document.getElementById('input-username').value.trim();
  const email = document.getElementById('input-email').value.trim();
  const phone = document.getElementById('input-phone').value.trim();
  const realName = document.getElementById('input-name').value.trim();
  const location = document.getElementById('input-location').value.trim();
  const fuzzy = document.getElementById('chk-fuzzy').checked;
  const digits = document.getElementById('chk-digits') ? document.getElementById('chk-digits').checked : true;

  if (!username && !email && !phone && !realName) {
    alert('Please provide at least a username, real name/alias, email, or phone number.');
    return;
  }

  currentFindings = [];
  currentEmailInfo = null;
  currentPhoneInfo = null;
  currentBriefingData = null;
  document.getElementById('results-grid').innerHTML = '';
  document.getElementById('progress-panel').style.display = 'block';
  document.getElementById('findings-count').innerText = '0 Discovered';
  document.getElementById('btn-reset-results').style.display = 'inline-block';
  document.getElementById('ai-briefing-card').style.display = 'none';

  if (currentEventSource) currentEventSource.close();

  const params = new URLSearchParams({
    username,
    known_names: realName,
    location,
    email,
    phone,
    enable_permutations: fuzzy
  });

  currentEventSource = new EventSource(`/api/scan/stream?${params.toString()}`);

  currentEventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.type === 'status_update') {
      document.getElementById('progress-detail').innerText = data.message;
    }

    if (data.type === 'email_result') {
      currentEmailInfo = data.data;
      renderFindingsGrid();
    }

    if (data.type === 'phone_result') {
      currentPhoneInfo = data.data;
      renderFindingsGrid();
    }

    if (data.type === 'probe_result') {
      const res = data.result;
      const progress = data.progress;
      document.getElementById('progress-percent').innerText = `${progress.percent}%`;
      document.getElementById('progress-detail').innerText = `Probing ${res.site} (@${res.username})...`;
      document.getElementById('progress-bar-fill').style.width = `${progress.percent}%`;

      if (res.found) {
        currentFindings.push(res);
        document.getElementById('findings-count').innerText = `${currentFindings.length} Discovered`;
        updateSubFilterBar();
        renderFindingsGrid();
        if (graphVisualizer) {
          graphVisualizer.buildFromScan(username || email || phone, currentFindings, currentEmailInfo, currentPhoneInfo);
        }
      }
    }

    if (data.type === 'ai_briefing') {
      const card = document.getElementById('ai-briefing-card');
      const text = document.getElementById('briefing-text');
      const confBadge = document.getElementById('briefing-confidence-badge');
      const identTag = document.getElementById('briefing-identity-tag');
      const rationaleEl = document.getElementById('briefing-rationale');
      const evidenceRow = document.getElementById('briefing-evidence-row');

      currentBriefingData = data.briefing;

      if (card && text) {
        text.innerText = data.briefing.briefing || data.briefing;
        
        if (confBadge && data.briefing.confidence !== undefined) {
          confBadge.innerText = `${data.briefing.confidence}% CONFIDENCE`;
        }

        if (identTag) {
          if (data.briefing.verified_identities && data.briefing.verified_identities.length > 0) {
            identTag.innerText = `VERIFIED: ${data.briefing.verified_identities.join(', ')}`;
            identTag.style.color = 'var(--status-found)';
          } else if (data.briefing.inferred_identity) {
            identTag.innerText = `INFERRED: ${data.briefing.inferred_identity}`;
            identTag.style.color = 'var(--status-warn)';
          } else {
            identTag.innerText = 'IDENTITY: INFERRED';
          }
        }

        if (rationaleEl && data.briefing.rationale) {
          rationaleEl.innerText = `Rationale: ${data.briefing.rationale}`;
        }

        if (evidenceRow && Array.isArray(data.briefing.evidence) && data.briefing.evidence.length > 0) {
          evidenceRow.innerHTML = data.briefing.evidence.map(ev => `
            <a href="${ev.url}" target="_blank" rel="noopener" class="sub-chip" style="font-size:10px;text-decoration:none;">
              ${ev.site} (@${ev.username}) [↗]
            </a>
          `).join('');
        }

        card.style.display = 'block';
      }
    }

    if (data.type === 'complete') {
      currentEventSource.close();
      document.getElementById('progress-detail').innerText = 'Reconnaissance Complete';
      updateSubFilterBar();
      renderFindingsGrid();
    }
  };

  currentEventSource.onerror = () => {
    if (currentEventSource) currentEventSource.close();
    document.getElementById('progress-detail').innerText = 'Reconnaissance Complete';
    updateSubFilterBar();
    renderFindingsGrid();
  };
}

function renderFindingsGrid() {
  const grid = document.getElementById('results-grid');
  grid.innerHTML = '';

  if (currentEmailInfo && currentEmailInfo.valid_syntax && (activeCategoryFilter === 'all' || activeCategoryFilter === 'exact')) {
    addEmailCard(currentEmailInfo);
  }
  if (currentPhoneInfo && currentPhoneInfo.valid && (activeCategoryFilter === 'all' || activeCategoryFilter === 'exact')) {
    addPhoneCard(currentPhoneInfo);
  }

  let filtered = currentFindings.filter(item => {
    if (activeCategoryFilter === 'all') return true;
    if (activeCategoryFilter === 'exact') return item.is_seed;
    if (activeCategoryFilter === 'permutation') return !item.is_seed;
    return item.category === activeCategoryFilter;
  });

  if (activePlatformFilter !== 'all') {
    filtered = filtered.filter(item => item.site === activePlatformFilter);
  }

  filtered.sort((a, b) => (b.is_seed ? 1 : 0) - (a.is_seed ? 1 : 0));

  if (filtered.length === 0 && (!currentEmailInfo || !currentEmailInfo.valid_syntax) && (!currentPhoneInfo || !currentPhoneInfo.valid)) {
    const empty = document.createElement('div');
    empty.style.gridColumn = '1 / -1';
    empty.style.padding = '30px';
    empty.style.textAlign = 'center';
    empty.style.color = 'var(--text-muted)';
    empty.style.background = 'var(--bg-card)';
    empty.style.border = '1px solid var(--border-color)';
    empty.style.borderRadius = '10px';
    empty.innerText = 'No active accounts discovered for this filter criteria.';
    grid.appendChild(empty);
    return;
  }

  filtered.forEach(item => addFindingCard(item));
}

function launchPivotScan(targetHandle) {
  const input = document.getElementById('input-username');
  if (input) {
    input.value = targetHandle;
    window.scrollTo({ top: 0, behavior: 'smooth' });
    startReconScan();
  }
}

function addFindingCard(item) {
  const grid = document.getElementById('results-grid');
  const card = document.createElement('div');
  card.className = 'target-card';
  const corrob = item.corroboration || { score: 50, verdict: 'VERIFIED' };
  const meta = item.metadata || {};
  
  const aliasTag = corrob.matched_alias ? `<span class="alias-tag">Matched: ${corrob.matched_alias}</span>` : '';
  const displayName = meta.display_name ? `<div style="font-size:13px;font-weight:600;color:var(--text-primary);">${meta.display_name}</div>` : '';
  
  // Avatar or initial fallback
  const avatarHtml = meta.avatar_url ? `
    <img src="${meta.avatar_url}" class="profile-avatar" alt="Avatar" onerror="this.style.display='none';">
  ` : `
    <div class="profile-avatar-fallback">${item.site.substring(0, 2).toUpperCase()}</div>
  `;

  // Bio Snippet
  const bioHtml = meta.bio ? `
    <div class="profile-bio-box">${meta.bio}</div>
  ` : '';

  // Mentioned Pivots
  let pivotsHtml = '';
  if (meta.mentioned_handles && meta.mentioned_handles.length > 0) {
    pivotsHtml = `
      <div class="pivots-container">
        <span class="pivots-label">Discovered Pivot Handles:</span>
        <div style="display:flex;gap:6px;flex-wrap:wrap;">
          ${meta.mentioned_handles.map(h => `
            <button type="button" class="btn-pivot-chip" onclick="launchPivotScan('${h}')">
              Pivot @${h} [⤾]
            </button>
          `).join('')}
        </div>
      </div>
    `;
  }

  // Outbound Links
  let linksHtml = '';
  if (meta.outbound_links && meta.outbound_links.length > 0) {
    linksHtml = `
      <div style="display:flex;gap:4px;flex-wrap:wrap;margin-top:2px;">
        ${meta.outbound_links.map(l => `
          <a href="${l}" target="_blank" rel="noopener" class="sub-chip" style="font-size:9px;color:var(--status-searching);">
            ${l.replace(/^https?:\/\/(www\.)?/, '')} [↗]
          </a>
        `).join('')}
      </div>
    `;
  }

  card.innerHTML = `
    <div class="card-top">
      <span class="platform-name">
        <span>${item.site}</span>
        <span class="category-tag">${item.category}</span>
      </span>
      <span class="corrob-badge ${item.is_seed ? 'exact' : ''}">
        ${item.is_seed ? 'Exact Match' : `${corrob.score}% Match`}
      </span>
    </div>

    <div class="profile-header-row">
      ${avatarHtml}
      <div style="display:flex;flex-direction:column;gap:2px;overflow:hidden;">
        ${displayName}
        <div class="account-handle">Handle: <strong>@${item.username}</strong></div>
      </div>
    </div>

    ${aliasTag}
    ${bioHtml}
    ${pivotsHtml}
    ${linksHtml}

    <a href="${item.profile_url}" target="_blank" rel="noopener" class="btn-profile-link">
      Open Profile [↗]
    </a>
  `;
  grid.appendChild(card);
}

function addEmailCard(emailData) {
  const grid = document.getElementById('results-grid');
  const card = document.createElement('div');
  card.className = 'target-card';
  card.style.borderColor = 'var(--status-searching)';

  card.innerHTML = `
    <div class="card-top">
      <span class="platform-name">Email Intelligence</span>
      <span class="category-tag">Identity</span>
    </div>
    <div class="account-handle"><code>${emailData.email}</code></div>
    <div style="font-size:11px;color:var(--text-secondary);">
      Domain: ${emailData.domain} | Gravatar: ${emailData.gravatar.exists ? 'Found' : 'None'}
    </div>
  `;
  grid.appendChild(card);
}

function addPhoneCard(phoneData) {
  const grid = document.getElementById('results-grid');
  const card = document.createElement('div');
  card.className = 'target-card';
  card.style.borderColor = 'var(--status-warn)';

  card.innerHTML = `
    <div class="card-top">
      <span class="platform-name">Carrier & Region</span>
      <span class="category-tag">${phoneData.iso}</span>
    </div>
    <div class="account-handle"><code>${phoneData.e164}</code></div>
    <div style="font-size:11px;color:var(--text-secondary);">
      Country: ${phoneData.country}
    </div>
  `;
  grid.appendChild(card);
}

async function loadHistory() {
  const list = await fetch('/api/dossiers').then(r => r.json());
  const tbody = document.getElementById('history-tbody');
  if (!tbody) return;

  if (list.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#666;">No recorded dossiers yet.</td></tr>';
    return;
  }

  tbody.innerHTML = list.map(d => `
    <tr>
      <td><strong>${d.target_name}</strong></td>
      <td><code>${d.seed_username || d.seed_email || d.seed_phone || '-'}</code></td>
      <td><span class="corrob-badge">${d.confidence !== null && d.confidence !== undefined ? `${d.confidence}%` : 'N/A'}</span></td>
      <td><span class="corrob-badge">${d.found_count} Accounts</span></td>
      <td>${d.created_at}</td>
    </tr>
  `).join('');
}