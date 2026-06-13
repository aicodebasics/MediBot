"use client";
import { useState, useRef, useEffect } from "react";
import { UserSession } from "@/app/page";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Source {
  source_document: string;
  section_title: string;
  collection: string;
}

interface Message {
  id:            number;
  role:          "user" | "bot";
  text:          string;
  sources:       Source[];
  retrieval_type?: string;
  loading?:      boolean;
}

const ROLE_COLORS: Record<string, string> = {
  doctor:            "bg-blue-100 text-blue-800",
  nurse:             "bg-green-100 text-green-800",
  billing_executive: "bg-amber-100 text-amber-800",
  technician:        "bg-purple-100 text-purple-800",
  admin:             "bg-red-100 text-red-800",
};

const COLLECTION_COLORS: Record<string, string> = {
  general:   "bg-gray-100 text-gray-600",
  clinical:  "bg-blue-100 text-blue-700",
  nursing:   "bg-green-100 text-green-700",
  billing:   "bg-yellow-100 text-yellow-700",
  equipment: "bg-purple-100 text-purple-700",
};

interface Props {
  session:  UserSession;
  onLogout: () => void;
}

export default function ChatPage({ session, onLogout }: Props) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 0,
      role: "bot",
      text: `Hello, ${session.username}! I'm MediBot. You're logged in as **${session.role}** with access to: ${session.collections.join(", ")}. How can I help you today?`,
      sources: [],
    },
  ]);
  const [input, setInput]   = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function sendMessage() {
    const q = input.trim();
    if (!q || sending) return;
    setInput("");
    setSending(true);

    const userMsg: Message = { id: Date.now(), role: "user", text: q, sources: [] };
    const loadingMsg: Message = { id: Date.now() + 1, role: "bot", text: "", sources: [], loading: true };
    setMessages(prev => [...prev, userMsg, loadingMsg]);

    try {
      const res = await fetch(`${API}/chat`, {
        method:  "POST",
        headers: {
          "Content-Type":  "application/json",
          Authorization:   `Bearer ${session.token}`,
        },
        body: JSON.stringify({ question: q }),
      });
      const data = await res.json();
      const botMsg: Message = {
        id:            Date.now() + 2,
        role:          "bot",
        text:          data.answer || data.detail || "No response",
        sources:       data.sources || [],
        retrieval_type: data.retrieval_type,
      };
      setMessages(prev => [...prev.slice(0, -1), botMsg]);
    } catch {
      setMessages(prev => [
        ...prev.slice(0, -1),
        { id: Date.now() + 2, role: "bot", text: "Error: Could not reach the backend.", sources: [] },
      ]);
    } finally {
      setSending(false);
    }
  }

  function renderText(text: string) {
    return text.split("\n").map((line, i) => (
      <span key={i}>
        {line.split(/(\*\*[^*]+\*\*)/).map((part, j) =>
          part.startsWith("**") && part.endsWith("**") ? (
            <strong key={j}>{part.slice(2, -2)}</strong>
          ) : (
            part
          )
        )}
        {i < text.split("\n").length - 1 && <br />}
      </span>
    ));
  }

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <aside className="w-64 bg-white border-r flex flex-col p-4 shrink-0">
        <div className="mb-6">
          <div className="text-xl font-bold text-gray-900 flex items-center gap-2">
            <span>🏥</span> MediBot
          </div>
          <p className="text-xs text-gray-400 mt-1">MediAssist Health Network</p>
        </div>

        <div className="mb-6">
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-2">Logged in as</p>
          <div className="font-medium text-gray-800">{session.username}</div>
          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full mt-1 inline-block ${ROLE_COLORS[session.role] || "bg-gray-100 text-gray-700"}`}>
            {session.role}
          </span>
        </div>

        <div className="mb-6">
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-2">Collections Access</p>
          <div className="flex flex-wrap gap-1">
            {session.collections.map(c => (
              <span key={c} className={`text-xs px-2 py-0.5 rounded-full font-medium ${COLLECTION_COLORS[c] || "bg-gray-100 text-gray-600"}`}>
                {c}
              </span>
            ))}
          </div>
        </div>

        <div className="mt-auto">
          <button
            onClick={onLogout}
            className="w-full text-sm text-gray-500 hover:text-red-600 border border-gray-200 hover:border-red-300 rounded-lg py-2 transition"
          >
            Sign Out
          </button>
        </div>
      </aside>

      {/* Chat area */}
      <div className="flex flex-col flex-1 min-w-0">
        <header className="bg-white border-b px-6 py-3 text-sm text-gray-500 shrink-0">
          Ask questions about your permitted document collections
        </header>

        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {messages.map(msg => (
            <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-2xl ${msg.role === "user" ? "order-2" : "order-1"}`}>
                {msg.loading ? (
                  <div className="bg-white border rounded-2xl px-4 py-3 shadow-sm">
                    <div className="flex gap-1 items-center">
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                    </div>
                  </div>
                ) : (
                  <>
                    <div
                      className={`rounded-2xl px-4 py-3 shadow-sm text-sm leading-relaxed ${
                        msg.role === "user"
                          ? "bg-indigo-600 text-white"
                          : "bg-white border text-gray-800"
                      }`}
                    >
                      {renderText(msg.text)}
                    </div>

                    {msg.retrieval_type && (
                      <div className="mt-1 flex items-center gap-2">
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                          msg.retrieval_type === "sql_rag"
                            ? "bg-purple-100 text-purple-700"
                            : "bg-teal-100 text-teal-700"
                        }`}>
                          {msg.retrieval_type === "sql_rag" ? "🗃 SQL RAG" : "🔍 Hybrid RAG"}
                        </span>
                      </div>
                    )}

                    {msg.sources.length > 0 && (
                      <div className="mt-2 space-y-1">
                        <p className="text-xs text-gray-400 font-medium">Sources:</p>
                        {msg.sources.map((s, i) => (
                          <div key={i} className="text-xs bg-gray-50 border rounded-lg px-3 py-1.5">
                            <span className={`inline-block px-1.5 py-0.5 rounded text-xs font-medium mr-2 ${COLLECTION_COLORS[s.collection] || "bg-gray-100"}`}>
                              {s.collection}
                            </span>
                            <span className="font-medium text-gray-700">{s.source_document}</span>
                            {s.section_title && s.section_title !== "—" && (
                              <span className="text-gray-400"> — {s.section_title}</span>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        <div className="bg-white border-t px-6 py-4 shrink-0">
          <div className="flex gap-3">
            <input
              className="flex-1 border border-gray-300 rounded-xl px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
              placeholder="Ask a question…"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && sendMessage()}
              disabled={sending}
            />
            <button
              onClick={sendMessage}
              disabled={sending || !input.trim()}
              className="bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2 rounded-xl text-sm font-medium transition disabled:opacity-50"
            >
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
