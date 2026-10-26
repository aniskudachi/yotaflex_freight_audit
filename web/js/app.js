// Freight Invoice Validation & Audit Interactive Application
document.addEventListener('DOMContentLoaded', () => {
  // State
  let currentInvoices = [];
  let currentSummary = null;
  let selectedInvoiceId = null;
  let activeTab = 'tab-workbench';
  let activeRole = 'Logistics Analyst';

  // Elements
  const navTabs = document.querySelectorAll('.nav-tab');
  const tabContents = document.querySelectorAll('.tab-content');
  const roleSelect = document.getElementById('role-select');
  const invoicesTableBody = document.getElementById('invoices-table-body');
  const filterDecision = document.getElementById('filter-decision');
  const filterCarrier = document.getElementById('filter-carrier');
  const filterIssue = document.getElementById('filter-issue');
  const searchInput = document.getElementById('search-input');
  const btnRunAudit = document.getElementById('btn-run-audit');
  const btnRegenStarter = document.getElementById('btn-regen-starter');
  const btnRegenFull = document.getElementById('btn-regen-full');
  
  // Drawer Elements
  const drawerOverlay = document.getElementById('drawer-overlay');
  const btnCloseDrawer = document.getElementById('btn-close-drawer');
  const drawerInvoiceId = document.getElementById('drawer-invoice-id');
  const drawerStatusBadge = document.getElementById('drawer-status-badge');
  const drawerContent = document.getElementById('drawer-content');
  const drawerActionDispute = document.getElementById('drawer-action-dispute');
  const drawerActionApprove = document.getElementById('drawer-action-approve');
  const drawerActionCredit = document.getElementById('drawer-action-credit');

  // Initialize
  init();

  function init() {
    setupEventListeners();
    loadCarriers();
    loadSummary();
    loadInvoices();
  }

  function setupEventListeners() {
    // Nav tabs
    navTabs.forEach(tab => {
      tab.addEventListener('click', () => {
        navTabs.forEach(t => t.classList.remove('active'));
        tabContents.forEach(c => c.classList.remove('active'));
        tab.classList.add('active');
        activeTab = tab.dataset.tab;
        const target = document.getElementById(activeTab);
        if (target) target.classList.add('active');

        if (activeTab === 'tab-evaluation') loadEvaluation();
        if (activeTab === 'tab-exceptions') loadExceptions();
        if (activeTab === 'tab-credits') loadCreditNotes();
        if (activeTab === 'tab-validation') loadValidation();
      });
    });

    // Role switcher
    if (roleSelect) {
      roleSelect.addEventListener('change', (e) => {
        activeRole = e.target.value;
        showToast(`Active role switched to: ${activeRole}`);
        updateRoleActions();
      });
    }

    // Filters
    [filterDecision, filterCarrier, filterIssue].forEach(f => {
      if (f) f.addEventListener('change', () => loadInvoices());
    });
    if (searchInput) {
      let debounceTimer;
      searchInput.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => loadInvoices(), 300);
      });
    }

    // Drawer close
    if (btnCloseDrawer) {
      btnCloseDrawer.addEventListener('click', closeDrawer);
    }
    if (drawerOverlay) {
      drawerOverlay.addEventListener('click', (e) => {
        if (e.target === drawerOverlay) closeDrawer();
      });
    }

    // Header Actions
    if (btnRunAudit) {
      btnRunAudit.addEventListener('click', async () => {
        btnRunAudit.disabled = true;
        btnRunAudit.innerText = 'Auditing...';
        showToast('Running rule-based audit engine across all invoices...');
        try {
          const res = await fetch('/api/run-audit', { method: 'POST' });
          const data = await res.json();
          showToast('Audit run completed successfully!');
          loadSummary();
          loadInvoices();
        } catch (err) {
          showToast('Audit run failed: ' + err.message);
        } finally {
          btnRunAudit.disabled = false;
          btnRunAudit.innerText = 'Run Audit';
        }
      });
    }

    if (btnRegenStarter) {
      btnRegenStarter.addEventListener('click', () => triggerRegen('starter'));
    }
    if (btnRegenFull) {
      btnRegenFull.addEventListener('click', () => triggerRegen('full'));
    }

    // Drawer actions
    if (drawerActionDispute) {
      drawerActionDispute.addEventListener('click', () => recordAction('DISPUTE', 'Dispute notice sent to carrier regarding rate/weight discrepancy.'));
    }
    if (drawerActionApprove) {
      drawerActionApprove.addEventListener('click', () => recordAction('APPROVED', 'Invoice approved for settlement by ' + activeRole));
    }
    if (drawerActionCredit) {
      drawerActionCredit.addEventListener('click', () => recordAction('CREDIT_REQUESTED', 'Requested carrier credit note to offset overcharge.'));
    }
  }

  async function triggerRegen(scale) {
    const confirmed = confirm(`Regenerate synthetic freight dataset with scale '${scale}' (Seed: 20261022)?`);
    if (!confirmed) return;
    showToast(`Generating ${scale} dataset (Master data, shipments, invoices, tariffs)...`);
    try {
      const res = await fetch('/api/regenerate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scale, seed: 20261022 })
      });
      const data = await res.json();
      showToast(`Regeneration to ${scale} completed!`);
      loadSummary();
      loadCarriers();
      loadInvoices();
    } catch (err) {
      showToast('Regeneration failed: ' + err.message);
    }
  }

  async function loadSummary() {
    try {
      const res = await fetch('/api/summary');
      const data = await res.json();
      currentSummary = data;

      // Update KPI widgets
      const s = data.summary || {};
      const f = data.financial_metrics || {};
      const g = data.ground_truth_evaluation || {};

      document.getElementById('kpi-total-invoices').innerText = (s.total_invoices_audited || 0).toLocaleString();
      document.getElementById('kpi-pass-count').innerText = `${s.pass_count || 0} (${((s.pass_count/s.total_invoices_audited)*100 || 0).toFixed(1)}%)`;
      document.getElementById('kpi-review-count').innerText = s.review_count || 0;
      document.getElementById('kpi-reject-count').innerText = s.reject_count || 0;
      
      document.getElementById('kpi-total-billed').innerText = `$${(f.total_billed_spend_usd || 0).toLocaleString(undefined, {minimumFractionDigits: 2})}`;
      document.getElementById('kpi-discrepancy-savings').innerText = `$${(f.total_discrepancy_overcharge_usd || 0).toLocaleString(undefined, {minimumFractionDigits: 2})}`;
      document.getElementById('kpi-roi-pct').innerText = `${f.potential_audit_savings_roi_pct || 0}%`;

      document.getElementById('kpi-accuracy').innerText = `${((g.accuracy || 1) * 100).toFixed(1)}%`;
      document.getElementById('kpi-recall').innerText = `${((g.recall || 1) * 100).toFixed(1)}%`;
    } catch (err) {
      console.error('Failed to load summary:', err);
    }
  }

  async function loadCarriers() {
    try {
      const res = await fetch('/api/carriers');
      const data = await res.json();
      if (filterCarrier && data.carriers) {
        filterCarrier.innerHTML = '<option value="">All Carriers</option>';
        data.carriers.forEach(c => {
          const opt = document.createElement('option');
          opt.value = c.carrier_id;
          opt.textContent = `${c.carrier_id} - ${c.carrier_name}`;
          filterCarrier.appendChild(opt);
        });
      }
    } catch (err) {
      console.error(err);
    }
  }

  async function loadInvoices() {
    const decision = filterDecision ? filterDecision.value : '';
    const carrier = filterCarrier ? filterCarrier.value : '';
    const issue = filterIssue ? filterIssue.value : '';
    const q = searchInput ? searchInput.value.trim() : '';

    const params = new URLSearchParams({ decision, carrier, issue, q });
    try {
      const res = await fetch(`/api/invoices?${params.toString()}`);
      const data = await res.json();
      currentInvoices = data.invoices || [];
      renderInvoicesTable(currentInvoices, data.filtered_count, data.total);
    } catch (err) {
      console.error('Failed to load invoices:', err);
    }
  }

  function renderInvoicesTable(invoices, filteredCount, totalCount) {
    const counterEl = document.getElementById('table-count-label');
    if (counterEl) {
      counterEl.innerText = `Showing ${invoices.length} of ${filteredCount} invoices (${totalCount} total)`;
    }

    if (!invoicesTableBody) return;
    invoicesTableBody.innerHTML = '';

    if (invoices.length === 0) {
      invoicesTableBody.innerHTML = `<tr><td colspan="8" style="text-align: center; padding: 2rem; color: var(--text-dim);">No freight invoices match the selected filters.</td></tr>`;
      return;
    }

    invoices.forEach(inv => {
      const tr = document.createElement('tr');
      if (inv.invoice_id === selectedInvoiceId) tr.classList.add('selected');

      const decisionBadge = getBadgeHtml(inv.decision);
      const issues = inv.issue_types ? inv.issue_types.split('|').map(t => `<span class="badge badge-issue">${t}</span>`).join(' ') : '<span style="color:var(--text-dim);">-</span>';
      const variance = inv.variance ? (parseFloat(inv.variance) > 0 ? `+$${parseFloat(inv.variance).toFixed(2)}` : `$${parseFloat(inv.variance).toFixed(2)}`) : '-';

      tr.innerHTML = `
        <td style="font-weight: 600; color: #a5b4fc;">${inv.invoice_id}</td>
        <td>${inv.shipment_id}</td>
        <td>${inv.carrier_id}</td>
        <td>${inv.invoice_date || '-'}</td>
        <td style="font-weight: 600;">$${parseFloat(inv.billed_total).toFixed(2)}</td>
        <td>${inv.expected_total ? `$${parseFloat(inv.expected_total).toFixed(2)}` : '-'}</td>
        <td style="color: ${parseFloat(inv.variance) > 0 ? 'var(--status-reject-text)' : 'inherit'}; font-weight: 600;">${variance}</td>
        <td>${decisionBadge}</td>
        <td>${issues}</td>
      `;

      tr.addEventListener('click', () => openInvoiceDetail(inv.invoice_id));
      invoicesTableBody.appendChild(tr);
    });
  }

  async function openInvoiceDetail(invId) {
    selectedInvoiceId = invId;
    document.querySelectorAll('#invoices-table-body tr').forEach(r => r.classList.remove('selected'));
    
    drawerInvoiceId.innerText = invId;
    drawerContent.innerHTML = `<div style="text-align:center; padding: 2rem; color:var(--text-dim);">Loading 360° audit trace...</div>`;
    drawerOverlay.classList.add('open');

    try {
      const res = await fetch(`/api/invoice-detail?id=${invId}`);
      const d = await res.json();
      renderInvoiceDetail(d);
    } catch (err) {
      drawerContent.innerHTML = `<div style="color:var(--status-reject-text);">Failed to load trace: ${err.message}</div>`;
    }
  }

  function renderInvoiceDetail(d) {
    const inv = d.invoice || {};
    const aud = d.audit_result || {};
    const shp = d.shipment || null;
    const rate = d.rate_card || null;
    const lines = d.lines || [];
    const expectedLines = d.expected_lines || [];
    const exceptions = d.exceptions || [];
    const credits = d.credit_notes || [];
    const events = d.audit_events || [];
    const gt = d.ground_truth || null;

    drawerStatusBadge.innerHTML = getBadgeHtml(aud.decision || 'RECEIVED');

    let html = '';

    // 1. Audit Outcome & Exception Banner
    if (aud.decision === 'REJECT' || aud.decision === 'REVIEW') {
      html += `
        <div class="detail-section" style="border-left: 4px solid ${aud.decision === 'REJECT' ? 'var(--status-reject-text)' : 'var(--status-review-text)'}; background: rgba(0,0,0,0.3);">
          <div class="detail-section-title" style="color: ${aud.decision === 'REJECT' ? 'var(--status-reject-text)' : 'var(--status-review-text)'};">
            <span>🚨 Audit Decision: ${aud.decision}</span>
            <span>Variance: $${parseFloat(aud.variance || 0).toFixed(2)}</span>
          </div>
          ${exceptions.map(e => `
            <div style="margin-bottom: 0.5rem; font-size: 0.8rem;">
              <span class="badge badge-issue">${e.issue_type}</span>
              <span style="font-weight: 600; color: #fca5a5;">${e.severity}:</span>
              <span>${e.explanation}</span>
            </div>
          `).join('')}
          ${gt ? `<div style="margin-top:0.5rem; font-size:0.75rem; color:var(--text-muted); border-top:1px dashed var(--border-color); padding-top:4px;">
            <b>Ground Truth Injected Anomaly:</b> ${gt.issue_type} (${gt.details})
          </div>` : ''}
        </div>
      `;
    } else {
      html += `
        <div class="detail-section" style="border-left: 4px solid var(--status-pass-text); background: rgba(16, 185, 129, 0.05);">
          <div class="detail-section-title" style="color: var(--status-pass-text);">
            <span>✓ Audit Decision: PASSED</span>
            <span>Variance: $0.00</span>
          </div>
          <p style="font-size:0.8rem; color:var(--text-muted);">Invoice charges match contracted rate card, chargeable weight tier, fuel surcharge percentage, and approved accessorial records with 100% precision.</p>
        </div>
      `;
    }

    // 2. Invoice & Shipment Characteristics (3-Way Matching)
    html += `
      <div class="detail-section">
        <div class="detail-section-title">
          <span>📦 Shipment Characteristics & Physical Attributes</span>
          <span>${shp ? shp.shipment_id : 'UNKNOWN SHIPMENT'}</span>
        </div>
        ${shp ? `
          <div class="grid-3" style="margin-bottom: 0.75rem;">
            <div class="meta-field"><span class="meta-label">Origin -> Dest</span><span class="meta-value">${shp.lane_id}</span></div>
            <div class="meta-field"><span class="meta-label">Service Level</span><span class="meta-value">${shp.service}</span></div>
            <div class="meta-field"><span class="meta-label">Delivery Date</span><span class="meta-value">${shp.delivery_date} (${shp.delivery_status})</span></div>
          </div>
          <div class="grid-3" style="background: rgba(255,255,255,0.02); padding: 8px; border-radius: var(--radius-sm);">
            <div class="meta-field"><span class="meta-label">Actual Scale Weight</span><span class="meta-value">${shp.actual_weight_kg} kg</span></div>
            <div class="meta-field"><span class="meta-label">Dimensions (L x W x H)</span><span class="meta-value">${shp.length_cm} × ${shp.width_cm} × ${shp.height_cm} cm</span></div>
            <div class="meta-field"><span class="meta-label">Dim Weight (Divisor 5000)</span><span class="meta-value">${shp.dimensional_weight_kg} kg</span></div>
          </div>
          <div style="margin-top: 0.5rem; font-size: 0.78rem; color: #a5b4fc;">
            <b>Chargeable Weight Formula:</b> max(${shp.actual_weight_kg} kg, ${shp.dimensional_weight_kg} kg) = <b>${shp.chargeable_weight_kg} kg</b>
          </div>
        ` : `
          <div style="color: var(--status-reject-text); font-size: 0.82rem;">
            ⚠️ <b>Shipment Not Found:</b> The referenced shipment ID (${inv.shipment_id}) does not exist in operational booking records.
          </div>
        `}
      </div>
    `;

    // 3. Contracted Rate Card Tariff Matching
    html += `
      <div class="detail-section">
        <div class="detail-section-title">
          <span>📄 Contracted Rate Card Tariff</span>
          <span>${rate ? rate.rate_id : 'Missing Tariff'}</span>
        </div>
        ${rate ? `
          <div class="grid-3">
            <div class="meta-field"><span class="meta-label">Contracted Base Rate</span><span class="meta-value">$${parseFloat(rate.base_rate).toFixed(2)}</span></div>
            <div class="meta-field"><span class="meta-label">Fuel Surcharge %</span><span class="meta-value">${(parseFloat(rate.fuel_pct) * 100).toFixed(0)}%</span></div>
            <div class="meta-field"><span class="meta-label">Contract Validity</span><span class="meta-value">${rate.effective_from} to ${rate.effective_to} (${rate.status})</span></div>
          </div>
          <div style="margin-top: 0.5rem; font-size: 0.75rem; color: var(--text-dim);">
            Weight Tier Range: [${rate.weight_min_kg} kg, ${rate.weight_max_kg} kg)
          </div>
        ` : `
          <div style="color: var(--status-reject-text);">No matching contracted rate card found for carrier and lane.</div>
        `}
      </div>
    `;

    // 4. Line Item Reconciliation: Expected vs Billed
    html += `
      <div class="detail-section">
        <div class="detail-section-title">
          <span>⚖️ Line Item Reconciliation (Expected vs Billed)</span>
          <span>Billed: $${parseFloat(inv.billed_total || 0).toFixed(2)}</span>
        </div>
        <table class="match-table">
          <thead>
            <tr>
              <th>Line #</th>
              <th>Charge Type</th>
              <th>Description</th>
              <th>Expected ($)</th>
              <th>Billed ($)</th>
              <th>Variance</th>
            </tr>
          </thead>
          <tbody>
            ${lines.map(l => {
              const expMatch = expectedLines.find(e => e.line_type === l.line_type);
              const expVal = expMatch ? parseFloat(expMatch.amount) : 0.00;
              const bldVal = parseFloat(l.amount);
              const diff = bldVal - expVal;
              const isMismatch = Math.abs(diff) > 0.01;
              return `
                <tr class="${isMismatch ? 'mismatch' : 'match'}">
                  <td>${l.line_no}</td>
                  <td><b>${l.line_type}</b></td>
                  <td>${l.description}</td>
                  <td>${expMatch ? `$${expVal.toFixed(2)}` : '<span style="color:var(--text-dim);">-</span>'}</td>
                  <td style="font-weight: 600;">$${bldVal.toFixed(2)}</td>
                  <td style="color: ${diff > 0 ? 'var(--status-reject-text)' : (diff < 0 ? 'var(--status-pass-text)' : 'inherit')}; font-weight: 600;">
                    ${diff !== 0 ? (diff > 0 ? `+$${diff.toFixed(2)}` : `-$${Math.abs(diff).toFixed(2)}`) : '$0.00'}
                  </td>
                </tr>
              `;
            }).join('')}
          </tbody>
        </table>
      </div>
    `;

    // 5. Credit Note & Dispute Reconciliation
    if (credits.length > 0) {
      html += `
        <div class="detail-section">
          <div class="detail-section-title">
            <span>💳 Credit Note & Dispute Settlement</span>
            <span>${credits.length} Record(s)</span>
          </div>
          ${credits.map(c => `
            <div style="padding: 8px; background: rgba(0,0,0,0.2); border-radius: var(--radius-sm); margin-bottom: 0.5rem;">
              <div style="display:flex; justify-content:space-between; margin-bottom: 4px;">
                <b>${c.credit_note_id}</b>
                <span class="badge ${c.validation_status === 'VALID' ? 'badge-pass' : 'badge-reject'}">${c.validation_status}</span>
              </div>
              <div class="grid-2">
                <div class="meta-field"><span class="meta-label">Credit Note Amount</span><span class="meta-value">$${parseFloat(c.amount).toFixed(2)}</span></div>
                <div class="meta-field"><span class="meta-label">Approved Dispute Limit</span><span class="meta-value">$${parseFloat(c.approved_dispute_amount).toFixed(2)}</span></div>
              </div>
              ${c.validation_status === 'EXCESS_CREDIT' ? `
                <div style="color:var(--status-reject-text); font-size:0.75rem; margin-top:4px;">
                  ⚠️ Credit note amount exceeds the approved dispute settlement limit!
                </div>
              ` : ''}
            </div>
          `).join('')}
        </div>
      `;
    }

    // 6. Chronological Audit Trail & State Transitions
    html += `
      <div class="detail-section">
        <div class="detail-section-title">
          <span>🕒 Preserved Audit Trail (Immutable Event History)</span>
        </div>
        <div class="timeline">
          ${events.map(ev => `
            <div class="timeline-item">
              <div class="timeline-dot"></div>
              <div class="timeline-time">${ev.timestamp} • <b>${ev.actor}</b> (${ev.entity_type}: ${ev.previous_state} -> ${ev.new_state})</div>
              <div class="timeline-text">${ev.notes}</div>
            </div>
          `).join('')}
        </div>
      </div>
    `;

    drawerContent.innerHTML = html;
  }

  function closeDrawer() {
    drawerOverlay.classList.remove('open');
    selectedInvoiceId = null;
    document.querySelectorAll('#invoices-table-body tr').forEach(r => r.classList.remove('selected'));
  }

  async function recordAction(actionType, defaultNotes) {
    if (!selectedInvoiceId) return;
    const notes = prompt(`Confirm action '${actionType}' for ${selectedInvoiceId}:`, defaultNotes);
    if (!notes) return;

    try {
      const res = await fetch('/api/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: actionType,
          invoice_id: selectedInvoiceId,
          actor: activeRole,
          notes: notes
        })
      });
      const data = await res.json();
      showToast(`Action '${actionType}' applied!`);
      // Reload drawer
      openInvoiceDetail(selectedInvoiceId);
    } catch (err) {
      showToast('Action failed: ' + err.message);
    }
  }

  function updateRoleActions() {
    // Show/hide or adjust action buttons based on active persona
    if (drawerActionApprove) {
      drawerActionApprove.style.display = (activeRole === 'Operations Manager' || activeRole === 'Logistics Analyst') ? 'inline-flex' : 'none';
    }
    if (drawerActionDispute) {
      drawerActionDispute.style.display = (activeRole === 'Logistics Analyst' || activeRole === 'Planner') ? 'inline-flex' : 'none';
    }
    if (drawerActionCredit) {
      drawerActionCredit.style.display = (activeRole === 'Carrier / Warehouse Operator' || activeRole === 'Logistics Analyst') ? 'inline-flex' : 'none';
    }
  }

  async function loadExceptions() {
    const container = document.getElementById('exceptions-container');
    if (!container) return;
    container.innerHTML = '<div style="color:var(--text-dim); padding:1rem;">Loading exceptions...</div>';
    try {
      const res = await fetch('/api/exceptions');
      const data = await res.json();
      const list = data.exceptions || [];
      if (list.length === 0) {
        container.innerHTML = '<div style="padding:1.5rem; color:var(--text-dim);">No open exceptions found.</div>';
        return;
      }
      container.innerHTML = `
        <table class="data-table">
          <thead>
            <tr>
              <th>Exception ID</th>
              <th>Invoice ID</th>
              <th>Shipment ID</th>
              <th>Carrier</th>
              <th>Issue Type</th>
              <th>Severity</th>
              <th>Variance ($)</th>
              <th>Explanation</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            ${list.map(e => `
              <tr onclick="window.inspectInvoice('${e.invoice_id}')">
                <td style="font-weight:600; color:#a5b4fc;">${e.exception_id}</td>
                <td>${e.invoice_id}</td>
                <td>${e.shipment_id}</td>
                <td>${e.carrier_id}</td>
                <td><span class="badge badge-issue">${e.issue_type}</span></td>
                <td>${getBadgeHtml(e.severity)}</td>
                <td style="color:var(--status-reject-text); font-weight:600;">$${parseFloat(e.variance || 0).toFixed(2)}</td>
                <td style="max-width:300px; overflow:hidden; text-overflow:ellipsis;">${e.explanation}</td>
                <td><span class="badge badge-review">${e.status}</span></td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
    } catch (err) {
      container.innerHTML = `<div style="color:var(--status-reject-text);">Error: ${err.message}</div>`;
    }
  }

  async function loadCreditNotes() {
    const container = document.getElementById('credits-container');
    if (!container) return;
    container.innerHTML = '<div style="color:var(--text-dim); padding:1rem;">Loading credit notes...</div>';
    try {
      const res = await fetch('/api/credit-notes');
      const data = await res.json();
      const list = data.credit_notes || [];
      container.innerHTML = `
        <table class="data-table">
          <thead>
            <tr>
              <th>Credit Note ID</th>
              <th>Invoice ID</th>
              <th>Carrier</th>
              <th>Amount ($)</th>
              <th>Approved Limit ($)</th>
              <th>Validation Status</th>
              <th>Settlement Status</th>
            </tr>
          </thead>
          <tbody>
            ${list.map(c => `
              <tr onclick="window.inspectInvoice('${c.invoice_id}')">
                <td style="font-weight:600; color:#a5b4fc;">${c.credit_note_id}</td>
                <td>${c.invoice_id}</td>
                <td>${c.carrier_id}</td>
                <td style="font-weight:600;">$${parseFloat(c.amount).toFixed(2)}</td>
                <td>$${parseFloat(c.approved_dispute_amount).toFixed(2)}</td>
                <td><span class="badge ${c.validation_status === 'VALID' ? 'badge-pass' : 'badge-reject'}">${c.validation_status}</span></td>
                <td><span class="badge ${c.status === 'APPLIED' ? 'badge-pass' : 'badge-review'}">${c.status}</span></td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
    } catch (err) {
      container.innerHTML = `<div style="color:var(--status-reject-text);">Error: ${err.message}</div>`;
    }
  }

  async function loadEvaluation() {
    const container = document.getElementById('evaluation-container');
    if (!container) return;
    try {
      const res = await fetch('/api/summary');
      const data = await res.json();
      const g = data.ground_truth_evaluation || {};
      const rates = g.detection_rate_by_issue_type || {};

      container.innerHTML = `
        <div style="margin-bottom: 1.5rem;">
          <h3 style="font-size:1.1rem; font-weight:700; margin-bottom:0.5rem;">Ground Truth Benchmark Evaluation Matrix</h3>
          <p style="color:var(--text-muted); font-size:0.82rem;">
            Measures the audit engine's detection accuracy against strictly isolated, out-of-band injected synthetic anomalies.
            Ground truth is never consumed by the rule engine.
          </p>
        </div>

        <div class="cm-container" style="margin-bottom: 2rem;">
          <div class="cm-box" style="border-color: rgba(16, 185, 129, 0.4);">
            <div class="cm-label">True Positives (Anomalies Detected)</div>
            <div class="cm-val text-pass">${g.true_positives || 0}</div>
            <div style="font-size:0.75rem; color:var(--text-dim);">Correctly caught discrepancies</div>
          </div>
          <div class="cm-box">
            <div class="cm-label">False Positives (Clean Flagged)</div>
            <div class="cm-val" style="color:var(--text-dim);">${g.false_positives || 0}</div>
            <div style="font-size:0.75rem; color:var(--text-dim);">False alarms on valid invoices</div>
          </div>
          <div class="cm-box">
            <div class="cm-label">False Negatives (Missed Anomalies)</div>
            <div class="cm-val text-reject">${g.false_negatives || 0}</div>
            <div style="font-size:0.75rem; color:var(--text-dim);">Undetected overcharges / violations</div>
          </div>
          <div class="cm-box" style="border-color: rgba(99, 102, 241, 0.4);">
            <div class="cm-label">True Negatives (Clean Invoices Passed)</div>
            <div class="cm-val" style="color:#a5b4fc;">${g.true_negatives || 0}</div>
            <div style="font-size:0.75rem; color:var(--text-dim);">Valid invoices smoothly settled</div>
          </div>
        </div>

        <div class="detail-section">
          <div class="detail-section-title">
            <span>Detection Rate by Injected Anomaly Category</span>
            <span>Target: 100% Recall</span>
          </div>
          <table class="match-table">
            <thead>
              <tr>
                <th>Anomaly Taxonomy</th>
                <th>Injected Count</th>
                <th>Detected Count</th>
                <th>Detection Recall Rate</th>
                <th>Benchmark Status</th>
              </tr>
            </thead>
            <tbody>
              ${Object.entries(rates).map(([k, v]) => `
                <tr>
                  <td><b>${k}</b></td>
                  <td>${v.injected}</td>
                  <td>${v.detected}</td>
                  <td style="font-weight:700; color: ${v.rate >= 1 ? 'var(--status-pass-text)' : 'var(--status-reject-text)'};">${(v.rate * 100).toFixed(1)}%</td>
                  <td><span class="badge ${v.rate >= 1 ? 'badge-pass' : 'badge-reject'}">${v.rate >= 1 ? 'PASSED (100%)' : 'NEEDS ATTENTION'}</span></td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      `;
    } catch (err) {
      container.innerHTML = `<div style="color:var(--status-reject-text);">Error: ${err.message}</div>`;
    }
  }

  async function loadValidation() {
    const container = document.getElementById('validation-container');
    if (!container) return;
    container.innerHTML = '<div style="color:var(--text-dim); padding:1rem;">Loading validation summary...</div>';
    try {
      const res = await fetch('/api/validation');
      const data = await res.json();
      const checks = data.checks || [];

      container.innerHTML = `
        <div style="margin-bottom: 1.5rem; display:flex; justify-content:space-between; align-items:center;">
          <div>
            <h3 style="font-size:1.1rem; font-weight:700;">Data Quality & Integrity Verification Suite</h3>
            <p style="color:var(--text-muted); font-size:0.82rem;">Step 8 validation: Primary Keys, Foreign Keys, Allowed Enums, Date Ordering, and Arithmetic Reconciliation.</p>
          </div>
          <span class="badge ${data.all_checks_passed ? 'badge-pass' : 'badge-reject'}" style="font-size:0.9rem; padding:6px 14px;">
            ${data.passed_checks} / ${data.total_checks} CHECKS PASSED
          </span>
        </div>

        <table class="data-table">
          <thead>
            <tr>
              <th>Rule Category</th>
              <th>Integrity Rule Description</th>
              <th>Status</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            ${checks.map(c => `
              <tr>
                <td><b>${c.category}</b></td>
                <td>${c.check}</td>
                <td><span class="badge ${c.passed ? 'badge-pass' : 'badge-reject'}">${c.passed ? 'PASSED' : 'FAILED'}</span></td>
                <td style="color:var(--text-muted);">${c.details || '-'}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
    } catch (err) {
      container.innerHTML = `<div style="color:var(--status-reject-text);">Error: ${err.message}</div>`;
    }
  }

  function getBadgeHtml(decision) {
    if (decision === 'PASS' || decision === 'APPROVED' || decision === 'VALID') {
      return `<span class="badge badge-pass">✓ ${decision}</span>`;
    } else if (decision === 'REVIEW') {
      return `<span class="badge badge-review">⚡ ${decision}</span>`;
    } else if (decision === 'REJECT' || decision === 'EXCESS_CREDIT') {
      return `<span class="badge badge-reject">✕ ${decision}</span>`;
    } else {
      return `<span class="badge" style="background:var(--bg-tertiary);">${decision}</span>`;
    }
  }

  function showToast(msg) {
    let toast = document.getElementById('app-toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'app-toast';
      toast.className = 'toast';
      document.body.appendChild(toast);
    }
    toast.innerText = msg;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 3500);
  }

  window.inspectInvoice = function(invId) {
    // Switch to workbench tab and open invoice
    document.querySelector('.nav-tab[data-tab="tab-workbench"]').click();
    openInvoiceDetail(invId);
  };
});
