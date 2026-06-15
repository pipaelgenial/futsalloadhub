import { useEffect, useMemo, useState } from "react";
import { http, formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { ChevronLeft, ChevronRight, Plus, X, CalendarDays, Trash2 } from "lucide-react";

const WEEKDAY_NAMES = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"];
const MONTHS_PT = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];

const isoDate = (d) => d.toISOString().slice(0, 10);
const fromISO = (s) => new Date(s + "T00:00:00");
const today = () => { const d = new Date(); d.setHours(0,0,0,0); return d; };

// Find Monday of the week that contains given date
function mondayOf(d) {
  const x = new Date(d);
  x.setHours(0,0,0,0);
  const day = (x.getDay() + 6) % 7; // 0=Mon
  x.setDate(x.getDate() - day);
  return x;
}

// Load heatmap colour
function loadColor(load) {
  if (!load) return null;
  if (load < 800) return { bg: "rgba(204,255,0,0.08)", border: "rgba(204,255,0,0.3)", color: "#CCFF00" };
  if (load < 2500) return { bg: "rgba(204,255,0,0.18)", border: "rgba(204,255,0,0.5)", color: "#CCFF00" };
  if (load < 4500) return { bg: "rgba(255,234,0,0.18)", border: "rgba(255,234,0,0.5)", color: "#FFEA00" };
  if (load < 7000) return { bg: "rgba(255,149,0,0.22)", border: "rgba(255,149,0,0.6)", color: "#FF9500" };
  return { bg: "rgba(255,59,48,0.25)", border: "rgba(255,59,48,0.7)", color: "#FF3B30" };
}

export default function CalendarPage() {
  const [anchor, setAnchor] = useState(mondayOf(today())); // first Monday in view
  const [days, setDays] = useState([]);
  const [athletes, setAthletes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedDate, setSelectedDate] = useState(null);
  const [planOpen, setPlanOpen] = useState(false);
  const [planForm, setPlanForm] = useState({ date: isoDate(today()), planned_rpe: 6, planned_duration: 75, notes: "", athlete_ids: [] });
  const [planSaving, setPlanSaving] = useState(false);

  const startISO = useMemo(() => isoDate(anchor), [anchor]);

  async function load() {
    setLoading(true);
    try {
      const { data } = await http.get(`/calendar?start=${startISO}&days=28`);
      setDays(data.days || []);
      setAthletes(data.athletes || []);
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setLoading(false); }
  }
  useEffect(() => { load(); }, [startISO]);

  function shiftWeeks(n) {
    const d = new Date(anchor);
    d.setDate(d.getDate() + n * 7);
    setAnchor(d);
  }

  function goToday() { setAnchor(mondayOf(today())); }

  const weeks = useMemo(() => {
    const out = [];
    for (let i = 0; i < days.length; i += 7) out.push(days.slice(i, i + 7));
    return out;
  }, [days]);

  const monthLabel = useMemo(() => {
    const last = new Date(anchor);
    last.setDate(last.getDate() + 27);
    if (anchor.getMonth() === last.getMonth())
      return `${MONTHS_PT[anchor.getMonth()]} ${anchor.getFullYear()}`;
    return `${MONTHS_PT[anchor.getMonth()].slice(0,3)} → ${MONTHS_PT[last.getMonth()].slice(0,3)} ${last.getFullYear()}`;
  }, [anchor]);

  const totalLoad = useMemo(() => days.reduce((s, d) => s + d.total_load, 0), [days]);
  const trainingDays = useMemo(() => days.filter((d) => d.athletes_count > 0).length, [days]);

  async function submitPlan(e) {
    e.preventDefault();
    setPlanSaving(true);
    try {
      await http.post("/planned-sessions", {
        date: planForm.date,
        planned_rpe: Number(planForm.planned_rpe),
        planned_duration: Number(planForm.planned_duration),
        notes: planForm.notes || null,
        athlete_ids: planForm.athlete_ids,
      });
      toast.success("Treino planeado");
      setPlanOpen(false);
      setPlanForm({ date: isoDate(today()), planned_rpe: 6, planned_duration: 75, notes: "", athlete_ids: [] });
      load();
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setPlanSaving(false); }
  }

  async function deletePlan(id) {
    if (!window.confirm("Eliminar sessão planeada?")) return;
    try {
      await http.delete(`/planned-sessions/${id}`);
      toast.success("Sessão planeada eliminada");
      load();
      if (selectedDate) {
        const updated = days.find((d) => d.date === selectedDate.date);
        if (updated) setSelectedDate({ ...updated, planned: updated.planned.filter((p) => p.id !== id) });
      }
    } catch (err) { toast.error(formatApiError(err)); }
  }

  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="text-xs text-[#CCFF00] tracking-[0.3em] uppercase mb-2">Análise Temporal</div>
          <h1 className="font-head text-5xl md:text-6xl font-black leading-none">CALENDÁRIO</h1>
          <p className="text-[#A3A3A3] text-sm mt-2">Sessões planeadas e cargas registadas — vista de 4 semanas</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => shiftWeeks(-4)} className="fld-btn-ghost px-3 py-2" data-testid="cal-prev"><ChevronLeft className="w-4 h-4" /></button>
          <button onClick={goToday} className="fld-btn-ghost text-xs" data-testid="cal-today">HOJE</button>
          <button onClick={() => shiftWeeks(4)} className="fld-btn-ghost px-3 py-2" data-testid="cal-next"><ChevronRight className="w-4 h-4" /></button>
          <button onClick={() => { setPlanForm({ ...planForm, date: selectedDate?.date || isoDate(today()) }); setPlanOpen(true); }} className="fld-btn-primary flex items-center gap-2" data-testid="cal-plan-btn">
            <Plus className="w-4 h-4" /> PLANEAR
          </button>
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="fld-card">
          <div className="fld-label">Vista</div>
          <div className="font-head text-2xl font-bold">{monthLabel}</div>
        </div>
        <div className="fld-card">
          <div className="fld-label">Carga Total (4 sem)</div>
          <div className="metric-num text-3xl text-[#CCFF00]">{Math.round(totalLoad)} <span className="text-sm text-[#A3A3A3] font-sans">UA</span></div>
        </div>
        <div className="fld-card">
          <div className="fld-label">Dias com Treino</div>
          <div className="metric-num text-3xl">{trainingDays}<span className="text-sm text-[#A3A3A3] font-sans">/28</span></div>
        </div>
        <div className="fld-card">
          <div className="fld-label">Planeados</div>
          <div className="metric-num text-3xl text-[#FFEA00]">{days.reduce((s, d) => s + d.planned.length, 0)}</div>
        </div>
      </div>

      {/* Grid */}
      <div className="fld-card" data-testid="calendar-grid">
        {/* Header weekdays */}
        <div className="grid grid-cols-7 gap-2 mb-3">
          {WEEKDAY_NAMES.map((d) => (
            <div key={d} className="font-head text-xs tracking-widest text-[#525252] uppercase text-center py-2">{d}</div>
          ))}
        </div>

        {loading ? (
          <div className="text-center py-20 text-[#A3A3A3]">A carregar...</div>
        ) : (
          <div className="space-y-2">
            {weeks.map((week, wi) => (
              <div key={wi} className="grid grid-cols-7 gap-2">
                {week.map((d) => {
                  const col = loadColor(d.total_load);
                  const isToday = d.date === isoDate(today());
                  const isPast = fromISO(d.date) < today();
                  return (
                    <button
                      key={d.date}
                      onClick={() => setSelectedDate(d)}
                      data-testid={`cal-day-${d.date}`}
                      className={`relative min-h-[110px] p-2 text-left border transition-all hover:border-white/40 ${selectedDate?.date === d.date ? "border-[#CCFF00]" : "border-white/8"} ${isPast && d.athletes_count === 0 && d.planned.length === 0 ? "opacity-50" : ""}`}
                      style={{
                        background: col?.bg || "transparent",
                        borderColor: selectedDate?.date === d.date ? "#CCFF00" : col?.border || "rgba(255,255,255,0.05)",
                      }}
                    >
                      <div className="flex items-start justify-between mb-1">
                        <div className={`metric-num text-base ${isToday ? "text-[#CCFF00]" : ""}`}>
                          {Number(d.date.slice(8, 10))}
                          {isToday && <span className="text-[10px] text-[#CCFF00] ml-1 uppercase tracking-widest">hoje</span>}
                        </div>
                        {d.athletes_count > 0 && (
                          <div className="text-[10px] text-[#A3A3A3]">{d.athletes_count}<span className="text-[#525252]">/atl</span></div>
                        )}
                      </div>
                      {d.total_load > 0 && (
                        <div className="metric-num text-xl" style={{ color: col?.color || "#fff" }}>{Math.round(d.total_load)}</div>
                      )}
                      {d.planned.length > 0 && (
                        <div className="absolute bottom-1 left-1 right-1 flex flex-wrap gap-1">
                          {d.planned.slice(0, 3).map((p) => (
                            <span key={p.id} className="text-[9px] uppercase tracking-widest border border-dashed border-[#FFEA00]/60 text-[#FFEA00] px-1 py-0.5">
                              {p.planned_rpe}×{p.planned_duration}'
                            </span>
                          ))}
                        </div>
                      )}
                    </button>
                  );
                })}
              </div>
            ))}
          </div>
        )}

        {/* Legend */}
        <div className="mt-5 pt-4 border-t border-white/5 flex flex-wrap items-center gap-3 text-[10px] text-[#A3A3A3] uppercase tracking-widest">
          <span>Intensidade carga total:</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 border border-[#CCFF00]/30 bg-[#CCFF00]/10" /> Baixa</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 border border-[#FFEA00]/50 bg-[#FFEA00]/20" /> Média</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 border border-[#FF9500]/60 bg-[#FF9500]/22" /> Alta</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 border border-[#FF3B30]/70 bg-[#FF3B30]/25" /> Muito alta</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 border border-dashed border-[#FFEA00]/60" /> Planeado</span>
        </div>
      </div>

      {/* Day details */}
      {selectedDate && (
        <div className="fld-card border-l-4 border-l-[#CCFF00]" data-testid="day-detail">
          <div className="flex items-start justify-between mb-4">
            <div>
              <div className="text-xs text-[#CCFF00] tracking-[0.3em] uppercase">{WEEKDAY_NAMES[selectedDate.weekday]}</div>
              <div className="font-head text-3xl font-bold">{selectedDate.date}</div>
            </div>
            <button onClick={() => setSelectedDate(null)} className="text-[#525252] hover:text-white"><X className="w-5 h-5" /></button>
          </div>

          {selectedDate.planned.length > 0 && (
            <div className="mb-5">
              <div className="font-head text-sm tracking-widest text-[#FFEA00] mb-2">PLANEADO</div>
              <div className="space-y-2">
                {selectedDate.planned.map((p) => (
                  <div key={p.id} className="flex items-center justify-between p-3 border border-dashed border-[#FFEA00]/30">
                    <div>
                      <div className="text-sm">
                        RPE <span className="metric-num text-white">{p.planned_rpe}</span>
                        {" · "}Duração <span className="metric-num text-white">{p.planned_duration}min</span>
                        {" · "}Carga prevista <span className="metric-num text-[#FFEA00]">{p.planned_load} UA</span>
                      </div>
                      {p.notes && <div className="text-xs text-[#A3A3A3] mt-1">{p.notes}</div>}
                      <div className="text-[10px] text-[#525252] mt-1">
                        {(!p.athlete_ids || p.athlete_ids.length === 0) ? "Equipa completa" : `${p.athlete_ids.length} atletas`}
                      </div>
                    </div>
                    <button onClick={() => deletePlan(p.id)} className="text-[#525252] hover:text-[#FF3B30]" data-testid={`delete-plan-${p.id}`}>
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {selectedDate.athletes.length > 0 ? (
            <div>
              <div className="font-head text-sm tracking-widest text-[#CCFF00] mb-2">REGISTADO · {selectedDate.athletes_count} ATLETAS · {Math.round(selectedDate.total_load)} UA</div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs uppercase tracking-widest text-[#525252] border-b border-white/5">
                      <th className="py-2 pr-4">Atleta</th>
                      <th className="py-2 px-2">RPE</th>
                      <th className="py-2 px-2">Duração</th>
                      <th className="py-2 px-2 text-[#CCFF00]">Carga</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedDate.athletes.sort((a, b) => b.load - a.load).map((a) => (
                      <tr key={a.session_id} className="border-b border-white/5">
                        <td className="py-2 pr-4">
                          {a.jersey_number && <span className="metric-num text-[#CCFF00] mr-2">#{a.jersey_number}</span>}
                          {a.name}
                        </td>
                        <td className="py-2 px-2 metric-num">{a.rpe}</td>
                        <td className="py-2 px-2">{a.duration_min}min</td>
                        <td className="py-2 px-2 metric-num text-[#CCFF00]">{a.load}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            selectedDate.planned.length === 0 && (
              <div className="text-sm text-[#A3A3A3] py-4">Sem sessões neste dia.</div>
            )
          )}
        </div>
      )}

      {/* Plan modal */}
      {planOpen && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-end md:items-center justify-center p-4">
          <form onSubmit={submitPlan} className="bg-[#0A0A0A] border border-white/10 max-w-lg w-full p-6 space-y-4 max-h-[90vh] overflow-y-auto" data-testid="plan-form">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CalendarDays className="w-5 h-5 text-[#CCFF00]" />
                <div className="font-head text-2xl font-bold">PLANEAR TREINO</div>
              </div>
              <button type="button" onClick={() => setPlanOpen(false)}><X className="w-5 h-5 text-[#525252]" /></button>
            </div>

            <div>
              <label className="fld-label">Data</label>
              <input className="fld-input" type="date" value={planForm.date} onChange={(e) => setPlanForm({ ...planForm, date: e.target.value })} required data-testid="plan-date" />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="fld-label">RPE Previsto (1-10)</label>
                <input className="fld-input" type="number" min="1" max="10" value={planForm.planned_rpe} onChange={(e) => setPlanForm({ ...planForm, planned_rpe: e.target.value })} required data-testid="plan-rpe" />
              </div>
              <div>
                <label className="fld-label">Duração (min)</label>
                <input className="fld-input" type="number" min="1" max="300" value={planForm.planned_duration} onChange={(e) => setPlanForm({ ...planForm, planned_duration: e.target.value })} required data-testid="plan-duration" />
              </div>
            </div>

            <div>
              <label className="fld-label">Atletas (vazio = equipa toda)</label>
              <div className="max-h-32 overflow-y-auto border border-white/10 p-2 space-y-1">
                {athletes.length === 0 && <div className="text-xs text-[#A3A3A3]">Sem atletas</div>}
                {athletes.map((a) => {
                  const checked = planForm.athlete_ids.includes(a.id);
                  return (
                    <label key={a.id} className="flex items-center gap-2 text-sm cursor-pointer hover:bg-white/5 p-1">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={(e) => {
                          if (e.target.checked) setPlanForm({ ...planForm, athlete_ids: [...planForm.athlete_ids, a.id] });
                          else setPlanForm({ ...planForm, athlete_ids: planForm.athlete_ids.filter((x) => x !== a.id) });
                        }}
                      />
                      {a.name} {a.jersey_number ? `#${a.jersey_number}` : ""}
                    </label>
                  );
                })}
              </div>
            </div>

            <div>
              <label className="fld-label">Notas (opcional)</label>
              <textarea className="fld-input" rows="2" value={planForm.notes} onChange={(e) => setPlanForm({ ...planForm, notes: e.target.value })} data-testid="plan-notes" />
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-white/5">
              <div className="text-xs text-[#A3A3A3]">Carga prevista: <span className="metric-num text-[#CCFF00] text-base ml-1">{(planForm.planned_rpe || 0) * (planForm.planned_duration || 0)} UA</span></div>
              <button type="submit" disabled={planSaving} className="fld-btn-primary" data-testid="plan-submit">
                {planSaving ? "A GUARDAR..." : "GUARDAR"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
