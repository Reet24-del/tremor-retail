"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { api, ApiError } from "./api";
import type { RunStatus } from "./types";

interface RunCtx {
  runId: string | null;
  run: RunStatus | null;
  loading: boolean;
  apiError: string | null;
  setRunId: (id: string) => void;
  refresh: () => Promise<void>;
}

const Ctx = createContext<RunCtx | null>(null);
const KEY = "tremor.runId";

export function RunProvider({ children }: { children: React.ReactNode }) {
  const [requestedId, setRequestedId] = useState<string | null>(null);
  const [run, setRun] = useState<RunStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const loadRef = useRef<(id: string) => Promise<void>>(async () => undefined);

  const load = useCallback(async (id: string) => {
    try {
      const r = await api.run(id);
      setRun(r);
      setApiError(null);
      if (r.status === "running") {
        timer.current = setTimeout(() => loadRef.current(id), 700);
      }
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        setRun(null);
        setRequestedId(null);
        try { localStorage.removeItem(KEY); } catch { /* storage unavailable */ }
      } else {
        setApiError(e instanceof Error ? e.message : "Unknown error");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadRef.current = load;
  }, [load]);

  useEffect(() => {
    let stored: string | null = null;
    try { stored = localStorage.getItem(KEY); } catch { /* storage unavailable */ }
    const id = stored || "latest";
    timer.current = setTimeout(() => load(id), 0); // subscribe to external run state outside the render pass
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, [load]);

  const runId = run?.run_id ?? requestedId;

  const setRunId = useCallback((id: string) => {
    if (timer.current) clearTimeout(timer.current);
    setRequestedId(id);
    try { localStorage.setItem(KEY, id); } catch { /* storage unavailable */ }
    setLoading(true);
    load(id);
  }, [load]);

  const refresh = useCallback(async () => {
    if (runId) await load(runId);
  }, [runId, load]);

  return <Ctx.Provider value={{ runId, run, loading, apiError, setRunId, refresh }}>{children}</Ctx.Provider>;
}

export function useRun() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useRun must be inside RunProvider");
  return c;
}
