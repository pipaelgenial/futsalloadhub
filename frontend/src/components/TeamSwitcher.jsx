import { useEffect, useRef, useState, useCallback } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { http, formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { ChevronDown, Check, Plus } from "lucide-react";
import TeamLogo from "@/components/TeamLogo";

/**
 * Displays the current active team and allows switching between user's teams (up to 5).
 * Compact variant for header use. On switch -> activate API + window.location.reload to refresh data.
 */
export default function TeamSwitcher() {
  const [teams, setTeams] = useState([]);
  const [open, setOpen] = useState(false);
  const [switching, setSwitching] = useState(false);
  const ref = useRef(null);
  const navigate = useNavigate();
  const location = useLocation();

  const load = useCallback(async () => {
    try {
      const { data } = await http.get("/teams");
      setTeams(data || []);
    } catch (err) {
      console.error(err);
    }
  }, []);

  // Refetch on route change (covers create/delete from /equipa)
  useEffect(() => { load(); }, [load, location.pathname]);

  // Also refetch when opening the dropdown so the list is always fresh
  function toggleOpen() {
    const next = !open;
    setOpen(next);
    if (next) load();
  }

  useEffect(() => {
    function onClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const active = teams.find((t) => t.active) || teams[0];

  async function switchTeam(id) {
    if (!id || switching || id === active?.id) { setOpen(false); return; }
    setSwitching(true);
    try {
      await http.post(`/teams/${id}/activate`);
      toast.success("Equipa alterada");
      // Hard reload so dashboards, calendars and atletas refetch with new team context
      window.location.reload();
    } catch (err) {
      toast.error(formatApiError(err));
      setSwitching(false);
    }
  }

  if (!teams.length) {
    return (
      <button
        onClick={() => navigate("/equipa")}
        data-testid="team-switcher-create"
        className="flex items-center gap-2 px-3 py-2 border border-[#CCFF00]/50 text-[#CCFF00] hover:bg-[#CCFF00]/10 transition-all font-head text-xs uppercase tracking-widest"
      >
        <Plus className="w-3.5 h-3.5" /> Criar Equipa
      </button>
    );
  }

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={toggleOpen}
        disabled={switching}
        data-testid="team-switcher-btn"
        className="flex items-center gap-2.5 px-2 py-1.5 border border-white/10 hover:border-white/30 bg-[#0F0F0F] transition-all w-full text-left"
      >
        <div className="shrink-0">
          <TeamLogo team={active} size={32} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[9px] uppercase tracking-widest text-[#525252]">Equipa Ativa</div>
          <div className="font-head text-sm font-bold truncate" data-testid="active-team-name">{active?.name || "—"}</div>
        </div>
        <ChevronDown className={`w-3.5 h-3.5 text-[#A3A3A3] shrink-0 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div
          data-testid="team-switcher-dropdown"
          className="absolute left-0 right-0 mt-1 bg-[#0F0F0F] border border-white/10 z-50 shadow-2xl"
        >
          <div className="text-[9px] uppercase tracking-widest text-[#525252] px-3 pt-2 pb-1">
            {teams.length} equipa{teams.length !== 1 ? "s" : ""} · máx 5
          </div>
          <div className="max-h-72 overflow-y-auto">
            {teams.map((t) => {
              const isActive = t.id === active?.id;
              return (
                <button
                  key={t.id}
                  onClick={() => switchTeam(t.id)}
                  disabled={switching}
                  data-testid={`team-switcher-item-${t.id}`}
                  className={`w-full flex items-center gap-2.5 px-3 py-2 text-left border-l-2 transition-all ${
                    isActive
                      ? "border-[#CCFF00] bg-white/5"
                      : "border-transparent hover:bg-white/5"
                  }`}
                >
                  <TeamLogo team={t} size={28} />
                  <div className="flex-1 min-w-0">
                    <div className="font-head text-xs font-bold truncate">{t.name}</div>
                    <div className="text-[10px] text-[#A3A3A3] truncate">{t.escalao} · {t.epoca}</div>
                  </div>
                  {isActive && <Check className="w-3.5 h-3.5 text-[#CCFF00] shrink-0" />}
                </button>
              );
            })}
          </div>
          <button
            onClick={() => { setOpen(false); navigate("/equipa"); }}
            data-testid="team-switcher-manage"
            className="w-full flex items-center gap-2 px-3 py-2.5 border-t border-white/10 text-[10px] uppercase tracking-widest text-[#CCFF00] hover:bg-[#CCFF00]/10 transition-all"
          >
            <Plus className="w-3 h-3" /> Gerir equipas
          </button>
        </div>
      )}
    </div>
  );
}
