"use client";
import { useCallback, useEffect, useState } from "react";
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
  const reload = useCallback(async () => {
    if (!patientId) return;
    try { setPlan(await api<CarePlan>(`/patients/${patientId}/care-plan`)); setError(null); }
    catch (e) { setError(e instanceof ApiError ? e : null); }
  }, [patientId]);
  useEffect(() => { setPlan(null); reload(); }, [reload]);
  return { plan, error, reload };
}

// Remember which relative is selected on this device. Convenience only: the server decides access.
const KEY = "cs-patient";
export function readSelected(): string | null { try { return localStorage.getItem(KEY); } catch { return null; } }
export function writeSelected(id: string) { try { localStorage.setItem(KEY, id); } catch { /* ignore */ } }
