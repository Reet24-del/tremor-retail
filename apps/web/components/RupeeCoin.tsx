"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Hero 3D: a brass rupee coin that turns slowly, follows the pointer and gives a small "tremor"
 * every few seconds (the moment Tremor notices a leak). three.js is loaded on the client only,
 * and a still frame is rendered when the visitor prefers reduced motion.
 */
export default function RupeeCoin() {
  const host = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    let disposed = false;
    let cleanup = () => {};

    (async () => {
      try {
        const THREE = await import("three");
        const { RoomEnvironment } = await import("three/examples/jsm/environments/RoomEnvironment.js");
        if (disposed) return;

        const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        renderer.toneMapping = THREE.ACESFilmicToneMapping;
        renderer.toneMappingExposure = 1.05;
        el.appendChild(renderer.domElement);

        const scene = new THREE.Scene();
        const pmrem = new THREE.PMREMGenerator(renderer);
        const envTex = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
        scene.environment = envTex;

        const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 100);
        camera.position.set(0, 0.2, 9);

        // ---- Face texture: embossed rupee sign with a lettered ring ----
        const face = () => {
          const c = document.createElement("canvas");
          c.width = c.height = 1024;
          const g = c.getContext("2d")!;
          g.fillStyle = "#808080";
          g.fillRect(0, 0, 1024, 1024);
          g.strokeStyle = "#e6e6e6";
          g.lineWidth = 14;
          g.beginPath();
          g.arc(512, 512, 470, 0, Math.PI * 2);
          g.stroke();
          g.lineWidth = 6;
          g.beginPath();
          g.arc(512, 512, 380, 0, Math.PI * 2);
          g.stroke();
          g.fillStyle = "#f2f2f2";
          g.font = "800 470px Inter, 'Noto Sans', 'Segoe UI', sans-serif";
          g.textAlign = "center";
          g.textBaseline = "middle";
          g.fillText("₹", 512, 540);
          const ring = "TREMOR · RETAIL · PROOF FOR EVERY RUPEE · ";
          g.font = "700 44px Inter, sans-serif";
          const chars = Array.from(ring);
          chars.forEach((ch, i) => {
            const a = (i / chars.length) * Math.PI * 2 - Math.PI / 2;
            g.save();
            g.translate(512 + Math.cos(a) * 425, 512 + Math.sin(a) * 425);
            g.rotate(a + Math.PI / 2);
            g.fillText(ch, 0, 0);
            g.restore();
          });
          const t = new THREE.CanvasTexture(c);
          t.colorSpace = THREE.NoColorSpace;
          return t;
        };
        const edge = (() => {
          const c = document.createElement("canvas");
          c.width = 1024;
          c.height = 32;
          const g = c.getContext("2d")!;
          for (let x = 0; x < 1024; x += 8) {
            g.fillStyle = x % 16 === 0 ? "#ffffff" : "#303030";
            g.fillRect(x, 0, 8, 32);
          }
          const t = new THREE.CanvasTexture(c);
          t.wrapS = THREE.RepeatWrapping;
          t.repeat.set(3, 1);
          return t;
        })();

        const brass = { color: new THREE.Color("#c3cad3"), metalness: 1, roughness: 0.3 }; // brushed steel
        const frontBump = face();
        const faceMat = (bump: InstanceType<typeof THREE.CanvasTexture>) =>
          new THREE.MeshStandardMaterial({ ...brass, bumpMap: bump, bumpScale: 7, roughnessMap: bump });
        // Rim: an open cylinder. Faces: two discs with plain planar UVs, so the artwork reads the right way
        // round from the front and (turned half a circle) from the back.
        const rimMat = new THREE.MeshStandardMaterial({ ...brass, color: new THREE.Color("#9aa3ad"), bumpMap: edge, bumpScale: 2 });
        const mats = [rimMat, faceMat(frontBump)];
        const geo = new THREE.CylinderGeometry(1.75, 1.75, 0.24, 160, 1, true);
        geo.rotateX(Math.PI / 2);
        const discGeo = new THREE.CircleGeometry(1.75, 160);
        const coin = new THREE.Group();
        coin.add(new THREE.Mesh(geo, rimMat));
        const front = new THREE.Mesh(discGeo, mats[1]);
        front.position.z = 0.12;
        const back = new THREE.Mesh(discGeo, mats[1]);
        back.position.z = -0.12;
        back.rotation.y = Math.PI;
        coin.add(front, back);
        const pivot = new THREE.Group();
        pivot.add(coin);
        scene.add(pivot);

        // Thin mint "seismograph" ring around the coin.
        const ringGeo = new THREE.TorusGeometry(2.35, 0.012, 8, 220);
        const ringMat = new THREE.MeshBasicMaterial({ color: "#5ee6a8", transparent: true, opacity: 0.55 });
        const ring = new THREE.Mesh(ringGeo, ringMat);
        ring.rotation.x = Math.PI / 2.4;
        scene.add(ring);

        scene.add(new THREE.AmbientLight("#dfe8f0", 0.25));
        const key = new THREE.DirectionalLight("#ffffff", 2.4);
        key.position.set(4, 5, 6);
        scene.add(key);
        const rim = new THREE.DirectionalLight("#5ee6a8", 2.2);
        rim.position.set(-5, -2, -3);
        scene.add(rim);

        const resize = () => {
          const w = el.clientWidth || 1;
          const h = el.clientHeight || 1;
          renderer.setSize(w, h, false);
          camera.aspect = w / h;
          camera.updateProjectionMatrix();
        };
        resize();
        const ro = new ResizeObserver(resize);
        ro.observe(el);

        const target = { x: 0, y: 0 };
        const onMove = (e: PointerEvent) => {
          const r = el.getBoundingClientRect();
          target.x = ((e.clientX - r.left) / r.width - 0.5) * 0.6;
          target.y = ((e.clientY - r.top) / r.height - 0.5) * 0.4;
        };
        window.addEventListener("pointermove", onMove, { passive: true });

        let raf = 0;
        const clock = new THREE.Clock();
        const frame = () => {
          const t = clock.getElapsedTime();
          coin.rotation.y = Math.sin(t * 0.42) * 0.85 - 0.25; // turns to show the face, never sits edge-on
          pivot.rotation.x += (target.y - pivot.rotation.x) * 0.05;
          pivot.rotation.z += (-target.x * 0.4 - pivot.rotation.z) * 0.05;
          pivot.position.y = Math.sin(t * 0.9) * 0.08;
          // The tremor: a short decaying shake every 5 seconds.
          const p = t % 5;
          const shake = p < 0.6 ? Math.sin(p * 60) * 0.06 * (1 - p / 0.6) : 0;
          pivot.position.x = shake;
          ring.scale.setScalar(1 + (p < 0.9 ? p * 0.12 : 0));
          ringMat.opacity = p < 0.9 ? 0.55 * (1 - p / 0.9) + 0.12 : 0.12 + 0.43 * Math.min(1, (p - 0.9) / 1.2);
          ring.rotation.z = t * 0.1;
          renderer.render(scene, camera);
          raf = requestAnimationFrame(frame);
        };
        if (reduce) {
          coin.rotation.y = -0.5;
          renderer.render(scene, camera);
        } else {
          frame();
        }

        cleanup = () => {
          cancelAnimationFrame(raf);
          ro.disconnect();
          window.removeEventListener("pointermove", onMove);
          geo.dispose();
          discGeo.dispose();
          ringGeo.dispose();
          mats.forEach((m) => m.dispose());
          ringMat.dispose();
          [frontBump, edge, envTex].forEach((x) => x.dispose());
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
  }, []);

  return (
    <div className="coin-stage" ref={host} aria-hidden="true">
      {failed && <div className="coin-fallback">₹</div>}
      
    </div>
  );
}
