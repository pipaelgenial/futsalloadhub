import { useEffect, useState } from "react";
import { http, formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { Link } from "react-router-dom";
import { RiskBadge, MetricCard, riskMeta, MonotonyAlert } from "@/components/Bits";
import PlayerAvatar from "@/components/PlayerAvatar";
import { AlertTriangle, Database, ArrowRight, Trash2 } from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceArea, CartesianGrid,
  BarChart, Bar, Cell,
} from "recharts";

const TEAM_SELECTION = "__team__";

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [detailSeries, setDetailSeries] = useState([]);
  const [detailMetrics, setDetailMetrics] = useState(null);
  const [detailLabel, setDetailLabel] = useState("");
  const [selectedDetail, setSelectedDetail] = useState(TEAM_SELECTION);

  async function load() {
    setLoading(true);
    try {
      const { data } = await http.get("/analytics/team");
      setData(data);
    } catch (err) {
      toast.error(formatApiError(err));
    } finally { setLoading(false); }
  }

  // Fetch detailed view depending on selected entity
  async function loadDetail(selection) {
    try {
      if (selection === TEAM_SELECTION) {
        const { data } = await http.get("/analytics/team-detailed");
        if (data?.team) {
          setDetailSeries(data.series || []);
          setDetailMetrics(data.metrics);
          setDetailLabel(`${data.team.name} (Equipa)`);
        } else {
          setDetailSeries([]);
          setDetailMetrics(null);
        }
      } else {
        const { data } = await http.get(`/analytics/athlete/${selection}`);
        setDetailSeries(data.series || []);
        setDetailMetrics(data.metrics);
        setDetailLabel(data.athlete.name);
      }
    } catch (err) { toast.error(formatApiError(err)); }
  }

  useEffect(() => { load(); }, []);
  useEffect(() => {
    if (data?.team && data.athletes.length > 0) loadDetail(selectedDetail);
  }, [data?.team?.id, selectedDetail]);

  async function seedDemo() {
    setSeeding(true);
    try {
      await http.post("/seed/demo");
      toast.success("Dados de demonstração criados");
      await load();
    } catch (err) {
      toast.error(formatApiError(err));
    } finally { setSeeding(false); }
  }

  async function resetAll() {
    const txt = window.prompt(
      "Esta ação elimina TODOS os dados: equipa, atletas, sessões, lesões e fotos.\n\nEscreva ELIMINAR (em maiúsculas) para confirmar:"
    );
    if (txt !== "ELIMINAR") {
      if (txt !== null) toast.error("Confirmação inválida — operação cancelada");
      return;
    }
    setSeeding(true);
    try {
      const { data } = await http.post("/reset-all");
      const d = data.deleted || {};
      toast.success(`Todos os dados foram eliminados (${d.athletes || 0} atletas, ${d.sessions || 0} sessões, ${d.injuries || 0} lesões)`);
      setDetailSeries([]);
      setDetailMetrics(null);
      setSelectedDetail(TEAM_SELECTION);
      await load();
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setSeeding(false); }
  }

  if (loading) return <div className="text-[#A3A3A3] font-head tracking-widest">A CARREGAR...</div>;

  const noTeam = !data?.team;
  const noAthletes = data?.team && (data.athletes || []).length === 0;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="text-xs text-[#CCFF00] tracking-[0.3em] uppercase mb-2">Painel Principal</div>
          <h1 className="font-head text-5xl md:text-6xl font-black leading-none">DASHBOARD</h1>
          {data?.team && (
            <div className="mt-3 text-[#A3A3A3] text-sm">
              <span className="text-white font-semibold">{data.team.name}</span> · {data.team.escalao} · Época {data.team.epoca}
            </div>
          )}
        </div>
        <div className="flex gap-2 flex-wrap">
          <button onClick={seedDemo} disabled={seeding} className="fld-btn-ghost flex items-center gap-2" data-testid="seed-demo-btn">
            <Database className="w-4 h-4" /> {seeding ? "A GERAR..." : "DADOS DEMO"}
          </button>
          <button
            onClick={resetAll}
            disabled={seeding || !data?.team}
            className="font-head font-bold uppercase tracking-widest px-5 py-2.5 text-xs flex items-center gap-2 transition-all border bg-transparent border-[#FF3B30]/30 text-[#FF3B30] hover:bg-[#FF3B30]/10 disabled:opacity-30 disabled:cursor-not-allowed"
            data-testid="reset-all-btn"
            title="Elimina todos os dados (irreversível)"
          >
            <Trash2 className="w-3.5 h-3.5" /> RESET TOTAL
          </button>
        </div>
      </div>

      {noTeam && (
        <div className="fld-card text-center py-16" data-testid="no-team-state">
          <div className="font-head text-2xl text-white mb-3">INSIRA DADOS DA EQUIPA</div>
          <p className="text-[#A3A3A3] mb-6 text-sm">Comece por configurar o perfil da sua equipa de futsal.</p>
          <Link to="/equipa" className="fld-btn-primary inline-block">CONFIGURAR EQUIPA</Link>
        </div>
      )}

      {noAthletes && (
        <div className="fld-card text-center py-16" data-testid="no-athletes-state">
          <div className="font-head text-2xl text-white mb-3">ADICIONE ATLETAS</div>
          <p className="text-[#A3A3A3] mb-6 text-sm">Adicione atletas à sua equipa para começar a registar sessões.</p>
          <Link to="/atletas" className="fld-btn-primary inline-block">GERIR ATLETAS</Link>
        </div>
      )}

      {data?.team && (data.athletes || []).length > 0 && (
        <>
          {/* Team metrics */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-7 gap-4">
            <MetricCard label="Atletas" value={data.summary.athletes_count} testid="metric-athletes" />
            <MetricCard label="Carga Aguda Média" value={data.summary.avg_acute} unit="UA" testid="metric-avg-acute" />
            <MetricCard label="Carga Crónica Média" value={data.summary.avg_chronic} unit="UA" accent testid="metric-avg-chronic" />
            <MetricCard label="Sono Médio" value={data.summary.avg_sleep || "—"} unit="/5" testid="metric-avg-sleep" />
            <MetricCard label="Bem-Estar Médio" value={data.summary.avg_wellness || "—"} unit="/10" testid="metric-avg-wellness" />
            <MetricCard label="Monotonia Média" value={data.summary.avg_monotony || "—"} testid="metric-avg-monotony" zoneCol={data.summary.avg_monotony ? (data.summary.avg_monotony_zone === "critical" ? "#FF3B30" : data.summary.avg_monotony_zone === "moderate_high" ? "#FFEA00" : "#00E676") : null} />
            <MetricCard label="C/ Dados Suficientes" value={`${data.summary.athletes_with_sufficient_data}/${data.summary.athletes_count}`} testid="metric-sufficient" />
          </div>

          {/* Team-wide monotony alert */}
          {data.summary.avg_monotony > 0 && (
            <MonotonyAlert
              value={data.summary.avg_monotony}
              zone={data.summary.avg_monotony_zone}
              testid="team-monotony-alert"
            />
          )}

          {/* Risk Alerts */}
          {(() => {
            const danger = data.athletes.filter((a) => a.metrics.risk === "danger");
            const warning = data.athletes.filter((a) => a.metrics.risk === "warning");
            if (!danger.length && !warning.length) return null;
            return (
              <div className="fld-card border-l-4 border-l-[#FF3B30]" data-testid="alerts-panel">
                <div className="flex items-center gap-3 mb-4">
                  <AlertTriangle className="w-5 h-5 text-[#FF3B30]" />
                  <div className="font-head text-xl font-bold tracking-tight">ALERTAS DE RISCO</div>
                </div>
                <div className="grid md:grid-cols-2 gap-3">
                  {[...danger, ...warning].map((a) => (
                    <Link key={a.id} to={`/atletas/${a.id}`} className="flex items-start gap-3 p-3 border border-white/5 hover:border-white/20 transition-colors" data-testid={`alert-row-${a.id}`}>
                      <PlayerAvatar athlete={a} size={48} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap mb-1">
                          <div className="font-semibold">{a.name}</div>
                          <RiskBadge risk={a.metrics.risk} />
                        </div>
                        <div className="text-xs text-[#A3A3A3] mb-1">
                          ACWR <span className="metric-num text-white">{a.metrics.acwr}</span>
                          {" · "}Mono <span className="metric-num text-white">{a.metrics.monotony || "—"}</span>
                          {" · "}Strain <span className="metric-num text-white">{a.metrics.strain || "—"}</span>
                        </div>
                        {a.metrics.risk_description && (
                          <div className="text-xs text-[#FFEA00]/80 leading-snug" data-testid={`alert-desc-${a.id}`}>
                            {a.metrics.risk_description}
                          </div>
                        )}
                      </div>
                      <ArrowRight className="w-4 h-4 text-[#525252] mt-2 flex-shrink-0" />
                    </Link>
                  ))}
                </div>
              </div>
            );
          })()}

          {/* ACWR chart with selector */}
          <div className="fld-card" data-testid="acwr-chart-panel">
            <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
              <div>
                <div className="fld-label">Vista Detalhada</div>
                <div className="font-head text-2xl font-bold">ACWR — {detailLabel || "Equipa"}</div>
              </div>
              <div className="flex items-center gap-3 flex-wrap">
                <select
                  value={selectedDetail}
                  onChange={(e) => setSelectedDetail(e.target.value)}
                  className="fld-input py-2 min-w-[220px]"
                  data-testid="detail-selector"
                >
                  <option value={TEAM_SELECTION}>Equipa (Visão Geral)</option>
                  <optgroup label="Atletas">
                    {data.athletes.map((a) => (
                      <option key={a.id} value={a.id}>{a.name}{a.jersey_number ? ` #${a.jersey_number}` : ""}</option>
                    ))}
                  </optgroup>
                </select>
                <div className="text-xs text-[#A3A3A3] hidden md:flex gap-4">
                  <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-[#CCFF00] inline-block" /> ACWR</span>
                  <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-white inline-block" /> Aguda</span>
                  <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-[#A3A3A3] inline-block" /> Crónica</span>
                </div>
              </div>
            </div>

            {/* Detail metrics summary line */}
            {detailMetrics && (
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-5 text-sm" data-testid="detail-metrics-row">
                <div>
                  <div className="fld-label">Aguda</div>
                  <div className="metric-num text-2xl">{detailMetrics.acute} <span className="text-xs text-[#A3A3A3]">UA</span></div>
                </div>
                <div>
                  <div className="fld-label">Crónica</div>
                  <div className="metric-num text-2xl">{detailMetrics.chronic} <span className="text-xs text-[#A3A3A3]">UA</span></div>
                </div>
                <div className="relative pl-3" style={{ borderLeft: `3px solid ${detailMetrics.sufficient_data ? (detailMetrics.acwr_zone === "sweet_spot" ? "#00E676" : detailMetrics.acwr_zone === "detraining" || detailMetrics.acwr_zone === "alert" ? "#FFEA00" : detailMetrics.acwr_zone === "high_risk" ? "#FF3B30" : "#525252") : "#525252"}` }} data-testid="detail-acwr">
                  <div className="fld-label">ACWR</div>
                  <div className="metric-num text-2xl" style={{ color: detailMetrics.sufficient_data ? (detailMetrics.acwr_zone === "sweet_spot" ? "#00E676" : detailMetrics.acwr_zone === "high_risk" ? "#FF3B30" : "#CCFF00") : "#525252" }}>
                    {detailMetrics.sufficient_data ? detailMetrics.acwr : "—"}
                  </div>
                  {detailMetrics.sufficient_data && (
                    <div className="text-[10px] uppercase tracking-widest mt-0.5" style={{ color: detailMetrics.acwr_zone === "sweet_spot" ? "#00E676" : detailMetrics.acwr_zone === "high_risk" ? "#FF3B30" : "#FFEA00" }}>
                      {detailMetrics.acwr_zone === "sweet_spot" ? "Zona Ótima" : detailMetrics.acwr_zone === "detraining" ? "Destreinamento" : detailMetrics.acwr_zone === "alert" ? "Alerta" : detailMetrics.acwr_zone === "high_risk" ? "Alto Risco" : ""}
                    </div>
                  )}
                </div>
                <div className="relative pl-3" style={{ borderLeft: `3px solid ${detailMetrics.monotony ? (detailMetrics.monotony_zone === "ideal" || detailMetrics.monotony_zone === "high_variation" ? "#00E676" : detailMetrics.monotony_zone === "moderate_high" ? "#FFEA00" : detailMetrics.monotony_zone === "critical" ? "#FF3B30" : "#525252") : "#525252"}` }} data-testid="detail-monotony">
                  <div className="fld-label">Monotonia</div>
                  <div className="metric-num text-2xl" style={{ color: detailMetrics.monotony ? (detailMetrics.monotony_zone === "ideal" || detailMetrics.monotony_zone === "high_variation" ? "#00E676" : detailMetrics.monotony_zone === "moderate_high" ? "#FFEA00" : detailMetrics.monotony_zone === "critical" ? "#FF3B30" : "#fff") : "#525252" }}>
                    {detailMetrics.monotony || "—"}
                  </div>
                  {detailMetrics.monotony > 0 && (
                    <div className="text-[10px] uppercase tracking-widest mt-0.5" style={{ color: detailMetrics.monotony_zone === "ideal" || detailMetrics.monotony_zone === "high_variation" ? "#00E676" : detailMetrics.monotony_zone === "moderate_high" ? "#FFEA00" : "#FF3B30" }}>
                      {detailMetrics.monotony_zone === "ideal" ? "Ideal" : detailMetrics.monotony_zone === "high_variation" ? "Boa Variação" : detailMetrics.monotony_zone === "moderate_high" ? "Mod-Alta" : detailMetrics.monotony_zone === "critical" ? "Crítica" : ""}
                    </div>
                  )}
                </div>
                <div className="relative pl-3" style={{ borderLeft: `3px solid ${detailMetrics.strain ? (detailMetrics.strain_zone === "moderate" ? "#00E676" : detailMetrics.strain_zone === "elevated" ? "#FFEA00" : detailMetrics.strain_zone === "extreme" ? "#FF3B30" : "#525252") : "#525252"}` }} data-testid="detail-strain">
                  <div className="fld-label">Strain</div>
                  <div className="metric-num text-2xl" style={{ color: detailMetrics.strain ? (detailMetrics.strain_zone === "moderate" ? "#00E676" : detailMetrics.strain_zone === "elevated" ? "#FFEA00" : detailMetrics.strain_zone === "extreme" ? "#FF3B30" : "#fff") : "#525252" }}>
                    {detailMetrics.strain || "—"}
                  </div>
                  {detailMetrics.strain > 0 && (
                    <div className="text-[10px] uppercase tracking-widest mt-0.5" style={{ color: detailMetrics.strain_zone === "moderate" ? "#00E676" : detailMetrics.strain_zone === "elevated" ? "#FFEA00" : detailMetrics.strain_zone === "extreme" ? "#FF3B30" : "#A3A3A3" }}>
                      {detailMetrics.strain_zone === "low" ? "Baixo" : detailMetrics.strain_zone === "moderate" ? "Moderado" : detailMetrics.strain_zone === "elevated" ? "Elevado" : detailMetrics.strain_zone === "extreme" ? "Extremo" : ""}
                    </div>
                  )}
                </div>
              </div>
            )}

            {!detailMetrics || !detailMetrics.sufficient_data ? (
              <div className="py-16 text-center" data-testid="insufficient-data-msg">
                <div className="font-head text-3xl font-bold text-[#A3A3A3] mb-2">DADOS INSUFICIENTES</div>
                <p className="text-sm text-[#525252]">
                  O painel ACWR exibe dados a partir de 28 dias após o primeiro treino.
                  {detailMetrics?.days_since_first > 0 && ` Faltam ${Math.max(0, 28 - detailMetrics.days_since_first)} dias.`}
                </p>
              </div>
            ) : (
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={detailSeries} margin={{ top: 10, right: 10, bottom: 0, left: -10 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" tick={{ fill: "#525252", fontSize: 10 }} tickFormatter={(v) => v.slice(5)} />
                    <YAxis yAxisId="left" tick={{ fill: "#525252", fontSize: 10 }} />
                    <YAxis yAxisId="right" orientation="right" tick={{ fill: "#CCFF00", fontSize: 10 }} domain={[0, 2]} />
                    <Tooltip contentStyle={{ background: "#141414", border: "1px solid rgba(255,255,255,0.15)" }} labelStyle={{ color: "#CCFF00" }} />
                    <ReferenceArea yAxisId="right" y1={0.8} y2={1.3} fill="#00E676" fillOpacity={0.06} />
                    <Line yAxisId="left" type="monotone" dataKey="acute" stroke="#FFFFFF" strokeWidth={1.5} dot={false} />
                    <Line yAxisId="left" type="monotone" dataKey="chronic" stroke="#A3A3A3" strokeWidth={1.5} dot={false} />
                    <Line yAxisId="right" type="monotone" dataKey="acwr" stroke="#CCFF00" strokeWidth={2.5} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          {/* Athletes table */}
          <div className="fld-card" data-testid="athletes-overview">
            <div className="flex items-center justify-between mb-4">
              <div className="font-head text-2xl font-bold">VISÃO GERAL DA EQUIPA</div>
              <Link to="/atletas" className="text-xs text-[#CCFF00] uppercase tracking-widest hover:underline">Gerir Atletas →</Link>
            </div>
            <div className="overflow-x-auto -mx-6 px-6">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-widest text-[#525252] border-b border-white/5">
                    <th className="py-3 pr-4">Atleta</th>
                    <th className="py-3 px-2">Aguda</th>
                    <th className="py-3 px-2">Crónica</th>
                    <th className="py-3 px-2 text-[#CCFF00]">ACWR</th>
                    <th className="py-3 px-2">Monotonia</th>
                    <th className="py-3 px-2">Strain</th>
                    <th className="py-3 px-2">Sessões</th>
                    <th className="py-3 px-2">Estado</th>
                  </tr>
                </thead>
                <tbody>
                  {data.athletes.map((a) => (
                    <tr key={a.id} className="border-b border-white/5 hover:bg-white/[0.02]">
                      <td className="py-3 pr-4">
                        <Link to={`/atletas/${a.id}`} className="hover:text-[#CCFF00]" data-testid={`athlete-row-${a.id}`}>
                          {a.name}
                          <span className="text-[#525252] text-xs ml-2">{a.position}</span>
                        </Link>
                      </td>
                      <td className="py-3 px-2 metric-num">{a.metrics.acute}</td>
                      <td className="py-3 px-2 metric-num">{a.metrics.chronic}</td>
                      <td className="py-3 px-2 metric-num text-[#CCFF00]">{a.metrics.sufficient_data ? a.metrics.acwr : "—"}</td>
                      <td className="py-3 px-2 metric-num">{a.metrics.monotony || "—"}</td>
                      <td className="py-3 px-2 metric-num">{a.metrics.strain || "—"}</td>
                      <td className="py-3 px-2">{a.metrics.total_sessions}</td>
                      <td className="py-3 px-2"><RiskBadge risk={a.metrics.risk} /></td>
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
