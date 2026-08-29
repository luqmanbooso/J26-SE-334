import React, { useState } from 'react';
import {
  LayoutDashboard,
  Sliders,
  Radio,
  Eye,
  FileText,
  Smartphone,
  Layers,
  History,
  GitBranch,
  Database,
  Terminal,
  Settings,
  ChevronLeft,
  ChevronRight,
  Flame,
  Activity,
  PanelLeftClose,
  PanelLeft
} from 'lucide-react';

export default function Sidebar({ activeTab, setActiveTab }) {
  const [isCollapsed, setIsCollapsed] = useState(false);

  const navSections = [
    {
      title: 'Testing Core',
      items: [
        { id: 'dashboard', label: 'Analytics', icon: LayoutDashboard },
        { id: 'app-integration', label: 'App Integration', icon: Terminal },
        { id: 'profiles', label: 'Stress Profiles', icon: Sliders },
        { id: 'human-stress', label: 'Biomechanical', icon: Flame },
      ]
    },
    {
      title: 'Live Oracles',
      items: [
        { id: 'live', label: 'Live Monitor', icon: Radio, badge: '60 FPS' },
        { id: 'vision', label: 'Vision Debugger', icon: Eye, badge: 'VLM' },
        { id: 'attribution', label: 'Attribution & Heal', icon: FileText, badge: 'S-BERT' },
      ]
    },
    {
      title: 'DevOps & Research',
      items: [
        { id: 'executions', label: 'Test Executions', icon: History },
        { id: 'cicd', label: 'CI/CD Pipelines', icon: GitBranch },
        { id: 'benchmarks', label: 'Benchmark Datasets', icon: Database },
      ]
    }
  ];

  return (
    <aside className={`sidebar ${isCollapsed ? 'collapsed' : ''}`}>
      {/* Top Header Row with Collapse Toggle */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: isCollapsed ? 'center' : 'space-between', marginBottom: '14px', flexShrink: 0 }}>
        {!isCollapsed && (
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '1px' }}>
            Navigation Rail
          </div>
        )}
        <button
          className="sidebar-collapse-toggle"
          onClick={() => setIsCollapsed(!isCollapsed)}
          title={isCollapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
          style={{ margin: isCollapsed ? '0 auto' : '0' }}
        >
          {isCollapsed ? <PanelLeft size={15} /> : <PanelLeftClose size={15} />}
        </button>
      </div>

      {/* Device Context Emulator Pill */}
      {!isCollapsed ? (
        <div style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid var(--border-subtle)', borderRadius: '10px', padding: '10px 12px', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '10px', flexShrink: 0 }}>
          <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#10b981', boxShadow: '0 0 8px #10b981', flexShrink: 0 }} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: '11px', color: '#fff', fontWeight: '700', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              Pixel 7 Pro (API 34)
            </div>
            <div style={{ fontSize: '9.5px', color: 'var(--text-dim)' }}>
              ADB Connected • Port 5554
            </div>
          </div>
        </div>
      ) : (
        <div
          style={{ display: 'flex', justifyContent: 'center', marginBottom: '14px', flexShrink: 0 }}
          title="Pixel 7 Pro (API 34) - ADB Connected"
        >
          <div style={{ width: '34px', height: '34px', borderRadius: '8px', background: 'rgba(255, 255, 255, 0.03)', border: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative' }}>
            <Smartphone size={16} color="var(--text-muted)" />
            <div style={{ position: 'absolute', top: '5px', right: '5px', width: '5px', height: '5px', borderRadius: '50%', background: '#10b981', boxShadow: '0 0 6px #10b981' }} />
          </div>
        </div>
      )}

      {/* Scrollable Navigation Sections */}
      <div className="sidebar-scrollable-content">
        {navSections.map((section, idx) => (
          <div key={idx} className="sidebar-group">
            {!isCollapsed && <div className="sidebar-heading">{section.title}</div>}
            <nav className="sidebar-nav">
              {section.items.map((item) => {
                const IconComponent = item.icon;
                const isActive = activeTab === item.id;

                return (
                  <button
                    key={item.id}
                    className={`sidebar-button ${isActive ? 'active' : ''}`}
                    onClick={() => setActiveTab(item.id)}
                    title={item.label}
                  >
                    <IconComponent size={17} className="sidebar-icon" color={isActive ? '#fb923c' : '#94a3b8'} />
                    {!isCollapsed && (
                      <>
                        <span style={{ flex: 1, marginLeft: '10px', overflow: 'hidden', textOverflow: 'ellipsis' }}>{item.label}</span>
                        {item.badge && (
                          <span
                            style={{
                              fontSize: '9px',
                              fontWeight: '800',
                              padding: '1px 6px',
                              borderRadius: '4px',
                              background: isActive ? 'rgba(251, 146, 60, 0.25)' : 'rgba(255, 255, 255, 0.08)',
                              color: isActive ? '#fed7aa' : 'var(--text-dim)',
                              border: isActive ? '1px solid rgba(251, 146, 60, 0.4)' : '1px solid transparent'
                            }}
                          >
                            {item.badge}
                          </span>
                        )}
                      </>
                    )}
                  </button>
                );
              })}
            </nav>
          </div>
        ))}
      </div>

      {/* Pinned Bottom User Card */}
      <div className="sidebar-footer-pinned">
        <div className="user-card" title="Luqman Booso - Lead Researcher (J26-SE-334)">
          <div className="user-avatar">LB</div>
          {!isCollapsed && (
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: '12px', fontWeight: '700', color: '#fff', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                Luqman Booso
              </div>
              <div style={{ fontSize: '10px', color: 'var(--text-dim)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                Lead Researcher (J26-SE-334)
              </div>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
