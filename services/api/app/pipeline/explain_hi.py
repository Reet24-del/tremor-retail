"""Hindi signal text (हिंदी).

Built from the same validated facts as the English template, never from the LLM, so every number a
shop owner reads in Hindi is the exact number the detector computed. The Hindi text goes through
the same number and prohibited-language checks as the English text before it is published.
"""

from __future__ import annotations

from .explain import THIN_MARGIN_PERCENT, check_text


def _inr(x: float) -> str:
    x = float(x)
    return f"₹{x:,.0f}" if x.is_integer() else f"₹{x:,.2f}"


def _pct(x: float) -> str:
    return f"{x:.1f} प्रतिशत"


def _join(parts: list[str]) -> str:
    if len(parts) == 1:
        return parts[0] + "।"
    return ", ".join(parts[:-1]) + " और " + parts[-1] + "।"


def template_text_hi(signal_type: str, facts: dict) -> dict:
    name = facts["product"]
    if signal_type == "margin_leakage":
        after = facts["average_selling_price_after"]
        obs = (
            f"बिल {facts['latest_invoice']} ({facts['latest_invoice_date']}) पर सप्लायर की लागत "
            f"{_inr(facts['prior_unit_cost'])} से बढ़कर {_inr(facts['latest_unit_cost'])} हो गई, जबकि औसत बिक्री मूल्य "
            + (f"उसके बाद {_inr(after)} रहा।" if facts["price_changes_after_cost_change"] else f"लगभग {_inr(after)} पर ही रहा।")
            + f" सकल मार्जिन {_pct(facts['prior_margin_percent'])} से घटकर {_pct(facts['current_margin_percent'])} रह गया।"
        )
        if facts["current_margin_percent"] < THIN_MARGIN_PERCENT:
            interp = "अब यह प्रोडक्ट शायद इतने कम मार्जिन पर बिक रहा है कि दुकान के बाकी खर्च इससे नहीं निकल पाएँगे।"
        else:
            interp = (
                "इस प्रोडक्ट का मार्जिन घट रहा है। मार्जिन अभी भी पॉज़िटिव है, लेकिन सप्लायर की लागत बढ़ने के बाद "
                "हर यूनिट पर पहले से कम कमाई हो रही है।"
            )
        if facts["price_changes_after_cost_change"]:
            d, p = facts["price_changes_after_cost_change"][-1]
            interp += (
                f" {d} को बिक्री मूल्य बढ़ाकर {_inr(p)} किया गया, जिससे बढ़ी हुई लागत का कुछ हिस्सा वापस आता है, "
                "लेकिन सिर्फ़ पिछले कुछ दिनों के लिए।"
            )
        checks = [f"{facts['supplier']} से नया सप्लायर रेट पक्का करें"]
        if abs(facts.get("stock_variance_units") or 0) >= 1:
            n = abs(int(facts["stock_variance_units"]))
            interp += f" {n} यूनिट का स्टॉक अंतर भी मिला, जिससे नुकसान और बढ़ सकता है। इससे यह पता नहीं चलता कि यूनिट क्यों कम हैं।"
            checks.append(f"{n} यूनिट के स्टॉक अंतर की दोबारा गिनती करें")
        checks.append("देखें कि बिक्री मूल्य अपडेट करना चाहिए या नहीं")
        return {
            "title": f"{name}: मार्जिन लीकेज की जाँच ज़रूरी",
            "observation": obs,
            "interpretation": interp,
            "next_check": _join(checks),
        }
    n = abs(int(facts["stock_variance_units"]))
    return {
        "title": f"{name}: स्टॉक का हिसाब मेल नहीं खा रहा",
        "observation": (
            f"अनुमानित क्लोज़िंग स्टॉक {facts['expected_closing_stock']:g} यूनिट है, लेकिन गिना गया क्लोज़िंग स्टॉक "
            f"{facts['actual_closing_stock']:g} यूनिट है। रिकॉर्ड में {n} यूनिट का अंतर है, जो पहली बार "
            f"{facts['discrepancy_dates'][0]} को दिखा।"
        ),
        "interpretation": (
            "यह बिना दर्ज हुई बिक्री, खराब हुआ स्टॉक जो लिखा नहीं गया या गिनती की गलती हो सकती है। "
            "यह रिकॉर्ड का मेल न खाना है जिसे जाँचना है, किसी की गलती का सबूत नहीं।"
        ),
        "next_check": _join([f"{name} को शेल्फ़ और गोदाम में दोबारा गिनें", "देखें कि उस दिन कोई बिक्री या नुकसान दर्ज होने से रह तो नहीं गया"]),
    }


LIMITATIONS_HI = {
    "Synthetic demo data": "सिंथेटिक डेमो डेटा",
    "Based only on the uploaded files": "सिर्फ़ अपलोड की गई फ़ाइलों पर आधारित",
    "Excludes tax, delivery charges, rebates and damaged stock unless recorded in the files": (
        "टैक्स, डिलीवरी चार्ज, छूट और खराब स्टॉक शामिल नहीं हैं, जब तक वे फ़ाइलों में दर्ज न हों"
    ),
    "Estimated amounts compare with the prior purchase cost; they are not an accounting loss": (
        "अनुमानित रकम पिछली खरीद लागत से तुलना है; यह हिसाब-किताब का असली नुकसान नहीं है"
    ),
    "Invoice fields come from cached validated extraction (verified against the PDF text)": (
        "बिल की जानकारी पहले से जाँचे गए एक्सट्रैक्शन से ली गई है (PDF टेक्स्ट से मिलाई गई)"
    ),
    "Checked from the sales and stock file alone: deliveries were inferred from stock increases. "
    "Add this supplier's bills to confirm.": (
        "सिर्फ़ सेल्स और स्टॉक फ़ाइल से जाँचा गया: स्टॉक बढ़ने से डिलीवरी का अंदाज़ा लगाया गया। पक्का करने के लिए इस सप्लायर के बिल जोड़ें।"
    ),
}

IMPACT_LABEL_HI = {
    "estimated margin leakage": "अनुमानित मार्जिन लीकेज",
    "estimated stock value not reconciled": "मेल न खाने वाले स्टॉक की अनुमानित कीमत",
}


def translate_hi(signal_type: str, facts: dict, limitations: list[str], impact_label: str) -> tuple[dict | None, list[str]]:
    """Returns (hindi_text or None, problems). Hindi is dropped, never published unchecked."""
    text = template_text_hi(signal_type, facts)
    problems = check_text(text, facts)
    if problems:
        return None, [f"Hindi wording rejected: {p}" for p in problems]
    return {
        **text,
        "limitations": [LIMITATIONS_HI.get(x, x) for x in limitations],
        "impact_label": IMPACT_LABEL_HI.get(impact_label, impact_label),
    }, []
