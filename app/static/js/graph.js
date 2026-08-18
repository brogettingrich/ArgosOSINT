class IntelligenceGraph {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.nodes = [];
    this.links = [];
    this.animationFrame = null;
    this.resize();
    window.addEventListener('resize', () => this.resize());
  }

  resize() {
    if (!this.canvas) return;
    const rect = this.canvas.parentElement.getBoundingClientRect();
    this.canvas.width = rect.width * window.devicePixelRatio;
    this.canvas.height = rect.height * window.devicePixelRatio;
    this.ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    this.width = rect.width;
    this.height = rect.height;
  }

  clear() {
    this.nodes = [];
    this.links = [];
    if (this.animationFrame) cancelAnimationFrame(this.animationFrame);
  }

  buildFromScan(seedTarget, findings, emailInfo, phoneInfo) {
    this.clear();
    const cx = this.width / 2 || 300;
    const cy = this.height / 2 || 250;

    // Root Target Node
    const rootNode = {
      id: 'root',
      label: seedTarget,
      type: 'root',
      x: cx,
      y: cy,
      vx: 0,
      vy: 0,
      radius: 18,
      color: '#ffffff'
    };
    this.nodes.push(rootNode);

    // Email Node if present
    if (emailInfo && emailInfo.valid_syntax) {
      const emailNode = {
        id: 'email',
        label: emailInfo.email,
        type: 'email',
        x: cx - 120,
        y: cy - 90,
        vx: 0,
        vy: 0,
        radius: 12,
        color: '#4facfe'
      };
      this.nodes.push(emailNode);
      this.links.push({ source: rootNode, target: emailNode });
    }

    // Phone Node if present
    if (phoneInfo && phoneInfo.valid) {
      const phoneNode = {
        id: 'phone',
        label: phoneInfo.country ? `${phoneInfo.e164} (${phoneInfo.iso})` : phoneInfo.e164,
        type: 'phone',
        x: cx + 120,
        y: cy - 90,
        vx: 0,
        vy: 0,
        radius: 12,
        color: '#f6d365'
      };
      this.nodes.push(phoneNode);
      this.links.push({ source: rootNode, target: phoneNode });
    }

    // Discovered Profile Findings Nodes
    const angleStep = (Math.PI * 2) / Math.max(findings.length, 1);
    findings.forEach((item, index) => {
      const angle = index * angleStep;
      const dist = 140 + (index % 3) * 30;
      const node = {
        id: `finding_${index}`,
        label: `${item.site} (@${item.username})`,
        type: 'finding',
        url: item.profile_url,
        x: cx + Math.cos(angle) * dist,
        y: cy + Math.sin(angle) * dist,
        vx: 0,
        vy: 0,
        radius: 10,
        color: '#38ef7d'
      };
      this.nodes.push(node);
      this.links.push({ source: rootNode, target: node });
    });

    this.startSimulation();
  }

  startSimulation() {
    const tick = () => {
      this.updatePhysics();
      this.render();
      this.animationFrame = requestAnimationFrame(tick);
    };
    this.animationFrame = requestAnimationFrame(tick);
  }

  updatePhysics() {
    // Gentle spring & repulsion simulation
    for (let i = 0; i < this.nodes.length; i++) {
      for (let j = i + 1; j < this.nodes.length; j++) {
        const n1 = this.nodes[i];
        const n2 = this.nodes[j];
        const dx = n2.x - n1.x;
        const dy = n2.y - n1.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        if (dist < 100) {
          const force = (100 - dist) / 100 * 0.5;
          n1.x -= (dx / dist) * force;
          n1.y -= (dy / dist) * force;
          n2.x += (dx / dist) * force;
          n2.y += (dy / dist) * force;
        }
      }
    }
  }

  render() {
    this.ctx.clearRect(0, 0, this.width, this.height);

    // Draw Links
    this.ctx.lineWidth = 1;
    this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.12)';
    for (const link of this.links) {
      this.ctx.beginPath();
      this.ctx.moveTo(link.source.x, link.source.y);
      this.ctx.lineTo(link.target.x, link.target.y);
      this.ctx.stroke();
    }

    // Draw Nodes
    for (const node of this.nodes) {
      this.ctx.beginPath();
      this.ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
      this.ctx.fillStyle = node.color;
      this.ctx.fill();

      // Node Label
      this.ctx.font = '11px JetBrains Mono, monospace';
      this.ctx.fillStyle = '#b0b0b0';
      this.ctx.textAlign = 'center';
      this.ctx.fillText(node.label, node.x, node.y + node.radius + 14);
    }
  }
}