"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { Lang } from "./types";

// UI strings only. Medical content is never translated here: it comes from stored, guarded outputs.
const dict = {
  appName: { en: "CareSaathi", hi: "केयरसाथी", mr: "केअरसाथी" },
  tagline: {
    en: "Every instruction, with its source.",
    hi: "हर निर्देश, उसके स्रोत के साथ।",
    mr: "प्रत्येक सूचना, तिच्या स्रोतासह.",
  },
  elderMode: { en: "Elder mode", hi: "बुज़ुर्ग मोड", mr: "ज्येष्ठ मोड" },
  familyMode: { en: "Family mode", hi: "परिवार मोड", mr: "कुटुंब मोड" },
  hello: { en: "Namaste", hi: "नमस्ते", mr: "नमस्कार" },
  tapToSpeak: { en: "Tap and speak", hi: "दबाइए और बोलिए", mr: "दाबा आणि बोला" },
  listening: { en: "Listening…", hi: "आपकी बात सुनी जा रही है…", mr: "ऐकत आहे…" },
  speaking: { en: "Speaking…", hi: "जवाब सुनाया जा रहा है…", mr: "बोलत आहे…" },
  todayMedicines: { en: "Your medicines today", hi: "आज की आपकी दवाइयाँ", mr: "आजची तुमची औषधे" },
  listen: { en: "Listen", hi: "सुनिए", mr: "ऐका" },
  repeat: { en: "Repeat that", hi: "फिर से बोलिए", mr: "पुन्हा सांगा" },
  slower: { en: "Slower", hi: "धीरे", mr: "हळू" },
  emergency: { en: "Emergency", hi: "आपातकाल", mr: "आणीबाणी" },
  morning: { en: "Morning", hi: "सुबह", mr: "सकाळ" },
  noon: { en: "Noon", hi: "दोपहर", mr: "दुपार" },
  evening: { en: "Evening", hi: "शाम", mr: "संध्याकाळ" },
  night: { en: "Night", hi: "रात", mr: "रात्र" },
  tablet: { en: "tablet", hi: "गोली", mr: "गोळी" },
  allergies: { en: "Allergies", hi: "एलर्जी", mr: "ॲलर्जी" },
  allergyNotRecorded: { en: "Allergies not recorded", hi: "एलर्जी दर्ज नहीं है", mr: "ॲलर्जी नोंदलेली नाही" },
  allergyNone: { en: "No known allergies, per document", hi: "कोई ज्ञात एलर्जी नहीं (दस्तावेज़ के अनुसार)", mr: "ज्ञात ॲलर्जी नाही (कागदपत्रानुसार)" },
  showSource: { en: "Show source", hi: "स्रोत देखें", mr: "स्रोत पहा" },
  confirm: { en: "Confirm", hi: "पुष्टि करें", mr: "पुष्टी करा" },
  reject: { en: "Not right", hi: "सही नहीं", mr: "बरोबर नाही" },
  approve: { en: "Approve", hi: "मंज़ूर करें", mr: "मंजूर करा" },
  refuse: { en: "Decline", hi: "मना करें", mr: "नकार द्या" },
  lastUpdated: { en: "Last updated", hi: "आखिरी अपडेट", mr: "शेवटचे अपडेट" },
} as const;

export type Key = keyof typeof dict;

interface Ctx {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (k: Key) => string;
}

const LangContext = createContext<Ctx | null>(null);

export function LangProvider({ children, initial = "en" }: { children: ReactNode; initial?: Lang }) {
  const [lang, setLangState] = useState<Lang>(initial);

  useEffect(() => {
    try {
      const saved = localStorage.getItem("cs-lang") as Lang | null;
      if (saved === "en" || saved === "hi" || saved === "mr") setLangState(saved);
    } catch {
      /* storage may be unavailable */
    }
  }, []);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    document.documentElement.lang = l;
    try {
      localStorage.setItem("cs-lang", l);
    } catch {
      /* ignore */
    }
  }, []);

  const value = useMemo<Ctx>(() => ({ lang, setLang, t: (k) => dict[k][lang] }), [lang, setLang]);
  return <LangContext.Provider value={value}>{children}</LangContext.Provider>;
}

export function useI18n() {
  const c = useContext(LangContext);
  if (!c) throw new Error("useI18n must be used inside LangProvider");
  return c;
}

export const speechLocale: Record<Lang, string> = { en: "en-IN", hi: "hi-IN", mr: "mr-IN" };
