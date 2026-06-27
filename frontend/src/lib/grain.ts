/**
 * Grain toggle — the one home for the film-grain background overlay switch.
 *
 * The grain is a static, low-opacity noise layer painted by BackgroundFX (see the
 * `.hf-bg__grain` recipe in index.css). It is purely decorative and motionless, so it
 * needs no capability detection or reduced-motion gating — just an on/off code toggle.
 *
 * Flip GRAIN_ENABLED to false to remove the grain everywhere without touching
 * BackgroundFX. Intensity lives in the `.hf-bg__grain` CSS rule (one styling home).
 */
export const GRAIN_ENABLED = true;
