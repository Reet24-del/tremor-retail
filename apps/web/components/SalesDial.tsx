"use client";

import { useEffect, useRef, useState } from "react";

export type DialCopy = {
  zones: readonly [string, string, string]; // left to right: can't pay, break-even, good sales
  steps: readonly [string, string, string]; // rising, falling, landed
  punch: string;
};

type Phase = 0 | 1 | 2;

/**
 * Landing 3D: a shop's money dial. The needle swings up to "good sales", shudders, then falls back
 * to "nothing left for the supplier": busy tills, thin margins. Illustrative, no numbers claimed.
 * three.js loads on the client only; reduced-motion visitors get the final frame.
 */
export default function SalesDial({ copy }: { copy: DialCopy }) {
  const host = useRef<HTMLDivElement>(null);
  const [phase, setPhase] = useState<Phase>(0);
  const [failed, setFailed] = useState(false);
  const zonesKey = copy.zones.join("|");

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    let disposed = false;
    let cleanup = () => {};
    const zones = zonesKey.split("|");

    (async () => {
      try {
        const THREE = await import("three");
        const { RoomEnvironment } = await import("three/examples/jsm/environments/RoomEnvironment.js");
        if (disposed) return;
        const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

        const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        renderer.outputColorSpace = THREE.SRGBColorSpace;
        el.appendChild(renderer.domElement);
        const scene = new THREE.Scene();
        const pmrem = new THREE.PMREMGenerator(renderer);
        const env = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
        scene.environment = env;
        const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 100);
        camera.position.set(0, 0.2, 11.5);

        // ---- Dial face drawn on a canvas: three zones, ticks and labels ----
        const SWEEP = (240 * Math.PI) / 180; // needle travel
        const START = Math.PI / 2 + SWEEP / 2; // left end, measured from +x counter-clockwise
        const faceCanvas = document.createElement("canvas");
        faceCanvas.width = faceCanvas.height = 1024;
        const g = faceCanvas.getContext("2d")!;
        const cx = 512, cy = 512;
        const ang = (v: number) => -(START - v * SWEEP); // canvas y points down, so flip
        g.fillStyle = "#fbf9f5";
        g.fillRect(0, 0, 1024, 1024);
        const band = (from: number, to: number, color: string) => {
          g.beginPath();
          g.strokeStyle = color;
          g.lineWidth = 58;
          g.arc(cx, cy, 390, ang(from), ang(to));
          g.stroke();
        };
        band(0, 0.3, "#b8664b");
        band(0.3, 0.6, "#d8c297");
        band(0.6, 1, "#5f8f71");
        for (let i = 0; i <= 40; i++) {
          const v = i / 40;
          const a = ang(v);
          const major = i % 5 === 0;
          const r1 = major ? 318 : 334;
          g.strokeStyle = "#1f2328";
          g.lineWidth = major ? 6 : 3;
          g.beginPath();
          g.moveTo(cx + Math.cos(a) * r1, cy + Math.sin(a) * r1);
          g.lineTo(cx + Math.cos(a) * 352, cy + Math.sin(a) * 352);
          g.stroke();
        }
        g.fillStyle = "#1f2328";
        g.textAlign = "center";
        g.textBaseline = "middle";
        g.font = "600 38px 'IBM Plex Sans', 'IBM Plex Sans Devanagari', 'Noto Sans Devanagari', sans-serif";
        // Zone labels sit below the needle's sweep so the needle never crosses them.
        ([[330, 640], [512, 300], [694, 640]] as const).forEach(([x, y], i) => {
          const words = zones[i].split(" ");
          const lines = words.length > 2 ? [words.slice(0, Math.ceil(words.length / 2)).join(" "), words.slice(Math.ceil(words.length / 2)).join(" ")] : [zones[i]];
          lines.forEach((ln, k) => g.fillText(ln, x, y + (k - (lines.length - 1) / 2) * 44));
        });
        g.font = "400 92px Newsreader, Georgia, serif";
        g.fillStyle = "#b8664b";
        g.fillText("₹", cx, cy + 250);
        const faceTex = new THREE.CanvasTexture(faceCanvas);
        faceTex.colorSpace = THREE.SRGBColorSpace;
        faceTex.anisotropy = 8;

        const dial = new THREE.Group();
        const R = 2.3;
        const face = new THREE.Mesh(new THREE.CircleGeometry(R, 128),
          new THREE.MeshBasicMaterial({ map: faceTex }));
        face.position.z = 0.1;
        const bodyGeo = new THREE.CylinderGeometry(R + 0.12, R + 0.22, 0.3, 128, 1);
        bodyGeo.rotateX(Math.PI / 2);
        const body = new THREE.Mesh(bodyGeo, new THREE.MeshStandardMaterial({ color: "#e7dfd1", roughness: 0.5, metalness: 0.1 }));
        body.position.z = -0.06;
        const bezelGeo = new THREE.TorusGeometry(R + 0.06, 0.09, 24, 160);
        const bezel = new THREE.Mesh(bezelGeo, new THREE.MeshStandardMaterial({ color: "#b98b62", roughness: 0.28, metalness: 0.9 }));
        bezel.position.z = 0.12;
        dial.add(body, face, bezel);

        // Needle: pivot at the centre, pointing along +y at value 0.5.
        const needle = new THREE.Group();
        const bladeGeo = new THREE.CylinderGeometry(0.018, 0.07, 2.05, 16);
        bladeGeo.translate(0, 0.78, 0);
        const blade = new THREE.Mesh(bladeGeo, new THREE.MeshStandardMaterial({ color: "#1f2328", roughness: 0.4, metalness: 0.3 }));
        const capGeo = new THREE.CylinderGeometry(0.2, 0.2, 0.16, 48);
        capGeo.rotateX(Math.PI / 2);
        const cap = new THREE.Mesh(capGeo, new THREE.MeshStandardMaterial({ color: "#b8664b", roughness: 0.55, metalness: 0.15 }));
        needle.add(blade, cap);
        needle.position.z = 0.22;
        dial.add(needle);

        // Soft contact shadow.
        const shadowCanvas = document.createElement("canvas");
        shadowCanvas.width = shadowCanvas.height = 128;
        const sg = shadowCanvas.getContext("2d")!;
        const grad = sg.createRadialGradient(64, 64, 0, 64, 64, 64);
        grad.addColorStop(0, "rgba(60,40,20,0.28)");
        grad.addColorStop(1, "rgba(60,40,20,0)");
        sg.fillStyle = grad;
        sg.fillRect(0, 0, 128, 128);
        const shadowTex = new THREE.CanvasTexture(shadowCanvas);
        const shadow = new THREE.Mesh(new THREE.PlaneGeometry(6.4, 1.6),
          new THREE.MeshBasicMaterial({ map: shadowTex, transparent: true, depthWrite: false }));
        shadow.rotation.x = -Math.PI / 2;
        shadow.position.set(0, -2.75, 0);
        scene.add(shadow);

        dial.rotation.x = -0.12;
        scene.add(dial);
        scene.add(new THREE.AmbientLight("#fff3e4", 0.35));
        const key = new THREE.DirectionalLight("#fff1dc", 2.4);
        key.position.set(-3, 4, 6);
        scene.add(key);

        const resize = () => {
          const w = el.clientWidth || 1;
          const h = el.clientHeight || 1;
          renderer.setSize(w, h, false);
          camera.aspect = w / h;
          camera.position.z = w < 600 ? 14 : 11.5;
          camera.updateProjectionMatrix();
        };
        resize();
        const ro = new ResizeObserver(resize);
        ro.observe(el);

        const pointer = { x: 0, y: 0 };
        const onMove = (e: PointerEvent) => {
          const r = el.getBoundingClientRect();
          pointer.x = (e.clientX - r.left) / r.width - 0.5;
          pointer.y = (e.clientY - r.top) / r.height - 0.5;
        };
        window.addEventListener("pointermove", onMove, { passive: true });

        // Value 0..1 over an 8 s loop: rise with overshoot, hold and shudder, fall, bounce, rest.
        const easeOutBack = (t: number) => 1 + 2.2 * Math.pow(t - 1, 3) + 1.2 * Math.pow(t - 1, 2);
        const valueAt = (t: number) => {
          if (t < 2.0) return 0.06 + 0.86 * easeOutBack(t / 2.0);
          if (t < 3.2) return 0.92 + Math.sin(t * 40) * 0.004;
          if (t < 3.9) return 0.92 + Math.sin(t * 70) * 0.02 * ((t - 3.2) / 0.7); // the tremor
          if (t < 4.9) { const k = (t - 3.9) / 1.0; return 0.92 - 0.86 * k * k; }
          if (t < 5.5) { const k = (t - 4.9) / 0.6; return 0.06 + Math.sin(k * Math.PI) * 0.05 * (1 - k); }
          return 0.06;
        };
        const phaseAt = (t: number): Phase => (t < 3.2 ? 0 : t < 4.9 ? 1 : 2);
        const setNeedle = (v: number) => { needle.rotation.z = SWEEP / 2 - v * SWEEP; };

        let raf = 0;
        let last: Phase = 0;
        const clock = new THREE.Clock();
        const LOOP = 8.5;
        const frame = () => {
          const t = clock.getElapsedTime() % LOOP;
          setNeedle(valueAt(t));
          const p = phaseAt(t);
          if (p !== last) {
            last = p;
            setPhase(p);
          }
          dial.rotation.y += (pointer.x * 0.35 - dial.rotation.y) * 0.05;
          dial.rotation.x += (-0.12 + pointer.y * 0.2 - dial.rotation.x) * 0.05;
          renderer.render(scene, camera);
          raf = requestAnimationFrame(frame);
        };
        if (reduce) {
          setNeedle(0.06);
          setPhase(2);
          renderer.render(scene, camera);
        } else {
          frame();
        }

        cleanup = () => {
          cancelAnimationFrame(raf);
          ro.disconnect();
          window.removeEventListener("pointermove", onMove);
          scene.traverse((o) => {
            const m = o as unknown as { geometry?: { dispose: () => void }; material?: { dispose: () => void } };
            m.geometry?.dispose();
            m.material?.dispose();
          });
          [faceTex, shadowTex, env].forEach((x) => x.dispose());
          pmrem.dispose();
          renderer.dispose();
          renderer.domElement.remove();
        };
      } catch {
        if (!disposed) setFailed(true);
      }
    })();

    return () => {
      disposed = true;
      cleanup();
    };
  }, [zonesKey]);

  return (
    <figure className="dial">
      <div className="dial-stage" ref={host} aria-hidden="true">{failed && <div className="dial-fallback">₹</div>}</div>
      <figcaption className="dial-read" aria-live="off">
        <span className={`dial-step ${phase === 0 ? "on" : ""}`}>{copy.steps[0]}</span>
        <span className={`dial-step ${phase === 1 ? "on" : ""}`}>{copy.steps[1]}</span>
        <span className={`dial-step warn ${phase === 2 ? "on" : ""}`}>{copy.steps[2]}</span>
        <p className="dial-punch">{copy.punch}</p>
      </figcaption>
    </figure>
  );
}
