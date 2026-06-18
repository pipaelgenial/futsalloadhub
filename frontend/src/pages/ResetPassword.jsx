import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { http, formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { Activity, Check, AlertOctagon } from "lucide-react";

export default function ResetPassword() {
  const { token } = useParams();
  const navigate = useNavigate();
  const [info, setInfo] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ password: "", confirm: "" });
  const [saving, setSaving] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    http.get(`/auth/reset/${token}`)
      .then(({ data }) => setInfo(data))
      .catch((err) => setError(formatApiError(err)))
      .finally(() => setLoading(false));
  }, [token]);

  async function onSubmit(e) {
    e.preventDefault();
    if (form.password !== form.confirm) {
      toast.error("As passwords não coincidem");
      return;
    }
    if (form.password.length < 6) {
      toast.error("A password deve ter pelo menos 6 caracteres");
      return;
    }
    setSaving(true);
    try {
      await http.post(`/auth/reset/${token}`, { password: form.password });
      setDone(true);
      toast.success("Password atualizada");
      setTimeout(() => navigate("/login"), 2200);
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setSaving(false); }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center">
        <div className="font-head text-[#CCFF00] tracking-widest">A VALIDAR LINK...</div>
      </div>
    );
  }

  if (error || !info) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center p-6 grain">
        <div className="w-full max-w-md text-center relative z-[2]" data-testid="reset-invalid">
          <div className="w-12 h-12 bg-[#FF3B30] flex items-center justify-center mx-auto mb-6">
            <AlertOctagon className="w-7 h-7 text-white" strokeWidth={3} />
          </div>
          <h2 className="font-head text-3xl font-black mb-4">LINK INVÁLIDO</h2>
          <p className="text-[#A3A3A3] text-sm mb-8">{error || "Este link já foi utilizado ou expirou."}</p>
          <Link to="/recuperar-password" className="fld-btn-primary inline-block">PEDIR NOVO LINK</Link>
        </div>
      </div>
    );
  }

  if (done) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center p-6 grain">
        <div className="w-full max-w-md text-center relative z-[2]" data-testid="reset-done">
          <div className="w-12 h-12 bg-[#CCFF00] flex items-center justify-center mx-auto mb-6">
            <Check className="w-7 h-7 text-black" strokeWidth={3} />
          </div>
          <h2 className="font-head text-3xl font-black mb-4">PASSWORD ATUALIZADA</h2>
          <p className="text-[#A3A3A3] text-sm mb-2">A redirecionar para o login...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center p-6 grain">
      <form onSubmit={onSubmit} className="w-full max-w-sm relative z-[2]" data-testid="reset-form">
        <div className="flex items-center gap-2 mb-8">
          <div className="w-10 h-10 bg-[#CCFF00] flex items-center justify-center">
            <Activity className="w-6 h-6 text-black" strokeWidth={3} />
          </div>
          <div>
            <div className="font-head text-xl font-extrabold leading-none">FUTSAL</div>
            <div className="font-head text-xs text-[#CCFF00] tracking-[0.3em] leading-none mt-0.5">LOAD HUB</div>
          </div>
        </div>

        <div className="text-xs text-[#CCFF00] tracking-[0.3em] uppercase mb-2">Nova Password</div>
        <h2 className="font-head text-3xl font-black mb-4">DEFINIR PASSWORD</h2>
        <p className="text-[#A3A3A3] text-sm mb-7">
          Conta: <span className="text-white font-bold">{info.email}</span>
        </p>

        <label className="fld-label">Nova password (min. 6)</label>
        <input
          className="fld-input mb-5"
          type="password"
          value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
          required
          minLength={6}
          data-testid="reset-password"
          autoFocus
        />

        <label className="fld-label">Confirmar password</label>
        <input
          className="fld-input mb-7"
          type="password"
          value={form.confirm}
          onChange={(e) => setForm({ ...form, confirm: e.target.value })}
          required
          minLength={6}
          data-testid="reset-confirm"
        />

        <button type="submit" disabled={saving} className="fld-btn-primary w-full" data-testid="reset-submit">
          {saving ? "A GUARDAR..." : "GUARDAR NOVA PASSWORD"}
        </button>
      </form>
    </div>
  );
}
