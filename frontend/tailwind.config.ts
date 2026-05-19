import type { Config } from 'tailwindcss'

export default {
    darkMode: ['class'],
    content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
  	extend: {
  		colors: {
  			/* shadcn/ui semantic tokens (raw var refs — hf tokens are hex/oklch, not HSL channels) */
  			background: 'var(--background)',
  			foreground: 'var(--foreground)',
  			card: {
  				DEFAULT: 'var(--card)',
  				foreground: 'var(--card-foreground)',
  			},
  			popover: {
  				DEFAULT: 'var(--popover)',
  				foreground: 'var(--popover-foreground)',
  			},
  			primary: {
  				DEFAULT: 'var(--primary)',
  				foreground: 'var(--primary-foreground)',
  			},
  			secondary: {
  				DEFAULT: 'var(--secondary)',
  				foreground: 'var(--secondary-foreground)',
  			},
  			muted: {
  				DEFAULT: 'var(--muted)',
  				foreground: 'var(--muted-foreground)',
  			},
  			accent: {
  				DEFAULT: 'var(--accent)',
  				foreground: 'var(--accent-foreground)',
  			},
  			destructive: {
  				DEFAULT: 'var(--destructive)',
  				foreground: 'var(--destructive-foreground)',
  			},
  			border: 'var(--border)',
  			input: 'var(--input)',
  			ring: 'var(--ring)',
  			hf: {
  				bg: 'var(--hf-bg)',
  				surface: 'var(--hf-surface)',
  				'surface-2': 'var(--hf-surface-2)',
  				border: 'var(--hf-border)',
  				'border-strong': 'var(--hf-border-strong)',
  				fg1: 'var(--hf-fg-1)',
  				fg2: 'var(--hf-fg-2)',
  				fg3: 'var(--hf-fg-3)',
  				fg4: 'var(--hf-fg-4)',
  				sage: 'var(--hf-sage)',
  				'sage-deep': 'var(--hf-sage-deep)',
  				'sage-soft': 'var(--hf-sage-soft)',
  				'sage-faint': 'var(--hf-sage-faint)',
  				terracotta: 'var(--hf-terracotta)',
  				'terracotta-soft': 'var(--hf-terracotta-soft)',
  				success: 'var(--hf-success)',
  				'success-soft': 'var(--hf-success-soft)',
  				warning: 'var(--hf-warning)',
  				'warning-soft': 'var(--hf-warning-soft)',
  				danger: 'var(--hf-danger)',
  				'danger-soft': 'var(--hf-danger-soft)',
  				info: 'var(--hf-info)',
  				'info-soft': 'var(--hf-info-soft)',
  				n50: '#F7F5F2',
  				n100: '#EFEBE4',
  				n200: '#E5E0D8',
  				n300: '#D4CEC4',
  				n500: '#9A958C',
  				n600: '#6E6A62',
  				n700: '#4A463F',
  				n900: '#1A1A1A'
  			}
  		},
  		fontFamily: {
  			display: [
  				'Instrument Serif',
  				'Georgia',
  				'serif'
  			],
  			sans: [
  				'Be Vietnam Pro',
  				'sans-serif'
  			],
  			mono: [
  				'Space Mono',
  				'monospace'
  			]
  		},
  		borderRadius: {
  			none: '0',
  			sm: '2px',
  			DEFAULT: '4px',
  			md: '4px',
  			lg: '8px',
  			full: '9999px'
  		},
  		keyframes: {
  			'accordion-down': {
  				from: {
  					height: '0'
  				},
  				to: {
  					height: 'var(--radix-accordion-content-height)'
  				}
  			},
  			'accordion-up': {
  				from: {
  					height: 'var(--radix-accordion-content-height)'
  				},
  				to: {
  					height: '0'
  				}
  			}
  		},
  		animation: {
  			'accordion-down': 'accordion-down 0.2s ease-out',
  			'accordion-up': 'accordion-up 0.2s ease-out'
  		}
  	}
  },
  plugins: [],
} satisfies Config
