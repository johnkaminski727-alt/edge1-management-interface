(() => {
  'use strict';

  const sections = [
    ['Command', [
      ['Operations Overview', '/admin/bigbird-overview.php'],
      ['Decision Centre', '#decisions'],
      ['Change Control', '/admin/bigbird-changes-audit.php']
    ]],
    ['Observe', [
      ['Service Health', '/admin/bigbird-operations-console.php'],
      ['Logs & Events', '/admin/bigbird-logs.php'],
      ['VPN & Devices', '/admin/bigbird-vpn-devices.php'],
      ['Electrum Watch Console', '#electrum'],
      ['Carrier Operations', '#carriers']
    ]],
    ['Analyze', [
      ['Analytics Workspace', '#analytics'],
      ['Security Analysis', '/admin/bigbird-security.php'],
      ['DNS Analysis', '/admin/bigbird-dns-queries.php'],
      ['Telephony Analysis', '/admin/telephony-analytics.php'],
      ['Carrier Analysis', '#carrier-analysis'],
      ['Production Analysis', '/admin/print-production.php']
    ]],
    ['Control', [
      ['Firewall Control', '/admin/bigbird-firewall.php'],
      ['DNS Control', '/admin/bigbird-dns-cache.php'],
      ['Service Control', '/admin/bigbird-operations-console.php#controls'],
      ['Carrier Requests', '#carrier-workflows'],
      ['Carrier Review Queue', '#carrier-review'],
      ['Automation', '/admin/bigbird-automation.php']
    ]],
    ['Govern', [
      ['Audit & Evidence', '/admin/bigbird-changes-audit.php'],
      ['Configuration', '/admin/bigbird-settings.php'],
      ['WW.CX AI', '/admin/bigbird-ai-chat.php']
    ]]
  ];

  const navigation = document.getElementById('navigation');
  if (!navigation) return;

  for (const [label, links] of sections) {
    const heading = document.createElement('h3');
    heading.textContent = label;
    navigation.appendChild(heading);

    for (const [text, href] of links) {
      const link = document.createElement('a');
      link.href = href;
      link.textContent = text;
      if (text === 'Operations Overview') link.className = 'active';
      navigation.appendChild(link);
    }
  }
})();
