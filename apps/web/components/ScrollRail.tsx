"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Reading-progress rail under the landing nav: one point per section, evenly spaced, with a
 * coloured line that fills as the visitor scrolls. Points are links to their sections.
 */
export default function ScrollRail({ steps }: { steps: readonly (readonly [string, string])[] }) {
  const fill = useRef<HTMLDivElement>(null);
  const [reached, setReached] = useState(0);

  useEffect(() => {
    let raf = 0;
    const update = () => {
      raf = 0;
      const els = steps.map(([id]) => document.getElementById(id));
      const mid = window.scrollY + window.innerHeight * 0.4;
      const tops = els.map((el) => (el ? el.getBoundingClientRect().top + window.scrollY : Infinity));
      // Progress between the section we are in and the next one, mapped onto evenly spaced points.
      let i = 0;
      while (i < tops.length - 1 && mid >= tops[i + 1]) i++;
      const atEnd = window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4;
      const span = (tops[i + 1] ?? tops[i] + 1) - tops[i];
      const within = i >= tops.length - 1 ? 0 : Math.min(1, Math.max(0, (mid - tops[i]) / span));
      const progress = atEnd ? 1 : (i + within) / (steps.length - 1);
      if (fill.current) fill.current.style.transform = `scaleX(${progress})`;
      setReached(atEnd ? steps.length - 1 : i);
    };
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (raf) cancelAnimationFrame(raf);
    };
  }, [steps]);

  return (
    <nav className="rail" aria-label="Page sections">
      <div className="rail-in">
        <div className="rail-track" aria-hidden="true"><div className="rail-fill" ref={fill} /></div>
        <ol>
          {steps.map(([id, label], i) => (
            <li key={id} className={i <= reached ? "on" : ""} style={{ left: `${(i / (steps.length - 1)) * 100}%` }}>
              <a href={`#${id}`} aria-current={i === reached ? "step" : undefined}>
                <span className="rail-dot" />
                <span className="rail-label">{label}</span>
              </a>
            </li>
          ))}
        </ol>
      </div>
    </nav>
  );
}
