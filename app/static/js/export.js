const Exporter = {
  exportJSON: (targetName, findings, emailInfo, phoneInfo, briefingData) => {
    const payload = {
      target: targetName,
      exported_at: new Date().toISOString(),
      executive_briefing: briefingData || null,
      identity_probes: {
        email: emailInfo,
        phone: phoneInfo
      },
      discovered_accounts_count: findings.length,
      accounts: findings
    };

    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `argos_dossier_${targetName.replace(/[^a-zA-Z0-9]/g, '_')}.json`;
    a.click();
    URL.revokeObjectURL(url);
  },

  exportHTML: (targetName, findings, briefingData) => {
    const briefingHtml = briefingData ? `
      <div style="background:#161b22;border:1px solid #30363d;padding:16px;border-radius:8px;margin-bottom:20px;">
        <h3 style="margin-top:0;color:#58a6ff;font-size:14px;">AI EXECUTIVE INTELLIGENCE BRIEFING (${briefingData.confidence || 0}% CONFIDENCE)</h3>
        <p style="color:#c9d1d9;font-size:13px;line-height:1.5;">${briefingData.briefing || ''}</p>
        ${briefingData.rationale ? `<p style="color:#8b949e;font-size:11px;font-style:italic;">Rationale: ${briefingData.rationale}</p>` : ''}
      </div>
    ` : '';

    const rows = findings.map(f => `
      <tr>
        <td><strong>${f.site}</strong></td>
        <td>@${f.username}</td>
        <td>${f.category}</td>
        <td><a href="${f.profile_url}" target="_blank" style="color:#58a6ff;">${f.profile_url}</a></td>
        <td>${f.corroboration ? f.corroboration.score : 50}%</td>
      </tr>
    `).join('');

    const htmlContent = `
      <!DOCTYPE html>
      <html>
      <head>
        <title>ArgosOSINT Dossier - ${targetName}</title>
        <style>
          body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0d1117; color: #c9d1d9; padding: 30px; }
          h1 { color: #58a6ff; }
          table { width: 100%; border-collapse: collapse; margin-top: 20px; }
          th, td { border: 1px solid #30363d; padding: 10px; text-align: left; }
          th { background: #161b22; }
          tr:nth-child(even) { background: #161b22; }
        </style>
      </head>
      <body>
        <h1>ArgosOSINT Intelligence Report: ${targetName}</h1>
        <p>Generated: ${new Date().toUTCString()} | Total Profiles Discovered: ${findings.length}</p>
        ${briefingHtml}
        <table>
          <thead>
            <tr><th>Platform</th><th>Handle</th><th>Category</th><th>Profile URL</th><th>Match Score</th></tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </body>
      </html>
    `;

    const blob = new Blob([htmlContent], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `argos_report_${targetName.replace(/[^a-zA-Z0-9]/g, '_')}.html`;
    a.click();
    URL.revokeObjectURL(url);
  }
};