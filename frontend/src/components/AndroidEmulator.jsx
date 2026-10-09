import React, { useState, useEffect } from 'react';
import {
  Smartphone,
  Wifi,
  WifiOff,
  Battery,
  BatteryWarning,
  BatteryCharging,
  PhoneCall,
  PhoneOff,
  RotateCw,
  Power,
  Volume2,
  VolumeX,
  ShoppingCart,
  CreditCard,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Play,
  Pause,
  ArrowLeft,
  Home,
  Square,
  ShieldAlert,
  Flame,
  Zap,
  Layers,
  Terminal,
  Activity,
  Sliders,
  Sparkles
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export default function AndroidEmulator({
  config = {},
  isSimulating = true,
  onToggleSimulation,
  activePerturbations = []
}) {
  // Emulator State
  const [isPowered, setIsPowered] = useState(true);
  const [orientation, setOrientation] = useState('portrait'); // portrait | landscape
  const [activeApp, setActiveApp] = useState('swiftpay'); // swiftpay | home | recents | settings
  const [screenFlow, setScreenFlow] = useState('cart'); // cart | checkout | processing | success | anr
  const [currentTime, setCurrentTime] = useState('10:42');
  const [batteryLevel, setBatteryLevel] = useState(82);
  const [isCharging, setIsCharging] = useState(false);
  
  // Real-time perturbation & touch simulation state
  const [tapPosition, setTapPosition] = useState(null);
  const [fps, setFps] = useState(60);
  const [droppedFrames, setDroppedFrames] = useState(0);
  const [incomingCall, setIncomingCall] = useState(null);
  const [headsUpToast, setHeadsUpToast] = useState(null);
  const [cartCount, setCartCount] = useState(2);
  const [transactionAmount, setTransactionAmount] = useState('647.00');

  const cpuStress = config?.cpuStress || 85;
  const ramStress = config?.ramStress || 75;
  const latency = config?.latency || 1250;

  // Real-time Clock Sync
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      const hrs = String(now.getHours()).padStart(2, '0');
      const mins = String(now.getMinutes()).padStart(2, '0');
      setCurrentTime(`${hrs}:${mins}`);
    };
    updateTime();
    const timer = setInterval(updateTime, 10000);
    return () => clearInterval(timer);
  }, []);

  // Compute live simulated FPS based on CPU Stress
  useEffect(() => {
    if (!isPowered) return;
    const interval = setInterval(() => {
      if (cpuStress > 85) {
        const jitterFps = Math.floor(Math.random() * 12) + 12; // 12 - 24 FPS
        setFps(jitterFps);
        setDroppedFrames(prev => prev + Math.floor(Math.random() * 4) + 2);
      } else if (cpuStress > 60) {
        const jitterFps = Math.floor(Math.random() * 15) + 38; // 38 - 53 FPS
        setFps(jitterFps);
      } else {
        setFps(59 + (Math.random() > 0.5 ? 1 : 0));
      }
    }, 1200);
    return () => clearInterval(interval);
  }, [cpuStress, isPowered]);

  // Automated Synthetic Touch Stream & Screen Progression
  useEffect(() => {
    if (!isSimulating || !isPowered || activeApp !== 'swiftpay') return;

    let step = 0;
    const actionInterval = setInterval(() => {
      step = (step + 1) % 6;

      if (step === 1) {
        // Tap Checkout
        setTapPosition({ x: 155, y: 520, label: 'ADB Tap: "Checkout ($647.00)"' });
        setTimeout(() => {
          setTapPosition(null);
          setScreenFlow('checkout');
        }, 600);
      } else if (step === 2) {
        // Tap Payment Method (Google Pay)
        setTapPosition({ x: 140, y: 340, label: 'ADB Tap: "Google Pay"' });
        setTimeout(() => setTapPosition(null), 500);
      } else if (step === 3) {
        // Tap Confirm Payment
        setTapPosition({ x: 155, y: 510, label: 'ADB Tap: "Authorize Payment"' });
        setTimeout(() => {
          setTapPosition(null);
          setScreenFlow('processing');
        }, 600);
      } else if (step === 4) {
        // Check if CPU / Latency triggers ANR or completes
        if (cpuStress >= 85 || latency >= 1500) {
          // Trigger ANR Freeze
          setScreenFlow('anr');
          setHeadsUpToast({
            title: 'Android System: LowMemoryKiller',
            body: 'LMK killed background services to reclaim 140MB RAM.',
            type: 'warning'
          });
        } else {
          setScreenFlow('success');
        }
      } else if (step === 5) {
        // Reset back to cart
        setTimeout(() => {
          setScreenFlow('cart');
        }, 1800);
      }
    }, 3200);

    return () => clearInterval(actionInterval);
  }, [isSimulating, isPowered, activeApp, cpuStress, latency]);

  // Watch for active perturbations to trigger heads-up alerts
  useEffect(() => {
    if (activePerturbations.includes('GSM_CALL')) {
      triggerIncomingCall();
    }
  }, [activePerturbations]);

  const triggerIncomingCall = () => {
    setIncomingCall({
      name: 'Unknown Caller',
      number: '+1 (555) 019-2831',
      time: 'Just now'
    });
  };

  const dismissCall = () => {
    setIncomingCall(null);
  };

  const triggerManualTap = (e) => {
    if (!isPowered) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = Math.round(e.clientX - rect.left);
    const y = Math.round(e.clientY - rect.top);
    setTapPosition({ x, y, label: `ADB Input (X:${x}, Y:${y})` });
    setTimeout(() => setTapPosition(null), 700);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px', width: '100%' }}>
      {/* Emulator Header Status Bar & Quick Actions */}
      <div style={{
        width: '100%',
        maxWidth: orientation === 'portrait' ? '360px' : '620px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        background: 'rgba(15, 23, 42, 0.75)',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        borderRadius: '14px',
        padding: '8px 14px',
        backdropFilter: 'blur(10px)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: isPowered ? '#10b981' : '#64748b', boxShadow: isPowered ? '0 0 8px #10b981' : 'none' }} />
          <span style={{ fontSize: '11px', fontWeight: '800', color: '#fff' }}>Pixel 7 Pro</span>
          <span style={{ fontSize: '10px', color: 'var(--text-dim)' }}>API 34 • ADB :5554</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <button
            onClick={() => setOrientation(prev => prev === 'portrait' ? 'landscape' : 'portrait')}
            title="Rotate Device (Portrait / Landscape)"
            style={{
              background: 'rgba(255, 255, 255, 0.06)',
              border: 'none',
              borderRadius: '8px',
              padding: '5px 8px',
              color: 'var(--text-dim)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              fontSize: '11px'
            }}
          >
            <RotateCw size={12} />
          </button>

          <button
            onClick={() => setIsPowered(!isPowered)}
            title={isPowered ? 'Lock / Standby' : 'Power On'}
            style={{
              background: isPowered ? 'rgba(251, 146, 60, 0.15)' : 'rgba(255, 255, 255, 0.06)',
              border: 'none',
              borderRadius: '8px',
              padding: '5px 8px',
              color: isPowered ? 'var(--accent-orange-bright)' : 'var(--text-dim)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              fontSize: '11px'
            }}
          >
            <Power size={12} />
          </button>

          {onToggleSimulation && (
            <button
              onClick={onToggleSimulation}
              title={isSimulating ? 'Pause Automated Simulation' : 'Resume Simulation'}
              style={{
                background: isSimulating ? 'rgba(56, 189, 248, 0.15)' : 'rgba(255, 255, 255, 0.06)',
                border: 'none',
                borderRadius: '8px',
                padding: '5px 8px',
                color: isSimulating ? 'var(--accent-cyan-bright)' : 'var(--text-dim)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                fontSize: '11px'
              }}
            >
              {isSimulating ? <Pause size={12} /> : <Play size={12} />}
            </button>
          )}
        </div>
      </div>

      {/* Realistic Mobile Device Frame Outer Wrapper */}
      <div style={{ position: 'relative', display: 'inline-block' }}>
        {/* Left Edge Hardware Buttons (Volume Rocker) */}
        <div style={{
          position: 'absolute',
          left: '-5px',
          top: '110px',
          width: '5px',
          height: '42px',
          background: '#2a334a',
          borderRadius: '4px 0 0 4px',
          boxShadow: 'inset 0 1px 1px rgba(255,255,255,0.2)'
        }} />
        <div style={{
          position: 'absolute',
          left: '-5px',
          top: '165px',
          width: '5px',
          height: '42px',
          background: '#2a334a',
          borderRadius: '4px 0 0 4px',
          boxShadow: 'inset 0 1px 1px rgba(255,255,255,0.2)'
        }} />

        {/* Right Edge Hardware Button (Power / Lock) */}
        <div style={{
          position: 'absolute',
          right: '-5px',
          top: '130px',
          width: '5px',
          height: '52px',
          background: '#2a334a',
          borderRadius: '0 4px 4px 0',
          boxShadow: 'inset 0 1px 1px rgba(255,255,255,0.2)',
          cursor: 'pointer'
        }}
        onClick={() => setIsPowered(!isPowered)}
        title="Hardware Power Button"
        />

        {/* The Real Android Chassis Container */}
        <div
          style={{
            width: orientation === 'portrait' ? '330px' : '590px',
            height: orientation === 'portrait' ? '650px' : '360px',
            background: '#0a0d14',
            borderRadius: '42px',
            border: '9px solid #1a2233',
            boxShadow: `
              0 30px 80px -15px rgba(0, 0, 0, 0.95),
              0 0 40px rgba(251, 146, 60, 0.18),
              inset 0 0 0 1px rgba(255, 255, 255, 0.15)
            `,
            position: 'relative',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
            transition: 'all 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
            userSelect: 'none'
          }}
          onClick={triggerManualTap}
        >
          {/* Top Speaker Ear-Piece Slit */}
          <div style={{
            position: 'absolute',
            top: '8px',
            left: '50%',
            transform: 'translateX(-50%)',
            width: '46px',
            height: '3px',
            background: '#222b3d',
            borderRadius: '3px',
            zIndex: 40
          }} />

          {/* Centered Pixel Front Punch-Hole Camera */}
          <div style={{
            position: 'absolute',
            top: '14px',
            left: '50%',
            transform: 'translateX(-50%)',
            width: '11px',
            height: '11px',
            borderRadius: '50%',
            background: '#05070d',
            border: '1px solid rgba(255, 255, 255, 0.12)',
            boxShadow: 'inset 0 0 2px #38bdf8',
            zIndex: 40
          }} />

          {/* Screen Glass Reflection Gradient Overlay */}
          <div style={{
            position: 'absolute',
            inset: 0,
            background: 'linear-gradient(135deg, rgba(255,255,255,0.05) 0%, transparent 40%, rgba(255,255,255,0.01) 100%)',
            pointerEvents: 'none',
            zIndex: 35
          }} />

          {/* Screen Power Off State */}
          {!isPowered ? (
            <div style={{
              flex: 1,
              background: '#04060a',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '12px',
              color: 'var(--text-dim)',
              fontSize: '12px'
            }}>
              <Power size={28} color="#334155" />
              <span>Device Locked</span>
              <button
                onClick={(e) => { e.stopPropagation(); setIsPowered(true); }}
                className="btn-secondary"
                style={{ fontSize: '11px', padding: '6px 14px' }}
              >
                Wake Pixel 7
              </button>
            </div>
          ) : (
            <>
              {/* Android 14 System Status Bar */}
              <div style={{
                height: '32px',
                padding: '0 16px',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                fontSize: '11px',
                fontWeight: '700',
                color: '#fff',
                background: 'rgba(10, 13, 20, 0.85)',
                backdropFilter: 'blur(8px)',
                zIndex: 30,
                borderBottom: '1px solid rgba(255, 255, 255, 0.04)'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span>{currentTime}</span>
                  {activePerturbations.length > 0 && (
                    <span style={{
                      fontSize: '8.5px',
                      background: 'rgba(251, 146, 60, 0.25)',
                      color: 'var(--accent-orange-bright)',
                      padding: '1px 4px',
                      borderRadius: '4px',
                      fontWeight: '800'
                    }}>
                      STRESS
                    </span>
                  )}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  {/* Network / Wi-Fi indicator */}
                  <span style={{ fontSize: '9px', color: latency > 1000 ? '#fbbf24' : '#94a3b8', fontWeight: '800' }}>
                    {latency > 1000 ? '3G Handoff' : '5G-SA'}
                  </span>
                  {latency > 1000 ? (
                    <WifiOff size={12} color="#fbbf24" />
                  ) : (
                    <Wifi size={12} color="#10b981" />
                  )}

                  {/* Battery Indicator */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '3px', fontSize: '9.5px', color: cpuStress > 85 ? '#f43f5e' : '#cbd5e1' }}>
                    <span>{cpuStress > 85 ? '10%' : `${batteryLevel}%`}</span>
                    {cpuStress > 85 ? (
                      <BatteryWarning size={13} color="#f43f5e" />
                    ) : (
                      <Battery size={13} color="#10b981" />
                    )}
                  </div>
                </div>
              </div>

              {/* Live Overlay: FPS Counter & ADB Coordinates Badge */}
              <div style={{
                position: 'absolute',
                top: '36px',
                left: '12px',
                zIndex: 25,
                display: 'flex',
                gap: '6px',
                pointerEvents: 'none'
              }}>
                <div style={{
                  background: 'rgba(0, 0, 0, 0.75)',
                  border: `1px solid ${fps < 25 ? '#f43f5e' : fps < 45 ? '#fbbf24' : '#10b981'}`,
                  borderRadius: '6px',
                  padding: '2px 6px',
                  fontSize: '9px',
                  fontWeight: '800',
                  color: fps < 25 ? '#f43f5e' : fps < 45 ? '#fbbf24' : '#10b981',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px'
                }}>
                  <Activity size={9} />
                  <span>{fps} FPS</span>
                  {fps < 25 && <span style={{ color: '#fff', fontSize: '8px' }}>• JANK</span>}
                </div>
              </div>

              {/* Heads-Up Toast Notification Popup */}
              <AnimatePresence>
                {headsUpToast && (
                  <motion.div
                    initial={{ y: -40, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    exit={{ y: -40, opacity: 0 }}
                    style={{
                      position: 'absolute',
                      top: '38px',
                      left: '12px',
                      right: '12px',
                      background: 'rgba(15, 23, 42, 0.95)',
                      border: '1px solid rgba(251, 146, 60, 0.4)',
                      borderRadius: '12px',
                      padding: '10px 12px',
                      zIndex: 35,
                      boxShadow: '0 8px 24px rgba(0,0,0,0.6)',
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: '8px'
                    }}
                    onClick={(e) => { e.stopPropagation(); setHeadsUpToast(null); }}
                  >
                    <AlertTriangle size={15} color="#fb923c" style={{ flexShrink: 0, marginTop: '2px' }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: '11px', fontWeight: '800', color: '#fff' }}>{headsUpToast.title}</div>
                      <div style={{ fontSize: '9.5px', color: 'var(--text-dim)', marginTop: '1px' }}>{headsUpToast.body}</div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Heads-Up Incoming Call Overlay */}
              <AnimatePresence>
                {incomingCall && (
                  <motion.div
                    initial={{ y: -60, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    exit={{ y: -60, opacity: 0 }}
                    style={{
                      position: 'absolute',
                      top: '38px',
                      left: '10px',
                      right: '10px',
                      background: '#13192b',
                      border: '1px solid rgba(56, 189, 248, 0.5)',
                      borderRadius: '16px',
                      padding: '12px',
                      zIndex: 38,
                      boxShadow: '0 12px 30px rgba(0,0,0,0.8)'
                    }}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <div style={{ width: '32px', height: '32px', borderRadius: '50%', background: 'rgba(56, 189, 248, 0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                          <PhoneCall size={16} color="#38bdf8" />
                        </div>
                        <div>
                          <div style={{ fontSize: '11.5px', fontWeight: '800', color: '#fff' }}>{incomingCall.name}</div>
                          <div style={{ fontSize: '9.5px', color: 'var(--text-dim)' }}>{incomingCall.number}</div>
                        </div>
                      </div>

                      <div style={{ display: 'flex', gap: '6px' }}>
                        <button
                          onClick={dismissCall}
                          style={{
                            background: '#ef4444',
                            border: 'none',
                            borderRadius: '50%',
                            width: '28px',
                            height: '28px',
                            color: '#fff',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            cursor: 'pointer'
                          }}
                        >
                          <PhoneOff size={13} />
                        </button>
                        <button
                          onClick={dismissCall}
                          style={{
                            background: '#10b981',
                            border: 'none',
                            borderRadius: '50%',
                            width: '28px',
                            height: '28px',
                            color: '#fff',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            cursor: 'pointer'
                          }}
                        >
                          <PhoneCall size={13} />
                        </button>
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Main Android Screen Viewport */}
              <div style={{
                flex: 1,
                background: '#0d111c',
                overflowY: 'auto',
                position: 'relative',
                display: 'flex',
                flexDirection: 'column'
              }}>
                {/* Synthetic ADB Touch Pointer Ripple Indicator */}
                {tapPosition && (
                  <motion.div
                    initial={{ scale: 0.2, opacity: 1 }}
                    animate={{ scale: 1.5, opacity: 0 }}
                    transition={{ duration: 0.6 }}
                    style={{
                      position: 'absolute',
                      top: `${tapPosition.y}px`,
                      left: `${tapPosition.x}px`,
                      width: '32px',
                      height: '32px',
                      borderRadius: '50%',
                      background: 'radial-gradient(circle, rgba(251,146,60,0.9) 0%, rgba(251,146,60,0.2) 60%, transparent 100%)',
                      border: '2px solid #fb923c',
                      boxShadow: '0 0 16px #fb923c',
                      transform: 'translate(-50%, -50%)',
                      pointerEvents: 'none',
                      zIndex: 35
                    }}
                  />
                )}

                {/* APP VIEW 1: SwiftPay Wallet & Checkout (Themis Benchmark app) */}
                {activeApp === 'swiftpay' && (
                  <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '16px 14px' }}>
                    {/* App Navbar */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <div style={{ width: '26px', height: '26px', borderRadius: '8px', background: 'linear-gradient(135deg, #fb923c, #ea580c)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontWeight: '900', fontSize: '13px' }}>
                          S
                        </div>
                        <div>
                          <div style={{ fontSize: '12px', fontWeight: '900', color: '#fff' }}>SwiftPay</div>
                          <div style={{ fontSize: '9px', color: 'var(--text-dim)' }}>v2.4.1 • In-App Store</div>
                        </div>
                      </div>

                      <div style={{ position: 'relative' }}>
                        <ShoppingCart size={16} color="#cbd5e1" />
                        <span style={{
                          position: 'absolute',
                          top: '-6px',
                          right: '-6px',
                          background: '#fb923c',
                          color: '#fff',
                          fontSize: '8px',
                          fontWeight: '800',
                          borderRadius: '50%',
                          width: '13px',
                          height: '13px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center'
                        }}>
                          {cartCount}
                        </span>
                      </div>
                    </div>

                    {/* SCREEN FLOW: Cart State */}
                    {screenFlow === 'cart' && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', flex: 1 }}>
                        <div style={{ fontSize: '11px', fontWeight: '800', color: 'var(--text-dim)', textTransform: 'uppercase' }}>
                          Cart Summary
                        </div>

                        {/* Item 1 */}
                        <div style={{ background: '#161c2e', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '12px', padding: '10px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <div>
                            <div style={{ fontSize: '11.5px', fontWeight: '700', color: '#fff' }}>Sony WH-1000XM5</div>
                            <div style={{ fontSize: '9.5px', color: 'var(--text-dim)' }}>ANC Headphones • Qty: 1</div>
                          </div>
                          <div style={{ fontSize: '12px', fontWeight: '900', color: 'var(--accent-orange-bright)' }}>$348.00</div>
                        </div>

                        {/* Item 2 */}
                        <div style={{ background: '#161c2e', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '12px', padding: '10px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <div>
                            <div style={{ fontSize: '11.5px', fontWeight: '700', color: '#fff' }}>Pixel Watch 2 LTE</div>
                            <div style={{ fontSize: '9.5px', color: 'var(--text-dim)' }}>Matte Black • Qty: 1</div>
                          </div>
                          <div style={{ fontSize: '12px', fontWeight: '900', color: 'var(--accent-orange-bright)' }}>$299.00</div>
                        </div>

                        {/* Promo / Coupon Box */}
                        <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px dashed rgba(255,255,255,0.1)', borderRadius: '10px', padding: '8px 10px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '10px' }}>
                          <span style={{ color: 'var(--text-dim)' }}>Code: HEART_CHAOS</span>
                          <span style={{ color: '#10b981', fontWeight: '700' }}>-$0.00 (No Discount)</span>
                        </div>

                        <div style={{ marginTop: 'auto', paddingTop: '10px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '8px' }}>
                            <span style={{ color: 'var(--text-dim)' }}>Order Total:</span>
                            <span style={{ fontWeight: '900', color: '#fff', fontSize: '14px' }}>${transactionAmount}</span>
                          </div>

                          <button
                            onClick={(e) => { e.stopPropagation(); setScreenFlow('checkout'); }}
                            style={{
                              width: '100%',
                              background: 'linear-gradient(135deg, #fb923c, #ea580c)',
                              color: '#fff',
                              border: 'none',
                              borderRadius: '12px',
                              padding: '12px',
                              fontSize: '12px',
                              fontWeight: '800',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              gap: '6px',
                              boxShadow: '0 4px 16px rgba(251, 146, 60, 0.3)'
                            }}
                          >
                            <CreditCard size={14} /> Checkout (${transactionAmount})
                          </button>
                        </div>
                      </div>
                    )}

                    {/* SCREEN FLOW: Checkout State */}
                    {screenFlow === 'checkout' && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', flex: 1 }}>
                        <div style={{ fontSize: '11px', fontWeight: '800', color: 'var(--text-dim)', textTransform: 'uppercase' }}>
                          Payment Gateway
                        </div>

                        <div style={{ background: '#161c2e', borderRadius: '12px', padding: '12px', border: '1px solid rgba(251,146,60,0.3)' }}>
                          <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>Selected Payment:</div>
                          <div style={{ fontSize: '13px', fontWeight: '800', color: '#fff', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <Zap size={14} color="#fb923c" /> Google Pay •••• 4022
                          </div>
                        </div>

                        <div style={{ background: '#161c2e', borderRadius: '12px', padding: '12px', border: '1px solid rgba(255,255,255,0.06)' }}>
                          <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>Delivery Address:</div>
                          <div style={{ fontSize: '12px', fontWeight: '700', color: '#cbd5e1', marginTop: '4px' }}>
                            742 Evergreen Terrace, Sector 4
                          </div>
                        </div>

                        <div style={{ marginTop: 'auto', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                          <button
                            onClick={(e) => { e.stopPropagation(); setScreenFlow('processing'); }}
                            style={{
                              width: '100%',
                              background: 'linear-gradient(135deg, #fb923c, #ea580c)',
                              color: '#fff',
                              border: 'none',
                              borderRadius: '12px',
                              padding: '12px',
                              fontSize: '12px',
                              fontWeight: '800',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              gap: '6px'
                            }}
                          >
                            Authorize Payment
                          </button>

                          <button
                            onClick={(e) => { e.stopPropagation(); setScreenFlow('cart'); }}
                            style={{
                              background: 'transparent',
                              border: 'none',
                              color: 'var(--text-dim)',
                              fontSize: '11px',
                              cursor: 'pointer',
                              padding: '6px'
                            }}
                          >
                            Cancel & Return
                          </button>
                        </div>
                      </div>
                    )}

                    {/* SCREEN FLOW: Mid-Transaction Processing */}
                    {screenFlow === 'processing' && (
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', flex: 1, gap: '14px', textAlign: 'center' }}>
                        <div style={{
                          width: '54px',
                          height: '54px',
                          borderRadius: '50%',
                          border: '3px solid rgba(251,146,60,0.2)',
                          borderTopColor: '#fb923c',
                          animation: 'spin 0.8s linear infinite'
                        }} />
                        <div>
                          <div style={{ fontSize: '13px', fontWeight: '800', color: '#fff' }}>Authorizing Transaction...</div>
                          <div style={{ fontSize: '10px', color: 'var(--text-dim)', marginTop: '4px' }}>
                            Dispatching SSL token to Payment Handoff Service
                          </div>
                        </div>
                        {latency > 1000 && (
                          <div style={{ background: 'rgba(251,191,36,0.1)', border: '1px solid rgba(251,191,36,0.3)', borderRadius: '8px', padding: '6px 10px', fontSize: '9.5px', color: '#fbbf24' }}>
                            Warning: RTT Latency {latency}ms (Handoff Degraded)
                          </div>
                        )}
                      </div>
                    )}

                    {/* SCREEN FLOW: Success Receipt */}
                    {screenFlow === 'success' && (
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', flex: 1, gap: '12px', textAlign: 'center' }}>
                        <div style={{ width: '50px', height: '50px', borderRadius: '50%', background: 'rgba(16, 185, 129, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                          <CheckCircle2 size={30} color="#10b981" />
                        </div>
                        <div>
                          <div style={{ fontSize: '14px', fontWeight: '900', color: '#fff' }}>Payment Complete!</div>
                          <div style={{ fontSize: '10.5px', color: 'var(--text-dim)', marginTop: '2px' }}>
                            Order #HEART-94281 Verified
                          </div>
                        </div>
                        <button
                          onClick={(e) => { e.stopPropagation(); setScreenFlow('cart'); }}
                          className="btn-secondary"
                          style={{ fontSize: '11px', padding: '6px 14px', marginTop: '10px' }}
                        >
                          New Transaction
                        </button>
                      </div>
                    )}

                    {/* SCREEN FLOW: Android System ANR Crash Dialog Overlay */}
                    {screenFlow === 'anr' && (
                      <div style={{
                        position: 'absolute',
                        inset: 0,
                        background: 'rgba(0, 0, 0, 0.75)',
                        backdropFilter: 'blur(4px)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        padding: '16px',
                        zIndex: 35
                      }}>
                        <div style={{
                          background: '#181d2c',
                          border: '1px solid rgba(244, 63, 94, 0.5)',
                          borderRadius: '16px',
                          padding: '18px 16px',
                          width: '100%',
                          maxWidth: '260px',
                          boxShadow: '0 16px 36px rgba(0,0,0,0.8)'
                        }}>
                          <div style={{ fontSize: '13px', fontWeight: '900', color: '#fff', display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <ShieldAlert size={16} color="#f43f5e" /> App isn't responding
                          </div>
                          <div style={{ fontSize: '10.5px', color: 'var(--text-dim)', marginTop: '8px', lineHeight: 1.4 }}>
                            "SwiftPay Mobile" isn't responding due to CPU governor throttle (Thread: main).
                          </div>

                          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '16px' }}>
                            <button
                              onClick={(e) => { e.stopPropagation(); setScreenFlow('cart'); }}
                              style={{
                                background: 'transparent',
                                border: 'none',
                                color: 'var(--accent-cyan-bright)',
                                fontSize: '11px',
                                fontWeight: '700',
                                cursor: 'pointer',
                                padding: '4px 8px'
                              }}
                            >
                              Wait
                            </button>
                            <button
                              onClick={(e) => { e.stopPropagation(); setActiveApp('home'); setScreenFlow('cart'); }}
                              style={{
                                background: 'rgba(244, 63, 94, 0.2)',
                                border: 'none',
                                color: '#fb7185',
                                borderRadius: '6px',
                                fontSize: '11px',
                                fontWeight: '700',
                                cursor: 'pointer',
                                padding: '6px 10px'
                              }}
                            >
                              Close App
                            </button>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* APP VIEW 2: Android Home Launcher Grid */}
                {activeApp === 'home' && (
                  <div style={{ flex: 1, padding: '24px 16px', display: 'flex', flexDirection: 'column' }}>
                    {/* Clock & Weather Widget */}
                    <div style={{ textAlign: 'center', margin: '20px 0 30px' }}>
                      <div style={{ fontSize: '38px', fontWeight: '900', color: '#fff', fontFamily: 'var(--font-display)', letterSpacing: '-1px' }}>
                        {currentTime}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>
                        Wednesday, Oct 7 • 28°C Sunny
                      </div>
                    </div>

                    {/* App Icons Grid */}
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px 10px', marginTop: 'auto', marginBottom: '24px' }}>
                      {/* SwiftPay App */}
                      <div
                        onClick={(e) => { e.stopPropagation(); setActiveApp('swiftpay'); }}
                        style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px', cursor: 'pointer' }}
                      >
                        <div style={{ width: '42px', height: '42px', borderRadius: '12px', background: 'linear-gradient(135deg, #fb923c, #ea580c)', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 4px 12px rgba(251,146,60,0.3)' }}>
                          <span style={{ color: '#fff', fontWeight: '900', fontSize: '16px' }}>S</span>
                        </div>
                        <span style={{ fontSize: '9.5px', color: '#fff' }}>SwiftPay</span>
                      </div>

                      {/* HEART Agent App */}
                      <div
                        onClick={(e) => { e.stopPropagation(); setHeadsUpToast({ title: 'HEART Agent Running', body: 'Perturbation daemon connected on port 8001.' }); }}
                        style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px', cursor: 'pointer' }}
                      >
                        <div style={{ width: '42px', height: '42px', borderRadius: '12px', background: 'linear-gradient(135deg, #0284c7, #0369a1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                          <Activity size={20} color="#fff" />
                        </div>
                        <span style={{ fontSize: '9.5px', color: '#fff' }}>HEART</span>
                      </div>

                      {/* Settings App */}
                      <div
                        onClick={(e) => { e.stopPropagation(); }}
                        style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px', cursor: 'pointer' }}
                      >
                        <div style={{ width: '42px', height: '42px', borderRadius: '12px', background: '#334155', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                          <Sliders size={20} color="#94a3b8" />
                        </div>
                        <span style={{ fontSize: '9.5px', color: '#fff' }}>Settings</span>
                      </div>

                      {/* Terminal App */}
                      <div
                        onClick={(e) => { e.stopPropagation(); }}
                        style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px', cursor: 'pointer' }}
                      >
                        <div style={{ width: '42px', height: '42px', borderRadius: '12px', background: '#090d18', border: '1px solid rgba(255,255,255,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                          <Terminal size={18} color="#10b981" />
                        </div>
                        <span style={{ fontSize: '9.5px', color: '#fff' }}>ADB Log</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Bottom Android 3-Button Navigation Bar */}
              <div style={{
                height: '36px',
                background: '#090d18',
                borderTop: '1px solid rgba(255, 255, 255, 0.04)',
                display: 'flex',
                justifyContent: 'space-around',
                alignItems: 'center',
                padding: '0 30px',
                zIndex: 30
              }}>
                {/* Back Button */}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    if (screenFlow === 'checkout') setScreenFlow('cart');
                    else if (screenFlow === 'anr') setScreenFlow('cart');
                    else setActiveApp('home');
                  }}
                  title="Android Back Button"
                  style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', padding: '4px 10px' }}
                >
                  <ArrowLeft size={15} />
                </button>

                {/* Home Button */}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setActiveApp('home');
                  }}
                  title="Android Home Button"
                  style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', padding: '4px 10px' }}
                >
                  <Home size={15} />
                </button>

                {/* Recents / Multitasking Button */}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    if (activeApp === 'home') setActiveApp('swiftpay');
                    else setActiveApp('home');
                  }}
                  title="Android Recents Button"
                  style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', padding: '4px 10px' }}
                >
                  <Square size={13} />
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Hardware Toolbar Actions Underneath Mockup */}
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', justifyContent: 'center', maxWidth: '340px' }}>
        <button
          onClick={triggerIncomingCall}
          className="btn-secondary"
          style={{ fontSize: '11px', padding: '6px 12px', display: 'flex', alignItems: 'center', gap: '5px' }}
        >
          <PhoneCall size={12} color="#38bdf8" /> Inject Call
        </button>

        <button
          onClick={() => {
            setHeadsUpToast({
              title: 'Battery Alert (10%)',
              body: 'Low battery threshold intent broadcasted.',
              type: 'warning'
            });
          }}
          className="btn-secondary"
          style={{ fontSize: '11px', padding: '6px 12px', display: 'flex', alignItems: 'center', gap: '5px' }}
        >
          <BatteryWarning size={12} color="#fbbf24" /> Drop Battery
        </button>

        <button
          onClick={() => {
            setScreenFlow('anr');
          }}
          className="btn-secondary"
          style={{ fontSize: '11px', padding: '6px 12px', display: 'flex', alignItems: 'center', gap: '5px' }}
        >
          <Flame size={12} color="#f43f5e" /> Force ANR
        </button>

        <button
          onClick={() => {
            setActiveApp('swiftpay');
            setScreenFlow('cart');
          }}
          className="btn-secondary"
          style={{ fontSize: '11px', padding: '6px 12px', display: 'flex', alignItems: 'center', gap: '5px' }}
        >
          <RefreshCw size={12} /> Restart App
        </button>
      </div>
    </div>
  );
}
