import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { http } from "@/lib/api";
import { ClipboardEdit, History, Calendar as CalIcon } from "lucide-react";
import { SESSION_TYPES } from "@/components/Bits";

export default function PlayerHome() {
  const [me, setMe] = useState(null);
  const [sessions, setSessions] = useState([]);

  useEffect(() => {
    Promise.all([
      http.get("/player/me").then(({ data }) => setMe(data)),
      http.get("/player/sessions").then(({ data }) => setSessions(data)),
    ]).catch(() => {});
  }, []);

  const last = sessions[0];
  const last7 = sessions.filter((s) => {
    const d = new Date(s.date);
    const today = new Date();
    return (today - d) <= 7 * 86400000;
  });

  return (
    <div className="space-y-6" data-testid="player-home">
      <div>
        <div className="text-xs text-[#CCFF00] tracking-[0.3em] uppercase mb-2">Vista de Atleta</div>
        <h1 className="font-head text-3xl sm:text-4xl md:text-5xl font-black leading-none">OLÁ, {(me?.athlete?.name || "ATLETA").toUpperCase().split(" ")[0]}</h1>
        <p className="text-[#A3A3A3] text-sm mt-2">
          {me?.team?.name ? <>Equipa: <span className="text-white">{me.team.name}</span> · {me.team.escalao}</> : "A carregar..."}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="fld-card">
          <div className="fld-label">Sessões nos últimos 7 dias</div>
          <div className="metric-num text-3xl text-[#CCFF00]">{last7.length}</div>
        </div>
        <div className="fld-card">
          <div className="fld-label">Total de sessões</div>
          <div className="metric-num text-3xl">{sessions.length}</div>
        </div>
      </div>

      {last && (
        <div className="fld-card" data-testid="player-last-session">
          <div className="fld-label flex items-center gap-1.5"><CalIcon className="w-3 h-3" /> Última sessão registada</div>
          <div className="mt-3 flex items-center gap-4 flex-wrap">
            <div>
              <div className="text-[10px] uppercase tracking-widest text-[#525252]">Data</div>
              <div className="font-head text-lg">{last.date}</div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-widest text-[#525252]">Tipo</div>
              <div className="font-head text-lg" style={{ color: SESSION_TYPES[last.session_type]?.color || "#fff" }}>
                {SESSION_TYPES[last.session_type]?.label || last.session_type}
              </div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-widest text-[#525252]">RPE</div>
              <div className="metric-num text-2xl">{last.rpe}</div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-widest text-[#525252]">Duração</div>
              <div className="metric-num text-2xl">{last.duration_min}<span className="text-xs text-[#A3A3A3]">min</span></div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-widest text-[#525252]">Sono</div>
              <div className="metric-num text-2xl">{last.sleep_quality ?? "—"}<span className="text-xs text-[#A3A3A3]">/5</span></div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-widest text-[#525252]">Bem-estar</div>
              <div className="metric-num text-2xl">{last.wellness ?? "—"}<span className="text-xs text-[#A3A3A3]">/10</span></div>
            </div>
          </div>
        </div>
      )}

      <div className="grid sm:grid-cols-2 gap-3">
        <Link to="/atleta/registar" data-testid="cta-register" className="fld-card border-l-4 border-l-[#CCFF00] hover:bg-white/[0.02] transition-all group">
          <ClipboardEdit className="w-6 h-6 text-[#CCFF00] mb-3" />
          <div className="font-head text-lg font-bold mb-1 group-hover:text-[#CCFF00] transition-colors">REGISTAR SESSÃO</div>
          <div className="text-[11px] text-[#A3A3A3]">Adicionar treino, jogo, ginásio ou recuperação de hoje.</div>
        </Link>
        <Link to="/atleta/historico" data-testid="cta-history" className="fld-card border-l-4 border-l-white/20 hover:bg-white/[0.02] transition-all group">
          <History className="w-6 h-6 text-[#A3A3A3] mb-3" />
          <div className="font-head text-lg font-bold mb-1 group-hover:text-white transition-colors">HISTÓRICO</div>
          <div className="text-[11px] text-[#A3A3A3]">Ver todas as sessões registadas.</div>
        </Link>
      </div>
    </div>
  );
}
