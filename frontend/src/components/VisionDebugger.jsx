import React, { useState } from 'react';
import { Eye, ArrowRight, Code, Send, Wifi, Battery, Camera, CheckCircle2, AlertCircle, Sparkles, Layers, Box } from 'lucide-react';
import { motion } from 'framer-motion';

export default function VisionDebugger({ onGoToAttribution }) {
  const [showHeatmap, setShowHeatmap] = useState(true);
  const [activeProfile, setActiveProfile] = useState('mid-transaction');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '28px', width: '100%', maxWidth: '1280px', margin: '0 auto' }}>
      {/* Top Header Bar */}
      <div className="glass-card" style={{ padding: '18px 26px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ background: 'rgba(255,87,34,0.15)', color: '#ff5722', width: '46px', height: '46px', borderRadius: '14px', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 0 20px rgba(255,87,34,0.3)' }}>
            <Eye size={24} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="glow-badge glow-badge-orange" style={{ fontSize: '9px', padding: '2px 8px' }}>Component 3</span>
              <span style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '600', textTransform: 'uppercase' }}>Vision-Language Oracle</span>
            </div>
            <select
              value={activeProfile}
              onChange={(e) => setActiveProfile(e.target.value)}
              className="input-styled"
              style={{ border: 'none', background: 'transparent', padding: '2px 0', fontSize: '18px', fontWeight: '900', color: 'var(--accent-orange-bright)', cursor: 'pointer', outline: 'none' }}
            >
              <option value="mid-transaction">Profile: Mid-Transaction Stress Test</option>
              <option value="network-flap">Profile: Network Flap & Low Memory</option>
            </select>
          </div>
        </div>

        <button className="btn-cta" onClick={onGoToAttribution}>
          View Attribution Report <ArrowRight size={16} />
        </button>
      </div>

      {/* Show Attention Heatmap Toggle & Screen Layout Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.15fr 1fr', gap: '24px' }}>
        {/* Left Column: Mobile Screen Device with Attention Heatmap */}
        <div className="glass-card" style={{ textAlign: 'center', position: 'relative', padding: '28px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '22px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <input
                type="checkbox"
                id="heatmapToggle"
                checked={showHeatmap}
                onChange={(e) => setShowHeatmap(e.target.checked)}
                style={{ accentColor: '#ff5722', width: '18px', height: '18px', cursor: 'pointer' }}
              />
              <label htmlFor="heatmapToggle" style={{ fontSize: '14px', fontWeight: '700', color: '#fff', cursor: 'pointer' }}>
                Show Attention Heatmap Spotlight
              </label>
            </div>
            <span className="glow-badge glow-badge-green" style={{ fontSize: '10px' }}>
              Qwen2-VL 4-bit AWQ Active
            </span>
          </div>

          {/* 3D Mobile Phone Frame */}
          <div className="phone-device-3d" style={{ borderColor: '#1c1c24', margin: '0 auto' }}>
            <div className="phone-dynamic-island" />
            <div className="phone-viewport" style={{ background: '#0a0a10', color: '#fff' }}>
              {/* Glowing Attention Heatmap Spot Overlay */}
              {showHeatmap && <div className="heatmap-spot-attention" />}

              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#94a3b8', marginBottom: '14px', position: 'relative', zIndex: 20 }}>
                <span>10:09</span>
                <span style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                  <Wifi size={12} />
                  <Battery size={12} />
                </span>
              </div>

              {/* Avatar Profile */}
              <div style={{ width: '48px', height: '48px', borderRadius: '50%', background: 'linear-gradient(135deg, #ef4444, #ff7043)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: '900', color: '#fff', margin: '0 auto 8px', fontSize: '16px', boxShadow: '0 0 16px rgba(239,68,68,0.5)', position: 'relative', zIndex: 20 }}>
                AJ
              </div>

              <div style={{ fontWeight: '800', fontSize: '16px', position: 'relative', zIndex: 20 }}>Alex Johnson</div>
              <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginBottom: '16px', position: 'relative', zIndex: 20 }}>alex.j@example.com</div>

              {/* Defective Overlapping Content Node */}
              <div style={{ borderColor: 'rgba(239,68,68,0.4)', background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.4)', borderRadius: '12px', padding: '12px', textAlign: 'left', position: 'relative', zIndex: 20 }}>
                <div style={{ fontSize: '11px', fontWeight: '700', color: '#fca5a5', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <AlertCircle size={14} color="#ef4444" /> Personal Details (Collision Zone)
                </div>
                <div style={{ fontSize: '10px', color: '#fca5a5', lineHeight: '1.4', marginTop: '6px' }}>
                  Bio: Senior Lead developer for mobile infrastructure. Dedicated to robust autonomous testing pipelines.
                </div>
                <div style={{ fontSize: '10px', color: '#fca5a5', marginTop: '6px', lineHeight: '1.4' }}>
                  Location: San Francisco, CA<br />
                  Phone: 415-555-0199
                </div>
              </div>

              {/* Colliding overlapping button bar */}
              <div style={{ display: 'flex', gap: '8px', marginTop: 'auto', position: 'relative', zIndex: 20, paddingTop: '10px' }}>
                <button style={{ flex: 1, background: '#ff5722', color: '#fff', border: '1px solid #ef4444', padding: '12px', borderRadius: '10px', fontWeight: '700', fontSize: '12px', boxShadow: '0 0 14px rgba(255,87,34,0.4)' }}>
                  SUBMIT
                </button>
                <button style={{ flex: 1, background: '#12121e', color: '#fff', border: '1px solid #ef4444', padding: '12px', borderRadius: '10px', fontWeight: '700', fontSize: '12px' }}>
                  SIGN UP
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Defect Metadata Panel */}
        <div className="glass-card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', padding: '28px' }}>
          <div>
            <div className="glass-card-title" style={{ marginBottom: '22px' }}>
              <div className="icon-wrap">
                <Camera size={18} />
              </div>
              <span>Visual Defect Classification Metadata</span>
            </div>

            <div className="defect-table">
              <div className="defect-row">
                <span className="defect-label">Defect Classification</span>
                <span className="defect-val" style={{ color: '#ef4444' }}>UI Overlap / Visibility Collision</span>
              </div>
              <div className="defect-row">
                <span className="defect-label">VLM Confidence Score</span>
                <span className="defect-val" style={{ color: '#10b981' }}>94.2%</span>
              </div>
              <div className="defect-row">
                <span className="defect-label">Triggering Environmental Stress</span>
                <span className="defect-val">CPU throttling + 3G Handover (t=4.2s)</span>
              </div>
              <div className="defect-row">
                <span className="defect-label">Fusion Strategy Mode</span>
                <span className="defect-val">Token Concatenation + Vision Tokens</span>
              </div>
              <div className="defect-row">
                <span className="defect-label">Model Quantization</span>
                <span className="defect-val">4-bit AWQ (Qwen2-VL)</span>
              </div>
              <div className="defect-row">
                <span className="defect-label">Framework Model Version</span>
                <span className="defect-val">v1.3</span>
              </div>
              <div className="defect-row">
                <span className="defect-label">Linked Stress Profile</span>
                <span className="defect-val" style={{ color: 'var(--accent-orange-bright)' }}>Mid-Transaction Stress Test</span>
              </div>
              <div className="defect-row" style={{ borderBottom: 'none' }}>
                <span className="defect-label">Telemetry Pipeline Sync</span>
                <span className="defect-val" style={{ color: '#10b981', display: 'flex', gap: '6px', alignItems: 'center' }}>
                  <CheckCircle2 size={15} /> Logged & Streamed (14:32:07)
                </span>
              </div>
            </div>
          </div>

          <button className="btn-cta" onClick={onGoToAttribution} style={{ width: '100%', borderRadius: '24px', padding: '14px', fontSize: '14px', marginTop: '26px' }}>
            <CheckCircle2 size={16} /> Synthesize Self-Healing Patch (C4)
          </button>
        </div>
      </div>

      {/* Code Inspection Panel */}
      <div className="glass-card" style={{ padding: '28px' }}>
        <div className="glass-card-title" style={{ marginBottom: '18px' }}>
          <div className="icon-wrap">
            <Code size={18} />
          </div>
          <span>View Hierarchy Collision & DOM Node Inspector</span>
        </div>

        <div className="code-window">
          <div style={{ color: '#64748b' }}>&lt;!-- HEART Visual Oracle Collision Frame Dump --&gt;</div>
          <div style={{ color: '#64748b' }}>&lt;ViewHierarchy bounds="[0,0][1080,2400]"&gt;</div>
          <div style={{ paddingLeft: '18px' }}>
            <div style={{ color: '#f472b6' }}>&lt;android.widget.FrameLayout class="profile-master" bounds="[0,210][1080,1890]"&gt;</div>
            <div style={{ background: 'rgba(239, 68, 68, 0.15)', borderLeft: '3px solid #ef4444', padding: '10px 14px', margin: '8px 0', borderRadius: '6px' }}>
              <div style={{ color: '#ef4444', fontWeight: '700' }}>&lt;!-- C3 DETECTED OVERFLOW_Y_COLLISION ZONE --&gt;</div>
              <div style={{ color: '#fff' }}>&lt;android.widget.LinearLayout bounds="[60,820][1020,1460]" conflict="OVERLAP"&gt;</div>
              <div style={{ paddingLeft: '18px', color: '#fca5a5' }}>
                &lt;android.widget.TextView text="Bio: Senior Lead..." bounds="[60,820][1020,1180]" /&gt;<br />
                &lt;android.widget.Button text="SUBMIT" bounds="[60,1120][520,1260]" /&gt; &lt;!-- 60px vertical intersection overlap --&gt;
              </div>
              <div style={{ color: '#fff' }}>&lt;/android.widget.LinearLayout&gt;</div>
            </div>
            <div style={{ color: '#f472b6' }}>&lt;/android.widget.FrameLayout&gt;</div>
          </div>
          <div style={{ color: '#64748b' }}>&lt;/ViewHierarchy&gt;</div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '18px' }}>
          <button className="btn-secondary" onClick={onGoToAttribution}>
            View Raw Hierarchy JSON
          </button>
          <button className="btn-cta" onClick={onGoToAttribution}>
            Forward to Telemetry Pipeline <Send size={15} />
          </button>
        </div>
      </div>
    </div>
  );
}
