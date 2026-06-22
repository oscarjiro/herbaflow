/**
 * useAsciiDna — owns the three.js renderer that turns a Draco-compressed
 * `dna.glb` into a live ASCII grid for the Landing hero backdrop.
 *
 * Lifecycle mirrors BackgroundFX (the one canonical lazy-three pattern):
 *   mount → guard (SSR / WebGL / reduced-motion) → lazy `import("three")`
 *   → init scene/camera/lights/loader → RAF loop → dispose on unmount.
 * A MutationObserver re-reads the ink token (`--hf-fg-1`) on theme change so
 * the ASCII recolours for light/dark, exactly like the mockup's syncDnaColor.
 *
 * three.js (and its GLTF/DRACO addons) are imported ONLY inside the effect, so
 * they stay in a Landing-only lazy chunk and never enter the app shell bundle.
 *
 * Returns a status the caller uses to decide whether to show the static
 * fallback: "fallback" when WebGL/reduced-motion rule out the live render or
 * the model fails to load; "loading" while the model streams; "ready" once it
 * is on screen. The renderer mounts into `containerRef`.
 */

import { useEffect, useState } from "react";

// Luminance ramp ported verbatim from landing.html (proven tuning).
const RAMP = " .'`^\",:;Il!i><~+_-?][}{1)(|/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$";

// Locked desktop tuning (Landing spec §3.2). Renderer constants, not UI colour.
const TUNING = {
  rotX: (13 * Math.PI) / 180,
  rotY: (3 * Math.PI) / 180,
  rotZ: (-25 * Math.PI) / 180,
  cameraFill: 0.4, // "size"
  spin: 0.6,
  emissive: 4.0, // "glow"
  brightness: 0.65,
  contrast: 0.75,
  floor: 0.06,
  resolution: 0.29, // "detail"
} as const;

// Vertical compression of the ASCII grid (monospace cells are taller than wide).
const ASCII_ASPECT = 0.52;

export type AsciiDnaStatus = "loading" | "ready" | "fallback";

/** Synchronously detect whether a WebGL context can be created. */
function webglSupported(): boolean {
  if (typeof document === "undefined") return false;
  try {
    const canvas = document.createElement("canvas");
    return !!(
      canvas.getContext("webgl2") ||
      canvas.getContext("webgl") ||
      canvas.getContext("experimental-webgl")
    );
  } catch {
    return false;
  }
}

/** Read the ink colour token (`--hf-fg-1`), theme-aware, with a safe default. */
function inkColor(): string {
  if (typeof document === "undefined") return "#1a1a1a";
  const v = getComputedStyle(document.documentElement).getPropertyValue("--hf-fg-1").trim();
  return v || "#1a1a1a";
}

export function useAsciiDna(containerRef: React.RefObject<HTMLDivElement | null>): AsciiDnaStatus {
  // Decided once per mount: reduced-motion or no WebGL forces the fallback.
  const reducedMotion =
    typeof window !== "undefined"
      ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
      : false;
  const canRender = !reducedMotion && webglSupported();

  const [status, setStatus] = useState<AsciiDnaStatus>(canRender ? "loading" : "fallback");

  useEffect(() => {
    if (!canRender) return;
    const container = containerRef.current;
    if (!container) return;

    let rafId: number | null = null;
    let disposed = false;

    // Loosely typed three objects so three is never referenced at module scope
    // (keeping it out of the default bundle), mirroring BackgroundFX.
    /* eslint-disable @typescript-eslint/no-explicit-any */
    let renderer: any = null;
    let scene: any = null;
    let camera: any = null;
    let rig: any = null;
    let model: any = null;
    let mixer: any = null;
    let timer: any = null;
    let modelRadius = 1;
    let framingDist = 1;
    /* eslint-enable @typescript-eslint/no-explicit-any */

    // ASCII conversion surface (offscreen 2D canvas + the DOM <pre> sink).
    const asciiCanvas = document.createElement("canvas");
    const asciiCtx = asciiCanvas.getContext("2d", { willReadFrequently: true });
    const asciiDom = document.createElement("div");
    asciiDom.style.whiteSpace = "pre";
    asciiDom.style.fontFamily = '"Courier New", ui-monospace, monospace';
    asciiDom.style.fontWeight = "700";
    asciiDom.style.color = inkColor();
    let asciiW = 1;
    let asciiH = 1;

    function sizeAscii(w: number, h: number) {
      asciiW = Math.max(1, (w * TUNING.resolution) | 0);
      // Height derives from the render height; ASCII cells are taller than wide.
      asciiH = Math.max(1, (h * TUNING.resolution * ASCII_ASPECT) | 0);
      asciiCanvas.width = asciiW;
      asciiCanvas.height = asciiH;
      asciiDom.style.width = w + "px";
      asciiDom.style.height = h + "px";
    }

    function drawAscii() {
      if (!asciiCtx || !renderer) return;
      asciiCtx.clearRect(0, 0, asciiW, asciiH);
      asciiCtx.drawImage(renderer.domElement, 0, 0, asciiW, asciiH);
      const d = asciiCtx.getImageData(0, 0, asciiW, asciiH).data;
      const chars = RAMP;
      let s = "";
      for (let y = 0; y < asciiH; y++) {
        for (let x = 0; x < asciiW; x++) {
          const i = (y * asciiW + x) * 4;
          // Dense RGBA buffer — every index is in bounds.
          const a = d[i + 3]!;
          let b: number;
          if (a < 8) {
            b = 0;
          } else {
            b = (0.3 * d[i]! + 0.59 * d[i + 1]! + 0.11 * d[i + 2]!) / 255;
            b = Math.min(1, b * TUNING.brightness);
            b = Math.pow(b, 1 / TUNING.contrast);
            if (b > 0.001) b = Math.max(b, TUNING.floor);
          }
          let idx = (b * (chars.length - 1) + 0.5) | 0;
          if (idx < 0) idx = 0;
          else if (idx >= chars.length) idx = chars.length - 1;
          s += chars[idx] ?? " ";
        }
        s += "\n";
      }
      const fs = (asciiDom.clientWidth || container!.clientWidth || 1) / asciiW / 0.6;
      asciiDom.style.fontSize = fs.toFixed(2) + "px";
      asciiDom.style.lineHeight = fs.toFixed(2) + "px";
      asciiDom.textContent = s;
    }

    // Re-sync the ASCII colour when the theme class flips (mockup syncDnaColor).
    const observer = new MutationObserver(() => {
      if (disposed) return;
      asciiDom.style.color = inkColor();
    });
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    });

    function applyCamera() {
      if (!camera) return;
      const vH = (camera.fov * Math.PI) / 180 / 2;
      const hH = Math.atan(Math.tan(vH) * camera.aspect);
      framingDist = Math.max(modelRadius / Math.sin(vH), modelRadius / Math.sin(hH)) * 1.1;
      camera.position.set(0, 0, framingDist * TUNING.cameraFill);
      camera.lookAt(0, 0, 0);
      camera.updateProjectionMatrix();
    }

    function onResize() {
      if (!renderer || !camera || !container) return;
      const w = container.clientWidth || window.innerWidth;
      const h = container.clientHeight || window.innerHeight;
      renderer.setSize(w, h);
      camera.aspect = w / h;
      sizeAscii(w, h);
      if (model) applyCamera();
      else camera.updateProjectionMatrix();
    }

    import("three")
      .then(async (THREE) => {
        if (disposed) return;

        // Guard: environments without real WebGL throw here. Fall back.
        try {
          renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        } catch {
          if (!disposed) setStatus("fallback");
          return;
        }

        const w = container.clientWidth || window.innerWidth || 1100;
        const h = container.clientHeight || window.innerHeight || 560;
        renderer.setSize(w, h);

        scene = new THREE.Scene();
        camera = new THREE.PerspectiveCamera(35, w / h, 0.01, 100);

        // Lighting ported from the mockup (white renderer constants — not UI colour).
        scene.add(new THREE.AmbientLight(0xffffff, 0.7));
        const key = new THREE.DirectionalLight(0xffffff, 4.0);
        key.position.set(2, 3, 4);
        scene.add(key);
        const rim = new THREE.DirectionalLight(0xffffff, 1.8);
        rim.position.set(-3, -1, 2);
        scene.add(rim);

        timer = new THREE.Timer();

        // Mount the ASCII sink (the canvas itself stays offscreen).
        sizeAscii(w, h);
        container.appendChild(asciiDom);

        // GLTF + DRACO. Decoder is vendored under /draco/ (see note below).
        const [{ GLTFLoader }, { DRACOLoader }] = await Promise.all([
          import("three/examples/jsm/loaders/GLTFLoader.js"),
          import("three/examples/jsm/loaders/DRACOLoader.js"),
        ]);
        if (disposed) return;

        const draco = new DRACOLoader();
        draco.setDecoderPath("/draco/");
        const loader = new GLTFLoader();
        loader.setDRACOLoader(draco);

        loader.load(
          "/assets/dna.glb",
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          (gltf: any) => {
            if (disposed) {
              draco.dispose();
              return;
            }
            model = gltf.scene;
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            model.traverse((o: any) => {
              if (o.isMesh && o.material) {
                const m = o.material;
                m.transparent = false;
                if (m.emissive) m.emissiveIntensity = TUNING.emissive;
                m.metalness = 0;
                m.roughness = 0.6;
              }
            });
            const box = new THREE.Box3().setFromObject(model);
            const sphere = box.getBoundingSphere(new THREE.Sphere());
            model.position.sub(sphere.center);
            modelRadius = sphere.radius || 1;

            rig = new THREE.Group();
            rig.add(model);
            scene.add(rig);
            applyCamera();

            if (gltf.animations && gltf.animations.length) {
              mixer = new THREE.AnimationMixer(model);
              mixer.clipAction(gltf.animations[0]).setLoop(THREE.LoopRepeat, Infinity).play();
            }
            draco.dispose(); // worker pool no longer needed after decode
            if (!disposed) setStatus("ready");
          },
          undefined,
          () => {
            // Model failed to load — show the static fallback, do not hang.
            draco.dispose();
            if (!disposed) setStatus("fallback");
          },
        );

        function loop() {
          if (disposed) return;
          // Timer (replaces deprecated Clock, r183+): update once per frame,
          // then read the frame-stable delta.
          timer.update();
          const dt = timer.getDelta();
          if (mixer) mixer.update(dt * TUNING.spin);
          if (rig) rig.rotation.set(TUNING.rotX, TUNING.rotY, TUNING.rotZ);
          if (model) {
            camera.position.set(0, 0, framingDist * TUNING.cameraFill);
            camera.lookAt(0, 0, 0);
          }
          renderer.render(scene, camera);
          drawAscii();
          rafId = requestAnimationFrame(loop);
        }
        rafId = requestAnimationFrame(loop);

        window.addEventListener("resize", onResize);
      })
      .catch(() => {
        if (!disposed) setStatus("fallback");
      });

    // Cleanup: cancel RAF, remove listeners, disconnect observer, dispose GPU.
    return () => {
      disposed = true;
      observer.disconnect();
      if (rafId !== null) cancelAnimationFrame(rafId);
      window.removeEventListener("resize", onResize);
      if (mixer) mixer.stopAllAction?.();
      if (renderer) {
        renderer.dispose();
        const canvas = renderer.domElement as HTMLCanvasElement | null;
        canvas?.parentNode?.removeChild(canvas);
      }
      asciiDom.parentNode?.removeChild(asciiDom);
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      scene?.traverse?.((o: any) => {
        if (o.geometry) o.geometry.dispose?.();
        const mat = o.material;
        if (Array.isArray(mat)) mat.forEach((m) => m?.dispose?.());
        else mat?.dispose?.();
      });
    };
  }, [canRender]);

  return status;
}
