import React, { useState } from 'react';
import { GitBranch, GitPullRequest, CheckCircle2, RefreshCw, Zap, ArrowRight, ShieldCheck, Play, Sparkles, Layers, Terminal, Clock } from 'lucide-react';
import { motion } from 'framer-motion';

export default function CiCdPipelines() {
  const [isRunning, setIsRunning] = useState(false);
  const [activeStage, setActiveStage] = useState(4);

  const handleRunPipeline = () => {
    setIsRunning(true);
    setActiveStage(1);
    const timers = [
      setTimeout(() => setActiveStage(2), 1000),
      setTimeout(() => setActiveStage(3), 2200),
      setTimeout(() => setActiveStage(4), 3500),
      setTimeout(() => setIsRunning(false), 4500)
    ];
  };

  const stages = [
    {
      id: 1,
      name: 'PR Trigger & Build',
      desc: 'GitHub Actions triggers automated build matrix on Pixel 7 (API 34) emulator.',
      duration: '42s',
      tag: 'STAGE 01',
      color: '#3b82f6'
    },
    {
      id: 2,
      name: 'Chaos Perturbation',
      desc: 'Perturbation Engine applies netem latency, packet loss, and CPU load during UI navigation.',
      duration: '1m 15s',
      tag: 'STAGE 02',
      color: '#ff5722'
    },
    {
      id: 3,
      name: 'On-Device VLM Oracle',
      desc: 'Qwen2-VL scans screen frames for layout collisions, text overflows, and clipping.',
      duration: '54s',
      tag: 'STAGE 03',
      color: '#8b5cf6'
    },
    {
      id: 4,
      name: 'Self-Healing Patch',
      desc: 'Sentence-BERT repairs broken DOM selectors and opens auto-verified regression PR.',
      duration: '18s',
      tag: 'STAGE 04',
      color: '#10b981'
    }
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '28px', width: '100%', maxWidth: '1280px', margin: '0 auto' }}>
      {/* Header */}
      <div className="glass-card" style={{ padding: '18px 26px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ background: 'rgba(255,87,34,0.15)', color: '#ff5722', width: '46px', height: '46px', borderRadius: '14px', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 0 20px rgba(255,87,34,0.3)' }}>
            <GitBranch size={24} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="glow-badge glow-badge-orange" style={{ fontSize: '9px', padding: '2px 8px' }}>Continuous Testing</span>
              <span style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '600', textTransform: 'uppercase' }}>Automated DevOps Pipeline</span>
            </div>
            <h1 style={{ fontSize: '20px', fontWeight: '900', color: '#fff', marginTop: '2px' }}>
              CI/CD & Self-Healing TDD Regression Pipeline
            </h1>
          </div>
        </div>

        <button className="btn-cta" onClick={handleRunPipeline} disabled={isRunning}>
          {isRunning ? <RefreshCw size={16} className="spin" /> : <Play size={16} />}
          {isRunning ? 'Running Pipeline Simulation...' : 'Trigger CI/CD Simulation'}
        </button>
      </div>

      {/* Interactive 4-Stage Pipeline Graph */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '20px', position: 'relative' }}>
        {stages.map((stage) => {
          const isPassed = activeStage >= stage.id;
          const isCurrent = isRunning && activeStage === stage.id;

          return (
            <motion.div
              key={stage.id}
              whileHover={{ y: -5, scale: 1.015 }}
              className="glass-card stat-accent-card"
              style={{
                padding: '26px 20px',
                borderColor: isCurrent ? 'var(--accent-orange)' : isPassed ? 'rgba(16,185,129,0.3)' : 'var(--border-subtle)',
                background: isCurrent ? 'rgba(255,87,34,0.1)' : 'var(--bg-card)',
                boxShadow: isCurrent ? '0 0 30px rgba(255,87,34,0.3)' : 'none'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                <span
                  style={{
                    fontSize: '10px',
                    fontWeight: '800',
                    color: isPassed ? stage.color : 'var(--text-dim)',
                    background: `${stage.color}18`,
                    padding: '3px 8px',
                    borderRadius: '6px',
                    border: `1px solid ${stage.color}33`
                  }}
                >
                  {stage.tag}
                </span>
                {isPassed ? (
                  <CheckCircle2 size={16} color={stage.color} />
                ) : (
                  <Clock size={16} color="var(--text-dim)" />
                )}
              </div>

              <h4 style={{ fontSize: '18px', fontWeight: '800', margin: '4px 0 10px', color: '#fff' }}>
                {stage.name}
              </h4>
              <p style={{ fontSize: '12px', color: 'var(--text-muted)', lineHeight: '1.6', marginBottom: '18px' }}>
                {stage.desc}
              </p>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '12px', borderTop: '1px solid rgba(255,255,255,0.06)', fontSize: '11px', color: 'var(--text-dim)' }}>
                <span>Duration</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontWeight: '700', color: '#fff' }}>{stage.duration}</span>
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* GitHub Actions Configuration Preview Card */}
      <div className="glass-card" style={{ padding: '28px' }}>
        <div className="glass-card-header">
          <div className="glass-card-title">
            <div className="icon-wrap">
              <Terminal size={18} />
            </div>
            <span>GitHub Actions Workflow Configuration (.github/workflows/heart-ci.yml)</span>
          </div>
          <span className="glow-badge glow-badge-orange" style={{ fontSize: '10px' }}>
            Production Ready
          </span>
        </div>

        <div className="code-window">
          <div style={{ color: '#64748b' }}># Continuous Robustness Verification & Regression Patch Bot</div>
          <div style={{ color: '#f472b6' }}>name: HEART Robustness Pipeline</div>
          <div style={{ color: '#e2e8f0' }}>on: [push, pull_request]</div>
          <br />
          <div style={{ color: '#f472b6' }}>jobs:</div>
          <div style={{ paddingLeft: '16px', color: '#e2e8f0' }}>robustness-gate:</div>
          <div style={{ paddingLeft: '32px', color: '#e2e8f0' }}>runs-on: ubuntu-latest</div>
          <div style={{ paddingLeft: '32px', color: '#e2e8f0' }}>steps:</div>
          <div style={{ paddingLeft: '48px', color: '#64748b' }}>- uses: actions/checkout@v4</div>
          <div style={{ paddingLeft: '48px', color: '#38bdf8' }}>- name: Run HEART Chaos & Vision Oracle</div>
          <div style={{ paddingLeft: '64px', color: '#e2e8f0' }}>run: |</div>
          <div style={{ paddingLeft: '80px', color: '#34d399' }}>pip install heart-testing-framework</div>
          <div style={{ paddingLeft: '80px', color: '#34d399' }}>heart-test run --apk ./app-release.apk --oracle on-device-vlm --auto-heal</div>
        </div>
      </div>
    </div>
  );
}
