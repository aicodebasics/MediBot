"use client";
import { useState } from "react";
import { UserSession } from "@/app/page";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const DEMO_USERS = [
  { username: "dr.mehta",     password: "doctor123",   role: "Doctor",             hint: "Clinical + Nursing + General" },
  { username: "nurse.priya",  password: "nurse123",    role: "Nurse",              hint: "Nursing + General" },
  { username: "billing.ravi", password: "billing123",  role: "Billing Executive",  hint: "Billing + General + SQL RAG" },
  { username: "tech.anand",   password: "tech123",     role: "Technician",         hint: "Equipment + General" },
  { username: "admin.sys",    password: "admin123",    role: "Admin",              hint: "All collections + SQL RAG" },
];

interface Props {
  onLogin: (s: UserSession) => void;
}

export default function LoginPage({ onLogin }: Props) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError]       = useState("");
  const [loading, setLoading]   = useState(false);

  async function handleLogin(u = username, p = password) {
    setLoading(true);
    setError("");
    try {
      const form = new URLSearchParams({ username: u, password: p });
      const res  = await fetch(`${API}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: form,
      });
      if (!res.ok) { setError("Invalid credentials"); return; }
      const data = await res.json();

      const colRes = await fetch(`${API}/collections/${data.role}`, {
        headers: { Authorization: `Bearer ${data.access_token}` },
      });
      const colData = await colRes.json();

      onLogin({
        username: data.username,
        role:     data.role,
        token:    data.access_token,
        collections: colData.collections || [],
      });
    } catch {
      setError("Cannot reach server. Is the backend running?");
    } finally {
      setLoading(false);
    }
  }

  function quickLogin(u: string, p: string) {
    setUsername(u);
    setPassword(p);
    handleLogin(u, p);
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-8">
        <div className="text-center mb-8">
          <div className="text-4xl mb-2">🏥</div>
          <h1 className="text-3xl font-bold text-gray-900">MediBot</h1>
          <p className="text-gray-500 mt-1">MediAssist Health Network</p>
        </div>

        <div className="space-y-4 mb-6">
          <input
            className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-400"
            placeholder="Username"
            value={username}
            onChange={e => setUsername(e.target.value)}
          />
          <input
            type="password"
            className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-400"
            placeholder="Password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleLogin()}
          />
          {error && <p className="text-red-500 text-sm">{error}</p>}
          <button
            onClick={() => handleLogin()}
            disabled={loading}
            className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2 rounded-lg transition disabled:opacity-50"
          >
            {loading ? "Signing in…" : "Sign In"}
          </button>
        </div>

        <div className="border-t pt-6">
          <p className="text-xs text-gray-500 mb-3 font-semibold uppercase tracking-wide">Demo Accounts</p>
          <div className="space-y-2">
            {DEMO_USERS.map(u => (
              <button
                key={u.username}
                onClick={() => quickLogin(u.username, u.password)}
                className="w-full text-left border border-gray-200 hover:border-indigo-300 hover:bg-indigo-50 rounded-lg px-3 py-2 transition"
              >
                <div className="flex justify-between items-center">
                  <span className="font-medium text-gray-800 text-sm">{u.role}</span>
                  <span className="text-xs text-gray-400">{u.username}</span>
                </div>
                <div className="text-xs text-gray-500 mt-0.5">{u.hint}</div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
