class IntelligenceGraph {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.nodes = [];
    this.links = [];
    this.allNodes = [];
    this.allLinks = [];
    this.animationFrame = null;
    this.isFrozen = false;
    this.simTicks = 0;

    // Active Filters
    this.activeCategory = 'all';
    this.activePlatform = 'all';
    this.searchQuery = '';

    // Viewport Transform (Pan & Zoom)
    this.scale = 1.0;
    this.panX = 0;
    this.panY = 0;
    this.isDragging = false;
    this.dragNode = null;
    this.dragStartX = 0;
    this.dragStartY = 0;
    this.hoverNode = null;

    this.setupInteractions();
    this.resize();
    window.addEventListener('resize', () => this.resize());
  }

  resize() {
    if (!this.canvas) return;
    const parent = this.canvas.parentElement;
    if (!parent) return;
    const rect = parent.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return;

    this.width = rect.width;
    this.height = rect.height;
    this.canvas.width = rect.width * window.devicePixelRatio;
    this.canvas.height = rect.height * window.devicePixelRatio;
    this.canvas.style.width = `${rect.width}px`;
    this.canvas.style.height = `${rect.height}px`;
    this.ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    this.render();
  }

  setupInteractions() {
    // Wheel Zoom centered on cursor
    this.canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      const rect = this.canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      const zoomFactor = e.deltaY < 0 ? 1.15 : 0.87;
      const newScale = Math.min(Math.max(this.scale * zoomFactor, 0.2), 5.0);

      this.panX = mouseX - (mouseX - this.panX) * (newScale / this.scale);
      this.panY = mouseY - (mouseY - this.panY) * (newScale / this.scale);
      this.scale = newScale;
      this.render();
    });

    // Mouse Down (Node Drag or Pan)
    this.canvas.addEventListener('mousedown', (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;
      const worldPos = this.screenToWorld(mouseX, mouseY);

      // Check visible nodes
      for (const node of this.nodes) {
        const dx = worldPos.x - node.x;
        const dy = worldPos.y - node.y;
        if (Math.sqrt(dx * dx + dy * dy) <= node.radius + 6) {
          this.dragNode = node;
          this.dragStartX = worldPos.x - node.x;
          this.dragStartY = worldPos.y - node.y;
          return;
        }
      }

      this.isDragging = true;
      this.dragStartX = mouseX - this.panX;
      this.dragStartY = mouseY - this.panY;
    });

    // Mouse Move (Pan, Drag, Hover)
    this.canvas.addEventListener('mousemove', (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      if (this.dragNode) {
        const worldPos = this.screenToWorld(mouseX, mouseY);
        this.dragNode.x = worldPos.x - this.dragStartX;
        this.dragNode.y = worldPos.y - this.dragStartY;
        this.render();
        return;
      }

      if (this.isDragging) {
        this.panX = mouseX - this.dragStartX;
        this.panY = mouseY - this.dragStartY;
        this.render();
        return;
      }

      const worldPos = this.screenToWorld(mouseX, mouseY);
      let foundHover = null;
      for (const node of this.nodes) {
        const dx = worldPos.x - node.x;
        const dy = worldPos.y - node.y;
        if (Math.sqrt(dx * dx + dy * dy) <= node.radius + 6) {
          foundHover = node;
          break;
        }
      }

      if (this.hoverNode !== foundHover) {
        this.hoverNode = foundHover;
        this.canvas.style.cursor = foundHover ? 'pointer' : 'grab';
        this.render();
      }
    });

    // Mouse Up
    window.addEventListener('mouseup', () => {
      this.isDragging = false;
      this.dragNode = null;
    });

    // Click to Open Profile
    this.canvas.addEventListener('click', (e) => {
      if (this.hoverNode && this.hoverNode.url) {
        window.open(this.hoverNode.url, '_blank', 'noopener,noreferrer');
      }
    });
  }

  screenToWorld(sx, sy) {
    return {
      x: (sx - this.panX) / this.scale,
      y: (sy - this.panY) / this.scale
    };
  }

  recenter() {
    this.panX = (this.width / 2) || 400;
    this.panY = (this.height / 2) || 300;
    this.scale = 0.85;
    this.render();
  }

  setCategoryFilter(cat) {
    this.activeCategory = cat;
    this.activePlatform = 'all';
    this.applyFilters();
  }

  setPlatformFilter(platform) {
    this.activePlatform = platform;
    this.applyFilters();
  }

  setSearchQuery(q) {
    this.searchQuery = (q || '').trim().toLowerCase();
    this.applyFilters();
  }

  toggleFreeze() {
    this.isFrozen = !this.isFrozen;
    const btn = document.getElementById('btn-graph-freeze');
    if (btn) btn.innerText = this.isFrozen ? 'Unfreeze' : 'Freeze';
    if (!this.isFrozen) this.startSimulation();
  }

  applyFilters() {
    if (!this.allNodes || this.allNodes.length === 0) return;

    this.nodes = this.allNodes.filter(n => {
      if (n.type === 'root') return true;
      if (this.activeCategory === 'exact' && !n.is_seed) return false;
      if (this.activeCategory !== 'all' && this.activeCategory !== 'exact' && n.category !== this.activeCategory) return false;
      if (this.activePlatform !== 'all' && n.label !== this.activePlatform) return false;
      if (this.searchQuery) {
        const text = `${n.label} ${n.sublabel} ${n.category || ''}`.toLowerCase();
        if (!text.includes(this.searchQuery)) return false;
      }
      return true;
    });

    const visibleNodeIds = new Set(this.nodes.map(n => n.id));
    this.links = this.allLinks.filter(l => visibleNodeIds.has(l.source.id) && visibleNodeIds.has(l.target.id));

    this.render();
  }

  buildFromScan(seedTarget, findings, emailInfo, phoneInfo) {
    if (this.animationFrame) cancelAnimationFrame(this.animationFrame);
    this.resize();

    this.allNodes = [];
    this.allLinks = [];

    // Center coordinates
    const cx = 0;
    const cy = 0;

    // Root Target Node
    const rootNode = {
      id: 'root',
      label: seedTarget || 'Target Seed',
      sublabel: 'Central Pivot',
      type: 'root',
      x: cx,
      y: cy,
      radius: 24,
      color: '#f8fafc',
      is_seed: true
    };
    this.allNodes.push(rootNode);

    // Email Node (Ring 1)
    if (emailInfo && emailInfo.valid_syntax) {
      const emailNode = {
        id: 'email',
        label: emailInfo.email,
        sublabel: 'Email Identity',
        type: 'email',
        category: 'Entity',
        x: cx - 180,
        y: cy - 120,
        radius: 16,
        color: '#06b6d4',
        is_seed: true
      };
      this.allNodes.push(emailNode);
      this.allLinks.push({ source: rootNode, target: emailNode });
    }

    // Phone Node (Ring 1)
    if (phoneInfo && phoneInfo.valid) {
      const phoneNode = {
        id: 'phone',
        label: phoneInfo.country ? `${phoneInfo.e164} (${phoneInfo.iso})` : phoneInfo.e164,
        sublabel: phoneInfo.country || 'Phone Identity',
        type: 'phone',
        category: 'Entity',
        x: cx + 180,
        y: cy - 120,
        radius: 16,
        color: '#f59e0b',
        is_seed: true
      };
      this.allNodes.push(phoneNode);
      this.allLinks.push({ source: rootNode, target: phoneNode });
    }

    // Platform findings with wide Category Sector Distribution
    const catColors = {
      'Social': '#10b981',
      'Developer': '#06b6d4',
      'Gaming': '#a855f7',
      'Media': '#ec4899',
      'Crypto': '#eab308',
      'General': '#10b981'
    };

    // Category Angular Sectors (Radially separated so categories never collide)
    const categorySectors = {
      'Social': { start: -Math.PI / 4, end: Math.PI / 4 },         // Right quadrant
      'Developer': { start: Math.PI * 0.8, end: Math.PI * 1.25 },   // Left quadrant
      'Gaming': { start: Math.PI * 0.35, end: Math.PI * 0.75 },     // Bottom-right
      'Media': { start: -Math.PI * 0.75, end: -Math.PI * 0.35 },    // Top quadrant
      'Crypto': { start: Math.PI * 1.3, end: Math.PI * 1.6 }
    };

    const categoryGroups = {};
    findings.forEach(f => {
      const cat = f.category || 'Social';
      if (!categoryGroups[cat]) categoryGroups[cat] = [];
      categoryGroups[cat].push(f);
    });

    let nodeIndex = 0;
    Object.keys(categoryGroups).forEach(cat => {
      const group = categoryGroups[cat];
      const sector = categorySectors[cat] || { start: 0, end: Math.PI * 2 };
      const angleSpan = sector.end - sector.start;
      const angleStep = group.length > 1 ? angleSpan / group.length : 0;

      group.forEach((item, i) => {
        const angle = sector.start + (i * angleStep) + (angleStep / 2);
        const ringDist = item.is_seed ? 260 : 420 + ((i % 3) * 75);
        const col = catColors[cat] || '#10b981';

        const node = {
          id: `finding_${nodeIndex++}`,
          label: item.site,
          sublabel: `@${item.username}`,
          category: cat,
          url: item.profile_url,
          is_seed: item.is_seed,
          meta: item.metadata || {},
          corrob: item.corroboration || {},
          type: 'finding',
          x: cx + Math.cos(angle) * ringDist,
          y: cy + Math.sin(angle) * ringDist,
          radius: item.is_seed ? 15 : 12,
          color: col
        };

        this.allNodes.push(node);
        this.allLinks.push({ source: rootNode, target: node });
      });
    });

    this.recenter();
    this.applyFilters();
    this.startSimulation();
  }

  startSimulation() {
    this.simTicks = 0;
    this.isFrozen = false;

    const tick = () => {
      if (this.isFrozen) return;

      this.updatePhysics();
      this.render();
      this.simTicks++;

      // Automatically freeze and stop animation after 45 frames (Zero drift / jitter)
      if (this.simTicks > 45) {
        this.isFrozen = true;
        const btn = document.getElementById('btn-graph-freeze');
        if (btn) btn.innerText = 'Unfreeze';
        return;
      }

      this.animationFrame = requestAnimationFrame(tick);
    };

    if (this.animationFrame) cancelAnimationFrame(this.animationFrame);
    this.animationFrame = requestAnimationFrame(tick);
  }

  updatePhysics() {
    const alpha = Math.max(0.01, 1 - (this.simTicks / 45));

    for (let i = 0; i < this.nodes.length; i++) {
      for (let j = i + 1; j < this.nodes.length; j++) {
        const n1 = this.nodes[i];
        const n2 = this.nodes[j];
        if (n1 === this.dragNode || n2 === this.dragNode) continue;
        if (n1.type === 'root') continue;

        const dx = n2.x - n1.x;
        const dy = n2.y - n1.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const targetDist = 95;

        if (dist < targetDist) {
          const force = ((targetDist - dist) / targetDist) * 0.4 * alpha;
          n1.x -= (dx / dist) * force;
          n1.y -= (dy / dist) * force;
          n2.x += (dx / dist) * force;
          n2.y += (dy / dist) * force;
        }
      }
    }
  }

  render() {
    if (!this.ctx || !this.width || !this.height) return;

    this.ctx.save();
    this.ctx.clearRect(0, 0, this.width, this.height);

    // Apply Pan & Zoom Viewport Transform
    this.ctx.translate(this.panX, this.panY);
    this.ctx.scale(this.scale, this.scale);

    // 1. Draw Links
    for (const link of this.links) {
      const isHighlighted = this.hoverNode && (this.hoverNode === link.source || this.hoverNode === link.target);
      this.ctx.beginPath();
      this.ctx.moveTo(link.source.x, link.source.y);
      this.ctx.lineTo(link.target.x, link.target.y);
      this.ctx.lineWidth = isHighlighted ? 2.0 : 1.0;
      this.ctx.strokeStyle = isHighlighted ? 'rgba(16, 185, 129, 0.7)' : 'rgba(255, 255, 255, 0.07)';
      this.ctx.stroke();
    }

    // 2. Draw Nodes
    for (const node of this.nodes) {
      const isHover = (node === this.hoverNode);

      // Glow Halo
      this.ctx.beginPath();
      this.ctx.arc(node.x, node.y, node.radius + (isHover ? 8 : 2), 0, Math.PI * 2);
      this.ctx.fillStyle = isHover ? 'rgba(255, 255, 255, 0.25)' : 'rgba(0, 0, 0, 0.6)';
      this.ctx.fill();

      // Node Circle
      this.ctx.beginPath();
      this.ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
      this.ctx.fillStyle = node.color;
      this.ctx.fill();

      // Border
      this.ctx.lineWidth = 1.5;
      this.ctx.strokeStyle = '#05070a';
      this.ctx.stroke();

      // Node Labels
      if (this.scale > 0.5 || isHover || node.type === 'root') {
        this.ctx.font = '600 11px Inter, sans-serif';
        this.ctx.fillStyle = '#f8fafc';
        this.ctx.textAlign = 'center';
        this.ctx.fillText(node.label, node.x, node.y + node.radius + 13);

        if (this.scale > 0.8 || isHover) {
          this.ctx.font = '10px JetBrains Mono, monospace';
          this.ctx.fillStyle = '#94a3b8';
          this.ctx.fillText(node.sublabel, node.x, node.y + node.radius + 24);
        }
      }
    }

    // 3. Floating HUD Tooltip when Hovering a Node
    if (this.hoverNode) {
      const hn = this.hoverNode;
      const hudW = 220;
      const hudH = hn.type === 'finding' ? 76 : 50;
      const hx = hn.x - hudW / 2;
      const hy = hn.y - hn.radius - hudH - 12;

      this.ctx.fillStyle = 'rgba(10, 14, 22, 0.96)';
      this.ctx.strokeStyle = '#2a364e';
      this.ctx.lineWidth = 1;
      this.ctx.beginPath();
      this.ctx.roundRect(hx, hy, hudW, hudH, 8);
      this.ctx.fill();
      this.ctx.stroke();

      this.ctx.textAlign = 'left';
      this.ctx.fillStyle = '#f8fafc';
      this.ctx.font = '600 12px Inter, sans-serif';
      this.ctx.fillText(hn.label, hx + 12, hy + 18);

      this.ctx.fillStyle = '#94a3b8';
      this.ctx.font = '10px JetBrains Mono, monospace';
      this.ctx.fillText(hn.sublabel, hx + 12, hy + 34);

      if (hn.type === 'finding') {
        const score = hn.corrob.score ? `${hn.corrob.score}% Match` : 'Verified';
        this.ctx.fillStyle = '#10b981';
        this.ctx.fillText(`${hn.category} • ${score} [Click to Open ↗]`, hx + 12, hy + 54);
      }
    }

    this.ctx.restore();
  }
}