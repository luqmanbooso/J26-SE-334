import React from 'react';
import { motion } from 'framer-motion';
import { Sliders, Cpu, Wifi, PhoneCall, Play, Zap, AlertTriangle, ShieldCheck, Flame, Layers, Radio, Sparkles } from 'lucide-react';

export default function StressProfiles({ config, setConfig, onRunTest }) {
  const presets = {
    'mid-transaction': {
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
    },
    'network-flap': {
      name: 'Network Flap & Low Memory',
      generalName: 'Network Flap Profile',
      targetModule: 'Payment API',
      cpuStress: 45,
      ramStress: 92,
      diskIo: 320,
      thermalState: 'Critical',
      networkProfile: '3G Edge / Flaky',
      latency: 3500,
      packetLoss: 8,
      dnsFailure: true,
      interruptionType: 'Memory Pressure',
      interruptions: ['Low Battery Warn', 'Memory Pressure', 'Network Handoff'],
      interruptionFreq: 8
    },
    'extreme-cpu': {
      name: 'Extreme CPU & Backgrounding',
      generalName: 'High Load Profile',
      targetModule: 'Order Submission',
      cpuStress: 98,
      ramStress: 88,
      diskIo: 950,
      thermalState: 'Critical',
      networkProfile: '4G, Slow Wifi, 5G',
      latency: 800,
      packetLoss: 5,
      dnsFailure: false,
      interruptionType: 'App Backgrounding',
      interruptions: ['Incoming Calls', 'Text Message', 'Network Handoff'],
      interruptionFreq: 6
    }
  };

  const handlePresetSelect = (presetKey) => {
    if (presets[presetKey]) {
      setConfig(presets[presetKey]);
    }
  };

  const toggleInterruption = (item) => {
    const list = config.interruptions || [];
    const updated = list.includes(item)
      ? list.filter(i => i !== item)
      : [...list, item];
    setConfig({ ...config, interruptions: updated });
  };

  // Calculate live combined chaos score
  const chaosScore = Math.min(
    99,
    Math.round(
      (config.cpuStress * 0.3) +
      (config.ramStress * 0.2) +
      (config.latency / 10000 * 25) +
      ((config.interruptions?.length || 0) * 5) +
      (config.thermalState === 'Critical' ? 15 : config.thermalState === 'Warn' ? 8 : 0)
    )
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '28px', width: '100%', maxWidth: '1280px', margin: '0 auto' }}>
      {/* Top Scenario Selector & Live Chaos Gauge */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 360px', gap: '20px' }}>
        <div className="glass-card" style={{ padding: '20px 26px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div style={{ background: 'rgba(255,87,34,0.15)', color: '#ff5722', width: '46px', height: '46px', borderRadius: '14px', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 0 20px rgba(255,87,34,0.3)' }}>
              <Sliders size={24} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span className="glow-badge glow-badge-orange" style={{ fontSize: '9px', padding: '2px 8px' }}>Component 1</span>
                <span style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '600', textTransform: 'uppercase' }}>Active Perturbation Scenario</span>
              </div>
              <select
                value={config.name === 'Mid-Transaction Stress Test' ? 'mid-transaction' : config.name === 'Network Flap & Low Memory' ? 'network-flap' : 'extreme-cpu'}
                onChange={(e) => handlePresetSelect(e.target.value)}
                className="input-styled"
                style={{ padding: '6px 0', fontSize: '18px', fontWeight: '900', color: 'var(--accent-orange-bright)', border: 'none', background: 'transparent', cursor: 'pointer', outline: 'none' }}
              >
                <option value="mid-transaction">Scenario: Mid-Transaction Stress Test</option>
                <option value="network-flap">Scenario: Network Flap & Low Memory</option>
                <option value="extreme-cpu">Scenario: Extreme CPU & Backgrounding</option>
              </select>
            </div>
          </div>

          <button className="btn-cta" onClick={onRunTest} style={{ padding: '12px 28px', fontSize: '14px' }}>
            <Play size={16} /> Deploy Chaos Test
          </button>
        </div>

        {/* Live Combined Chaos Index Score Meter */}
        <div className="glass-card stat-accent-card" style={{ padding: '18px 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderColor: chaosScore > 75 ? 'rgba(239,68,68,0.5)' : 'rgba(255,87,34,0.4)' }}>
          <div>
            <div style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Combined Chaos Score</div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', margin: '4px 0' }}>
              <span style={{ fontSize: '36px', fontWeight: '900', color: chaosScore > 75 ? '#ef4444' : 'var(--accent-orange-bright)', fontFamily: 'var(--font-display)' }}>
                {chaosScore}%
              </span>
              <span
                style={{
                  fontSize: '10px',
                  fontWeight: '700',
                  padding: '2px 8px',
                  borderRadius: '6px',
                  background: chaosScore > 75 ? 'rgba(239,68,68,0.2)' : 'rgba(255,87,34,0.2)',
                  color: chaosScore > 75 ? '#f87171' : '#ff7a45',
                  border: `1px solid ${chaosScore > 75 ? 'rgba(239,68,68,0.4)' : 'rgba(255,87,34,0.4)'}`
                }}
              >
                {chaosScore > 75 ? 'CRITICAL CHAOS' : 'HEAVY STRESS'}
              </span>
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>ADB Shell Stressor Active</div>
          </div>
          {chaosScore > 75 ? (
            <div style={{ width: '48px', height: '48px', borderRadius: '50%', background: 'rgba(239,68,68,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#ef4444', boxShadow: '0 0 20px rgba(239,68,68,0.3)' }}>
              <AlertTriangle size={28} />
            </div>
          ) : (
            <div style={{ width: '48px', height: '48px', borderRadius: '50%', background: 'rgba(255,87,34,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#ff5722', boxShadow: '0 0 20px rgba(255,87,34,0.3)' }}>
              <ShieldCheck size={28} />
            </div>
          )}
        </div>
      </div>

      {/* 2-Column Grid Layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
        {/* Left Column: General & Hardware Stress */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* General Configurations */}
          <div className="glass-card" style={{ padding: '26px' }}>
            <div className="glass-card-title" style={{ marginBottom: '18px' }}>
              <div className="icon-wrap">
                <Layers size={18} />
              </div>
              <span>General Target Module Binding</span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              <div className="form-field">
                <label>Scenario Name</label>
                <select
                  value={config.generalName || 'Payment Flow Stress'}
                  onChange={(e) => setConfig({ ...config, generalName: e.target.value })}
                  className="input-styled"
                >
                  <option>Payment Flow Stress</option>
                  <option>Network Flap Profile</option>
                  <option>High Load Profile</option>
                </select>
              </div>
              <div className="form-field">
                <label>Target Module</label>
                <select
                  value={config.targetModule || 'Checkout Service'}
                  onChange={(e) => setConfig({ ...config, targetModule: e.target.value })}
                  className="input-styled"
                >
                  <option>Checkout Service</option>
                  <option>Payment API Gateway</option>
                  <option>Order Submission</option>
                  <option>User Auth Pipeline</option>
                </select>
              </div>
            </div>
          </div>

          {/* Hardware Load Stressors */}
          <div className="glass-card" style={{ padding: '26px' }}>
            <div className="glass-card-title" style={{ marginBottom: '22px' }}>
              <div className="icon-wrap">
                <Cpu size={18} />
              </div>
              <span>Hardware Load (ADB Shell Stressor)</span>
            </div>

            <div className="form-field">
              <label>
                <span>CPU Throttling Load</span>
                <span className="val-badge">{config.cpuStress}%</span>
              </label>
              <input
                type="range"
                min="0"
                max="100"
                value={config.cpuStress}
                onChange={(e) => setConfig({ ...config, cpuStress: Number(e.target.value) })}
              />
            </div>

            <div className="form-field">
              <label>
                <span>RAM Pressure Stress</span>
                <span className="val-badge">{config.ramStress}%</span>
              </label>
              <input
                type="range"
                min="0"
                max="100"
                value={config.ramStress}
                onChange={(e) => setConfig({ ...config, ramStress: Number(e.target.value) })}
              />
            </div>

            <div className="form-field">
              <label>
                <span>Disk I/O Stress (IOPS)</span>
                <span className="val-badge">{config.diskIo} IOPS</span>
              </label>
              <input
                type="range"
                min="0"
                max="1000"
                step="50"
                value={config.diskIo}
                onChange={(e) => setConfig({ ...config, diskIo: Number(e.target.value) })}
              />
            </div>

            <div className="form-field" style={{ marginBottom: 0 }}>
              <label>Thermal State Injection:</label>
              <div className="chip-row">
                {['Normal', 'Warn', 'Critical'].map((state) => (
                  <button
                    key={state}
                    className={`chip-item ${config.thermalState === state ? 'active' : ''}`}
                    onClick={() => setConfig({ ...config, thermalState: state })}
                  >
                    <span className={`radio-dot ${config.thermalState === state ? 'active' : ''}`} />
                    {state}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Network & OS Interruptions */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Network Control */}
          <div className="glass-card" style={{ padding: '26px' }}>
            <div className="glass-card-title" style={{ marginBottom: '22px' }}>
              <div className="icon-wrap">
                <Wifi size={18} />
              </div>
              <span>Network Control (Netem / Emulator Console)</span>
            </div>

            <div className="form-field">
              <label>Network Profile</label>
              <select
                value={config.networkProfile || '4G, Slow Wifi, 5G'}
                onChange={(e) => setConfig({ ...config, networkProfile: e.target.value })}
                className="input-styled"
              >
                <option>4G, Slow Wifi, 5G</option>
                <option>3G Edge / Flaky</option>
                <option>WiFi &lt;-&gt; 4G Handover</option>
                <option>2G High Latency Tunnel</option>
              </select>
            </div>

            <div className="form-field">
              <label>
                <span>Injected Latency (ms)</span>
                <span className="val-badge">{config.latency} ms</span>
              </label>
              <input
                type="range"
                min="0"
                max="10000"
                step="100"
                value={config.latency}
                onChange={(e) => setConfig({ ...config, latency: Number(e.target.value) })}
              />
            </div>

            <div className="form-field">
              <label>
                <span>Packet Loss Rate</span>
                <span className="val-badge">{config.packetLoss}%</span>
              </label>
              <input
                type="range"
                min="0"
                max="10"
                step="0.5"
                value={config.packetLoss}
                onChange={(e) => setConfig({ ...config, packetLoss: Number(e.target.value) })}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderTop: '1px solid rgba(255,255,255,0.06)' }}>
              <div>
                <div style={{ fontSize: '13px', color: '#fff', fontWeight: '600' }}>DNS Failure Injection</div>
                <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>Simulate unreachable domain name resolution</div>
              </div>
              <input
                type="checkbox"
                checked={config.dnsFailure}
                onChange={(e) => setConfig({ ...config, dnsFailure: e.target.checked })}
                style={{ accentColor: '#ff5722', width: '20px', height: '20px', cursor: 'pointer' }}
              />
            </div>
          </div>

          {/* OS Interruptions */}
          <div className="glass-card" style={{ padding: '26px' }}>
            <div className="glass-card-title" style={{ marginBottom: '22px' }}>
              <div className="icon-wrap">
                <PhoneCall size={18} />
              </div>
              <span>OS Interruptions (Emulator GSM & AM Commands)</span>
            </div>

            <div className="form-field">
              <label>Interruption Scenario Mode</label>
              <select
                value={config.interruptionType || 'Incoming Call, Low Battery'}
                onChange={(e) => setConfig({ ...config, interruptionType: e.target.value })}
                className="input-styled"
              >
                <option>Incoming Call, Low Battery</option>
                <option>SMS / Push Notification Overlay</option>
                <option>App Backgrounding & Resume</option>
                <option>Memory Pressure Kill</option>
              </select>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '13px', color: 'var(--text-muted)', marginBottom: '12px' }}>
                Active Stress Triggers:
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                {['Incoming Calls', 'Text Message', 'Low Battery Warn', 'Memory Pressure', 'Network Handoff', 'Screen Rotate'].map((item) => {
                  const isActive = (config.interruptions || []).includes(item);
                  return (
                    <div
                      key={item}
                      onClick={() => toggleInterruption(item)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '10px',
                        fontSize: '12px',
                        color: isActive ? '#fff' : 'var(--text-muted)',
                        background: isActive ? 'rgba(255,87,34,0.14)' : 'rgba(255,255,255,0.03)',
                        border: `1px solid ${isActive ? 'rgba(255,87,34,0.4)' : 'rgba(255,255,255,0.06)'}`,
                        padding: '8px 12px',
                        borderRadius: '10px',
                        cursor: 'pointer',
                        userSelect: 'none',
                        transition: 'all 0.2s ease'
                      }}
                    >
                      <div className={`radio-dot ${isActive ? 'active' : ''}`} />
                      <span style={{ fontWeight: isActive ? '600' : '400' }}>{item}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
