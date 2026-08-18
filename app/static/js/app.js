let currentFindings = [];
let currentEmailInfo = null;
let currentPhoneInfo = null;
let graphVisualizer = null;
let currentEventSource = null;
let activeFilter = 'all';

document.addEventListener('DOMContentLoaded', () => {
  graphVisualizer = new IntelligenceGraph('graphCanvas');
  setupNavigation();
  setupPermutationPreview();
  setupFormSubmit();
  setupFilterChips();
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
        graphVisualizer.resize();
      }
      if (btn.dataset.target === 'view-history') {
        loadHistory();
      }
    });
  });
}

function setupFilterChips() {
  document.querySelectorAll('.filter-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      activeFilter = chip.dataset.filter;
      renderFindingsGrid();
    });
  });
}

function setupPermutationPreview() {
  const usernameInput = document.getElementById('input-username');
  const previewBar = document.getElementById('permutation-preview-bar');
  const chkFuzzy = document.getElementById('chk-fuzzy');

  let debounceTimer;
  const updatePreview = () => {
    clearTimeout(debounceTimer);
    const val = usernameInput.value.trim();
    if (!val || !chkFuzzy.checked) {
      previewBar.innerHTML = '';
      return;
    }
    debounceTimer = setTimeout(async () => {
      const data = await API.getPermutations(val, 10);
      if (data.permutations) {
        previewBar.innerHTML = data.permutations.map(p => `
          <span class="perm-chip ${p.is_seed ? 'seed' : ''}">
            ${p.username} <span style="opacity:0.5;">(${Math.round(p.similarity*100)}%)</span>
          </span>
        `).join('');
      }
    }, 250);
  };

  usernameInput.addEventListener('input', updatePreview);
  chkFuzzy.addEventListener('change', updatePreview);
}

function setupFormSubmit() {
  const form = document.getElementById('scan-form');
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    startReconScan();
  });

  document.getElementById('btn-export-json').addEventListener('click', () => {
    const target = document.getElementById('input-username').value || 'Target';
    Exporter.exportJSON(target, currentFindings, currentEmailInfo, currentPhoneInfo);
  });

  document.getElementById('btn-export-html').addEventListener('click', () => {
    const target = document.getElementById('input-username').value || 'Target';
    Exporter.exportHTML(target, currentFindings);
  });
}

function startReconScan() {
  const username = document.getElementById('input-username').value.trim();
  const email = document.getElementById('input-email').value.trim();
  const phone = document.getElementById('input-phone').value.trim();
  const realName = document.getElementById('input-name').value.trim();
  const fuzzy = document.getElementById('chk-fuzzy').checked;

  if (!username && !email && !phone) {
    alert('Please provide at least a username, email, or phone number.');
    return;
  }

  currentFindings = [];
  currentEmailInfo = null;
  currentPhoneInfo = null;
  document.getElementById('results-grid').innerHTML = '';
  document.getElementById('progress-panel').style.display = 'block';
  document.getElementById('findings-count').innerText = '0 Findings';

  if (currentEventSource) currentEventSource.close();

  const params = new URLSearchParams({
    username, email, phone, real_name: realName, fuzzy, max_perms: 12
  });

  currentEventSource = new EventSource(`/api/scan/stream?${params.toString()}`);

  currentEventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);

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
      document.getElementById('progress-detail').innerText = `${progress.completed}/${progress.total} Probes (${res.site})`;
      document.getElementById('progress-bar-fill').style.width = `${progress.percent}%`;

      if (res.found) {
        currentFindings.push(res);
        document.getElementById('findings-count').innerText = `${currentFindings.length} Discovered`;
        renderFindingsGrid();
        if (graphVisualizer) {
          graphVisualizer.buildFromScan(username || email || phone, currentFindings, currentEmailInfo, currentPhoneInfo);
        }
      }
    }

    if (data.type === 'complete') {
      currentEventSource.close();
      document.getElementById('progress-detail').innerText = 'Reconnaissance Complete';
    }
  };

  currentEventSource.onerror = () => {
    if (currentEventSource) currentEventSource.close();
    document.getElementById('progress-detail').innerText = 'Scan session complete.';
  };
}

function renderFindingsGrid() {
  const grid = document.getElementById('results-grid');
  grid.innerHTML = '';

  if (currentEmailInfo && currentEmailInfo.valid_syntax && (activeFilter === 'all' || activeFilter === 'exact')) {
    addEmailCard(currentEmailInfo);
  }
  if (currentPhoneInfo && currentPhoneInfo.valid && (activeFilter === 'all' || activeFilter === 'exact')) {
    addPhoneCard(currentPhoneInfo);
  }

  const filtered = currentFindings.filter(item => {
    if (activeFilter === 'all') return true;
    if (activeFilter === 'exact') return item.is_seed;
    if (activeFilter === 'permutation') return !item.is_seed;
    return item.category === activeFilter;
  });

  // Sort exact matches first, then by match score
  filtered.sort((a, b) => (b.is_seed ? 1 : 0) - (a.is_seed ? 1 : 0));

  filtered.forEach(item => addFindingCard(item));
}

function addFindingCard(item) {
  const grid = document.getElementById('results-grid');
  const card = document.createElement('div');
  card.className = 'target-card';
  const corrob = item.corroboration || { score: 50, verdict: 'VERIFIED' };

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
    <div class="account-handle">Handle: <strong>@${item.username}</strong></div>
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
  const list = await API.getDossiers();
  const tbody = document.getElementById('history-tbody');
  if (!tbody) return;

  if (list.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:#666;">No recorded dossiers yet.</td></tr>';
    return;
  }

  tbody.innerHTML = list.map(d => `
    <tr>
      <td><strong>${d.target_name}</strong></td>
      <td><code>${d.seed_username || d.seed_email || d.seed_phone || '-'}</code></td>
      <td><span class="corrob-badge">${d.found_count} Accounts</span></td>
      <td>${d.created_at}</td>
    </tr>
  `).join('');
}