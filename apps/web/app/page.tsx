"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import RupeeCoin from "@/components/RupeeCoin";
import { Wordmark } from "@/components/AppShell";
import { api } from "@/lib/api";
import { LangToggle, useLang } from "@/lib/i18n";
import { useRun } from "@/lib/run-context";

/*
 * Landing page. Short on purpose: one headline, one sentence, one action. The EN / हिंदी toggle
 * switches the whole page; a single line in the other language sits under the headline so both
 * audiences know the product speaks their language.
 *
 * Proof numbers come from the stress test (docs/stress-test.md) and the bundled demo store.
 */
const COPY = {
  en: {
    eyebrow: "Profit-leakage intelligence for kirana stores",
    h1a: "Find the rupees your shop is ",
    h1b: "quietly losing.",
    alt: "आपकी दुकान का छुपा हुआ नुकसान, सबूत के साथ।",
    lede: "Upload your sales file. Tremor finds where margin and stock slip away and shows the exact row behind every number.",
    run: "Run the sample store",
    starting: "Starting…",
    upload: "Upload my files",
    open: "Open app",
    proof: [
      ["98.5%", "recall on 50 random test stores"],
      ["98.0%", "precision on the same stores"],
      ["₹5,495", "flagged in the demo store, with proof"],
    ],
    featH: "Leads you can check in five minutes. Never accusations.",
    feats: [
      ["₹", "Stock that does not add up", "Your sales and stock CSV alone is enough to spot units that go missing.", "CSV only"],
      ["↗", "Costs eating your margin", "Add supplier bills and Tremor catches price rises you did not pass on.", "Bills optional"],
      ["✓", "Proof for every number", "Every figure links to the CSV row or bill line it came from. In English or Hindi.", "EN · हिंदी"],
    ],
    ctaH: "See it on a real-looking store",
    ctaP: "90 days of synthetic grocery data. Results in under a minute.",
    foot: "Team Three Musketeers · Hack-e-Awadh 2026",
    synthetic: "Demo numbers are synthetic",
  },
  hi: {
    eyebrow: "किराना दुकानों के लिए मुनाफ़े की जाँच",
    h1a: "आपकी दुकान का जो मुनाफ़ा ",
    h1b: "चुपचाप रिस रहा है, उसे पकड़िए।",
    alt: "Find the rupees your shop is quietly losing.",
    lede: "अपनी सेल्स फ़ाइल अपलोड करें। Tremor बताता है कि मार्जिन और स्टॉक कहाँ घट रहा है, और हर आँकड़े के पीछे की पंक्ति दिखाता है।",
    run: "सैंपल दुकान चलाएँ",
    starting: "शुरू हो रहा है…",
    upload: "अपनी फ़ाइलें अपलोड करें",
    open: "ऐप खोलें",
    proof: [
      ["98.5%", "50 रैंडम टेस्ट दुकानों पर रिकॉल"],
      ["98.0%", "उन्हीं दुकानों पर प्रिसिज़न"],
      ["₹5,495", "डेमो दुकान में सबूत के साथ पकड़ा गया"],
    ],
    featH: "ऐसे सुराग जिन्हें आप पाँच मिनट में जाँच सकें। कभी इल्ज़ाम नहीं।",
    feats: [
      ["₹", "स्टॉक जो मेल नहीं खाता", "गायब होते यूनिट पकड़ने के लिए सिर्फ़ आपकी सेल्स और स्टॉक CSV काफ़ी है।", "सिर्फ़ CSV"],
      ["↗", "मार्जिन खाती लागत", "सप्लायर के बिल जोड़ें, Tremor वो बढ़े दाम पकड़ेगा जो आपने आगे नहीं बढ़ाए।", "बिल वैकल्पिक"],
      ["✓", "हर आँकड़े का सबूत", "हर संख्या उस CSV पंक्ति या बिल लाइन से जुड़ी है जहाँ से वह आई। हिंदी या अंग्रेज़ी में।", "EN · हिंदी"],
    ],
    ctaH: "असली जैसी दुकान पर देखें",
    ctaP: "90 दिन का सिंथेटिक किराना डेटा। एक मिनट से कम में नतीजे।",
    foot: "Team Three Musketeers · Hack-e-Awadh 2026",
    synthetic: "डेमो के आँकड़े सिंथेटिक हैं",
  },
} as const;

function useReveal() {
  useEffect(() => {
    const els = Array.from(document.querySelectorAll<HTMLElement>(".reveal"));
    if (!("IntersectionObserver" in window)) {
      els.forEach((e) => e.classList.add("in"));
      return;
    }
    const io = new IntersectionObserver((entries) => entries.forEach((en) => en.isIntersecting && en.target.classList.add("in")),
      { rootMargin: "0px 0px -8% 0px" });
    els.forEach((e) => io.observe(e));
    return () => io.disconnect();
  }, []);
}

export default function Landing() {
  const router = useRouter();
  const { setRunId } = useRun();
  const { lang } = useLang();
  const c = COPY[lang];
  const other = lang === "en" ? "hi" : "en";
  const [starting, setStarting] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useReveal();

  const startDemo = async () => {
    setStarting(true);
    setErr(null);
    try {
      const r = await api.startDemo();
      setRunId(r.run_id);
      router.push(`/runs/${r.run_id}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not start the sample run");
      setStarting(false);
    }
  };

  return (
    <div className="landing">
      <nav className="l-nav" aria-label="Site">
        <div className="l-wrap l-nav-in">
          <Wordmark />
          <div className="row">
            <LangToggle compact />
            <Link className="btn btn-sm" href="/dashboard">{c.open}</Link>
          </div>
        </div>
      </nav>

      <header className="hero">
        <div className="hero-glow" />
        <div className="hero-grid" />
        <div className="l-wrap hero-in">
          <div>
            <span className="eyebrow"><i aria-hidden="true" />{c.eyebrow}</span>
            <h1>{c.h1a}<em>{c.h1b}</em></h1>
            <p className="tagline-alt" lang={other}>{c.alt}</p>
            <p className="lede">{c.lede}</p>
            <div className="hero-cta">
              <button className="btn btn-primary btn-lg" onClick={startDemo} disabled={starting}>{starting ? c.starting : c.run}</button>
              <Link className="btn btn-lg" href="/upload">{c.upload}</Link>
            </div>
            {err && <div className="alert alert-error" style={{ marginTop: 14, maxWidth: 500 }}>{err}</div>}
          </div>
          <RupeeCoin />
        </div>
      </header>

      <section className="proof" aria-label="Results">
        <div className="l-wrap proof-in">
          {c.proof.map(([n, label]) => (
            <div key={label} className="proof-item reveal"><b>{n}</b><span>{label}</span></div>
          ))}
        </div>
      </section>

      <section className="features l-wrap" aria-labelledby="feat-h">
        <h2 id="feat-h" className="reveal">{c.featH}</h2>
        <div className="feature-grid">
          {c.feats.map(([icon, h, p, tag]) => (
            <article key={h} className="feature reveal">
              <div className="feature-icon" aria-hidden="true">{icon}</div>
              <h3>{h}</h3>
              <p>{p}</p>
              <span className="tag">{tag}</span>
            </article>
          ))}
        </div>
      </section>

      <section className="cta-band l-wrap">
        <div className="cta-card reveal">
          <div>
            <h2>{c.ctaH}</h2>
            <p>{c.ctaP}</p>
          </div>
          <button className="btn btn-primary btn-lg" onClick={startDemo} disabled={starting}>{starting ? c.starting : c.run}</button>
        </div>
      </section>

      <footer className="l-wrap l-foot row between">
        <span>{c.foot}</span>
        <span>{c.synthetic}</span>
      </footer>
    </div>
  );
}
