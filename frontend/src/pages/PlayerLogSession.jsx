import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { http, formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { SESSION_TYPES, SESSION_TYPE_ORDER } from "@/components/Bits";

function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export default function PlayerLogSession() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    date: todayISO(),
    session_type: "training",
    rpe: 5,
    duration_min: 75,
    sleep_quality: 4,
    wellness: 7,
    notes: "",
  });
  const [saving, setSaving] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setSaving(true);
    try {
      await http.post("/player/sessions", form);
      toast.success("Sessão registada");
      navigate("/atleta/historico");
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setSaving(false); }
  }

  return (
    <div className="space-y-6">
      <div>
        <div className="text-xs text-[#CCFF00] tracking-[0.3em] uppercase mb-2">Auto-Reporte</div>
        <h1 className="font-head text-3xl sm:text-4xl font-black leading-none">REGISTAR SESSÃO</h1>
        <p className="text-[#A3A3A3] text-xs sm:text-sm mt-2">
          Indica como correu a sessão. Os dados ficam disponíveis para a equipa técnica.
        </p>
      </div>

      <form onSubmit={onSubmit} className="fld-card space-y-5" data-testid="player-session-form">
        <div className="grid sm:grid-cols-2 gap-5">
          <div>
            <label className="fld-label">Data</label>
            <input className="fld-input" type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} required data-testid="ps-date" />
          </div>
          <div>
            <label className="fld-label">Tipo de Sessão</label>
            <div className="grid grid-cols-2 gap-1.5">
              {SESSION_TYPE_ORDER.map((type) => {
                const meta = SESSION_TYPES[type];
                const isActive = form.session_type === type;
                return (
                  <button
                    type="button"
                    key={type}
                    onClick={() => setForm({ ...form, session_type: type })}
                    data-testid={`ps-type-${type}`}
                    className="text-[11px] uppercase tracking-widest px-2 py-2 border transition-all"
                    style={{
                      borderColor: isActive ? meta.color : "rgba(255,255,255,0.10)",
                      color: isActive ? meta.color : "#A3A3A3",
                      background: isActive ? `${meta.color}15` : "transparent",
                    }}
                  >
                    {meta.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        <div>
          <label className="fld-label">RPE (esforço percebido) — <span className="metric-num text-[#CCFF00]">{form.rpe}</span>/10</label>
          <input type="range" min="1" max="10" value={form.rpe} onChange={(e) => setForm({ ...form, rpe: Number(e.target.value) })} data-testid="ps-rpe" className="w-full" />
          <div className="flex justify-between text-[10px] text-[#525252] uppercase tracking-widest mt-1">
            <span>1 muito leve</span><span>5 moderado</span><span>10 máximo</span>
          </div>
        </div>

        <div>
          <label className="fld-label">Duração: <span className="metric-num text-[#CCFF00]">{form.duration_min}</span> min</label>
          <input type="range" min="15" max="180" step="5" value={form.duration_min} onChange={(e) => setForm({ ...form, duration_min: Number(e.target.value) })} data-testid="ps-duration" className="w-full" />
        </div>

        <div className="grid sm:grid-cols-2 gap-5">
          <div>
            <label className="fld-label">Qualidade do sono — <span className="metric-num text-[#CCFF00]">{form.sleep_quality}</span>/5</label>
            <input type="range" min="1" max="5" value={form.sleep_quality} onChange={(e) => setForm({ ...form, sleep_quality: Number(e.target.value) })} data-testid="ps-sleep" className="w-full" />
            <div className="text-[10px] text-[#525252] mt-1">1 péssimo · 5 excelente</div>
          </div>
          <div>
            <label className="fld-label">Bem-estar geral — <span className="metric-num text-[#CCFF00]">{form.wellness}</span>/10</label>
            <input type="range" min="1" max="10" value={form.wellness} onChange={(e) => setForm({ ...form, wellness: Number(e.target.value) })} data-testid="ps-wellness" className="w-full" />
            <div className="text-[10px] text-[#525252] mt-1">1 mau · 10 ótimo</div>
          </div>
        </div>

        <div>
          <label className="fld-label">Notas (opcional)</label>
          <textarea
            className="fld-input min-h-[70px]"
            value={form.notes}
            onChange={(e) => setForm({ ...form, notes: e.target.value })}
            placeholder="Algo que queiras partilhar com a equipa técnica..."
            data-testid="ps-notes"
          />
        </div>

        <button type="submit" disabled={saving} className="fld-btn-primary w-full" data-testid="ps-submit">
          {saving ? "A REGISTAR..." : "REGISTAR SESSÃO"}
        </button>
      </form>
    </div>
  );
}
