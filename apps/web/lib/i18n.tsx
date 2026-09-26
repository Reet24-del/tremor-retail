"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { SignalSummary } from "./types";

export type Lang = "en" | "hi";
const STORAGE_KEY = "tremor.lang";

/**
 * UI strings. Keys are grouped by screen. Signal text itself (title, observation and so on) is not
 * here: the API returns Hindi versions built from the same validated facts, see explain_hi.py.
 */
const en = {
  "nav.overview": "Overview",
  "nav.sources": "Data sources",
  "nav.signals": "Signals",
  "nav.reviews": "Reviews",
  "nav.home": "Home",
  "shell.tagline": "Profit leakage intelligence",
  "shell.activeStore": "Active store",
  "shell.noStore": "No store analysed yet",
  "shell.synthetic": "Synthetic demo data",
  "shell.foot": "Tremor gives investigation leads. It never changes prices, credit or stock on its own.",
  "shell.menu": "Menu",
  "shell.apiDown": "API unreachable",
  "shell.noRun": "No analysis run yet",
  "shell.analysing": "Analysing",
  "shell.failed": "Run failed",
  "shell.failedAt": "at",
  "shell.complete": "Analysis complete",
  "shell.lastRun": "Last run",
  "shell.language": "Language",

  "ov.title": "Overview",
  "ov.desc": "Tremor reads your sales and stock file (and supplier bills if you have them), finds where profit may be leaking and shows the proof for every finding. It never takes an action for you.",
  "ov.startH": "Start an analysis",
  "ov.startP": "Start with your sales and stock CSV. Supplier bills are optional: add them to also check whether rising costs are eating your margin. The sample store runs instantly with synthetic data.",
  "ov.runSample": "Run sample grocery store",
  "ov.starting": "Starting…",
  "ov.upload": "Upload my files",
  "ov.records": "Records analysed",
  "ov.recordsSub": "{p} products, {a} to {b}",
  "ov.runToSee": "Run an analysis to see this",
  "ov.invoices": "Supplier bills read",
  "ov.invoicesSub": "{n} line items · {m} extraction",
  "ov.invoicesEmpty": "PDF bills with page references",
  "ov.review": "Signals requiring review",
  "ov.reviewSub": "{n} candidates rejected with a reason",
  "ov.reviewEmpty": "Evidence-backed findings only",
  "ov.amount": "Amount requiring investigation",
  "ov.amountSub": "Estimate across open signals, not an accounting loss",
  "ov.loadingRun": "Loading latest run",
  "ov.inProgress": "Analysis in progress",
  "ov.lastFailed": "The last run failed",
  "ov.topSignals": "Top signals",
  "ov.viewAll": "View all {n}",
  "ov.noSignalsH": "No signals in the reviewed period",
  "ov.noSignalsP": "Tremor checked {r} records and {i} bills from {a} to {b}. That does not prove there is no risk.",
  "ov.noRunH": "No analysis yet",
  "ov.noRunP": "Run the sample grocery store to see a complete example in under a minute.",
  "ov.notes": "Notes from this run:",

  "bills.noBillsH": "Margin checks need supplier bills.",
  "bills.noBillsP": "Stock was checked from your sales file alone. To see whether rising supplier costs are eating into your margin, add the bills from your suppliers.",
  "bills.moreH": "Add one more supplier bill to compare costs.",
  "bills.moreP": "Tremor needs bills from at least two dates to see whether a supplier raised a price.",
  "bills.add": "Add supplier bills",
  "bills.adding": "Adding bills…",
  "bills.choosePdf": "Choose supplier bill PDFs.",

  "sig.title": "Signals",
  "sig.desc": "Ranked by severity and estimated amount. Each signal needs a number from your records and proof from a second source.",
  "sig.open": "Open",
  "sig.all": "All",
  "sig.noRunH": "No analysis yet",
  "sig.startFrom": "Start from the",
  "sig.running": "Analysis still running",
  "sig.follow": "Follow progress",
  "sig.loading": "Loading signals",
  "sig.noneOpenH": "No open signals",
  "sig.noneOpenP": "Dismissed signals are under “All”.",
  "sig.rejectedH": "Checked and not escalated",
  "sig.rejectedP": "Unusual patterns Tremor found but did not publish, with the reason.",
  "sig.rejected": "Rejected",
  "sig.noneRejected": "Nothing was rejected in this run.",

  "sev.high": "High severity",
  "sev.medium": "Medium severity",
  "sev.low": "Low severity",
  "type.margin_leakage": "Margin leakage",
  "type.inventory_discrepancy": "Inventory discrepancy",
  "status.new": "New",
  "status.unresolved": "Unresolved",
  "status.confirmed": "Confirmed for investigation",
  "status.dismissed": "Dismissed",
  "status.needs_data": "Needs data",

  "up.title": "Upload my files",
  "up.desc": "Your sales and stock CSV is enough to find stock that does not add up. Supplier bills are optional and unlock margin checks. Files are only used for this analysis; Tremor never changes your records.",
  "up.csvH": "1. Sales and stock CSV",
  "up.example": "Download example CSV",
  "up.columns": "Required columns: transaction_id, transaction_date, product_id, product_name, quantity_sold, unit_selling_price, opening_stock, closing_stock. Optional: recorded_damage, recorded_returns.",
  "up.chooseCsv": "Choose or drop a CSV",
  "up.selected": "Selected: {f}",
  "up.csvHint": "CSV, up to 10 MB",
  "up.checking": "Checking columns and rows…",
  "up.good": "Looks good.",
  "up.rowsSummary": "{r} rows · {p} products · {a} to {b} · INR",
  "up.columnsFound": "Columns:",
  "up.fix": "Fix these before continuing:",
  "up.billsH": "2. Supplier bills",
  "up.optional": "(optional)",
  "up.billsP": "Add bills to check margins. Bills from at least two dates let Tremor compare an older cost with the latest one. You can also add them later. Digital PDFs work best.",
  "up.choosePdf": "Choose or drop invoice PDFs",
  "up.pdfHint": "PDF, up to 10 MB each",
  "up.remove": "Remove",
  "up.noBills": "No bills: Tremor will check stock only and ask for bills if it needs them.",
  "up.oneBill": "One bill gives no earlier cost to compare with. Add another from a different date to check margins.",
  "up.pdfBad": "{f}: must be a PDF under 10 MB",
  "up.uploading": "Uploading…",
  "up.start": "Start analysis",
  "up.stockOnly": "Check stock now",
  "up.noAuto": "No automatic action will happen. You review every finding.",

  "det.back": "Signals",
  "det.what": "What we saw",
  "det.why": "Why it matters",
  "det.next": "Next check",
  "det.limits": "Limitations",
  "det.hiNote": "Hindi text is generated from the same checked numbers as the English text.",

  "stage.validating_records": "Validating records",
  "stage.reading_supplier_bills": "Reading supplier bills",
  "stage.matching_products": "Matching products",
  "stage.calculating_features": "Calculating financial features",
  "stage.finding_unusual_changes": "Finding unusual changes",
  "stage.linking_evidence": "Linking evidence",
  "stage.preparing_signals": "Preparing signals",
  "stage.done": "done",
  "stage.failed": "failed",
  "stage.active": "in progress",
  "stage.waiting": "waiting",
} as const;

export type Key = keyof typeof en;

const hi: Record<Key, string> = {
  "nav.overview": "डैशबोर्ड",
  "nav.sources": "डेटा स्रोत",
  "nav.signals": "संकेत",
  "nav.reviews": "समीक्षा",
  "nav.home": "होम",
  "shell.tagline": "मुनाफ़े के रिसाव की जाँच",
  "shell.activeStore": "चालू दुकान",
  "shell.noStore": "अभी कोई दुकान जाँची नहीं गई",
  "shell.synthetic": "सिंथेटिक डेमो डेटा",
  "shell.foot": "Tremor सिर्फ़ जाँच के सुराग देता है। यह खुद कभी दाम, उधार या स्टॉक नहीं बदलता।",
  "shell.menu": "मेन्यू",
  "shell.apiDown": "API से कनेक्ट नहीं हो पा रहा",
  "shell.noRun": "अभी कोई जाँच नहीं हुई",
  "shell.analysing": "जाँच चल रही है",
  "shell.failed": "जाँच रुक गई",
  "shell.failedAt": "इस चरण पर:",
  "shell.complete": "जाँच पूरी",
  "shell.lastRun": "पिछली जाँच",
  "shell.language": "भाषा",

  "ov.title": "डैशबोर्ड",
  "ov.desc": "Tremor आपकी सेल्स और स्टॉक फ़ाइल (और अगर हों तो सप्लायर के बिल) पढ़ता है, पता लगाता है कि मुनाफ़ा कहाँ रिस रहा है और हर बात का सबूत दिखाता है। यह आपकी जगह कोई कदम नहीं उठाता।",
  "ov.startH": "जाँच शुरू करें",
  "ov.startP": "अपनी सेल्स और स्टॉक CSV से शुरू करें। सप्लायर के बिल ज़रूरी नहीं हैं: उन्हें जोड़ने पर यह भी दिखेगा कि बढ़ती लागत आपका मार्जिन तो नहीं खा रही। सैंपल दुकान सिंथेटिक डेटा के साथ तुरंत चलती है।",
  "ov.runSample": "सैंपल किराना दुकान चलाएँ",
  "ov.starting": "शुरू हो रहा है…",
  "ov.upload": "अपनी फ़ाइलें अपलोड करें",
  "ov.records": "जाँचे गए रिकॉर्ड",
  "ov.recordsSub": "{p} प्रोडक्ट, {a} से {b}",
  "ov.runToSee": "यह देखने के लिए जाँच चलाएँ",
  "ov.invoices": "पढ़े गए सप्लायर बिल",
  "ov.invoicesSub": "{n} लाइन आइटम · {m} एक्सट्रैक्शन",
  "ov.invoicesEmpty": "पेज के हवाले के साथ PDF बिल",
  "ov.review": "समीक्षा वाले संकेत",
  "ov.reviewSub": "{n} संभावित मामले कारण सहित खारिज",
  "ov.reviewEmpty": "सिर्फ़ सबूत वाले नतीजे",
  "ov.amount": "जाँच लायक रकम",
  "ov.amountSub": "खुले संकेतों का अनुमान, हिसाब-किताब का असली नुकसान नहीं",
  "ov.loadingRun": "पिछली जाँच लोड हो रही है",
  "ov.inProgress": "जाँच चल रही है",
  "ov.lastFailed": "पिछली जाँच पूरी नहीं हुई",
  "ov.topSignals": "मुख्य संकेत",
  "ov.viewAll": "सभी {n} देखें",
  "ov.noSignalsH": "इस अवधि में कोई संकेत नहीं",
  "ov.noSignalsP": "Tremor ने {a} से {b} तक {r} रिकॉर्ड और {i} बिल जाँचे। इसका मतलब यह नहीं कि कोई जोखिम नहीं है।",
  "ov.noRunH": "अभी कोई जाँच नहीं",
  "ov.noRunP": "एक मिनट से कम में पूरा उदाहरण देखने के लिए सैंपल किराना दुकान चलाएँ।",
  "ov.notes": "इस जाँच के नोट्स:",

  "bills.noBillsH": "मार्जिन जाँचने के लिए सप्लायर के बिल चाहिए।",
  "bills.noBillsP": "स्टॉक सिर्फ़ आपकी सेल्स फ़ाइल से जाँचा गया। बढ़ती सप्लायर लागत मार्जिन तो नहीं खा रही, यह देखने के लिए अपने सप्लायर के बिल जोड़ें।",
  "bills.moreH": "लागत की तुलना के लिए एक और सप्लायर बिल जोड़ें।",
  "bills.moreP": "सप्लायर ने दाम बढ़ाया या नहीं, यह देखने के लिए Tremor को कम से कम दो अलग तारीखों के बिल चाहिए।",
  "bills.add": "सप्लायर बिल जोड़ें",
  "bills.adding": "बिल जोड़े जा रहे हैं…",
  "bills.choosePdf": "सप्लायर बिल की PDF चुनें।",

  "sig.title": "संकेत",
  "sig.desc": "गंभीरता और अनुमानित रकम के हिसाब से क्रम में। हर संकेत के लिए आपके रिकॉर्ड का एक आँकड़ा और दूसरे स्रोत से सबूत ज़रूरी है।",
  "sig.open": "खुले",
  "sig.all": "सभी",
  "sig.noRunH": "अभी कोई जाँच नहीं",
  "sig.startFrom": "यहाँ से शुरू करें:",
  "sig.running": "जाँच अभी चल रही है",
  "sig.follow": "प्रगति देखें",
  "sig.loading": "संकेत लोड हो रहे हैं",
  "sig.noneOpenH": "कोई खुला संकेत नहीं",
  "sig.noneOpenP": "खारिज किए गए संकेत “सभी” में हैं।",
  "sig.rejectedH": "जाँचे गए, पर आगे नहीं बढ़ाए गए",
  "sig.rejectedP": "Tremor को मिले असामान्य पैटर्न जो प्रकाशित नहीं किए गए, कारण सहित।",
  "sig.rejected": "खारिज",
  "sig.noneRejected": "इस जाँच में कुछ भी खारिज नहीं हुआ।",

  "sev.high": "ज़्यादा गंभीर",
  "sev.medium": "मध्यम गंभीर",
  "sev.low": "कम गंभीर",
  "type.margin_leakage": "मार्जिन लीकेज",
  "type.inventory_discrepancy": "स्टॉक में अंतर",
  "status.new": "नया",
  "status.unresolved": "अनसुलझा",
  "status.confirmed": "जाँच के लिए पक्का",
  "status.dismissed": "खारिज",
  "status.needs_data": "और डेटा चाहिए",

  "up.title": "अपनी फ़ाइलें अपलोड करें",
  "up.desc": "जो स्टॉक मेल नहीं खा रहा, उसे ढूँढने के लिए आपकी सेल्स और स्टॉक CSV काफ़ी है। सप्लायर बिल ज़रूरी नहीं, पर उनसे मार्जिन की जाँच भी होती है। फ़ाइलें सिर्फ़ इसी जाँच में इस्तेमाल होती हैं; Tremor आपके रिकॉर्ड कभी नहीं बदलता।",
  "up.csvH": "1. सेल्स और स्टॉक CSV",
  "up.example": "उदाहरण CSV डाउनलोड करें",
  "up.columns": "ज़रूरी कॉलम: transaction_id, transaction_date, product_id, product_name, quantity_sold, unit_selling_price, opening_stock, closing_stock. वैकल्पिक: recorded_damage, recorded_returns.",
  "up.chooseCsv": "CSV चुनें या यहाँ छोड़ें",
  "up.selected": "चुनी गई: {f}",
  "up.csvHint": "CSV, 10 MB तक",
  "up.checking": "कॉलम और पंक्तियाँ जाँची जा रही हैं…",
  "up.good": "सब ठीक है।",
  "up.rowsSummary": "{r} पंक्तियाँ · {p} प्रोडक्ट · {a} से {b} · INR",
  "up.columnsFound": "कॉलम:",
  "up.fix": "आगे बढ़ने से पहले ये ठीक करें:",
  "up.billsH": "2. सप्लायर के बिल",
  "up.optional": "(वैकल्पिक)",
  "up.billsP": "मार्जिन जाँचने के लिए बिल जोड़ें। कम से कम दो तारीखों के बिल से Tremor पुरानी और नई लागत की तुलना कर पाता है। आप इन्हें बाद में भी जोड़ सकते हैं। डिजिटल PDF सबसे अच्छे चलते हैं।",
  "up.choosePdf": "बिल की PDF चुनें या यहाँ छोड़ें",
  "up.pdfHint": "PDF, हर एक 10 MB तक",
  "up.remove": "हटाएँ",
  "up.noBills": "बिल नहीं हैं: Tremor सिर्फ़ स्टॉक जाँचेगा और ज़रूरत पड़ने पर बिल माँगेगा।",
  "up.oneBill": "एक बिल से पुरानी लागत से तुलना नहीं हो पाती। मार्जिन जाँचने के लिए किसी दूसरी तारीख का बिल जोड़ें।",
  "up.pdfBad": "{f}: 10 MB से छोटी PDF होनी चाहिए",
  "up.uploading": "अपलोड हो रहा है…",
  "up.start": "जाँच शुरू करें",
  "up.stockOnly": "अभी स्टॉक जाँचें",
  "up.noAuto": "कुछ भी अपने आप नहीं होगा। हर नतीजा आप खुद देखेंगे।",

  "det.back": "संकेत",
  "det.what": "हमने क्या देखा",
  "det.why": "यह क्यों ज़रूरी है",
  "det.next": "अगली जाँच",
  "det.limits": "सीमाएँ",
  "det.hiNote": "हिंदी टेक्स्ट उन्हीं जाँचे गए आँकड़ों से बनाया गया है जिनसे अंग्रेज़ी टेक्स्ट बना है।",

  "stage.validating_records": "रिकॉर्ड की जाँच",
  "stage.reading_supplier_bills": "सप्लायर बिल पढ़ना",
  "stage.matching_products": "प्रोडक्ट मिलाना",
  "stage.calculating_features": "वित्तीय हिसाब लगाना",
  "stage.finding_unusual_changes": "असामान्य बदलाव ढूँढना",
  "stage.linking_evidence": "सबूत जोड़ना",
  "stage.preparing_signals": "संकेत तैयार करना",
  "stage.done": "पूरा",
  "stage.failed": "रुका",
  "stage.active": "चल रहा है",
  "stage.waiting": "बाकी",
};

const DICT: Record<Lang, Record<Key, string>> = { en, hi };

export function translate(lang: Lang, key: Key, vars?: Record<string, string | number | null | undefined>): string {
  let s = DICT[lang][key] ?? en[key];
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, String(v ?? ""));
  return s;
}

type Ctx = { lang: Lang; setLang: (l: Lang) => void; t: (key: Key, vars?: Record<string, string | number | null | undefined>) => string };
const LangContext = createContext<Ctx>({ lang: "en", setLang: () => {}, t: (k, v) => translate("en", k, v) });

export function LangProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>("en");

  // Restore the saved choice after hydration; storage can be unavailable, so it is optional.
  useEffect(() => {
    const id = setTimeout(() => {
      try {
        const saved = window.localStorage.getItem(STORAGE_KEY);
        if (saved === "hi" || saved === "en") setLangState(saved);
      } catch {
        /* storage blocked: keep English */
      }
    }, 0);
    return () => clearTimeout(id);
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      window.localStorage.setItem(STORAGE_KEY, l);
    } catch {
      /* ignore */
    }
  }, []);

  const value = useMemo<Ctx>(() => ({ lang, setLang, t: (k, v) => translate(lang, k, v) }), [lang, setLang]);
  return <LangContext.Provider value={value}>{children}</LangContext.Provider>;
}

export const useLang = () => useContext(LangContext);

/** Signal text in the chosen language, falling back to English when a translation is missing. */
export function signalText<T extends Pick<SignalSummary, "title" | "observation" | "financial_impact" | "translations">>(
  s: T, lang: Lang,
) {
  const tr = lang === "en" ? undefined : s.translations?.[lang];
  return {
    title: tr?.title ?? s.title,
    observation: tr?.observation ?? s.observation,
    impactLabel: tr?.impact_label ?? s.financial_impact.label,
    translated: !!tr,
  };
}

export function LangToggle({ compact = false }: { compact?: boolean }) {
  const { lang, setLang, t } = useLang();
  return (
    <div className="seg lang-toggle" role="group" aria-label={t("shell.language")}>
      <button aria-pressed={lang === "en"} onClick={() => setLang("en")} lang="en">{compact ? "EN" : "English"}</button>
      <button aria-pressed={lang === "hi"} onClick={() => setLang("hi")} lang="hi">हिंदी</button>
    </div>
  );
}
