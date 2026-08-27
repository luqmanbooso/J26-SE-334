import React, { useState } from 'react';
import { Terminal, Upload, Cpu, CheckCircle2, Copy, Play, ArrowRight, Code, Shield, Sparkles, Layers, Smartphone } from 'lucide-react';
import { motion } from 'framer-motion';

export default function AppIntegration() {
  const [apkFile, setApkFile] = useState('MyTargetApp-v2.4.1.apk');
  const [packageName, setPackageName] = useState('com.example.checkout');
  const [integrationType, setIntegrationType] = useState('cli');
  const [copied, setCopied] = useState(false);

  const snippets = {
    cli: `# 1. Install HEART Framework CLI via pip
pip install heart-testing-framework --upgrade

# 2. Execute zero-SDK stress injection on target APK
heart-test run \\
  --apk ./${apkFile} \\
  --package ${packageName} \\
  --profile payment-stress-heavy \\
  --vlm-oracle on-device-qwen2vl \\
  --export-report ./reports/heart-summary.json`,

    appium: `from heart_framework import HeartOrchestrator, PerturbationConfig
from heart_framework.oracles import VisionLanguageOracle

# Initialize zero-SDK framework wrapper around Appium / UiAutomator2
config = PerturbationConfig(
    cpu_stress=85,
    ram_stress=75,
    latency_ms=1250,
    network_profile="4G_to_3G_handoff",
    vlm_oracle=VisionLanguageOracle(quantization="4bit_awq")
)

orchestrator = HeartOrchestrator(
    apk_path="./${apkFile}",
    package_name="${packageName}",
    config=config
)

# Start test execution under environmental and motor chaos
session = orchestrator.start_session()
session.inject_perturbation()
assert session.verify_layout_stability()`,

    github: `name: HEART Mobile Robustness Test Pipeline

on:
  push:
    branches: [ main, staging ]
  pull_request:
    branches: [ main ]

jobs:
  robustness-suite:
    name: Execute Chaos & On-Device VLM Verification
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python 3.10
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
          
      - name: Run HEART Framework Robustness Check
        uses: reactivecircus/android-emulator-runner@v2
        with:
          api-level: 34
          target: google_apis
          arch: x86_64
          script: |
            pip install heart-testing-framework
            heart-test run --apk ./${apkFile} --ci-mode --auto-heal`
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(snippets[integrationType]);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '28px', width: '100%', maxWidth: '1280px', margin: '0 auto' }}>
      {/* Top Header Card */}
      <div className="glass-card" style={{ padding: '18px 26px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ background: 'rgba(255,87,34,0.15)', color: '#ff5722', width: '46px', height: '46px', borderRadius: '14px', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 0 20px rgba(255,87,34,0.3)' }}>
            <Terminal size={24} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="glow-badge glow-badge-orange" style={{ fontSize: '9px', padding: '2px 8px' }}>Zero-SDK Architecture</span>
              <span style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '600', textTransform: 'uppercase' }}>Target App Setup</span>
            </div>
            <h1 style={{ fontSize: '20px', fontWeight: '900', color: '#fff', marginTop: '2px' }}>
              Connect Target Mobile Application (.APK / .IPA)
            </h1>
          </div>
        </div>

        <button className="btn-cta">
          <Play size={16} /> Test Integration Live
        </button>
      </div>

      {/* 2-Column Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.35fr', gap: '24px' }}>
        {/* Left Column: Target App Configuration Form */}
        <div className="glass-card" style={{ padding: '28px' }}>
          <div className="glass-card-title" style={{ marginBottom: '22px' }}>
            <div className="icon-wrap">
              <Upload size={18} />
            </div>
            <span>Target Application Package Details</span>
          </div>

          <div className="form-field">
            <label>
              <span>Target APK Package File</span>
              <span className="val-badge">Auto-detect</span>
            </label>
            <div style={{ display: 'flex', gap: '10px' }}>
              <input
                type="text"
                value={apkFile}
                onChange={(e) => setApkFile(e.target.value)}
                className="input-styled"
              />
              <button className="btn-secondary" style={{ whiteSpace: 'nowrap', padding: '10px 16px', fontSize: '12px' }}>
                Browse...
              </button>
            </div>
          </div>

          <div className="form-field">
            <label>
              <span>Android Package Identifier</span>
              <span style={{ fontSize: '11px', color: 'var(--text-dim)' }}>manifest package</span>
            </label>
            <input
              type="text"
              value={packageName}
              onChange={(e) => setPackageName(e.target.value)}
              className="input-styled"
            />
          </div>

          <div className="form-field">
            <label>
              <span>Target Execution Engine</span>
            </label>
            <select className="input-styled">
              <option>UiAutomator2 (Android 8.0 - 15)</option>
              <option>XCUITest (iOS 14.0 - 18)</option>
              <option>Appium Core Driver 2.0</option>
              <option>Espresso Hermetic Driver</option>
            </select>
          </div>

          <div style={{ background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.25)', padding: '16px', borderRadius: '14px', fontSize: '12px', color: '#34d399', display: 'flex', gap: '12px', alignItems: 'flex-start', marginTop: '10px' }}>
            <CheckCircle2 size={20} style={{ flexShrink: 0, marginTop: '2px' }} />
            <div>
              <strong style={{ color: '#fff', fontSize: '13px' }}>Zero Source-Code Modification Required</strong>
              <div style={{ color: '#a7f3d0', marginTop: '4px', lineHeight: '1.5' }}>
                HEART attaches externally via ADB shell protocols, accessibility services, and emulator hooks without modifying application code or injecting debug agents.
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Code Snippet Generator */}
        <div className="glass-card" style={{ padding: '28px', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
            <div className="glass-card-title" style={{ margin: 0 }}>
              <div className="icon-wrap">
                <Code size={18} />
              </div>
              <span>Integration Snippet Generator</span>
            </div>
            <button className="btn-secondary" onClick={handleCopy} style={{ padding: '6px 14px', fontSize: '12px', display: 'flex', gap: '6px', alignItems: 'center' }}>
              <Copy size={13} /> {copied ? 'Copied!' : 'Copy Snippet'}
            </button>
          </div>

          <div className="chip-row" style={{ marginBottom: '18px' }}>
            <button className={`chip-item ${integrationType === 'cli' ? 'active' : ''}`} onClick={() => setIntegrationType('cli')}>
              <Terminal size={14} /> CLI Command
            </button>
            <button className={`chip-item ${integrationType === 'appium' ? 'active' : ''}`} onClick={() => setIntegrationType('appium')}>
              <Code size={14} /> Python Appium SDK
            </button>
            <button className={`chip-item ${integrationType === 'github' ? 'active' : ''}`} onClick={() => setIntegrationType('github')}>
              <Layers size={14} /> GitHub Actions CI/CD
            </button>
          </div>

          <div className="code-window" style={{ flex: 1, minHeight: '290px' }}>
            <pre style={{ margin: 0, color: '#e2e8f0' }}>{snippets[integrationType]}</pre>
          </div>
        </div>
      </div>
    </div>
  );
}
