import { useEffect, useState } from "react";
import { http, formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { Link } from "react-router-dom";
import { Plus, Trash2, UserPlus, Copy, X, Check } from "lucide-react";
import PlayerAvatar from "@/components/PlayerAvatar";

function buildInviteUrl(tokenOrUrl) {
  if (!tokenOrUrl) return "";
  if (tokenOrUrl.startsWith("http")) return tokenOrUrl;
  // url field returned by backend is relative like "/convite/<token>"
  return `${window.location.origin}${tokenOrUrl.startsWith("/") ? tokenOrUrl : `/convite/${tokenOrUrl}`}`;
}

export default function Athletes() {
  const [list, setList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", position: "", jersey_number: "" });
  const [saving, setSaving] = useState(false);
  const [inviteModal, setInviteModal] = useState(null); // { athlete, info }

  async function load() {
    setLoading(true);
    try {
      const { data } = await http.get("/athletes");
      setList(data);
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setLoading(false); }
  }
  useEffect(() => { load(); }, []);

  async function create(e) {
    e.preventDefault();
    setSaving(true);
    try {
      const { data: athlete } = await http.post("/athletes", {
        name: form.name,
        position: form.position || null,
        jersey_number: form.jersey_number ? Number(form.jersey_number) : null,
      });
      toast.success("Atleta criado");
      setForm({ name: "", position: "", jersey_number: "" });
      setOpen(false);
      // Auto-generate invite link and open modal
      try {
        const { data: invite } = await http.post(`/athletes/${athlete.id}/invite`);
        setInviteModal({ athlete, info: invite });
      } catch (e2) {
        // non-blocking
        console.warn("Could not auto-create invite:", e2);
      }
      load();
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setSaving(false); }
  }

  async function openInvite(athlete) {
    try {
      const { data: invite } = await http.post(`/athletes/${athlete.id}/invite`);
      setInviteModal({ athlete, info: invite });
    } catch (err) { toast.error(formatApiError(err)); }
  }

  async function copyInvite(url) {
    try {
      await navigator.clipboard.writeText(url);
      toast.success("Link copiado para a área de transferência");
    } catch {
      // fallback
      const ta = document.createElement("textarea");
      ta.value = url;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      toast.success("Link copiado");
    }
  }

  async function remove(id) {
    if (!window.confirm("Eliminar atleta e respetivas sessões? Se o atleta tiver conta de acesso, esta será também removida.")) return;
    try {
      await http.delete(`/athletes/${id}`);
      toast.success("Atleta eliminado");
      load();
    } catch (err) { toast.error(formatApiError(err)); }
  }

  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="text-xs text-[#CCFF00] tracking-[0.3em] uppercase mb-2">Plantel</div>
          <h1 className="font-head text-3xl sm:text-4xl md:text-5xl font-black leading-none">ATLETAS</h1>
        </div>
        <button className="fld-btn-primary flex items-center gap-2" onClick={() => setOpen(!open)} data-testid="add-athlete-btn">
          <Plus className="w-4 h-4" /> {open ? "FECHAR" : "ADICIONAR"}
        </button>
      </div>

      {open && (
        <form onSubmit={create} className="fld-card max-w-2xl space-y-4" data-testid="athlete-form">
          <div className="grid md:grid-cols-3 gap-4">
            <div className="md:col-span-2">
              <label className="fld-label">Nome</label>
              <input className="fld-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required data-testid="athlete-name" />
            </div>
            <div>
              <label className="fld-label">Nº</label>
              <input className="fld-input" type="number" min="1" max="99" value={form.jersey_number} onChange={(e) => setForm({ ...form, jersey_number: e.target.value })} data-testid="athlete-number" />
            </div>
          </div>
          <div>
            <label className="fld-label">Posição</label>
            <select className="fld-input" value={form.position} onChange={(e) => setForm({ ...form, position: e.target.value })} data-testid="athlete-position">
              <option value="">— Selecionar —</option>
              <option value="Guarda-Redes">Guarda-Redes</option>
              <option value="Fixo">Fixo</option>
              <option value="Ala">Ala</option>
              <option value="Pivô">Pivô</option>
              <option value="Universal">Universal</option>
            </select>
          </div>
          <button type="submit" className="fld-btn-primary" disabled={saving} data-testid="athlete-save">
            {saving ? "A GUARDAR..." : "CRIAR ATLETA"}
          </button>
        </form>
      )}

      {loading ? (
        <div className="text-[#A3A3A3]">A carregar...</div>
      ) : list.length === 0 ? (
        <div className="fld-card text-center py-16" data-testid="no-athletes">
          <div className="font-head text-2xl">SEM ATLETAS</div>
          <p className="text-[#A3A3A3] text-sm mt-2">Adicione o primeiro atleta para começar.</p>
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {list.map((a) => (
            <div key={a.id} className="fld-card fld-card-hover relative" data-testid={`athlete-card-${a.id}`}>
              <div className="flex items-start justify-between mb-3">
                <PlayerAvatar athlete={a} size={56} editable onChange={load} />
                <div className="flex items-center gap-3">
                  <div className="metric-num text-[#CCFF00] text-3xl">{a.jersey_number ? `#${a.jersey_number}` : "—"}</div>
                  <button onClick={() => remove(a.id)} className="text-[#525252] hover:text-[#FF3B30]" data-testid={`delete-athlete-${a.id}`}>
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
              <Link to={`/atletas/${a.id}`} className="block">
                <div className="font-head text-xl font-bold mb-1 hover:text-[#CCFF00] transition-colors flex items-center gap-2">
                  {a.name}
                  {a.is_injured && (
                    <span className="text-[9px] uppercase tracking-widest px-1.5 py-0.5 text-[#FF3B30] bg-[#FF3B30]/10 border border-[#FF3B30]/40" data-testid={`injured-badge-${a.id}`}>
                      Lesionado
                    </span>
                  )}
                </div>
                <div className="text-xs text-[#A3A3A3] uppercase tracking-widest">{a.position || "Sem posição"}</div>
              </Link>
              <button
                onClick={() => openInvite(a)}
                data-testid={`invite-athlete-${a.id}`}
                className="mt-3 w-full flex items-center justify-center gap-1.5 text-[10px] uppercase tracking-widest px-2 py-1.5 border border-[#CCFF00]/30 text-[#CCFF00] hover:bg-[#CCFF00]/10 transition-all"
              >
                <UserPlus className="w-3 h-3" /> Convite de acesso
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Invite Modal */}
      {inviteModal && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4" onClick={() => setInviteModal(null)} data-testid="invite-modal">
          <div className="bg-[#0F0F0F] border border-white/10 max-w-md w-full p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-start justify-between mb-4">
              <div>
                <div className="text-xs text-[#CCFF00] tracking-[0.3em] uppercase mb-1">Convite de Atleta</div>
                <div className="font-head text-xl font-bold">{inviteModal.athlete.name}</div>
              </div>
              <button onClick={() => setInviteModal(null)} className="text-[#525252] hover:text-white" data-testid="invite-close">
                <X className="w-5 h-5" />
              </button>
            </div>

            {inviteModal.info.linked ? (
              <div className="space-y-3">
                <div className="flex items-center gap-2 text-[#CCFF00]">
                  <Check className="w-4 h-4" />
                  <span className="text-sm font-bold">Atleta já tem conta de acesso</span>
                </div>
                <div className="text-xs text-[#A3A3A3]">
                  Email associado: <span className="text-white font-bold">{inviteModal.info.player_email}</span>
                </div>
                <div className="text-[11px] text-[#525252]">
                  Para revogar, elimine o atleta — a conta de acesso será removida automaticamente.
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                <p className="text-xs text-[#A3A3A3]">
                  Partilha este link com o atleta. Ele poderá criar a sua conta e começar a registar sessões.
                </p>
                <div className="bg-black/50 border border-white/10 p-3 break-all text-xs text-[#CCFF00] font-mono" data-testid="invite-url">
                  {buildInviteUrl(inviteModal.info.url)}
                </div>
                <button
                  onClick={() => copyInvite(buildInviteUrl(inviteModal.info.url))}
                  data-testid="invite-copy"
                  className="fld-btn-primary w-full flex items-center justify-center gap-2"
                >
                  <Copy className="w-4 h-4" /> COPIAR LINK
                </button>
                <div className="text-[10px] text-[#525252] uppercase tracking-widest">
                  O link é único e válido até ser utilizado.
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
