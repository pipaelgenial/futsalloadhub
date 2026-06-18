import { useEffect, useRef, useState, useCallback } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { http, formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { Bell, Check, RotateCcw, AlertTriangle, AlertOctagon, Activity, Heart, Moon, Battery } from "lucide-react";

const RESOLVED_KEY = "fld_alerts_resolved";
const SEEN_KEY = "fld_alerts_seen";
const DASHBOARD_TOAST_KEY = "fld_alerts_dash_toast_at";

function loadResolved() {
  try { return new Set(JSON.parse(localStorage.getItem(RESOLVED_KEY) || "[]")); }
  catch { return new Set(); }
}
function saveResolved(set) {
  localStorage.setItem(RESOLVED_KEY, JSON.stringify(Array.from(set)));
}
function loadSeen() {
  try { return new Set(JSON.parse(localStorage.getItem(SEEN_KEY) || "[]")); }
  catch { return new Set(); }
}
function saveSeen(set) {
  localStorage.setItem(SEEN_KEY, JSON.stringify(Array.from(set)));
}

const TYPE_ICON = {
  acwr_high: AlertOctagon,
  acwr_low: Activity,
  monotony_critical: AlertTriangle,
  strain_extreme: AlertOctagon,
  sleep_poor: Moon,
  wellness_low: Battery,
  injury_open: Heart,
};

function severityStyle(s) {
  if (s === "danger") return { bg: "rgba(255,59,48,0.10)", border: "#FF3B30", text: "#FF3B30", dot: "bg-[#FF3B30]" };
  if (s === "warning") return { bg: "rgba(255,149,0,0.10)", border: "#FF9500", text: "#FF9500", dot: "bg-[#FF9500]" };
  return { bg: "rgba(204,255,0,0.08)", border: "#CCFF00", text: "#CCFF00", dot: "bg-[#CCFF00]" };
}

export default function NotificationsBell({ testid = "notifications-bell" }) {
  const [alerts, setAlerts] = useState([]);
  const [resolved, setResolved] = useState(loadResolved());
  const [seen, setSeen] = useState(loadSeen());
  const [open, setOpen] = useState(false);
  const [showResolved, setShowResolved] = useState(false);
  const ref = useRef(null);
  const navigate = useNavigate();
  const location = useLocation();
  const onDashboardMount = location.pathname === "/";

  const fetchAlerts = useCallback(async () => {
    try {
      const { data } = await http.get("/alerts");
      setAlerts(Array.isArray(data) ? data : []);
    } catch (err) {
      // Silent; app may still be initialising
      console.error(formatApiError(err));
    }
  }, []);

  useEffect(() => {
    fetchAlerts();
    const t = setInterval(fetchAlerts, 60000); // refresh every minute
    return () => clearInterval(t);
  }, [fetchAlerts]);

  // Close on outside click
  useEffect(() => {
    function onClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  // On dashboard mount: toast danger alerts that are NEW (unseen + unresolved)
  useEffect(() => {
    if (!onDashboardMount || alerts.length === 0) return;
    const last = Number(localStorage.getItem(DASHBOARD_TOAST_KEY) || 0);
    if (Date.now() - last < 5 * 60 * 1000) return; // throttle 5min
    const newDangers = alerts.filter(
      (a) => a.severity === "danger" && !resolved.has(a.id) && !seen.has(a.id),
    );
    if (newDangers.length > 0) {
      const headline = newDangers.length === 1
        ? `${newDangers[0].athlete_name}: ${newDangers[0].title}`
        : `${newDangers.length} alertas de risco elevado`;
      toast.error(headline, {
        description: "Abre o sino de notificações para ver detalhes.",
        duration: 6000,
      });
      localStorage.setItem(DASHBOARD_TOAST_KEY, String(Date.now()));
    }
     
  }, [alerts.length, onDashboardMount]);

  const active = alerts.filter((a) => !resolved.has(a.id));
  const unseenCount = active.filter((a) => !seen.has(a.id)).length;
  const dangerCount = active.filter((a) => a.severity === "danger").length;

  function markAllSeen() {
    const next = new Set(seen);
    active.forEach((a) => next.add(a.id));
    setSeen(next);
    saveSeen(next);
  }

  function toggleOpen() {
    const next = !open;
    setOpen(next);
    if (next) markAllSeen();
  }

  function resolveAlert(id) {
    const next = new Set(resolved);
    next.add(id);
    setResolved(next);
    saveResolved(next);
  }

  function unresolveAlert(id) {
    const next = new Set(resolved);
    next.delete(id);
    setResolved(next);
    saveResolved(next);
  }

  function clearResolved() {
    const stillActive = new Set(alerts.map((a) => a.id));
    // Keep only resolved that are no longer active (they auto-cleared from list).
    const keep = new Set();
    resolved.forEach((id) => { if (!stillActive.has(id)) keep.add(id); });
    setResolved(keep);
    saveResolved(keep);
    toast.success("Resolvidos limpos");
  }

  const resolvedList = alerts.filter((a) => resolved.has(a.id));

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={toggleOpen}
        data-testid={testid}
        aria-label="Notificações"
        className="relative flex items-center justify-center w-9 h-9 border border-white/10 hover:border-white/30 bg-[#0F0F0F] transition-all"
      >
        <Bell className={`w-4 h-4 ${dangerCount > 0 ? "text-[#FF3B30]" : "text-[#A3A3A3]"}`} />
        {unseenCount > 0 && (
          <span
            data-testid="notifications-badge"
            className={`absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 font-head text-[10px] font-bold flex items-center justify-center ${
              dangerCount > 0 ? "bg-[#FF3B30] text-white" : "bg-[#FF9500] text-black"
            }`}
          >
            {unseenCount > 9 ? "9+" : unseenCount}
          </span>
        )}
      </button>

      {open && (
        <div
          data-testid="notifications-dropdown"
          className="absolute right-0 mt-2 w-[360px] max-w-[calc(100vw-2rem)] bg-[#0F0F0F] border border-white/10 z-50 shadow-2xl"
        >
          <div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
            <div>
              <div className="text-[9px] uppercase tracking-widest text-[#525252]">Notificações</div>
              <div className="font-head text-sm font-bold">
                {active.length} ativa{active.length !== 1 ? "s" : ""}
                {dangerCount > 0 && <span className="text-[#FF3B30] ml-2">· {dangerCount} risco elevado</span>}
              </div>
            </div>
            <button
              onClick={() => setShowResolved((s) => !s)}
              data-testid="toggle-resolved"
              className="text-[10px] uppercase tracking-widest text-[#A3A3A3] hover:text-white transition-colors"
            >
              {showResolved ? "Esconder resolvidos" : `Ver resolvidos (${resolvedList.length})`}
            </button>
          </div>

          <div className="max-h-[420px] overflow-y-auto">
            {active.length === 0 && !showResolved && (
              <div className="text-center py-10 px-4 text-[#525252] text-sm" data-testid="notifications-empty">
                <Check className="w-8 h-8 mx-auto mb-2 text-[#CCFF00]/50" />
                Tudo em ordem. Sem alertas no momento.
              </div>
            )}

            {active.map((a) => {
              const st = severityStyle(a.severity);
              const Icon = TYPE_ICON[a.type] || AlertTriangle;
              return (
                <div
                  key={a.id}
                  data-testid={`alert-item-${a.id}`}
                  className="flex items-start gap-3 px-4 py-3 border-b border-white/5 hover:bg-white/[0.02] transition-colors"
                  style={{ borderLeft: `3px solid ${st.border}`, background: st.bg }}
                >
                  <div className="shrink-0 mt-0.5">
                    <Icon className="w-4 h-4" style={{ color: st.text }} />
                  </div>
                  <button
                    type="button"
                    onClick={() => { setOpen(false); if (a.athlete_id) navigate(`/atletas/${a.athlete_id}`); }}
                    className="flex-1 min-w-0 text-left"
                    data-testid={`alert-open-${a.id}`}
                  >
                    <div className="flex items-center gap-1.5">
                      <span className="font-head text-xs font-bold truncate" style={{ color: st.text }}>{a.title}</span>
                      <span className="text-[#A3A3A3] text-[11px] truncate">· {a.athlete_name}</span>
                    </div>
                    <div className="text-[11px] text-[#A3A3A3] mt-0.5 break-words">{a.message}</div>
                  </button>
                  <button
                    type="button"
                    onClick={() => resolveAlert(a.id)}
                    title="Marcar como resolvido"
                    data-testid={`alert-resolve-${a.id}`}
                    className="shrink-0 text-[#525252] hover:text-[#CCFF00] transition-colors"
                  >
                    <Check className="w-4 h-4" />
                  </button>
                </div>
              );
            })}

            {showResolved && resolvedList.length > 0 && (
              <>
                <div className="px-4 py-2 text-[9px] uppercase tracking-widest text-[#525252] bg-black/40">Resolvidos</div>
                {resolvedList.map((a) => {
                  const Icon = TYPE_ICON[a.type] || AlertTriangle;
                  return (
                    <div
                      key={a.id}
                      data-testid={`alert-resolved-${a.id}`}
                      className="flex items-start gap-3 px-4 py-2.5 border-b border-white/5 opacity-60"
                    >
                      <Icon className="w-3.5 h-3.5 text-[#525252] mt-0.5" />
                      <div className="flex-1 min-w-0">
                        <div className="text-xs text-[#A3A3A3] line-through truncate">{a.title} · {a.athlete_name}</div>
                        <div className="text-[10px] text-[#525252] truncate">{a.message}</div>
                      </div>
                      <button
                        onClick={() => unresolveAlert(a.id)}
                        title="Reabrir"
                        data-testid={`alert-reopen-${a.id}`}
                        className="text-[#525252] hover:text-[#FF9500]"
                      >
                        <RotateCcw className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  );
                })}
              </>
            )}
          </div>

          {resolvedList.length > 0 && (
            <button
              onClick={clearResolved}
              data-testid="clear-resolved"
              className="w-full text-[10px] uppercase tracking-widest text-[#A3A3A3] hover:text-white border-t border-white/10 py-2.5 transition-colors"
            >
              Limpar histórico de resolvidos
            </button>
          )}
        </div>
      )}
    </div>
  );
}
