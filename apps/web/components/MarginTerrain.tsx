"use client";

import { useEffect, useRef, useState } from "react";

type Ridge = { id: string; name: string; profit: number[]; margin: number[]; gap: number[]; flagged_from: number | null };
type Data = { dates: string[]; products: Ridge[] };

const HERO = "SKU-OIL-1L";

/**
 * Landing 3D: the demo store as a ridgeline terrain. One line per product, 90 days left to right,
 * height = daily gross profit (scaled to each product's peak), dips = units short against the stock arithmetic. A scanner sweeps
 * the timeline and the lines Tremor flags light up from the day the leak starts.
 *
 * Data: /landing-ridges.json, built from the demo fixture by scripts/build_landing_data.py.
 */
export default function MarginTerrain({ caption }: { caption: { legend: string; flagged: string; hero: string } }) {
  const host = useRef<HTMLDivElement>(null);
  const tip = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    let disposed = false;
    let cleanup = () => {};

    (async () => {
      try {
        const [THREE, data] = await Promise.all([
          import("three"),
          fetch("/landing-ridges.json").then((r) => r.json() as Promise<Data>),
        ]);
        if (disposed) return;
        const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

        const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        el.appendChild(renderer.domElement);
        const scene = new THREE.Scene();
        scene.fog = new THREE.Fog("#f5f1ea", 8, 17);
        const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 100);

        const days = data.dates.length;
        const W = 13; // world width of the timeline
        const D = 8.5; // world depth across products
        const x = (i: number) => (i / (days - 1) - 0.5) * W;
        const products = [...data.products].sort((a, b) => Number(a.flagged_from !== null) - Number(b.flagged_from !== null));
        // Spread flagged products through the field instead of stacking them at the front.
        const order = products.filter((p) => p.flagged_from === null);
        // Flagged products sit in the nearer rows so their step down is visible.
        products.filter((p) => p.flagged_from !== null).forEach((p, k) => order.splice(order.length - 9 + k * 2, 0, p));
        const z = (k: number) => (k / (order.length - 1) - 0.5) * D;
        const y = (p: Ridge, i: number) => p.profit[i] * 1.3 + Math.max(-0.9, p.gap[i] / 16);

        const disposables: { dispose: () => void }[] = [];
        const lineGray = new THREE.LineBasicMaterial({ color: "#8a857c", transparent: true, opacity: 0.9 });
        const lineHot = new THREE.LineBasicMaterial({ color: "#b8664b", depthTest: false, fog: false });
        const fill = new THREE.MeshBasicMaterial({ color: "#f5f1ea", side: THREE.DoubleSide, polygonOffset: true,
          polygonOffsetFactor: 1, polygonOffsetUnits: 1 });
        disposables.push(lineGray, lineHot, fill);

        const hot: { geo: InstanceType<typeof THREE.BufferGeometry>; from: number; count: number }[] = [];
        let heroPoint = new THREE.Vector3();

        order.forEach((p, k) => {
          const zz = z(k);
          const pts = Array.from({ length: days }, (_, i) => new THREE.Vector3(x(i), y(p, i), zz));
          // Occluding skirt under each ridge so rear lines hide behind front ones.
          const skirt = new THREE.BufferGeometry();
          const pos: number[] = [];
          for (let i = 0; i < days - 1; i++) {
            const a = pts[i], b = pts[i + 1];
            pos.push(a.x, -1.2, zz, b.x, -1.2, zz, a.x, a.y, zz, b.x, -1.2, zz, b.x, b.y, zz, a.x, a.y, zz);
          }
          skirt.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
          scene.add(new THREE.Mesh(skirt, fill));
          disposables.push(skirt);

          const base = new THREE.BufferGeometry().setFromPoints(pts);
          scene.add(new THREE.Line(base, lineGray));
          disposables.push(base);

          if (p.flagged_from !== null) {
            const seg = pts.slice(p.flagged_from - 1 < 0 ? 0 : p.flagged_from - 1).map((v) => v.clone().setY(v.y + 0.004));
            const g = new THREE.BufferGeometry().setFromPoints(seg);
            g.setDrawRange(0, 0);
            const hotLine = new THREE.Line(g, lineHot);
            hotLine.renderOrder = 10; // drawn last, over the skirts
            scene.add(hotLine);
            hot.push({ geo: g, from: Math.max(0, p.flagged_from - 1), count: seg.length });
            disposables.push(g);
            if (p.id === HERO) heroPoint = pts[Math.min(days - 1, p.flagged_from + 4)].clone();
          }
        });

        // The scanner: a faint sheet across all products that sweeps the timeline.
        const scanGeo = new THREE.PlaneGeometry(D + 0.6, 2.6);
        scanGeo.rotateY(Math.PI / 2);
        const scanMat = new THREE.MeshBasicMaterial({ color: "#b8664b", transparent: true, opacity: 0.07, side: THREE.DoubleSide,
          depthWrite: false });
        const edgeGeo = new THREE.BufferGeometry().setFromPoints([
          new THREE.Vector3(0, 1.4, -(D + 0.6) / 2), new THREE.Vector3(0, 1.4, (D + 0.6) / 2)]);
        const edgeMat = new THREE.LineBasicMaterial({ color: "#b8664b", transparent: true, opacity: 0.6 });
        const scanGroup = new THREE.Group();
        const sheet = new THREE.Mesh(scanGeo, scanMat);
        sheet.position.y = 0.1;
        scanGroup.add(sheet, new THREE.Line(edgeGeo, edgeMat));
        scene.add(scanGroup);
        disposables.push(scanGeo, scanMat, edgeGeo, edgeMat);

        const resize = () => {
          const w = el.clientWidth || 1;
          const h = el.clientHeight || 1;
          renderer.setSize(w, h, false);
          camera.aspect = w / h;
          camera.position.set(0, 6.2, w < 700 ? 12 : 8.2);
          camera.lookAt(0, -0.6, 0.6);
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

        const world = new THREE.Group();
        scene.children.slice().forEach((c) => world.add(c));
        scene.add(world);

        const SWEEP = 7; // seconds for one pass over the 90 days
        const project = new THREE.Vector3();
        let raf = 0;
        const clock = new THREE.Clock();
        const frame = () => {
          const t = reduce ? SWEEP : clock.getElapsedTime();
          const phase = Math.min(1, (t % (SWEEP + 3)) / SWEEP); // sweep, then hold for 3 s
          const dayIdx = phase * (days - 1);
          scanGroup.position.x = x(dayIdx);
          scanMat.opacity = phase >= 1 ? 0 : 0.07;
          edgeMat.opacity = phase >= 1 ? 0 : 0.6;
          hot.forEach((h) => h.geo.setDrawRange(0, Math.max(0, Math.min(h.count, Math.ceil(dayIdx - h.from + 1)))));

          world.rotation.y += ((reduce ? 0 : pointer.x * 0.25) - world.rotation.y) * 0.05;
          world.rotation.x += ((reduce ? 0 : pointer.y * 0.08) - world.rotation.x) * 0.05;
          renderer.render(scene, camera);

          // Pin the hero label to the oil ridge once the scanner has passed it.
          if (tip.current) {
            project.copy(heroPoint).applyMatrix4(world.matrixWorld).project(camera);
            const shown = dayIdx >= (heroPoint.x / W + 0.5) * (days - 1);
            tip.current.style.transform = `translate(${((project.x + 1) / 2) * el.clientWidth}px, ${((1 - project.y) / 2) * el.clientHeight}px)`;
            tip.current.style.opacity = shown ? "1" : "0";
          }
          if (!reduce) raf = requestAnimationFrame(frame);
        };
        frame();

        cleanup = () => {
          cancelAnimationFrame(raf);
          ro.disconnect();
          window.removeEventListener("pointermove", onMove);
          disposables.forEach((d) => d.dispose());
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
  }, []);

  return (
    <figure className="terrain">
      <div className="terrain-stage" ref={host} aria-hidden="true">
        {!failed && <div className="terrain-tip" ref={tip}><span>{caption.hero}</span></div>}
      </div>
      <figcaption className="terrain-caption">
        <span><i className="k-gray" />{caption.legend}</span>
        <span><i className="k-hot" />{caption.flagged}</span>
      </figcaption>
    </figure>
  );
}
