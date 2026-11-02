"use client";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "./api";
import type { CarePlan } from "./types";
import { afterCommit } from "./defer";

export interface PatientRow { id: string; full_name: string; preferred_language: "en" | "hi" | "mr"; age: number | null; is_synthetic: boolean }

export function usePatients() {
  const [patients, setPatients] = useState<PatientRow[] | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const reload = useCallback(async () => {
    try { setPatients(await api<PatientRow[]>("/patients")); setError(null); }
    catch (e) { setError(e instanceof ApiError ? e : null); setPatients([]); }
  }, []);
  useEffect(() => { afterCommit(reload); }, [reload]);
  return { patients, error, reload };
}

export function useCarePlan(patientId: string | null) {
  // The answer is stored together with the relative it belongs to. Switching relative starts a new request while the
  // old one is still in flight, and without this pairing the slower answer wins: one relative's medicines drawn under
  // another relative's name. A result whose id no longer matches the selection is simply never returned.
  const [res, setRes] = useState<{ id: string; plan: CarePlan | null; error: ApiError | null } | null>(null);
  const reload = useCallback(async () => {
    if (!patientId) return;
    try { setRes({ id: patientId, plan: await api<CarePlan>(`/patients/${patientId}/care-plan`), error: null }); }
    catch (e) { setRes({ id: patientId, plan: null, error: e instanceof ApiError ? e : null }); }
  }, [patientId]);
  useEffect(() => { afterCommit(reload); }, [reload]);
  const mine = res && res.id === patientId ? res : null;
  return { plan: mine?.plan ?? null, error: mine?.error ?? null, reload };
}

// Remember which relative is selected on this device. Convenience only: the server decides access.
const KEY = "cs-patient";
export function readSelected(): string | null { try { return localStorage.getItem(KEY); } catch { return null; } }
export function writeSelected(id: string) { try { localStorage.setItem(KEY, id); } catch { /* ignore */ } }

// Loading the demo family creates a patient, members and documents all at once. Every panel already on screen is
// holding the empty answers it got before any of that existed, so the app is loaded afresh rather than navigated:
// /app is the page we are already on, so a router push would change nothing.
export function reloadApp(): void {
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination -- a full load is the point, see above
  window.location.assign("/app");
}
