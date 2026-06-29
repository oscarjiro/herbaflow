/**
 * BackgroundFX — dotted-glow background layer.
 *
 * Renders a fixed, aria-hidden, pointer-events:none layer behind page content.
 * Three modes via the `glow` prop (default "blobs"):
 *   "off"   — nothing visible; component still mounts the root wrapper.
 *   "blobs" — animated dot grid + two subtle drifting colour blobs.
 *   "flow"  — animated dot grid + an interactive WebGL flow shader.
 *             three.js is dynamically imported ONLY when glow==="flow".
 *
 * One canonical home — do not replicate the dots recipe anywhere else.
 */

import { useEffect, useRef } from "react";
import { cn } from "@/lib/cn";
import { GRAIN_ENABLED } from "@/lib/grain";

// ---------------------------------------------------------------------------
// Fragment shader ported verbatim from landing.html mockup (proven tuning).
// ---------------------------------------------------------------------------
const FLOW_FS = `precision highp float;
uniform float uTime;
uniform vec2  uRes;
uniform vec2  uMouse;
uniform vec3  cBg, cA, cB, cC;

float hash(vec2 p) {
  p = fract(p * vec2(123.34, 345.45));
  p += dot(p, p + 34.345);
  return fract(p.x * p.y);
}
float noise(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  float a = hash(i), b = hash(i + vec2(1., 0.)),
        c = hash(i + vec2(0., 1.)), d = hash(i + vec2(1., 1.));
  vec2 u = f * f * (3. - 2. * f);
  return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}
float fbm(vec2 p) {
  float v = 0., a = 0.5;
  for (int i = 0; i < 5; i++) { v += a * noise(p); p *= 2.0; a *= 0.5; }
  return v;
}
void main() {
  vec2 uv = gl_FragCoord.xy / uRes;
  float asp = uRes.x / uRes.y;
  vec2 p = vec2(uv.x * asp, uv.y) * 1.6;
  float t = uTime * 0.035;
  p += (uMouse - 0.5) * 0.55;
  float md = distance(vec2(uv.x * asp, uv.y), vec2(uMouse.x * asp, uMouse.y));
  float mInf = smoothstep(0.55, 0.0, md);
  vec2 q = vec2(fbm(p + vec2(0.0, t)), fbm(p + vec2(5.2, 1.3) - t));
  vec2 r = vec2(fbm(p + 3.0 * q + vec2(1.7, 9.2) + t * 0.6),
                fbm(p + 3.0 * q + vec2(8.3, 2.8) - t * 0.4));
  float f = fbm(p + 3.0 * r);
  float boost = 1.0 + mInf * 1.6;
  vec3 col = cBg;
  col = mix(col, cA, smoothstep(0.2, 0.9, f)   * 0.085 * boost);
  col = mix(col, cB, smoothstep(0.3, 0.95, r.x) * 0.07  * boost);
  col = mix(col, cC, smoothstep(0.25, 0.9, q.y) * 0.06  * boost);
  float g = hash(gl_FragCoord.xy + uTime) * 0.018 - 0.009;
  col += g;
  gl_FragColor = vec4(col, 1.0);
}`;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Parse "#rrggbb" into a [r,g,b] triple (0..1 each). */
function hexToRgb(hex: string): [number, number, number] {
  return [
    parseInt(hex.slice(1, 3), 16) / 255,
    parseInt(hex.slice(3, 5), 16) / 255,
    parseInt(hex.slice(5, 7), 16) / 255,
  ];
}

/**
 * Parse a CSS color value (hex or rgb()/rgba()) into [r,g,b] triple (0..1).
 * Returns null if the value cannot be parsed (empty / unsupported format).
 */
export function parseCssColor(value: string): [number, number, number] | null {
  const v = value.trim();
  if (!v) return null;

  // hex "#rrggbb" or "#rgb"
  if (v.startsWith("#")) {
    const full = v.length === 4 ? "#" + v[1] + v[1] + v[2] + v[2] + v[3] + v[3] : v;
    if (full.length !== 7) return null;
    return hexToRgb(full);
  }

  // rgb(r, g, b) or rgba(r, g, b, a)
  const m = v.match(/rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/);
  if (m) {
    return [parseInt(m[1]!, 10) / 255, parseInt(m[2]!, 10) / 255, parseInt(m[3]!, 10) / 255];
  }

  return null;
}

// Hard-coded fallbacks (the proven resolved values for each theme).
// Used when getComputedStyle is unavailable (SSR / jsdom without CSS).
const FALLBACK_LIGHT = {
  bg: "#f7f5f2",
  a: "#8fa084",
  b: "#b8755c",
  c: "#6b7e62",
} as const;
const FALLBACK_DARK = {
  bg: "#14130f",
  a: "#a6b89a",
  b: "#cb8b72",
  c: "#8aa07e",
} as const;

/**
 * Derive the flow colour palette by reading CSS custom properties at runtime.
 * Falls back to hard-coded constants when a computed value is empty (jsdom/SSR).
 *
 * Reading from `getComputedStyle` means the palette automatically tracks future
 * token renames without code changes, and changes correctly between light/dark
 * modes whenever this function is called.
 */
export function flowPaletteFromTokens(): {
  bg: [number, number, number];
  a: [number, number, number];
  b: [number, number, number];
  c: [number, number, number];
} {
  const isDark = document.documentElement.classList.contains("dark");
  const fallback = isDark ? FALLBACK_DARK : FALLBACK_LIGHT;
  const cs = getComputedStyle(document.documentElement);

  function read(prop: string, fallbackHex: string): [number, number, number] {
    const raw = cs.getPropertyValue(prop);
    return parseCssColor(raw) ?? (hexToRgb(fallbackHex) as [number, number, number]);
  }

  return {
    bg: read("--hf-bg", fallback.bg),
    a: read("--hf-sage", fallback.a),
    b: read("--hf-terracotta", fallback.b),
    c: read("--hf-sage-deep", fallback.c),
  };
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
export interface BackgroundFXProps {
  glow?: "off" | "blobs" | "flow";
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export function BackgroundFX({ glow = "blobs" }: BackgroundFXProps) {
  const flowRef = useRef<HTMLDivElement>(null);

  // Detect reduced-motion preference (stable for the lifetime of the render).
  const reducedMotion =
    typeof window !== "undefined"
      ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
      : false;

  // -------------------------------------------------------------------------
  // Flow WebGL effect — only runs when glow === "flow".
  // -------------------------------------------------------------------------
  useEffect(() => {
    if (glow !== "flow") return;

    const container = flowRef.current;
    if (!container) return;

    let rafId: number | null = null;
    let disposed = false;

    // We type the three objects loosely to avoid importing three at the
    // module level (keeping it out of the default bundle).
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let renderer: any = null;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let material: any = null;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let geometry: any = null;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let uniforms: any = null;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let threeRef: any = null; // cached THREE module for the observer callback
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let sceneRef: any = null;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let camRef: any = null;

    // MutationObserver that re-applies the palette when the theme class changes.
    // Declared here so cleanup can always call .disconnect() even before import resolves.
    const observer = new MutationObserver(() => {
      if (disposed || !uniforms || !threeRef) return;
      const p = flowPaletteFromTokens();
      uniforms.cBg.value.set(...p.bg);
      uniforms.cA.value.set(...p.a);
      uniforms.cB.value.set(...p.b);
      uniforms.cC.value.set(...p.c);
      // Under reduced-motion the RAF loop is not running — render one fresh frame
      // so the static frame picks up the new theme colours.
      if (reducedMotion && renderer && sceneRef && camRef) {
        renderer.render(sceneRef, camRef);
      }
    });
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    });

    const mousePos = { x: 0.5, y: 0.5 };

    function onMouse(e: MouseEvent) {
      mousePos.x = e.clientX / window.innerWidth;
      mousePos.y = 1 - e.clientY / window.innerHeight;
      if (uniforms) {
        uniforms.uMouse.value.set(mousePos.x, mousePos.y);
      }
    }

    function onResize() {
      if (!renderer || !uniforms) return;
      const w = window.innerWidth;
      const h = window.innerHeight;
      renderer.setSize(w, h);
      uniforms.uRes.value.set(w, h);
    }

    // Dynamically import three only when glow==="flow".
    import("three")
      .then((THREE) => {
        if (disposed) return; // unmounted before import resolved

        // Guard: jsdom / environments without WebGL will throw. Catch and bail.
        let r: typeof renderer;
        try {
          r = new THREE.WebGLRenderer({ antialias: true });
          r.outputColorSpace = THREE.LinearSRGBColorSpace;
        } catch {
          // No WebGL — fall back gracefully to the dots/blobs appearance.
          return;
        }

        const w = window.innerWidth;
        const h = window.innerHeight;
        r.setSize(w, h);

        const scene = new THREE.Scene();
        const cam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);

        // Read the palette from CSS custom properties (theme-aware, token-tracked).
        const p = flowPaletteFromTokens();

        uniforms = {
          uTime: { value: 0 },
          uRes: { value: new THREE.Vector2(w, h) },
          uMouse: { value: new THREE.Vector2(mousePos.x, mousePos.y) },
          cBg: { value: new THREE.Vector3(...p.bg) },
          cA: { value: new THREE.Vector3(...p.a) },
          cB: { value: new THREE.Vector3(...p.b) },
          cC: { value: new THREE.Vector3(...p.c) },
        };

        material = new THREE.ShaderMaterial({
          uniforms,
          vertexShader: "void main(){ gl_Position = vec4(position, 1.0); }",
          fragmentShader: FLOW_FS,
        });

        geometry = new THREE.PlaneGeometry(2, 2);
        scene.add(new THREE.Mesh(geometry, material));

        container.appendChild(r.domElement);
        renderer = r;
        // Cache refs needed by the MutationObserver callback.
        threeRef = THREE;
        sceneRef = scene;
        camRef = cam;

        // RAF loop (skipped under reduced motion — render one static frame).
        if (reducedMotion) {
          r.render(scene, cam);
          return;
        }

        function loop() {
          if (disposed) return;
          uniforms.uTime.value = performance.now() / 1000;
          r.render(scene, cam);
          rafId = requestAnimationFrame(loop);
        }
        rafId = requestAnimationFrame(loop);

        window.addEventListener("mousemove", onMouse, { passive: true });
        window.addEventListener("resize", onResize);
      })
      .catch(() => {
        // Import failure — silently degrade to dots/blobs appearance.
      });

    // Cleanup: cancel RAF, remove listeners, disconnect observer, dispose GPU resources.
    return () => {
      disposed = true;
      observer.disconnect();
      if (rafId !== null) cancelAnimationFrame(rafId);
      window.removeEventListener("mousemove", onMouse);
      window.removeEventListener("resize", onResize);
      if (geometry) geometry.dispose();
      if (material) material.dispose();
      if (renderer) {
        renderer.dispose();
        const canvas = renderer.domElement as HTMLCanvasElement | null;
        canvas?.parentNode?.removeChild(canvas);
      }
    };
  }, [glow, reducedMotion]);

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------
  if (glow === "off") {
    return (
      <div
        aria-hidden="true"
        style={{ pointerEvents: "none" }}
        className="fixed inset-0 z-0 overflow-hidden"
      />
    );
  }

  return (
    <div
      aria-hidden="true"
      style={{ pointerEvents: "none" }}
      className="fixed inset-0 z-0 overflow-hidden"
    >
      {/* Dots layer — always present (disabled/static under reduced motion) */}
      <div
        data-bg-layer="dots"
        data-motion-reduced={reducedMotion ? "true" : undefined}
        className={cn("hf-bg__dots", reducedMotion && "hf-bg__dots--static")}
      />

      {/* Blobs (default ambience) */}
      {glow === "blobs" && (
        <div data-bg-layer="blobs" className="hf-bg__blobs">
          <div className="hf-bg__glow hf-bg__glow--g1" />
          <div className="hf-bg__glow hf-bg__glow--g2" />
          <div className="hf-bg__glow hf-bg__glow--g3" />
        </div>
      )}

      {/* Flow WebGL container */}
      {glow === "flow" && <div ref={flowRef} data-bg-layer="flow" className="hf-bg__flow" />}

      {/* Subtle film-grain overlay — topmost bg layer (static; code-toggled). */}
      {GRAIN_ENABLED && <div data-bg-layer="grain" className="hf-bg__grain" />}
    </div>
  );
}
