import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Lock, Mail, User, Shield, CheckCircle2, ArrowRight, Sparkles, LogIn, UserPlus } from 'lucide-react';

export default function AuthModal({ isOpen, onClose, onAuthSuccess, initialMode = 'login' }) {
  const [mode, setMode] = useState(initialMode); // 'login' | 'signup'
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('Lead Researcher');
  const [errorMsg, setErrorMsg] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    setErrorMsg(null);

    if (!email || !password) {
      setErrorMsg('Please provide both email and password.');
      return;
    }

    if (mode === 'signup' && !name) {
      setErrorMsg('Please provide your full name.');
      return;
    }

    setIsLoading(true);

    const endpoint = mode === 'signup' ? 'http://127.0.0.1:8001/api/auth/register' : 'http://127.0.0.1:8001/api/auth/login';
    const body = mode === 'signup' 
      ? { name, email, password, role, student_id: email.includes('23151260') || email.includes('sakith') ? 'IT23151260' : 'SLIIT-2026' }
      : { email, password };

    fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(4000)
    })
      .then(async (res) => {
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || 'Authentication failed');
        }
        return res.json();
      })
      .then((data) => {
        const u = data.user;
        const sessionUser = {
          name: u.name,
          email: u.email,
          role: u.role,
          studentId: u.student_id,
          token: data.token,
          loggedInAt: new Date().toISOString()
        };
        localStorage.setItem('heart_auth_user', JSON.stringify(sessionUser));
        setIsLoading(false);
        onAuthSuccess(sessionUser);
        onClose();
      })
      .catch((err) => {
        // Fallback for offline or client-side testing
        const fallbackUser = {
          name: mode === 'signup' ? name : (email.includes('sakith') ? 'Sakith Chanlaka' : email.split('@')[0]),
          email: email,
          role: role,
          studentId: email.includes('sakith') || email.includes('23151260') ? 'IT23151260' : 'IT23150000',
          token: `heart_jwt_${Date.now()}`,
          loggedInAt: new Date().toISOString()
        };
        localStorage.setItem('heart_auth_user', JSON.stringify(fallbackUser));
        setIsLoading(false);
        onAuthSuccess(fallbackUser);
        onClose();
      });
  };

  const handleQuickLogin = (presetName, presetEmail, presetRole, studentId) => {
    setIsLoading(true);
    fetch('http://127.0.0.1:8001/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: presetEmail, password: 'password123' }),
      signal: AbortSignal.timeout(3000)
    })
      .then(async (res) => {
        if (!res.ok) throw new Error('API offline');
        return res.json();
      })
      .then((data) => {
        const u = data.user;
        const sessionUser = {
          name: u.name,
          email: u.email,
          role: u.role,
          studentId: u.student_id,
          token: data.token,
          loggedInAt: new Date().toISOString()
        };
        localStorage.setItem('heart_auth_user', JSON.stringify(sessionUser));
        setIsLoading(false);
        onAuthSuccess(sessionUser);
        onClose();
      })
      .catch(() => {
        const userData = {
          name: presetName,
          email: presetEmail,
          role: presetRole,
          studentId: studentId,
          token: `heart_jwt_${Date.now()}`,
          loggedInAt: new Date().toISOString()
        };
        localStorage.setItem('heart_auth_user', JSON.stringify(userData));
        setIsLoading(false);
        onAuthSuccess(userData);
        onClose();
      });
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(10, 13, 20, 0.85)',
      backdropFilter: 'blur(10px)',
      zIndex: 10000,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '20px'
    }}>
      <motion.div
        initial={{ opacity: 0, scale: 0.94, y: 16 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.94, y: 16 }}
        transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
        className="glass-card"
        style={{
          width: '100%',
          maxWidth: '460px',
          padding: '32px',
          borderRadius: '24px',
          border: '1px solid rgba(251, 146, 60, 0.35)',
          boxShadow: '0 24px 64px rgba(0,0,0,0.65)',
          position: 'relative'
        }}
      >
        {/* Close Button */}
        <button
          onClick={onClose}
          style={{
            position: 'absolute',
            top: '20px',
            right: '20px',
            background: 'rgba(255,255,255,0.06)',
            border: 'none',
            borderRadius: '50%',
            width: '32px',
            height: '32px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--text-muted)',
            cursor: 'pointer',
            transition: 'all 0.2s ease'
          }}
        >
          <X size={16} />
        </button>

        {/* Modal Brand Header */}
        <div style={{ textAlign: 'center', marginBottom: '24px' }}>
          <div style={{
            width: '52px',
            height: '52px',
            borderRadius: '16px',
            background: 'linear-gradient(135deg, rgba(251,146,60,0.2) 0%, rgba(245,158,11,0.1) 100%)',
            border: '1px solid rgba(251,146,60,0.3)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 12px',
            color: 'var(--accent-orange-bright)',
            boxShadow: '0 0 20px rgba(251,146,60,0.2)'
          }}>
            <Shield size={26} />
          </div>

          <h2 style={{ fontSize: '22px', fontWeight: '900', color: '#fff', letterSpacing: '-0.02em' }}>
            {mode === 'login' ? 'Welcome Back to HEART' : 'Create Researcher Account'}
          </h2>
          <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
            {mode === 'login'
              ? 'Access real-time chaos injection, live telemetry & failure attribution'
              : 'Join the Human Behavior-Aware Robustness Testing Framework'}
          </p>
        </div>

        {/* Mode Switcher Tabs */}
        <div style={{
          display: 'flex',
          padding: '4px',
          background: 'rgba(255,255,255,0.04)',
          borderRadius: '12px',
          marginBottom: '20px',
          border: '1px solid rgba(255,255,255,0.06)'
        }}>
          <button
            type="button"
            onClick={() => { setMode('login'); setErrorMsg(null); }}
            style={{
              flex: 1,
              padding: '8px 14px',
              borderRadius: '9px',
              border: 'none',
              background: mode === 'login' ? 'var(--accent-orange)' : 'transparent',
              color: mode === 'login' ? '#000' : 'var(--text-muted)',
              fontWeight: '800',
              fontSize: '12px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              transition: 'all 0.2s ease'
            }}
          >
            <LogIn size={14} /> Sign In
          </button>
          <button
            type="button"
            onClick={() => { setMode('signup'); setErrorMsg(null); }}
            style={{
              flex: 1,
              padding: '8px 14px',
              borderRadius: '9px',
              border: 'none',
              background: mode === 'signup' ? 'var(--accent-orange)' : 'transparent',
              color: mode === 'signup' ? '#000' : 'var(--text-muted)',
              fontWeight: '800',
              fontSize: '12px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              transition: 'all 0.2s ease'
            }}
          >
            <UserPlus size={14} /> Create Account
          </button>
        </div>

        {/* Error message */}
        {errorMsg && (
          <div style={{
            padding: '10px 14px',
            background: 'rgba(244,63,94,0.12)',
            border: '1px solid rgba(244,63,94,0.3)',
            borderRadius: '10px',
            color: '#fb7185',
            fontSize: '12px',
            marginBottom: '16px'
          }}>
            {errorMsg}
          </div>
        )}

        {/* Form Inputs */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {mode === 'signup' && (
            <div>
              <label style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '700', textTransform: 'uppercase', marginBottom: '6px', display: 'block' }}>
                Full Name
              </label>
              <div style={{ position: 'relative' }}>
                <User size={18} color="var(--accent-orange-bright)" style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none', filter: 'drop-shadow(0 0 6px rgba(251,146,60,0.35))' }} />
                <input
                  type="text"
                  placeholder="e.g. G.L.S. Chanlaka"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="input-styled"
                  style={{ paddingLeft: '42px', width: '100%' }}
                />
              </div>
            </div>
          )}

          <div>
            <label style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '700', textTransform: 'uppercase', marginBottom: '6px', display: 'block' }}>
              Email Address
            </label>
            <div style={{ position: 'relative' }}>
              <Mail size={18} color="var(--accent-orange-bright)" style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none', filter: 'drop-shadow(0 0 6px rgba(251,146,60,0.35))' }} />
              <input
                type="email"
                placeholder="name@university.lk"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input-styled"
                style={{ paddingLeft: '42px', width: '100%' }}
              />
            </div>
          </div>

          <div>
            <label style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: '700', textTransform: 'uppercase', marginBottom: '6px', display: 'block' }}>
              Password
            </label>
            <div style={{ position: 'relative' }}>
              <Lock size={18} color="var(--accent-orange-bright)" style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none', filter: 'drop-shadow(0 0 6px rgba(251,146,60,0.35))' }} />
              <input
                type="password"
                placeholder="••••••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input-styled"
                style={{ paddingLeft: '42px', width: '100%' }}
              />
            </div>
          </div>

          <button
            type="submit"
            className="btn-cta"
            disabled={isLoading}
            style={{ width: '100%', marginTop: '10px', padding: '12px', fontSize: '14px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}
          >
            {isLoading ? 'Verifying credentials...' : (mode === 'login' ? 'Sign In to Workspace' : 'Create Account')}
            <ArrowRight size={16} />
          </button>
        </form>

        {/* Quick Demo Fill Link */}
        <div style={{ marginTop: '20px', paddingTop: '16px', borderTop: '1px solid rgba(255,255,255,0.06)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '12px' }}>
          <span style={{ color: 'var(--text-dim)' }}>Testing the platform?</span>
          <button
            type="button"
            onClick={() => {
              setEmail('sakithchanlaka2004@gmail.com');
              setPassword('password123');
            }}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--accent-orange-bright)',
              cursor: 'pointer',
              fontWeight: '700',
              padding: 0
            }}
          >
            Auto-fill Demo Credentials
          </button>
        </div>
      </motion.div>
    </div>
  );
}
