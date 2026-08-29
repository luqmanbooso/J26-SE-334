import React from 'react';
import { Activity, ShieldCheck, AlertTriangle, RefreshCw, Cpu, Layers, TrendingUp, CheckCircle2 } from 'lucide-react';
import { motion } from 'framer-motion';
import { AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell, ResponsiveContainer, XAxis, YAxis, Tooltip } from 'recharts';

export default function AnalyticsDashboard() {
  const anomalyData = [
    { name: 'UI Overlap', count: 18, fill: '#fb923c' },
    { name: 'Text Clipping', count: 12, fill: '#38bdf8' },
    { name: 'Occlusion', count: 7, fill: '#8b5cf6' },
    { name: 'Z-Index Drift', count: 9, fill: '#10b981' },
    { name: 'ANR Lag', count: 4, fill: '#fb7185' }
  ];

  const timeSeriesReproducibility = [
    { run: 'Run 1', monkey: 14, heart: 48 },
    { run: 'Run 2', monkey: 18, heart: 62 },
    { run: 'Run 3', monkey: 12, heart: 78 },
    { run: 'Run 4', monkey: 22, heart: 88 },
    { run: 'Run 5', monkey: 25, heart: 94 },
    { run: 'Run 6', monkey: 20, heart: 98 },
  ];

  const pieData = [
    { name: 'Auto-Healed (S-BERT)', value: 68, color: '#10b981' },
    { name: 'Flagged by VLM Oracle', value: 24, color: '#fb923c' },
    { name: 'Manual Review', value: 8, color: '#38bdf8' }
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '28px', width: '100%', maxWidth: '1280px', margin: '0 auto' }}>
      {/* Top Header Card */}
      <div className="glass-card" style={{ padding: '18px 26px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ background: 'rgba(251,146,60,0.12)', color: 'var(--accent-orange-bright)', width: '46px', height: '46px', borderRadius: '14px', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 0 16px rgba(251,146,60,0.2)' }}>
            <Activity size={24} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '600', textTransform: 'uppercase' }}>Intelligence & Telemetry</span>
            </div>
            <h1 style={{ fontSize: '20px', fontWeight: '900', color: '#fff', marginTop: '2px' }}>
              Robustness Analytics & Benchmark Intelligence
            </h1>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <span className="glow-badge glow-badge-green" style={{ fontSize: '11px' }}>
            <CheckCircle2 size={13} /> 52 Crash Bugs Benchmark Synced
          </span>
        </div>
      </div>

      {/* 4 Stat Overview Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '18px' }}>
        <div className="glass-card stat-accent-card" style={{ padding: '24px 20px', borderTopColor: 'var(--accent-orange)' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '700', textTransform: 'uppercase' }}>Chaos Vulnerability Rate</div>
          <div style={{ fontSize: '36px', fontWeight: '900', color: 'var(--accent-orange-bright)', fontFamily: 'var(--font-display)', margin: '6px 0 2px' }}>
            38.4%
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>+24% vs Vanilla Monkey Testing</div>
        </div>

        <div className="glass-card stat-accent-card" style={{ padding: '24px 20px', borderTopColor: 'var(--accent-green)' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '700', textTransform: 'uppercase' }}>Self-Healing Resolution</div>
          <div style={{ fontSize: '36px', fontWeight: '900', color: '#34d399', fontFamily: 'var(--font-display)', margin: '6px 0 2px' }}>
            94.2%
          </div>
          <div style={{ fontSize: '11px', color: '#10b981' }}>Sentence-BERT Cosine Remapping</div>
        </div>

        <div className="glass-card stat-accent-card" style={{ padding: '24px 20px', borderTopColor: 'var(--accent-cyan)' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '700', textTransform: 'uppercase' }}>On-Device VLM Latency</div>
          <div style={{ fontSize: '36px', fontWeight: '900', color: '#38bdf8', fontFamily: 'var(--font-display)', margin: '6px 0 2px' }}>
            312<span style={{ fontSize: '14px', fontWeight: '600' }}>ms</span>
          </div>
          <div style={{ fontSize: '11px', color: '#38bdf8' }}>4-bit AWQ Quantized Qwen2-VL</div>
        </div>

        <div className="glass-card stat-accent-card" style={{ padding: '24px 20px', borderTopColor: '#a78bfa' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '700', textTransform: 'uppercase' }}>Evaluated Dataset Screens</div>
          <div style={{ fontSize: '36px', fontWeight: '900', color: '#a78bfa', fontFamily: 'var(--font-display)', margin: '6px 0 2px' }}>
            72,000+
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Rico Mobile Ground Truth</div>
        </div>
      </div>

      {/* 2-Column Analytics Charts */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '24px' }}>
        {/* Left Chart: Time Series Comparison (HEART vs Monkey) */}
        <div className="glass-card" style={{ padding: '28px' }}>
          <div className="glass-card-title" style={{ marginBottom: '22px' }}>
            <div className="icon-wrap">
              <TrendingUp size={18} />
            </div>
            <span>Bug Reproduction Efficiency (% Success vs Trial Cycles)</span>
          </div>

          <div style={{ width: '100%', height: '270px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={timeSeriesReproducibility}>
                <defs>
                  <linearGradient id="heartGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#fb923c" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#fb923c" stopOpacity={0.0} />
                  </linearGradient>
                  <linearGradient id="monkeyGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#64748b" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#64748b" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="run" stroke="#64748b" tick={{ fill: '#64748b', fontSize: 11 }} />
                <YAxis stroke="#64748b" tick={{ fill: '#64748b', fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: '#0e121f', border: '1px solid rgba(251,146,60,0.3)', borderRadius: '12px', color: '#fff', fontSize: '12px' }}
                />
                <Area type="monotone" dataKey="heart" name="HEART Framework" stroke="#fb923c" strokeWidth={3} fillOpacity={1} fill="url(#heartGradient)" />
                <Area type="monotone" dataKey="monkey" name="Standard Monkey Test" stroke="#64748b" strokeWidth={1.5} fillOpacity={1} fill="url(#monkeyGradient)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div style={{ display: 'flex', justifyContent: 'center', gap: '24px', fontSize: '12px', marginTop: '12px' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#fb923c', fontWeight: '600' }}>
              <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#fb923c' }} /> HEART Framework (Ours)
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#94a3b8' }}>
              <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#64748b' }} /> Android Monkey (Baseline)
            </span>
          </div>
        </div>

        {/* Right Chart: Anomaly Distribution */}
        <div className="glass-card" style={{ padding: '28px' }}>
          <div className="glass-card-title" style={{ marginBottom: '22px' }}>
            <div className="icon-wrap">
              <AlertTriangle size={18} />
            </div>
            <span>Detected Non-Crash GUI Anomalies (By Category)</span>
          </div>

          <div style={{ width: '100%', height: '270px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={anomalyData} layout="vertical">
                <XAxis type="number" stroke="#64748b" tick={{ fill: '#64748b', fontSize: 11 }} />
                <YAxis dataKey="name" type="category" stroke="#64748b" tick={{ fill: '#cbd5e1', fontSize: 11 }} width={100} />
                <Tooltip
                  contentStyle={{ background: '#0e121f', border: '1px solid rgba(251,146,60,0.3)', borderRadius: '12px', color: '#fff', fontSize: '12px' }}
                />
                <Bar dataKey="count" radius={[0, 6, 6, 0]}>
                  {anomalyData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}
