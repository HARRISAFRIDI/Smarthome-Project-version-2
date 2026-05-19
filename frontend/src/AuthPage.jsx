import React, { useState } from 'react';

const API = 'http://localhost:8000/api';

export default function AuthPage({ onAuth }) {
  const [tab, setTab]         = useState('login');
  const [name, setName]       = useState('');
  const [email, setEmail]     = useState('');
  const [password, setPass]   = useState('');
  const [location, setLoc]    = useState(null);   // {latitude, longitude}
  const [locLabel, setLocLabel] = useState('');
  const [error, setError]     = useState('');
  const [loading, setLoading] = useState(false);
  const [locLoading, setLocLoading] = useState(false);

  const requestLocation = () => {
    if (!navigator.geolocation) {
      setError('Geolocation not supported by your browser.');
      return;
    }
    setLocLoading(true);
    navigator.geolocation.getCurrentPosition(
      pos => {
        const lat = pos.coords.latitude;
        const lon = pos.coords.longitude;
        setLoc({ latitude: lat, longitude: lon });
        setLocLabel(`📍 ${lat.toFixed(5)}, ${lon.toFixed(5)}`);
        setLocLoading(false);
        setError('');
      },
      err => {
        setError('Location denied. Using default Mardan location.');
        setLoc({ latitude: 34.19251361001708, longitude: 72.02845291100556 });
        setLocLabel('📍 Mardan (default)');
        setLocLoading(false);
      }
    );
  };

  const handleSubmit = async e => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (tab === 'signup') {
        if (!location) { setError('Please allow location access first.'); setLoading(false); return; }
        const res = await fetch(`${API}/auth/signup`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, email, password,
            latitude: location.latitude, longitude: location.longitude }),
        });
        const d = await res.json();
        if (!res.ok) throw new Error(d.detail || 'Signup failed');
        onAuth(d.user);
      } else {
        const res = await fetch(`${API}/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password }),
        });
        const d = await res.json();
        if (!res.ok) throw new Error(d.detail || 'Invalid credentials');
        onAuth(d.user);
      }
    } catch (ex) {
      setError(ex.message);
    }
    setLoading(false);
  };

  return (
    <div className="auth-root">
      <div className="auth-card">
        {/* Brand */}
        <div className="auth-brand">
          <span className="auth-brand-icon">🏠</span>
          <div className="auth-brand-text">
            <div className="auth-brand-name">HomeSense</div>
            <div className="auth-brand-sub">AI Home Automation</div>
          </div>
        </div>

        {/* Tabs */}
        <div className="auth-tabs">
          <button className={`auth-tab ${tab==='login'?'auth-tab-active':''}`} onClick={()=>{setTab('login');setError('');}}>Sign In</button>
          <button className={`auth-tab ${tab==='signup'?'auth-tab-active':''}`} onClick={()=>{setTab('signup');setError('');}}>Sign Up</button>
        </div>

        <form onSubmit={handleSubmit} className="auth-form">
          {tab === 'signup' && (
            <div className="auth-field">
              <label>Full Name</label>
              <input type="text" placeholder="e.g. Ahmed Khan" value={name}
                onChange={e=>setName(e.target.value)} required />
            </div>
          )}
          <div className="auth-field">
            <label>Email</label>
            <input type="email" placeholder="you@example.com" value={email}
              onChange={e=>setEmail(e.target.value)} required />
          </div>
          <div className="auth-field">
            <label>Password</label>
            <input type="password" placeholder="••••••••" value={password}
              onChange={e=>setPass(e.target.value)} required />
          </div>

          {tab === 'signup' && (
            <div className="auth-location-wrap">
              <label>Location <span className="auth-label-note">(for live weather &amp; AI)</span></label>
              <button type="button" className="auth-loc-btn" onClick={requestLocation} disabled={locLoading}>
                {locLoading ? '⏳ Getting location...' : location ? locLabel : '📍 Allow Location Access'}
              </button>
              {location && (
                <div className="auth-loc-ok">✅ Location captured — AI will use your local weather</div>
              )}
            </div>
          )}

          {error && <div className="auth-error">⚠️ {error}</div>}

          <button type="submit" className="auth-submit" disabled={loading}>
            {loading ? '⏳ Please wait...' : tab === 'signup' ? '🚀 Create Account' : '🔑 Sign In'}
          </button>
        </form>

        <div className="auth-footer">
          {tab === 'login'
            ? <>New user? <button className="auth-link" onClick={()=>setTab('signup')}>Create account</button></>
            : <>Already have an account? <button className="auth-link" onClick={()=>setTab('login')}>Sign in</button></>
          }
        </div>

        <div className="auth-info">
          🌤️ Live weather from <strong>OpenWeather API</strong> will power AI predictions for your location
        </div>
      </div>
    </div>
  );
}
