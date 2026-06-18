import { useState } from "react";
import { Link } from "react-router-dom";
import { http, formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { Activity, Mail, ArrowLeft } from "lucide-react";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setLoading(true);
    try {
      await http.post("/auth/forgot", { email });
      setSubmitted(true);
    } catch (err) {
      toast.error(formatApiError(err));
    } finally { setLoading(false); }
  }

  if (submitted) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center p-6 grain">
        <div className="w-full max-w-md text-center relative z-[2]" data-testid="forgot-sent">
          <div className="w-12 h-12 bg-[#CCFF00] flex items-center justify-center mx-auto mb-6">
            <Mail className="w-6 h-6 text-black" strokeWidth={3} />
          </div>
          <div className="text-xs text-[#CCFF00] tracking-[0.3em] uppercase mb-3">Verifica o teu email</div>
          <h2 className="font-head text-3xl font-black mb-4">PEDIDO ENVIADO</h2>
          <p className="text-[#A3A3A3] text-sm mb-2">
            Se a conta <span className="text-white font-bold">{email}</span> existir, irás receber um email com um link de recuperação válido por 1 hora.
          </p>
          <p className="text-[#525252] text-xs mb-8">
            Não te esqueças de verificar a pasta de SPAM.
          </p>
          <Link to="/login" className="fld-btn-primary inline-flex items-center gap-2" data-testid="back-to-login">
            <ArrowLeft className="w-4 h-4" /> VOLTAR AO LOGIN
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center p-6 grain">
      <form onSubmit={onSubmit} className="w-full max-w-sm relative z-[2]" data-testid="forgot-form">
        <div className="flex items-center gap-2 mb-8">
          <div className="w-10 h-10 bg-[#CCFF00] flex items-center justify-center">
            <Activity className="w-6 h-6 text-black" strokeWidth={3} />
          </div>
          <div>
            <div className="font-head text-xl font-extrabold leading-none">FUTSAL</div>
            <div className="font-head text-xs text-[#CCFF00] tracking-[0.3em] leading-none mt-0.5">LOAD HUB</div>
          </div>
        </div>

        <div className="text-xs text-[#CCFF00] tracking-[0.3em] uppercase mb-2">Recuperar Acesso</div>
        <h2 className="font-head text-3xl font-black mb-4">ESQUECESTE A PASSWORD?</h2>
        <p className="text-[#A3A3A3] text-sm mb-7">
          Indica o teu email. Se a conta existir, enviamos um link para criares uma nova password.
        </p>

        <label className="fld-label">Email</label>
        <input
          className="fld-input mb-7"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          data-testid="forgot-email"
          autoFocus
        />

        <button type="submit" disabled={loading || !email} className="fld-btn-primary w-full" data-testid="forgot-submit">
          {loading ? "A ENVIAR..." : "ENVIAR LINK DE RECUPERAÇÃO"}
        </button>

        <div className="mt-6 text-center text-xs text-[#525252]">
          <Link to="/login" className="hover:text-white inline-flex items-center gap-1.5" data-testid="forgot-back">
            <ArrowLeft className="w-3 h-3" /> Voltar ao login
          </Link>
        </div>
      </form>
    </div>
  );
}
