import React, { useState } from 'react';
import { Activity, CheckCircle2, AlertTriangle, RefreshCw, Smartphone, Play, Search, Download, Filter, ChevronRight, X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export default function TestExecutions() {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('All');
  const [selectedRun, setSelectedRun] = useState(null);

  const runs = [
    { id: 'RUN-2026-0891', profile: 'Mid-Transaction Stress Test', app: 'CheckoutFlow.apk', status: 'HEALED', duration: '4m 12s', stress: '85% Severe', device: 'Pixel 7 Pro (API 34)', date: '2026-08-27 18:20', logSample: 'Found 1 layout collision. Repaired with S-BERT embedding (0.94 similarity).' },
    { id: 'RUN-2026-0890', profile: 'Network Flap & Low Memory', app: 'PaymentGateway.apk', status: 'ANOMALY_DETECTED', duration: '6m 45s', stress: '92% Critical', device: 'Samsung S24 (API 34)', date: '2026-08-27 17:45', logSample: 'Qwen2-VL flagged OVERFLOW_Y_COLLISION at checkout confirm button.' },
    { id: 'RUN-2026-0889', profile: 'Extreme CPU & Backgrounding', app: 'UserProfile.apk', status: 'PASSED', duration: '3m 10s', stress: '60% Moderate', device: 'Pixel 5 (API 30)', date: '2026-08-27 16:30', logSample: 'All test assertions passed cleanly under high background load.' },
    { id: 'RUN-2026-0888', profile: 'Biomechanical Tremor Test', app: 'AuthService.apk', status: 'HEALED', duration: '5m 02s', stress: '78% High', device: 'Pixel 7 Pro (API 34)', date: '2026-08-27 15:10', logSample: 'Fitts error compensation remapped missed tap target at login button.' },
    { id: 'RUN-2026-0887', profile: 'Thermal Throttling Suite', app: 'OrderCart.apk', status: 'PASSED', duration: '2m 55s', stress: '50% Medium', device: 'Samsung S24 (API 34)', date: '2026-08-27 14:00', logSample: 'Device throttled to 80C without introducing fatal ANR or UI collisions.' },
  ];

  const filteredRuns = runs.filter(r => {
    const matchesSearch = r.id.toLowerCase().includes(search.toLowerCase()) || r.profile.toLowerCase().includes(search.toLowerCase()) || r.app.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = statusFilter === 'All' || r.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '28px', width: '100%', maxWidth: '1280px', margin: '0 auto' }}>
      {/* Header */}
      <div className="glass-card" style={{ padding: '18px 26px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ background: 'rgba(251,146,60,0.12)', color: 'var(--accent-orange-bright)', width: '46px', height: '46px', borderRadius: '14px', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 0 16px rgba(251,146,60,0.2)' }}>
            <Activity size={24} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="glow-badge glow-badge-orange" style={{ fontSize: '9px', padding: '2px 8px' }}>Execution History</span>
              <span style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '600', textTransform: 'uppercase' }}>Campaign Ledger</span>
            </div>
            <h1 style={{ fontSize: '20px', fontWeight: '900', color: '#fff', marginTop: '2px' }}>
              Automated Robustness Test Campaigns
            </h1>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ position: 'relative' }}>
            <Search size={15} style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-dim)' }} />
            <input
              type="text"
              placeholder="Search run ID, profile, app..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="input-styled"
              style={{ paddingLeft: '38px', width: '240px', padding: '8px 14px 8px 38px' }}
            />
          </div>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="input-styled"
            style={{ width: '150px', padding: '8px 14px' }}
          >
            <option value="All">All Verdicts</option>
            <option value="HEALED">Healed (S-BERT)</option>
            <option value="ANOMALY_DETECTED">Anomaly (VLM)</option>
            <option value="PASSED">Passed</option>
          </select>

          <button className="btn-secondary" style={{ padding: '8px 16px', fontSize: '12px' }}>
            <Download size={15} /> Export History
          </button>
        </div>
      </div>

      {/* Runs Table */}
      <div className="glass-card" style={{ padding: '20px', overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-dim)', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.6px' }}>
              <th style={{ padding: '14px 18px' }}>Run ID</th>
              <th style={{ padding: '14px 18px' }}>Stress Scenario</th>
              <th style={{ padding: '14px 18px' }}>Target APK</th>
              <th style={{ padding: '14px 18px' }}>Device</th>
              <th style={{ padding: '14px 18px' }}>Chaos Load</th>
              <th style={{ padding: '14px 18px' }}>Duration</th>
              <th style={{ padding: '14px 18px' }}>Verdict Status</th>
              <th style={{ padding: '14px 18px', textAlign: 'right' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredRuns.map((run) => (
              <tr key={run.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', transition: 'background 0.2s' }}>
                <td style={{ padding: '16px 18px', fontFamily: 'var(--font-mono)', fontWeight: '700', color: 'var(--accent-orange-bright)' }}>
                  {run.id}
                </td>
                <td style={{ padding: '16px 18px', fontWeight: '600', color: '#fff' }}>
                  {run.profile}
                </td>
                <td style={{ padding: '16px 18px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: '12px' }}>
                  {run.app}
                </td>
                <td style={{ padding: '16px 18px', color: 'var(--text-muted)' }}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                    <Smartphone size={14} color="#64748b" /> {run.device}
                  </span>
                </td>
                <td style={{ padding: '16px 18px', color: '#fb7185', fontWeight: '600' }}>
                  {run.stress}
                </td>
                <td style={{ padding: '16px 18px', fontFamily: 'var(--font-mono)', color: 'var(--text-dim)' }}>
                  {run.duration}
                </td>
                <td style={{ padding: '16px 18px' }}>
                  {run.status === 'HEALED' && (
                    <span className="glow-badge glow-badge-green" style={{ fontSize: '10px' }}>
                      <RefreshCw size={11} /> S-BERT Healed
                    </span>
                  )}
                  {run.status === 'ANOMALY_DETECTED' && (
                    <span className="glow-badge glow-badge-red" style={{ fontSize: '10px' }}>
                      <AlertTriangle size={11} /> GUI Overlap Bug
                    </span>
                  )}
                  {run.status === 'PASSED' && (
                    <span className="glow-badge glow-badge-cyan" style={{ fontSize: '10px' }}>
                      <CheckCircle2 size={11} /> Clean Pass
                    </span>
                  )}
                </td>
                <td style={{ padding: '16px 18px', textAlign: 'right' }}>
                  <button
                    className="btn-secondary"
                    onClick={() => setSelectedRun(run)}
                    style={{ padding: '5px 14px', fontSize: '11px' }}
                  >
                    Inspect
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Expandable Execution Inspection Modal / Drawer */}
      <AnimatePresence>
        {selectedRun && (
          <div
            style={{
              position: 'fixed',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              background: 'rgba(5, 8, 16, 0.75)',
              backdropFilter: 'blur(8px)',
              zIndex: 999,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
            onClick={() => setSelectedRun(null)}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              onClick={(e) => e.stopPropagation()}
              className="glass-card"
              style={{
                width: '90%',
                maxWidth: '650px',
                zIndex: 1000,
                boxShadow: '0 25px 70px rgba(0,0,0,0.9), 0 0 35px rgba(251,146,60,0.25)',
                padding: '32px',
                border: '1px solid rgba(251, 146, 60, 0.3)'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span className="glow-badge glow-badge-orange">{selectedRun.id}</span>
                  <h3 style={{ fontSize: '18px', fontWeight: '800', color: '#fff' }}>Execution Log Diagnostics</h3>
                </div>
                <button
                  onClick={() => setSelectedRun(null)}
                  style={{ background: 'rgba(255,255,255,0.06)', border: 'none', color: '#fff', borderRadius: '50%', width: '32px', height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}
                >
                  <X size={16} />
                </button>
              </div>

              <div className="defect-table" style={{ marginBottom: '20px' }}>
                <div className="defect-row">
                  <span className="defect-label">Scenario Profile</span>
                  <span className="defect-val">{selectedRun.profile}</span>
                </div>
                <div className="defect-row">
                  <span className="defect-label">Target Application</span>
                  <span className="defect-val">{selectedRun.app}</span>
                </div>
                <div className="defect-row">
                  <span className="defect-label">Execution Device</span>
                  <span className="defect-val">{selectedRun.device}</span>
                </div>
                <div className="defect-row">
                  <span className="defect-label">Execution Timestamp</span>
                  <span className="defect-val">{selectedRun.date}</span>
                </div>
              </div>

              <div className="code-window" style={{ maxHeight: '160px', marginBottom: '20px' }}>
                <div style={{ color: '#34d399' }}>// Diagnostic Telemetry Summary:</div>
                <div style={{ color: '#cbd5e1', marginTop: '6px' }}>{selectedRun.logSample}</div>
              </div>

              <button className="btn-cta" onClick={() => setSelectedRun(null)} style={{ width: '100%', borderRadius: '20px' }}>
                Close Diagnostics
              </button>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
