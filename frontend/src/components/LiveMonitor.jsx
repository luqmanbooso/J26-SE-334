import React, { useState, useEffect } from 'react';
import { Radio, AlertTriangle, Cpu, Wifi, Play, Pause, Smartphone, RefreshCw, Volume2, ShieldAlert, Terminal, Sparkles, Activity, Zap, Flame } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { motion } from 'framer-motion';

export default function LiveMonitor({ config }) {
  const [isStreaming, setIsStreaming] = useState(true);
  const [speedMultiplier, setSpeedMultiplier] = useState(1);
  const [activeAlert, setActiveAlert] = useState('Low Battery Warning: Injected level 10%');
  const [logs, setLogs] = useState([
    { time: '14:22:01', tag: 'APP', msg: 'Navigating to CheckoutScreen', type: 'info' },
    { time: '14:22:02', tag: 'ENGINE', msg: "Semantic trigger 'Mid-Transaction' reached.", type: 'warning' },
    { time: '14:22:02', tag: 'INJECTOR', msg: 'Executing tc qdisc: 4G -> 3G Flaky Handover [SUCCESS]', type: 'error' },
    { time: '14:22:03', tag: 'INJECTOR', msg: 'Forcing Battery Level to 10% via dumpsys battery set level 10 [SUCCESS]', type: 'error' },
    { time: '14:22:04', tag: 'MONITOR', msg: 'UI thread frame render time spiked to 850ms (>16ms limit)', type: 'warning' },
    { time: '14:22:05', tag: 'VISION_ORACLE', msg: 'Qwen2-VL frame inspection: OVERFLOW_Y_COLLISION detected at submit button', type: 'error' }
  ]);

  const [telemetry, setTelemetry] = useState([
    { time: '00:00', bandwidth: 12, cpu: 45, latency: 150, memory: 310 },
    { time: '00:05', bandwidth: 8, cpu: 65, latency: 280, memory: 350 },
    { time: '00:10', bandwidth: 4, cpu: 78, latency: 540, memory: 420 },
    { time: '00:15', bandwidth: 1.2, cpu: 92, latency: 1250, memory: 580 },
    { time: '00:20', bandwidth: 0.5, cpu: 85, latency: 890, memory: 510 },
    { time: '00:25', bandwidth: 3.5, cpu: 60, latency: 340, memory: 440 },
  ]);

  // Live streaming log simulation loop
  useEffect(() => {
    let interval;
    if (isStreaming) {
      interval = setInterval(() => {
        const now = new Date();
        const timeStr = now.toTimeString().split(' ')[0];
        const sampleLogs = [
          { tag: 'ADB_SHELL', msg: 'Executing tc qdisc add dev wlan0 root netem delay 1200ms loss 5%', type: 'info' },
          { tag: 'BIOMECHANICS', msg: 'Applied Fitts Law spatial Gaussian distortion (dx: +16px, dy: -9px)', type: 'warning' },
          { tag: 'VLM_ORACLE', msg: 'Quantized Qwen2-VL frame screenshot analysis: OVERFLOW_Y_COLLISION (94% conf)', type: 'error' },
          { tag: 'SELF_HEALING', msg: 'Sentence-BERT locator repair candidate found: //android.widget.Button[@text="SUBMIT"] (sim: 0.942)', type: 'success' },
          { tag: 'PERF_SINK', msg: 'Memory pressure am com-memory-pressure -> GC_CONCURRENT (24MB freed)', type: 'info' }
        ];
        const randomLog = sampleLogs[Math.floor(Math.random() * sampleLogs.length)];
        setLogs(prev => [...prev.slice(-16), { time: timeStr, ...randomLog }]);

        // Random telemetry variation
        setTelemetry(prev => {
          const lastTime = prev[prev.length - 1]?.time || '00:30';
          const newCpu = Math.min(99, Math.max(30, Math.floor(Math.random() * 30) + 65));
          const newLatency = Math.min(2500, Math.max(100, Math.floor(Math.random() * 800) + 600));
          return [...prev.slice(-7), { time: timeStr.slice(3, 8), bandwidth: +(Math.random() * 4).toFixed(1), cpu: newCpu, latency: newLatency }];
        });
      }, 2400 / speedMultiplier);
    }
    return () => clearInterval(interval);
  }, [isStreaming, speedMultiplier]);

  const triggerChaosEvent = (type) => {
    const now = new Date().toTimeString().split(' ')[0];
    if (type === 'call') {
      setActiveAlert('INCOMING CALL: +1 (555) 019-2834');
      setLogs(prev => [...prev, { time: now, tag: 'OS_INTERRUPT', msg: 'Injected GSM incoming call overlay via emulator console (gsm call +15550192834)', type: 'error' }]);
    } else if (type === 'memory') {
      setActiveAlert('MEMORY PRESSURE: am com-memory-pressure CRITICAL');
      setLogs(prev => [...prev, { time: now, tag: 'ADB_MEMORY', msg: 'Forced RAM stress to 94% -> LowMemoryKiller invoked', type: 'error' }]);
    } else if (type === 'wifi') {
      setActiveAlert('NETWORK HANDOVER: 4G LTE -> 3G Flaky');
      setLogs(prev => [...prev, { time: now, tag: 'NET_FLAP', msg: 'Toggled network packet loss to 8% and added 3500ms latency', type: 'warning' }]);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '28px', width: '100%', maxWidth: '1280px', margin: '0 auto' }}>
      {/* Top Bar */}
      <div className="glass-card" style={{ padding: '18px 26px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ background: 'rgba(255,87,34,0.15)', color: '#ff5722', width: '46px', height: '46px', borderRadius: '14px', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 0 20px rgba(255,87,34,0.3)' }}>
            <Radio size={24} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="pulse-beacon pulse-beacon-green" />
              <span style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '600', textTransform: 'uppercase' }}>Live Execution & Telemetry</span>
            </div>
            <h1 style={{ fontSize: '20px', fontWeight: '900', color: '#fff', marginTop: '2px' }}>
              Real-Time ADB Stream & Android Device Preview
            </h1>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', gap: '4px', background: 'rgba(255,255,255,0.03)', padding: '4px', borderRadius: '24px', border: '1px solid rgba(255,255,255,0.08)' }}>
            {[1, 2, 5].map(speed => (
              <button
                key={speed}
                onClick={() => setSpeedMultiplier(speed)}
                className={`nav-link ${speedMultiplier === speed ? 'active' : ''}`}
                style={{ padding: '5px 12px', fontSize: '12px', borderRadius: '18px' }}
              >
                {speed}x
              </button>
            ))}
          </div>

          <button className="btn-cta" onClick={() => setIsStreaming(!isStreaming)}>
            {isStreaming ? <Pause size={16} /> : <Play size={16} />}
            {isStreaming ? 'Pause Stream' : 'Resume Live Stream'}
          </button>
        </div>
      </div>

      {/* Grid Layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.35fr 1fr', gap: '24px' }}>
        {/* Left Column: Live Terminal Stream & Recharts Telemetry Cards */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Terminal Box */}
          <div className="glass-card" style={{ padding: '26px' }}>
            <div className="glass-card-header">
              <div className="glass-card-title">
                <div className="icon-wrap">
                  <Terminal size={18} />
                </div>
                <span>Live ADB & Perturbation Stream</span>
              </div>
              <span className="glow-badge glow-badge-green" style={{ fontSize: '10px' }}>
                <span className="pulse-beacon pulse-beacon-green" style={{ width: '6px', height: '6px' }} />
                Real-Time Telemetry
              </span>
            </div>

            <div className="terminal-box" style={{ minHeight: '230px' }}>
              {logs.map((log, idx) => (
                <div key={idx} className="terminal-line">
                  <span className="terminal-time">[{log.time}]</span>
                  <span className="terminal-tag">{log.tag}:</span>
                  <span className={`terminal-msg ${log.type}`}>{log.msg}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Telemetry Metrics Grid */}
          <div className="glass-card" style={{ padding: '26px' }}>
            <div className="glass-card-title" style={{ marginBottom: '20px' }}>
              <div className="icon-wrap">
                <Cpu size={18} />
              </div>
              <span>Real-Time Telemetry Waveforms</span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '20px' }}>
              <div style={{ background: 'rgba(255,87,34,0.08)', border: '1px solid rgba(255,87,34,0.25)', borderRadius: '14px', padding: '16px' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '600', textTransform: 'uppercase' }}>Network Bandwidth</div>
                <div style={{ fontSize: '26px', fontWeight: '900', color: 'var(--accent-orange-bright)', fontFamily: 'var(--font-display)', marginTop: '4px' }}>
                  1.2 <span style={{ fontSize: '14px', color: 'var(--text-muted)' }}>Mbps</span>
                </div>
              </div>

              <div style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.25)', borderRadius: '14px', padding: '16px' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '600', textTransform: 'uppercase' }}>CPU Load / Temp</div>
                <div style={{ fontSize: '26px', fontWeight: '900', color: '#f87171', fontFamily: 'var(--font-display)', marginTop: '4px' }}>
                  82°C <span style={{ fontSize: '14px', color: 'var(--text-muted)' }}>(85% load)</span>
                </div>
              </div>
            </div>

            <div style={{ height: '160px', width: '100%' }}>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={telemetry} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorLatency" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#ff5722" stopOpacity={0.5} />
                      <stop offset="95%" stopColor="#ff5722" stopOpacity={0.0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="time" stroke="#64748b" fontSize={11} tickLine={false} />
                  <YAxis stroke="#64748b" fontSize={11} tickLine={false} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0a0a12',
                      borderRadius: '12px',
                      border: '1px solid rgba(255,87,34,0.4)',
                      color: '#fff',
                      fontSize: '12px'
                    }}
                  />
                  <Area type="monotone" dataKey="latency" stroke="#ff5722" strokeWidth={2.5} fillOpacity={1} fill="url(#colorLatency)" name="UI Latency (ms)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* Right Column: 3D Mobile Device Frame with Interactive Chaos Injector Triggers */}
        <div className="glass-card" style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '26px' }}>
          <div style={{ fontSize: '15px', fontWeight: '800', color: '#fff', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Smartphone size={18} color="var(--accent-orange-bright)" />
            <span>Active Pixel 7 Pro Preview</span>
          </div>

          {/* Interactive Trigger Buttons */}
          <div style={{ display: 'flex', gap: '8px', marginBottom: '20px', flexWrap: 'wrap', justifyContent: 'center' }}>
            <button className="btn-secondary" onClick={() => triggerChaosEvent('call')} style={{ padding: '7px 14px', fontSize: '11px' }}>
              + Injected Call
            </button>
            <button className="btn-secondary" onClick={() => triggerChaosEvent('memory')} style={{ padding: '7px 14px', fontSize: '11px' }}>
              + RAM Stress
            </button>
            <button className="btn-secondary" onClick={() => triggerChaosEvent('wifi')} style={{ padding: '7px 14px', fontSize: '11px' }}>
              + 3G Flap
            </button>
          </div>

          {/* 3D Mobile Device Frame */}
          <div className="phone-device-3d" style={{ borderColor: '#1c1c24' }}>
            <div className="phone-dynamic-island" />
            <div className="phone-viewport" style={{ background: '#09090e' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#94a3b8', marginBottom: '14px', position: 'relative', zIndex: 20 }}>
                <span>10:09</span>
                <span style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                  <Wifi size={12} color="#f59e0b" />
                  <span style={{ fontSize: '10px', color: '#f59e0b', fontWeight: '700' }}>3G FLAKY</span>
                </span>
              </div>

              {/* Dynamic Alert Banner */}
              <div style={{ background: 'rgba(239, 68, 68, 0.16)', border: '1px solid rgba(239, 68, 68, 0.45)', borderRadius: '12px', padding: '10px 14px', fontSize: '11px', color: '#fca5a5', display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px', textAlign: 'left', lineHeight: '1.3' }}>
                <AlertTriangle size={16} color="#ef4444" style={{ flexShrink: 0 }} />
                <span>{activeAlert}</span>
              </div>

              {/* Checkout Screen Content with Spinning Loader */}
              <div style={{ textAlign: 'left', margin: '8px 0' }}>
                <h3 style={{ fontSize: '20px', fontWeight: '900', color: '#fff' }}>Checkout</h3>
                <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '2px' }}>Order Confirmation Flow</div>
              </div>

              {/* Spinning Orange Loader Circle */}
              <div style={{ margin: '22px auto', width: '52px', height: '52px', borderRadius: '50%', border: '4px solid rgba(255,87,34,0.2)', borderTopColor: '#ff5722', animation: 'spin 1s linear infinite' }} />

              <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '14px', padding: '14px', marginTop: 'auto', textAlign: 'left' }}>
                <div style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-muted)', marginBottom: '8px', textTransform: 'uppercase' }}>Order Summary</div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-dim)' }}>
                  <span>Subtotal</span>
                  <span>$110.00</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-dim)', margin: '4px 0' }}>
                  <span>Shipping fees</span>
                  <span>$9.99</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '14px', fontWeight: '900', color: '#fff', marginTop: '8px', borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '8px' }}>
                  <span>Total</span>
                  <span>$119.99</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
