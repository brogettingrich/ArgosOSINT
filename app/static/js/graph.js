class IntelligenceGraph {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.nodes = [];
    this.links = [];
    this.animationFrame = null;

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
    const rect = this.canvas.parentElement.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return;
    
    this.width = rect.width;
    this.height = rect.height;
    this.canvas.width = rect.width * window.devicePixelRatio;
    this.canvas.height = rect.height * window.devicePixelRatio;
    this.canvas.style.width = `${rect.width}px`;
    this.canvas.style.height = `${rect.height}px`;
    this.ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
  }

  setupInteractions() {
    // Wheel Zoom (Zoom in/out with mouse focus)
    this.canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      const rect = this.canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      const zoomFactor = e.deltaY < 0 ? 1.15 : 0.87;
      const newScale = Math.min(Math.max(this.scale * zoomFactor, 0.25), 4.5);

      // Adjust pan to zoom towards mouse cursor
      this.panX = mouseX - (mouseX - this.panX) * (newScale / this.scale);
      this.panY = mouseY - (mouseY - this.panY) * (newScale / this.scale);
      this.scale = newScale;
    });

    // Mouse Down (Node Drag or Canvas Pan)
    this.canvas.addEventListener('mousedown', (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;
      const worldPos = this.screenToWorld(mouseX, mouseY);

      // Check if clicking a node
      for (const node of this.nodes) {
        const dx = worldPos.x - node.x;
        const dy = worldPos.y - node.y;
        if (Math.sqrt(dx * dx + dy * dy) <= node.radius + 4) {
          this.dragNode = node;
          this.dragStartX = worldPos.x - node.x;
          this.dragStartY = worldPos.y - node.y;
          return;
        }
      }

      // Otherwise Pan Canvas
      this.isDragging = true;
      this.dragStartX = mouseX - this.panX;
      this.dragStartY = mouseY - this.panY;
    });

    // Mouse Move (Pan, Drag Node, Hover HUD)
    this.canvas.addEventListener('mousemove', (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      if (this.dragNode) {
        const worldPos = this.screenToWorld(mouseX, mouseY);
        this.dragNode.x = worldPos.x - this.dragStartX;
        this.dragNode.y = worldPos.y - this.dragStartY;
        this.dragNode.vx = 0;
        this.dragNode.vy = 0;
        return;
      }

      if (this.isDragging) {
        this.panX = mouseX - this.dragStartX;
        this.panY = mouseY - this.dragStartY;
        return;
      }

      // Check Hovered Node
      const worldPos = this.screenToWorld(mouseX, mouseY);
      let foundHover = null;
      for (const node of this.nodes) {
        const dx = worldPos.x - node.x;
        const dy = worldPos.y - node.y;
        if (Math.sqrt(dx * dx + dy * dy) <= node.radius + 4) {
          foundHover = node;
          break;
        }
      }
      this.hoverNode = foundHover;
      this.canvas.style.cursor = foundHover ? 'pointer' : 'grab';
    });

    // Mouse Up
    window.addEventListener('mouseup', () => {
      this.isDragging = false;
      this.dragNode = null;
      if (this.canvas) this.canvas.style.cursor = this.hoverNode ? 'pointer' : 'default';
    });

    // Click to open profile
    this.canvas.addEventListener('click', (e) => {
      if (this.hoverNode && this.hoverNode.url) {
        window.open(this.hoverNode.url, '_blank', 'noopener');
      }
    });
  }

  screenToWorld(sx, sy) {
    return {
      x: (sx - this.panX) / this.scale,
      y: (sy - this.panY) / this.scale
    };
  }

  clear() {
    this.nodes = [];
    this.links = [];
    if (this.animationFrame) cancelAnimationFrame(this.animationFrame);
  }

  buildFromScan(seedTarget, findings, emailInfo, phoneInfo) {
    this.clear();
    this.resize();

    const cx = this.width / 2 || 400;
    const cy = this.height / 2 || 300;
    this.panX = 0;
    this.panY = 0;
    this.scale = 1.0;

    // Root Target Node
    const rootNode = {
      id: 'root',
      label: seedTarget,
      sublabel: 'Target Seed',
      type: 'root',
      x: cx,
      y: cy,
      vx: 0,
      vy: 0,
      radius: 20,
      color: '#f8fafc',
      glow: 'rgba(255, 255, 255, 0.3)'
    };
    this.nodes.push(rootNode);

    // Email Node
    if (emailInfo && emailInfo.valid_syntax) {
      const emailNode = {
        id: 'email',
        label: emailInfo.email,
        sublabel: 'Email Entity',
        type: 'email',
        x: cx - 140,
        y: cy - 100,
        vx: 0,
        vy: 0,
        radius: 14,
        color: '#06b6d4',
        glow: 'rgba(6, 182, 212, 0.3)'
      };
      this.nodes.push(emailNode);
      this.links.push({ source: rootNode, target: emailNode });
    }

    // Phone Node
    if (phoneInfo && phoneInfo.valid) {
      const phoneNode = {
        id: 'phone',
        label: phoneInfo.country ? `${phoneInfo.e164} (${phoneInfo.iso})` : phoneInfo.e164,
        sublabel: phoneInfo.country || 'Phone Entity',
        type: 'phone',
        x: cx + 140,
        y: cy - 100,
        vx: 0,
        vy: 0,
        radius: 14,
        color: '#f59e0b',
        glow: 'rgba(245, 158, 11, 0.3)'
      };
      this.nodes.push(phoneNode);
      this.links.push({ source: rootNode, target: phoneNode });
    }

    // Profile Findings Nodes
    const catColors = {
      'Social': '#10b981',
      'Developer': '#06b6d4',
      'Gaming': '#a855f7',
      'Media': '#ec4899',
      'Crypto': '#eab308',
      'General': '#10b981'
    };

    const angleStep = (Math.PI * 2) / Math.max(findings.length, 1);
    findings.forEach((item, index) => {
      const angle = index * angleStep;
      const dist = 160 + (index % 3) * 45;
      const col = catColors[item.category] || '#10b981';

      const node = {
        id: `finding_${index}`,
        label: item.site,
        sublabel: `@${item.username}`,
        category: item.category,
        url: item.profile_url,
        meta: item.metadata || {},
        corrob: item.corroboration || {},
        type: 'finding',
        x: cx + Math.cos(angle) * dist,
        y: cy + Math.sin(angle) * dist,
        vx: 0,
        vy: 0,
        radius: 12,
        color: col,
        glow: col
      };
      this.nodes.push(node);
      this.links.push({ source: rootNode, target: node });
    });

    this.startSimulation();
  }

  startSimulation() {
    let ticks = 0;
    const tick = () => {
      this.updatePhysics();
      this.render();
      ticks++;
      this.animationFrame = requestAnimationFrame(tick);
    };
    this.animationFrame = requestAnimationFrame(tick);
  }

  updatePhysics() {
    for (let i = 0; i < this.nodes.length; i++) {
      for (let j = i + 1; j < this.nodes.length; j++) {
        const n1 = this.nodes[i];
        const n2 = this.nodes[j];
        if (n1 === this.dragNode || n2 === this.dragNode) continue;

        const dx = n2.x - n1.x;
        const dy = n2.y - n1.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const targetDist = 110;
        if (dist < targetDist) {
          const force = (targetDist - dist) / targetDist * 0.3;
          n1.x -= (dx / dist) * force;
          n1.y -= (dy / dist) * force;
          n2.x += (dx / dist) * force;
          n2.y += (dy / dist) * force;
        }
      }
    }
  }

  render() {
    this.ctx.save();
    this.ctx.clearRect(0, 0, this.width, this.height);

    // Apply Viewport Transform
    this.ctx.translate(this.panX, this.panY);
    this.ctx.scale(this.scale, this.scale);

    // 1. Draw Links
    this.ctx.lineWidth = 1.2;
    for (const link of this.links) {
      const isHighlighted = this.hoverNode && (this.hoverNode === link.source || this.hoverNode === link.target);
      this.ctx.beginPath();
      this.ctx.moveTo(link.source.x, link.source.y);
      this.ctx.lineTo(link.target.x, link.target.y);
      this.ctx.strokeStyle = isHighlighted ? 'rgba(16, 185, 129, 0.6)' : 'rgba(255, 255, 255, 0.08)';
      this.ctx.stroke();
    }

    // 2. Draw Nodes
    for (const node of this.nodes) {
      const isHover = (node === this.hoverNode);

      // Node Glow
      this.ctx.beginPath();
      this.ctx.arc(node.x, node.y, node.radius + (isHover ? 6 : 2), 0, Math.PI * 2);
      this.ctx.fillStyle = isHover ? 'rgba(255, 255, 255, 0.2)' : 'rgba(0, 0, 0, 0.5)';
      this.ctx.fill();

      // Node Body
      this.ctx.beginPath();
      this.ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
      this.ctx.fillStyle = node.color;
      this.ctx.fill();

      // Node Border
      this.ctx.lineWidth = 1.5;
      this.ctx.strokeStyle = '#080a0f';
      this.ctx.stroke();

      // Level-of-Detail Labels
      if (this.scale > 0.55 || isHover || node.type === 'root') {
        this.ctx.font = '600 11px Inter, sans-serif';
        this.ctx.fillStyle = '#f8fafc';
        this.ctx.textAlign = 'center';
        this.ctx.fillText(node.label, node.x, node.y + node.radius + 13);

        if (this.scale > 0.85 || isHover) {
          this.ctx.font = '10px JetBrains Mono, monospace';
          this.ctx.fillStyle = '#94a3b8';
          this.ctx.fillText(node.sublabel, node.x, node.y + node.radius + 25);
        }
      }
    }

    // 3. Floating HUD Tooltip when Hovering a node
    if (this.hoverNode) {
      const hn = this.hoverNode;
      const hudW = 200;
      const hudH = hn.type === 'finding' ? 70 : 45;
      const hx = hn.x - hudW / 2;
      const hy = hn.y - hn.radius - hudH - 12;

      this.ctx.fillStyle = 'rgba(14, 18, 26, 0.95)';
      this.ctx.strokeStyle = '#2a364e';
      this.ctx.lineWidth = 1;
      this.ctx.beginPath();
      this.ctx.roundRect(hx, hy, hudW, hudH, 8);
      this.ctx.fill();
      this.ctx.stroke();

      this.ctx.textAlign = 'left';
      this.ctx.fillStyle = '#f8fafc';
      this.ctx.font = '600 11px Inter, sans-serif';
      this.ctx.fillText(hn.label, hx + 10, hy + 18);

      this.ctx.fillStyle = '#94a3b8';
      this.ctx.font = '10px JetBrains Mono, monospace';
      this.ctx.fillText(hn.sublabel, hx + 10, hy + 32);

      if (hn.type === 'finding') {
        const score = hn.corrob.score ? `${hn.corrob.score}% Match` : 'Verified';
        this.ctx.fillStyle = '#10b981';
        this.ctx.fillText(`${hn.category} • ${score} [Click to Open]`, hx + 10, hy + 50);
      }
    }

    this.ctx.restore();
  }
}