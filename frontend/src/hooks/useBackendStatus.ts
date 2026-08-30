import { useEffect, useRef, useState } from "react";
import { checkBackendHealth } from "@/api/repository";

export type BackendStatus = "checking" | "online" | "offline";

export function useBackendStatus(pollMs = 20_000): BackendStatus {
  const [status, setStatus] = useState<BackendStatus>("checking");
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;

    const check = async () => {
      try {
        await checkBackendHealth();
        if (mounted.current) setStatus("online");
      } catch {
        if (mounted.current) setStatus("offline");
      }
    };

    check();
    const interval = setInterval(check, pollMs);

    return () => {
      mounted.current = false;
      clearInterval(interval);
    };
  }, [pollMs]);

  return status;
}
