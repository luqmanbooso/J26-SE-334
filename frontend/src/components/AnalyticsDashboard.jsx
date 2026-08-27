import React, { useState } from 'react';
import { Activity, ShieldAlert, Cpu, CheckCircle2, TrendingUp, Download, Smartphone, Clock, Eye, RefreshCw, Zap, Flame, BarChart3, Layers, Filter } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar, Cell } from 'recharts';
import { motion } from 'framer-motion';

export default function AnalyticsDashboard() {
  const [timeRange, setTimeRange] = useState('7d');
  const [selectedDevice, setSelectedDevice] = useState('pixel7');

  const stressExposureData = [
    { load: '10%', overlaps: 2, crashes: 0, nonFatal: 1 },
    { load: '25%', overlaps: 6, crashes: 1, nonFatal: 4 },
    { load: '40%', overlaps: 14, crashes: 2, nonFatal: 9 },
    { load: '60%', overlaps: 28, crashes: 6, nonFatal: 18 },
    { load: '75%', overlaps: 52, crashes: 14, nonFatal: 36 },
    { load: '90%', overlaps: 74, crashes: 29, nonFatal: 52 },
    { load: '100%', overlaps: 96, crashes: 52, nonFatal: 68 },
  ];

  const failureAttributionData = [
    { category: 'Network Handover', count: 48, fill: '#ff5722' },
    { category: 'CPU / Thermal', count: 36, fill: '#ff7a45' },
    { category: 'Touch Tremor', count: 28, fill: '#f59e0b' },
    { category: 'OS Interruption', count: 18, fill: '#3b82f6' },
    { category: 'Memory Pressure', count: 12, fill: '#10b981' },
  ];

  const statCards = [
    {
      title: 'Total Test Campaigns',
      value: '1,284',
      trend: '+14.2%',
      trendUp: true,
      desc: 'from last week',
      icon: TrendingUp,
      color: '#10b981',
      badge: 'Active'
    },
    {
      title: 'MTBF (Mean Time Between Failure)',
      value: '4.2',
      unit: 'hrs',
      trend: '75% load threshold',
      icon: Clock,
      color: '#ff7043',
      badge: 'Stress Limit'
    },
    {
      title: 'On-Device VLM Accuracy',
      value: '98.4%',
      desc: 'Qwen2-VL 4-bit Quantized',
      icon: CheckCircle2,
      color: '#34d399',
      badge: 'Verified'
    },
    {
      title: 'Self-Healing Repair Rate',
      value: '94.2%',
      desc: 'Sentence-BERT remapped',
      icon: RefreshCw,
      color: '#3b82f6',
      badge: 'Automated'
    }
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '28px', width: '100%', maxWidth: '1280px', margin: '0 auto' }}>
      {/* Top Filter & Intelligence Bar */}
      <div className="glass-card" style={{ padding: '18px 26px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ background: 'rgba(255,87,34,0.15)', color: '#ff5722', width: '46px', height: '46px', borderRadius: '14px', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 0 20px rgba(255,87,34,0.3)' }}>
            <Activity size={24} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="glow-badge glow-badge-orange" style={{ fontSize: '9px', padding: '2px 8px' }}>Telemetry Core</span>
              <span style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '600', textTransform: 'uppercase' }}>Framework Analytics</span>
            </div>
            <h1 style={{ fontSize: '20px', fontWeight: '900', color: '#fff', marginTop: '2px' }}>
              Robustness & Failure Attribution Intelligence
            </h1>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
          {/* Time Range Selector */}
          <div style={{ display: 'flex', gap: '4px', background: 'rgba(255,255,255,0.03)', padding: '4px', borderRadius: '24px', border: '1px solid rgba(255,255,255,0.08)' }}>
            {['24h', '7d', '30d', 'All'].map(range => (
              <button
                key={range}
                onClick={() => setTimeRange(range)}
                className={`nav-link ${timeRange === range ? 'active' : ''}`}
                style={{ padding: '5px 14px', fontSize: '12px', borderRadius: '18px' }}
              >
                {range}
              </button>
            ))}
          </div>

          {/* Device Dropdown */}
          <select
            value={selectedDevice}
            onChange={(e) => setSelectedDevice(e.target.value)}
            className="input-styled"
            style={{ width: '160px', padding: '8px 14px' }}
          >
            <option value="pixel7">Pixel 7 Pro (API 34)</option>
            <option value="s24">Samsung S24 (API 34)</option>
            <option value="pixel5">Pixel 5 (API 30)</option>
          </select>

          <button className="btn-secondary" style={{ padding: '8px 16px', fontSize: '12px' }}>
            <Download size={15} /> Export Report
          </button>
        </div>
      </div>

      {/* 4 Stat Summary Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '18px' }}>
        {statCards.map((card, i) => {
          const Icon = card.icon;
          return (
            <motion.div
              key={i}
              whileHover={{ y: -5, scale: 1.015 }}
              className="glass-card stat-accent-card"
              style={{ padding: '24px 20px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: '500' }}>{card.title}</span>
                <span
                  style={{
                    fontSize: '9px',
                    fontWeight: '700',
                    padding: '2px 8px',
                    borderRadius: '8px',
                    background: `${card.color}22`,
                    color: card.color,
                    border: `1px solid ${card.color}44`
                  }}
                >
                  {card.badge}
                </span>
              </div>

              <div style={{ margin: '14px 0 6px', display: 'flex', alignItems: 'baseline', gap: '6px' }}>
                <span style={{ fontSize: '36px', fontWeight: '900', color: '#fff', fontFamily: 'var(--font-display)', letterSpacing: '-1px' }}>
                  {card.value}
                </span>
                {card.unit && (
                  <span style={{ fontSize: '16px', color: 'var(--text-dim)', fontWeight: '600' }}>
                    {card.unit}
                  </span>
                )}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: card.trendUp ? '#10b981' : 'var(--text-dim)', fontWeight: '600' }}>
                <Icon size={14} color={card.color} />
                <span>{card.trend || card.desc}</span>
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* Row 2 Charts Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: '22px' }}>
        {/* Stress Intensity vs Failure Exposure Area Chart */}
        <div className="glass-card" style={{ padding: '26px' }}>
          <div className="glass-card-header">
            <div className="glass-card-title">
              <div className="icon-wrap">
                <ShieldAlert size={18} />
              </div>
              <span>Stress Intensity vs Failure Exposure Rate</span>
            </div>
            <div style={{ display: 'flex', gap: '16px', fontSize: '11px', color: 'var(--text-muted)' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#ff5722', boxShadow: '0 0 8px #ff5722' }} /> GUI Collisions
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#ef4444', boxShadow: '0 0 8px #ef4444' }} /> Fatal Crashes
              </span>
            </div>
          </div>

          <div style={{ height: '260px', width: '100%', marginTop: '10px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={stressExposureData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorOverlaps" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ff5722" stopOpacity={0.45} />
                    <stop offset="95%" stopColor="#ff5722" stopOpacity={0.0} />
                  </linearGradient>
                  <linearGradient id="colorCrashes" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ef4444" stopOpacity={0.5} />
                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="load" stroke="#64748b" fontSize={11} tickLine={false} />
                <YAxis stroke="#64748b" fontSize={11} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0a0a12',
                    borderRadius: '14px',
                    border: '1px solid rgba(255,87,34,0.4)',
                    boxShadow: '0 8px 30px rgba(0,0,0,0.8)',
                    color: '#fff',
                    fontSize: '12px'
                  }}
                />
                <Area type="monotone" dataKey="overlaps" stroke="#ff5722" strokeWidth={2.5} fillOpacity={1} fill="url(#colorOverlaps)" name="GUI Collisions" />
                <Area type="monotone" dataKey="crashes" stroke="#ef4444" strokeWidth={2.5} fillOpacity={1} fill="url(#colorCrashes)" name="Fatal Crashes" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Failure Attribution Bar Chart */}
        <div className="glass-card" style={{ padding: '26px' }}>
          <div className="glass-card-header">
            <div className="glass-card-title">
              <div className="icon-wrap">
                <BarChart3 size={18} />
              </div>
              <span>Failure Attribution Breakdown</span>
            </div>
            <span className="glow-badge glow-badge-orange" style={{ fontSize: '10px' }}>5 Categories</span>
          </div>

          <div style={{ height: '260px', width: '100%', marginTop: '10px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={failureAttributionData} layout="vertical" margin={{ top: 10, right: 20, left: 10, bottom: 0 }}>
                <XAxis type="number" stroke="#64748b" fontSize={11} tickLine={false} />
                <YAxis dataKey="category" type="category" stroke="#94a3b8" fontSize={11} width={120} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0a0a12',
                    borderRadius: '14px',
                    border: '1px solid rgba(255,87,34,0.4)',
                    boxShadow: '0 8px 30px rgba(0,0,0,0.8)',
                    color: '#fff',
                    fontSize: '12px'
                  }}
                />
                <Bar dataKey="count" radius={[0, 8, 8, 0]}>
                  {failureAttributionData.map((entry, index) => (
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
