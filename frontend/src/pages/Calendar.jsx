import { useEffect, useMemo, useState } from "react";
import { http, formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { ChevronLeft, ChevronRight, X } from "lucide-react";
import { SESSION_TYPES, SessionTypeBadge } from "@/components/Bits";

const WEEKDAY_NAMES = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"];
const MONTHS_PT = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];

const isoDate = (d) => d.toISOString().slice(0, 10);
const fromISO = (s) => new Date(s + "T00:00:00");
const today = () => { const d = new Date(); d.setHours(0,0,0,0); return d; };

function mondayOf(d) {
  const x = new Date(d);
  x.setHours(0,0,0,0);
  const day = (x.getDay() + 6) % 7;
  x.setDate(x.getDate() - day);
  return x;
}

function loadColor(load) {
  if (!load) return null;
  if (load < 800) return { bg: "rgba(204,255,0,0.08)", border: "rgba(204,255,0,0.3)", color: "#CCFF00" };
  if (load < 2500) return { bg: "rgba(204,255,0,0.18)", border: "rgba(204,255,0,0.5)", color: "#CCFF00" };
  if (load < 4500) return { bg: "rgba(255,234,0,0.18)", border: "rgba(255,234,0,0.5)", color: "#FFEA00" };
  if (load < 7000) return { bg: "rgba(255,149,0,0.22)", border: "rgba(255,149,0,0.6)", color: "#FF9500" };
  return { bg: "rgba(255,59,48,0.25)", border: "rgba(255,59,48,0.7)", color: "#FF3B30" };
}

function dominantType(typeCounts) {
  if (!typeCounts) return null;
  let max = 0;
  let dom = null;
  for (const [k, v] of Object.entries(typeCounts)) {
    if (v > max) { max = v; dom = k; }
  }
  return dom;
}

export default function CalendarPage() {
  const [anchor, setAnchor] = useState(mondayOf(today()));
  const [days, setDays] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedDate, setSelectedDate] = useState(null);

  const startISO = useMemo(() => isoDate(anchor), [anchor]);

  async function load() {
    setLoading(true);
    try {
      const { data } = await http.get(`/calendar?start=${startISO}&days=28`);
      setDays(data.days || []);
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
  const typeTotals = useMemo(() => {
    const out = { training: 0, match: 0, gym: 0, recovery: 0 };
    days.forEach((d) => {
      const types = d.session_types || {};
      Object.entries(types).forEach(([k, v]) => { out[k] = (out[k] || 0) + v; });
    });
    return out;
  }, [days]);

  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="text-xs text-[#CCFF00] tracking-[0.3em] uppercase mb-2">Análise Temporal</div>
          <h1 className="font-head text-5xl md:text-6xl font-black leading-none">CALENDÁRIO</h1>
          <p className="text-[#A3A3A3] text-sm mt-2">Visão geral das cargas totais — 4 semanas</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => shiftWeeks(-4)} className="fld-btn-ghost px-3 py-2" data-testid="cal-prev"><ChevronLeft className="w-4 h-4" /></button>
          <button onClick={goToday} className="fld-btn-ghost text-xs" data-testid="cal-today">HOJE</button>
          <button onClick={() => shiftWeeks(4)} className="fld-btn-ghost px-3 py-2" data-testid="cal-next"><ChevronRight className="w-4 h-4" /></button>
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
          <div className="fld-label">Dias Ativos</div>
          <div className="metric-num text-3xl">{trainingDays}<span className="text-sm text-[#A3A3A3] font-sans">/28</span></div>
        </div>
        <div className="fld-card">
          <div className="fld-label">Distribuição por Tipo</div>
          <div className="flex flex-wrap gap-1 mt-2">
            {Object.entries(typeTotals).map(([k, v]) => {
              if (!v) return null;
              const meta = SESSION_TYPES[k];
              return (
                <span key={k} className="text-[10px] uppercase tracking-widest px-1.5 py-0.5" style={{ color: meta.color, background: `${meta.color}15`, border: `1px solid ${meta.color}40` }}>
                  {meta.label} <span className="metric-num text-white ml-1">{v}</span>
                </span>
              );
            })}
          </div>
        </div>
      </div>

      {/* Grid */}
      <div className="fld-card" data-testid="calendar-grid">
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
                  const dom = dominantType(d.session_types);
                  const domMeta = dom ? SESSION_TYPES[dom] : null;
                  return (
                    <button
                      key={d.date}
                      onClick={() => setSelectedDate(d)}
                      data-testid={`cal-day-${d.date}`}
                      className={`relative min-h-[110px] p-2 text-left border transition-all hover:border-white/40 ${selectedDate?.date === d.date ? "border-[#CCFF00]" : "border-white/8"} ${isPast && d.athletes_count === 0 ? "opacity-50" : ""}`}
                      style={{
                        background: col?.bg || "transparent",
                        borderColor: selectedDate?.date === d.date ? "#CCFF00" : (col?.border || (domMeta ? `${domMeta.color}30` : "rgba(255,255,255,0.05)")),
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
                      {d.session_types && Object.keys(d.session_types).length > 0 && (
                        <div className="absolute bottom-1 left-1 right-1 flex flex-wrap gap-1">
                          {Object.entries(d.session_types).map(([k, v]) => {
                            const m = SESSION_TYPES[k];
                            if (!m) return null;
                            return (
                              <span key={k} className="text-[9px] uppercase tracking-widest px-1 py-0.5" style={{ color: m.color, background: `${m.color}15`, border: `1px solid ${m.color}40` }}>
                                {m.label}{v > 1 ? ` ×${v}` : ""}
                              </span>
                            );
                          })}
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
          <span className="mx-2 text-[#525252]">|</span>
          {Object.entries(SESSION_TYPES).map(([k, m]) => (
            <span key={k} className="flex items-center gap-1" style={{ color: m.color }}>
              <span className="w-3 h-3 border" style={{ borderColor: `${m.color}80`, background: `${m.color}15` }} /> {m.label}
            </span>
          ))}
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

          {selectedDate.athletes.length > 0 ? (
            <div>
              <div className="font-head text-sm tracking-widest text-[#CCFF00] mb-2">REGISTADO · {selectedDate.athletes_count} ATLETAS · {Math.round(selectedDate.total_load)} UA</div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs uppercase tracking-widest text-[#525252] border-b border-white/5">
                      <th className="py-2 pr-4">Atleta</th>
                      <th className="py-2 px-2">Tipo</th>
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
                        <td className="py-2 px-2"><SessionTypeBadge type={a.session_type || "training"} size="sm" /></td>
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
            <div className="text-sm text-[#A3A3A3] py-4">Sem sessões neste dia.</div>
          )}
        </div>
      )}
    </div>
  );
}
