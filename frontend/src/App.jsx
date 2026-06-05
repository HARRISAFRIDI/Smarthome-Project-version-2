import React, { useState, useEffect, useCallback } from 'react';
import './App.css';
import AuthPage from './AuthPage';

const API = 'http://localhost:8000/api';
const DEVICE_ICONS = { AC: '❄️', Fan: '🌀', Light: '💡', TV: '📺', Fridge: '🧊' };

// ── Sidebar ──────────────────────────────────────────────────────
function Sidebar({ page, setPage, unread, user, onLogout }) {
  const items = [
    { id: 'dashboard',     icon: '⊞',  label: 'Dashboard' },
    { id: 'devices',       icon: '🔌', label: 'Devices' },
    { id: 'predictions',   icon: '🤖', label: 'AI Predictions' },
    { id: 'analytics',     icon: '📊', label: 'Analytics' },
    { id: 'notifications', icon: '🔔', label: 'Notifications', badge: unread },
    { id: 'settings',      icon: '⚙️', label: 'Settings' },
  ];
  const initials = user?.name ? user.name.split(' ').map(w=>w[0]).join('').toUpperCase().slice(0,2) : 'SA';
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <span className="brand-icon">🏠</span>
        <div>
          <div className="brand-name">HomeSense</div>
          <div className="brand-sub">AI Control</div>
        </div>
      </div>
      <nav className="sidebar-nav">
        {items.map(i => (
          <button key={i.id} className={`nav-item ${page===i.id?'active':''}`} onClick={()=>setPage(i.id)}>
            <span className="nav-icon">{i.icon}</span>
            <span>{i.label}</span>
            {i.badge > 0 && <span className="nav-badge">{i.badge}</span>}
          </button>
        ))}
      </nav>
      <div className="sidebar-footer">
        <div className="user-avatar">{initials}</div>
        <div style={{flex:1,minWidth:0}}>
          <div className="user-name" style={{overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>
            {user?.name || 'System Admin'}
          </div>
          <div className="user-email" style={{overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>
            {user?.email || 'admin@smarthome.ai'}
          </div>
        </div>
        <button className="logout-btn" title="Sign out" onClick={onLogout}>⏻</button>
      </div>
    </aside>
  );
}

// ── StatCard ─────────────────────────────────────────────────────
function StatCard({ icon, label, value, sub, accent }) {
  return (
    <div className="stat-card" style={{ '--accent': accent }}>
      <div className="stat-icon">{icon}</div>
      <div className="stat-body">
        <div className="stat-label">{label}</div>
        <div className="stat-value">{value}</div>
        {sub && <div className="stat-sub">{sub}</div>}
      </div>
      <div className="stat-glow" />
    </div>
  );
}

// ── DeviceCard ───────────────────────────────────────────────────
function DeviceCard({ device, onToggle, onOverrideDuration }) {
  const icon = DEVICE_ICONS[device.name] || '🔧';
  const [loading, setLoading] = useState(false);
  const [showSlider, setShowSlider] = useState(false);
  const [sliderVal, setSliderVal] = useState(30);

  const toggle = async () => {
    setLoading(true);
    await onToggle(device.id, !device.status, sliderVal);
    setLoading(false);
  };

  const applyDuration = async () => {
    await onOverrideDuration(device.id, sliderVal);
    setShowSlider(false);
  };

  return (
    <div className={`device-card ${device.status ? 'device-on' : 'device-off'}`}>
      <div className="device-icon-wrap">
        <span className="device-icon">{icon}</span>
        <span className={`device-pulse ${device.status ? 'pulse-on' : ''}`} />
      </div>
      <div className="device-info">
        <div className="device-name">{device.name}</div>
        <div className="device-type">{device.type}</div>
        <div className="device-watt">⚡ {device.energy_consumption}W</div>
        {device.manually_locked && (
          <div className="lock-badge">🔒 AI locked · {device.lock_minutes_remaining}m left</div>
        )}
      </div>
      <div className="device-actions">
        <button
          className={`toggle-btn ${device.status ? 'btn-on' : 'btn-off'}`}
          onClick={toggle}
          disabled={loading}
        >
          {loading ? '···' : device.status ? 'ON' : 'OFF'}
        </button>
        <button
          className="override-btn"
          title="Set AI override duration"
          onClick={() => setShowSlider(s => !s)}
        >⏱</button>
      </div>

      {showSlider && (
        <div className="override-slider-wrap">
          <div className="override-slider-label">
            AI Override Lock: <strong>{sliderVal} min</strong>
          </div>
          <input
            type="range" min={5} max={60} step={5}
            value={sliderVal}
            onChange={e => setSliderVal(Number(e.target.value))}
            className="override-range"
          />
          <div className="override-slider-ticks">
            <span>5m</span><span>30m</span><span>60m</span>
          </div>
          <button className="apply-btn" onClick={applyDuration}>Apply Duration</button>
        </div>
      )}
      <div className="device-updated">Updated just now</div>
    </div>
  );
}

function ConfidenceBar({ value, color }) {
  return (
    <div className="conf-track">
      <div className="conf-fill" style={{ width: `${value * 100}%`, background: color }} />
    </div>
  );
}

// ── HomeAwayCard ─────────────────────────────────────────────────
function HomeAwayCard({ isHome, onToggle }) {
  const [loading, setLoading] = useState(false);

  const toggle = async () => {
    setLoading(true);
    await onToggle(!isHome);
    setLoading(false);
  };

  return (
    <div className={`home-away-card ${isHome ? 'hac-home' : 'hac-away'}`}>
      <div className="hac-left">
        <div className="hac-icon-wrap">
          <span className="hac-icon">{isHome ? '🏠' : '✈️'}</span>
          {isHome && <span className="hac-pulse" />}
        </div>
        <div className="hac-body">
          <div className="hac-mode-label">Presence Mode</div>
          <div className="hac-status">{isHome ? 'You are HOME' : 'You are AWAY'}</div>
          <div className="hac-sub">
            {isHome
              ? 'AI managing all devices normally'
              : '❄️ AC · 🌀 Fan · 💡 Light · 📺 TV are OFF — 🧊 Fridge stays ON'}
          </div>
        </div>
      </div>
      <button
        id="home-away-toggle-btn"
        className={`hac-btn ${isHome ? 'hac-btn-leave' : 'hac-btn-return'}`}
        onClick={toggle}
        disabled={loading}
      >
        {loading ? '···' : isHome ? '🚪 Leave Home' : '🏠 I\'m Back'}
      </button>
    </div>
  );
}

// ── Pages ─────────────────────────────────────────────────────────

function DashboardPage({ devices, systemStatus, weather, isHome, onHomeToggle }) {
  const online = devices.filter(d => d.status).length;
  const energy = devices.reduce((s,d) => s + (d.status ? d.energy_consumption*0.001 : 0), 0);
  const acc    = systemStatus?.model?.accuracy ?? 0;
  const tempDisplay = weather?.temp_c != null ? `${weather.temp_c}°C` : (systemStatus?.weather?.temp_c != null ? `${systemStatus.weather.temp_c}°C` : '—');
  const weatherDesc = weather?.description || systemStatus?.weather?.description || '';
  const weatherCity = weather?.city || systemStatus?.weather?.city || '';
  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Dashboard <span className="title-chip">LIVE</span></h1>
        <div className="page-time">{new Date().toLocaleString()}</div>
      </div>

      {/* ── Home / Away banner ── */}
      <HomeAwayCard isHome={isHome} onToggle={onHomeToggle} />

      <div className="stat-grid">
        <StatCard icon="🔌" label="Devices Online"  value={`${online}/${devices.length}`} sub="Active now"    accent="#6C63FF" />
        <StatCard icon="⚡" label="Total Energy"     value={`${energy.toFixed(1)} kWh`}    sub="Current load" accent="#00D4FF" />
        <StatCard icon="🤖" label="AI Accuracy"      value={`${(acc*100).toFixed(1)}%`}    sub="RandomForest" accent="#00E676" />
        <StatCard icon="🌡️" label="Live Temperature" value={tempDisplay}                   sub={weatherDesc || 'OpenWeather API'} accent="#FFD740" />
      </div>
      {weatherCity && (
        <div className="weather-banner">
          <span>🌤️</span>
          <span><strong>{weatherCity}</strong> — {weatherDesc} · {tempDisplay} · Source: RapidAPI OpenWeather</span>
        </div>
      )}
      <div className="section-title">Active Devices</div>
      <div className="devices-overview">
        {devices.map(d => (
          <div key={d.id} className={`ov-item ${d.status?'ov-on':'ov-off'}`}>
            <span>{DEVICE_ICONS[d.name]||'🔧'} {d.name}</span>
            <span className={`badge ${d.status?'badge-on':'badge-off'}`}>{d.status?'ON':'OFF'}</span>
          </div>
        ))}
      </div>
      {systemStatus && (
        <>
          <div className="section-title" style={{marginTop:'2rem'}}>System Info</div>
          <div className="info-grid">
            <div className="info-card"><div className="info-label">Model Type</div><div className="info-val">{systemStatus.model?.type}</div></div>
            <div className="info-card"><div className="info-label">DB Records</div><div className="info-val">{systemStatus.database?.records?.toLocaleString()}</div></div>
            <div className="info-card"><div className="info-label">DB Type</div><div className="info-val">SQLite</div></div>
            <div className="info-card"><div className="info-label">Model Loaded</div><div className="info-val">{systemStatus.model?.loaded?'✅ Yes':'❌ No'}</div></div>
          </div>
        </>
      )}
    </div>
  );
}

function DevicesPage({ devices, onToggle, onOverrideDuration }) {
  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Device Control</h1>
        <div className="page-sub">Manage all 5 smart devices · Click ⏱ to set AI override lock (5–60 min)</div>
      </div>
      <div className="devices-grid">
        {devices.map(d => (
          <DeviceCard key={d.id} device={d} onToggle={onToggle} onOverrideDuration={onOverrideDuration} />
        ))}
      </div>
    </div>
  );
}

function PredictionsPage() {
  const [pred, setPred] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetch_pred = useCallback(async () => {
    try {
      const r = await fetch(`${API}/current-prediction`);
      setPred(await r.json());
    } catch { /* ignore */ }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetch_pred();
    const t = setInterval(fetch_pred, 30000);
    return () => clearInterval(t);
  }, [fetch_pred]);

  if (loading) return <div className="page"><div className="spinner" /></div>;

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">AI Predictions <span className="title-chip">RF MODEL</span></h1>
        <div className="page-sub">
          {pred ? `${pred.model} · Temp: ${pred.temperature}°C · ${new Date(pred.timestamp).toLocaleTimeString()}` : ''}
        </div>
      </div>
      <div className="pred-grid">
        {pred?.predictions?.map(p => (
          <div key={p.device_id} className={`pred-card ${p.predicted_action ? 'pred-on' : 'pred-off'}`}>
            <div className="pred-icon">{DEVICE_ICONS[p.device_name] || '🔧'}</div>
            <div className="pred-name">{p.device_name}</div>
            <div className={`pred-state ${p.predicted_action ? 'state-on' : 'state-off'}`}>
              Predicted: {p.predicted_action ? 'ON' : 'OFF'}
            </div>
            {p.manually_locked && (
              <div className="pred-lock">🔒 Locked {p.lock_minutes_remaining}m</div>
            )}
            <div className="pred-conf-label">Confidence: {(p.confidence * 100).toFixed(1)}%</div>
            <ConfidenceBar value={p.confidence} color={p.predicted_action ? '#00E676' : '#FF5252'} />
          </div>
        ))}
      </div>
      <button className="refresh-btn" onClick={fetch_pred}>↻ Refresh Prediction</button>
    </div>
  );
}

function AnalyticsPage({ analytics }) {
  const [daily, setDaily] = useState(null);
  const [summary, setSummary] = useState(null);

  useEffect(() => {
    fetch(`${API}/history/daily`).then(r => r.json()).then(d => setDaily(d.daily)).catch(() => {});
    fetch(`${API}/history`).then(r => r.json()).then(d => setSummary(d.summary)).catch(() => {});
  }, []);

  const days = daily ? [...new Set(daily.map(r => r.day))].sort().slice(-14) : [];
  const deviceIds = [1,2,3,4,5];
  const deviceNames = { 1:'AC', 2:'Fan', 3:'Light', 4:'TV', 5:'Fridge' };
  const COLORS = { 1:'#6C63FF', 2:'#00D4FF', 3:'#FFD740', 4:'#FF8A80', 5:'#00E676' };

  const chartData = days.map(day => {
    const row = { day };
    deviceIds.forEach(id => {
      const r = daily?.find(x => x.day === day && x.device_id === id);
      row[id] = r ? r.on_count : 0;
    });
    return row;
  });
  const maxCount = Math.max(...chartData.flatMap(r => deviceIds.map(id => r[id])), 1);

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Analytics <span className="title-chip">14 DAYS</span></h1>
      </div>
      {summary && (
        <div className="ana-sum-grid">
          {summary.map(s => (
            <div key={s.device_id} className="ana-sum-card">
              <div className="ana-device-name">{DEVICE_ICONS[s.device_name]} {s.device_name}</div>
              <div className="ana-on-pct">{s.on_percentage}% ON</div>
              <div className="ana-track">
                <div className="ana-fill" style={{ width: `${s.on_percentage}%`, background: COLORS[s.device_id] }} />
              </div>
              <div className="ana-energy">{(s.total_energy_wh / 1000).toFixed(1)} kWh</div>
            </div>
          ))}
        </div>
      )}
      <div className="section-title" style={{marginTop:'2rem'}}>Daily ON Count — Last 14 Days</div>
      <div className="chart-wrap">
        <div className="chart-legend">
          {deviceIds.map(id => (
            <span key={id} className="legend-item">
              <span className="legend-dot" style={{background: COLORS[id]}} />
              {deviceNames[id]}
            </span>
          ))}
        </div>
        <div className="bar-chart">
          {chartData.map(row => (
            <div key={row.day} className="bar-col">
              <div className="bar-stacks">
                {deviceIds.map(id => (
                  <div
                    key={id} className="bar-seg"
                    style={{ height: `${(row[id] / maxCount) * 120}px`, background: COLORS[id], opacity: 0.85 }}
                    title={`${deviceNames[id]}: ${row[id]} times ON`}
                  />
                ))}
              </div>
              <div className="bar-label">{row.day?.slice(5)}</div>
            </div>
          ))}
        </div>
      </div>
      {analytics?.devices && (
        <>
          <div className="section-title" style={{marginTop:'2rem'}}>Device Performance</div>
          <div className="perf-table">
            <div className="perf-row perf-header">
              <span>Device</span><span>Actions</span><span>Accuracy</span><span>Energy</span>
            </div>
            {analytics.devices.map(d => (
              <div key={d.device_id} className="perf-row">
                <span>{DEVICE_ICONS[d.device_name]} {d.device_name}</span>
                <span>{d.total_actions?.toLocaleString()}</span>
                <span>
                  <div className="acc-bar"><div className="acc-fill" style={{width:`${d.avg_accuracy*100}%`}} /></div>
                  {(d.avg_accuracy*100).toFixed(1)}%
                </span>
                <span>{d.energy_total?.toFixed(0)} kWh</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// ── Notifications Page ────────────────────────────────────────────
const NODE_COLOR = {
  'User Manual Control': '#FFD740',
  'Agent Auto-Control':  '#00D4FF',
};
const ACTION_COLOR = { ON: '#00E676', OFF: '#FF5252' };

function NotificationsPage({ onMarkRead }) {
  const [notifs, setNotifs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all'); // all | manual | ai

  const load = useCallback(async () => {
    try {
      const r = await fetch(`${API}/notifications/24h`);
      const d = await r.json();
      setNotifs(d.notifications || []);
    } catch { /* ignore */ }
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
    // Poll every 3 seconds so new notifications appear almost instantly
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [load]);

  const markRead = async () => {
    await fetch(`${API}/notifications/read-all`, { method: 'POST' });
    setNotifs(prev => prev.map(n => ({ ...n, read: true })));
    onMarkRead();
  };

  const filtered = notifs.filter(n => {
    if (filter === 'manual') return n.node === 'User Manual Control';
    if (filter === 'ai')     return n.node === 'Agent Auto-Control';
    return true;
  });

  const fmt = ts => {
    const d = new Date(ts);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' · ' +
           d.toLocaleDateString([], { month: 'short', day: 'numeric' });
  };

  if (loading) return <div className="page"><div className="spinner" /></div>;

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Notifications <span className="title-chip">24H</span></h1>
        <div className="page-sub">{filtered.length} events in the last 24 hours</div>
      </div>

      <div className="notif-toolbar">
        <div className="notif-filters">
          {['all','manual','ai'].map(f => (
            <button
              key={f}
              className={`filter-btn ${filter === f ? 'filter-active' : ''}`}
              onClick={() => setFilter(f)}
            >
              {f === 'all' ? '📋 All' : f === 'manual' ? '👤 Manual' : '🤖 AI Auto'}
            </button>
          ))}
        </div>
        <div style={{display:'flex',gap:'0.5rem'}}>
          <button className="refresh-btn" onClick={load}>↻ Refresh</button>
          <button className="refresh-btn" onClick={markRead}>✓ Mark all read</button>
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="notif-empty">No events recorded in the last 24 hours.</div>
      ) : (
        <div className="notif-list">
          {filtered.map((n, i) => (
            <div
              key={n.id ?? i}
              className={`notif-item ${!n.read ? 'notif-unread' : ''}`}
            >
              <div className="notif-left">
                <span className="notif-device-icon">{DEVICE_ICONS[n.device] || '🔧'}</span>
                <div className="notif-body">
                  <div className="notif-title">
                    <strong>{n.device}</strong>
                    <span
                      className="notif-action-badge"
                      style={{ background: ACTION_COLOR[n.action] || '#888' }}
                    >{n.action}</span>
                    <span
                      className="notif-node-badge"
                      style={{ borderColor: NODE_COLOR[n.node] || '#555', color: NODE_COLOR[n.node] || '#aaa' }}
                    >{n.node}</span>
                  </div>
                  <div className="notif-reason">{n.reason}</div>
                  <div className="notif-meta">
                    <span>🕐 {fmt(n.timestamp)}</span>
                    {n.confidence != null && <span>· Conf: {n.confidence}%</span>}
                  </div>
                </div>
              </div>
              {!n.read && <span className="notif-dot" />}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function SettingsPage({ systemStatus, nightMode, onNightModeToggle }) {
  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Settings</h1>
      </div>
      <div className="settings-grid">
        <div className="settings-card">
          <h3>System</h3>
          <div className="setting-row"><span>API Server</span><span>http://localhost:8000</span></div>
          <div className="setting-row"><span>Version</span><span>4.0.0</span></div>
          <div className="setting-row"><span>Status</span><span className="badge badge-on">Online</span></div>
        </div>
        <div className="settings-card">
          <h3>ML Model</h3>
          <div className="setting-row"><span>Type</span><span>{systemStatus?.model?.type || 'RandomForest'}</span></div>
          <div className="setting-row"><span>Loaded</span><span>{systemStatus?.model?.loaded ? '✅ Yes' : '❌ No'}</span></div>
          <div className="setting-row"><span>Accuracy</span><span>{((systemStatus?.model?.accuracy||0)*100).toFixed(1)}%</span></div>
          <div className="setting-row"><span>Trend</span><span>{systemStatus?.model?.trend || 'Improving'}</span></div>
        </div>
        <div className="settings-card">
          <h3>Database</h3>
          <div className="setting-row"><span>Type</span><span>SQLite 🗄️</span></div>
          <div className="setting-row"><span>File</span><span>home_automation.db</span></div>
          <div className="setting-row"><span>Records</span><span>{systemStatus?.database?.records?.toLocaleString() || '—'}</span></div>
          <div className="setting-row"><span>History</span><span>14 days</span></div>
          <div className="setting-row"><span>Tables</span><span>two_week_logs, agent_logs, notifications</span></div>
        </div>
        <div className="settings-card">
          <h3>AI Override</h3>
          <div className="setting-row"><span>Default Lock</span><span>30 minutes</span></div>
          <div className="setting-row"><span>Range</span><span>5 – 60 minutes</span></div>
          <div className="setting-row"><span>Per Device</span><span>✅ Yes (use ⏱ button)</span></div>
          <div className="setting-row"><span>Notifications</span><span>Stored 24h in DB</span></div>
        </div>

        {/* ── Deep-Night Block ─────────────────────────────── */}
        <div className="settings-card night-mode-card">
          <h3>🌙 Deep-Night Block</h3>
          <p className="night-mode-desc">
            When <strong>ON</strong>, the AI will <em>not</em> automatically turn on
            <strong> Light</strong> or <strong>TV</strong> between&nbsp;
            <strong>11&nbsp;PM – 5&nbsp;AM</strong>. You can still control them manually.
            AC, Fan and Fridge are never blocked.
          </p>
          <div className="setting-row night-mode-row">
            <span className={`night-mode-label ${nightMode ? 'nm-on' : 'nm-off'}`}>
              {nightMode ? '🔒 Block active (sleep hours protected)' : '🔓 Block disabled (AI free to turn on anytime)'}
            </span>
            <button
              id="night-mode-toggle"
              className={`nm-toggle ${nightMode ? 'nm-toggle-on' : 'nm-toggle-off'}`}
              onClick={() => onNightModeToggle(!nightMode)}
              title={nightMode ? 'Click to disable deep-night block' : 'Click to enable deep-night block'}
            >
              <span className="nm-knob" />
            </button>
          </div>
          <div className="night-mode-hours">
            <span className="nm-hour">23:00</span>
            {[0,1,2,3,4,5].map(h => (
              <span key={h} className={`nm-hour ${nightMode ? 'nm-hour-blocked' : 'nm-hour-free'}`}>
                {String(h).padStart(2,'0')}:00
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── App ────────────────────────────────────────────────────────────
export default function App() {
  const [user, setUser]           = useState(() => {
    try { return JSON.parse(localStorage.getItem('hs_user')); } catch { return null; }
  });
  const [page, setPage]           = useState('dashboard');
  const [devices, setDevices]     = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [systemStatus, setSystemStatus] = useState(null);
  const [weather, setWeather]     = useState(null);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState(null);
  const [unread, setUnread]       = useState(0);
  const [nightMode, setNightMode] = useState(true); // deep-night block default ON
  const [isHome, setIsHome]       = useState(true); // presence mode: true = home

  // ── ALL HOOKS must come before any early return ──────────────────
  const refreshUnread = useCallback(() => {
    fetch(`${API}/notifications/unread-count`).then(r=>r.json()).then(d=>setUnread(d.count)).catch(()=>{});
  }, []);

  const refreshDevices = useCallback(() => {
    Promise.all([1,2,3,4,5].map(id=>
      fetch(`${API}/devices/${id}`).then(r=>r.json()).catch(()=>null)
    )).then(results => {
      const mapped = results.filter(Boolean).map(d => ({
        id: d.device_id, name: d.device_name, type: d.type, status: d.status,
        energy_consumption: [2500,150,100,200,500][d.device_id-1],
        manually_locked: d.manually_locked,
        lock_minutes_remaining: d.lock_minutes_remaining,
      }));
      if (mapped.length) setDevices(mapped);
    });
  }, []);

  useEffect(() => {
    if (!user) return; // skip data fetching when logged out
    const fetchAll = async () => {
      try {
        const [devR, anaR, sysR, wR] = await Promise.all([
          fetch(`${API}/devices/status`),
          fetch(`${API}/analytics`),
          fetch(`${API}/system/status`),
          fetch(`${API}/weather/current`),
        ]);
        setDevices(await devR.json());
        setAnalytics(await anaR.json());
        setSystemStatus(await sysR.json());
        setWeather(await wR.json());
        setError(null);
      } catch { setError('Cannot connect to backend. Is it running on port 8000?'); }
      setLoading(false);
    };
    fetchAll();
    refreshUnread();
    // Load deep-night mode state from backend
    fetch(`${API}/settings/night-mode`).then(r=>r.json()).then(d=>setNightMode(d.enabled)).catch(()=>{});
    // Load home/away status from backend
    fetch(`${API}/home/status`).then(r=>r.json()).then(d=>setIsHome(d.is_home)).catch(()=>{});
    // Poll devices + unread every 5s; unread count separately every 3s for near-instant notification badge
    const t5 = setInterval(() => {
      refreshDevices();
      fetch(`${API}/system/status`).then(r=>r.json()).then(setSystemStatus).catch(()=>{});
      fetch(`${API}/weather/current`).then(r=>r.json()).then(setWeather).catch(()=>{});
    }, 5000);
    const t3 = setInterval(refreshUnread, 3000);
    return () => { clearInterval(t5); clearInterval(t3); };
  }, [user, refreshDevices, refreshUnread]);
  // ── end hooks ─────────────────────────────────────────────────────

  const handleAuth = (userData) => {
    localStorage.setItem('hs_user', JSON.stringify(userData));
    setUser(userData);
  };

  const handleLogout = () => {
    localStorage.removeItem('hs_user');
    setUser(null);
  };

  // Auth guard — AFTER all hooks
  if (!user) return <AuthPage onAuth={handleAuth} />;

  const handleToggle = async (id, newStatus, durationMinutes=30) => {
    try {
      await fetch(`${API}/device/control`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({device_id:id, action:newStatus, duration_minutes:durationMinutes}),
      });
      // Immediately refresh devices AND unread badge so notification appears without waiting
      refreshDevices();
      refreshUnread();
    } catch { setError('Failed to control device'); }
  };

  const handleOverrideDuration = async (deviceId, minutes) => {
    try {
      await fetch(`${API}/device/override-duration`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({device_id:deviceId, minutes}),
      });
      refreshDevices();
    } catch { setError('Failed to update override duration'); }
  };

  const handleNightModeToggle = async (enabled) => {
    try {
      const r = await fetch(`${API}/settings/night-mode`, {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ enabled }),
      });
      const d = await r.json();
      setNightMode(d.enabled);
    } catch { setError('Failed to update deep-night mode'); }
  };

  const handleHomeToggle = async (newIsHome) => {
    try {
      const r = await fetch(`${API}/home/status`, {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ is_home: newIsHome }),
      });
      const d = await r.json();
      setIsHome(d.is_home);
      // Refresh devices + badge immediately so OFF state appears without waiting
      refreshDevices();
      refreshUnread();
    } catch { setError('Failed to update home/away status'); }
  };

  if (loading) return (
    <div className="app-loading">
      <div className="spinner" />
      <p>Connecting to HomeSense AI...</p>
    </div>
  );

  return (
    <div className="app">
      <Sidebar page={page} setPage={setPage} unread={unread} user={user} onLogout={handleLogout} />
      <main className="main">
        {error && (
          <div className="error-bar">⚠️ {error}<button onClick={()=>setError(null)}>✕</button></div>
        )}
        {page==='dashboard'     && <DashboardPage devices={devices} systemStatus={systemStatus} weather={weather} isHome={isHome} onHomeToggle={handleHomeToggle} />}
        {page==='devices'       && <DevicesPage devices={devices} onToggle={handleToggle} onOverrideDuration={handleOverrideDuration} />}
        {page==='predictions'   && <PredictionsPage />}
        {page==='analytics'     && <AnalyticsPage analytics={analytics} />}
        {page==='notifications' && <NotificationsPage onMarkRead={()=>setUnread(0)} />}
        {page==='settings'      && <SettingsPage systemStatus={systemStatus} weather={weather} user={user} nightMode={nightMode} onNightModeToggle={handleNightModeToggle} />}
      </main>
    </div>
  );
}


