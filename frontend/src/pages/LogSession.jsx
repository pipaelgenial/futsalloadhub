import { useEffect, useState } from "react";
import { http, formatApiError } from "@/lib/api";
import { toast } from "sonner";

const todayISO = () => new Date().toISOString().slice(0, 10);

export default function LogSession() {
  const [athletes, setAthletes] = useState([]);
  const [form, setForm] = useState({
    athlete_id: "",
    date: todayISO(),
    rpe: 5,
    duration_min: 75,
    sleep_quality: 4,
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
        <h1 className="font-head text-5xl md:text-6xl font-black leading-none">SESSÃO</h1>
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

          <div className="grid md:grid-cols-2 gap-5">
            <div>
              <label className="fld-label">RPE (Esforço Percebido 1-10)</label>
              <input className="fld-input" type="number" min="1" max="10" value={form.rpe} onChange={(e) => setForm({ ...form, rpe: e.target.value })} required data-testid="session-rpe" />
              <div className="text-xs text-[#525252] mt-1">1 = Muito leve · 10 = Esforço máximo</div>
            </div>
            <div>
              <label className="fld-label">Duração (min)</label>
              <input className="fld-input" type="number" min="1" max="300" value={form.duration_min} onChange={(e) => setForm({ ...form, duration_min: e.target.value })} required data-testid="session-duration" />
            </div>
          </div>

          <div>
            <label className="fld-label">Qualidade do Sono (1-5)</label>
            <div className="flex gap-2">
              {[1, 2, 3, 4, 5].map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setForm({ ...form, sleep_quality: n })}
                  data-testid={`sleep-${n}`}
                  className={`flex-1 py-3 font-head tracking-widest text-sm border transition-colors ${
                    form.sleep_quality === n
                      ? "bg-[#CCFF00] text-black border-[#CCFF00]"
                      : "bg-transparent text-white border-white/15 hover:border-white/30"
                  }`}
                >
                  {n}
                </button>
              ))}
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
