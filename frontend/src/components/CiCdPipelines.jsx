import React, { useState } from 'react';
import { GitBranch, GitPullRequest, CheckCircle2, RefreshCw, Zap, ArrowRight, ShieldCheck, Play, Layers, Terminal, Clock, Activity } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export default function CiCdPipelines() {
  const [isRunning, setIsRunning] = useState(false);
  const [activeStage, setActiveStage] = useState(4);

  const handleRunPipeline = () => {
    setIsRunning(true);
    setActiveStage(1);
    setTimeout(() => setActiveStage(2), 1100);
    setTimeout(() => setActiveStage(3), 2300);
    setTimeout(() => setActiveStage(4), 3600);
    setTimeout(() => setIsRunning(false), 4800);
  };

  const stages = [
    {
      id: 1,
      name: 'PR Trigger & Build',
      desc: 'GitHub Actions triggers automated build matrix on Pixel 7 (API 34) emulator.',
      duration: '42s',
      tag: 'STAGE 01',
      color: '#38bdf8'
    },
    {
      id: 2,
      name: 'Chaos Perturbation',
      desc: 'Perturbation Engine applies netem latency, packet loss, and CPU load during UI navigation.',
      duration: '1m 15s',
      tag: 'STAGE 02',
      color: '#fb923c'
    },
    {
      id: 3,
      name: 'On-Device VLM Oracle',
      desc: 'Qwen2-VL scans screen frames for layout collisions, text overflows, and clipping.',
      duration: '54s',
      tag: 'STAGE 03',
      color: '#a78bfa'
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
          <div style={{ background: 'rgba(251,146,60,0.12)', color: 'var(--accent-orange-bright)', width: '46px', height: '46px', borderRadius: '14px', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 0 16px rgba(251,146,60,0.2)' }}>
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
          {isRunning ? 'Simulating Pipeline Flow...' : 'Trigger CI/CD Simulation'}
        </button>
      </div>

      {/* Interactive 4-Stage Pipeline Graph with Connected Data Cable */}
      <div style={{ position: 'relative' }}>
        {/* Animated Connecting Data Cable Stream */}
        <div style={{ position: 'absolute', top: '50%', left: '8%', right: '8%', height: '2px', transform: 'translateY(-50%)', zIndex: 0, pointerEvents: 'none' }}>
          <svg width="100%" height="10" style={{ overflow: 'visible' }}>
            <line
              x1="0"
              y1="5"
              x2="100%"
              y2="5"
              stroke={isRunning ? '#fb923c' : 'rgba(255,255,255,0.1)'}
              strokeWidth="2"
              className={isRunning ? 'flow-stream-line' : ''}
            />
          </svg>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '20px', position: 'relative', zIndex: 1 }}>
          {stages.map((stage) => {
            const isPassed = activeStage >= stage.id;
            const isCurrent = isRunning && activeStage === stage.id;

            return (
              <motion.div
                key={stage.id}
                whileHover={{ y: -6, scale: 1.02 }}
                animate={isCurrent ? { scale: [1, 1.03, 1], transition: { repeat: Infinity, duration: 1.2 } } : {}}
                className={`glass-card stat-accent-card ${isCurrent ? 'shimmer-active' : ''}`}
                style={{
                  padding: '26px 20px',
                  borderTopColor: isCurrent ? 'var(--accent-orange)' : isPassed ? stage.color : 'var(--border-subtle)',
                  background: isCurrent ? 'rgba(251,146,60,0.14)' : 'var(--bg-card)',
                  boxShadow: isCurrent ? '0 0 30px rgba(251,146,60,0.35)' : 'none',
                  transition: 'all 0.3s ease'
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

                <h4 style={{ fontSize: '17px', fontWeight: '800', margin: '4px 0 10px', color: '#fff' }}>
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
          <div style={{ color: '#fb923c' }}>name: HEART Robustness Pipeline</div>
          <div style={{ color: '#cbd5e1' }}>on: [push, pull_request]</div>
          <br />
          <div style={{ color: '#fb923c' }}>jobs:</div>
          <div style={{ paddingLeft: '16px', color: '#cbd5e1' }}>robustness-gate:</div>
          <div style={{ paddingLeft: '32px', color: '#cbd5e1' }}>runs-on: ubuntu-latest</div>
          <div style={{ paddingLeft: '32px', color: '#cbd5e1' }}>steps:</div>
          <div style={{ paddingLeft: '48px', color: '#64748b' }}>- uses: actions/checkout@v4</div>
          <div style={{ paddingLeft: '48px', color: '#38bdf8' }}>- name: Run HEART Chaos & Vision Oracle</div>
          <div style={{ paddingLeft: '64px', color: '#cbd5e1' }}>run: |</div>
          <div style={{ paddingLeft: '80px', color: '#34d399' }}>pip install heart-testing-framework</div>
          <div style={{ paddingLeft: '80px', color: '#34d399' }}>heart-test run --apk ./app-release.apk --oracle on-device-vlm --auto-heal</div>
        </div>
      </div>
    </div>
  );
}
