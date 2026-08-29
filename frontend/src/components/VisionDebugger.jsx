import React, { useState } from 'react';
import { Eye, AlertTriangle, CheckCircle2, RefreshCw, Smartphone, ArrowRight, Layers, Box, Cpu, Crosshair, ShieldAlert, FileText, ShoppingCart, UserCheck, Grid, CreditCard, ChevronRight } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export default function VisionDebugger({ onGoToAttribution }) {
  const [selectedScreenId, setSelectedScreenId] = useState('checkout');
  const [selectedBox, setSelectedBox] = useState('defect_box');
  const [isScanning, setIsScanning] = useState(false);
  const [scanComplete, setScanComplete] = useState(true);

  // Multi-Screen Ground Truth Database
  const screens = [
    {
      id: 'checkout',
      title: 'Payment Checkout',
      category: 'E-Commerce',
      icon: CreditCard,
      defectCount: 1,
      defectType: 'UI Element Occlusion / Overlap',
      severity: 'Critical',
      iou: '0.382',
      injectedStress: 'CPU 85% + Netem 3G Flaky Handoff',
      targetNode: 'android.widget.Button (btn_confirm)',
      collidingNode: 'android.widget.TextView (banner_voucher)',
      vlmInsight: 'Severe bounding box collision detected. <VoucherBanner> [42, 310, 280, 45] occludes 38.2% of <ConfirmButton> [50, 337, 270, 52]. Asynchronous translate animation halted under CPU governor throttle.',
      renderUi: (selected, onSelect) => (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
          <div style={{ fontSize: '15px', fontWeight: '800', marginBottom: '14px', textAlign: 'center' }}>Payment Checkout</div>

          <div style={{ background: '#1c2234', borderRadius: '12px', padding: '12px 14px', marginBottom: '10px', border: '1px solid rgba(255,255,255,0.08)' }}>
            <div style={{ fontSize: '10px', color: '#94a3b8', fontWeight: '700', textTransform: 'uppercase' }}>Subtotal Balance</div>
            <div style={{ fontSize: '18px', fontWeight: '900', color: 'var(--accent-cyan-bright)', marginTop: '2px' }}>$84.50 USD</div>
          </div>

          <div style={{ background: '#1c2234', borderRadius: '12px', padding: '10px 14px', marginBottom: '14px', border: '1px solid rgba(255,255,255,0.08)', fontSize: '11px', color: '#cbd5e1' }}>
            <div>💳 Express Visa •••• 4242</div>
          </div>

          {/* Colliding Layout Region */}
          <div style={{ position: 'relative', marginTop: '14px' }}>
            <div
              onClick={() => onSelect('box1')}
              style={{
                background: 'rgba(251, 146, 60, 0.16)',
                border: selected === 'box1' ? '2px solid #fb923c' : '1px dashed #fb923c',
                padding: '12px',
                borderRadius: '10px',
                cursor: 'pointer',
                position: 'relative',
                zIndex: 10,
                boxShadow: selected === 'box1' ? '0 0 16px rgba(251,146,60,0.35)' : 'none',
                transition: 'all 0.25s ease'
              }}
            >
              <div style={{ fontSize: '9px', color: 'var(--accent-orange-bright)', fontWeight: '800' }}>[VOUCHER BANNER - DOM NODE #18]</div>
              <div style={{ fontSize: '12px', fontWeight: '700', color: '#fff' }}>Apply 20% Discount Code</div>
            </div>

            <div
              onClick={() => onSelect('defect_box')}
              className="hud-target-box"
              style={{
                background: 'rgba(244, 63, 94, 0.22)',
                border: selected === 'defect_box' ? '2px solid #fb7185' : '1px dashed #fb7185',
                padding: '14px',
                borderRadius: '10px',
                cursor: 'pointer',
                marginTop: '-16px', // Overlapping defect
                marginLeft: '8px',
                position: 'relative',
                zIndex: 15,
                boxShadow: selected === 'defect_box' ? '0 0 20px rgba(244,63,94,0.45)' : 'none',
                transition: 'all 0.25s ease'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '9px', color: '#fb7185', fontWeight: '800' }}>[SUBMIT BUTTON - OCCLUDED]</span>
                <Crosshair size={12} color="#fb7185" />
              </div>
              <div style={{ fontSize: '13px', fontWeight: '900', color: '#fff', marginTop: '2px' }}>Confirm Payment ($84.50)</div>
            </div>
          </div>

          <div style={{ marginTop: 'auto', background: 'rgba(244,63,94,0.14)', border: '1px solid rgba(244,63,94,0.35)', padding: '10px', borderRadius: '8px', fontSize: '11px', color: '#fca5a5' }}>
            <strong style={{ color: '#fb7185' }}>Oracle Verdict:</strong> OVERFLOW_Y_COLLISION (IoU 0.382)
          </div>
        </div>
      )
    },
    {
      id: 'kyc',
      title: 'KYC & ID Verification',
      category: 'Fintech / Banking',
      icon: UserCheck,
      defectCount: 1,
      defectType: 'Viewport Bounds Clipping / Truncation',
      severity: 'High',
      iou: '0.294',
      injectedStress: 'Font Scale 1.35x + RAM Pressure 80%',
      targetNode: 'android.widget.FrameLayout (camera_container)',
      collidingNode: 'android.widget.TextView (kyc_instructions)',
      vlmInsight: 'System font zoom + dynamic density shift caused instruction copy to push document frame past screen viewport limit [y: 620px > max: 580px]. Action button rendered unclickable.',
      renderUi: (selected, onSelect) => (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
          <div style={{ fontSize: '15px', fontWeight: '800', marginBottom: '12px', textAlign: 'center' }}>Identity Verification</div>

          <div style={{ background: '#1c2234', borderRadius: '10px', padding: '10px 12px', marginBottom: '10px', border: '1px solid rgba(255,255,255,0.08)' }}>
            <div style={{ fontSize: '11px', color: '#cbd5e1', lineHeight: '1.4' }}>
              Position government passport within the camera bounding guidelines.
            </div>
          </div>

          {/* Camera Frame Preview with Truncation Bug */}
          <div
            onClick={() => onSelect('defect_box')}
            className="hud-target-box"
            style={{
              background: 'rgba(244, 63, 94, 0.15)',
              border: selected === 'defect_box' ? '2px solid #fb7185' : '1px dashed #fb7185',
              borderRadius: '12px',
              padding: '24px 14px',
              textAlign: 'center',
              cursor: 'pointer',
              marginBottom: '10px'
            }}
          >
            <div style={{ fontSize: '9px', color: '#fb7185', fontWeight: '800', marginBottom: '6px' }}>[CAMERA SCAN FRAME - CLIPPED]</div>
            <div style={{ width: '100%', height: '110px', border: '2px dashed #64748b', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#94a3b8', fontSize: '11px' }}>
              [ Passport MRZ Area ]
            </div>
          </div>

          {/* Truncated Action CTA */}
          <div style={{ position: 'relative', marginTop: '-12px', opacity: 0.5, border: '1px dashed #fb7185', padding: '8px', borderRadius: '8px', background: 'rgba(244,63,94,0.1)' }}>
            <div style={{ fontSize: '10px', color: '#fb7185', fontWeight: '700' }}>[PARTIALLY OFFSCREEN] Capture Scan</div>
          </div>

          <div style={{ marginTop: 'auto', background: 'rgba(244,63,94,0.14)', border: '1px solid rgba(244,63,94,0.35)', padding: '10px', borderRadius: '8px', fontSize: '11px', color: '#fca5a5' }}>
            <strong style={{ color: '#fb7185' }}>Oracle Verdict:</strong> BOUNDS_TRUNCATION (IoU 0.294)
          </div>
        </div>
      )
    },
    {
      id: 'catalog',
      title: 'Product Catalog & Filter',
      category: 'Retail Store',
      icon: Grid,
      defectCount: 1,
      defectType: 'Z-Index Stack Level Collision',
      severity: 'Medium',
      iou: '0.415',
      injectedStress: 'Orientation Rotation + Flaky 3G',
      targetNode: 'android.widget.HorizontalScrollView (category_tabs)',
      collidingNode: 'android.view.View (filter_overlay_dimmer)',
      vlmInsight: 'Sticky header overlay z-layer failed to release touch interception after orientation flip. Dimmer layer overlaps active category chips, suppressing onClick events.',
      renderUi: (selected, onSelect) => (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
          <div style={{ fontSize: '15px', fontWeight: '800', marginBottom: '12px', textAlign: 'center' }}>Product Catalog</div>

          <div style={{ display: 'flex', gap: '6px', marginBottom: '10px' }}>
            <span style={{ padding: '4px 10px', background: 'var(--accent-orange)', color: '#fff', borderRadius: '16px', fontSize: '10px', fontWeight: '700' }}>All</span>
            <span style={{ padding: '4px 10px', background: '#1c2234', color: '#cbd5e1', borderRadius: '16px', fontSize: '10px' }}>Electronics</span>
            <span style={{ padding: '4px 10px', background: '#1c2234', color: '#cbd5e1', borderRadius: '16px', fontSize: '10px' }}>Apparel</span>
          </div>

          {/* Grid with Sticky Overlay Glitch */}
          <div style={{ position: 'relative', flex: 1 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
              <div style={{ background: '#1c2234', borderRadius: '8px', padding: '10px', textAlign: 'center', fontSize: '11px' }}>
                <div style={{ height: '55px', background: '#252d44', borderRadius: '6px', marginBottom: '6px' }} />
                Item #101
              </div>
              <div style={{ background: '#1c2234', borderRadius: '8px', padding: '10px', textAlign: 'center', fontSize: '11px' }}>
                <div style={{ height: '55px', background: '#252d44', borderRadius: '6px', marginBottom: '6px' }} />
                Item #102
              </div>
            </div>

            {/* Stuck Filter Overlay Defect */}
            <div
              onClick={() => onSelect('defect_box')}
              className="hud-target-box"
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                background: 'rgba(244, 63, 94, 0.25)',
                border: selected === 'defect_box' ? '2px solid #fb7185' : '1px dashed #fb7185',
                borderRadius: '10px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                zIndex: 20
              }}
            >
              <div style={{ textAlign: 'center', color: '#fb7185', fontSize: '11px', fontWeight: '800' }}>
                [Z-INDEX GHOST OVERLAY (TRAPS TOUCH)]
              </div>
            </div>
          </div>

          <div style={{ marginTop: 'auto', background: 'rgba(244,63,94,0.14)', border: '1px solid rgba(244,63,94,0.35)', padding: '10px', borderRadius: '8px', fontSize: '11px', color: '#fca5a5' }}>
            <strong style={{ color: '#fb7185' }}>Oracle Verdict:</strong> ZINDEX_INTERCEPT_COLLISION (IoU 0.415)
          </div>
        </div>
      )
    },
    {
      id: 'cart',
      title: 'Cart & Promo Voucher',
      category: 'E-Commerce',
      icon: ShoppingCart,
      defectCount: 0,
      defectType: 'Nominal Layout (0 Defects)',
      severity: 'Pass',
      iou: '0.000',
      injectedStress: 'Normal Motor Profile',
      targetNode: 'android.widget.RecyclerView (cart_items)',
      collidingNode: 'None (Clean Spatial Alignment)',
      vlmInsight: 'Spatial layout verified with 100% confidence. All text nodes and tap targets respect 48dp minimum touch bounding boxes with zero occlusion.',
      renderUi: (selected, onSelect) => (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
          <div style={{ fontSize: '15px', fontWeight: '800', marginBottom: '14px', textAlign: 'center' }}>Shopping Cart</div>

          <div style={{ background: '#1c2234', borderRadius: '10px', padding: '12px', marginBottom: '10px', border: '1px solid rgba(255,255,255,0.08)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', fontWeight: '700' }}>
              <span>Wireless ANC Headphones</span>
              <span style={{ color: 'var(--accent-cyan-bright)' }}>$129.00</span>
            </div>
            <div style={{ fontSize: '10px', color: '#94a3b8', marginTop: '2px' }}>Qty: 1 • Matte Black</div>
          </div>

          <div style={{ background: '#1c2234', borderRadius: '10px', padding: '12px', marginBottom: '14px', border: '1px solid rgba(255,255,255,0.08)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', fontWeight: '700' }}>
              <span>USB-C Fast Charger 65W</span>
              <span style={{ color: 'var(--accent-cyan-bright)' }}>$24.00</span>
            </div>
            <div style={{ fontSize: '10px', color: '#94a3b8', marginTop: '2px' }}>Qty: 1 • Braided 2M</div>
          </div>

          <div style={{ marginTop: 'auto', background: 'rgba(16,185,129,0.14)', border: '1px solid rgba(16,185,129,0.35)', padding: '12px', borderRadius: '8px', fontSize: '11px', color: '#a7f3d0' }}>
            <strong style={{ color: '#34d399' }}>Oracle Verdict:</strong> NOMINAL_LAYOUT_VERIFIED (0 Defects)
          </div>
        </div>
      )
    }
  ];

  const currentScreen = screens.find((s) => s.id === selectedScreenId) || screens[0];

  const handleRescan = () => {
    setIsScanning(true);
    setScanComplete(false);
    setTimeout(() => {
      setIsScanning(false);
      setScanComplete(true);
    }, 1400);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '28px', width: '100%', maxWidth: '1280px', margin: '0 auto' }}>
      {/* Top Header Card */}
      <div className="glass-card" style={{ padding: '18px 26px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ background: 'rgba(251,146,60,0.12)', color: 'var(--accent-orange-bright)', width: '46px', height: '46px', borderRadius: '14px', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 0 16px rgba(251,146,60,0.2)' }}>
            <Eye size={24} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '600', textTransform: 'uppercase' }}>Vision-Language Oracle (Qwen2-VL)</span>
            </div>
            <h1 style={{ fontSize: '20px', fontWeight: '900', color: '#fff', marginTop: '2px' }}>
              On-Device Visual Bug Inspector & Spatial Layout Oracle
            </h1>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <button className="btn-secondary" onClick={handleRescan} disabled={isScanning} style={{ padding: '8px 16px', fontSize: '12px' }}>
            <RefreshCw size={14} className={isScanning ? 'spin' : ''} /> {isScanning ? 'Scanning Screen...' : 'Re-Scan Frame'}
          </button>
          <button className="btn-cta" onClick={onGoToAttribution}>
            <FileText size={16} /> Synthesize Self-Healing Patch <ArrowRight size={16} />
          </button>
        </div>
      </div>

      {/* Screen / Page Selection Rail */}
      <div className="glass-card" style={{ padding: '16px 20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
          <div style={{ fontSize: '12px', fontWeight: '700', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '1px' }}>
            Select Target Mobile Page for Spatial Oracle Inspection:
          </div>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            4 Emulated Test Screens
          </span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '14px' }}>
          {screens.map((screen) => {
            const Icon = screen.icon;
            const isSelected = selectedScreenId === screen.id;

            return (
              <div
                key={screen.id}
                onClick={() => {
                  setSelectedScreenId(screen.id);
                  setSelectedBox('defect_box');
                }}
                style={{
                  background: isSelected ? 'rgba(251, 146, 60, 0.12)' : 'rgba(255, 255, 255, 0.03)',
                  border: isSelected ? '1px solid var(--accent-orange)' : '1px solid var(--border-subtle)',
                  borderRadius: '12px',
                  padding: '14px 16px',
                  cursor: 'pointer',
                  transition: 'all 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
                  boxShadow: isSelected ? '0 0 20px rgba(251, 146, 60, 0.2)' : 'none',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px'
                }}
              >
                <div style={{ width: '38px', height: '38px', borderRadius: '10px', background: isSelected ? 'rgba(251, 146, 60, 0.25)' : 'rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: isSelected ? '#fed7aa' : 'var(--text-muted)' }}>
                  <Icon size={20} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: '13px', fontWeight: '700', color: isSelected ? '#fff' : 'var(--text-main)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {screen.title}
                  </div>
                  <div style={{ fontSize: '10px', color: 'var(--text-dim)', marginTop: '2px' }}>
                    {screen.category}
                  </div>
                </div>
                {screen.defectCount > 0 ? (
                  <span className="glow-badge glow-badge-red" style={{ fontSize: '9px', padding: '2px 7px' }}>
                    {screen.defectCount} Defect
                  </span>
                ) : (
                  <span className="glow-badge glow-badge-green" style={{ fontSize: '9px', padding: '2px 7px' }}>
                    Passed
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* 2-Column Inspector Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '24px' }}>
        {/* Left Column: Interactive Screen Inspector Frame with Laser Scanline */}
        <div className="glass-card" style={{ padding: '28px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', marginBottom: '18px' }}>
            <div className="glass-card-title" style={{ margin: 0 }}>
              <div className="icon-wrap">
                <Box size={18} />
              </div>
              <span>{currentScreen.title} — Frame Analysis</span>
            </div>
            {currentScreen.defectCount > 0 ? (
              <span className="glow-badge glow-badge-red" style={{ fontSize: '10px' }}>
                <AlertTriangle size={11} /> {currentScreen.defectCount} Defect Flagged
              </span>
            ) : (
              <span className="glow-badge glow-badge-green" style={{ fontSize: '10px' }}>
                <CheckCircle2 size={11} /> Clean Frame Layout
              </span>
            )}
          </div>

          {/* Phone Frame with Overlap Annotations & Scanning Beam */}
          <div className="phone-device-3d" style={{ width: '310px', height: '560px', position: 'relative' }}>
            <div className="phone-dynamic-island" />

            {/* Live Laser Scanning Line Animation */}
            <div className="laser-scanline" />

            {/* HUD Status Bar in Top Left */}
            <div style={{ position: 'absolute', top: '10px', left: '16px', zIndex: 35, fontSize: '9px', fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan-bright)', letterSpacing: '0.8px', background: 'rgba(9,13,24,0.8)', padding: '2px 6px', borderRadius: '4px' }}>
              VLM_REC: 60FPS
            </div>

            <div className="phone-viewport" style={{ background: '#121624', color: '#fff', padding: '36px 16px 16px', display: 'flex', flexDirection: 'column', position: 'relative' }}>
              {currentScreen.renderUi(selectedBox, setSelectedBox)}
            </div>
          </div>
        </div>

        {/* Right Column: Page-Wise Defect Properties & VLM Prompt Diagnostics */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '22px' }}>
          {/* Defect Inspector Table */}
          <div className="glass-card" style={{ padding: '28px' }}>
            <div className="glass-card-title" style={{ marginBottom: '18px' }}>
              <div className="icon-wrap">
                <AlertTriangle size={18} />
              </div>
              <span>Spatial Anomaly Specifications ({currentScreen.title})</span>
            </div>

            <div className="defect-table">
              <div className="defect-row">
                <span className="defect-label">Anomaly Classification</span>
                <span className="defect-val" style={{ color: currentScreen.defectCount > 0 ? '#fb7185' : '#34d399' }}>
                  {currentScreen.defectType}
                </span>
              </div>
              <div className="defect-row">
                <span className="defect-label">Affected Target Node</span>
                <span className="defect-val">{currentScreen.targetNode}</span>
              </div>
              <div className="defect-row">
                <span className="defect-label">Colliding / Obstructing Node</span>
                <span className="defect-val">{currentScreen.collidingNode}</span>
              </div>
              <div className="defect-row">
                <span className="defect-label">Intersection over Union (IoU)</span>
                <span className="defect-val" style={{ color: currentScreen.defectCount > 0 ? 'var(--accent-orange-bright)' : '#34d399' }}>
                  {currentScreen.iou} {currentScreen.defectCount > 0 ? '(High Collision)' : '(Pass)'}
                </span>
              </div>
              <div className="defect-row">
                <span className="defect-label">Injected Stress Vector</span>
                <span className="defect-val">{currentScreen.injectedStress}</span>
              </div>
            </div>
          </div>

          {/* VLM Chain-of-Thought Output */}
          <div className="glass-card" style={{ padding: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <span style={{ fontSize: '12px', fontWeight: '700', color: '#fff', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Cpu size={15} color="var(--accent-cyan-bright)" /> Qwen2-VL On-Device VLM Analysis
              </span>
              <span className="glow-badge glow-badge-blue" style={{ fontSize: '9px' }}>4-bit AWQ On-Device</span>
            </div>

            <div className="code-window" style={{ maxHeight: '190px', fontSize: '11px' }}>
              <div style={{ color: '#64748b' }}>// System Prompt: Detect bounding box overlaps, offscreen truncations & visual defects on: {currentScreen.title}</div>
              <div style={{ color: 'var(--accent-cyan-bright)', marginTop: '8px', lineHeight: '1.55' }}>
                &gt; VLM Response: {currentScreen.vlmInsight}
              </div>
              {currentScreen.defectCount > 0 && (
                <div style={{ color: '#fb7185', marginTop: '8px', fontWeight: '600' }}>
                  &gt; Recommended Action: Remap XPath locator with Sentence-BERT & apply auto-layout padding constraint in synthesized patch.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
