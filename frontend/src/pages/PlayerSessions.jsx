import { useEffect, useState } from "react";
import { http, formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { Trash2 } from "lucide-react";
import { SESSION_TYPES, SessionTypeBadge } from "@/components/Bits";

export default function PlayerSessions() {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const { data } = await http.get("/player/sessions");
      setSessions(data || []);
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setLoading(false); }
  }
  useEffect(() => { load(); }, []);

  async function remove(s) {
    if (!window.confirm(`Eliminar sessão de ${s.date}?`)) return;
    try {
      await http.delete(`/player/sessions/${s.id}`);
      toast.success("Sessão eliminada");
      load();
    } catch (err) { toast.error(formatApiError(err)); }
  }

  return (
    <div className="space-y-6" data-testid="player-sessions">
      <div>
        <div className="text-xs text-[#CCFF00] tracking-[0.3em] uppercase mb-2">Histórico</div>
        <h1 className="font-head text-3xl sm:text-4xl font-black leading-none">MINHAS SESSÕES</h1>
        <p className="text-[#A3A3A3] text-xs sm:text-sm mt-2">
          {sessions.length} sessões registadas
        </p>
      </div>

      {loading ? (
        <div className="text-center py-20 text-[#A3A3A3]">A carregar...</div>
      ) : sessions.length === 0 ? (
        <div className="fld-card text-center py-12">
          <div className="text-[#A3A3A3] text-sm">Ainda não tens sessões registadas.</div>
        </div>
      ) : (
        <div className="space-y-2">
          {sessions.map((s) => {
            const meta = SESSION_TYPES[s.session_type] || SESSION_TYPES.training;
            return (
              <div key={s.id} data-testid={`session-${s.id}`} className="fld-card flex items-center gap-4" style={{ borderLeft: `3px solid ${meta.color}` }}>
                <div className="shrink-0">
                  <div className="text-[10px] uppercase tracking-widest text-[#525252]">Data</div>
                  <div className="font-head text-base font-bold">{s.date}</div>
                </div>
                <div className="flex-1 grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                  <div>
                    <div className="text-[9px] uppercase tracking-widest text-[#525252]">Tipo</div>
                    <SessionTypeBadge type={s.session_type} size="sm" />
                  </div>
                  <div>
                    <div className="text-[9px] uppercase tracking-widest text-[#525252]">RPE / Duração</div>
                    <div className="metric-num text-sm">{s.rpe} <span className="text-[#525252]">·</span> {s.duration_min}m</div>
                  </div>
                  <div>
                    <div className="text-[9px] uppercase tracking-widest text-[#525252]">Sono</div>
                    <div className="metric-num text-sm">{s.sleep_quality ?? "—"}/5</div>
                  </div>
                  <div>
                    <div className="text-[9px] uppercase tracking-widest text-[#525252]">Bem-estar</div>
                    <div className="metric-num text-sm">{s.wellness ?? "—"}/10</div>
                  </div>
                </div>
                <button
                  onClick={() => remove(s)}
                  data-testid={`delete-${s.id}`}
                  className="shrink-0 text-[#525252] hover:text-[#FF3B30] p-1"
                  title="Eliminar"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
