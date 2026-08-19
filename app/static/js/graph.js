class IntelligenceGraph {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.nodes = [];
    this.links = [];
    this.scale = 1.0;
    this.offsetX = 0;
    this.offsetY = 0;
    this.isDragging = false;
    this.dragNode = null;
    this.lastMouseX = 0;
    this.lastMouseY = 0;
    this.isFrozen = false;
    this.simTicks = 0;
    this.activeCategory = 'all';
    this.activePlatform = 'all';
    this.searchQuery = '';
    this.hoverNode = null;

    this.categoryAngles = {
      'Social': { start: 0, end: Math.PI * 0.7 },
      'Developer': { start: Math.PI * 0.75, end: Math.PI * 1.25 },
      'Gaming': { start: Math.PI * 1.3, end: Math.PI * 1.7 },
      'Media': { start: Math.PI * 1.75, end: Math.PI * 2.0 },
      'General': { start: 0, end: Math.PI * 2.0 }
    };

    this.initEvents();
    this.resize();
    window.addEventListener('resize', () => this.resize());
  }

  resize() {
    if (!this.canvas) return;
    const parent = this.canvas.parentElement;
    this.canvas.width = parent.clientWidth || 900;
    this.canvas.height = parent.clientHeight || 650;
    if (this.offsetX === 0 && this.offsetY === 0) {
      this.offsetX = this.canvas.width / 2;
      this.offsetY = this.canvas.height / 2;
    }
    this.render();
  }

  recenter() {
    this.scale = 1.0;
    this.offsetX = this.canvas.width / 2;
    this.offsetY = this.canvas.height / 2;
    this.render();
  }

  toggleFreeze() {
    this.isFrozen = !this.isFrozen;
    const btn = document.getElementById('btn-graph-freeze');
    if (btn) {
      btn.innerText = this.isFrozen ? 'Unfreeze Physics' : 'Freeze Physics';
    }
    if (!this.isFrozen) {
      this.simTicks = 0;
      this.animate();
    }
  }

  setCategoryFilter(category) {
    this.activeCategory = category;
    this.activePlatform = 'all';
    this.render();
  }

  setPlatformFilter(platform) {
    this.activePlatform = platform;
    this.render();
  }

  setSearchQuery(q) {
    this.searchQuery = (q || '').trim().toLowerCase();
    this.render();
  }

  buildFromScan(seedIdentifier, findings = [], emailInfo = null, phoneInfo = null) {
    this.nodes = [];
    this.links = [];
    this.simTicks = 0;
    this.isFrozen = false;

    // Center Root Node
    const rootNode = {
      id: 'root',
      label: seedIdentifier || 'Target Identity',
      category: 'Target',
      type: 'root',
      x: 0,
      y: 0,
      vx: 0,
      vy: 0,
      radius: 26,
      color: '#ffffff',
      strokeColor: '#10b981',
      isRoot: true,
      data: { seed: seedIdentifier }
    };
    this.nodes.push(rootNode);

    // Email Node
    if (emailInfo && emailInfo.email) {
      const emailNode = {
        id: 'email-root',
        label: emailInfo.email,
        category: 'Identity',
        type: 'email',
        x: -180,
        y: -140,
        vx: 0,
        vy: 0,
        radius: 18,
        color: '#06b6d4',
        strokeColor: '#0891b2',
        data: emailInfo
      };
      this.nodes.push(emailNode);
      this.links.push({ source: rootNode, target: emailNode, label: 'Email', color: '#06b6d4' });
    }

    // Phone Node
    if (phoneInfo && phoneInfo.e164) {
      const phoneNode = {
        id: 'phone-root',
        label: phoneInfo.e164,
        category: 'Identity',
        type: 'phone',
        x: 180,
        y: -140,
        vx: 0,
        vy: 0,
        radius: 18,
        color: '#f59e0b',
        strokeColor: '#d97706',
        data: phoneInfo
      };
      this.nodes.push(phoneNode);
      this.links.push({ source: rootNode, target: phoneNode, label: 'Phone', color: '#f59e0b' });
    }

    const catBuckets = { 'Social': [], 'Developer': [], 'Gaming': [], 'Media': [], 'General': [] };
    const avatarMap = {};

    findings.forEach(f => {
      const cat = f.category || 'General';
      if (!catBuckets[cat]) catBuckets[cat] = [];
      catBuckets[cat].push(f);
    });

    Object.keys(catBuckets).forEach(cat => {
      const list = catBuckets[cat];
      if (list.length === 0) return;

      const sector = this.categoryAngles[cat] || { start: 0, end: Math.PI * 2 };
      const arc = sector.end - sector.start;
      const angleStep = arc / Math.max(list.length, 1);

      list.forEach((f, idx) => {
        const theta = sector.start + (idx + 0.5) * angleStep;
        const ringRadius = f.is_seed ? (240 + (idx % 2) * 50) : (380 + (idx % 3) * 60);

        const node = {
          id: `node-${f.site}-${f.username}`,
          label: `@${f.username}`,
          subLabel: f.site,
          category: f.category,
          type: 'account',
          site: f.site,
          username: f.username,
          profile_url: f.profile_url,
          is_seed: f.is_seed,
          avatar_hash: f.metadata?.avatar_hash,
          x: Math.cos(theta) * ringRadius,
          y: Math.sin(theta) * ringRadius,
          vx: 0,
          vy: 0,
          radius: f.is_seed ? 17 : 13,
          color: this.getCategoryColor(f.category),
          strokeColor: f.is_seed ? '#ffffff' : this.getCategoryColor(f.category),
          data: f
        };
        this.nodes.push(node);
        this.links.push({
          source: rootNode,
          target: node,
          label: f.is_seed ? 'Exact Match' : 'Permutation',
          color: f.is_seed ? '#10b981' : '#2a364e',
          width: f.is_seed ? 2 : 1
        });

        // Group by avatar hash for cross-platform visual links
        if (node.avatar_hash) {
          if (!avatarMap[node.avatar_hash]) avatarMap[node.avatar_hash] = [];
          avatarMap[node.avatar_hash].push(node);
        }
      });
    });

    // Draw Cross-Platform Avatar Correlation Links
    Object.values(avatarMap).forEach(matchedNodes => {
      if (matchedNodes.length > 1) {
        for (let i = 0; i < matchedNodes.length - 1; i++) {
          this.links.push({
            source: matchedNodes[i],
            target: matchedNodes[i + 1],
            label: 'Avatar Match',
            color: '#06b6d4',
            width: 2,
            dashed: true
          });
        }
      }
    });

    this.animate();
  }

  getCategoryColor(cat) {
    switch (cat) {
      case 'Social': return '#3b82f6';
      case 'Developer': return '#10b981';
      case 'Gaming': return '#8b5cf6';
      case 'Media': return '#ec4899';
      case 'Crypto': return '#f59e0b';
      default: return '#94a3b8';
    }
  }

  animate() {
    if (this.isFrozen) return;

    if (this.simTicks < 45) {
      this.simTicks++;
      this.applyForces();
      this.render();
      requestAnimationFrame(() => this.animate());
    } else {
      this.isFrozen = true;
      this.render();
    }
  }

  applyForces() {
    const kRepel = 7000;
    const minDistance = 95;

    for (let i = 0; i < this.nodes.length; i++) {
      for (let j = i + 1; j < this.nodes.length; j++) {
        const n1 = this.nodes[i];
        const n2 = this.nodes[j];

        const dx = n2.x - n1.x;
        const dy = n2.y - n1.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;

        if (dist < minDistance * 2.5) {
          const force = (kRepel / (dist * dist));
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;

          if (!n1.isRoot) { n1.vx -= fx; n1.vy -= fy; }
          if (!n2.isRoot) { n2.vx += fx; n2.vy += fy; }
        }
      }
    }

    const damping = 0.65;
    for (let i = 0; i < this.nodes.length; i++) {
      const n = this.nodes[i];
      if (n.isRoot) continue;
      n.x += n.vx * 0.1;
      n.y += n.vy * 0.1;
      n.vx *= damping;
      n.vy *= damping;
    }
  }

  isNodeVisible(n) {
    if (n.isRoot || n.type === 'email' || n.type === 'phone') return true;

    if (this.activeCategory !== 'all') {
      if (this.activeCategory === 'exact' && !n.is_seed) return false;
      if (this.activeCategory !== 'exact' && n.category !== this.activeCategory) return false;
    }

    if (this.activePlatform !== 'all' && n.site !== this.activePlatform) {
      return false;
    }

    if (this.searchQuery) {
      const matchLabel = n.label && n.label.toLowerCase().includes(this.searchQuery);
      const matchSite = n.site && n.site.toLowerCase().includes(this.searchQuery);
      const matchDisp = n.data?.metadata?.display_name && n.data.metadata.display_name.toLowerCase().includes(this.searchQuery);
      if (!matchLabel && !matchSite && !matchDisp) return false;
    }

    return true;
  }

  render() {
    if (!this.ctx) return;
    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    ctx.save();
    ctx.translate(this.offsetX, this.offsetY);
    ctx.scale(this.scale, this.scale);

    // 1. Draw Links
    this.links.forEach(l => {
      if (!this.isNodeVisible(l.source) || !this.isNodeVisible(l.target)) return;

      ctx.beginPath();
      if (l.dashed) {
        ctx.setLineDash([4, 4]);
      } else {
        ctx.setLineDash([]);
      }
      ctx.moveTo(l.source.x, l.source.y);
      ctx.lineTo(l.target.x, l.target.y);
      ctx.strokeStyle = l.color || '#1a2232';
      ctx.lineWidth = l.width || 1;
      ctx.stroke();
      ctx.setLineDash([]);
    });

    // 2. Draw Nodes
    this.nodes.forEach(n => {
      if (!this.isNodeVisible(n)) return;

      ctx.beginPath();
      ctx.arc(n.x, n.y, n.radius, 0, Math.PI * 2);
      ctx.fillStyle = n.color;
      ctx.fill();
      ctx.lineWidth = n.isRoot ? 3 : 2;
      ctx.strokeStyle = n.strokeColor || '#ffffff';
      ctx.stroke();

      // Label text
      ctx.font = n.isRoot ? 'bold 13px Inter, sans-serif' : '11px Inter, sans-serif';
      ctx.fillStyle = '#f4f4f5';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      ctx.fillText(n.label, n.x, n.y + n.radius + 5);

      if (n.subLabel) {
        ctx.font = '9px JetBrains Mono, monospace';
        ctx.fillStyle = '#94a3b8';
        ctx.fillText(n.subLabel, n.x, n.y + n.radius + 18);
      }
    });

    ctx.restore();
  }

  initEvents() {
    this.canvas.addEventListener('mousedown', (e) => {
      const pos = this.getCanvasPos(e);
      const clicked = this.findNodeAt(pos.x, pos.y);

      if (clicked) {
        this.dragNode = clicked;
        if (clicked.profile_url && e.detail === 2) {
          window.open(clicked.profile_url, '_blank', 'noopener,noreferrer');
        }
      } else {
        this.isDragging = true;
        this.lastMouseX = e.clientX;
        this.lastMouseY = e.clientY;
      }
    });

    this.canvas.addEventListener('mousemove', (e) => {
      if (this.dragNode) {
        const pos = this.getCanvasPos(e);
        this.dragNode.x = pos.x;
        this.dragNode.y = pos.y;
        this.render();
      } else if (this.isDragging) {
        const dx = e.clientX - this.lastMouseX;
        const dy = e.clientY - this.lastMouseY;
        this.offsetX += dx;
        this.offsetY += dy;
        this.lastMouseX = e.clientX;
        this.lastMouseY = e.clientY;
        this.render();
      }
    });

    window.addEventListener('mouseup', () => {
      this.isDragging = false;
      this.dragNode = null;
    });

    this.canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
      this.scale = Math.min(Math.max(this.scale * zoomFactor, 0.25), 4.0);
      this.render();
    }, { passive: false });

    this.canvas.addEventListener('click', (e) => {
      const pos = this.getCanvasPos(e);
      const clicked = this.findNodeAt(pos.x, pos.y);
      if (clicked && clicked.profile_url) {
        window.open(clicked.profile_url, '_blank', 'noopener,noreferrer');
      }
    });
  }

  getCanvasPos(e) {
    const rect = this.canvas.getBoundingClientRect();
    const clientX = e.clientX - rect.left;
    const clientY = e.clientY - rect.top;
    return {
      x: (clientX - this.offsetX) / this.scale,
      y: (clientY - this.offsetY) / this.scale
    };
  }

  findNodeAt(x, y) {
    for (let i = this.nodes.length - 1; i >= 0; i--) {
      const n = this.nodes[i];
      if (!this.isNodeVisible(n)) continue;
      const dx = n.x - x;
      const dy = n.y - y;
      if (Math.sqrt(dx * dx + dy * dy) <= n.radius + 6) {
        return n;
      }
    }
    return null;
  }
}