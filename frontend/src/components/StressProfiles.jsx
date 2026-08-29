import React from 'react';
import { Sliders, Zap, Shield, Cpu, Wifi, Activity, Play, Layers } from 'lucide-react';
import { motion } from 'framer-motion';

export default function StressProfiles({ config, setConfig, onRunTest }) {
  const updateField = (field, value) => {
    setConfig(prev => ({ ...prev, [field]: value }));
  };

  const presetProfiles = [
    {
      name: 'Mid-Transaction Stress Test',
      generalName: 'Payment Flow Stress',
      targetModule: 'Checkout Service',
      cpuStress: 85,
      ramStress: 75,
      diskIo: 650,
      latency: 1250,
      packetLoss: 3,
      dnsFailure: true,
      thermalState: 'Warn',
      networkProfile: '4G, Slow Wifi, 5G',
      interruptionType: 'Incoming Call, Low Battery',
      interruptionFreq: 4,
      desc: 'Simulates heavy CPU throttling during asynchronous tokenization & gateway response.'
    },
    {
      name: 'Subway Network Dropout',
      generalName: 'Transit Offline Recovery',
      targetModule: 'Sync Daemon',
      cpuStress: 50,
      ramStress: 60,
      diskIo: 400,
      latency: 2800,
      packetLoss: 18,
      dnsFailure: true,
      thermalState: 'None',
      networkProfile: 'Cellular Dead Zone',
      interruptionType: 'Airplane Mode Toggle',
      interruptionFreq: 6,
      desc: 'Rapid 4G to No-Connection transitions with high packet retransmission load.'
    },
    {
      name: 'Extreme Resource Starvation',
      generalName: 'Low-End Device Emulation',
      targetModule: 'Rendering Engine',
      cpuStress: 95,
      ramStress: 90,
      diskIo: 900,
      latency: 800,
      packetLoss: 1,
      dnsFailure: false,
      thermalState: 'Critical',
      networkProfile: '2G / EDGE',
      interruptionType: 'Low Memory Kill (LMK)',
      interruptionFreq: 8,
      desc: 'High memory pressure forcing Android OS process kill & state restoration.'
    }
  ];

  // Calculated overall chaos score
  const chaosScore = Math.round((config.cpuStress * 0.4) + (config.ramStress * 0.3) + (Math.min(config.latency, 2000) / 2000 * 30));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '28px', width: '100%', maxWidth: '1280px', margin: '0 auto' }}>
      {/* Top Header Card */}
      <div className="glass-card" style={{ padding: '18px 26px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ background: 'rgba(251,146,60,0.12)', color: 'var(--accent-orange-bright)', width: '46px', height: '46px', borderRadius: '14px', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 0 16px rgba(251,146,60,0.2)' }}>
            <Sliders size={24} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '600', textTransform: 'uppercase' }}>Environmental Chaos Engine</span>
            </div>
            <h1 style={{ fontSize: '20px', fontWeight: '900', color: '#fff', marginTop: '2px' }}>
              Environmental Stress Configuration & Context Perturbation
            </h1>
          </div>
        </div>

        <button className="btn-cta" onClick={onRunTest}>
          <Play size={16} /> Deploy Stress Scenario to Emulator
        </button>
      </div>

      {/* Preset Profiles Selector */}
      <div>
        <div style={{ fontSize: '12px', color: 'var(--text-dim)', fontWeight: '700', textTransform: 'uppercase', marginBottom: '12px', letterSpacing: '0.8px' }}>
          Standard Research Perturbation Profiles
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '18px' }}>
          {presetProfiles.map((p, idx) => {
            const isSelected = config.name === p.name;
            return (
              <motion.div
                key={idx}
                whileHover={{ y: -4 }}
                onClick={() => setConfig(p)}
                className="glass-card"
                style={{
                  padding: '20px',
                  cursor: 'pointer',
                  borderColor: isSelected ? 'var(--accent-orange)' : 'var(--border-subtle)',
                  background: isSelected ? 'rgba(251,146,60,0.08)' : 'var(--bg-card)',
                  boxShadow: isSelected ? '0 0 20px rgba(251,146,60,0.18)' : 'none'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <span className="radio-dot active" style={{ opacity: isSelected ? 1 : 0.2 }} />
                  <span style={{ fontSize: '11px', color: isSelected ? 'var(--accent-orange-bright)' : 'var(--text-dim)', fontWeight: '700' }}>
                    {p.targetModule}
                  </span>
                </div>
                <h4 style={{ fontSize: '16px', fontWeight: '800', color: '#fff', marginBottom: '6px' }}>{p.name}</h4>
                <p style={{ fontSize: '12px', color: 'var(--text-muted)', lineHeight: '1.5' }}>{p.desc}</p>
              </motion.div>
            );
          })}
        </div>
      </div>

      {/* Main 2-Column Form */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '24px' }}>
        {/* Left Column: Sliders */}
        <div className="glass-card" style={{ padding: '28px' }}>
          <div className="glass-card-title" style={{ marginBottom: '22px' }}>
            <div className="icon-wrap">
              <Cpu size={18} />
            </div>
            <span>Hardware Resource Starvation Knobs</span>
          </div>

          <div className="form-field">
            <label>
              <span>CPU Stress Level</span>
              <span className="val-badge">{config.cpuStress}%</span>
            </label>
            <input
              type="range"
              min="0"
              max="100"
              value={config.cpuStress}
              onChange={(e) => updateField('cpuStress', Number(e.target.value))}
            />
          </div>

          <div className="form-field">
            <label>
              <span>RAM Pressure</span>
              <span className="val-badge">{config.ramStress}%</span>
            </label>
            <input
              type="range"
              min="0"
              max="100"
              value={config.ramStress}
              onChange={(e) => updateField('ramStress', Number(e.target.value))}
            />
          </div>

          <div className="form-field">
            <label>
              <span>Simulated Latency (Netem)</span>
              <span className="val-badge">{config.latency} ms</span>
            </label>
            <input
              type="range"
              min="0"
              max="3000"
              step="50"
              value={config.latency}
              onChange={(e) => updateField('latency', Number(e.target.value))}
            />
          </div>

          <div className="form-field" style={{ marginBottom: 0 }}>
            <label>
              <span>Packet Loss Probability</span>
              <span className="val-badge">{config.packetLoss}%</span>
            </label>
            <input
              type="range"
              min="0"
              max="25"
              value={config.packetLoss}
              onChange={(e) => updateField('packetLoss', Number(e.target.value))}
            />
          </div>
        </div>

        {/* Right Column: Chaos Gauge & Context Target */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '22px' }}>
          {/* Chaos Gauge Card */}
          <div className="glass-card stat-accent-card" style={{ padding: '28px', textAlign: 'center', borderTopColor: 'var(--accent-orange)' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '700', textTransform: 'uppercase', marginBottom: '8px' }}>
              Calculated Perturbation Severity
            </div>
            <div style={{ fontSize: '56px', fontWeight: '900', color: 'var(--accent-orange-bright)', fontFamily: 'var(--font-display)', margin: '4px 0' }}>
              {chaosScore} <span style={{ fontSize: '20px', color: 'var(--text-muted)' }}>/ 100</span>
            </div>
            <div style={{ fontSize: '12px', color: chaosScore > 75 ? '#fb7185' : '#10b981', fontWeight: '600' }}>
              {chaosScore > 75 ? 'Severe Stress (High Collision Probability)' : 'Moderate Environmental Perturbation'}
            </div>
          </div>

          {/* Module Selector */}
          <div className="glass-card" style={{ padding: '24px' }}>
            <div className="form-field" style={{ marginBottom: '14px' }}>
              <label>
                <span>Target Execution Context</span>
              </label>
              <input
                type="text"
                value={config.targetModule}
                onChange={(e) => updateField('targetModule', e.target.value)}
                className="input-styled"
              />
            </div>

            <div className="form-field" style={{ marginBottom: 0 }}>
              <label>
                <span>Thermal Throttling State</span>
              </label>
              <select
                value={config.thermalState}
                onChange={(e) => updateField('thermalState', e.target.value)}
                className="input-styled"
              >
                <option value="None">None (35°C Nominal)</option>
                <option value="Warn">Warning (60°C Throttling)</option>
                <option value="Critical">Critical (85°C Extreme Throttle)</option>
              </select>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
