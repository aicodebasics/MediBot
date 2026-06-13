"use client";
import { useState } from "react";
import LoginPage from "@/components/LoginPage";
import ChatPage from "@/components/ChatPage";

export interface UserSession {
  username: string;
  role: string;
  token: string;
  collections: string[];
}

export default function Home() {
  const [session, setSession] = useState<UserSession | null>(null);

  if (!session) return <LoginPage onLogin={setSession} />;
  return <ChatPage session={session} onLogout={() => setSession(null)} />;
}
