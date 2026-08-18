const Exporter = {
  exportJSON(targetName, findings, emailInfo, phoneInfo) {
    const report = {
      platform: "ArgosOSINT",
      generated_at: new Date().toISOString(),
      target: targetName,
      email_intelligence: emailInfo,
      phone_intelligence: phoneInfo,
      total_findings: findings.length,
      findings: findings
    };
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `Argos_Dossier_${targetName.replace(/[^a-zA-Z0-9]/g, '_')}.json`;
    a.click();
    URL.revokeObjectURL(url);
  },

  exportHTML(targetName, findings) {
    const rows = findings.map(f => `
      <tr>
        <td style="padding:10px;border-bottom:1px solid #222;"><strong>${f.site}</strong></td>
        <td style="padding:10px;border-bottom:1px solid #222;">${f.category}</td>
        <td style="padding:10px;border-bottom:1px solid #222;"><code>${f.username}</code></td>
        <td style="padding:10px;border-bottom:1px solid #222;"><a href="${f.profile_url}" target="_blank" style="color:#38ef7d;">${f.profile_url}</a></td>
      </tr>
    `).join('');

    const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>ArgosOSINT Dossier: ${targetName}</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #000; color: #fff; padding: 30px; }
    h1 { font-size: 20px; border-bottom: 1px solid #333; padding-bottom: 10px; }
    table { width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 13px; }
    th { text-align: left; padding: 10px; background: #111; color: #888; border-bottom: 1px solid #333; }
  </style>
</head>
<body>
  <h1>ArgosOSINT Target Dossier: ${targetName}</h1>
  <p style="color:#888;font-size:12px;">Generated at: ${new Date().toUTCString()} | Total Discovered Accounts: ${findings.length}</p>
  <table>
    <thead><tr><th>Platform</th><th>Category</th><th>Handle</th><th>Direct Link</th></tr></thead>
    <tbody>${rows}</tbody>
  </table>
</body>
</html>`;

    const blob = new Blob([html], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `Argos_Dossier_${targetName.replace(/[^a-zA-Z0-9]/g, '_')}.html`;
    a.click();
    URL.revokeObjectURL(url);
  }
};