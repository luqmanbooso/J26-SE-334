import React, { useState } from 'react';
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
import { Activity, LayoutDashboard, Sliders, Radio, Eye, FileText, Smartphone } from 'lucide-react';

export default function App() {
  const [activeTab, setActiveTab] = useState('landing');

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

  const handleLaunchDashboard = (targetView = 'dashboard') => {
    setActiveTab(targetView);
  };

  const pageVariants = {
    initial: { opacity: 0, y: 14, filter: 'blur(3px)' },
    animate: { opacity: 1, y: 0, filter: 'blur(0px)', transition: { duration: 0.32, ease: [0.16, 1, 0.3, 1] } },
    exit: { opacity: 0, y: -10, filter: 'blur(2px)', transition: { duration: 0.18, ease: 'easeIn' } }
  };

  const navMenuItems = [
    { id: 'landing', label: 'Overview' },
    { id: 'dashboard', label: 'Analytics' },
    { id: 'app-integration', label: 'App Integration' },
    { id: 'profiles', label: 'Stress Profiles' },
    { id: 'human-stress', label: 'Biomechanical' },
    { id: 'live', label: 'Live Monitor' },
    { id: 'vision', label: 'Vision Debugger' },
    { id: 'attribution', label: 'Attribution' },
  ];

  return (
    <div className="app-shell">
      {/* Interactive Glowing Cursor */}
      <CustomCursor />

      {/* Animated Ambient Background & Floating Soft Orbs */}
      <div className="ambient-bg" />
      <div className="ambient-orb ambient-orb-1" />
      <div className="ambient-orb ambient-orb-2" />

      {/* Top Frosted Navbar */}
      <header className="navbar">
        <div className="nav-brand" onClick={() => setActiveTab('landing')}>
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
          {navMenuItems.map((item) => (
            <button
              key={item.id}
              className={`nav-link ${activeTab === item.id ? 'active' : ''}`}
              onClick={() => setActiveTab(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <div style={{ display: 'flex', gap: '14px', alignItems: 'center' }}>
          <button className="btn-cta" onClick={() => handleLaunchDashboard('dashboard')}>
            <Activity size={15} /> Demo Workspace
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <AnimatePresence mode="wait">
        {activeTab === 'landing' ? (
          <motion.div key="landing" variants={pageVariants} initial="initial" animate="animate" exit="exit" style={{ width: '100%' }}>
            <LandingPage onLaunchDashboard={handleLaunchDashboard} />
          </motion.div>
        ) : (
          <motion.div key="workspace" variants={pageVariants} initial="initial" animate="animate" exit="exit" className="workspace-container">
            <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} />
            <main className="main-content">
              <AnimatePresence mode="wait">
                <motion.div key={activeTab} variants={pageVariants} initial="initial" animate="animate" exit="exit" style={{ width: '100%' }}>
                  {activeTab === 'dashboard' && <AnalyticsDashboard />}
                  {activeTab === 'app-integration' && <AppIntegration />}
                  {activeTab === 'profiles' && <StressProfiles config={stressConfig} setConfig={setStressConfig} onRunTest={() => setActiveTab('live')} />}
                  {activeTab === 'human-stress' && <HumanStressProfiler />}
                  {activeTab === 'live' && <LiveMonitor config={stressConfig} onInspectVision={() => setActiveTab('vision')} />}
                  {activeTab === 'vision' && <VisionDebugger onGoToAttribution={() => setActiveTab('attribution')} />}
                  {activeTab === 'attribution' && <AttributionReport onDeployCiCd={() => setActiveTab('cicd')} onViewAnalytics={() => setActiveTab('dashboard')} />}
                  {activeTab === 'executions' && <TestExecutions />}
                  {activeTab === 'cicd' && <CiCdPipelines />}
                  {activeTab === 'benchmarks' && <BenchmarkApps />}
                </motion.div>
              </AnimatePresence>
            </main>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Workspace Status Footer */}
      {activeTab !== 'landing' && (
        <footer>
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
      )}
    </div>
  );
}
