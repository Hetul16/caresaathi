import type { Lang, PlanItem } from "./types";

const slotWord: Record<Lang, Record<"morning" | "noon" | "evening" | "night", string>> = {
  en: { morning: "in the morning", noon: "at noon", evening: "in the evening", night: "at night" },
  hi: { morning: "सुबह", noon: "दोपहर में", evening: "शाम को", night: "रात को" },
  mr: { morning: "सकाळी", noon: "दुपारी", evening: "संध्याकाळी", night: "रात्री" },
};
const unit: Record<Lang, string> = { en: "tablet", hi: "गोली", mr: "गोळी" };
const waiting: Record<Lang, string> = {
  en: "This one is waiting for your family to confirm.",
  hi: "इसकी पुष्टि के लिए आपके परिवार का इंतज़ार है।",
  mr: "याच्या पुष्टीसाठी तुमच्या कुटुंबाची प्रतीक्षा आहे.",
};
const written: Record<Lang, string> = {
  en: "As written by your doctor.",
  hi: "जैसा आपके डॉक्टर ने लिखा है।",
  mr: "तुमच्या डॉक्टरांनी लिहिल्याप्रमाणे.",
};

// Spoken text is assembled by code from stored fields, so the voice can never add a claim of its own.
export function spokenDose(item: PlanItem, lang: Lang): string {
  const parts: string[] = [item.title];
  if (item.schedule) {
    for (const slot of ["morning", "noon", "evening", "night"] as const) {
      const n = item.schedule[slot];
      if (n) parts.push(`${slotWord[lang][slot]} ${n} ${unit[lang]}`);
    }
  } else if (item.detail) {
    parts.push(item.detail);
  }
  parts.push(item.confirmed ? written[lang] : waiting[lang]);
  return parts.join(". ");
}
