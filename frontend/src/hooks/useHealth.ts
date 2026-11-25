import { useEffect, useState } from "react";
import { fetchHealth } from "../services/api";
import type { ConnectionState, HealthInfo } from "../types";

export function useHealth(intervalMs = 20000) {
  const [state, setState] = useState<ConnectionState>("checking");
  const [info, setInfo] = useState<HealthInfo | null>(null);

  useEffect(() => {
    let alive = true;
    const check = async () => {
      try {
        const h = await fetchHealth();
        if (alive) {
          setInfo(h);
          setState("online");
        }
      } catch {
        if (alive) setState("offline");
      }
    };
    check();
    const t = setInterval(check, intervalMs);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [intervalMs]);

  return { state, info };
}
