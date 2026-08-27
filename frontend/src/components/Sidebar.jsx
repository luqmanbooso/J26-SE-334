import React from 'react';
import { LayoutDashboard, Sliders, Radio, FileText, Activity, Eye, GitBranch, Database, Flame, Smartphone, Terminal, Zap, ShieldAlert, CheckCircle2 } from 'lucide-react';

export default function Sidebar({ activeTab, setActiveTab }) {
  const overviewItems = [
    { id: 'dashboard', label: 'Analytics Dashboard', icon: LayoutDashboard, badge: 'Live' },
    { id: 'profiles', label: 'Stress Profiles (C1)', icon: Sliders, badge: null },
    { id: 'human-stress', label: 'Human Stress (C2)', icon: Flame, badge: 'New' },
    { id: 'app-integration', label: 'App Integration (SDK)', icon: Terminal, badge: null },
  ];

  const navItems = [
    { id: 'live', label: 'Live Monitor & ADB', icon: Radio, badge: 'Stream' },
    { id: 'vision', label: 'Vision Oracle (C3)', icon: Eye, badge: 'VLM' },
    { id: 'attribution', label: 'Attribution & Heal (C4)', icon: FileText, badge: 'Auto' },
    { id: 'executions', label: 'Test Executions', icon: Activity, badge: null },
    { id: 'cicd', label: 'CI/CD Pipelines', icon: GitBranch, badge: null },
    { id: 'benchmarks', label: 'Benchmark Datasets', icon: Database, badge: '52+ Bugs' },
  ];

  return (
    <aside className="sidebar" style={{ position: 'sticky', top: '70px', height: 'calc(100vh - 70px)', overflowY: 'auto' }}>
      <div>
        {/* Section 1: Overview */}
        <div className="sidebar-group">
          <div className="sidebar-heading">Intelligence & Setup</div>
          <div className="sidebar-nav">
            {overviewItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  className={`sidebar-button ${isActive ? 'active' : ''}`}
                  onClick={() => setActiveTab(item.id)}
                >
                  <Icon size={17} className="sidebar-icon" />
                  <span style={{ flex: 1 }}>{item.label}</span>
                  {item.badge && (
                    <span
                      style={{
                        fontSize: '9px',
                        fontWeight: '700',
                        padding: '2px 6px',
                        borderRadius: '6px',
                        background: item.badge === 'Live' || item.badge === 'New' ? 'rgba(255,87,34,0.2)' : 'rgba(255,255,255,0.06)',
                        color: item.badge === 'Live' || item.badge === 'New' ? '#ff7043' : 'var(--text-muted)',
                        border: `1px solid ${item.badge === 'Live' || item.badge === 'New' ? 'rgba(255,87,34,0.4)' : 'rgba(255,255,255,0.08)'}`
                      }}
                    >
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Section 2: Core Engines */}
        <div className="sidebar-group">
          <div className="sidebar-heading">Execution Engines</div>
          <div className="sidebar-nav">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  className={`sidebar-button ${isActive ? 'active' : ''}`}
                  onClick={() => setActiveTab(item.id)}
                >
                  <Icon size={17} className="sidebar-icon" />
                  <span style={{ flex: 1 }}>{item.label}</span>
                  {item.badge && (
                    <span
                      style={{
                        fontSize: '9px',
                        fontWeight: '700',
                        padding: '2px 6px',
                        borderRadius: '6px',
                        background: item.badge === 'Stream' ? 'rgba(16,185,129,0.18)' : item.badge === 'VLM' ? 'rgba(139,92,246,0.2)' : 'rgba(255,255,255,0.06)',
                        color: item.badge === 'Stream' ? '#34d399' : item.badge === 'VLM' ? '#c084fc' : 'var(--text-muted)',
                        border: `1px solid ${item.badge === 'Stream' ? 'rgba(16,185,129,0.3)' : 'rgba(255,255,255,0.08)'}`
                      }}
                    >
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Section 3: Target Devices */}
        <div className="sidebar-group">
          <div className="sidebar-heading">Active Testbed Devices</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '12px', color: '#34d399', background: 'rgba(16, 185, 129, 0.08)', padding: '10px 12px', borderRadius: '10px', border: '1px solid rgba(16, 185, 129, 0.2)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Smartphone size={15} />
                <span>Pixel 7 Pro (API 34)</span>
              </div>
              <span className="pulse-beacon pulse-beacon-green" style={{ width: '6px', height: '6px' }} />
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '12px', color: 'var(--text-muted)', background: 'rgba(255, 255, 255, 0.02)', padding: '10px 12px', borderRadius: '10px', border: '1px solid rgba(255, 255, 255, 0.05)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Smartphone size={15} />
                <span>Samsung S24 (Ready)</span>
              </div>
              <span style={{ fontSize: '10px', color: 'var(--text-dim)' }}>Standby</span>
            </div>
          </div>
        </div>
      </div>

      {/* User Profile Card */}
      <div className="user-card" style={{ marginTop: 'auto' }}>
        <div className="user-avatar">LB</div>
        <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: '13px', fontWeight: '700', color: '#fff', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            Luqman Booso
          </div>
          <div style={{ fontSize: '11px', color: 'var(--accent-orange-bright)', fontWeight: '600' }}>
            Research Lead
          </div>
        </div>
        <CheckCircle2 size={14} color="#10b981" />
      </div>
    </aside>
  );
}
