import React, { useState } from 'react';
import {
  Briefcase, Check, Shield, Download, Monitor, Zap, Users,
  Building2, Sparkles, ArrowRight, DollarSign, Clock, Lock,
  Server, Cpu, CheckCircle2, AlertCircle, FileText, ChevronRight
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export default function CommercializationPlan({ onNavigate }) {
  const [selectedBilling, setSelectedBilling] = useState('monthly'); // 'monthly' | 'annual'
  const [activeTier, setActiveTier] = useState('Enterprise');
  const [activatedLicense, setActivatedLicense] = useState(null);
  const [simulatedKey, setSimulatedKey] = useState('');
  const [notice, setNotice] = useState(null);

  const tiers = [
    {
      id: 'Community',
      name: 'Community Edition',
      badge: 'Open Source & Students',
      priceMonthly: 0,
      priceAnnual: 0,
      description: 'Ideal for undergraduate researchers, students, and open-source contributors testing mobile clients.',
      target: 'Students & Open-Source Devs',
      color: '#94a3b8',
      features: [
        '1 Local User Seat',
        'Local ADB Device Execution',
        'Standard System & Network Perturbations',
        'Up to 500 scans / month',
        'Community Forum & GitHub Discussions Support',
        'Permissive Apache-2.0 License Foundation'
      ],
      cta: 'Current Free Tier',
      isPopular: false
    },
    {
      id: 'Developer',
      name: 'Developer Pro',
      badge: 'Solo QA & Freelancers',
      priceMonthly: 29,
      priceAnnual: 24,
      description: 'Targeted at solo QA automation engineers and freelance mobile contractors requiring parallel test execution.',
      target: 'Freelancers & Solo QA',
      color: '#38bdf8',
      features: [
        '2 Parallel Test Runners',
        'Custom YAML / JSON Stress Profiles',
        'CI/CD Pipeline Export (GitHub Actions, GitLab)',
        'Automated Appium Script Generation',
        'Email Support with 48h SLA',
        'Exportable Executive PDF Defect Reports'
      ],
      cta: 'Select Developer Pro',
      isPopular: false
    },
    {
      id: 'Team',
      name: 'Team Automation',
      badge: 'Startups & QA Teams',
      priceMonthly: 59,
      priceAnnual: 49,
      description: 'Engineered for fast-paced mobile development teams needing coordinated chaos campaigns and self-healing.',
      target: 'Startups & QA Teams',
      color: '#fb923c',
      features: [
        '5 Parallel Test Runners & Emulator Pools',
        'Dedicated Multi-User Dashboard',
        'Unlimited S-BERT Self-Healing Test Repairs',
        'Jira, Slack, & Sentry Webhook Integration',
        'Priority Technical Support (12h SLA)',
        'Shared Organization Workspace & User Roles'
      ],
      cta: 'Upgrade to Team',
      isPopular: true
    },
    {
      id: 'Enterprise',
      name: 'Enterprise Air-Gapped',
      badge: 'Regulated Sectors & Superapps',
      priceMonthly: 99,
      priceAnnual: 79,
      description: 'Designed for banks, telemedicine, and fintech superapps requiring strict data sovereignty and zero cloud egress.',
      target: 'FinTech, Healthcare & Banks',
      color: '#a855f7',
      features: [
        'Windows Native Desktop Application (Local .exe)',
        '100% Air-Gapped On-Premises Execution',
        'Zero Data Egress (No External Cloud Transmissions)',
        'Local Quantized Qwen2-VL Model (4-bit AWQ)',
        'Unlimited Device Bridges (Hardware USB & Emulators)',
        'Custom Chaos Vectors & Dedicated Success Engineer',
        '24/7 Enterprise SLA with Formal Support Agreement'
      ],
      cta: 'Deploy Enterprise Air-Gapped',
      isPopular: false
    }
  ];

  const personas = [
    {
      role: 'QA Automation Lead',
      pain: 'Brittle ADB shell scripts that are desynchronized with app state and break on layout updates.',
      solution: 'Automatic semantic synchronization injected mid-transaction, eliminating manual script maintenance.',
      benefit: 'Reduces test regression upkeep effort by over 70% while improving fault reproduction.'
    },
    {
      role: 'Site Reliability Engineer (SRE)',
      pain: 'Mobile client behavior under backend latency or server throttling is unknown until outages hit production.',
      solution: 'Proactive mobile fault injection shifting chaos engineering left into standard pre-release pipelines.',
      benefit: 'Prevents catastrophic app freezes and cascade timeouts before public store releases.'
    },
    {
      role: 'Mobile Product Manager',
      pain: '70% user abandonment rate caused by non-crash UI glitches and unresponsive payment checkout buttons.',
      solution: 'Detects non-crash visual overlap, touch target misalignments, and state loss under stress.',
      benefit: 'Protects core retention metrics and checkout conversion rates in mission-critical mobile flows.'
    }
  ];

  const handleSimulateActivation = (tierId) => {
    const randomKey = `HEART-${tierId.toUpperCase()}-${Math.random().toString(36).substring(2, 7).toUpperCase()}-2026`;
    setSimulatedKey(randomKey);
    setActiveTier(tierId);
    setActivatedLicense({
      tier: tierId,
      key: randomKey,
      validUntil: 'October 2027',
      status: 'Active (On-Premises Air-Gapped)'
    });
    setNotice(`License entitlement for [${tierId}] successfully registered!`);
    setTimeout(() => setNotice(null), 4000);
  };

  const handleDownloadWindowsApp = () => {
    setNotice('Initializing Windows Native Desktop Application (.exe / .bat launcher package)...');
    // Trigger download of the windows launcher script
    const launcherScript = `@echo off
title HEART - Mobile Robustness Testing Framework (Windows Enterprise)
echo =========================================================================
echo   HEART Mobile Robustness Testing Framework - Windows Desktop Edition
echo   Component 1: Context-Aware Environmental Perturbation Engine
echo   Student: Chanlaka G.L.S. (IT23151260) - Project ID: J26-SE-334
echo =========================================================================
cd /d "%~dp0"
python launch_windows_desktop.py
pause
`;
    const blob = new Blob([launcherScript], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'HEART_Windows_Studio_Launcher.bat';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    setTimeout(() => setNotice('Windows launcher script downloaded! Double-click to start.'), 1500);
  };

  return (
    <div className="tab-pane-container" style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
      {/* Header Banner */}
      <motion.div
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        style={{
          padding: '28px 32px',
          borderRadius: '24px',
          background: 'linear-gradient(135deg, rgba(28,33,48,0.95) 0%, rgba(38,44,62,0.85) 100%)',
          border: '1px solid rgba(251,146,60,0.25)',
          boxShadow: '0 8px 32px rgba(0,0,0,0.35)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '20px'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <div style={{
            background: 'linear-gradient(135deg, rgba(251,146,60,0.2) 0%, rgba(245,158,11,0.1) 100%)',
            color: 'var(--accent-orange-bright)',
            width: '56px',
            height: '56px',
            borderRadius: '16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            border: '1px solid rgba(251,146,60,0.35)',
            boxShadow: '0 0 24px rgba(251,146,60,0.25)'
          }}>
            <Briefcase size={28} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
              <span style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '700', letterSpacing: '0.8px', textTransform: 'uppercase' }}>
                HEART Commercialization Strategy • Section 6
              </span>
              <span style={{
                fontSize: '11px',
                padding: '2px 10px',
                borderRadius: '12px',
                fontWeight: '700',
                background: 'rgba(168, 85, 247, 0.15)',
                color: '#c084fc',
                border: '1px solid rgba(168, 85, 247, 0.3)'
              }}>
                Value-Based Tiered Licensing
              </span>
            </div>
            <h1 style={{ fontSize: '24px', fontWeight: '900', color: '#fff', marginTop: '4px', letterSpacing: '-0.02em' }}>
              Commercialization & Enterprise Deployment
            </h1>
            <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '2px' }}>
              "Automate Chaos. Ensure Reliability." Shifting mobile chaos engineering left into pre-release QA pipelines.
            </p>
          </div>
        </div>

        {/* Billing Switch */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          background: 'rgba(15, 23, 42, 0.6)',
          padding: '4px',
          borderRadius: '14px',
          border: '1px solid var(--border-subtle)'
        }}>
          <button
            onClick={() => setSelectedBilling('monthly')}
            style={{
              padding: '8px 16px',
              borderRadius: '10px',
              border: 'none',
              background: selectedBilling === 'monthly' ? 'var(--accent-orange-bright)' : 'transparent',
              color: selectedBilling === 'monthly' ? '#000' : 'var(--text-muted)',
              fontSize: '12px',
              fontWeight: '700',
              cursor: 'pointer',
              transition: 'all 0.2s'
            }}
          >
            Monthly
          </button>
          <button
            onClick={() => setSelectedBilling('annual')}
            style={{
              padding: '8px 16px',
              borderRadius: '10px',
              border: 'none',
              background: selectedBilling === 'annual' ? 'var(--accent-orange-bright)' : 'transparent',
              color: selectedBilling === 'annual' ? '#000' : 'var(--text-muted)',
              fontSize: '12px',
              fontWeight: '700',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'all 0.2s'
            }}
          >
            Annual <span style={{ fontSize: '10px', padding: '1px 6px', background: 'rgba(0,0,0,0.3)', borderRadius: '6px', color: '#fff' }}>Save 20%</span>
          </button>
        </div>
      </motion.div>

      {/* Action Notification Banner */}
      <AnimatePresence>
        {notice && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            style={{
              padding: '12px 20px',
              background: 'rgba(16, 185, 129, 0.12)',
              border: '1px solid rgba(16, 185, 129, 0.35)',
              borderRadius: '14px',
              color: '#34d399',
              fontSize: '13px',
              display: 'flex',
              alignItems: 'center',
              gap: '10px'
            }}
          >
            <CheckCircle2 size={16} />
            <span>{notice}</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ========================================================================= */}
      {/* WINDOWS APPLICATION EDITION SPECIAL HIGHLIGHT BANNER */}
      {/* ========================================================================= */}
      <motion.div
        initial={{ opacity: 0, scale: 0.98 }}
        animate={{ opacity: 1, scale: 1 }}
        style={{
          background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.85) 0%, rgba(15, 23, 42, 0.9) 100%)',
          borderRadius: '24px',
          border: '1px solid rgba(56, 189, 248, 0.35)',
          padding: '28px 32px',
          position: 'relative',
          overflow: 'hidden',
          boxShadow: '0 12px 40px rgba(0, 0, 0, 0.4)'
        }}
      >
        <div style={{
          position: 'absolute',
          top: 0,
          right: 0,
          width: '320px',
          height: '100%',
          background: 'radial-gradient(circle at top right, rgba(56, 189, 248, 0.15) 0%, transparent 70%)',
          pointerEvents: 'none'
        }} />

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '20px', position: 'relative', zIndex: 1 }}>
          <div style={{ maxWidth: '780px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
              <span style={{
                background: 'rgba(56, 189, 248, 0.2)',
                color: '#38bdf8',
                fontSize: '11px',
                fontWeight: '800',
                padding: '3px 10px',
                borderRadius: '8px',
                letterSpacing: '0.6px',
                textTransform: 'uppercase',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px'
              }}>
                <Monitor size={13} /> Windows Desktop Application Edition
              </span>
              <span style={{
                background: 'rgba(16, 185, 129, 0.15)',
                color: '#10b981',
                fontSize: '11px',
                fontWeight: '700',
                padding: '3px 10px',
                borderRadius: '8px',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px'
              }}>
                <Lock size={12} /> Air-Gapped Compliant
              </span>
            </div>

            <h2 style={{ fontSize: '22px', fontWeight: '900', color: '#fff', marginBottom: '8px' }}>
              HEART Desktop Studio for Windows (Native .exe / MSI)
            </h2>
            <p style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: '1.6' }}>
              Regulated organizations in FinTech, Healthcare, and Defense structurally cannot upload internal APK binaries or test telemetry to external clouds. The <strong>Windows Desktop Edition</strong> runs 100% on-premises with native USB ADB bridges, zero cloud data egress, and embedded quantized VLM models.
            </p>

            <div style={{ display: 'flex', gap: '24px', marginTop: '16px', flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: '#cbd5e1' }}>
                <CheckCircle2 size={14} color="#38bdf8" /> Direct USB & Wi-Fi ADB Hardware Bridge
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: '#cbd5e1' }}>
                <CheckCircle2 size={14} color="#38bdf8" /> Zero External Telemetry Leakage (Air-Gapped)
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: '#38bdf8' }}>
                <CheckCircle2 size={14} color="#38bdf8" /> One-Click Launcher (`launch_windows_desktop.py`)
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <button
              onClick={handleDownloadWindowsApp}
              className="btn-cta"
              style={{
                padding: '12px 24px',
                borderRadius: '14px',
                fontSize: '14px',
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                boxShadow: '0 4px 20px rgba(56, 189, 248, 0.3)'
              }}
            >
              <Download size={16} /> Download Windows Launcher (.bat)
            </button>
            <span style={{ fontSize: '11px', color: 'var(--text-dim)', textAlign: 'center' }}>
              Compatible with Windows 10 & 11 (x64) • Python 3.10+
            </span>
          </div>
        </div>
      </motion.div>

      {/* ========================================================================= */}
      {/* 4 VALUE-BASED PRICING TIERS GRID */}
      {/* ========================================================================= */}
      <div>
        <div style={{ marginBottom: '18px' }}>
          <h2 style={{ fontSize: '18px', fontWeight: '800', color: '#fff' }}>
            Value-Based Tiered Licensing
          </h2>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
            Captured from Proposal Section 6: Tailored for academic researchers up to Fortune 500 mobile enterprises.
          </p>
        </div>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(270px, 1fr))',
          gap: '20px'
        }}>
          {tiers.map((tier) => {
            const price = selectedBilling === 'annual' ? tier.priceAnnual : tier.priceMonthly;
            const isCurrentActive = activeTier === tier.id;

            return (
              <motion.div
                key={tier.id}
                whileHover={{ y: -4 }}
                style={{
                  background: isCurrentActive
                    ? 'linear-gradient(135deg, rgba(30, 41, 59, 0.95) 0%, rgba(20, 28, 45, 0.9) 100%)'
                    : 'var(--bg-surface)',
                  borderRadius: '20px',
                  border: isCurrentActive
                    ? `2px solid ${tier.color}`
                    : tier.isPopular
                    ? '1px solid rgba(251, 146, 60, 0.4)'
                    : '1px solid var(--border-subtle)',
                  padding: '24px',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  position: 'relative',
                  boxShadow: isCurrentActive
                    ? `0 12px 36px ${tier.color}25`
                    : '0 4px 20px rgba(0,0,0,0.2)'
                }}
              >
                {tier.isPopular && (
                  <span style={{
                    position: 'absolute',
                    top: '-12px',
                    right: '20px',
                    background: 'var(--accent-orange-bright)',
                    color: '#000',
                    fontSize: '10px',
                    fontWeight: '900',
                    textTransform: 'uppercase',
                    padding: '3px 10px',
                    borderRadius: '10px',
                    letterSpacing: '0.5px'
                  }}>
                    Most Popular
                  </span>
                )}

                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <h3 style={{ fontSize: '18px', fontWeight: '900', color: '#fff' }}>{tier.name}</h3>
                    <span style={{ fontSize: '11px', color: tier.color, fontWeight: '700' }}>{tier.badge}</span>
                  </div>

                  <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '8px', minHeight: '36px' }}>
                    {tier.description}
                  </p>

                  <div style={{ margin: '18px 0', display: 'flex', alignItems: 'baseline', gap: '4px' }}>
                    <span style={{ fontSize: '32px', fontWeight: '900', color: '#fff' }}>${price}</span>
                    <span style={{ fontSize: '12px', color: 'var(--text-dim)' }}>
                      {price === 0 ? '/ forever' : `/ month ${selectedBilling === 'annual' ? '(billed yearly)' : ''}`}
                    </span>
                  </div>

                  <div style={{ borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: '16px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    <span style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '700', textTransform: 'uppercase' }}>
                      Key Capabilities:
                    </span>
                    {tier.features.map((f, i) => (
                      <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', fontSize: '12px', color: '#e2e8f0' }}>
                        <Check size={14} color={tier.color} style={{ marginTop: '2px', flexShrink: 0 }} />
                        <span>{f}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div style={{ marginTop: '24px' }}>
                  <button
                    onClick={() => handleSimulateActivation(tier.id)}
                    className={tier.id === 'Enterprise' ? 'btn-cta' : tier.isPopular ? 'btn-cta' : 'btn-outline'}
                    style={{
                      width: '100%',
                      padding: '11px 16px',
                      borderRadius: '12px',
                      fontSize: '13px',
                      fontWeight: '800',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '8px',
                      background: isCurrentActive ? tier.color : undefined,
                      color: isCurrentActive ? (tier.id === 'Community' ? '#000' : '#fff') : undefined
                    }}
                  >
                    {isCurrentActive ? (
                      <>
                        <CheckCircle2 size={15} /> Active Entitlement
                      </>
                    ) : (
                      <>
                        <Sparkles size={14} /> {tier.cta}
                      </>
                    )}
                  </button>
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>

      {/* ========================================================================= */}
      {/* FINANCIALS & BREAK-EVEN PROJECTION */}
      {/* ========================================================================= */}
      <div style={{
        background: 'var(--bg-surface)',
        borderRadius: '24px',
        border: '1px solid var(--border-subtle)',
        padding: '28px 32px'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px', marginBottom: '20px' }}>
          <div>
            <h2 style={{ fontSize: '18px', fontWeight: '800', color: '#fff' }}>
              Investment, Break-Even & Financial Projections (Section 6 & 7)
            </h2>
            <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
              Undergraduate research cost justification transitioning into early commercial revenue recovery.
            </p>
          </div>
          <div style={{
            background: 'rgba(16, 185, 129, 0.1)',
            border: '1px solid rgba(16, 185, 129, 0.3)',
            borderRadius: '12px',
            padding: '6px 14px',
            fontSize: '12px',
            color: '#10b981',
            fontWeight: '700'
          }}>
            Break-Even Point: 9 to 12 Months
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
          <div style={{ background: 'rgba(15, 23, 42, 0.5)', padding: '16px', borderRadius: '16px', border: '1px solid rgba(255,255,255,0.06)' }}>
            <span style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', fontWeight: '700' }}>Actual Research Cost</span>
            <div style={{ fontSize: '24px', fontWeight: '900', color: '#fff', margin: '4px 0' }}>~$0 – $150</div>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Free-tier compute & open-source F-Droid/Themis datasets.</span>
          </div>

          <div style={{ background: 'rgba(15, 23, 42, 0.5)', padding: '16px', borderRadius: '16px', border: '1px solid rgba(255,255,255,0.06)' }}>
            <span style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', fontWeight: '700' }}>Cost to Commercialize</span>
            <div style={{ fontSize: '24px', fontWeight: '900', color: 'var(--accent-orange-bright)', margin: '4px 0' }}>$100 – $300</div>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Managed PostgreSQL sync bus for the first 6 months.</span>
          </div>

          <div style={{ background: 'rgba(15, 23, 42, 0.5)', padding: '16px', borderRadius: '16px', border: '1px solid rgba(255,255,255,0.06)' }}>
            <span style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', fontWeight: '700' }}>Target Initial MRR</span>
            <div style={{ fontSize: '24px', fontWeight: '900', color: '#38bdf8', margin: '4px 0' }}>$1,269 / mo</div>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>20 Devs ($580) + 10 Teams ($590) + 1 Enterprise ($99).</span>
          </div>

          <div style={{ background: 'rgba(15, 23, 42, 0.5)', padding: '16px', borderRadius: '16px', border: '1px solid rgba(255,255,255,0.06)' }}>
            <span style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', fontWeight: '700' }}>Software Licenses</span>
            <div style={{ fontSize: '24px', fontWeight: '900', color: '#10b981', margin: '4px 0' }}>$0 (Apache-2.0)</div>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Zero proprietary license fees; 100% commercial rights retained.</span>
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* TARGET CUSTOMER PERSONAS & VALUE PROPOSITIONS */}
      {/* ========================================================================= */}
      <div>
        <div style={{ marginBottom: '18px' }}>
          <h2 style={{ fontSize: '18px', fontWeight: '800', color: '#fff' }}>
            Customer Personas & Problem-Solution Fit
          </h2>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
            Elicited from senior QA professionals and Site Reliability Engineers during proposal preparation.
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
          {personas.map((p, idx) => (
            <div
              key={idx}
              style={{
                background: 'var(--bg-surface)',
                borderRadius: '20px',
                border: '1px solid var(--border-subtle)',
                padding: '24px',
                display: 'flex',
                flexDirection: 'column',
                gap: '14px'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '10px',
                  background: 'rgba(251, 146, 60, 0.15)',
                  color: 'var(--accent-orange-bright)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontWeight: '800'
                }}>
                  {idx + 1}
                </div>
                <h3 style={{ fontSize: '16px', fontWeight: '800', color: '#fff' }}>{p.role}</h3>
              </div>

              <div style={{ fontSize: '12px', color: '#94a3b8' }}>
                <strong style={{ color: '#f87171' }}>Industry Pain Point: </strong>
                {p.pain}
              </div>

              <div style={{ fontSize: '12px', color: '#cbd5e1' }}>
                <strong style={{ color: 'var(--accent-orange-bright)' }}>HEART Technical Solution: </strong>
                {p.solution}
              </div>

              <div style={{
                marginTop: 'auto',
                padding: '10px 14px',
                background: 'rgba(16, 185, 129, 0.08)',
                border: '1px solid rgba(16, 185, 129, 0.2)',
                borderRadius: '10px',
                fontSize: '11px',
                color: '#34d399'
              }}>
                <strong>Measurable Impact: </strong>{p.benefit}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
