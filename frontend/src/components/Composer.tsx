import { ArrowUp, Loader2, SlidersHorizontal } from "lucide-react";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";

interface Props {
  onSend: (text: string) => Promise<boolean>;
  loading: boolean;
  systemPrompt: string;
  onSystemPrompt: (v: string) => void;
}

const MAX = 4000;

export function Composer({ onSend, loading, systemPrompt, onSystemPrompt }: Props) {
  const [text, setText] = useState("");
  const [showSystem, setShowSystem] = useState(false);
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [text]);

  const canSend = text.trim().length > 0 && !loading;

  const submit = async () => {
    if (!canSend) return;
    const draft = text;
    setText(""); // cleared immediately after sending
    const ok = await onSend(draft);
    if (!ok) setText((cur) => cur || draft); // restore on failure so nothing is lost
    ref.current?.focus();
  };

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      void submit();
    }
  };

  return (
    <div className="border-t border-line bg-paper/90 px-4 pb-4 pt-3 backdrop-blur">
      <div className="mx-auto max-w-3xl">
        <div className="mb-2">
          <button
            type="button"
            onClick={() => setShowSystem((s) => !s)}
            aria-expanded={showSystem}
            className="inline-flex items-center gap-1.5 rounded-md px-1.5 py-1 text-xs text-ink-soft hover:bg-line/60"
          >
            <SlidersHorizontal size={13} aria-hidden="true" />
            System prompt{systemPrompt.trim() ? " · set" : ""}
          </button>
          {/* Always mounted (hidden when collapsed) so the field is stable for tests and keeps its value. */}
          <div className={showSystem ? "mt-1.5" : "hidden"}>
            <textarea
              data-testid="system-prompt-input"
              value={systemPrompt}
              onChange={(e) => onSystemPrompt(e.target.value)}
              rows={2}
              maxLength={4000}
              placeholder="Optional. For example: You are a concise assistant that answers in plain language."
              aria-label="System prompt"
              className="w-full resize-none rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-faint"
            />
          </div>
        </div>

        <div className="flex items-end gap-2 rounded-2xl border border-line bg-surface p-2 shadow-sm focus-within:border-accent/60">
          <textarea
            ref={ref}
            data-testid="chat-input"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={onKey}
            rows={1}
            maxLength={MAX}
            disabled={loading}
            placeholder="Message Ledger…"
            aria-label="Message"
            className="max-h-[200px] min-h-[40px] flex-1 resize-none bg-transparent px-2 py-2 text-[15px] leading-relaxed text-ink placeholder:text-ink-faint focus:outline-none disabled:opacity-60"
          />
          <button
            data-testid="send-button"
            onClick={() => void submit()}
            disabled={!canSend}
            aria-label={loading ? "Sending" : "Send message"}
            className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-accent text-white transition-colors hover:bg-accent-ink disabled:bg-line disabled:text-ink-faint"
          >
            {loading ? <Loader2 size={18} className="animate-spin" aria-hidden="true" /> : <ArrowUp size={18} aria-hidden="true" />}
          </button>
        </div>
        <p className="mt-1.5 px-2 text-[11px] text-ink-faint">Enter to send · Shift+Enter for a new line</p>
      </div>
    </div>
  );
}
