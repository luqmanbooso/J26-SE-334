import React, { useState } from 'react';
import { FileText, RefreshCw, CheckCircle2, AlertTriangle, Code, ArrowRight, Sparkles, Download, Copy, Layers } from 'lucide-react';
import { motion } from 'framer-motion';

export default function AttributionReport() {
  const [isHealing, setIsHealing] = useState(false);
  const [healed, setHealed] = useState(true);
  const [repairRate, setRepairRate] = useState(94.2);
  const [copied, setCopied] = useState(false);

  const handleRunSelfHealing = () => {
    setIsHealing(true);
    setTimeout(() => {
      setHealed(true);
      setRepairRate(98.4);
      setIsHealing(false);
    }, 1400);
  };

  const handleCopyCode = () => {
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '28px', width: '100%', maxWidth: '1280px', margin: '0 auto' }}>
      {/* Top Header Card */}
      <div className="glass-card" style={{ padding: '18px 26px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ background: 'rgba(255,87,34,0.15)', color: '#ff5722', width: '46px', height: '46px', borderRadius: '14px', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 0 20px rgba(255,87,34,0.3)' }}>
            <FileText size={24} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '600', textTransform: 'uppercase' }}>Attribution & Self-Healing Engine</span>
            </div>
            <h1 style={{ fontSize: '20px', fontWeight: '900', color: '#fff', marginTop: '2px' }}>
              Attribution & Self-Healing Regression Test Synthesizer
            </h1>
          </div>
        </div>

        <button className="btn-cta" onClick={handleRunSelfHealing} disabled={isHealing}>
          <RefreshCw size={16} className={isHealing ? 'spin' : ''} />
          {isHealing ? 'Synthesizing Self-Healing Script...' : 'Run Self-Healing Repair Engine'}
        </button>
      </div>

      {/* Metric Stat Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '18px' }}>
        <div className="glass-card stat-accent-card" style={{ padding: '24px 20px' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '700', textTransform: 'uppercase' }}>Stress Events Injected</div>
          <div style={{ fontSize: '34px', fontWeight: '900', color: 'var(--accent-orange-bright)', fontFamily: 'var(--font-display)', margin: '6px 0 2px' }}>
            124+
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>ADB Shell & Netem Chaos</div>
        </div>

        <div className="glass-card stat-accent-card" style={{ padding: '24px 20px' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '700', textTransform: 'uppercase' }}>Detected Anomalies</div>
          <div style={{ fontSize: '34px', fontWeight: '900', color: '#f87171', fontFamily: 'var(--font-display)', margin: '6px 0 2px' }}>
            18
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Non-Crash Visual Collisions</div>
        </div>

        <div className="glass-card stat-accent-card" style={{ padding: '24px 20px' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '700', textTransform: 'uppercase' }}>Self-Healing Repair Rate</div>
          <div style={{ fontSize: '34px', fontWeight: '900', color: '#34d399', fontFamily: 'var(--font-display)', margin: '6px 0 2px' }}>
            {repairRate}%
          </div>
          <div style={{ fontSize: '11px', color: '#10b981' }}>Sentence-BERT Resolved</div>
        </div>

        <div className="glass-card stat-accent-card" style={{ padding: '24px 20px' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '700', textTransform: 'uppercase' }}>S-BERT Embedding Match</div>
          <div style={{ fontSize: '34px', fontWeight: '900', color: '#60a5fa', fontFamily: 'var(--font-display)', margin: '6px 0 2px' }}>
            0.942
          </div>
          <div style={{ fontSize: '11px', color: '#3b82f6' }}>Cosine Similarity Index</div>
        </div>
      </div>

      {/* Code Window with Sentence-BERT Remapping Highlights */}
      <div className="glass-card" style={{ padding: '28px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
          <div className="glass-card-title" style={{ margin: 0 }}>
            <div className="icon-wrap">
              <Code size={18} />
            </div>
            <span>Auto-Synthesized Appium Regression Test (Python)</span>
          </div>

          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            {healed && (
              <span className="glow-badge glow-badge-green" style={{ fontSize: '11px' }}>
                <CheckCircle2 size={13} /> Sentence-BERT Remapped & Verified
              </span>
            )}
            <button className="btn-secondary" onClick={handleCopyCode} style={{ padding: '6px 14px', fontSize: '12px', display: 'flex', gap: '6px', alignItems: 'center' }}>
              <Copy size={13} /> {copied ? 'Copied!' : 'Copy Script'}
            </button>
            <button className="btn-secondary" style={{ padding: '6px 14px', fontSize: '12px', display: 'flex', gap: '6px', alignItems: 'center' }}>
              <Download size={13} /> Export .py
            </button>
          </div>
        </div>

        <div className="code-window">
          <div style={{ color: '#64748b' }}># =========================================================================</div>
          <div style={{ color: '#64748b' }}># AUTO-SYNTHESIZED APPIUM REGRESSION SCRIPT</div>
          <div style={{ color: '#64748b' }}># Generated by HEART Framework Self-Healing Synthesis Engine</div>
          <div style={{ color: '#64748b' }}># Incident ID: INC-2026-0891 | Root Cause: UI_COLLISION under 3G_FLAKY stress</div>
          <div style={{ color: '#64748b' }}># =========================================================================</div>
          <br />
          <div style={{ color: '#f472b6' }}>import pytest</div>
          <div style={{ color: '#f472b6' }}>from appium import webdriver</div>
          <div style={{ color: '#f472b6' }}>from heart_framework.oracles import VisionOracle</div>
          <div style={{ color: '#f472b6' }}>from heart_framework.perturbation import ChaosInjector</div>
          <br />
          <div style={{ color: '#fff', fontWeight: '700' }}>def test_checkout_under_stress(driver):</div>
          <div style={{ paddingLeft: '22px', color: '#64748b' }}># 1. Replay environmental conditions present during failure</div>
          <div style={{ paddingLeft: '22px', color: '#38bdf8' }}>
            injector = ChaosInjector(driver)
          </div>
          <div style={{ paddingLeft: '22px', color: '#38bdf8' }}>
            injector.apply_profile(&#123;"cpu_stress": 85, "network": "3g_flaky", "battery": 10&#125;)
          </div>
          <br />
          <div style={{ paddingLeft: '22px', color: '#64748b' }}># 2. Navigation through target flow</div>
          <div style={{ paddingLeft: '22px', color: '#e2e8f0' }}>driver.find_element("id", "com.example.checkout:id/btn_cart").click()</div>
          <br />

          {/* Broken Line vs Remapped Line */}
          <div style={{ paddingLeft: '22px', background: 'rgba(239, 68, 68, 0.15)', borderLeft: '3px solid #ef4444', padding: '10px 14px', margin: '6px 0', borderRadius: '6px', color: '#fca5a5' }}>
            <div style={{ fontSize: '11px', color: '#ef4444', fontWeight: '700' }}># [BROKEN LOCATOR TARGET - OBSOLETE DOM NODE COLLISION]:</div>
            <code># driver.find_element_by_xpath("//android.widget.Button[@id='submit']").click()</code>
          </div>

          <div style={{ paddingLeft: '22px', background: 'rgba(16, 185, 129, 0.15)', borderLeft: '3px solid #10b981', padding: '10px 14px', margin: '6px 0', borderRadius: '6px', color: '#a7f3d0', fontWeight: '600' }}>
            <div style={{ fontSize: '11px', color: '#34d399', fontWeight: '700' }}># [SENTENCE-BERT REPAIRED LOCATOR - COSINE SIMILARITY 0.942]:</div>
            <code>driver.find_element_by_xpath("//android.widget.Button[@text='SUBMIT']").click()</code>
          </div>

          <br />
          <div style={{ paddingLeft: '22px', color: '#64748b' }}># 3. Vision-Language Oracle layout verification</div>
          <div style={{ paddingLeft: '22px', color: '#34d399', fontWeight: '700' }}>
            assert VisionOracle.verify_no_overlap(driver.get_screenshot_as_png(), threshold=0.95)
          </div>
        </div>
      </div>
    </div>
  );
}
