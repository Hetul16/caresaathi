"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "./api";
import type { CarePlan } from "./types";

export interface PatientRow { id: string; full_name: string; preferred_language: "en" | "hi" | "mr"; age: number | null; is_synthetic: boolean }

export function usePatients() {
  const [patients, setPatients] = useState<PatientRow[] | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const reload = useCallback(async () => {
    try { setPatients(await api<PatientRow[]>("/patients")); setError(null); }
    catch (e) { setError(e instanceof ApiError ? e : null); setPatients([]); }
  }, []);
  useEffect(() => { reload(); }, [reload]);
  return { patients, error, reload };
}

export function useCarePlan(patientId: string | null) {
  const [plan, setPlan] = useState<CarePlan | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  // Switching relative starts a new request while the old one is still in flight. Without this counter the slower
  // answer wins, and one relative's medicines are drawn under another relative's name. Drop anything that is no
  // longer the current request.
  const run = useRef(0);
  const reload = useCallback(async () => {
    if (!patientId) return;
    const mine = ++run.current;
    try {
      const got = await api<CarePlan>(`/patients/${patientId}/care-plan`);
      if (mine !== run.current) return;
      setPlan(got); setError(null);
    } catch (e) {
      if (mine !== run.current) return;
      setError(e instanceof ApiError ? e : null);
    }
  }, [patientId]);
  useEffect(() => { setPlan(null); reload(); }, [reload]);
  return { plan, error, reload };
}

// Remember which relative is selected on this device. Convenience only: the server decides access.
const KEY = "cs-patient";
export function readSelected(): string | null { try { return localStorage.getItem(KEY); } catch { return null; } }
export function writeSelected(id: string) { try { localStorage.setItem(KEY, id); } catch { /* ignore */ } }
