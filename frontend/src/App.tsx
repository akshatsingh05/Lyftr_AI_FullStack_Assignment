import { AlertCircle, Menu, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Composer } from "./components/Composer";
import { MessageBubble } from "./components/MessageBubble";
import { Sidebar } from "./components/Sidebar";
import { StatusDot } from "./components/StatusDot";
import { Welcome } from "./components/Welcome";
import { useChat } from "./hooks/useChat";
import { useHealth } from "./hooks/useHealth";

export default function App() {
  const chat = useChat();
  const { state, info } = useHealth();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [chat.messages, chat.loading, chat.error]);

  return (
    <div className="flex h-full">
      <Sidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onNewChat={chat.newChat}
        sessionId={chat.sessionId}
        messageCount={chat.messages.length}
        connection={state}
        info={info}
        disabled={chat.loading}
      />

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-line bg-surface/70 px-4 py-3">
          <button onClick={() => setSidebarOpen(true)} className="rounded-md p-1.5 text-ink-soft hover:bg-paper md:hidden" aria-label="Open sidebar">
            <Menu size={20} />
          </button>
          <h2 className="font-serif text-lg">Ledger</h2>
          <div className="ml-auto flex items-center gap-2 text-xs text-ink-soft">
            <StatusDot state={state} />
            <span>{state === "online" ? "Connected" : state === "checking" ? "Connecting…" : "Offline"}</span>
          </div>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto" aria-live="polite">
          {chat.messages.length === 0 && !chat.loading ? (
            <Welcome onPick={(t) => void chat.send(t)} disabled={chat.loading || state === "offline"} />
          ) : (
            <div className="mx-auto flex max-w-3xl flex-col gap-5 px-4 py-6">
              {chat.messages.map((m) => (
                <MessageBubble key={m.id} message={m} />
              ))}
              {chat.loading && (
                <div className="flex" role="status" aria-label="Assistant is responding">
                  <div className="flex items-center gap-1.5 rounded-2xl rounded-bl-md border border-line bg-surface px-4 py-3.5">
                    <span className="typing-dot h-1.5 w-1.5 rounded-full bg-ink-soft" />
                    <span className="typing-dot h-1.5 w-1.5 rounded-full bg-ink-soft" />
                    <span className="typing-dot h-1.5 w-1.5 rounded-full bg-ink-soft" />
                  </div>
                </div>
              )}
              <div ref={endRef} />
            </div>
          )}
        </div>

        {chat.error && (
          <div className="mx-auto w-full max-w-3xl px-4 pb-2" role="alert">
            <div className="flex items-start gap-2.5 rounded-xl border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-900">
              <AlertCircle size={17} className="mt-0.5 shrink-0" aria-hidden="true" />
              <p className="flex-1">{chat.error}</p>
              <button onClick={chat.dismissError} className="rounded p-0.5 hover:bg-red-100" aria-label="Dismiss error">
                <X size={15} />
              </button>
            </div>
          </div>
        )}

        <Composer onSend={chat.send} loading={chat.loading} systemPrompt={chat.systemPrompt} onSystemPrompt={chat.setSystemPrompt} />
      </main>
    </div>
  );
}
