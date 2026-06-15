// frontend/i18n.js
// Phase 5: UI-copy translations only (EN/MS/TL). Analysis OUTPUT (red flags,
// summaries, recommended actions, LLM content) stays English — translating
// AI-generated legal content would need separate LLM calls with no quality
// guarantee (Phase 6). Tagalog deliberately carries a STRONGER warning on the
// MOM-letter note: machine translation is not a legal translation.
export const translations = {
  en: {
    disclaimer: "Not legal advice and not exhaustive. A 'no red flags found' result does not guarantee a contract is fair. Singapore employment contracts (MVP scope).",
    redaction_banner_title: "Privacy Protection Active",
    redaction_banner_note: "Automated redaction is best-effort. It may not catch all identifying details. Review before relying on this for sensitive documents.",
    mom_letter_note: "Fill in the bracketed fields before sending. AI-generated — review carefully before submission.",
    privacy_link: "Privacy Policy & Terms",
  },
  ms: {
    disclaimer: "Ini bukan nasihat undang-undang dan tidak menyeluruh. Keputusan 'tiada tanda merah' tidak menjamin kontrak adalah adil. Kontrak pekerjaan Singapura (skop MVP).",
    redaction_banner_title: "Perlindungan Privasi Aktif",
    redaction_banner_note: "Pengolahan data dilakukan secara automatik. Ia mungkin tidak mengesan semua maklumat pengenalan. Semak sebelum menggunakan dokumen sensitif.",
    mom_letter_note: "Isi medan dalam kurungan sebelum menghantar. Dijana oleh AI — semak dengan teliti sebelum dikemukakan.",
    privacy_link: "Polisi Privasi & Terma",
  },
  tl: {
    disclaimer: "Hindi ito legal na payo at hindi kumprehensibo. Ang resulta na 'walang red flag' ay hindi ginagarantiyahan na patas ang kontrata. Mga kontrata sa trabaho sa Singapore (MVP scope).",
    redaction_banner_title: "Aktibo ang Proteksyon ng Privacy",
    redaction_banner_note: "Ang awtomatikong pag-redact ay pinakamahusay na pagsisikap. Maaaring hindi mahuli ang lahat ng detalyeng nagpapakilala. Suriin bago gamitin para sa sensitibong dokumento.",
    mom_letter_note: "Punan ang mga field sa loob ng bracket bago ipadala. Ginawa ng AI — suriin nang maingat bago isumite. BABALA: Ito ay isang heneralisadong pagsasalin at hindi isang legal na pagsasalin. I-verify ang lahat ng legal na sanggunian kasama ang isang kwalipikadong tagapagsalin bago isumite sa MOM.",
    privacy_link: "Patakaran sa Privacy at Mga Tuntunin",
  },
};

const DEFAULT_LANG = "en";

export function getLang() {
  const l = localStorage.getItem("cg_lang");
  return translations[l] ? l : DEFAULT_LANG;
}

export function setLang(lang) {
  if (translations[lang]) localStorage.setItem("cg_lang", lang);
}

// Translate every element carrying data-i18n="<key>". Idempotent — safe to call
// on load, on language change, and after dynamic content (re)renders.
export function applyTranslations(lang) {
  const dict = translations[lang] || translations[DEFAULT_LANG];
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    if (dict[key] != null) el.textContent = dict[key];
  });
}
