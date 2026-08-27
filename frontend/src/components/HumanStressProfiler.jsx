import React, { useState, useEffect } from 'react';
import { Activity, Play, XCircle, Target, Hand, Wifi, Battery, CheckCircle2, Pause, Sparkles, Flame, Sliders, RefreshCw } from 'lucide-react';
import { motion } from 'framer-motion';

export default function HumanStressProfiler() {
  const [frustration, setFrustration] = useState(75);
  const [urgency, setUrgency] = useState(65);
  const [swipeVelocity, setSwipeVelocity] = useState(82);
  const [activeTouchType, setActiveTouchType] = useState('taps');
  const [isSimulating, setIsSimulating] = useState(false);
  const [playbackTime, setPlaybackTime] = useState(4.2);

  // Dynamic live metric calculations driven by slider inputs
  const fittsError = Math.min(48, Math.round((frustration * 0.28) + (urgency * 0.16)));
  const missedTargets = Math.min(32, Math.round((frustration * 0.2) + (swipeVelocity * 0.14)));
  const calculatedVelocity = Math.round(220 + (swipeVelocity * 5.8));

  // Playback timer simulation loop
  useEffect(() => {
    let interval;
    if (isSimulating) {
      interval = setInterval(() => {
        setPlaybackTime(prev => {
          if (prev >= 10.0) {
            setIsSimulating(false);
            return 10.0;
          }
          return Number((prev + 0.2).toFixed(2));
        });
      }, 200);
    }
    return () => clearInterval(interval);
  }, [isSimulating]);

  const toggleSimulation = () => {
    if (isSimulating) {
      setIsSimulating(false);
    } else {
      if (playbackTime >= 10.0) setPlaybackTime(0.0);
      setIsSimulating(true);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '28px', width: '100%', maxWidth: '1280px', margin: '0 auto' }}>
      {/* Top Header */}
      <div className="glass-card" style={{ padding: '18px 26px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ background: 'rgba(255,87,34,0.15)', color: '#ff5722', width: '46px', height: '46px', borderRadius: '14px', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 0 20px rgba(255,87,34,0.3)' }}>
            <Flame size={24} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="glow-badge glow-badge-orange" style={{ fontSize: '9px', padding: '2px 8px' }}>Component 2</span>
              <span style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '600', textTransform: 'uppercase' }}>Sub-Objective C2</span>
            </div>
            <h1 style={{ fontSize: '20px', fontWeight: '900', color: '#fff', marginTop: '2px' }}>
              Human Stress Profiler & Interactive Touch Heatmap Simulation
            </h1>
          </div>
        </div>

        <button className="btn-cta" onClick={toggleSimulation}>
          {isSimulating ? <Pause size={16} /> : <Play size={16} />}
          {isSimulating ? 'Pause Biomechanical Run' : 'Run Biomechanical Simulation'}
        </button>
      </div>

      {/* Grid Layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.15fr 1fr', gap: '24px' }}>
        {/* Left Column: Interactive Sliders & Live Calculated Metrics */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '22px' }}>
          {/* Sliders Card */}
          <div className="glass-card" style={{ padding: '28px' }}>
            <div className="glass-card-title" style={{ marginBottom: '22px' }}>
              <div className="icon-wrap">
                <Sliders size={18} />
              </div>
              <span>Cognitive & Biomechanical Parameter Knobs</span>
            </div>

            <div className="form-field">
              <label>
                <span>Frustration Level</span>
                <span className="val-badge">{frustration}%</span>
              </label>
              <input
                type="range"
                min="0"
                max="100"
                value={frustration}
                onChange={(e) => setFrustration(Number(e.target.value))}
              />
            </div>

            <div className="form-field">
              <label>
                <span>Urgency Index</span>
                <span className="val-badge">{urgency}%</span>
              </label>
              <input
                type="range"
                min="0"
                max="100"
                value={urgency}
                onChange={(e) => setUrgency(Number(e.target.value))}
              />
            </div>

            <div className="form-field" style={{ marginBottom: 0 }}>
              <label>
                <span>Erratic Swipe Velocity</span>
                <span className="val-badge">{swipeVelocity}%</span>
              </label>
              <input
                type="range"
                min="0"
                max="100"
                value={swipeVelocity}
                onChange={(e) => setSwipeVelocity(Number(e.target.value))}
              />
            </div>
          </div>

          {/* 3 Metric Cards (Calculated Live from Sliders!) */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
            <div className="glass-card stat-accent-card" style={{ padding: '20px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '700', textTransform: 'uppercase' }}>Fitts's Law Error</span>
                <XCircle size={18} color={fittsError > 25 ? '#ef4444' : '#10b981'} />
              </div>
              <div style={{ fontSize: '34px', fontWeight: '900', color: fittsError > 25 ? '#ef4444' : '#fff', fontFamily: 'var(--font-display)', margin: '8px 0 2px' }}>
                {fittsError}%
              </div>
              <span style={{ fontSize: '10px', color: fittsError > 25 ? '#f87171' : 'var(--text-dim)' }}>
                {fittsError > 25 ? 'High Distortion' : 'Nominal Motor'}
              </span>
            </div>

            <div className="glass-card stat-accent-card" style={{ padding: '20px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '700', textTransform: 'uppercase' }}>Missed Targets</span>
                <Target size={18} color={missedTargets > 15 ? '#ff7043' : '#10b981'} />
              </div>
              <div style={{ fontSize: '34px', fontWeight: '900', color: missedTargets > 15 ? '#ff7043' : '#fff', fontFamily: 'var(--font-display)', margin: '8px 0 2px' }}>
                {missedTargets}
              </div>
              <span style={{ fontSize: '10px', color: 'var(--text-dim)' }}>Touch Bounding Offsets</span>
            </div>

            <div className="glass-card stat-accent-card" style={{ padding: '20px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '700', textTransform: 'uppercase' }}>Swipe Velocity</span>
                <Hand size={18} color="#10b981" />
              </div>
              <div style={{ fontSize: '32px', fontWeight: '900', color: '#10b981', fontFamily: 'var(--font-display)', margin: '8px 0 2px' }}>
                {calculatedVelocity} <span style={{ fontSize: '13px', fontWeight: '600' }}>px/s</span>
              </div>
              <span style={{ fontSize: '10px', color: '#34d399' }}>Erratic Kinetic Drift</span>
            </div>
          </div>

          {/* Research Context Notice */}
          <div style={{ background: 'rgba(255,87,34,0.06)', border: '1px solid rgba(255,87,34,0.25)', borderRadius: '16px', padding: '18px 22px', fontSize: '12px', color: 'var(--text-body)', display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
            <Activity size={20} color="var(--accent-orange-bright)" style={{ flexShrink: 0, marginTop: '2px' }} />
            <div>
              <strong style={{ color: '#fff' }}>Biomechanical Motor Formulation</strong>
              <div style={{ color: 'var(--text-muted)', marginTop: '4px', lineHeight: '1.55' }}>
                Operationalizes Fitts's Law spatial variance: <code>MT = a + b · log₂(2D/W)</code>. Under cognitive stress, touch coordinates receive continuous Gaussian perturbation modeling thumb tremors and trajectory overshoot.
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: 3D Phone Mockup with Live Touch Heatmap Spot Reactions */}
        <div className="glass-card" style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '28px' }}>
          {/* Top Touch Mode Selector Pills */}
          <div style={{ display: 'inline-flex', background: 'rgba(255,255,255,0.04)', borderRadius: '30px', padding: '4px', marginBottom: '22px', border: '1px solid rgba(255,255,255,0.08)' }}>
            <button className={`nav-link ${activeTouchType === 'taps' ? 'active' : ''}`} onClick={() => setActiveTouchType('taps')} style={{ borderRadius: '24px', padding: '6px 18px', fontSize: '12px' }}>
              Frantic Taps
            </button>
            <button className={`nav-link ${activeTouchType === 'swipes' ? 'active' : ''}`} onClick={() => setActiveTouchType('swipes')} style={{ borderRadius: '24px', padding: '6px 18px', fontSize: '12px' }}>
              Erratic Swipes
            </button>
            <button className={`nav-link ${activeTouchType === 'dead' ? 'active' : ''}`} onClick={() => setActiveTouchType('dead')} style={{ borderRadius: '24px', padding: '6px 18px', fontSize: '12px' }}>
              Dead Clicks
            </button>
          </div>

          {/* 3D Mobile Phone Frame */}
          <div className="phone-device-3d" style={{ borderColor: '#1c1c24' }}>
            <div className="phone-dynamic-island" />
            <div className="phone-viewport" style={{ background: '#f8fafc', color: '#0f172a', position: 'relative' }}>
              {/* Dynamic Touch Heatmap Gradient Spot based on mode */}
              <div
                style={{
                  position: 'absolute',
                  top: activeTouchType === 'taps' ? '45%' : activeTouchType === 'swipes' ? '30%' : '75%',
                  left: activeTouchType === 'taps' ? '40%' : activeTouchType === 'swipes' ? '50%' : '35%',
                  width: `${85 + (frustration * 0.9)}px`,
                  height: `${85 + (frustration * 0.9)}px`,
                  background: activeTouchType === 'dead'
                    ? 'radial-gradient(circle, rgba(239,68,68,0.95) 0%, rgba(245,158,11,0.65) 45%, transparent 75%)'
                    : 'radial-gradient(circle, rgba(255,87,34,0.9) 0%, rgba(16,185,129,0.55) 45%, transparent 75%)',
                  filter: 'blur(12px)',
                  mixBlendMode: 'multiply',
                  pointerEvents: 'none',
                  zIndex: 15,
                  transform: 'translate(-50%, -50%)',
                  transition: 'all 0.3s cubic-bezier(0.16, 1, 0.3, 1)'
                }}
              />

              {/* Animated Live Tap Ripple Dot when simulating */}
              {isSimulating && (
                <div
                  style={{
                    position: 'absolute',
                    top: `${42 + (Math.sin(playbackTime * 4) * 20)}%`,
                    left: `${50 + (Math.cos(playbackTime * 4) * 25)}%`,
                    width: '20px',
                    height: '20px',
                    borderRadius: '50%',
                    background: '#ef4444',
                    boxShadow: '0 0 24px #ef4444, 0 0 8px #fff',
                    zIndex: 25,
                    pointerEvents: 'none',
                    transform: 'translate(-50%, -50%)'
                  }}
                />
              )}

              {/* Status Bar */}
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#475569', marginBottom: '14px', position: 'relative', zIndex: 20 }}>
                <span style={{ fontWeight: '600' }}>10:09</span>
                <span style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                  <Wifi size={12} />
                  <Battery size={12} />
                </span>
              </div>

              {/* Mock App UI */}
              <div style={{ textAlign: 'center', margin: '14px 0', position: 'relative', zIndex: 20 }}>
                <h3 style={{ fontSize: '20px', fontWeight: '900', color: '#0f172a' }}>Member Login</h3>
                <p style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>
                  Please select your account to continue.
                </p>
              </div>

              <div style={{ display: 'flex', gap: '6px', marginBottom: '16px', position: 'relative', zIndex: 20 }}>
                <button style={{ flex: 1, background: '#ea580c', color: '#fff', border: 'none', padding: '8px', borderRadius: '8px', fontSize: '11px', fontWeight: '700' }}>Personal</button>
                <button style={{ flex: 1, background: '#e2e8f0', color: '#334155', border: 'none', padding: '8px', borderRadius: '8px', fontSize: '11px' }}>Business</button>
                <button style={{ flex: 1, background: '#e2e8f0', color: '#334155', border: 'none', padding: '8px', borderRadius: '8px', fontSize: '11px' }}>Merchant</button>
              </div>

              <div style={{ background: '#fff', border: '1px solid #cbd5e1', borderRadius: '10px', padding: '10px 14px', marginBottom: '10px', textAlign: 'left', position: 'relative', zIndex: 20, boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
                <div style={{ fontSize: '10px', color: '#94a3b8', fontWeight: '600', textTransform: 'uppercase' }}>Email address</div>
                <div style={{ fontSize: '12px', color: '#0f172a', marginTop: '2px', fontWeight: '500' }}>alex.johnson@email.com</div>
              </div>

              <div style={{ background: '#fff', border: '1px solid #cbd5e1', borderRadius: '10px', padding: '10px 14px', marginBottom: '16px', textAlign: 'left', position: 'relative', zIndex: 20, boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
                <div style={{ fontSize: '10px', color: '#94a3b8', fontWeight: '600', textTransform: 'uppercase' }}>Passcode</div>
                <div style={{ fontSize: '12px', color: '#0f172a', marginTop: '2px', letterSpacing: '2px' }}>••••••••</div>
              </div>

              <button style={{ width: '100%', background: 'linear-gradient(135deg, #ea580c, #c2410c)', color: '#fff', border: 'none', padding: '12px', borderRadius: '10px', fontWeight: '700', fontSize: '13px', marginTop: 'auto', position: 'relative', zIndex: 20, boxShadow: '0 4px 14px rgba(234,88,12,0.4)' }}>
                Continue Login
              </button>
            </div>
          </div>

          {/* Interactive Playback Scrubber Bar */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px', width: '100%', maxWidth: '320px', marginTop: '20px' }}>
            <div
              onClick={toggleSimulation}
              style={{ width: '38px', height: '38px', borderRadius: '50%', background: 'linear-gradient(135deg, #ff5722, #e64a19)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', boxShadow: '0 0 16px rgba(255,87,34,0.5)', flexShrink: 0 }}
            >
              {isSimulating ? <Pause size={16} /> : <Play size={16} />}
            </div>
            <input
              type="range"
              min="0"
              max="10"
              step="0.1"
              value={playbackTime}
              onChange={(e) => setPlaybackTime(Number(e.target.value))}
              style={{ flex: 1 }}
            />
            <span style={{ fontSize: '12px', color: 'var(--accent-orange-bright)', fontFamily: 'var(--font-mono)', width: '42px', fontWeight: '700' }}>
              {playbackTime.toFixed(1)}s
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
