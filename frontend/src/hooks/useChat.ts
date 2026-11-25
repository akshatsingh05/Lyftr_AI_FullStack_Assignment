import { useCallback, useRef, useState } from "react";
import { sendChat } from "../services/api";
import type { UiMessage } from "../types";
import { newSessionId, uid } from "../utils/session";

export function useChat() {
  const [sessionId, setSessionId] = useState(newSessionId); // new id on every page load
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [systemPrompt, setSystemPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inFlight = useRef(false); // guards against duplicate submissions (double Enter / click)

  /** Resolves to true when the message was accepted, false when it failed (caller restores the draft). */
  const send = useCallback(
    async (text: string): Promise<boolean> => {
      const message = text.trim();
      if (!message || inFlight.current) return false;
      inFlight.current = true;
      setLoading(true);
      setError(null);
      const userMsg: UiMessage = { id: uid(), role: "user", content: message };
      setMessages((m) => [...m, userMsg]);
      try {
        const res = await sendChat(sessionId, message, systemPrompt);
        setMessages((m) => [...m, { id: uid(), role: "assistant", content: res.reply, metadata: res.metadata }]);
        return true;
      } catch (e) {
        // The backend stores nothing on failure, so mirror that: drop the optimistic message.
        setMessages((m) => m.filter((x) => x.id !== userMsg.id));
        setError(e instanceof Error ? e.message : "Something went wrong.");
        return false;
      } finally {
        inFlight.current = false;
        setLoading(false);
      }
    },
    [sessionId, systemPrompt],
  );

  const newChat = useCallback(() => {
    if (inFlight.current) return;
    setSessionId(newSessionId());
    setMessages([]);
    setError(null);
  }, []);

  return { sessionId, messages, systemPrompt, setSystemPrompt, loading, error, dismissError: () => setError(null), send, newChat };
}
