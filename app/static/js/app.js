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
  setupGraphControls();
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
        }, 50);
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

function setupGraphControls() {
  document.querySelectorAll('#graph-category-filters .filter-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      document.querySelectorAll('#graph-category-filters .filter-chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      if (graphVisualizer) {
        graphVisualizer.setCategoryFilter(chip.dataset.graphCat);
        updateGraphSubFilterBar();
      }
    });
  });

  const searchInput = document.getElementById('graph-search-input');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      if (graphVisualizer) graphVisualizer.setSearchQuery(e.target.value);
    });
  }

  const btnZoomIn = document.getElementById('btn-graph-zoom-in');
  const btnZoomOut = document.getElementById('btn-graph-zoom-out');
  const btnRecenter = document.getElementById('btn-graph-recenter');
  const btnFreeze = document.getElementById('btn-graph-freeze');

  if (btnZoomIn) btnZoomIn.addEventListener('click', () => {
    if (graphVisualizer) {
      graphVisualizer.scale = Math.min(graphVisualizer.scale * 1.25, 5.0);
      graphVisualizer.render();
    }
  });

  if (btnZoomOut) btnZoomOut.addEventListener('click', () => {
    if (graphVisualizer) {
      graphVisualizer.scale = Math.max(graphVisualizer.scale * 0.8, 0.2);
      graphVisualizer.render();
    }
  });

  if (btnRecenter) btnRecenter.addEventListener('click', () => {
    if (graphVisualizer) graphVisualizer.recenter();
  });

  if (btnFreeze) btnFreeze.addEventListener('click', () => {
    if (graphVisualizer) graphVisualizer.toggleFreeze();
  });
}

function updateGraphSubFilterBar() {
  const subBar = document.getElementById('graph-platform-sub-filters');
  if (!subBar || !graphVisualizer) return;

  const currentCat = graphVisualizer.activeCategory;
  let relevantFindings = currentFindings;

  if (currentCat !== 'all' && currentCat !== 'exact') {
    relevantFindings = relevantFindings.filter(f => f.category === currentCat);
  }

  const siteCounts = {};
  relevantFindings.forEach(f => {
    siteCounts[f.site] = (siteCounts[f.site] || 0) + 1;
  });

  const sites = Object.keys(siteCounts).sort();

  if (sites.length > 1) {
    subBar.style.display = 'flex';
    subBar.innerHTML = `
      <button class="sub-chip ${graphVisualizer.activePlatform === 'all' ? 'active' : ''}" data-site="all">
        All ${currentCat === 'all' ? 'Platforms' : currentCat} (${relevantFindings.length})
      </button>
      ${sites.map(s => `
        <button class="sub-chip ${graphVisualizer.activePlatform === s ? 'active' : ''}" data-site="${s}">
          ${s} (${siteCounts[s]})
        </button>
      `).join('')}
    `;

    subBar.querySelectorAll('.sub-chip').forEach(btn => {
      btn.addEventListener('click', () => {
        subBar.querySelectorAll('.sub-chip').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        graphVisualizer.setPlatformFilter(btn.dataset.site);
      });
    });
  } else {
    subBar.style.display = 'none';
    subBar.innerHTML = '';
  }
}

function updateSubFilterBar() {
  const subBar = document.getElementById('sub-filter-row');
  if (!subBar) return;

  if (['Social', 'Developer', 'Gaming', 'Media'].includes(activeCategoryFilter)) {
    const siteCounts = {};
    currentFindings
      .filter(f => f.category === activeCategoryFilter)
      .forEach(f => {
        siteCounts[f.site] = (siteCounts[f.site] || 0) + 1;
      });

    const sites = Object.keys(siteCounts).sort();

    if (sites.length > 0) {
      subBar.style.display = 'flex';
      const totalInCat = currentFindings.filter(f => f.category === activeCategoryFilter).length;

      subBar.innerHTML = `
        <button class="sub-chip ${activePlatformFilter === 'all' ? 'active' : ''}" data-site="all">
          All ${activeCategoryFilter} (${totalInCat})
        </button>
      ` + sites.map(site => {
        const count = siteCounts[site];
        const isActive = (activePlatformFilter === site);
        return `
          <button class="sub-chip ${isActive ? 'active' : ''}" data-site="${site}">
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
  }
}

function initLiveHealthCheck() {
  checkAIHealth();
  setInterval(checkAIHealth, 30000);
}

function setupPermutationPreview() {
  const usernameInput = document.getElementById('input-username');
  const nameInput = document.getElementById('input-name');
  const locationInput = document.getElementById('input-location');
  const previewBar = document.getElementById('permutation-preview-bar');

  let debounceTimer;
  const updatePreview = () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(async () => {
      const username = usernameInput.value.trim();
      const rawNames = nameInput.value.trim();
      const location = locationInput ? locationInput.value.trim() : '';

      if (!username && !rawNames) {
        previewBar.innerHTML = '';
        return;
      }

      const known_names = rawNames ? rawNames.split(',').map(s => s.trim()).filter(Boolean) : [];
      try {
        const res = await fetch('/api/permutations', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, known_names, location, enable_digit_collisions: false })
        }).then(r => r.json());

        const perms = res.permutations || [];
        if (perms.length > 0) {
          previewBar.innerHTML = `
            <div class="variants-badge">
              <span class="badge-dot"></span>
              <span>${perms.length} target handle variations active in scan matrix</span>
            </div>
          `;
        } else {
          previewBar.innerHTML = '';
        }
      } catch (e) {
        previewBar.innerHTML = '';
      }
    }, 300);
  };

  usernameInput.addEventListener('input', updatePreview);
  nameInput.addEventListener('input', updatePreview);
  if (locationInput) locationInput.addEventListener('input', updatePreview);
}

async function setupSettingsModal() {
  const modal = document.getElementById('settings-modal');
  const openBtn = document.getElementById('btn-open-settings');
  const closeBtn = document.getElementById('btn-close-settings');
  const form = document.getElementById('settings-form');
  const providerSelect = document.getElementById('setting-provider');
  const keyInput = document.getElementById('setting-api-key');
  const toggleKeyBtn = document.getElementById('btn-toggle-key');
  const modelSelect = document.getElementById('setting-model-select');
  const hostPresetSelect = document.getElementById('setting-host-preset');
  const hostInput = document.getElementById('setting-host');
  const enableAiChk = document.getElementById('setting-enable-ai');
  const groupKey = document.getElementById('group-api-key');
  const groupHost = document.getElementById('group-ollama-host');
  const testBtn = document.getElementById('btn-test-ai');
  const testStatus = document.getElementById('test-status-box');

  const populateModels = async (provider, chosenModel) => {
    if (provider === 'groq') {
      const apiKey = keyInput.value.trim();
      let modelsToUse = FALLBACK_GROQ_MODELS;

      if (apiKey && apiKey.startsWith('gsk_')) {
        try {
          const res = await fetch(`/api/models/live?key=${encodeURIComponent(apiKey)}`).then(r => r.json());
          if (res && res.models && res.models.length > 0) {
            modelsToUse = res.models;
          }
        } catch (e) {}
      }

      modelSelect.innerHTML = modelsToUse.map(m => `<option value="${m.id}">${m.name}</option>`).join('');

      let target = chosenModel || modelsToUse[0].id;
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

  if (hostPresetSelect) {
    hostPresetSelect.addEventListener('change', () => {
      if (hostPresetSelect.value !== 'custom') {
        hostInput.value = hostPresetSelect.value;
      }
    });
  }

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
    testStatus.style.color = 'var(--status-searching)';
    testStatus.innerText = 'Connecting to inference server...';

    const payload = {
      ai_provider: providerSelect.value,
      ai_api_key: keyInput.value.trim(),
      ai_model: modelSelect.value,
      ai_host: hostInput.value.trim(),
      enable_ai: enableAiChk.checked
    };

    try {
      const res = await fetch('/api/settings/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      }).then(r => r.json());

      if (res.success) {
        testStatus.style.color = 'var(--status-found)';
        testStatus.innerText = `Online: ${res.message}`;
        if (res.discovered_host && hostInput) {
          hostInput.value = res.discovered_host;
        }
      } else {
        testStatus.style.color = 'var(--status-error)';
        testStatus.innerText = `Failed: ${res.error || 'Connection failed'}`;
      }
    } catch (e) {
      testStatus.style.color = 'var(--status-error)';
      testStatus.innerText = `Error: ${e.message}`;
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

    await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    modal.style.display = 'none';
    checkAIHealth();
  });
}

function setupFormSubmit() {
  const form = document.getElementById('scan-form');
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    startReconScan();
  });
}

function startReconScan() {
  const username = document.getElementById('input-username').value.trim();
  const known_names = document.getElementById('input-name').value.trim();
  const location = document.getElementById('input-location') ? document.getElementById('input-location').value.trim() : '';
  const email = document.getElementById('input-email').value.trim();
  const phone = document.getElementById('input-phone').value.trim();
  const enable_permutations = document.getElementById('chk-fuzzy').checked;

  if (!username && !email && !phone && !known_names) {
    alert('Please provide at least a Username, Name, Email, or Phone Number to begin.');
    return;
  }

  currentFindings = [];
  currentEmailInfo = null;
  currentPhoneInfo = null;
  currentBriefingData = null;

  const progressPanel = document.getElementById('progress-panel');
  const briefingCard = document.getElementById('ai-briefing-card');
  const findingsCount = document.getElementById('findings-count');
  const resetBtn = document.getElementById('btn-reset-results');

  progressPanel.style.display = 'block';
  briefingCard.style.display = 'none';
  findingsCount.innerText = 'Probing Target Matrix...';
  if (resetBtn) resetBtn.style.display = 'inline-flex';

  updateSubFilterBar();
  renderFindingsGrid();

  if (graphVisualizer) {
    graphVisualizer.buildFromScan(username || known_names || email || phone, [], null, null);
  }

  const queryParams = new URLSearchParams({
    username,
    known_names,
    location,
    email,
    phone,
    enable_permutations: enable_permutations ? 'true' : 'false'
  });

  if (currentEventSource) currentEventSource.close();
  currentEventSource = new EventSource(`/api/scan/stream?${queryParams.toString()}`);

  currentEventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.type === 'init') {
      document.getElementById('progress-detail').innerText = `Session initialized (Dossier #${data.dossier_id})`;
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
        updateGraphSubFilterBar();
        renderFindingsGrid();
        if (graphVisualizer) {
          graphVisualizer.buildFromScan(username || known_names || email || phone, currentFindings, currentEmailInfo, currentPhoneInfo);
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
            <a href="${ev.url}" target="_blank" rel="noopener noreferrer" class="sub-chip" style="font-size:10px;text-decoration:none;">
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
      updateGraphSubFilterBar();
      renderFindingsGrid();
    }
  };

  currentEventSource.onerror = () => {
    if (currentEventSource) currentEventSource.close();
    document.getElementById('progress-detail').innerText = 'Reconnaissance Complete';
    updateSubFilterBar();
    updateGraphSubFilterBar();
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

  // Count shared avatar hashes for correlation badge
  const hashMatches = {};
  currentFindings.forEach(f => {
    const h = f.metadata?.avatar_hash;
    if (h) {
      if (!hashMatches[h]) hashMatches[h] = [];
      hashMatches[h].push(f.site);
    }
  });

  filtered.forEach(item => addFindingCard(item, hashMatches));
}

function launchPivotScan(targetHandle) {
  const input = document.getElementById('input-username');
  if (input) {
    input.value = targetHandle;
    window.scrollTo({ top: 0, behavior: 'smooth' });
    startReconScan();
  }
}

function addFindingCard(item, hashMatches = {}) {
  const grid = document.getElementById('results-grid');
  const card = document.createElement('div');
  card.className = 'target-card';
  const corrob = item.corroboration || { score: 50, verdict: 'VERIFIED' };
  const meta = item.metadata || {};
  const metrics = meta.metrics || {};
  
  const aliasTag = corrob.matched_alias ? `<span class="alias-tag">Matched: ${corrob.matched_alias}</span>` : '';
  const displayName = meta.display_name ? `<div style="font-size:13px;font-weight:600;color:var(--text-primary);">${meta.display_name}</div>` : '';
  
  const avatarHtml = meta.avatar_url ? `
    <img src="${meta.avatar_url}" class="profile-avatar" alt="Avatar" onerror="this.style.display='none';">
  ` : `
    <div class="profile-avatar-fallback">${item.site.substring(0, 2).toUpperCase()}</div>
  `;

  // Avatar match badge
  let avatarMatchBadge = '';
  if (meta.avatar_hash && hashMatches[meta.avatar_hash] && hashMatches[meta.avatar_hash].length > 1) {
    const others = hashMatches[meta.avatar_hash].filter(s => s !== item.site);
    if (others.length > 0) {
      avatarMatchBadge = `<div class="avatar-match-badge">Shared Photo with ${others.join(', ')}</div>`;
    }
  }

  // Follower / Metric Badges
  let metricsHtml = '';
  const metricItems = [];
  if (metrics.followers) metricItems.push(`<span>Followers: <strong>${metrics.followers}</strong></span>`);
  if (metrics.following) metricItems.push(`<span>Following: <strong>${metrics.following}</strong></span>`);
  if (metrics.posts) metricItems.push(`<span>Posts: <strong>${metrics.posts}</strong></span>`);
  if (metrics.repos) metricItems.push(`<span>Repos: <strong>${metrics.repos}</strong></span>`);

  if (metricItems.length > 0) {
    metricsHtml = `
      <div class="metrics-row">
        ${metricItems.map(m => `<div class="metric-badge">${m}</div>`).join('')}
      </div>
    `;
  }

  const bioHtml = meta.bio ? `
    <div class="profile-bio-box">${meta.bio}</div>
  ` : '';

  // Outbound Links
  let outboundHtml = '';
  if (meta.outbound_links && meta.outbound_links.length > 0) {
    outboundHtml = `
      <div class="outbound-row">
        ${meta.outbound_links.map(link => {
          let label = link.replace(/^https?:\/\/(www\.)?/, '').split('/')[0];
          return `<a href="${link}" target="_blank" rel="noopener noreferrer" class="btn-outbound-link">${label} [↗]</a>`;
        }).join('')}
      </div>
    `;
  }

  // Handle Pivots
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
        ${avatarMatchBadge}
      </div>
    </div>

    ${metricsHtml}
    ${aliasTag}
    ${bioHtml}
    ${outboundHtml}
    ${pivotsHtml}

    <a href="${item.profile_url}" target="_blank" rel="noopener noreferrer" class="btn-profile-link">
      Open Profile [↗]
    </a>
  `;
  grid.appendChild(card);
}

function addEmailCard(emailData) {
  const grid = document.getElementById('results-grid');
  const card = document.createElement('div');
  card.className = 'target-card';

  card.innerHTML = `
    <div class="card-top">
      <span class="platform-name">Email Intelligence</span>
      <span class="category-tag">Identity</span>
    </div>
    <div style="font-size:14px;font-weight:600;color:var(--status-searching);">${emailData.email}</div>
    <div class="profile-bio-box">
      <div>Domain: <strong>${emailData.domain}</strong></div>
      <div>MX Provider: <strong>${emailData.mx_provider}</strong></div>
      <div>Deliverable: <strong>${emailData.deliverable ? 'Confirmed Active' : 'Unknown'}</strong></div>
    </div>
  `;
  grid.appendChild(card);
}

function addPhoneCard(phoneData) {
  const grid = document.getElementById('results-grid');
  const card = document.createElement('div');
  card.className = 'target-card';

  card.innerHTML = `
    <div class="card-top">
      <span class="platform-name">Telephony Intelligence</span>
      <span class="category-tag">Identity</span>
    </div>
    <div style="font-size:14px;font-weight:600;color:var(--status-warn);">${phoneData.e164}</div>
    <div class="profile-bio-box">
      <div>Country: <strong>${phoneData.country || 'Unknown'} (${phoneData.iso})</strong></div>
      <div>Format: <strong>${phoneData.intl_format}</strong></div>
    </div>
  `;
  grid.appendChild(card);
}

async function loadHistory() {
  const tbody = document.getElementById('history-tbody');
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:20px;">Loading dossiers...</td></tr>';

  try {
    const history = await fetch('/api/history').then(r => r.json());
    if (history.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:20px;color:var(--text-muted);">No scan dossiers recorded yet.</td></tr>';
      return;
    }

    tbody.innerHTML = history.map(d => `
      <tr>
        <td><strong>${d.target_name}</strong></td>
        <td style="font-family:var(--font-mono);font-size:11px;">${d.seed_username || d.seed_email || d.seed_phone}</td>
        <td><span class="corrob-badge">${d.ai_confidence}%</span></td>
        <td>${d.findings_count} Profiles</td>
        <td style="font-family:var(--font-mono);font-size:11px;color:var(--text-muted);">${d.created_at}</td>
      </tr>
    `).join('');
  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:20px;color:var(--status-error);">Failed to load history.</td></tr>';
  }
}