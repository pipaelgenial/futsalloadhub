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

function daysInMonth(year, monthIdx) { return new Date(year, monthIdx + 1, 0).getDate(); }
function firstDayOfMonth(year, monthIdx) { return new Date(year, monthIdx, 1); }
function startOfWeekMonday(d) {
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

function MonthGrid({ year, monthIdx, daysData, selectedDate, onSelect }) {
  const first = firstDayOfMonth(year, monthIdx);
  // Grid start = Monday of week containing first day
  const gridStart = startOfWeekMonday(first);
  const totalDays = daysInMonth(year, monthIdx);
  // Build 6x7 = 42 cells max, but trim to needed rows
  const last = new Date(year, monthIdx, totalDays);
  const gridEnd = startOfWeekMonday(last);
  gridEnd.setDate(gridEnd.getDate() + 6);

  const cells = [];
  let cur = new Date(gridStart);
  while (cur <= gridEnd) {
    const iso = isoDate(cur);
    const inMonth = cur.getMonth() === monthIdx;
    const dayData = daysData[iso];
    cells.push({ date: new Date(cur), iso, inMonth, data: dayData });
    cur.setDate(cur.getDate() + 1);
  }
  const rows = [];
  for (let i = 0; i < cells.length; i += 7) rows.push(cells.slice(i, i + 7));

  return (
    <div className="fld-card" data-testid={`month-grid-${year}-${monthIdx + 1}`}>
      <div className="font-head text-xl sm:text-2xl font-bold mb-3 uppercase">
        {MONTHS_PT[monthIdx]} <span className="text-[#A3A3A3]">{year}</span>
      </div>
      <div className="grid grid-cols-7 gap-1.5 mb-2">
        {WEEKDAY_NAMES.map((d) => (
          <div key={d} className="font-head text-[10px] sm:text-xs tracking-widest text-[#525252] uppercase text-center py-1.5">{d}</div>
        ))}
      </div>
      <div className="space-y-1.5">
        {rows.map((row, ri) => (
          <div key={ri} className="grid grid-cols-7 gap-1.5">
            {row.map((c) => {
              const d = c.data;
              const col = d ? loadColor(d.total_load) : null;
              const isToday = c.iso === isoDate(today());
              const dimmed = !c.inMonth;
              return (
                <button
                  key={c.iso}
                  onClick={() => c.inMonth && onSelect(d || { date: c.iso, weekday: (c.date.getDay() + 6) % 7, athletes: [], athletes_count: 0, total_load: 0, session_types: {}, planned: [] })}
                  data-testid={`cal-day-${c.iso}`}
                  disabled={dimmed}
                  className={`relative min-h-[80px] sm:min-h-[95px] p-1.5 text-left border transition-all ${selectedDate?.date === c.iso ? "border-[#CCFF00]" : "border-white/8"} ${dimmed ? "opacity-20 cursor-default" : "hover:border-white/40"}`}
                  style={{
                    background: col?.bg || "transparent",
                    borderColor: selectedDate?.date === c.iso ? "#CCFF00" : (col?.border || "rgba(255,255,255,0.05)"),
                  }}
                >
                  <div className="flex items-start justify-between mb-1">
                    <div className={`metric-num text-sm sm:text-base ${isToday ? "text-[#CCFF00]" : ""}`}>
                      {c.date.getDate()}
                    </div>
                    {d?.athletes_count > 0 && (
                      <div className="text-[9px] sm:text-[10px] text-[#A3A3A3]">{d.athletes_count}</div>
                    )}
                  </div>
                  {d?.total_load > 0 && (
                    <div className="metric-num text-base sm:text-lg" style={{ color: col?.color || "#fff" }}>{Math.round(d.total_load)}</div>
                  )}
                  {d?.session_types && Object.keys(d.session_types).length > 0 && (
                    <div className="absolute bottom-1 left-1 right-1 flex flex-wrap gap-0.5">
                      {Object.entries(d.session_types).slice(0, 3).map(([k, v]) => {
                        const m = SESSION_TYPES[k];
                        if (!m) return null;
                        return (
                          <span key={k} className="text-[8px] uppercase tracking-widest px-1 py-0.5" style={{ color: m.color, background: `${m.color}15`, border: `1px solid ${m.color}40` }}>
                            {m.short}{v > 1 ? v : ""}
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
    </div>
  );
}

export default function CalendarPage() {
  const [year, setYear] = useState(today().getFullYear());
  const [monthIdx, setMonthIdx] = useState(today().getMonth());
  const [spanMonths, setSpanMonths] = useState(1);
  const [daysData, setDaysData] = useState({}); // iso -> day
  const [loading, setLoading] = useState(true);
  const [selectedDate, setSelectedDate] = useState(null);

  // Build start/end across spanMonths
  const range = useMemo(() => {
    const start = new Date(year, monthIdx, 1);
    const endMonth = monthIdx + spanMonths - 1;
    const endY = year + Math.floor(endMonth / 12);
    const endM = ((endMonth % 12) + 12) % 12;
    const lastDay = daysInMonth(endY, endM);
    const end = new Date(endY, endM, lastDay);
    const days = Math.floor((end - start) / 86400000) + 1;
    return { start, days };
  }, [year, monthIdx, spanMonths]);

  async function load() {
    setLoading(true);
    try {
      const startISO = isoDate(range.start);
      const { data } = await http.get(`/calendar?start=${startISO}&days=${range.days}`);
      const map = {};
      (data.days || []).forEach((d) => { map[d.date] = d; });
      setDaysData(map);
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setLoading(false); }
  }
  useEffect(() => { load(); }, [range.start.getTime(), range.days]);

  function shiftMonth(n) {
    let m = monthIdx + n;
    let y = year;
    while (m < 0) { m += 12; y -= 1; }
    while (m > 11) { m -= 12; y += 1; }
    setYear(y);
    setMonthIdx(m);
  }
  function goToday() {
    setYear(today().getFullYear());
    setMonthIdx(today().getMonth());
  }

  // Month list for dropdown (current year + previous year + next 3 months)
  const monthOptions = useMemo(() => {
    const out = [];
    const today_ = today();
    for (let y = today_.getFullYear() - 1; y <= today_.getFullYear() + 1; y++) {
      for (let m = 0; m < 12; m++) {
        out.push({ y, m, label: `${MONTHS_PT[m]} ${y}` });
      }
    }
    return out;
  }, []);

  const visibleMonths = useMemo(() => {
    const arr = [];
    for (let i = 0; i < spanMonths; i++) {
      let m = monthIdx + i;
      let y = year + Math.floor(m / 12);
      m = ((m % 12) + 12) % 12;
      arr.push({ y, m });
    }
    return arr;
  }, [year, monthIdx, spanMonths]);

  const totalLoad = useMemo(() => Object.values(daysData).reduce((s, d) => s + (d.total_load || 0), 0), [daysData]);
  const trainingDays = useMemo(() => Object.values(daysData).filter((d) => d.athletes_count > 0).length, [daysData]);
  const typeTotals = useMemo(() => {
    const out = { training: 0, match: 0, gym: 0, recovery: 0 };
    Object.values(daysData).forEach((d) => {
      const types = d.session_types || {};
      Object.entries(types).forEach(([k, v]) => { out[k] = (out[k] || 0) + v; });
    });
    return out;
  }, [daysData]);

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="text-xs text-[#CCFF00] tracking-[0.3em] uppercase mb-2">Análise Temporal</div>
          <h1 className="font-head text-3xl sm:text-4xl md:text-5xl font-black leading-none">CALENDÁRIO</h1>
          <p className="text-[#A3A3A3] text-xs sm:text-sm mt-2">Visão mensal das cargas totais</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button onClick={() => shiftMonth(-1)} className="fld-btn-ghost px-3 py-2" data-testid="cal-prev"><ChevronLeft className="w-4 h-4" /></button>
          <select
            value={`${year}-${monthIdx}`}
            onChange={(e) => {
              const [y, m] = e.target.value.split("-").map(Number);
              setYear(y); setMonthIdx(m);
            }}
            className="fld-input py-2 text-sm min-w-[150px]"
            data-testid="month-selector"
          >
            {monthOptions.map((o) => (
              <option key={`${o.y}-${o.m}`} value={`${o.y}-${o.m}`}>{o.label}</option>
            ))}
          </select>
          <select
            value={spanMonths}
            onChange={(e) => setSpanMonths(Number(e.target.value))}
            className="fld-input py-2 text-sm"
            data-testid="span-selector"
          >
            <option value={1}>1 mês</option>
            <option value={2}>2 meses</option>
            <option value={3}>3 meses</option>
            <option value={6}>6 meses</option>
          </select>
          <button onClick={() => shiftMonth(1)} className="fld-btn-ghost px-3 py-2" data-testid="cal-next"><ChevronRight className="w-4 h-4" /></button>
          <button onClick={goToday} className="fld-btn-ghost text-xs" data-testid="cal-today">HOJE</button>
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <div className="fld-card">
          <div className="fld-label">Carga Total no Período</div>
          <div className="metric-num text-2xl sm:text-3xl text-[#CCFF00]">{Math.round(totalLoad)} <span className="text-xs text-[#A3A3A3] font-sans">UA</span></div>
        </div>
        <div className="fld-card">
          <div className="fld-label">Dias Ativos</div>
          <div className="metric-num text-2xl sm:text-3xl">{trainingDays}<span className="text-xs text-[#A3A3A3] font-sans">/{range.days}</span></div>
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

      {loading ? (
        <div className="text-center py-20 text-[#A3A3A3]">A carregar...</div>
      ) : (
        <div className="space-y-6">
          {visibleMonths.map(({ y, m }) => (
            <MonthGrid
              key={`${y}-${m}`}
              year={y}
              monthIdx={m}
              daysData={daysData}
              selectedDate={selectedDate}
              onSelect={setSelectedDate}
            />
          ))}
        </div>
      )}

      {/* Legend */}
      <div className="fld-card flex flex-wrap items-center gap-3 text-[10px] text-[#A3A3A3] uppercase tracking-widest">
        <span>Intensidade carga:</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 border border-[#CCFF00]/30 bg-[#CCFF00]/10" /> Baixa</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 border border-[#FFEA00]/50 bg-[#FFEA00]/20" /> Média</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 border border-[#FF9500]/60 bg-[#FF9500]/22" /> Alta</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 border border-[#FF3B30]/70 bg-[#FF3B30]/25" /> Muito alta</span>
        <span className="mx-2 text-[#525252]">|</span>
        {Object.entries(SESSION_TYPES).map(([k, m]) => (
          <span key={k} className="flex items-center gap-1" style={{ color: m.color }}>
            <span className="w-3 h-3 border" style={{ borderColor: `${m.color}80`, background: `${m.color}15` }} />
            <span className="font-bold">{m.short}</span> {m.label}
          </span>
        ))}
      </div>

      {selectedDate && selectedDate.athletes_count > 0 && (
        <div className="fld-card border-l-4 border-l-[#CCFF00]" data-testid="day-detail">
          <div className="flex items-start justify-between mb-4">
            <div>
              <div className="text-xs text-[#CCFF00] tracking-[0.3em] uppercase">{WEEKDAY_NAMES[selectedDate.weekday]}</div>
              <div className="font-head text-2xl sm:text-3xl font-bold">{selectedDate.date}</div>
            </div>
            <button onClick={() => setSelectedDate(null)} className="text-[#525252] hover:text-white"><X className="w-5 h-5" /></button>
          </div>
          <div className="font-head text-xs sm:text-sm tracking-widest text-[#CCFF00] mb-2">{selectedDate.athletes_count} ATLETAS · {Math.round(selectedDate.total_load)} UA</div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs sm:text-sm">
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
      )}
    </div>
  );
}
