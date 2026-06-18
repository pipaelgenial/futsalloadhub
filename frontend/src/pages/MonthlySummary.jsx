import { useEffect, useMemo, useState } from "react";
import { http, formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { MetricCard } from "@/components/Bits";
import { ArrowUp, ArrowDown, Minus } from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell,
  LineChart, Line,
} from "recharts";

const MONTH_NAMES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];
const formatMonth = (k) => {
  const [y, m] = k.split("-");
  return `${MONTH_NAMES[Number(m) - 1]}/${y.slice(2)}`;
};

const TEAM_SELECTION = "__team__";

export default function MonthlySummary() {
  const [athletes, setAthletes] = useState([]);
  const [selected, setSelected] = useState(TEAM_SELECTION);
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
          ? "/analytics/monthly/team/overview?months=6"
          : `/analytics/monthly/${selected}?months=6`;
        const { data } = await http.get(url);
        // normalize: team endpoint has no `athlete`
        if (selected === TEAM_SELECTION) {
          setData({ ...data, label: `${data.team?.name || "Equipa"} (Equipa)`, isTeam: true });
        } else {
          setData({ ...data, label: data.athlete?.name, isTeam: false });
        }
      } catch (err) { toast.error(formatApiError(err)); }
      finally { setLoading(false); }
    })();
  }, [selected]);

  const chartData = useMemo(
    () => (data?.months || []).map((m) => ({ ...m, label: formatMonth(m.month) })),
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
          <div className="text-xs text-[#CCFF00] tracking-[0.3em] uppercase mb-2">Análise Mensal</div>
          <h1 className="font-head text-3xl sm:text-4xl md:text-5xl font-black leading-none">RESUMO MENSAL</h1>
          <p className="text-[#A3A3A3] text-sm mt-2">Média de carga e qualidade do sono · Evolução vs. mês anterior</p>
        </div>
        <select
          className="fld-input w-64"
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          data-testid="monthly-athlete-select"
        >
          <option value={TEAM_SELECTION}>Equipa (Visão Geral)</option>
          <optgroup label="Atletas">
            {athletes.length === 0 && <option disabled>— Sem atletas —</option>}
            {athletes.map((a) => (
              <option key={a.id} value={a.id}>{a.name} {a.jersey_number ? `#${a.jersey_number}` : ""}</option>
            ))}
          </optgroup>
        </select>
      </div>

      {data?.isTeam && (
        <div className="text-sm text-[#A3A3A3]" data-testid="monthly-team-label">
          A analisar dados agregados de <span className="text-white font-semibold">{data.athletes_count}</span> atletas.
        </div>
      )}

      {!selected && (
        <div className="fld-card text-center py-16">
          <div className="font-head text-2xl">SELECIONE UMA OPÇÃO</div>
          <p className="text-[#A3A3A3] text-sm mt-2">Escolha a equipa ou um atleta para ver o resumo mensal.</p>
        </div>
      )}

      {loading && <div className="text-[#A3A3A3] font-head tracking-widest">A CARREGAR...</div>}

      {data && !loading && (
        <>
          {/* Evolution headline */}
          <div className="fld-card flex items-center justify-between flex-wrap gap-4" data-testid="evolution-headline">
            <div>
              <div className="fld-label">Evolução da Condição Física</div>
              <div className="flex items-center gap-3 mt-1">
                {evolutionMeta && (
                  <evolutionMeta.Icon className="w-7 h-7" style={{ color: evolutionMeta.color }} />
                )}
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
              Comparação da carga média entre o primeiro e o último mês com dados.
              {evolutionMeta?.label === "Subiu" && " ⚠️ Carga em crescimento — atenção ao acúmulo de fadiga."}
              {evolutionMeta?.label === "Desceu" && " ✓ Carga a diminuir — janela favorável de recuperação."}
            </div>
          </div>

          {/* Avg load chart */}
          <div className="fld-card" data-testid="monthly-load-chart">
            <div className="font-head text-xl font-bold mb-1">CARGA MÉDIA POR SESSÃO</div>
            <div className="text-xs text-[#A3A3A3] mb-4">Unidades Arbitrárias (RPE × Duração)</div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 10, right: 10, bottom: 0, left: -10 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="label" tick={{ fill: "#A3A3A3", fontSize: 11 }} />
                  <YAxis tick={{ fill: "#525252", fontSize: 11 }} />
                  <Tooltip contentStyle={{ background: "#141414", border: "1px solid rgba(255,255,255,0.15)" }} labelStyle={{ color: "#CCFF00" }} />
                  <Bar dataKey="avg_load" radius={[0, 0, 0, 0]}>
                    {chartData.map((m) => (
                      <Cell key={m.month || m.label} fill={m.avg_load > 0 ? "#CCFF00" : "#262626"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Avg sleep line chart */}
          <div className="fld-card" data-testid="monthly-sleep-chart">
            <div className="font-head text-xl font-bold mb-1">QUALIDADE DO SONO</div>
            <div className="text-xs text-[#A3A3A3] mb-4">Média mensal (1-5)</div>
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

          {/* Table */}
          <div className="fld-card" data-testid="monthly-table">
            <div className="font-head text-xl font-bold mb-4">DETALHE POR MÊS</div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-widest text-[#525252] border-b border-white/5">
                    <th className="py-3 pr-4">Mês</th>
                    <th className="py-3 px-2">Sessões</th>
                    <th className="py-3 px-2">Carga Total</th>
                    <th className="py-3 px-2 text-[#CCFF00]">Carga Média</th>
                    <th className="py-3 px-2">Δ vs. mês anterior</th>
                    <th className="py-3 px-2">Sono Médio</th>
                  </tr>
                </thead>
                <tbody>
                  {data.months.map((m) => (
                    <tr key={m.month} className="border-b border-white/5">
                      <td className="py-3 pr-4 font-medium">{formatMonth(m.month)}</td>
                      <td className="py-3 px-2 metric-num">{m.sessions}</td>
                      <td className="py-3 px-2 metric-num">{m.total_load || "—"}</td>
                      <td className="py-3 px-2 metric-num text-[#CCFF00]">{m.avg_load || "—"}</td>
                      <td className="py-3 px-2">
                        {m.delta_load_pct === null || m.delta_load_pct === undefined ? (
                          <span className="text-[#525252]">—</span>
                        ) : m.delta_load_pct > 0 ? (
                          <span className="text-[#FF3B30] inline-flex items-center gap-1"><ArrowUp className="w-3 h-3" /> +{m.delta_load_pct}%</span>
                        ) : m.delta_load_pct < 0 ? (
                          <span className="text-[#00E676] inline-flex items-center gap-1"><ArrowDown className="w-3 h-3" /> {m.delta_load_pct}%</span>
                        ) : (
                          <span className="text-[#A3A3A3]">0%</span>
                        )}
                      </td>
                      <td className="py-3 px-2 metric-num">{m.avg_sleep || "—"}<span className="text-[#525252] text-xs">/5</span></td>
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
