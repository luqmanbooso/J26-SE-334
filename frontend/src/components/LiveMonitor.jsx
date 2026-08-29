import React, { useState, useEffect } from 'react';
import { Radio, AlertTriangle, ShieldCheck, Cpu, Wifi, Smartphone, CheckCircle2, Play, Pause, Activity, RefreshCw, Terminal, Layers, Eye, ArrowRight } from 'lucide-react';
import { motion } from 'framer-motion';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

export default function LiveMonitor({ config, onInspectVision }) {
  const [isInjecting, setIsInjecting] = useState(true);
  const [logs, setLogs] = useState([
    { id: 1, time: '14:22:01', tag: 'NETEM', msg: 'Simulating packet loss 3.5% on wlan0 interface', type: 'warning' },
    { id: 2, time: '14:22:04', tag: 'ADB_SHELL', msg: 'Applied stress-ng --cpu 4 --io 2 --vm 1 --vm-bytes 256M', type: 'info' },
    { id: 3, time: '14:22:08', tag: 'VLM_ORACLE', msg: 'Screen frame captured: 0 visual defects detected', type: 'success' },
    { id: 4, time: '14:22:12', tag: 'SURFACE_FLINGER', msg: 'Frame drop detected: 14 fps lag during scroll animation', type: 'error' },
    { id: 5, time: '14:22:15', tag: 'CHAOS_INJECTOR', msg: 'Triggered battery drop notification intent (10% state)', type: 'warning' }
  ]);

  // Live Chart Data Stream
  const [telemetryData, setTelemetryData] = useState([
    { time: '0s', cpu: 42, latency: 120, ram: 55 },
    { time: '2s', cpu: 65, latency: 240, ram: 60 },
    { time: '4s', cpu: 82, latency: 850, ram: 72 },
    { time: '6s', cpu: 88, latency: 1100, ram: 78 },
    { time: '8s', cpu: 74, latency: 920, ram: 75 },
    { time: '10s', cpu: 85, latency: 1250, ram: 82 },
  ]);

  useEffect(() => {
    let interval;
    if (isInjecting) {
      interval = setInterval(() => {
        const nextTime = `${(telemetryData.length * 2)}s`;
        const nextCpu = Math.min(98, Math.max(40, Math.floor(Math.random() * 30) + 70));
        const nextLatency = Math.min(1800, Math.max(300, Math.floor(Math.random() * 800) + 700));
        const nextRam = Math.min(95, Math.max(60, Math.floor(Math.random() * 15) + 75));

        setTelemetryData(prev => {
          const updated = [...prev.slice(1), { time: nextTime, cpu: nextCpu, latency: nextLatency, ram: nextRam }];
          return updated;
        });

        // Add periodic logs
        if (Math.random() > 0.4) {
          const now = new Date().toTimeString().split(' ')[0];
          const newLog = {
            id: Date.now(),
            time: now,
            tag: Math.random() > 0.5 ? 'VLM_ORACLE' : 'NETEM_CHAOS',
            msg: Math.random() > 0.5 ? `Telemetry frame verified. Latency: ${nextLatency}ms` : `CPU throttle active: ${nextCpu}% usage`,
            type: nextCpu > 88 ? 'warning' : 'info'
          };
          setLogs(prev => [newLog, ...prev.slice(0, 15)]);
        }
      }, 1500);
    }
    return () => clearInterval(interval);
  }, [isInjecting, telemetryData]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '28px', width: '100%', maxWidth: '1280px', margin: '0 auto' }}>
      {/* Top Header Card */}
      <div className="glass-card" style={{ padding: '18px 26px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ background: 'rgba(251,146,60,0.12)', color: 'var(--accent-orange-bright)', width: '46px', height: '46px', borderRadius: '14px', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 0 16px rgba(251,146,60,0.2)' }}>
            <Radio size={24} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="pulse-beacon pulse-beacon-orange" />
              <span style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '600', textTransform: 'uppercase' }}>Live Perturbation Channel</span>
            </div>
            <h1 style={{ fontSize: '20px', fontWeight: '900', color: '#fff', marginTop: '2px' }}>
              Real-Time Chaos Injection & ADB Telemetry
            </h1>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
          <button className="btn-secondary" onClick={() => setLogs([])} style={{ padding: '8px 16px', fontSize: '12px' }}>
            <RefreshCw size={14} /> Clear Logs
          </button>
          <button className="btn-secondary" onClick={onInspectVision} style={{ padding: '8px 16px', fontSize: '12px', color: 'var(--accent-cyan-bright)' }}>
            <Eye size={14} /> Inspect Vision Oracle <ArrowRight size={13} />
          </button>
          <button className="btn-cta" onClick={() => setIsInjecting(!isInjecting)}>
            {isInjecting ? <Pause size={16} /> : <Play size={16} />}
            {isInjecting ? 'Pause Chaos Stream' : 'Resume Injection'}
          </button>
        </div>
      </div>

      {/* 4 Stat Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '18px' }}>
        <div className="glass-card stat-accent-card" style={{ padding: '24px 20px', borderTopColor: 'var(--accent-orange)' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '700', textTransform: 'uppercase' }}>CPU Load Target</div>
          <div style={{ fontSize: '34px', fontWeight: '900', color: 'var(--accent-orange-bright)', fontFamily: 'var(--font-display)', margin: '6px 0 2px' }}>
            {config?.cpuStress || 85}%
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>4 Cores Multi-threaded</div>
        </div>

        <div className="glass-card stat-accent-card" style={{ padding: '24px 20px', borderTopColor: 'var(--accent-cyan)' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '700', textTransform: 'uppercase' }}>RAM Pressure</div>
          <div style={{ fontSize: '34px', fontWeight: '900', color: 'var(--accent-cyan-bright)', fontFamily: 'var(--font-display)', margin: '6px 0 2px' }}>
            {config?.ramStress || 75}%
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>LowMemoryKiller (LMK) active</div>
        </div>

        <div className="glass-card stat-accent-card" style={{ padding: '24px 20px', borderTopColor: 'var(--accent-amber)' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '700', textTransform: 'uppercase' }}>Simulated Latency</div>
          <div style={{ fontSize: '34px', fontWeight: '900', color: '#fbbf24', fontFamily: 'var(--font-display)', margin: '6px 0 2px' }}>
            {config?.latency || 1250}<span style={{ fontSize: '14px', fontWeight: '600' }}>ms</span>
          </div>
          <div style={{ fontSize: '11px', color: '#fbbf24' }}>Netem 3G Flaky Handoff</div>
        </div>

        <div className="glass-card stat-accent-card" style={{ padding: '24px 20px', borderTopColor: 'var(--accent-green)' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '700', textTransform: 'uppercase' }}>Active Emulator</div>
          <div style={{ fontSize: '20px', fontWeight: '800', color: '#fff', margin: '14px 0 6px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Smartphone size={20} color="#10b981" /> Pixel 7 Pro
          </div>
          <div style={{ fontSize: '11px', color: '#10b981' }}>Android 14 (API 34) Online</div>
        </div>
      </div>

      {/* Real-Time Telemetry Curve */}
      <div className="glass-card" style={{ padding: '28px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
          <div className="glass-card-title" style={{ margin: 0 }}>
            <div className="icon-wrap">
              <Activity size={18} />
            </div>
            <span>Live System Stress Curves (CPU & Network Latency)</span>
          </div>
          <div style={{ display: 'flex', gap: '16px', fontSize: '12px' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#fb923c' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#fb923c' }} /> CPU (%)
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#38bdf8' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#38bdf8' }} /> Latency (ms)
            </span>
          </div>
        </div>

        <div style={{ width: '100%', height: '260px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={telemetryData}>
              <defs>
                <linearGradient id="cpuGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#fb923c" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#fb923c" stopOpacity={0.0} />
                </linearGradient>
                <linearGradient id="latencyGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#38bdf8" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="#38bdf8" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="time" stroke="#64748b" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={{ stroke: 'rgba(255,255,255,0.08)' }} />
              <YAxis stroke="#64748b" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={{ stroke: 'rgba(255,255,255,0.08)' }} />
              <Tooltip
                contentStyle={{ background: '#0e121f', border: '1px solid rgba(251,146,60,0.3)', borderRadius: '12px', color: '#fff', fontSize: '12px' }}
              />
              <Area type="monotone" dataKey="cpu" stroke="#fb923c" strokeWidth={2.5} fillOpacity={1} fill="url(#cpuGradient)" />
              <Area type="monotone" dataKey="latency" stroke="#38bdf8" strokeWidth={2} fillOpacity={1} fill="url(#latencyGradient)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Live Stream Terminal */}
      <div className="glass-card" style={{ padding: '28px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
          <div className="glass-card-title" style={{ margin: 0 }}>
            <div className="icon-wrap">
              <Terminal size={18} />
            </div>
            <span>ADB Shell Injection Terminal Output</span>
          </div>
          <span className="glow-badge glow-badge-orange" style={{ fontSize: '10px' }}>
            Streaming @ 60 FPS
          </span>
        </div>

        <div className="terminal-box" style={{ minHeight: '220px' }}>
          {logs.map((log) => (
            <div key={log.id} className="terminal-line">
              <span className="terminal-time">[{log.time}]</span>
              <span className="terminal-tag">&lt;{log.tag}&gt;</span>
              <span className={`terminal-msg ${log.type}`}>{log.msg}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
