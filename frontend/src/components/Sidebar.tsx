import { MessageSquarePlus, X } from "lucide-react";
import type { ConnectionState, HealthInfo } from "../types";
import { StatusDot } from "./StatusDot";

interface Props {
  open: boolean;
  onClose: () => void;
  onNewChat: () => void;
  sessionId: string;
  messageCount: number;
  connection: ConnectionState;
  info: HealthInfo | null;
  disabled: boolean;
}

export function Sidebar({ open, onClose, onNewChat, sessionId, messageCount, connection, info, disabled }: Props) {
  return (
    <>
      {open && <div className="fixed inset-0 z-20 bg-ink/30 md:hidden" onClick={onClose} aria-hidden="true" />}
      <aside
        aria-label="Sidebar"
        className={`fixed inset-y-0 left-0 z-30 flex w-72 flex-col border-r border-line bg-surface transition-transform md:static md:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between px-5 pb-3 pt-5">
          <div className="flex items-center gap-2.5">
            <span className="grid h-7 w-7 place-items-center rounded-md bg-accent font-serif text-base leading-none text-paper">L</span>
            <span className="font-serif text-xl tracking-tight">Ledger</span>
          </div>
          <button onClick={onClose} className="rounded-md p-1.5 text-ink-soft hover:bg-paper md:hidden" aria-label="Close sidebar">
            <X size={18} />
          </button>
        </div>

        <p className="px-5 text-sm leading-relaxed text-ink-soft">
          A chat assistant that shows what every answer cost: source, model, speed and tokens.
        </p>

        <div className="px-4 pt-5">
          <button
            onClick={() => {
              onNewChat();
              onClose();
            }}
            disabled={disabled}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-accent px-3 py-2.5 text-sm font-medium text-white transition-colors hover:bg-accent-ink disabled:opacity-50"
          >
            <MessageSquarePlus size={16} aria-hidden="true" /> New chat
          </button>
        </div>

        <div className="px-4 pt-6">
          <p className="px-1 pb-1.5 text-xs font-medium text-ink-faint">Current conversation</p>
          <div className="rounded-lg border border-line bg-paper/60 px-3 py-2.5" aria-current="true">
            <p className="truncate font-mono text-xs text-ink">{sessionId}</p>
            <p className="mt-0.5 text-xs text-ink-soft">
              {messageCount === 0 ? "No messages yet" : `${messageCount} message${messageCount === 1 ? "" : "s"}`}
            </p>
          </div>
        </div>

        <div className="mt-auto border-t border-line px-5 py-4 text-xs text-ink-soft">
          <div className="flex items-center gap-2">
            <StatusDot state={connection} />
            <span>{connection === "online" ? "Backend connected" : connection === "checking" ? "Connecting…" : "Backend unreachable"}</span>
          </div>
          {connection === "online" && info && (
            <p className="mt-1.5 text-ink-faint">
              {info.keys_configured} API key{info.keys_configured === 1 ? "" : "s"} · cache {info.cache_enabled ? "on" : "off"}
            </p>
          )}
        </div>
      </aside>
    </>
  );
}
