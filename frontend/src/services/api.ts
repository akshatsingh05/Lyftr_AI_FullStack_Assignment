import type { ChatResponse, HealthInfo } from "../types";

// Never hardcode a deployed URL: it comes from the build-time env var.
const BASE = ((import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000").replace(/\/+$/, "");

export class ApiError extends Error {
  constructor(message: string, public status?: number) {
    super(message);
  }
}

function describeDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        const field = Array.isArray(d?.loc) ? d.loc.filter((p: string) => p !== "body").join(".") : "";
        return field ? `${field}: ${d?.msg ?? "invalid"}` : String(d?.msg ?? "invalid");
      })
      .join("; ");
  }
  return "Unexpected error";
}

export async function sendChat(sessionId: string, message: string, systemPrompt: string): Promise<ChatResponse> {
  let res: Response;
  try {
    res = await fetch(`${BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId,
        message,
        ...(systemPrompt.trim() ? { system_prompt: systemPrompt.trim() } : {}),
      }),
    });
  } catch {
    throw new ApiError("Can't reach the server. Check your connection and that the backend is running.");
  }

  if (res.ok) return (await res.json()) as ChatResponse;

  let detail: unknown;
  try {
    detail = (await res.json()).detail;
  } catch {
    /* non-JSON error body */
  }
  if (res.status === 422) throw new ApiError(`Your message couldn't be sent. ${describeDetail(detail)}`, 422);
  if (res.status === 503) throw new ApiError("All AI providers are unavailable right now. Please try again in a moment.", 503);
  if (res.status === 502) throw new ApiError("The AI provider rejected this request. Try rephrasing your message.", 502);
  throw new ApiError(`Something went wrong (HTTP ${res.status}). ${detail ? describeDetail(detail) : ""}`.trim(), res.status);
}

export async function fetchHealth(): Promise<HealthInfo> {
  const res = await fetch(`${BASE}/health`);
  if (!res.ok) throw new ApiError("unhealthy", res.status);
  return (await res.json()) as HealthInfo;
}
