/* =====================================================================
   <ascii-dna> — Animated double-helix web component
   ---------------------------------------------------------------------
   Renders a rotating DNA helix as a monospace character grid.
   - 80 × 22 chars by default; configurable via attributes
   - Two strands as sin / -sin curves with depth via cos()
   - Pauses when off-screen (IntersectionObserver)
   - Runs at ~10 fps for a meditative editorial pace
   - Respects prefers-reduced-motion (renders one static frame)

   Usage:
     <ascii-dna cols="80" rows="22" speed="0.06"></ascii-dna>

   Styling: the host element is display:block. Color comes from
   --hf-dna-front (default --hf-fg-1) and --hf-dna-back (default --hf-fg-4).
   ===================================================================== */

(function () {
  class AsciiDna extends HTMLElement {
    static get observedAttributes() { return ['cols', 'rows', 'speed', 'cycles', 'chars']; }

    connectedCallback() {
      // Defaults
      this.cols    = parseInt(this.getAttribute('cols'))    || 80;
      this.rows    = parseInt(this.getAttribute('rows'))    || 22;
      this.speed   = parseFloat(this.getAttribute('speed')) || 0.06;
      this.cycles  = parseFloat(this.getAttribute('cycles')) || 2.4;
      this.chars   = this.getAttribute('chars') || 'default';   // 'default' | 'dots' | 'bases'

      this.t = 0;
      this.lastFrame = 0;
      this.visible = false;
      this.raf = null;

      // Host styles
      Object.assign(this.style, {
        display: 'block',
        fontFamily: 'var(--font-mono, ui-monospace, "Space Mono", monospace)',
        fontSize: '14px',
        lineHeight: '1.0',
        letterSpacing: '0',
        whiteSpace: 'pre',
        color: 'var(--hf-dna-front, var(--hf-fg-1, #1A1A1A))',
        userSelect: 'none',
        contain: 'layout paint',
      });

      // Inject inner style for strand tiers (scoped via :scope-like)
      const styleEl = document.createElement('style');
      styleEl.textContent = `
        ascii-dna .dna-back  { color: var(--hf-dna-back, var(--hf-fg-4, #9A958C)); opacity: .55; }
        ascii-dna .dna-mid   { color: var(--hf-dna-back, var(--hf-fg-4, #9A958C)); opacity: .85; }
        ascii-dna .dna-front { color: var(--hf-dna-front, var(--hf-fg-1, #1A1A1A)); }
        ascii-dna .dna-rung  { color: var(--hf-dna-back, var(--hf-fg-4, #9A958C)); opacity: .35; }
        ascii-dna .dna-base  { color: var(--hf-sage-deep, #6B7E62); opacity: .8; }
      `;
      if (!document.head.querySelector('style[data-ascii-dna]')) {
        styleEl.setAttribute('data-ascii-dna', '');
        document.head.appendChild(styleEl);
      }

      // Reduced motion → render one frame and bail
      this.prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      // speed=0 → static (one render, no rAF loop)
      this.staticMode = !this.speed;

      this.render();

      if (this.staticMode) return;

      // Visibility-gated animation
      this.io = new IntersectionObserver(([entry]) => {
        this.visible = entry.isIntersecting;
        if (this.visible && !this.raf && !this.prefersReduced) {
          this.raf = requestAnimationFrame(this.tick);
        }
      }, { threshold: 0.01 });
      this.io.observe(this);

      // Pause when tab hidden
      this._visHandler = () => {
        if (document.hidden && this.raf) { cancelAnimationFrame(this.raf); this.raf = null; }
        else if (!document.hidden && this.visible && !this.prefersReduced) {
          this.raf = requestAnimationFrame(this.tick);
        }
      };
      document.addEventListener('visibilitychange', this._visHandler);
    }

    disconnectedCallback() {
      if (this.raf) cancelAnimationFrame(this.raf);
      this.io && this.io.disconnect();
      if (this._visHandler) document.removeEventListener('visibilitychange', this._visHandler);
    }

    attributeChangedCallback() {
      this.cols    = parseInt(this.getAttribute('cols'))    || this.cols;
      this.rows    = parseInt(this.getAttribute('rows'))    || this.rows;
      this.speed   = parseFloat(this.getAttribute('speed')) || this.speed;
      this.cycles  = parseFloat(this.getAttribute('cycles')) || this.cycles;
      this.chars   = this.getAttribute('chars') || this.chars || 'default';
      this.render();
    }

    tick = (now) => {
      if (!this.visible) { this.raf = null; return; }
      this.raf = requestAnimationFrame(this.tick);
      // ~12 fps
      if (now - this.lastFrame < 82) return;
      this.lastFrame = now;
      this.t += this.speed;
      this.render();
    };

    // Map depth (-1 back → 1 front) to a (char, css-class) pair.
    strandChar(z) {
      if (this.chars === 'dots') {
        // Atmospheric halftone — only dot characters, density via class.
        if (z >  0.65) return ['●', 'dna-front'];
        if (z >  0.20) return ['•', 'dna-mid'];
        if (z > -0.20) return ['·', 'dna-mid'];
        if (z > -0.65) return ['·', 'dna-back'];
        return ['·', 'dna-back'];
      }
      if (z >  0.65) return ['O', 'dna-front'];
      if (z >  0.20) return ['o', 'dna-mid'];
      if (z > -0.20) return [':', 'dna-mid'];
      if (z > -0.65) return ['.', 'dna-back'];
      return ['·', 'dna-back'];
    }

    render() {
      const { cols, rows, t, cycles } = this;

      // 2D buffer of [char, cls]
      const empty = [' ', ''];
      const grid = Array.from({ length: rows }, () =>
        Array.from({ length: cols }, () => empty)
      );

      const cy = (rows - 1) / 2;
      const amp = (rows - 2) / 2;

      // Base pairs — fixed sequence so they don't flicker
      // (deterministic by column index, not time)
      const BASES = ['A·T', 'T·A', 'G·C', 'C·G'];

      // 1) Rungs first (under strands)
      const rungEvery = 4;
      const showRungs = this.chars !== 'dots';   // atmospheric mode skips rungs
      for (let x = 0; x < cols; x++) {
        const angle = (x / cols) * cycles * Math.PI * 2 + t;
        const y1 = cy + amp * Math.sin(angle);
        const y2 = cy + amp * Math.sin(angle + Math.PI);

        if (showRungs && x % rungEvery === 0) {
          const yA = Math.round(Math.min(y1, y2));
          const yB = Math.round(Math.max(y1, y2));
          const sep = yB - yA;

          // No rung when strands are crossed/too close
          if (sep >= 3) {
            const isMaxOpen = Math.abs(Math.sin(angle)) > 0.92;
            for (let y = yA + 1; y < yB; y++) {
              grid[y][x] = ['│', 'dna-rung'];
            }
            // At max-open frames, mark with a base-letter label at the middle
            if (isMaxOpen) {
              const mid = Math.round((yA + yB) / 2);
              const base = BASES[Math.floor(x / rungEvery) % BASES.length];
              // Place 3 chars centered: e.g. A·T
              if (x > 0 && x < cols - 1) {
                grid[mid][x - 1] = [base[0], 'dna-base'];
                grid[mid][x]     = [base[1], 'dna-base'];
                grid[mid][x + 1] = [base[2], 'dna-base'];
              }
            }
          }
        }
      }

      // 2) Strands on top
      for (let x = 0; x < cols; x++) {
        const angle = (x / cols) * cycles * Math.PI * 2 + t;
        const y1 = Math.round(cy + amp * Math.sin(angle));
        const y2 = Math.round(cy + amp * Math.sin(angle + Math.PI));
        const z1 = Math.cos(angle);
        const z2 = Math.cos(angle + Math.PI);

        if (y1 >= 0 && y1 < rows) grid[y1][x] = this.strandChar(z1);
        if (y2 >= 0 && y2 < rows) grid[y2][x] = this.strandChar(z2);
      }

      // 3) Flatten — group consecutive same-class cells into runs
      let html = '';
      for (let r = 0; r < rows; r++) {
        const row = grid[r];
        let i = 0;
        while (i < cols) {
          const cls = row[i][1];
          let j = i;
          let buf = '';
          while (j < cols && row[j][1] === cls) {
            buf += row[j][0];
            j++;
          }
          // HTML-safe (only chars are ASCII + · │ — no need to escape)
          html += cls ? `<span class="${cls}">${buf}</span>` : buf;
          i = j;
        }
        if (r < rows - 1) html += '\n';
      }
      this.innerHTML = html;
    }
  }

  if (!customElements.get('ascii-dna')) {
    customElements.define('ascii-dna', AsciiDna);
  }
})();
