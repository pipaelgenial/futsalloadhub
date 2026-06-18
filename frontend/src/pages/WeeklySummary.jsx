import { useEffect, useMemo, useState } from "react";
import { http, formatApiError, downloadFile } from "@/lib/api";
import { toast } from "sonner";
import { ArrowUp, ArrowDown, Minus, FileDown } from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell,
  LineChart, Line,
} from "recharts";

const TEAM_SELECTION = "__team__";

export default function WeeklySummary() {
  const [athletes, setAthletes] = useState([]);
  const [selected, setSelected] = useState(TEAM_SELECTION);
  const [weeks, setWeeks] = useState(8);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await http.get("/athletes");
        setAthletes(data);
      } catch (err) { toast.error(formatApiError(err)); }
    })();
  }, []);

  useEffect(() => {
    if (!selected) return;
    (async () => {
      setLoading(true);
      try {
        const url = selected === TEAM_SELECTION
          ? `/analytics/weekly/team/overview?weeks=${weeks}`
          : `/analytics/weekly/${selected}?weeks=${weeks}`;
        const { data } = await http.get(url);
        if (selected === TEAM_SELECTION) {
          setData({ ...data, label: `${data.team?.name || "Equipa"} (Equipa)`, isTeam: true });
        } else {
          setData({ ...data, label: data.athlete?.name, isTeam: false });
        }
      } catch (err) { toast.error(formatApiError(err)); }
      finally { setLoading(false); }
    })();
  }, [selected, weeks]);

  const chartData = useMemo(
    () => (data?.weeks || []).map((w) => ({ ...w })),
    [data]
  );

  const evolutionMeta = useMemo(() => {
    if (!data) return null;
    if (data.evolution === "subiu") return { color: "#FF3B30", label: "Subiu", Icon: ArrowUp };
    if (data.evolution === "desceu") return { color: "#00E676", label: "Desceu", Icon: ArrowDown };
    if (data.evolution === "estável") return { color: "#A3A3A3", label: "Estável", Icon: Minus };
    return null;
  }, [data]);

  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="text-xs text-[#CCFF00] tracking-[0.3em] uppercase mb-2">Análise Semanal</div>
          <h1 className="font-head text-3xl sm:text-4xl md:text-5xl font-black leading-none">RESUMO SEMANAL</h1>
          <p className="text-[#A3A3A3] text-sm mt-2">Média de carga, sono e bem-estar · Evolução vs. semana anterior</p>
        </div>
        <div className="flex gap-2 items-center">
          <select
            className="fld-input py-2"
            value={weeks}
            onChange={(e) => setWeeks(Number(e.target.value))}
            data-testid="weeks-range"
          >
            <option value={4}>4 semanas</option>
            <option value={8}>8 semanas</option>
            <option value={12}>12 semanas</option>
          </select>
          <select
            className="fld-input w-64 py-2"
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            data-testid="weekly-athlete-select"
          >
            <option value={TEAM_SELECTION}>Equipa (Visão Geral)</option>
            <optgroup label="Atletas">
              {athletes.length === 0 && <option disabled>— Sem atletas —</option>}
              {athletes.map((a) => (
                <option key={a.id} value={a.id}>{a.name} {a.jersey_number ? `#${a.jersey_number}` : ""}</option>
              ))}
            </optgroup>
          </select>
          {selected !== TEAM_SELECTION && (
            <button
              type="button"
              onClick={async () => {
                try {
                  await downloadFile(`/export/weekly/${selected}.pdf?weeks=${weeks}`, "resumo_semanal.pdf");
                  toast.success("PDF gerado");
                } catch (err) { toast.error(formatApiError(err)); }
              }}
              data-testid="export-weekly-pdf"
              className="flex items-center gap-1.5 px-3 py-2 border border-[#CCFF00]/40 text-[#CCFF00] hover:bg-[#CCFF00]/10 transition-all text-xs font-head uppercase tracking-widest"
              title="Exportar resumo do atleta selecionado em PDF"
            >
              <FileDown className="w-3.5 h-3.5" /> PDF
            </button>
          )}
        </div>
      </div>

      {data?.isTeam && (
        <div className="text-sm text-[#A3A3A3]" data-testid="weekly-team-label">
          A analisar dados agregados de <span className="text-white font-semibold">{data.athletes_count}</span> atletas.
        </div>
      )}

      {loading && <div className="text-[#A3A3A3] font-head tracking-widest">A CARREGAR...</div>}

      {data && !loading && (
        <>
          <div className="fld-card flex items-center justify-between flex-wrap gap-4" data-testid="evolution-headline">
            <div>
              <div className="fld-label">Evolução da Condição Física</div>
              <div className="flex items-center gap-3 mt-1">
                {evolutionMeta && <evolutionMeta.Icon className="w-7 h-7" style={{ color: evolutionMeta.color }} />}
                <div className="font-head text-3xl font-bold" style={{ color: evolutionMeta?.color || "#fff" }}>
                  {evolutionMeta?.label || "Indeterminado"}
                </div>
                {data.evolution_pct !== 0 && (
                  <div className="metric-num text-2xl" style={{ color: evolutionMeta?.color }}>
                    {data.evolution_pct > 0 ? "+" : ""}{data.evolution_pct}%
                  </div>
                )}
              </div>
            </div>
            <div className="text-sm text-[#A3A3A3] max-w-md text-right">
              Comparação da carga média entre a primeira e a última semana com dados.
              {evolutionMeta?.label === "Subiu" && " ⚠️ Carga em crescimento — atenção ao acúmulo de fadiga."}
              {evolutionMeta?.label === "Desceu" && " ✓ Carga a diminuir — janela favorável de recuperação."}
            </div>
          </div>

          <div className="fld-card" data-testid="weekly-load-chart">
            <div className="font-head text-xl font-bold mb-1">CARGA MÉDIA POR SESSÃO</div>
            <div className="text-xs text-[#A3A3A3] mb-4">Unidades Arbitrárias (RPE × Duração)</div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 10, right: 10, bottom: 0, left: -10 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="label" tick={{ fill: "#A3A3A3", fontSize: 11 }} />
                  <YAxis tick={{ fill: "#525252", fontSize: 11 }} />
                  <Tooltip contentStyle={{ background: "#141414", border: "1px solid rgba(255,255,255,0.15)" }} labelStyle={{ color: "#CCFF00" }} />
                  <Bar dataKey="avg_load">
                    {chartData.map((m) => (
                      <Cell key={m.week || m.label} fill={m.avg_load > 0 ? "#CCFF00" : "#262626"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="grid md:grid-cols-2 gap-4">
            <div className="fld-card" data-testid="weekly-sleep-chart">
              <div className="font-head text-xl font-bold mb-1">QUALIDADE DO SONO</div>
              <div className="text-xs text-[#A3A3A3] mb-4">Média semanal (1-5)</div>
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 10, right: 10, bottom: 0, left: -10 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="label" tick={{ fill: "#A3A3A3", fontSize: 11 }} />
                    <YAxis domain={[0, 5]} tick={{ fill: "#525252", fontSize: 11 }} />
                    <Tooltip contentStyle={{ background: "#141414", border: "1px solid rgba(255,255,255,0.15)" }} labelStyle={{ color: "#CCFF00" }} />
                    <Line type="monotone" dataKey="avg_sleep" stroke="#00E676" strokeWidth={2.5} dot={{ r: 4, fill: "#00E676" }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="fld-card" data-testid="weekly-wellness-chart">
              <div className="font-head text-xl font-bold mb-1">BEM-ESTAR CORPORAL</div>
              <div className="text-xs text-[#A3A3A3] mb-4">Média semanal (1-10)</div>
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 10, right: 10, bottom: 0, left: -10 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="label" tick={{ fill: "#A3A3A3", fontSize: 11 }} />
                    <YAxis domain={[0, 10]} tick={{ fill: "#525252", fontSize: 11 }} />
                    <Tooltip contentStyle={{ background: "#141414", border: "1px solid rgba(255,255,255,0.15)" }} labelStyle={{ color: "#CCFF00" }} />
                    <Line type="monotone" dataKey="avg_wellness" stroke="#CCFF00" strokeWidth={2.5} dot={{ r: 4, fill: "#CCFF00" }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          <div className="fld-card" data-testid="weekly-table">
            <div className="font-head text-xl font-bold mb-4">DETALHE POR SEMANA</div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-widest text-[#525252] border-b border-white/5">
                    <th className="py-3 pr-4">Semana</th>
                    <th className="py-3 px-2">Período</th>
                    <th className="py-3 px-2">Sessões</th>
                    <th className="py-3 px-2">Carga Total</th>
                    <th className="py-3 px-2 text-[#CCFF00]">Carga Média</th>
                    <th className="py-3 px-2">Δ vs. anterior</th>
                    <th className="py-3 px-2">Sono</th>
                    <th className="py-3 px-2">Bem-Estar</th>
                  </tr>
                </thead>
                <tbody>
                  {data.weeks.map((w) => (
                    <tr key={w.week} className="border-b border-white/5">
                      <td className="py-3 pr-4 font-medium">{w.label}</td>
                      <td className="py-3 px-2 text-xs text-[#A3A3A3]">{w.start_date.slice(5)} → {w.end_date.slice(5)}</td>
                      <td className="py-3 px-2 metric-num">{w.sessions}</td>
                      <td className="py-3 px-2 metric-num">{w.total_load || "—"}</td>
                      <td className="py-3 px-2 metric-num text-[#CCFF00]">{w.avg_load || "—"}</td>
                      <td className="py-3 px-2">
                        {w.delta_load_pct === null || w.delta_load_pct === undefined ? (
                          <span className="text-[#525252]">—</span>
                        ) : w.delta_load_pct > 0 ? (
                          <span className="text-[#FF3B30] inline-flex items-center gap-1"><ArrowUp className="w-3 h-3" /> +{w.delta_load_pct}%</span>
                        ) : w.delta_load_pct < 0 ? (
                          <span className="text-[#00E676] inline-flex items-center gap-1"><ArrowDown className="w-3 h-3" /> {w.delta_load_pct}%</span>
                        ) : (
                          <span className="text-[#A3A3A3]">0%</span>
                        )}
                      </td>
                      <td className="py-3 px-2 metric-num">{w.avg_sleep || "—"}<span className="text-[#525252] text-xs">/5</span></td>
                      <td className="py-3 px-2 metric-num">{w.avg_wellness || "—"}<span className="text-[#525252] text-xs">/10</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
