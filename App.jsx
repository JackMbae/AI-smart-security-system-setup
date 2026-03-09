import { useState, useEffect, useRef } from "react";

const API = "http://localhost:8000/api/v1";
const WS_BASE = "ws://localhost:8000";

const SEVERITY_COLORS = { low: "#22c55e", medium: "#f59e0b", high: "#ef4444", critical: "#7c3aed" };
const EVENT_ICONS = {
  unknown_person: "🚨", known_person: "✅", loitering: "⚠️",
  intrusion: "🔴", night_activity: "🌙", package_delivered: "📦",
  package_removed: "📦", door_interaction: "🚪", motion_detected: "👁️",
};

function useApi(url) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    fetch(url).then(r => r.json()).then(d => { setData(d); setLoading(false); }).catch(() => setLoading(false));
  }, [url]);
  return { data, loading };
}

function Sidebar({ active, set }) {
  const tabs = [
    { id: "dashboard", label: "Dashboard", icon: "🏠" },
    { id: "cameras", label: "Cameras", icon: "📷" },
    { id: "events", label: "Events", icon: "📋" },
    { id: "faces", label: "Known Faces", icon: "👤" },
    { id: "system", label: "System", icon: "⚙️" },
  ];
  return (
    <div style={{ width: 220, background: "#0f172a", color: "#e2e8f0", display: "flex", flexDirection: "column" }}>
      <div style={{ padding: "24px 20px 16px", borderBottom: "1px solid #1e293b" }}>
        <div style={{ fontSize: 20, fontWeight: 700, color: "#38bdf8" }}>🛡️ SecureAI</div>
        <div style={{ fontSize: 11, color: "#64748b", marginTop: 2 }}>Smart Security System</div>
      </div>
      <nav style={{ padding: "12px 0", flex: 1 }}>
        {tabs.map(t => (
          <button key={t.id} onClick={() => set(t.id)} style={{
            display: "flex", alignItems: "center", gap: 10, width: "100%",
            padding: "11px 20px", border: "none",
            background: active === t.id ? "#1e3a5f" : "transparent",
            color: active === t.id ? "#38bdf8" : "#94a3b8",
            cursor: "pointer", fontSize: 14, textAlign: "left",
            borderLeft: active === t.id ? "3px solid #38bdf8" : "3px solid transparent",
          }}>
            <span style={{ fontSize: 18 }}>{t.icon}</span>{t.label}
          </button>
        ))}
      </nav>
    </div>
  );
}

function EventCard({ evt }) {
  return (
    <div style={{
      background: "#0f172a", borderRadius: 8, padding: "10px 12px", marginBottom: 8,
      borderLeft: `3px solid ${SEVERITY_COLORS[evt.severity] || "#475569"}`,
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: 13, color: "#e2e8f0", fontWeight: 500 }}>
          {EVENT_ICONS[evt.event_type] || "🔔"} {evt.description || evt.event_type}
        </span>
        <span style={{
          fontSize: 10, padding: "2px 7px", borderRadius: 10,
          background: (SEVERITY_COLORS[evt.severity] || "#475569") + "22",
          color: SEVERITY_COLORS[evt.severity] || "#475569",
        }}>{(evt.severity || "").toUpperCase()}</span>
      </div>
      <div style={{ fontSize: 11, color: "#64748b", marginTop: 4 }}>
        📷 {evt.camera_name || `Camera ${evt.camera_id}`} • {new Date(evt.timestamp).toLocaleTimeString()}
        {evt.person_name && ` • 👤 ${evt.person_name}`}
      </div>
    </div>
  );
}

function DashboardView({ liveEvents }) {
  const { data: cameras } = useApi(`${API}/cameras`);
  const { data: stats } = useApi(`${API}/events/stats/summary`);
  const statCards = [
    { label: "Active Cameras", value: cameras?.length || 0, icon: "📷", color: "#38bdf8" },
    { label: "Events (24h)", value: stats?.total || 0, icon: "📋", color: "#f59e0b" },
    { label: "Intrusions", value: stats?.by_type?.intrusion || 0, icon: "🔴", color: "#ef4444" },
    { label: "Unknown Persons", value: stats?.by_type?.unknown_person || 0, icon: "🚨", color: "#7c3aed" },
  ];
  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 16, marginBottom: 24 }}>
        {statCards.map(s => (
          <div key={s.label} style={{ background: "#1e293b", borderRadius: 12, padding: 20, border: `1px solid ${s.color}22` }}>
            <div style={{ fontSize: 28 }}>{s.icon}</div>
            <div style={{ fontSize: 32, fontWeight: 700, color: s.color, marginTop: 8 }}>{s.value}</div>
            <div style={{ color: "#64748b", fontSize: 13, marginTop: 4 }}>{s.label}</div>
          </div>
        ))}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        <div>
          <h3 style={{ color: "#e2e8f0", margin: "0 0 12px", fontSize: 14 }}>📷 Camera Feeds</h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            {(cameras || []).slice(0, 4).map(cam => (
              <div key={cam.id} style={{ background: "#1e293b", borderRadius: 10, overflow: "hidden", border: "1px solid #334155" }}>
                <div style={{ background: "#000", height: 140, position: "relative" }}>
                  <img src={`${API}/stream/${cam.id}/snapshot`} alt={cam.name}
                    style={{ width: "100%", height: "100%", objectFit: "cover" }}
                    onError={e => { e.target.parentElement.style.background = "#1a1a2e"; }} />
                  <div style={{ position: "absolute", top: 6, left: 6, background: "rgba(0,0,0,.7)", color: "#22c55e", padding: "2px 7px", borderRadius: 4, fontSize: 10 }}>● LIVE</div>
                </div>
                <div style={{ padding: "8px 10px" }}>
                  <div style={{ color: "#e2e8f0", fontSize: 13, fontWeight: 600 }}>{cam.name}</div>
                  <div style={{ color: "#64748b", fontSize: 11 }}>{cam.location || "No location"}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
        <div style={{ background: "#1e293b", borderRadius: 12, padding: 16, height: 340, overflowY: "auto" }}>
          <h3 style={{ color: "#e2e8f0", margin: "0 0 12px", fontSize: 14 }}>🔴 Live Alerts</h3>
          {liveEvents.length === 0
            ? <div style={{ color: "#475569", textAlign: "center", paddingTop: 60 }}>No recent alerts</div>
            : liveEvents.map((evt, i) => <EventCard key={i} evt={evt} />)
          }
        </div>
      </div>
    </div>
  );
}

function CamerasView() {
  const { data: cameras, loading } = useApi(`${API}/cameras`);
  const [form, setForm] = useState({ name: "", stream_url: "", location: "" });
  const [showAdd, setShowAdd] = useState(false);
  const [msg, setMsg] = useState("");

  const handleAdd = async () => {
    const r = await fetch(`${API}/cameras`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form) });
    if (r.ok) { setMsg("Camera added!"); setShowAdd(false); } else setMsg("Error");
  };
  const handleDelete = async (id) => {
    if (confirm("Delete?")) { await fetch(`${API}/cameras/${id}`, { method: "DELETE" }); window.location.reload(); }
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 20 }}>
        <h2 style={{ color: "#e2e8f0", margin: 0 }}>📷 Camera Management</h2>
        <button onClick={() => setShowAdd(!showAdd)} style={{ background: "#38bdf8", color: "#0f172a", border: "none", padding: "9px 18px", borderRadius: 8, cursor: "pointer", fontWeight: 600 }}>+ Add Camera</button>
      </div>
      {msg && <div style={{ background: "#1e3a5f", color: "#38bdf8", padding: "10px 14px", borderRadius: 8, marginBottom: 16 }}>{msg}</div>}
      {showAdd && (
        <div style={{ background: "#1e293b", borderRadius: 12, padding: 20, marginBottom: 20 }}>
          {["name", "stream_url", "location"].map(f => (
            <div key={f} style={{ marginBottom: 12 }}>
              <label style={{ color: "#94a3b8", fontSize: 12, display: "block", marginBottom: 4 }}>{f.toUpperCase()}</label>
              <input value={form[f]} onChange={e => setForm({ ...form, [f]: e.target.value })} placeholder={f === "stream_url" ? "rtsp://user:pass@ip/stream" : ""}
                style={{ width: "100%", padding: "9px 12px", background: "#0f172a", border: "1px solid #334155", borderRadius: 8, color: "#e2e8f0", fontSize: 14, boxSizing: "border-box" }} />
            </div>
          ))}
          <div style={{ display: "flex", gap: 10 }}>
            <button onClick={handleAdd} style={{ background: "#22c55e", color: "#fff", border: "none", padding: "9px 18px", borderRadius: 8, cursor: "pointer", fontWeight: 600 }}>Add Camera</button>
            <button onClick={() => setShowAdd(false)} style={{ background: "#334155", color: "#e2e8f0", border: "none", padding: "9px 18px", borderRadius: 8, cursor: "pointer" }}>Cancel</button>
          </div>
        </div>
      )}
      {loading ? <div style={{ color: "#475569", textAlign: "center", padding: 40 }}>Loading...</div> : (
        <div style={{ display: "grid", gap: 12 }}>
          {(cameras || []).map(cam => (
            <div key={cam.id} style={{ background: "#1e293b", borderRadius: 12, padding: 18, display: "flex", justifyContent: "space-between", alignItems: "center", border: "1px solid #334155" }}>
              <div>
                <div style={{ color: "#e2e8f0", fontWeight: 600, fontSize: 15 }}><span style={{ color: "#22c55e" }}>● </span>{cam.name}</div>
                <div style={{ color: "#64748b", fontSize: 12, marginTop: 4 }}>{cam.stream_url}</div>
                <div style={{ color: "#475569", fontSize: 12 }}>📍 {cam.location || "No location"}</div>
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <a href={`http://localhost:8000/api/v1/stream/${cam.id}/mjpeg`} target="_blank" rel="noreferrer"
                  style={{ background: "#1e3a5f", color: "#38bdf8", border: "1px solid #38bdf8", padding: "7px 14px", borderRadius: 8, fontSize: 12, textDecoration: "none" }}>▶ Stream</a>
                <button onClick={() => handleDelete(cam.id)} style={{ background: "#450a0a", color: "#ef4444", border: "1px solid #ef4444", padding: "7px 14px", borderRadius: 8, cursor: "pointer", fontSize: 12 }}>Delete</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function EventsView() {
  const { data: events, loading } = useApi(`${API}/events?limit=100`);
  const ack = async (id) => { await fetch(`${API}/events/${id}/acknowledge`, { method: "PATCH" }); };
  return (
    <div>
      <h2 style={{ color: "#e2e8f0", margin: "0 0 20px" }}>📋 Security Events</h2>
      {loading ? <div style={{ color: "#475569", textAlign: "center", padding: 40 }}>Loading...</div> : (
        <div>
          {(events || []).map(evt => (
            <div key={evt.id} style={{
              background: "#1e293b", borderRadius: 10, padding: "12px 16px", marginBottom: 8,
              display: "flex", justifyContent: "space-between", alignItems: "center",
              borderLeft: `4px solid ${SEVERITY_COLORS[evt.severity] || "#475569"}`,
              opacity: evt.acknowledged ? 0.6 : 1,
            }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span style={{ fontSize: 18 }}>{EVENT_ICONS[evt.event_type] || "🔔"}</span>
                  <span style={{ color: "#e2e8f0", fontWeight: 500, fontSize: 14 }}>{evt.description || evt.event_type}</span>
                  <span style={{ fontSize: 10, padding: "2px 7px", borderRadius: 10, background: (SEVERITY_COLORS[evt.severity] || "#475569") + "22", color: SEVERITY_COLORS[evt.severity] || "#475569" }}>{(evt.severity || "").toUpperCase()}</span>
                </div>
                <div style={{ color: "#64748b", fontSize: 12, marginTop: 4 }}>
                  📷 Camera {evt.camera_id} {evt.person_name && `• 👤 ${evt.person_name}`} {evt.zone_name && `• 📍 ${evt.zone_name}`} • {new Date(evt.timestamp).toLocaleString()}
                </div>
              </div>
              {!evt.acknowledged && <button onClick={() => ack(evt.id)} style={{ background: "#052e16", color: "#22c55e", border: "1px solid #22c55e", padding: "5px 12px", borderRadius: 6, cursor: "pointer", fontSize: 12, marginLeft: 12 }}>✓ Ack</button>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function FacesView() {
  const { data: persons, loading } = useApi(`${API}/faces`);
  const [name, setName] = useState(""); const [role, setRole] = useState("known");
  const [file, setFile] = useState(null); const [msg, setMsg] = useState("");

  const handleUpload = async () => {
    if (!name || !file) { setMsg("Name and image required"); return; }
    const fd = new FormData();
    fd.append("name", name); fd.append("role", role); fd.append("image", file);
    const r = await fetch(`${API}/faces`, { method: "POST", body: fd });
    if (r.ok) { setMsg(`✅ ${name} added`); setName(""); setFile(null); }
    else { const e = await r.json(); setMsg(`❌ ${e.detail}`); }
  };
  const del = async (id, n) => { if (confirm(`Delete ${n}?`)) { await fetch(`${API}/faces/${id}`, { method: "DELETE" }); window.location.reload(); } };

  return (
    <div>
      <h2 style={{ color: "#e2e8f0", margin: "0 0 20px" }}>👤 Known Faces Database</h2>
      <div style={{ background: "#1e293b", borderRadius: 12, padding: 20, marginBottom: 20 }}>
        <h3 style={{ color: "#e2e8f0", margin: "0 0 16px", fontSize: 15 }}>Add New Person</h3>
        {msg && <div style={{ background: "#1e3a5f", color: "#38bdf8", padding: "8px 12px", borderRadius: 6, marginBottom: 12 }}>{msg}</div>}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 2fr auto", gap: 12, alignItems: "end" }}>
          <div><label style={{ color: "#94a3b8", fontSize: 12, display: "block", marginBottom: 4 }}>NAME</label>
            <input value={name} onChange={e => setName(e.target.value)} style={{ width: "100%", padding: "9px 12px", background: "#0f172a", border: "1px solid #334155", borderRadius: 8, color: "#e2e8f0", fontSize: 14, boxSizing: "border-box" }} /></div>
          <div><label style={{ color: "#94a3b8", fontSize: 12, display: "block", marginBottom: 4 }}>ROLE</label>
            <select value={role} onChange={e => setRole(e.target.value)} style={{ width: "100%", padding: "9px 12px", background: "#0f172a", border: "1px solid #334155", borderRadius: 8, color: "#e2e8f0", fontSize: 14 }}>
              <option value="known">Known</option><option value="family">Family</option><option value="employee">Employee</option></select></div>
          <div><label style={{ color: "#94a3b8", fontSize: 12, display: "block", marginBottom: 4 }}>PHOTO</label>
            <input type="file" accept="image/*" onChange={e => setFile(e.target.files[0])} style={{ width: "100%", padding: "9px 12px", background: "#0f172a", border: "1px solid #334155", borderRadius: 8, color: "#94a3b8", fontSize: 13, boxSizing: "border-box" }} /></div>
          <button onClick={handleUpload} style={{ background: "#22c55e", color: "#fff", border: "none", padding: "9px 18px", borderRadius: 8, cursor: "pointer", fontWeight: 600 }}>Add</button>
        </div>
      </div>
      {loading ? <div style={{ color: "#475569", textAlign: "center", padding: 40 }}>Loading...</div> : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 14 }}>
          {(persons || []).map(p => (
            <div key={p.id} style={{ background: "#1e293b", borderRadius: 12, padding: 16, textAlign: "center", border: "1px solid #334155" }}>
              <div style={{ width: 56, height: 56, borderRadius: "50%", background: "#38bdf822", margin: "0 auto 10px", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 24 }}>👤</div>
              <div style={{ color: "#e2e8f0", fontWeight: 600 }}>{p.name}</div>
              <div style={{ background: "#0f172a", color: "#38bdf8", padding: "2px 8px", borderRadius: 10, fontSize: 11, display: "inline-block", marginTop: 6 }}>{p.role}</div>
              <div style={{ marginTop: 10 }}>
                <button onClick={() => del(p.id, p.name)} style={{ background: "transparent", color: "#ef4444", border: "1px solid #ef4444", padding: "4px 10px", borderRadius: 6, cursor: "pointer", fontSize: 11 }}>Remove</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function SystemView() {
  const { data: status } = useApi(`http://localhost:8000/api/v1/system/status`);
  return (
    <div>
      <h2 style={{ color: "#e2e8f0", margin: "0 0 20px" }}>⚙️ System Status</h2>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        <div style={{ background: "#1e293b", borderRadius: 12, padding: 20 }}>
          <h3 style={{ color: "#e2e8f0", margin: "0 0 16px", fontSize: 14 }}>System Resources</h3>
          {[
            { label: "CPU Usage", value: `${status?.cpu_percent?.toFixed(1) || "—"}%`, warn: status?.cpu_percent > 80 },
            { label: "Memory Usage", value: `${status?.memory_percent?.toFixed(1) || "—"}%`, warn: status?.memory_percent > 85 },
            { label: "WebSocket Clients", value: status?.websocket_connections || 0 },
          ].map(item => (
            <div key={item.label} style={{ display: "flex", justifyContent: "space-between", padding: "10px 0", borderBottom: "1px solid #334155" }}>
              <span style={{ color: "#94a3b8", fontSize: 13 }}>{item.label}</span>
              <span style={{ color: item.warn ? "#ef4444" : "#22c55e", fontWeight: 600 }}>{item.value}</span>
            </div>
          ))}
        </div>
        <div style={{ background: "#1e293b", borderRadius: 12, padding: 20 }}>
          <h3 style={{ color: "#e2e8f0", margin: "0 0 16px", fontSize: 14 }}>Active Pipelines</h3>
          {(status?.pipelines || []).map(p => (
            <div key={p.camera_id} style={{ background: "#0f172a", borderRadius: 8, padding: "10px 12px", marginBottom: 8 }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "#e2e8f0", fontSize: 13 }}>{p.camera_name}</span>
                <span style={{ color: "#22c55e", fontSize: 12 }}>{p.fps} FPS</span>
              </div>
              <div style={{ color: "#64748b", fontSize: 11, marginTop: 4 }}>Frames: {p.frame_count?.toLocaleString()} • Tracked: {p.tracked_objects}</div>
            </div>
          ))}
          {(!status?.pipelines || status.pipelines.length === 0) && <div style={{ color: "#475569", fontSize: 13 }}>No active pipelines</div>}
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [activeTab, setActiveTab] = useState("dashboard");
  const [liveEvents, setLiveEvents] = useState([]);

  useEffect(() => {
    const connect = () => {
      const ws = new WebSocket(`${WS_BASE}/ws/events`);
      ws.onmessage = e => {
        const msg = JSON.parse(e.data);
        if (msg.type === "security_event") setLiveEvents(prev => [msg.data, ...prev].slice(0, 50));
      };
      ws.onclose = () => setTimeout(connect, 3000);
    };
    try { connect(); } catch {}
  }, []);

  const views = { dashboard: <DashboardView liveEvents={liveEvents} />, cameras: <CamerasView />, events: <EventsView />, faces: <FacesView />, system: <SystemView /> };

  return (
    <div style={{ display: "flex", height: "100vh", background: "#0f172a", fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif", overflow: "hidden" }}>
      <Sidebar active={activeTab} set={setActiveTab} />
      <main style={{ flex: 1, overflowY: "auto", padding: 28 }}>{views[activeTab]}</main>
    </div>
  );
}
