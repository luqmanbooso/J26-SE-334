import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowUpRight, ArrowRight, ChevronDown, CheckCircle2, Zap, Shield, Activity, Terminal, Layers, RefreshCw, Smartphone, Cpu, Eye, GitBranch, Database, ShieldAlert, CpuIcon } from 'lucide-react';
import ThreeHeroCanvas from './ThreeHeroCanvas';

export default function LandingPage({ onLaunchDashboard }) {
  const [activeFaq, setActiveFaq] = useState(null);
  const [deployMode, setDeployMode] = useState('manual');

  const faqs = [
    {
      q: "How does this differ from Appium or Android Monkey?",
      a: "While tools like Monkey generate random blind events, HEART operationalizes validated biomechanical motor models (Fitts's Law) and applies cognitive stress-conditioned spatial distortion at the execution level with on-device Vision-Language Oracles."
    },
    {
      q: "Does the Vision Oracle require an active cloud connection?",
      a: "No! It utilizes a compact 4-bit/8-bit AWQ quantized Qwen2-VL Vision-Language Model running completely on-device, eliminating cloud latency and protecting sensitive application telemetry."
    },
    {
      q: "How are broken test scripts repaired automatically?",
      a: "Production Crashlytics & Sentry logs are ingested by Self-Healing Synthesis, leveraging Sentence-BERT semantic embeddings to repair outdated DOM locator targets into executable Appium regression suites."
    },
    {
      q: "Is it completely open-source and free to evaluate?",
      a: "Yes, the framework is an academic research project (IT4010 / J26-SE-334) developed under SLIIT Software Systems & Technologies research group with full open-access benchmarks."
    }
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', width: '100%', position: 'relative', overflowX: 'hidden' }}>
      {/* Background Ambient Diagonal Ray Assets */}
      <div className="diagonal-ray-left" />
      <div className="diagonal-ray-right" />

      {/* Hero Section with Interactive Three.js 3D Background */}
      <section style={{ minHeight: '88vh', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', padding: '100px 24px 80px', textAlign: 'center', maxWidth: '1180px', margin: '0 auto', position: 'relative', width: '100%' }}>
        {/* Three.js 3D WebGL Canvas Layer */}
        <ThreeHeroCanvas />

        <div style={{ position: 'relative', zIndex: 3, maxWidth: '960px' }}>

          {/* Hero Title */}
          <motion.h1
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.65, delay: 0.1 }}
            style={{ fontSize: '72px', fontWeight: '900', letterSpacing: '-2.5px', lineHeight: '1.04', marginBottom: '24px' }}
          >
            Automate <span style={{ background: 'linear-gradient(135deg, #fed7aa 0%, #fb923c 50%, #f97316 100%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>Chaos</span>.<br />
            Ensure Flawless Reliability.
          </motion.h1>

          {/* Hero Subtitle */}
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            style={{ fontSize: '18px', color: 'var(--text-muted)', maxWidth: '780px', margin: '0 auto 42px', lineHeight: '1.65', fontWeight: '400' }}
          >
            A unified, zero-SDK testing framework integrating real-world environmental perturbation, biomechanical stress modeling, on-device visual oracles, and self-healing telemetry synthesis.
          </motion.p>

          {/* Action Buttons */}
          <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.3 }}
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '18px', marginBottom: '70px', flexWrap: 'wrap' }}
          >
            <button className="btn-cta" onClick={() => onLaunchDashboard('dashboard')} style={{ padding: '14px 36px', fontSize: '14px' }}>
              <Activity size={18} /> Launch Demo Workspace
            </button>
            <button className="btn-secondary" onClick={() => onLaunchDashboard('profiles')} style={{ padding: '14px 32px', fontSize: '14px' }}>
              <Terminal size={18} /> Explore Perturbation Suite
            </button>
          </motion.div>

          {/* 3 Metric Stats Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '24px', maxWidth: '960px', margin: '0 auto' }}>
            <motion.div
              whileHover={{ y: -8, scale: 1.03 }}
              transition={{ type: 'spring', stiffness: 300 }}
              className="glass-card stat-accent-card"
              style={{ padding: '28px 20px', textAlign: 'center', borderTopColor: 'var(--accent-orange)' }}
            >
              <div style={{ fontSize: '11px', color: 'var(--accent-orange-bright)', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px' }}>
                Crash Bugs Reproduced
              </div>
              <div style={{ fontSize: '46px', fontWeight: '900', color: '#fff', fontFamily: 'var(--font-display)' }}>
                52+
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-dim)', marginTop: '4px' }}>Themis Benchmark Suite</div>
            </motion.div>

            <motion.div
              whileHover={{ y: -8, scale: 1.03 }}
              transition={{ type: 'spring', stiffness: 300 }}
              className="glass-card stat-accent-card"
              style={{ padding: '28px 20px', textAlign: 'center', borderTopColor: 'var(--accent-cyan)' }}
            >
              <div style={{ fontSize: '11px', color: 'var(--accent-cyan-bright)', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px' }}>
                UI Screens Analyzed
              </div>
              <div style={{ fontSize: '46px', fontWeight: '900', color: '#fff', fontFamily: 'var(--font-display)' }}>
                72K+
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-dim)', marginTop: '4px' }}>Rico Dataset Ground Truth</div>
            </motion.div>

            <motion.div
              whileHover={{ y: -8, scale: 1.03 }}
              transition={{ type: 'spring', stiffness: 300 }}
              className="glass-card stat-accent-card"
              style={{ padding: '28px 20px', textAlign: 'center', borderTopColor: 'var(--accent-green)' }}
            >
              <div style={{ fontSize: '11px', color: 'var(--accent-green-bright)', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px' }}>
                Tested Mobile Apps
              </div>
              <div style={{ fontSize: '46px', fontWeight: '900', color: '#fff', fontFamily: 'var(--font-display)' }}>
                9.7K+
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-dim)', marginTop: '4px' }}>F-Droid & Commercial APKs</div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* Section 2: Designed for Real-World Environments */}
      <section style={{ padding: '90px 24px 70px', maxWidth: '1140px', margin: '0 auto', width: '100%', position: 'relative' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '48px', flexWrap: 'wrap', gap: '20px' }}>
          <div>
            <span className="glow-badge glow-badge-orange" style={{ marginBottom: '14px' }}>Core 4-Pillar Architecture</span>
            <h2 style={{ fontSize: '46px', fontWeight: '900', lineHeight: '1.12' }}>
              Designed for Real-<br />World Environments.<br />
              Powered by <span style={{ color: 'var(--accent-orange-bright)' }}>Vision AI</span>.
            </h2>
          </div>
          <div style={{ padding: '10px' }}>
            <div className="hologram-orb-container">
              <div className="hologram-core" />
              <div className="hologram-ring hologram-ring-1" />
              <div className="hologram-ring hologram-ring-2" />
              <div className="hologram-ring hologram-ring-3" />
            </div>
          </div>
        </div>

        {/* 4 Feature Module Cards */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
          <motion.div
            whileHover={{ y: -6, scale: 1.01 }}
            className="glass-card interactive-hover"
            onClick={() => onLaunchDashboard('profiles')}
            style={{ cursor: 'pointer', padding: '32px' }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '22px' }}>
              <p style={{ fontSize: '13px', color: 'var(--text-muted)', maxWidth: '82%', lineHeight: '1.6' }}>
                Orchestrates dynamic network handovers (4G/3G/WiFi), CPU throttling, memory leaks, and battery drops aligned to target UI flows.
              </p>
              <div style={{ width: '40px', height: '40px', borderRadius: '50%', background: 'linear-gradient(135deg, #fb923c, #ea580c)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', boxShadow: '0 0 16px rgba(251,146,60,0.35)' }}>
                <ArrowUpRight size={18} />
              </div>
            </div>
            <div>
              <h3 style={{ fontSize: '22px', fontWeight: '800', color: '#fff' }}>Context-Aware Perturbation</h3>
            </div>
          </motion.div>

          <motion.div
            whileHover={{ y: -6, scale: 1.01 }}
            className="glass-card interactive-hover"
            onClick={() => onLaunchDashboard('human-stress')}
            style={{ cursor: 'pointer', padding: '32px' }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '22px' }}>
              <p style={{ fontSize: '13px', color: 'var(--text-muted)', maxWidth: '82%', lineHeight: '1.6' }}>
                Simulates erratic swiping velocity, tremors, and missed touch targets parameterized by cognitive frustration and urgency states.
              </p>
              <div style={{ width: '40px', height: '40px', borderRadius: '50%', background: 'linear-gradient(135deg, #fb923c, #ea580c)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', boxShadow: '0 0 16px rgba(251,146,60,0.35)' }}>
                <ArrowUpRight size={18} />
              </div>
            </div>
            <div>
              <h3 style={{ fontSize: '22px', fontWeight: '800', color: '#fff' }}>Human Stress Interaction</h3>
            </div>
          </motion.div>

          <motion.div
            whileHover={{ y: -6, scale: 1.01 }}
            className="glass-card interactive-hover"
            onClick={() => onLaunchDashboard('vision')}
            style={{ cursor: 'pointer', padding: '32px' }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '22px' }}>
              <p style={{ fontSize: '13px', color: 'var(--text-muted)', maxWidth: '82%', lineHeight: '1.6' }}>
                Detects non-crash layout overlaps, text clipping, and occlusion anomalies using a lightweight on-device 4-bit quantized Qwen2-VL model.
              </p>
              <div style={{ width: '40px', height: '40px', borderRadius: '50%', background: 'linear-gradient(135deg, #38bdf8, #0284c7)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', boxShadow: '0 0 16px rgba(56,189,248,0.35)' }}>
                <ArrowUpRight size={18} />
              </div>
            </div>
            <div>
              <h3 style={{ fontSize: '22px', fontWeight: '800', color: '#fff' }}>Vision-Semantic Oracle</h3>
            </div>
          </motion.div>

          <motion.div
            whileHover={{ y: -6, scale: 1.01 }}
            className="glass-card interactive-hover"
            onClick={() => onLaunchDashboard('attribution')}
            style={{ cursor: 'pointer', padding: '32px' }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '22px' }}>
              <p style={{ fontSize: '13px', color: 'var(--text-muted)', maxWidth: '82%', lineHeight: '1.6' }}>
                Correlates production crash logs with environmental states, repairing broken locators using Sentence-BERT embeddings into executable scripts.
              </p>
              <div style={{ width: '40px', height: '40px', borderRadius: '50%', background: 'linear-gradient(135deg, #10b981, #059669)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', boxShadow: '0 0 16px rgba(16,185,129,0.35)' }}>
                <ArrowUpRight size={18} />
              </div>
            </div>
            <div>
              <h3 style={{ fontSize: '22px', fontWeight: '800', color: '#fff' }}>Self-Healing Synthesis</h3>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Section 3: 4-Step Sequence Timeline with Connecting Flow Cables */}
      <section style={{ padding: '80px 24px', maxWidth: '1140px', margin: '0 auto', width: '100%', textAlign: 'center', position: 'relative' }}>
        <span className="glow-badge glow-badge-orange" style={{ marginBottom: '14px' }}>Autonomous Workflow</span>
        <h2 style={{ fontSize: '38px', fontWeight: '900', marginBottom: '48px' }}>From Chaos Injection to Auto-Repair</h2>

        <div style={{ position: 'relative', marginBottom: '50px' }}>
          {/* Animated Connecting Data Cable Stream */}
          <div style={{ position: 'absolute', top: '50%', left: '8%', right: '8%', height: '2px', transform: 'translateY(-50%)', zIndex: 0, pointerEvents: 'none' }}>
            <svg width="100%" height="10" style={{ overflow: 'visible' }}>
              <line
                x1="0"
                y1="5"
                x2="100%"
                y2="5"
                stroke="#fb923c"
                strokeWidth="2"
                className="flow-stream-line"
                style={{ opacity: 0.6 }}
              />
            </svg>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '20px', position: 'relative', zIndex: 1 }}>
            {/* Step 1 */}
            <motion.div
              whileHover={{ y: -6, scale: 1.02 }}
              className="glass-card"
              style={{ textAlign: 'left', padding: '24px', borderTop: '2px solid var(--accent-orange)' }}
            >
              <span className="glow-badge glow-badge-orange" style={{ fontSize: '10px', marginBottom: '10px' }}>Stage 01</span>
              <div style={{ fontSize: '24px', fontWeight: '900', color: '#fff', marginBottom: '8px' }}>Inject Chaos</div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', lineHeight: '1.55' }}>
                Systematically trigger network flapping, thermal strain, and OS interruptions.
              </div>
            </motion.div>

            {/* Step 2 */}
            <motion.div
              whileHover={{ y: -6, scale: 1.02 }}
              className="glass-card"
              style={{ textAlign: 'left', padding: '24px', borderTop: '2px solid var(--accent-amber)' }}
            >
              <span className="glow-badge glow-badge-orange" style={{ fontSize: '10px', marginBottom: '10px' }}>Stage 02</span>
              <div style={{ fontSize: '24px', fontWeight: '900', color: '#fff', marginBottom: '8px' }}>Stress Motor</div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', lineHeight: '1.55' }}>
                Generate biomechanical spatial tremor and rapid frantic swipe trajectories.
              </div>
            </motion.div>

            {/* Step 3 */}
            <motion.div
              whileHover={{ y: -6, scale: 1.02 }}
              className="glass-card"
              style={{ textAlign: 'left', padding: '24px', borderTop: '2px solid var(--accent-cyan)' }}
            >
              <span className="glow-badge glow-badge-cyan" style={{ fontSize: '10px', marginBottom: '10px' }}>Stage 03</span>
              <div style={{ fontSize: '24px', fontWeight: '900', color: '#fff', marginBottom: '8px' }}>Detect Bugs</div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', lineHeight: '1.55' }}>
                Qwen2-VL visual oracle identifies UI collision and overlap defects on-device.
              </div>
            </motion.div>

            {/* Step 4 */}
            <motion.div
              whileHover={{ y: -6, scale: 1.02 }}
              className="glass-card"
              style={{ textAlign: 'left', padding: '24px', borderTop: '2px solid var(--accent-green)' }}
            >
              <span className="glow-badge glow-badge-green" style={{ fontSize: '10px', marginBottom: '10px' }}>Stage 04</span>
              <div style={{ fontSize: '24px', fontWeight: '900', color: '#10b981', marginBottom: '8px' }}>Self-Heal</div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', lineHeight: '1.55' }}>
                Sentence-BERT repairs broken DOM selectors and synthesizes regression scripts.
              </div>
            </motion.div>
          </div>
        </div>

        <button className="btn-cta" onClick={() => onLaunchDashboard('live')} style={{ padding: '12px 32px', fontSize: '14px', margin: '0 auto' }}>
          Explore Live Telemetry Stream <ArrowRight size={16} />
        </button>
      </section>

      {/* Section 4: Framework Deployment Modes */}
      <section style={{ padding: '80px 24px', maxWidth: '1140px', margin: '0 auto', width: '100%', textAlign: 'center' }}>
        <h2 style={{ fontSize: '42px', fontWeight: '900', marginBottom: '12px' }}>Choose Framework Deployment Mode</h2>
        <p style={{ fontSize: '14px', color: 'var(--text-muted)', maxWidth: '700px', margin: '0 auto 36px', lineHeight: '1.6' }}>
          Deploy the HEART testing suite across your dev lifecycle — from standalone local debugging to automated GitHub Actions CI/CD.
        </p>

        <div style={{ display: 'inline-flex', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '30px', padding: '5px', marginBottom: '48px' }}>
          <button
            className={`nav-link ${deployMode === 'manual' ? 'active' : ''}`}
            onClick={() => setDeployMode('manual')}
            style={{ borderRadius: '24px', padding: '8px 24px', fontSize: '13px' }}
          >
            Manual Execution
          </button>
          <button
            className={`nav-link ${deployMode === 'automated' ? 'active' : ''}`}
            onClick={() => setDeployMode('automated')}
            style={{ borderRadius: '24px', padding: '8px 24px', fontSize: '13px' }}
          >
            Automated Pipeline
          </button>
        </div>

        {/* 3 Deployment Mode Cards */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '24px', alignItems: 'center' }}>
          {/* Card 1 */}
          <div className="glass-card" style={{ padding: '36px 26px', textAlign: 'left' }}>
            <span className="glow-badge glow-badge-blue" style={{ fontSize: '10px', marginBottom: '12px' }}>Local Sandbox</span>
            <h3 style={{ fontSize: '28px', fontWeight: '900', margin: '8px 0 16px' }}>On-Device</h3>
            <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '24px', lineHeight: '1.6' }}>
              Ideal for immediate emulator testing and targeted environmental perturbation runs.
            </p>
            <div style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '700', textTransform: 'uppercase', marginBottom: '12px' }}>Features Included</div>
            <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '12px', color: 'var(--text-body)', marginBottom: '32px' }}>
              <li style={{ display: 'flex', gap: '8px', alignItems: 'center' }}><CheckCircle2 size={15} color="#38bdf8" /> Local Emulator Streaming</li>
              <li style={{ display: 'flex', gap: '8px', alignItems: 'center' }}><CheckCircle2 size={15} color="#38bdf8" /> ADB Chaos Stressor Suite</li>
              <li style={{ display: 'flex', gap: '8px', alignItems: 'center' }}><CheckCircle2 size={15} color="#38bdf8" /> Biomechanical Motor Controls</li>
            </ul>
            <button className="btn-secondary" onClick={() => onLaunchDashboard('profiles')} style={{ width: '100%', borderRadius: '24px' }}>
              Initialize Sandbox
            </button>
          </div>

          {/* Card 2 (Middle Elevated Glowing Card) */}
          <div className="glass-card" style={{ background: 'linear-gradient(180deg, rgba(32, 24, 38, 0.85), rgba(16, 22, 38, 0.95))', border: '1px solid rgba(251, 146, 60, 0.4)', padding: '42px 28px', textAlign: 'left', transform: 'scale(1.03)', boxShadow: '0 0 35px rgba(251,146,60,0.2)' }}>
            <span className="glow-badge glow-badge-orange" style={{ fontSize: '10px', marginBottom: '12px' }}>Most Recommended</span>
            <h3 style={{ fontSize: '32px', fontWeight: '900', margin: '8px 0 16px', color: '#fff' }}>Automated CI</h3>
            <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '24px', lineHeight: '1.6' }}>
              Closed-loop continuous integration triggered on every Pull Request build.
            </p>
            <div style={{ fontSize: '11px', color: 'var(--accent-orange-bright)', fontWeight: '700', textTransform: 'uppercase', marginBottom: '12px' }}>Everything in Sandbox, Plus:</div>
            <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '12px', color: '#fff', marginBottom: '32px' }}>
              <li style={{ display: 'flex', gap: '8px', alignItems: 'center' }}><CheckCircle2 size={15} color="#fb923c" /> Context-Aware Perturbation Scheduler</li>
              <li style={{ display: 'flex', gap: '8px', alignItems: 'center' }}><CheckCircle2 size={15} color="#fb923c" /> Quantized Qwen2-VL Oracle</li>
              <li style={{ display: 'flex', gap: '8px', alignItems: 'center' }}><CheckCircle2 size={15} color="#fb923c" /> Non-Crash UI Layout Collisions</li>
              <li style={{ display: 'flex', gap: '8px', alignItems: 'center' }}><CheckCircle2 size={15} color="#fb923c" /> Automated Appium Regression Runner</li>
            </ul>
            <button className="btn-cta" onClick={() => onLaunchDashboard('cicd')} style={{ width: '100%', borderRadius: '24px' }}>
              Integrate CI/CD Pipeline
            </button>
          </div>

          {/* Card 3 */}
          <div className="glass-card" style={{ padding: '36px 26px', textAlign: 'left' }}>
            <span className="glow-badge glow-badge-green" style={{ fontSize: '10px', marginBottom: '12px' }}>Self-Healing Mode</span>
            <h3 style={{ fontSize: '28px', fontWeight: '900', margin: '8px 0 16px' }}>Telemetry Sync</h3>
            <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '24px', lineHeight: '1.6' }}>
              Leverage real-world production logs (Firebase/Sentry) for continuous test maintenance.
            </p>
            <div style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '700', textTransform: 'uppercase', marginBottom: '12px' }}>Features Included</div>
            <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '12px', color: 'var(--text-body)', marginBottom: '32px' }}>
              <li style={{ display: 'flex', gap: '8px', alignItems: 'center' }}><CheckCircle2 size={15} color="#10b981" /> Everything in Automated CI</li>
              <li style={{ display: 'flex', gap: '8px', alignItems: 'center' }}><CheckCircle2 size={15} color="#10b981" /> Telemetry Synthesis Engine</li>
              <li style={{ display: 'flex', gap: '8px', alignItems: 'center' }}><CheckCircle2 size={15} color="#10b981" /> Sentence-BERT Locator Recovery</li>
            </ul>
            <button className="btn-secondary" onClick={() => onLaunchDashboard('attribution')} style={{ width: '100%', borderRadius: '24px' }}>
              Connect Production Logs
            </button>
          </div>
        </div>
      </section>

      {/* Section 5: FAQ Accordion */}
      <section style={{ padding: '80px 24px', maxWidth: '900px', margin: '0 auto', width: '100%', position: 'relative' }}>
        <h2 style={{ fontSize: '38px', fontWeight: '900', textAlign: 'center', marginBottom: '12px' }}>Frequently Asked Questions</h2>
        <p style={{ fontSize: '14px', color: 'var(--text-muted)', textAlign: 'center', marginBottom: '40px' }}>
          Key technical answers about our testing methodology, VLM oracles, and self-healing engine.
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {faqs.map((faq, idx) => (
            <motion.div
              key={idx}
              className="glass-card"
              onClick={() => setActiveFaq(activeFaq === idx ? null : idx)}
              style={{ cursor: 'pointer', padding: '22px 28px' }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontWeight: '700', fontSize: '15px', color: activeFaq === idx ? 'var(--accent-orange-bright)' : '#fff' }}>
                <span>{faq.q}</span>
                <ChevronDown size={18} style={{ transform: activeFaq === idx ? 'rotate(180deg)' : 'none', transition: 'transform 0.3s ease', color: 'var(--accent-orange)' }} />
              </div>
              <AnimatePresence>
                {activeFaq === idx && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: 0.25 }}
                  >
                    <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '14px', lineHeight: '1.65' }}>
                      {faq.a}
                    </p>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Section 6: Ready to Test Banner */}
      <section style={{ padding: '60px 24px 60px', maxWidth: '1100px', margin: '0 auto', width: '100%' }}>
        <motion.div
          whileHover={{ scale: 1.01 }}
          className="glass-card shimmer-active"
          style={{ background: 'linear-gradient(135deg, rgba(32, 24, 38, 0.85), rgba(16, 22, 38, 0.95))', border: '1px solid rgba(251,146,60,0.3)', padding: '60px 36px', textAlign: 'center', borderRadius: '32px', boxShadow: '0 0 35px rgba(251,146,60,0.15)' }}
        >
          <span className="glow-badge glow-badge-orange" style={{ marginBottom: '16px' }}>Ready For Production</span>
          <h2 style={{ fontSize: '44px', fontWeight: '900', marginBottom: '16px', color: '#fff' }}>
            Ready to Test for Real-World Chaos?
          </h2>
          <p style={{ fontSize: '15px', color: 'var(--text-muted)', maxWidth: '640px', margin: '0 auto 34px', lineHeight: '1.65' }}>
            Transform fragile mobile test suites into robust, self-healing regression pipelines powered by AI vision and biomechanical modeling.
          </p>
          <button className="btn-cta" onClick={() => onLaunchDashboard('dashboard')} style={{ padding: '14px 40px', fontSize: '14px', margin: '0 auto' }}>
            Initialize Framework <ArrowRight size={18} />
          </button>
        </motion.div>
      </section>

      {/* Rich Multi-Column Interactive Footer */}
      <footer style={{ background: 'var(--bg-surface)', borderTop: '1px solid rgba(255,255,255,0.08)', padding: '64px 36px 36px', marginTop: '40px', width: '100%', position: 'relative', zIndex: 2 }}>
        <div style={{ maxWidth: '1140px', margin: '0 auto', display: 'grid', gridTemplateColumns: '1.5fr 1fr 1fr 1fr', gap: '40px', marginBottom: '48px', fontSize: '13px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
              <img src="/logo.png" alt="Logo" style={{ width: '32px', height: '32px', filter: 'drop-shadow(0 0 8px rgba(251,146,60,0.35))' }} />
              <span style={{ fontFamily: 'var(--font-display)', fontWeight: '900', fontSize: '18px', color: '#fff', letterSpacing: '0.5px' }}>
                HEART <span style={{ color: 'var(--accent-orange-bright)' }}>FRAMEWORK</span>
              </span>
            </div>
            <p style={{ color: 'var(--text-muted)', fontSize: '12px', lineHeight: '1.7', marginBottom: '16px' }}>
              A specialized academic research initiative (Project ID: J26-SE-334) under SLIIT Software Systems & Technologies (SST) research group. Pioneering autonomous mobile reliability under environmental and human stress.
            </p>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              <span className="glow-badge glow-badge-orange" style={{ fontSize: '10px' }}>SDG 9: Industry & Innovation</span>
              <span className="glow-badge glow-badge-green" style={{ fontSize: '10px' }}>SDG 8: Economic Growth</span>
            </div>
          </div>

          <div>
            <h4 style={{ fontSize: '13px', fontWeight: '800', color: 'var(--accent-orange-bright)', marginBottom: '16px', letterSpacing: '0.5px', textTransform: 'uppercase' }}>
              Research Components
            </h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', color: 'var(--text-muted)', fontSize: '13px' }}>
              <span onClick={() => onLaunchDashboard('profiles')} style={{ cursor: 'pointer', transition: 'color 0.2s', display: 'flex', alignItems: 'center', gap: '6px' }} className="nav-hover-link">
                <ArrowRight size={12} color="var(--accent-orange)" /> Environmental Engine
              </span>
              <span onClick={() => onLaunchDashboard('human-stress')} style={{ cursor: 'pointer', transition: 'color 0.2s', display: 'flex', alignItems: 'center', gap: '6px' }} className="nav-hover-link">
                <ArrowRight size={12} color="var(--accent-orange)" /> Biomechanical Engine
              </span>
              <span onClick={() => onLaunchDashboard('vision')} style={{ cursor: 'pointer', transition: 'color 0.2s', display: 'flex', alignItems: 'center', gap: '6px' }} className="nav-hover-link">
                <ArrowRight size={12} color="var(--accent-orange)" /> On-Device Vision Oracle
              </span>
              <span onClick={() => onLaunchDashboard('attribution')} style={{ cursor: 'pointer', transition: 'color 0.2s', display: 'flex', alignItems: 'center', gap: '6px' }} className="nav-hover-link">
                <ArrowRight size={12} color="var(--accent-orange)" /> Self-Healing Synthesis
              </span>
            </div>
          </div>

          <div>
            <h4 style={{ fontSize: '13px', fontWeight: '800', color: 'var(--accent-cyan-bright)', marginBottom: '16px', letterSpacing: '0.5px', textTransform: 'uppercase' }}>
              Evaluation & Tools
            </h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', color: 'var(--text-muted)', fontSize: '13px' }}>
              <span onClick={() => onLaunchDashboard('dashboard')} style={{ cursor: 'pointer' }} className="nav-hover-link">
                Analytics Intelligence
              </span>
              <span onClick={() => onLaunchDashboard('benchmarks')} style={{ cursor: 'pointer' }} className="nav-hover-link">
                Themis 52 Crash Dataset
              </span>
              <span onClick={() => onLaunchDashboard('benchmarks')} style={{ cursor: 'pointer' }} className="nav-hover-link">
                Rico 72K+ UI Dataset
              </span>
              <span onClick={() => onLaunchDashboard('cicd')} style={{ cursor: 'pointer' }} className="nav-hover-link">
                CI/CD Action Workflows
              </span>
              <span onClick={() => onLaunchDashboard('executions')} style={{ cursor: 'pointer' }} className="nav-hover-link">
                Execution History Logs
              </span>
            </div>
          </div>

          <div>
            <h4 style={{ fontSize: '13px', fontWeight: '800', color: 'var(--accent-green-bright)', marginBottom: '16px', letterSpacing: '0.5px', textTransform: 'uppercase' }}>
              Project Information
            </h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', color: 'var(--text-muted)', fontSize: '12px' }}>
              <div>
                <span style={{ color: '#fff', fontWeight: '600' }}>Institution:</span><br />
                SLIIT Faculty of Computing
              </div>
              <div>
                <span style={{ color: '#fff', fontWeight: '600' }}>Research Lead:</span><br />
                Luqman Booso (Vision Oracle Lead)
              </div>
              <div>
                <span style={{ color: '#fff', fontWeight: '600' }}>Academic Year:</span><br />
                2026 Batch Final Year
              </div>
            </div>
          </div>
        </div>

        <div style={{ maxWidth: '1140px', margin: '0 auto', paddingTop: '24px', borderTop: '1px solid rgba(255,255,255,0.06)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '12px', color: 'var(--text-dim)', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            © 2026 HEART Framework (J26-SE-334). All rights reserved. Software Systems & Technologies Research.
          </div>
          <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
            <span style={{ cursor: 'pointer', color: 'var(--text-muted)' }} onClick={() => onLaunchDashboard('landing')}>Overview</span>
            <span style={{ cursor: 'pointer', color: 'var(--text-muted)' }} onClick={() => onLaunchDashboard('dashboard')}>Analytics</span>
            <span style={{ cursor: 'pointer', color: 'var(--text-muted)' }} onClick={() => onLaunchDashboard('profiles')}>Profiles</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
