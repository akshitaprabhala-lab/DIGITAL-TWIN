import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { formatApiErrorDetail } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Activity, ShieldAlert } from "lucide-react";

export default function Login() {
  const { login, register } = useAuth();
  const nav = useNavigate();
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("doctor@twinmed.app");
  const [password, setPassword] = useState("twinmed123");
  const [name, setName] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setErr(""); setBusy(true);
    try {
      if (mode === "login") await login(email, password);
      else await register(name, email, password);
      nav("/");
    } catch (e2) {
      setErr(formatApiErrorDetail(e2.response?.data?.detail) || e2.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="h-screen w-screen flex bg-twin-stage text-zinc-100 overflow-hidden">
      {/* left: imaging visual */}
      <div className="hidden md:block relative flex-1 border-r border-twin-darkline">
        <img
          src="https://images.pexels.com/photos/14829613/pexels-photo-14829613.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"
          alt="research lab"
          className="absolute inset-0 w-full h-full object-cover opacity-40"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-twin-stage via-twin-stage/60 to-transparent" />
        <div className="absolute bottom-0 left-0 p-12 max-w-lg">
          <div className="flex items-center gap-2 text-twin-teal mb-4">
            <Activity className="h-5 w-5" />
            <span className="font-mono tracking-widest text-xs uppercase">TwinMed · precision engine</span>
          </div>
          <h1 className="text-4xl font-semibold tracking-tight leading-tight">
            A personalised physiological twin for every patient.
          </h1>
          <p className="mt-4 text-sm text-zinc-400 leading-relaxed">
            Test drugs and doses on a validated virtual twin before you prescribe. Mechanistic
            models produce the numbers — the assistant only reasons about them.
          </p>
        </div>
      </div>

      {/* right: auth form */}
      <div className="w-full md:w-[440px] flex flex-col justify-center px-10">
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-1">
            <div className="h-8 w-8 rounded-md bg-twin-teal flex items-center justify-center">
              <Activity className="h-4 w-4 text-black" />
            </div>
            <span className="text-lg font-semibold tracking-tight">TwinMed</span>
          </div>
          <p className="text-sm text-zinc-400">Clinician sign-in</p>
        </div>

        <form onSubmit={submit} className="space-y-4">
          {mode === "register" && (
            <div className="space-y-1.5">
              <Label className="text-zinc-300 text-xs">Full name</Label>
              <Input data-testid="auth-name" value={name} onChange={(e) => setName(e.target.value)}
                required className="bg-zinc-900 border-twin-darkline text-zinc-100" placeholder="Dr. Jane Doe" />
            </div>
          )}
          <div className="space-y-1.5">
            <Label className="text-zinc-300 text-xs">Email</Label>
            <Input data-testid="auth-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)}
              required className="bg-zinc-900 border-twin-darkline text-zinc-100 font-mono" />
          </div>
          <div className="space-y-1.5">
            <Label className="text-zinc-300 text-xs">Password</Label>
            <Input data-testid="auth-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              required className="bg-zinc-900 border-twin-darkline text-zinc-100 font-mono" />
          </div>

          {err && (
            <div data-testid="auth-error" className="flex items-start gap-2 text-xs text-twin-amber bg-twin-amber/10 border border-twin-amber/30 rounded-md px-3 py-2">
              <ShieldAlert className="h-4 w-4 mt-0.5 shrink-0" /> <span>{err}</span>
            </div>
          )}

          <Button data-testid="auth-submit" type="submit" disabled={busy}
            className="w-full bg-twin-teal hover:bg-teal-600 text-black font-medium">
            {busy ? "…" : mode === "login" ? "Sign in" : "Create account"}
          </Button>
        </form>

        <button
          data-testid="auth-toggle"
          onClick={() => { setMode(mode === "login" ? "register" : "login"); setErr(""); }}
          className="mt-4 text-xs text-zinc-400 hover:text-twin-teal text-left"
        >
          {mode === "login" ? "New clinician? Create an account" : "Have an account? Sign in"}
        </button>

        <div className="mt-8 text-[11px] text-zinc-500 font-mono leading-relaxed border-t border-twin-darkline pt-4">
          DEMO · doctor@twinmed.app / twinmed123<br />
          No real PHI — synthetic patients only.
        </div>
      </div>
    </div>
  );
}
