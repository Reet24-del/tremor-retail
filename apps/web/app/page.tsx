"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import SalesDial from "@/components/SalesDial";
import { Wordmark } from "@/components/AppShell";
import { api } from "@/lib/api";
import { LangToggle, useLang } from "@/lib/i18n";
import { useRun } from "@/lib/run-context";
import ScrollRail from "@/components/ScrollRail";

/*
 * Landing page. The picture is the product's own data: the demo store's 90 days of margin, with the
 * leaks Tremor finds lit up. Copy is short and the EN / हिंदी toggle switches the whole page.
 * Proof numbers come from docs/stress-test.md and the bundled demo store.
 */
const COPY = {
  en: {
    kicker: "Tremor Retail · for small-scale retailers",
    rail: [["intro", "Intro"], ["problem", "The problem"], ["proof", "Proof"], ["signal", "What you get"], ["how", "How it works"]],
    h1: "See where your margin quietly goes.",
    lede: "Leak detection for small-scale retailers, with the exact row or bill line behind every rupee.",
    run: "Run the sample store",
    starting: "Starting…",
    upload: "Upload my files",
    open: "Open app",
    dial: {
      zones: ["Can't pay supplier", "Break-even", "Good sales"],
      steps: ["The till says it was a good week.", "Then the supplier rate went up. Stock went missing.", "Nothing left to pay the supplier."],
      punch: "Tremor shows you where it went, line by line.",
    },
    sigKicker: "What you get",
    sigH: "A lead, not a verdict.",
    sigP: "Every signal says what changed, what it may mean and what to check next. The numbers are computed, never written by the AI, and a stock gap is never called theft.",
    card: {
      sev: "High severity",
      title: "Sunpure Cooking Oil 1 L: margin leakage requires review",
      obs: "Supplier cost rose from ₹118 to ₹132 on invoice SW-184 (10 Sep) while the shelf price stayed at ₹135. Margin fell from 12.6% to 2.2%.",
      next: "Next: verify the latest rate with Shakti Wholesale and recount 12 units.",
      amt: "₹1,680",
      amtLabel: "estimated margin leakage",
      ev: ["Invoice SW-184, page 1", "Sales rows since 10 Sep", "Stock count, 18 Sep"],
    },
    howH: "How it works",
    how: [
      ["Upload", "A sales and stock CSV is enough. Supplier PDFs are optional and unlock margin checks."],
      ["Match", "Bill lines are matched to your products by name and pack size. Unsure matches wait for you."],
      ["Check", "Unusual changes are ranked by rupees at stake, then tested against festivals, bulk orders and price changes."],
      ["Review", "You confirm or dismiss each lead. Tremor never changes a price, a credit limit or your stock."],
    ],
    proof: "We tested Tremor on 50 stores it had never seen. It found 98.5% of the hidden leaks, and 98% of what it flagged was real.",
    proofLink: "Read how we tested",
    foot: "Team Three Musketeers · Hack-e-Awadh 2026 · demo data is synthetic",
  },
  hi: {
    kicker: "Tremor Retail · छोटे खुदरा व्यापारियों के लिए",
    rail: [["intro", "शुरुआत"], ["problem", "समस्या"], ["proof", "सबूत"], ["signal", "आपको क्या मिलता है"], ["how", "कैसे काम करता है"]],
    h1: "देखिए आपका मार्जिन चुपचाप कहाँ जा रहा है।",
    lede: "छोटे खुदरा व्यापारियों के लिए रिसाव की जाँच, हर रुपये के पीछे की पंक्ति या बिल लाइन के साथ।",
    run: "सैंपल दुकान चलाएँ",
    starting: "शुरू हो रहा है…",
    upload: "अपनी फ़ाइलें अपलोड करें",
    open: "ऐप खोलें",
    dial: {
      zones: ["सप्लायर का पैसा नहीं", "बराबर", "अच्छी बिक्री"],
      steps: ["गल्ला कहता है हफ़्ता अच्छा गया।", "फिर सप्लायर का रेट बढ़ा। स्टॉक गायब हुआ।", "सप्लायर को देने के लिए कुछ नहीं बचा।"],
      punch: "Tremor दिखाता है कि पैसा कहाँ गया, लाइन दर लाइन।",
    },
    sigKicker: "आपको क्या मिलता है",
    sigH: "एक सुराग, फ़ैसला नहीं।",
    sigP: "हर संकेत बताता है कि क्या बदला, इसका क्या मतलब हो सकता है और आगे क्या जाँचना है। आँकड़े गणना से आते हैं, AI उन्हें नहीं लिखता, और स्टॉक के अंतर को कभी चोरी नहीं कहा जाता।",
    card: {
      sev: "ज़्यादा गंभीर",
      title: "Sunpure Cooking Oil 1 L: मार्जिन लीकेज की जाँच ज़रूरी",
      obs: "बिल SW-184 (10 Sep) पर सप्लायर की लागत ₹118 से ₹132 हो गई, जबकि दाम ₹135 ही रहा। मार्जिन 12.6% से घटकर 2.2% रह गया।",
      next: "अगला कदम: Shakti Wholesale से नया रेट पक्का करें और 12 यूनिट दोबारा गिनें।",
      amt: "₹1,680",
      amtLabel: "अनुमानित मार्जिन लीकेज",
      ev: ["बिल SW-184, पेज 1", "10 Sep से बिक्री की पंक्तियाँ", "18 Sep की स्टॉक गिनती"],
    },
    howH: "कैसे काम करता है",
    how: [
      ["अपलोड", "सेल्स और स्टॉक CSV काफ़ी है। सप्लायर की PDF वैकल्पिक हैं, उनसे मार्जिन की जाँच होती है।"],
      ["मिलान", "बिल की लाइनें नाम और पैक साइज़ से आपके प्रोडक्ट से मिलाई जाती हैं। शक वाले मिलान आपके पास आते हैं।"],
      ["जाँच", "असामान्य बदलाव दाँव पर लगे रुपयों से क्रम में आते हैं, फिर त्योहार, थोक ऑर्डर और दाम बदलाव से परखे जाते हैं।"],
      ["समीक्षा", "हर सुराग को आप पक्का या खारिज करते हैं। Tremor कभी दाम, उधार या स्टॉक नहीं बदलता।"],
    ],
    proof: "हमने Tremor को 50 ऐसी दुकानों पर परखा जिन्हें इसने पहले नहीं देखा था। इसने 98.5% छुपे रिसाव पकड़े, और जो पकड़ा उसमें 98% सही निकला।",
    proofLink: "हमने कैसे परखा",
    foot: "Team Three Musketeers · Hack-e-Awadh 2026 · डेमो डेटा सिंथेटिक है",
  },
} as const;

/** A sentence whose words brighten one by one as it scrolls through the viewport. */
function RevealText({ text }: { text: string }) {
  const ref = useRef<HTMLParagraphElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const words = Array.from(el.querySelectorAll<HTMLElement>(".w"));
    const onScroll = () => {
      const r = el.getBoundingClientRect();
      const vh = window.innerHeight;
      const progress = Math.min(1, Math.max(0, (vh * 0.85 - r.top) / (r.height + vh * 0.35)));
      const lit = Math.round(progress * words.length);
      words.forEach((w, i) => w.classList.toggle("on", i < lit));
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [text]);
  return (
    <p ref={ref}>
      {text.split(" ").map((w, i) => <span key={i} className="w">{w} </span>)}
    </p>
  );
}

const STRESS_DOC = "https://github.com/Reet24-del/tremor-retail/blob/main/docs/stress-test.md";

export default function Landing() {
  const router = useRouter();
  const { setRunId } = useRun();
  const { lang } = useLang();
  const c = COPY[lang];
  const [starting, setStarting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

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
            <Link className="l-open" href="/dashboard">{c.open} →</Link>
          </div>
        </div>
        <ScrollRail steps={c.rail} />
      </nav>

      <header className="l-wrap hero" id="intro">
        <p className="kicker">{c.kicker}</p>
        <h1>{c.h1}</h1>
        <p className="lede">{c.lede}</p>
        <div className="hero-cta">
          <button className="btn btn-primary btn-lg" onClick={startDemo} disabled={starting}>{starting ? c.starting : c.run}</button>
          <Link className="text-link" href="/upload">{c.upload} →</Link>
        </div>
        {err && <div className="alert alert-error" style={{ marginTop: 14, maxWidth: 520, marginInline: "auto" }}>{err}</div>}
      </header>

      <div className="l-wrap l-anchor" id="problem">
        <SalesDial copy={c.dial} />
      </div>

      <section className="l-wrap statement l-anchor" id="proof" aria-label="Results">
        <RevealText text={c.proof} />
        <a href={STRESS_DOC} target="_blank" rel="noreferrer">{c.proofLink} ↗</a>
      </section>

      <section className="l-wrap l-section sig-section l-anchor" id="signal" aria-labelledby="sig-h">
        <div>
          <p className="kicker">{c.sigKicker}</p>
          <h2 id="sig-h">{c.sigH}</h2>
          <p className="l-body">{c.sigP}</p>
        </div>
        <article className="demo-card" aria-label="Example signal">
          <div className="row between">
            <span className="badge badge-high">▲ {c.card.sev}</span>
            <span className="demo-amt">{c.card.amt}<small>{c.card.amtLabel}</small></span>
          </div>
          <h3>{c.card.title}</h3>
          <p>{c.card.obs}</p>
          <p className="demo-next">{c.card.next}</p>
          <ul className="demo-ev">
            <li><span className="src src-pdf">PDF</span>{c.card.ev[0]}</li>
            <li><span className="src src-csv">CSV</span>{c.card.ev[1]}</li>
            <li><span className="src src-csv">CSV</span>{c.card.ev[2]}</li>
          </ul>
        </article>
      </section>

      <section className="l-wrap l-section l-anchor" id="how" aria-labelledby="how-h">
        <h2 id="how-h">{c.howH}</h2>
        <ol className="how">
          {c.how.map(([h, p], i) => (
            <li key={h}><span className="how-n">0{i + 1}</span><strong>{h}</strong><p>{p}</p></li>
          ))}
        </ol>
      </section>

      <footer className="l-wrap l-foot">{c.foot}</footer>
    </div>
  );
}
