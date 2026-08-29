import React, { useState } from 'react';
import { Database, Search, Eye, ExternalLink, Play, CheckCircle2, AlertTriangle, Layers, BookOpen, Download } from 'lucide-react';
import { motion } from 'framer-motion';

export default function BenchmarkApps() {
  const [activeTab, setActiveTab] = useState('themis');
  const [search, setSearch] = useState('');

  const themisBugs = [
    { id: 'THEMIS-01', app: 'AnkiDroid', bugType: 'Tail Energy & Network Lockout', reproducible: 'Yes (100%)', severity: 'Critical', paperRef: '[13] ESEC/FSE 2022' },
    { id: 'THEMIS-02', app: 'K-9 Mail', bugType: 'Async Thread Latency Overlap', reproducible: 'Yes (100%)', severity: 'High', paperRef: '[13] ESEC/FSE 2022' },
    { id: 'THEMIS-03', app: 'VLC Mobile', bugType: 'Thermal Throttling Frame Drop', reproducible: 'Yes (100%)', severity: 'Medium', paperRef: '[13] ESEC/FSE 2022' },
    { id: 'THEMIS-04', app: 'Nextcloud', bugType: 'Battery Drain State Spike', reproducible: 'Yes (100%)', severity: 'High', paperRef: '[13] ESEC/FSE 2022' },
    { id: 'THEMIS-05', app: 'AntennaPod', bugType: 'Audio Thread Deadlock under WiFi Loss', reproducible: 'Yes (100%)', severity: 'Critical', paperRef: '[13] ESEC/FSE 2022' },
    { id: 'THEMIS-06', app: 'OpenTracks', bugType: 'GPS Sensor Queue Overflow', reproducible: 'Yes (100%)', severity: 'Medium', paperRef: '[13] ESEC/FSE 2022' },
  ];

  const ricoScreens = [
    { id: 'RICO-8491', category: 'E-Commerce / Checkout', uiElements: '24 nodes', layoutComplexity: 'High', anomalyClass: 'Button-Text Overlap' },
    { id: 'RICO-8492', category: 'Finance / Banking', uiElements: '18 nodes', layoutComplexity: 'Medium', anomalyClass: 'Occluded Modal Input' },
    { id: 'RICO-8493', category: 'Social / Profile', uiElements: '32 nodes', layoutComplexity: 'Extreme', anomalyClass: 'Clipping at Screen Edge' },
    { id: 'RICO-8494', category: 'Productivity / Task', uiElements: '15 nodes', layoutComplexity: 'Low', anomalyClass: 'Z-Index Collision' },
  ];

  const filteredThemis = themisBugs.filter(b => b.app.toLowerCase().includes(search.toLowerCase()) || b.bugType.toLowerCase().includes(search.toLowerCase()) || b.id.toLowerCase().includes(search.toLowerCase()));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '28px', width: '100%', maxWidth: '1280px', margin: '0 auto' }}>
      {/* Header */}
      <div className="glass-card" style={{ padding: '18px 26px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ background: 'rgba(251,146,60,0.12)', color: 'var(--accent-orange-bright)', width: '46px', height: '46px', borderRadius: '14px', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 0 16px rgba(251,146,60,0.2)' }}>
            <Database size={24} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="glow-badge glow-badge-orange" style={{ fontSize: '9px', padding: '2px 8px' }}>Empirical Benchmarks</span>
              <span style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '600', textTransform: 'uppercase' }}>Ground-Truth Evaluation Datasets</span>
            </div>
            <h1 style={{ fontSize: '20px', fontWeight: '900', color: '#fff', marginTop: '2px' }}>
              Themis Benchmark (52 Crash Bugs) & Rico UI Dataset (72K+ Screens)
            </h1>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <button className={`nav-link ${activeTab === 'themis' ? 'active' : ''}`} onClick={() => setActiveTab('themis')} style={{ borderRadius: '20px', padding: '6px 18px', fontSize: '12px' }}>
            Themis Crash Dataset (52)
          </button>
          <button className={`nav-link ${activeTab === 'rico' ? 'active' : ''}`} onClick={() => setActiveTab('rico')} style={{ borderRadius: '20px', padding: '6px 18px', fontSize: '12px' }}>
            Rico UI Dataset (72K)
          </button>
        </div>
      </div>

      {/* Search & Action Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '14px', flexWrap: 'wrap' }}>
        <div style={{ position: 'relative' }}>
          <Search size={15} style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-dim)' }} />
          <input
            type="text"
            placeholder="Filter by bug ID, app name, category..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input-styled"
            style={{ paddingLeft: '38px', width: '280px', padding: '8px 14px 8px 38px' }}
          />
        </div>

        <button className="btn-secondary" style={{ padding: '8px 16px', fontSize: '12px' }}>
          <Download size={15} /> Export Ground-Truth JSON
        </button>
      </div>

      {/* Benchmark Table Content */}
      <div className="glass-card" style={{ padding: '20px', overflowX: 'auto' }}>
        {activeTab === 'themis' ? (
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-dim)', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.6px' }}>
                <th style={{ padding: '14px 18px' }}>Bug ID</th>
                <th style={{ padding: '14px 18px' }}>Target Application</th>
                <th style={{ padding: '14px 18px' }}>Bug Classification</th>
                <th style={{ padding: '14px 18px' }}>Severity</th>
                <th style={{ padding: '14px 18px' }}>HEART Reproducibility</th>
                <th style={{ padding: '14px 18px' }}>Paper Reference</th>
                <th style={{ padding: '14px 18px', textAlign: 'right' }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredThemis.map((bug) => (
                <tr key={bug.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', transition: 'background 0.2s' }}>
                  <td style={{ padding: '16px 18px', fontFamily: 'var(--font-mono)', color: 'var(--accent-orange-bright)', fontWeight: '700' }}>
                    {bug.id}
                  </td>
                  <td style={{ padding: '16px 18px', fontWeight: '700', color: '#fff' }}>
                    {bug.app}
                  </td>
                  <td style={{ padding: '16px 18px', color: '#fb7185' }}>
                    {bug.bugType}
                  </td>
                  <td style={{ padding: '16px 18px' }}>
                    <span
                      style={{
                        fontSize: '10px',
                        fontWeight: '700',
                        padding: '2px 8px',
                        borderRadius: '6px',
                        background: bug.severity === 'Critical' ? 'rgba(244,63,94,0.18)' : 'rgba(245,158,11,0.18)',
                        color: bug.severity === 'Critical' ? '#fb7185' : '#fbbf24',
                        border: `1px solid ${bug.severity === 'Critical' ? 'rgba(244,63,94,0.35)' : 'rgba(245,158,11,0.35)'}`
                      }}
                    >
                      {bug.severity}
                    </span>
                  </td>
                  <td style={{ padding: '16px 18px', color: '#34d399', fontWeight: '700' }}>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                      <CheckCircle2 size={14} /> {bug.reproducible}
                    </span>
                  </td>
                  <td style={{ padding: '16px 18px', color: 'var(--text-muted)' }}>
                    {bug.paperRef}
                  </td>
                  <td style={{ padding: '16px 18px', textAlign: 'right' }}>
                    <button className="btn-secondary" style={{ padding: '5px 14px', fontSize: '11px' }}>
                      Replay Test
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-dim)', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.6px' }}>
                <th style={{ padding: '14px 18px' }}>Rico Screen ID</th>
                <th style={{ padding: '14px 18px' }}>Category Domain</th>
                <th style={{ padding: '14px 18px' }}>DOM Element Count</th>
                <th style={{ padding: '14px 18px' }}>Layout Complexity</th>
                <th style={{ padding: '14px 18px' }}>Visual Anomaly Class</th>
                <th style={{ padding: '14px 18px', textAlign: 'right' }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {ricoScreens.map((screen) => (
                <tr key={screen.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', transition: 'background 0.2s' }}>
                  <td style={{ padding: '16px 18px', fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan-bright)', fontWeight: '700' }}>
                    {screen.id}
                  </td>
                  <td style={{ padding: '16px 18px', fontWeight: '700', color: '#fff' }}>
                    {screen.category}
                  </td>
                  <td style={{ padding: '16px 18px', color: 'var(--text-muted)' }}>
                    {screen.uiElements}
                  </td>
                  <td style={{ padding: '16px 18px', color: 'var(--accent-orange-bright)' }}>
                    {screen.layoutComplexity}
                  </td>
                  <td style={{ padding: '16px 18px', color: '#fb7185' }}>
                    {screen.anomalyClass}
                  </td>
                  <td style={{ padding: '16px 18px', textAlign: 'right' }}>
                    <button className="btn-secondary" style={{ padding: '5px 14px', fontSize: '11px' }}>
                      Inspect Screen
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
