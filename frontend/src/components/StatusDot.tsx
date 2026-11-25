import type { ConnectionState } from "../types";

export function StatusDot({ state }: { state: ConnectionState }) {
  const color = state === "online" ? "bg-emerald-600" : state === "checking" ? "bg-amber-500" : "bg-red-600";
  return <span className={`inline-block h-2 w-2 rounded-full ${color}`} role="img" aria-label={`Connection ${state}`} />;
}
