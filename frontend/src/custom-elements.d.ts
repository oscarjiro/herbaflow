import type * as React from 'react'

declare module 'cytoscape-fcose'

declare module 'react' {
  namespace JSX {
    interface IntrinsicElements {
      'ascii-dna': React.DetailedHTMLProps<React.HTMLAttributes<HTMLElement>, HTMLElement>
    }
  }
}
