import { useEffect, useState } from "react";
import { http, formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { SESSION_TYPES, SESSION_TYPE_ORDER } from "@/components/Bits";

const todayISO = () => new Date().toISOString().slice(0, 10);

const RPE_LABELS = {
  1: "Muito Leve",
  2: "Leve",
  3: "Confortável",
  4: "Algo Difícil",
  5: "Difícil",
  6: "Bastante Difícil",
  7: "Muito Difícil",
  8: "Extremamente Difícil",
  9: "Quase Máximo",
  10: "Esforço Máximo",
};

const SLEEP_LABELS = {
  1: "Muito Mau",
  2: "Mau",
  3: "Razoável",
  4: "Bom",
  5: "Excelente",
};

const WELLNESS_LABELS = {
  1: "Esgotamento profundo / doença",
  2: "Dor intensa / muito mal",
  3: "Cansaço extremo",
  4: "Letargia / dor desconfortável",
  5: "Energia moderada com tensão",
  6: "Funcional com alguma tensão",
  7: "Equilíbrio bom, corpo relaxado",
  8: "Mente desperta, ótima energia",
  9: "Vitalidade plena",
  10: "Energia radiante, sem dores",
};

function rpeColor(n) {
  if (n <= 3) return "#00E676";
  if (n <= 5) return "#CCFF00";
  if (n <= 7) return "#FFEA00";
  if (n <= 8) return "#FF9500";
  return "#FF3B30";
}
function sleepColor(n) {
  if (n <= 2) return "#FF3B30";
  if (n === 3) return "#FFEA00";
  return "#00E676";
}
function wellnessColor(n) {
  if (n <= 2) return "#FF3B30";
  if (n <= 4) return "#FF9500";
  if (n <= 6) return "#FFEA00";
  if (n <= 8) return "#00E676";
  return "#CCFF00";
}

export default function LogSession() {
  const [athletes, setAthletes] = useState([]);
  const [form, setForm] = useState({
    athlete_id: "",
    date: todayISO(),
    session_type: "training",
    rpe: 5,
    duration_min: 75,
    sleep_quality: 4,
    wellness: 7,
    notes: "",
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await http.get("/athletes");
        setAthletes(data);
        if (data[0]) setForm((f) => ({ ...f, athlete_id: data[0].id }));
      } catch (err) { toast.error(formatApiError(err)); }
    })();
  }, []);

  async function onSubmit(e) {
    e.preventDefault();
    if (!form.athlete_id) { toast.error("Selecione um atleta"); return; }
    setSaving(true);
    try {
      await http.post("/sessions", {
        ...form,
        rpe: Number(form.rpe),
        duration_min: Number(form.duration_min),
        sleep_quality: Number(form.sleep_quality),
        wellness: Number(form.wellness),
        session_type: form.session_type,
      });
      toast.success(`Sessão registada — Carga ${form.rpe * form.duration_min} UA`);
      setForm((f) => ({ ...f, notes: "" }));
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setSaving(false); }
  }

  const computedLoad = (form.rpe || 0) * (form.duration_min || 0);

  return (
    <div className="space-y-8 max-w-3xl">
      <div>
        <div className="text-xs text-[#CCFF00] tracking-[0.3em] uppercase mb-2">Registo Diário</div>
        <h1 className="font-head text-3xl sm:text-4xl md:text-5xl font-black leading-none">SESSÃO</h1>
      </div>

      {athletes.length === 0 ? (
        <div className="fld-card">
          <div className="font-head text-xl">SEM ATLETAS</div>
          <p className="text-[#A3A3A3] text-sm mt-2">Adicione atletas primeiro em <span className="text-[#CCFF00]">Atletas</span>.</p>
        </div>
      ) : (
        <form onSubmit={onSubmit} className="fld-card space-y-5" data-testid="session-form">
          <div className="grid md:grid-cols-2 gap-5">
            <div>
              <label className="fld-label">Atleta</label>
              <select className="fld-input" value={form.athlete_id} onChange={(e) => setForm({ ...form, athlete_id: e.target.value })} data-testid="session-athlete">
                {athletes.map((a) => (
                  <option key={a.id} value={a.id}>{a.name} {a.jersey_number ? `#${a.jersey_number}` : ""}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="fld-label">Data</label>
              <input className="fld-input" type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} required data-testid="session-date" />
            </div>
          </div>

          <div>
            <label className="fld-label">Tipo de Sessão</label>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {SESSION_TYPE_ORDER.map((k) => {
                const meta = SESSION_TYPES[k];
                const active = form.session_type === k;
                return (
                  <button
                    key={k}
                    type="button"
                    onClick={() => setForm({ ...form, session_type: k })}
                    data-testid={`session-type-${k}`}
                    className="py-3 font-head tracking-widest text-sm uppercase border transition-all"
                    style={{
                      background: active ? meta.color : "transparent",
                      color: active ? "#000" : meta.color,
                      borderColor: active ? meta.color : `${meta.color}50`,
                    }}
                  >
                    {meta.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="grid md:grid-cols-2 gap-5">
            <div>
              <label className="fld-label">PSE — Esforço Percebido (1-10)</label>
              <div className="grid grid-cols-10 gap-1">
                {[1,2,3,4,5,6,7,8,9,10].map((n) => {
                  const color = rpeColor(n);
                  const active = Number(form.rpe) === n;
                  return (
                    <button
                      key={n}
                      type="button"
                      onClick={() => setForm({ ...form, rpe: n })}
                      data-testid={`rpe-${n}`}
                      className="py-2.5 font-head text-sm border transition-all"
                      style={{
                        background: active ? color : "transparent",
                        color: active ? "#000" : "#fff",
                        borderColor: active ? color : "rgba(255,255,255,0.15)",
                      }}
                    >
                      {n}
                    </button>
                  );
                })}
              </div>
              <div className="text-xs mt-2 min-h-[1.2rem]" style={{ color: rpeColor(Number(form.rpe)) }} data-testid="rpe-label">
                {RPE_LABELS[Number(form.rpe)] || "—"}
              </div>
            </div>
            <div>
              <label className="fld-label">Duração (min)</label>
              <input className="fld-input" type="number" min="1" max="300" value={form.duration_min} onChange={(e) => setForm({ ...form, duration_min: e.target.value })} required data-testid="session-duration" />
            </div>
          </div>

          <div>
            <label className="fld-label">Qualidade do Sono (1-5)</label>
            <div className="grid grid-cols-5 gap-2">
              {[1, 2, 3, 4, 5].map((n) => {
                const color = sleepColor(n);
                const active = form.sleep_quality === n;
                return (
                  <button
                    key={n}
                    type="button"
                    onClick={() => setForm({ ...form, sleep_quality: n })}
                    data-testid={`sleep-${n}`}
                    className="py-3 font-head tracking-widest text-sm border transition-colors"
                    style={{
                      background: active ? color : "transparent",
                      color: active ? "#000" : "#fff",
                      borderColor: active ? color : "rgba(255,255,255,0.15)",
                    }}
                  >
                    {n}
                  </button>
                );
              })}
            </div>
            <div className="text-xs mt-2 min-h-[1.2rem]" style={{ color: sleepColor(form.sleep_quality) }} data-testid="sleep-label">
              {SLEEP_LABELS[form.sleep_quality] || "—"}
            </div>
          </div>

          <div>
            <label className="fld-label">Bem-Estar Corporal (1-10)</label>
            <div className="grid grid-cols-10 gap-1.5">
              {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => {
                const color = wellnessColor(n);
                const active = form.wellness === n;
                return (
                  <button
                    key={n}
                    type="button"
                    onClick={() => setForm({ ...form, wellness: n })}
                    data-testid={`wellness-${n}`}
                    className="py-3 font-head tracking-widest text-sm border transition-all"
                    style={{
                      background: active ? color : "transparent",
                      color: active ? "#000" : "#fff",
                      borderColor: active ? color : "rgba(255,255,255,0.15)",
                    }}
                  >
                    {n}
                  </button>
                );
              })}
            </div>
            <div className="text-xs mt-2 min-h-[1.2rem]" style={{ color: wellnessColor(form.wellness) }} data-testid="wellness-label">
              {WELLNESS_LABELS[form.wellness] || "—"}
            </div>
          </div>

          <div>
            <label className="fld-label">Notas (opcional)</label>
            <textarea className="fld-input" rows="2" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} data-testid="session-notes" />
          </div>

          <div className="flex items-center justify-between pt-2 border-t border-white/5">
            <div>
              <div className="fld-label mb-1">Carga Calculada</div>
              <div className="metric-num text-3xl text-[#CCFF00]" data-testid="computed-load">{computedLoad} <span className="text-sm text-[#A3A3A3] font-sans">UA</span></div>
            </div>
            <button type="submit" disabled={saving} className="fld-btn-primary" data-testid="session-submit">
              {saving ? "A REGISTAR..." : "REGISTAR SESSÃO"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
