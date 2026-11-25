import { Check, Copy } from "lucide-react";
import { useState } from "react";
import type { UiMessage } from "../types";

export function MessageBubble({ message }: { message: UiMessage }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end" data-testid="user-message">
        <div className="reply-text max-w-[85%] rounded-2xl rounded-br-md bg-ink px-4 py-2.5 text-[15px] leading-relaxed text-paper sm:max-w-[75%]">
          {message.content}
        </div>
      </div>
    );
  }
  return <AssistantMessage message={message} />;
}

function AssistantMessage({ message }: { message: UiMessage }) {
  const [copied, setCopied] = useState(false);
  const m = message.metadata;
  const cached = m?.resolution_source === "LLM_CACHE";

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable */
    }
  };

  return (
    <div className="flex" data-testid="assistant-message">
      <div className="max-w-[92%] sm:max-w-[80%]">
        <div className="reply-text rounded-2xl rounded-bl-md border border-line bg-surface px-4 py-3 text-[15px] leading-relaxed text-ink">
          {message.content}
        </div>
        {m && (
          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 px-1 text-xs text-ink-soft">
            <span
              data-testid="meta-source"
              className={`rounded px-1.5 py-0.5 font-mono text-[11px] ${cached ? "bg-amber-soft text-amber-ink" : "bg-accent-soft text-accent-ink"}`}
            >
              {m.resolution_source}
            </span>
            <span data-testid="meta-model" className="font-mono text-[11px]">{m.model}</span>
            <span data-testid="meta-latency">{m.latency_ms} ms</span>
            <span data-testid="meta-input-tokens">Input: {m.input_tokens} tokens</span>
            <span data-testid="meta-output-tokens">Output: {m.output_tokens} tokens</span>
            {m.fallback_attempts > 0 && (
              <span title="Keys that failed before this one answered">
                via {m.key_id} after {m.fallback_attempts} failed {m.fallback_attempts === 1 ? "key" : "keys"}
              </span>
            )}
            <button
              onClick={copy}
              className="ml-auto inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-ink-faint hover:bg-line/60 hover:text-ink"
              aria-label="Copy response"
            >
              {copied ? <Check size={13} aria-hidden="true" /> : <Copy size={13} aria-hidden="true" />}
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
