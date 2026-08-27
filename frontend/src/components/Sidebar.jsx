import React from 'react';
import { LayoutDashboard, Sliders, Radio, FileText, Activity, Eye, GitBranch, Database, Flame, Smartphone, Terminal } from 'lucide-react';

export default function Sidebar({ activeTab, setActiveTab }) {
  const overviewItems = [
    { id: 'dashboard', label: 'Analytics Dashboard', icon: LayoutDashboard },
    { id: 'profiles', label: 'Stress Profiles', icon: Sliders },
    { id: 'human-stress', label: 'Human Stress Profiler', icon: Flame },
    { id: 'app-integration', label: 'App Integration (SDK)', icon: Terminal },
  ];

  const navItems = [
    { id: 'live', label: 'Live Monitor', icon: Radio },
    { id: 'vision', label: 'Vision DOM Debugger', icon: Eye },
    { id: 'attribution', label: 'Attribution Reports', icon: FileText },
    { id: 'executions', label: 'Test Executions', icon: Activity },
    { id: 'cicd', label: 'CI/CD Pipelines', icon: GitBranch },
    { id: 'benchmarks', label: 'Benchmark Datasets', icon: Database },
  ];

  return (
    <aside className="sidebar" style={{ position: 'sticky', top: '66px', height: 'calc(100vh - 66px)', overflowY: 'auto' }}>
      <div>
        <div className="sidebar-group">
          <div className="sidebar-heading">Overview & Setup</div>
          <div className="sidebar-nav">
            {overviewItems.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.id}
                  className={`sidebar-button ${activeTab === item.id ? 'active' : ''}`}
                  onClick={() => setActiveTab(item.id)}
                >
                  <Icon size={17} />
                  {item.label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="sidebar-group">
          <div className="sidebar-heading">Navigation</div>
          <div className="sidebar-nav">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.id}
                  className={`sidebar-button ${activeTab === item.id ? 'active' : ''}`}
                  onClick={() => setActiveTab(item.id)}
                >
                  <Icon size={17} />
                  {item.label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="sidebar-group">
          <div className="sidebar-heading">Target Emulators / Devices</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: '#10b981', background: 'rgba(16, 185, 129, 0.1)', padding: '8px 12px', borderRadius: '8px', border: '1px solid rgba(16, 185, 129, 0.2)' }}>
              <Smartphone size={15} /> Pixel 7 Pro (API 34)
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: '#9ca3af', background: 'rgba(255, 255, 255, 0.03)', padding: '8px 12px', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.06)' }}>
              <Smartphone size={15} /> Samsung S24, Pixel 5
            </div>
          </div>
        </div>
      </div>

      <div className="user-card" style={{ marginTop: 'auto' }}>
        <div className="user-avatar">LB</div>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <div style={{ fontSize: '13px', fontWeight: '700' }}>Luqman Booso</div>
          <div style={{ fontSize: '11px', color: '#6b7280' }}>Vision Oracle Lead</div>
        </div>
      </div>
    </aside>
  );
}
