import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import LandingPage from './components/LandingPage';
import Sidebar from './components/Sidebar';
import AnalyticsDashboard from './components/AnalyticsDashboard';
import StressProfiles from './components/StressProfiles';
import HumanStressProfiler from './components/HumanStressProfiler';
import AppIntegration from './components/AppIntegration';
import LiveMonitor from './components/LiveMonitor';
import VisionDebugger from './components/VisionDebugger';
import AttributionReport from './components/AttributionReport';
import TestExecutions from './components/TestExecutions';
import CiCdPipelines from './components/CiCdPipelines';
import BenchmarkApps from './components/BenchmarkApps';
import CustomCursor from './components/CustomCursor';
import AuthModal from './components/AuthModal';
import {
  Activity, ArrowLeft, ChevronRight, User, LogOut, LogIn,
  Shield, CheckCircle2, Home, Sliders, Radio, Eye, FileText, Smartphone
} from 'lucide-react';

export default function App() {
  // Hash-based routing to support browser Back and Forward buttons
  const getInitialTab = () => {
    const hash = window.location.hash.replace('#', '');
    return hash || 'landing';
  };

  const [activeTab, setActiveTab] = useState(getInitialTab);
  const [historyStack, setHistoryStack] = useState(['landing']);
  const mainContentRef = useRef(null);

  // Authentication State with persistent localStorage session
  const [user, setUser] = useState(() => {
    try {
      const saved = localStorage.getItem('heart_auth_user');
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [authModalMode, setAuthModalMode] = useState('login');
  const [showUserDropdown, setShowUserDropdown] = useState(false);

  // Synchronize browser history and hash changes
  useEffect(() => {
    const handleHashChange = () => {
      const currentHash = window.location.hash.replace('#', '') || 'landing';
      setActiveTab(currentHash);
      if (mainContentRef.current) {
        mainContentRef.current.scrollTo({ top: 0, behavior: 'smooth' });
      }
      window.scrollTo({ top: 0, behavior: 'smooth' });
    };
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  // Navigate with history tracking and smooth top scroll
  const navigateTo = (tab) => {
    if (tab !== activeTab) {
      setHistoryStack((prev) => [...prev, activeTab]);
      window.location.hash = tab === 'landing' ? '' : tab;
      setActiveTab(tab);
      if (mainContentRef.current) {
        mainContentRef.current.scrollTo({ top: 0, behavior: 'smooth' });
      }
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  // Backwards navigation using browser history and history stack fallback
  const goBack = () => {
    if (window.history.length > 1) {
      window.history.back();
    } else if (historyStack.length > 0) {
      const prevTab = historyStack[historyStack.length - 1];
      setHistoryStack((prev) => prev.slice(0, -1));
      navigateTo(prevTab);
    } else {
      navigateTo('landing');
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('heart_auth_user');
    setUser(null);
    setShowUserDropdown(false);
  };

  const [stressConfig, setStressConfig] = useState({
    name: 'Mid-Transaction Stress Test',
    generalName: 'Payment Flow Stress',
    targetModule: 'Checkout Service',
    cpuStress: 85,
    ramStress: 75,
    diskIo: 650,
    thermalState: 'Warn',
    networkProfile: '4G, Slow Wifi, 5G',
    latency: 1250,
    packetLoss: 3,
    dnsFailure: true,
    interruptionType: 'Incoming Call, Low Battery',
    interruptions: ['Incoming Calls', 'Low Battery Warn', 'Memory Pressure', 'Network Handoff'],
    interruptionFreq: 4
  });

  const pageVariants = {
    initial: { opacity: 0, y: 8 },
    animate: { opacity: 1, y: 0, transition: { duration: 0.22, ease: 'easeOut' } },
    exit: { opacity: 0, y: -6, transition: { duration: 0.14, ease: 'easeIn' } }
  };

  const navMenuItems = [
    { id: 'landing', label: 'Overview', match: ['landing'] },
    { id: 'dashboard', label: 'Testing Core', match: ['dashboard', 'app-integration', 'profiles', 'human-stress'] },
    { id: 'live', label: 'Visual Oracles & AI', match: ['live', 'vision', 'attribution'] },
    { id: 'executions', label: 'DevOps Matrix', match: ['executions', 'cicd', 'benchmarks'] },
  ];

  const getTabTitle = (tab) => {
    const titles = {
      'landing': 'Overview',
      'dashboard': 'Analytics Dashboard',
      'app-integration': 'Connect Target Application',
      'profiles': 'Environmental Chaos Engine',
      'human-stress': 'Human Stress Profiler',
      'live': 'Live Perturbation Channel',
      'vision': 'Vision-Language Oracle',
      'attribution': 'Self-Healing Synthesizer',
      'executions': 'Test Execution History',
      'cicd': 'CI/CD Matrix',
      'benchmarks': 'Themis & Rico Benchmarks'
    };
    return titles[tab] || 'Workspace';
  };

  return (
    <div className="app-shell">
      {/* Interactive Glowing Cursor */}
      <CustomCursor />

      {/* Auth Modal */}
      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        initialMode={authModalMode}
        onAuthSuccess={(authData) => setUser(authData)}
      />

      {/* Animated Ambient Background */}
      <div className="ambient-bg" />
      <div className="ambient-orb ambient-orb-1" />
      <div className="ambient-orb ambient-orb-2" />

      {/* Top Frosted Navbar */}
      <header className="navbar">
        <div className="nav-brand" onClick={() => navigateTo('landing')} style={{ cursor: 'pointer' }}>
          <div className="brand-badge-glow">
            <img
              src="/logo_white.png"
              alt="HEART Logo"
              style={{
                height: '42px',
                width: 'auto',
                maxHeight: '42px',
                objectFit: 'contain',
                filter: 'drop-shadow(0 0 10px rgba(251, 146, 60, 0.35))'
              }}
            />
          </div>
        </div>

        <nav className="nav-menu">
          {navMenuItems.map((item) => {
            const isActive = item.match.includes(activeTab);
            return (
              <button
                key={item.id}
                className={`nav-link ${isActive ? 'active' : ''}`}
                onClick={() => navigateTo(item.id)}
              >
                {item.label}
              </button>
            );
          })}
        </nav>

        {/* Right Nav: Auth + Demo Workspace Button */}
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          {user ? (
            <div style={{ position: 'relative' }}>
              <button
                onClick={() => setShowUserDropdown(!showUserDropdown)}
                className="btn-outline"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '6px 14px',
                  borderRadius: '12px',
                  borderColor: 'rgba(251, 146, 60, 0.4)',
                  background: 'rgba(251, 146, 60, 0.08)'
                }}
              >
                <div style={{
                  width: '26px',
                  height: '26px',
                  borderRadius: '50%',
                  background: 'var(--accent-orange)',
                  color: '#000',
                  fontWeight: '900',
                  fontSize: '11px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                  {user.name.charAt(0)}
                </div>
                <div style={{ textAlign: 'left', lineHeight: 1.2 }}>
                  <div style={{ fontSize: '12px', fontWeight: '800', color: '#fff' }}>
                    {user.name.split(' ')[0]}
                  </div>
                  <div style={{ fontSize: '9px', color: 'var(--accent-orange-bright)', fontWeight: '700' }}>
                    {user.studentId || user.role}
                  </div>
                </div>
              </button>

              {/* User Dropdown */}
              <AnimatePresence>
                {showUserDropdown && (
                  <motion.div
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 6 }}
                    className="glass-card"
                    style={{
                      position: 'absolute',
                      right: 0,
                      top: '115%',
                      width: '220px',
                      padding: '12px',
                      borderRadius: '14px',
                      zIndex: 1000,
                      border: '1px solid rgba(251, 146, 60, 0.3)',
                      boxShadow: '0 12px 32px rgba(0,0,0,0.5)'
                    }}
                  >
                    <div style={{ padding: '6px 8px 10px', borderBottom: '1px solid rgba(255,255,255,0.08)', marginBottom: '8px' }}>
                      <div style={{ fontSize: '13px', fontWeight: '800', color: '#fff' }}>{user.name}</div>
                      <div style={{ fontSize: '11px', color: 'var(--text-dim)', overflow: 'hidden', textOverflow: 'ellipsis' }}>{user.email}</div>
                      <span style={{
                        display: 'inline-block',
                        marginTop: '4px',
                        fontSize: '9px',
                        padding: '1px 6px',
                        borderRadius: '6px',
                        background: 'rgba(251, 146, 60, 0.2)',
                        color: 'var(--accent-orange-bright)',
                        fontWeight: '700'
                      }}>
                        {user.role}
                      </span>
                    </div>

                    <button
                      onClick={handleLogout}
                      style={{
                        width: '100%',
                        padding: '8px 10px',
                        borderRadius: '8px',
                        border: 'none',
                        background: 'rgba(244, 63, 94, 0.1)',
                        color: '#fb7185',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        fontSize: '12px',
                        fontWeight: '700'
                      }}
                    >
                      <LogOut size={14} /> Sign Out
                    </button>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          ) : (
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                className="btn-outline"
                onClick={() => { setAuthModalMode('login'); setIsAuthModalOpen(true); }}
                style={{ padding: '8px 14px', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}
              >
                <LogIn size={13} /> Sign In
              </button>
              <button
                className="btn-secondary"
                onClick={() => { setAuthModalMode('signup'); setIsAuthModalOpen(true); }}
                style={{ padding: '8px 14px', fontSize: '12px' }}
              >
                Register
              </button>
            </div>
          )}

          <button className="btn-cta" onClick={() => navigateTo('dashboard')} style={{ padding: '8px 16px', fontSize: '13px' }}>
            <Activity size={14} /> Demo Workspace
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <AnimatePresence mode="wait">
        {activeTab === 'landing' ? (
          <motion.div key="landing" variants={pageVariants} initial="initial" animate="animate" exit="exit" style={{ width: '100%' }}>
            <LandingPage onLaunchDashboard={navigateTo} />
          </motion.div>
        ) : (
          <motion.div key="workspace" variants={pageVariants} initial="initial" animate="animate" exit="exit" className="workspace-container">
            <Sidebar activeTab={activeTab} setActiveTab={navigateTo} user={user} />

            <main ref={mainContentRef} className="main-content">
              {/* Workspace Top Navigation Bar & Backwards Button */}
              <div className="workspace-nav-bar">
                <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                  <button onClick={goBack} className="btn-back-nav" title="Navigate to previous page (Alt + Left)">
                    <ArrowLeft size={14} />
                    <span>Back</span>
                  </button>

                  <div className="breadcrumb-trail">
                    <span onClick={() => navigateTo('landing')} style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Home size={12} /> Overview
                    </span>
                    <ChevronRight size={12} />
                    <span onClick={() => navigateTo('dashboard')} style={{ cursor: 'pointer' }}>Workspace</span>
                    <ChevronRight size={12} />
                    <span className="active">{getTabTitle(activeTab)}</span>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', color: 'var(--text-dim)' }}>
                  <span>Press Back or use browser arrows</span>
                </div>
              </div>

              {/* Active Tab Router */}
              <AnimatePresence mode="wait">
                <motion.div key={activeTab} variants={pageVariants} initial="initial" animate="animate" exit="exit" style={{ width: '100%', minHeight: 'calc(100vh - 240px)' }}>
                  {activeTab === 'dashboard' && <AnalyticsDashboard />}
                  {activeTab === 'app-integration' && <AppIntegration />}
                  {activeTab === 'profiles' && <StressProfiles config={stressConfig} setConfig={setStressConfig} onRunTest={() => navigateTo('live')} />}
                  {activeTab === 'human-stress' && <HumanStressProfiler />}
                  {activeTab === 'live' && <LiveMonitor config={stressConfig} onInspectVision={() => navigateTo('vision')} />}
                  {activeTab === 'vision' && <VisionDebugger onGoToAttribution={() => navigateTo('attribution')} />}
                  {activeTab === 'attribution' && <AttributionReport onDeployCiCd={() => navigateTo('cicd')} onViewAnalytics={() => navigateTo('dashboard')} />}
                  {activeTab === 'executions' && <TestExecutions onReRunTest={() => navigateTo('profiles')} />}
                  {activeTab === 'cicd' && <CiCdPipelines />}
                  {activeTab === 'benchmarks' && <BenchmarkApps />}
                </motion.div>
              </AnimatePresence>

              {/* Workspace Status Footer at the bottom of scroll stream */}
              <footer style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: '16px', padding: '16px 28px', marginTop: '48px', width: '100%' }}>
                <div style={{ maxWidth: '1240px', margin: '0 auto', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <img src="/logo_white.png" alt="Logo" style={{ width: '22px', height: '22px', filter: 'drop-shadow(0 0 6px rgba(251, 146, 60, 0.3))' }} />
                    <span style={{ fontWeight: '700', color: '#fff' }}>Project ID: J26-SE-334</span>
                    <span style={{ color: 'var(--text-dim)' }}>•</span>
                    <span style={{ color: 'var(--text-muted)' }}>SST Software Systems & Technologies Research</span>
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-dim)' }}>
                    <span>Human Behavior-Aware Robustness Testing Framework © 2026</span>
                  </div>
                </div>
              </footer>
            </main>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
