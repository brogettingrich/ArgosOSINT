let currentFindings = [];
let currentEmailInfo = null;
let currentPhoneInfo = null;
let currentEmailPivots = [];
let currentBreachRecords = [];
let currentBriefingData = null;
let graphVisualizer = null;
let currentEventSource = null;
let activeCategoryFilter = 'all';
let activePlatformFilter = 'all';
let isAIOnline = false;

const FALLBACK_GROQ_MODELS = [
  { id: 'openai/gpt-oss-20b', name: 'GPT-OSS 20B (Recommended · High Limit & Ultra-Fast)' },
  { id: 'groq/compound-mini', name: 'Groq Compound Mini (Fast & Generous Limits)' },
  { id: 'openai/gpt-oss-120b', name: 'GPT-OSS 120B (High Intelligence Flagship)' },
  { id: 'qwen/qwen3.6-27b', name: 'Qwen 3.6 27B (Reasoning Preview)' },
  { id: 'allam-2-7b', name: 'Allam 2 7B' },
  { id: 'llama-3.3-70b-versatile', name: 'Llama 3.3 70B Versatile' },
  { id: 'llama-3.1-8b-instant', name: 'Llama 3.1 8B Instant' }
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
  setupFaceSeedPicker();
  initLiveHealthCheck();
  setupExternalLinkIntercept();
});

/**
 * "Find With Face" seed-photo picker.
 *
 * On desktop browsers, clicking the button invokes the standard fileInput.click().
 * On native Android, Android's WebView has no WebChromeClient attached, so fileInput.click()
 * is silently ignored. For Android, we request /api/face/pick-native to launch the native
 * Intent.ACTION_GET_CONTENT chooser. The result is returned via window.onNativePhotoPicked.
 */
function setupFaceSeedPicker() {
  const btn = document.getElementById('btn-find-with-face');
  const fileInput = document.getElementById('input-face-photo');
  const preview = document.getElementById('face-seed-preview');
  const thumb = document.getElementById('face-seed-thumb');
  const filenameLabel = document.getElementById('face-seed-filename');
  const clearBtn = document.getElementById('btn-clear-face-seed');
  const statusLabel = document.getElementById('face-seed-status');
  if (!btn || !fileInput) return;

  // Check whether running in native Android environment
  let isNativeAndroid = false;
  fetch('/api/face/is-native')
    .then(r => r.json())
    .then(data => {
      if (data && data.is_native) isNativeAndroid = true;
    })
    .catch(() => {});

  btn.addEventListener('click', async () => {
    if (isNativeAndroid) {
      if (statusLabel) {
        statusLabel.textContent = 'Opening gallery…';
        statusLabel.className = 'face-seed-status pending';
      }
      try {
        const resp = await fetch('/api/face/pick-native', { method: 'POST' });
        if (!resp.ok) {
          // Fallback to standard input if native pick request fails
          fileInput.click();
        }
      } catch (err) {
        fileInput.click();
      }
    } else {
      fileInput.click();
    }
  });

  fileInput.addEventListener('change', () => {
    const file = fileInput.files && fileInput.files[0];
    if (!file) return;

    window.faceSeedFile = file;

    const reader = new FileReader();
    reader.onload = (e) => {
      thumb.src = e.target.result;
      filenameLabel.textContent = 'Uploaded'; // never the real filename -- some run long enough to break the row layout
      preview.style.display = 'flex';
      btn.style.display = 'none';
      uploadFaceSeed(file, statusLabel, thumb);
    };
    reader.readAsDataURL(file);
  });

  // Global callback invoked from native Android (main.py -> evaluateJavascript)
  window.onNativePhotoPicked = function(base64Data, filename) {
    try {
      const byteCharacters = atob(base64Data);
      const byteNumbers = new Array(byteCharacters.length);
      for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
      }
      const byteArray = new Uint8Array(byteNumbers);
      const blob = new Blob([byteArray], { type: 'image/jpeg' });
      const file = new File([blob], filename || 'photo.jpg', { type: 'image/jpeg' });

      window.faceSeedFile = file;
      thumb.src = 'data:image/jpeg;base64,' + base64Data;
      filenameLabel.textContent = 'Uploaded';
      preview.style.display = 'flex';
      btn.style.display = 'none';
      uploadFaceSeed(file, statusLabel, thumb);
    } catch (err) {
      console.error('Error handling native photo:', err);
      if (statusLabel) {
        statusLabel.textContent = 'Failed to load photo';
        statusLabel.className = 'face-seed-status error';
      }
    }
  };

  // Global callback invoked if native photo picker is cancelled
  window.onNativePhotoCancelled = function() {
    if (statusLabel && statusLabel.textContent === 'Opening gallery…') {
      statusLabel.textContent = '';
      statusLabel.className = 'face-seed-status';
    }
  };

  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      window.faceSeedFile = null;
      fileInput.value = '';
      preview.style.display = 'none';
      btn.style.display = '';
      if (statusLabel) { statusLabel.textContent = ''; statusLabel.className = 'face-seed-status'; }
    });
  }
}

async function uploadFaceSeed(file, statusLabel, thumbEl) {
  if (statusLabel) {
    statusLabel.textContent = 'Checking photo…';
    statusLabel.className = 'face-seed-status pending';
  }
  try {
    const formData = new FormData();
    formData.append('photo', file);
    const res = await fetch('/api/face/seed', { method: 'POST', body: formData });
    const data = await res.json();
    if (statusLabel) {
      if (data.status === 'ok') {
        // Swap to the actual aligned crop that got analyzed, not the raw
        // upload -- shows exactly what the model saw, same reasoning Cleer's
        // own UI uses for its face thumbnails.
        if (thumbEl && data.analyzed_crop_jpeg_b64) {
          thumbEl.src = 'data:image/jpeg;base64,' + data.analyzed_crop_jpeg_b64;
        }
        statusLabel.textContent = '✓ Face detected';
        statusLabel.className = 'face-seed-status ok';
      } else {
        statusLabel.textContent = data.message || 'Could not use this photo';
        statusLabel.className = 'face-seed-status error';
      }
    }
  } catch (e) {
    if (statusLabel) {
      statusLabel.textContent = 'Upload failed — check connection';
      statusLabel.className = 'face-seed-status error';
    }
  }
}

/**
 * Intercept all anchor clicks inside the WebView.
 * External URLs (anything that is NOT our local 127.0.0.1 server) are
 * sent to /api/open-external so the Android native layer can fire an
 * ACTION_VIEW Intent, opening the link in Chrome / the native app while
 * leaving ArgosOSINT and all scan progress completely untouched.
 * On desktop browsers this is a transparent no-op (fetch returns fast).
 */
function setupExternalLinkIntercept() {
  document.addEventListener('click', function(e) {
    const anchor = e.target.closest('a[href]');
    if (!anchor) return;
    const href = anchor.href || '';
    // Only intercept external http(s) URLs — leave in-page anchors alone
    if ((href.startsWith('http://') || href.startsWith('https://')) &&
        !href.startsWith('http://127.0.0.1') &&
        !href.startsWith('http://localhost')) {
      e.preventDefault();
      e.stopPropagation();
      fetch('/api/open-external?url=' + encodeURIComponent(href))
        .catch(() => {});  // fire-and-forget; errors are silent
    }
  }, true /* capture phase — fires before any other handler */);
}

function setupNavigation() {
  // Unified handler for both desktop (.nav-tab-btn) and mobile (.bottom-nav-btn)
  function activateTab(targetId) {
    document.querySelectorAll('.view-section').forEach(s => s.style.display = 'none');
    document.querySelectorAll('.nav-tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.bottom-nav-btn').forEach(b => b.classList.remove('active'));

    const targetView = document.getElementById(targetId);
    if (targetView) targetView.style.display = 'flex';

    // Sync active class on both nav sets
    document.querySelectorAll(`.nav-tab-btn[data-target="${targetId}"]`).forEach(b => b.classList.add('active'));
    document.querySelectorAll(`.bottom-nav-btn[data-target="${targetId}"]`).forEach(b => b.classList.add('active'));

    if (targetId === 'view-graph' && graphVisualizer) {
      setTimeout(() => {
        graphVisualizer.resize();
        const target = document.getElementById('input-username').value || document.getElementById('input-name').value || 'Target';
        if (currentFindings.length > 0 || currentEmailInfo || currentPhoneInfo) {
          graphVisualizer.buildFromScan(target, currentFindings, currentEmailInfo, currentPhoneInfo);
        }
      }, 50);
    }
    if (targetId === 'view-history') {
      loadHistory();
    }
  }

  document.querySelectorAll('.nav-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => activateTab(btn.dataset.target));
  });

  document.querySelectorAll('.bottom-nav-btn').forEach(btn => {
    btn.addEventListener('click', () => activateTab(btn.dataset.target));
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
        ALL (${relevantFindings.length})
      </button>
      ${sites.map(s => `
        <button class="sub-chip ${graphVisualizer.activePlatform === s ? 'active' : ''}" data-site="${s}">
          ${s.toUpperCase()} (${siteCounts[s]})
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
          ALL ${activeCategoryFilter.toUpperCase()} (${totalInCat})
        </button>
      ` + sites.map(site => {
        const count = siteCounts[site];
        const isActive = (activePlatformFilter === site);
        return `
          <button class="sub-chip ${isActive ? 'active' : ''}" data-site="${site}">
            ${site.toUpperCase()} (${count})
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
    const panel = document.getElementById('progress-panel');
    const bar = document.getElementById('progress-bar-fill');
    const pct = document.getElementById('progress-percent');
    if (panel) panel.style.display = 'none';
    if (bar) bar.style.width = '0%';
    if (pct) pct.innerText = '0%';
  };

  if (dismissBtn) dismissBtn.addEventListener('click', doDismiss);
  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      doDismiss();
      currentFindings = [];
      currentEmailInfo = null;
      currentPhoneInfo = null;
      currentEmailPivots = [];
      currentBreachRecords = [];
      currentBriefingData = null;
      const count = document.getElementById('findings-count');
      const briefing = document.getElementById('ai-briefing-card');
      if (count) count.innerText = '0 DISCOVERED';
      if (briefing) briefing.style.display = 'none';
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
  if (!statusPill || !statusText) return;

  try {
    const res = await fetch('/api/settings/health').then(r => r.json());
    statusText.innerText = res.label;
    isAIOnline = res.online;

    if (res.online) {
      statusText.style.color = 'var(--accent-green)';
      if (collisionBadge) {
        collisionBadge.innerText = `ENGINE ACTIVE (${res.provider.toUpperCase()})`;
        collisionBadge.style.color = 'var(--accent-green)';
      }
    } else {
      statusText.style.color = 'var(--text-muted)';
      if (collisionBadge) {
        collisionBadge.innerText = 'LOCAL DETERMINISTIC MODE';
        collisionBadge.style.color = 'var(--text-secondary)';
      }
    }
  } catch (e) {
    statusText.innerText = 'Offline';
    statusText.style.color = 'var(--text-muted)';
  }

  // Mirror AI status to the mobile inline element (visible only on small screens via mobile.css)
  const mobileStatus = document.getElementById('ai-status-mobile');
  if (mobileStatus) {
    mobileStatus.innerText = statusText.innerText;
    mobileStatus.style.color = statusText.style.color;
  }
}

function initLiveHealthCheck() {
  checkAIHealth();
  setInterval(checkAIHealth, 12000);
}

function setupPermutationPreview() {
  const usernameInput = document.getElementById('input-username');
  const nameInput = document.getElementById('input-name');
  const locationInput = document.getElementById('input-location');
  const fuzzyChk = document.getElementById('chk-fuzzy');
  const digitsChk = document.getElementById('chk-digits');
  const previewBar = document.getElementById('permutation-preview-bar');

  if (!usernameInput || !previewBar) return;

  let debounceTimer;

  const updatePreview = () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(async () => {
      const u = usernameInput.value.trim();
      const n = nameInput.value.trim();
      const loc = locationInput ? locationInput.value.trim() : '';
      const allowFuzzy = fuzzyChk ? fuzzyChk.checked : true;
      const allowDigits = digitsChk ? digitsChk.checked : false;

      if (!u && !n) {
        previewBar.style.display = 'none';
        previewBar.innerHTML = '';
        return;
      }

      const names = n ? n.split(',').map(s => s.trim()).filter(Boolean) : [];

      try {
        const res = await fetch('/api/permutations', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            username: u,
            known_names: names,
            location: loc,
            enable_digit_collisions: allowDigits
          })
        }).then(r => r.json());

        let perms = res.permutations || [];
        if (!allowFuzzy) {
          perms = perms.filter(p => p.is_seed);
        }

        if (perms.length > 1) {
          const seeds = perms.filter(p => p.is_seed).map(p => `@${p.username}`);
          const nonSeeds = perms.filter(p => !p.is_seed).map(p => `@${p.username}`);
          const displayCount = Math.min(perms.length, 12);
          const shown = [...seeds, ...nonSeeds].slice(0, displayCount);
          const remainder = perms.length - shown.length;

          previewBar.style.display = 'block';
          previewBar.innerHTML = `
            <span>TARGET MUTATIONS (${perms.length} IDENTIFIERS):</span>
            <span style="color:var(--text-secondary);">${shown.join(' · ')}${remainder > 0 ? ` · +${remainder} more` : ''}</span>
          `;
        } else {
          previewBar.style.display = 'none';
          previewBar.innerHTML = '';
        }
      } catch (e) {
        previewBar.style.display = 'none';
        previewBar.innerHTML = '';
      }
    }, 250);
  };

  usernameInput.addEventListener('input', updatePreview);
  nameInput.addEventListener('input', updatePreview);
  if (locationInput) locationInput.addEventListener('input', updatePreview);
  if (fuzzyChk) fuzzyChk.addEventListener('change', updatePreview);
  if (digitsChk) digitsChk.addEventListener('change', updatePreview);
}

async function setupSettingsModal() {
  const modal = document.getElementById('settings-modal');
  const openBtn = document.getElementById('btn-open-settings');
  const closeBtn = document.getElementById('btn-close-settings');
  const form = document.getElementById('settings-form');
  const providerSelect = document.getElementById('setting-provider');
  const keyInput = document.getElementById('setting-api-key');
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
      let modelsToUse = FALLBACK_GROQ_MODELS;
      try {
        const apiKey = (keyInput ? keyInput.value.trim() : '') || localStorage.getItem('argos_groq_api_key') || '';
        const res = await fetch(`/api/models/live?key=${encodeURIComponent(apiKey)}`).then(r => r.json());
        if (res && res.models && res.models.length > 0) {
          modelsToUse = res.models;
        }
      } catch (e) {}

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

  // Load persistent settings from Server with localStorage sync
  try {
    const serverSettings = await fetch('/api/settings').then(r => r.json());
    if (serverSettings.ai_provider) providerSelect.value = serverSettings.ai_provider;
    if (serverSettings.ai_host) hostInput.value = serverSettings.ai_host;
    enableAiChk.checked = serverSettings.enable_ai !== false;

    const storedKey = serverSettings.ai_api_key || localStorage.getItem('argos_groq_api_key') || '';
    if (keyInput) {
      keyInput.value = storedKey;
      if (storedKey) {
        localStorage.setItem('argos_groq_api_key', storedKey);
      }
    }

    await populateModels(providerSelect.value, serverSettings.ai_model);
  } catch (e) {}

  if (keyInput) {
    keyInput.addEventListener('input', () => {
      const val = keyInput.value.trim();
      if (val) {
        localStorage.setItem('argos_groq_api_key', val);
      }
    });
  }

  providerSelect.addEventListener('change', updateVisibility);
  updateVisibility();

  if (openBtn) {
    openBtn.addEventListener('click', () => {
      modal.style.display = 'flex';
      testStatus.style.display = 'none';
      const localBackup = localStorage.getItem('argos_groq_api_key');
      if (localBackup && keyInput && !keyInput.value) {
        keyInput.value = localBackup;
      }
      updateVisibility();
    });
  }

  if (closeBtn) {
    closeBtn.addEventListener('click', () => {
      modal.style.display = 'none';
    });
  }

  if (testBtn) {
    testBtn.addEventListener('click', async () => {
      testStatus.style.display = 'block';
      testStatus.style.color = 'var(--text-secondary)';
      testStatus.innerText = 'Connecting to inference server...';

      const apiKey = keyInput.value.trim();
      if (apiKey) {
        localStorage.setItem('argos_groq_api_key', apiKey);
      }

      const payload = {
        ai_provider: providerSelect.value,
        ai_api_key: apiKey,
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
          testStatus.style.color = 'var(--accent-green)';
          testStatus.innerText = `ONLINE: ${res.message}`;
          if (res.discovered_host && hostInput) {
            hostInput.value = res.discovered_host;
          }
        } else {
          testStatus.style.color = 'var(--accent-red)';
          testStatus.innerText = `FAILED: ${res.error || 'Connection failed'}`;
        }
      } catch (e) {
        testStatus.style.color = 'var(--accent-red)';
        testStatus.innerText = `ERROR: ${e.message}`;
      }
    });
  }

  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const apiKey = keyInput.value.trim();
      if (apiKey) {
        localStorage.setItem('argos_groq_api_key', apiKey);
      }

      const payload = {
        ai_provider: providerSelect.value,
        ai_api_key: apiKey,
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
}

function setupFormSubmit() {
  const form = document.getElementById('scan-form');
  if (!form) return;
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    startReconScan();
  });
}

function startReconScan() {
  // The backend consumes whatever seed photo is staged into THIS scan's new
  // dossier the moment it starts (see _consume_pending_face_seed in main.py)
  // -- reset the picker UI here to match, so it can't misleadingly look
  // like the same photo is still staged for a future, unrelated scan.
  const faceBtn = document.getElementById('btn-find-with-face');
  const facePreview = document.getElementById('face-seed-preview');
  if (window.faceSeedFile && faceBtn && facePreview) {
    window.faceSeedFile = null;
    facePreview.style.display = 'none';
    faceBtn.style.display = '';
  }

  const username = document.getElementById('input-username').value.trim();
  const known_names = document.getElementById('input-name').value.trim();
  const location = document.getElementById('input-location') ? document.getElementById('input-location').value.trim() : '';
  const email = document.getElementById('input-email').value.trim();
  const phone = document.getElementById('input-phone').value.trim();
  const enable_permutations = document.getElementById('chk-fuzzy') ? document.getElementById('chk-fuzzy').checked : true;
  const enable_digit_collisions = document.getElementById('chk-digits') ? document.getElementById('chk-digits').checked : false;

  if (!username && !email && !phone && !known_names) {
    alert('Please enter at least a Username, Name, Email, or Phone Number to begin.');
    return;
  }

  currentFindings = [];
  currentEmailInfo = null;
  currentPhoneInfo = null;
  currentEmailPivots = [];
  currentBreachRecords = [];
  currentBriefingData = null;

  const progressPanel = document.getElementById('progress-panel');
  const briefingCard = document.getElementById('ai-briefing-card');
  const findingsCount = document.getElementById('findings-count');
  const resetBtn = document.getElementById('btn-reset-results');

  if (progressPanel) progressPanel.style.display = 'block';
  if (briefingCard) briefingCard.style.display = 'none';
  if (findingsCount) findingsCount.innerText = 'PROBING TARGET MATRIX...';
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
    enable_permutations: enable_permutations ? 'true' : 'false',
    enable_digit_collisions: enable_digit_collisions ? 'true' : 'false'
  });

  if (currentEventSource) currentEventSource.close();
  currentEventSource = new EventSource(`/api/scan/stream?${queryParams.toString()}`);

  currentEventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.type === 'init') {
      const detail = document.getElementById('progress-detail');
      if (detail) detail.innerText = `Session Initialized (Dossier #${data.dossier_id.substring(0, 8)})`;
    }

    if (data.type === 'email_result') {
      currentEmailInfo = data.data;
      renderFindingsGrid();
    }

    if (data.type === 'email_pivots') {
      currentEmailPivots = data.pivots || [];
      currentBreachRecords = data.breaches || [];

      (data.pivots || []).forEach(p => {
        const exists = currentFindings.some(f => f.site === p.service && f.username === p.username);
        if (!exists) {
          currentFindings.push({
            site: p.service,
            category: p.category || 'Email Pivot',
            username: p.username,
            profile_url: p.profile_url,
            found: true,
            status_code: 200,
            is_seed: true,
            is_email_pivot: true,
            corroboration: { score: 95, verdict: 'EMAIL REGISTERED' },
            metadata: {
              display_name: p.display_name,
              bio: p.bio,
              avatar_url: p.avatar_url,
              metrics: p.metrics || {}
            }
          });
        }
      });

      const countEl = document.getElementById('findings-count');
      if (countEl) countEl.innerText = `${currentFindings.length} DISCOVERED`;
      updateSubFilterBar();
      updateGraphSubFilterBar();
      renderFindingsGrid();
      if (graphVisualizer) {
        graphVisualizer.buildFromScan(username || known_names || email || phone, currentFindings, currentEmailInfo, currentPhoneInfo);
      }
    }

    if (data.type === 'phone_result') {
      currentPhoneInfo = data.data;
      renderFindingsGrid();
    }

    if (data.type === 'probe_result') {
      const res = data.result;
      const progress = data.progress;
      const pctEl = document.getElementById('progress-percent');
      const detailEl = document.getElementById('progress-detail');
      const barFill = document.getElementById('progress-bar-fill');
      const countEl = document.getElementById('findings-count');

      if (pctEl) pctEl.innerText = `${progress.percent}%`;
      if (detailEl) detailEl.innerText = `Probing ${res.site} (@${res.username})...`;
      if (barFill) barFill.style.width = `${progress.percent}%`;

      if (res.found) {
        currentFindings.push(res);
        if (countEl) countEl.innerText = `${currentFindings.length} DISCOVERED`;
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

      currentBriefingData = data.briefing;

      if (card && text) {
        let briefingContent = (typeof data.briefing === 'string') ? data.briefing : (data.briefing.briefing || '');
        briefingContent = briefingContent.replace(/<think>[\s\S]*?<\/think>/gi, '');
        briefingContent = briefingContent.replace(/<think>[\s\S]*/gi, '');
        briefingContent = briefingContent.replace(/```(?:json)?[\s\S]*?```/gi, '');
        briefingContent = briefingContent.replace(/^(?:Here's a thinking process|Analysis|Reasoning|Output|Draft Briefing):\s*/gi, '');
        briefingContent = briefingContent.replace(/[\*\#\_`]/g, '').trim();

        text.innerText = briefingContent;
        
        if (confBadge && data.briefing.confidence !== undefined) {
          confBadge.innerText = `CONFIDENCE: ${data.briefing.confidence}%`;
        }

        if (identTag) {
          if (data.briefing.verified_identities && data.briefing.verified_identities.length > 0) {
            identTag.innerText = `VERIFIED: ${data.briefing.verified_identities.join(', ')}`;
            identTag.style.color = 'var(--accent-green)';
          } else if (data.briefing.inferred_identity) {
            identTag.innerText = `INFERRED: ${data.briefing.inferred_identity}`;
            identTag.style.color = 'var(--accent-amber)';
          }
        }

        if (rationaleEl && data.briefing.rationale) {
          rationaleEl.innerText = `Rationale: ${data.briefing.rationale}`;
        }

        card.style.display = 'block';
      }
    }

    if (data.type === 'complete') {
      currentEventSource.close();
      const detail = document.getElementById('progress-detail');
      const pctEl = document.getElementById('progress-percent');
      const barFill = document.getElementById('progress-bar-fill');
      if (detail) detail.innerText = 'Probe Sequence Completed';
      if (pctEl) pctEl.innerText = '100%';
      if (barFill) barFill.style.width = '100%';
      updateSubFilterBar();
      updateGraphSubFilterBar();
      renderFindingsGrid();
      if (graphVisualizer) {
        graphVisualizer.buildFromScan(username || known_names || email || phone, currentFindings, currentEmailInfo, currentPhoneInfo);
      }
    }
  };

  currentEventSource.onerror = () => {
    if (currentEventSource) currentEventSource.close();
    const detail = document.getElementById('progress-detail');
    const pctEl = document.getElementById('progress-percent');
    const barFill = document.getElementById('progress-bar-fill');
    if (detail) detail.innerText = 'Probe Sequence Completed';
    if (pctEl) pctEl.innerText = '100%';
    if (barFill) barFill.style.width = '100%';
    updateSubFilterBar();
    updateGraphSubFilterBar();
    renderFindingsGrid();
    if (graphVisualizer) {
      graphVisualizer.buildFromScan(username || known_names || email || phone, currentFindings, currentEmailInfo, currentPhoneInfo);
    }
  };
}

function renderFindingsGrid() {
  const grid = document.getElementById('results-grid');
  if (!grid) return;
  grid.innerHTML = '';

  if (activeCategoryFilter === 'breaches') {
    if (currentBreachRecords.length === 0) {
      const empty = document.createElement('div');
      empty.style.gridColumn = '1 / -1';
      empty.style.padding = '24px';
      empty.style.textAlign = 'center';
      empty.style.color = 'var(--text-muted)';
      empty.style.fontFamily = 'var(--font-mono)';
      empty.style.fontSize = '11px';
      empty.style.background = 'var(--bg-layer-1)';
      empty.innerText = 'NO PUBLIC BREACH RECORDS DETECTED FOR TARGET';
      grid.appendChild(empty);
      return;
    }
    currentBreachRecords.forEach(b => addBreachCard(b));
    return;
  }

  if (currentEmailInfo && currentEmailInfo.valid_syntax && (activeCategoryFilter === 'all' || activeCategoryFilter === 'exact')) {
    addEmailCard(currentEmailInfo);
  }
  if (currentPhoneInfo && currentPhoneInfo.valid && (activeCategoryFilter === 'all' || activeCategoryFilter === 'exact')) {
    addPhoneCard(currentPhoneInfo);
  }

  let filtered = currentFindings.filter(item => {
    if (activeCategoryFilter === 'all') return true;
    if (activeCategoryFilter === 'exact') return item.is_seed && !item.is_email_pivot;
    if (activeCategoryFilter === 'email_pivot') return item.is_email_pivot;
    if (activeCategoryFilter === 'permutation') return !item.is_seed;
    if (activeCategoryFilter === 'faces') {
      const factors = (item.corroboration && item.corroboration.factors) || [];
      return factors.some(f => f.startsWith('Face match'));
    }
    return item.category === activeCategoryFilter;
  });

  if (activePlatformFilter !== 'all') {
    filtered = filtered.filter(item => item.site === activePlatformFilter);
  }

  filtered.sort((a, b) => (b.is_seed ? 1 : 0) - (a.is_seed ? 1 : 0));

  if (filtered.length === 0 && (!currentEmailInfo || !currentEmailInfo.valid_syntax) && (!currentPhoneInfo || !currentPhoneInfo.valid) && (currentBreachRecords.length === 0 || activeCategoryFilter !== 'all')) {
    const empty = document.createElement('div');
    empty.style.gridColumn = '1 / -1';
    empty.style.padding = '24px';
    empty.style.textAlign = 'center';
    empty.style.color = 'var(--text-muted)';
    empty.style.fontFamily = 'var(--font-mono)';
    empty.style.fontSize = '11px';
    empty.style.background = 'var(--bg-layer-1)';
    empty.innerText = 'NO MATCHING TARGET ENTITIES DISCOVERED';
    grid.appendChild(empty);
    return;
  }

  const hashMatches = {};
  currentFindings.forEach(f => {
    const h = f.metadata && f.metadata.avatar_hash;
    if (h) {
      if (!hashMatches[h]) hashMatches[h] = [];
      hashMatches[h].push(f.site);
    }
  });

  filtered.forEach(item => addFindingCard(item, hashMatches));

  if (activeCategoryFilter === 'all' && currentBreachRecords.length > 0) {
    currentBreachRecords.forEach(b => addBreachCard(b));
  }
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
  if (!grid) return;
  const card = document.createElement('div');
  card.className = 'target-card';
  const corrob = item.corroboration || { score: 50, verdict: 'VERIFIED' };
  const meta = item.metadata || {};
  const metrics = meta.metrics || {};
  
  const displayName = meta.display_name ? `<div class="display-name-text">${meta.display_name}</div>` : '';
  
  const avatarHtml = meta.avatar_url ? `
    <img src="${meta.avatar_url}" class="profile-avatar" alt="Avatar" onerror="this.style.display='none';">
  ` : `
    <div class="profile-avatar-fallback">${item.site.substring(0, 2).toUpperCase()}</div>
  `;

  let avatarMatchText = '';
  if (meta.avatar_hash && hashMatches[meta.avatar_hash] && hashMatches[meta.avatar_hash].length > 1) {
    const others = hashMatches[meta.avatar_hash].filter(s => s !== item.site);
    if (others.length > 0) {
      avatarMatchText = `<div class="avatar-correlate-text">IDENTICAL PHOTO // ${others.join(', ').toUpperCase()}</div>`;
    }
  }

  let factorsHtml = '';
  if (corrob.factors && corrob.factors.length > 0 && !item.is_seed && !item.is_email_pivot) {
    factorsHtml = `
      <div class="corrob-factors-row">
        ${corrob.factors.map(f => `<span class="corrob-factor-tag${f.startsWith('Face match') ? ' face-match' : ''}">${f}</span>`).join('')}
      </div>
    `;
  }

  let metricsHtml = '';
  const metricItems = [];
  if (metrics.followers) metricItems.push(`<span class="metric-item">FOLL: <strong>${metrics.followers}</strong></span>`);
  if (metrics.following) metricItems.push(`<span class="metric-item">FLWG: <strong>${metrics.following}</strong></span>`);
  if (metrics.posts) metricItems.push(`<span class="metric-item">POSTS: <strong>${metrics.posts}</strong></span>`);
  if (metrics.repos) metricItems.push(`<span class="metric-item">REPOS: <strong>${metrics.repos}</strong></span>`);
  if (metrics.karma) metricItems.push(`<span class="metric-item">KARMA: <strong>${metrics.karma}</strong></span>`);

  if (metricItems.length > 0) {
    metricsHtml = `<div class="metrics-row">${metricItems.join(' · ')}</div>`;
  }

  const bioHtml = meta.bio ? `<div class="profile-bio-box">${meta.bio}</div>` : '';

  let pivotsHtml = '';
  if (meta.mentioned_handles && meta.mentioned_handles.length > 0) {
    pivotsHtml = `
      <div class="pivot-actions-row">
        <span class="pivot-label">Pivot:</span>
        ${meta.mentioned_handles.map(h => `
          <button type="button" class="btn-pivot-trigger" onclick="launchPivotScan('${h}')">
            @${h}
          </button>
        `).join('')}
      </div>
    `;
  }

  let indicatorHtml = '';
  if (item.is_email_pivot) {
    indicatorHtml = `<span class="corrob-indicator" style="color:var(--accent-cyan, #06b6d4);background:rgba(6, 182, 212, 0.1);border-color:rgba(6, 182, 212, 0.3);">● EMAIL REGISTERED</span>`;
  } else if (item.is_seed) {
    indicatorHtml = `<span class="corrob-indicator exact">● EXACT</span>`;
  } else {
    indicatorHtml = `<span class="corrob-indicator">● ${corrob.score}% MATCH</span>`;
  }

  card.innerHTML = `
    <div class="card-top">
      <span class="platform-name">
        <span>${item.site.toUpperCase()}</span>
        <span class="category-tag">// ${item.is_email_pivot ? 'EMAIL PIVOT' : item.category}</span>
      </span>
      ${indicatorHtml}
    </div>

    <div class="profile-header-row">
      ${avatarHtml}
      <div class="profile-meta-col">
        ${displayName}
        <div class="account-handle-text">@${item.username}</div>
        ${avatarMatchText}
      </div>
    </div>

    ${factorsHtml}
    ${metricsHtml}
    ${bioHtml}
    ${pivotsHtml}

    <a href="${item.profile_url}" target="_blank" rel="noopener noreferrer" class="btn-profile-link">
      OPEN PROFILE [↗]
    </a>
  `;
  grid.appendChild(card);
}

function addBreachCard(breach) {
  const grid = document.getElementById('results-grid');
  if (!grid) return;
  const card = document.createElement('div');
  card.className = 'target-card';
  card.style.border = '1px solid rgba(239, 68, 68, 0.3)';

  const classesPills = (breach.data_classes || []).map(c => `
    <span style="font-family:var(--font-mono);font-size:10px;padding:2px 6px;background:rgba(239, 68, 68, 0.15);color:var(--accent-red);border:1px solid rgba(239, 68, 68, 0.3);">
      ${c}
    </span>
  `).join(' ');

  card.innerHTML = `
    <div class="card-top">
      <span class="platform-name" style="color:var(--accent-red);">
        <span>${breach.breach_name.toUpperCase()}</span>
        <span class="category-tag">// BREACH EXPOSURE</span>
      </span>
      <span class="corrob-indicator" style="color:var(--accent-red);background:rgba(239, 68, 68, 0.1);border-color:rgba(239, 68, 68, 0.3);">
        ● COMPROMISED
      </span>
    </div>
    <div style="font-size:12px;font-weight:600;font-family:var(--font-mono);color:#ffffff;margin-top:6px;margin-bottom:6px;">
      ${breach.compromised_email}
    </div>
    <div class="profile-bio-box">
      <div style="font-family:var(--font-mono);font-size:11px;color:var(--text-secondary);margin-bottom:6px;">
        EXPOSURE YEAR: <strong>${breach.year}</strong> · IMPACT: <strong>${breach.pwn_count}</strong>
      </div>
      <div style="display:flex;gap:4px;flex-wrap:wrap;">${classesPills}</div>
    </div>
  `;
  grid.appendChild(card);
}

function addEmailCard(emailData) {
  const grid = document.getElementById('results-grid');
  if (!grid) return;
  const card = document.createElement('div');
  card.className = 'target-card';

  card.innerHTML = `
    <div class="card-top">
      <span class="platform-name">EMAIL FOOTPRINT</span>
      <span class="category-tag">// IDENTITY</span>
    </div>
    <div style="font-size:13px;font-weight:600;font-family:var(--font-mono);color:#ffffff;">${emailData.email}</div>
    <div class="profile-bio-box">
      <div>DOMAIN: <strong>${emailData.domain}</strong></div>
      <div>MX PROVIDER: <strong>${emailData.mx_provider}</strong></div>
      <div>DELIVERABLE: <strong>${emailData.deliverable ? 'YES' : 'UNKNOWN'}</strong></div>
    </div>
  `;
  grid.appendChild(card);
}

function addPhoneCard(phoneData) {
  const grid = document.getElementById('results-grid');
  if (!grid) return;
  const card = document.createElement('div');
  card.className = 'target-card';

  card.innerHTML = `
    <div class="card-top">
      <span class="platform-name">TELEPHONY INTEL</span>
      <span class="category-tag">// IDENTITY</span>
    </div>
    <div style="font-size:13px;font-weight:600;font-family:var(--font-mono);color:#ffffff;">${phoneData.e164}</div>
    <div class="profile-bio-box">
      <div>COUNTRY: <strong>${phoneData.country || 'UNKNOWN'} (${phoneData.iso})</strong></div>
      <div>FORMAT: <strong>${phoneData.intl_format}</strong></div>
      ${phoneData.carrier ? `<div>CARRIER: <strong>${phoneData.carrier}</strong></div>` : ''}
    </div>
  `;
  grid.appendChild(card);
}

async function loadHistory() {
  const tbody = document.getElementById('history-tbody');
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:20px;color:var(--text-muted);">LOADING DOSSIERS...</td></tr>';

  try {
    const history = await fetch('/api/history').then(r => r.json());
    if (history.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:20px;color:var(--text-muted);">NO STORED DOSSIERS</td></tr>';
      return;
    }

    tbody.innerHTML = history.map(d => `
      <tr style="border-bottom:1px solid var(--border-subtle);">
        <td style="padding:10px 8px;color:#ffffff;font-weight:600;">${d.target_name}</td>
        <td style="padding:10px 8px;color:var(--text-secondary);">${d.seed_username || d.seed_email || d.seed_phone}</td>
        <td style="padding:10px 8px;color:var(--accent-green);">${d.confidence}%</td>
        <td style="padding:10px 8px;color:var(--text-secondary);">${d.findings_count} PROFILES</td>
        <td style="padding:10px 8px;color:var(--text-muted);">${d.created_at}</td>
      </tr>
    `).join('');
  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:20px;color:var(--accent-red);">FAILED TO LOAD HISTORY</td></tr>';
  }
}
