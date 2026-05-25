/**
 * Display formatting utilities.
 */

// Words that stay lowercase in title-case unless they are the first word
const MINOR_WORDS = new Set([
  'a', 'an', 'the',
  'and', 'but', 'or', 'nor',
  'at', 'by', 'for', 'in', 'of', 'on', 'to', 'up', 'via', 'with',
])

/**
 * Format a disease name for display.
 *
 * Rules:
 * - Title-cases each space-separated word
 * - Preserves all-caps acronyms (HIV, COVID, DNA, SARS, EBV, …)
 * - Keeps minor words (prepositions, conjunctions, articles) lowercase
 *   unless they are the first word
 *
 * @example
 * formatDiseaseName("breast cancer")         // "Breast Cancer"
 * formatDiseaseName("type 2 diabetes mellitus") // "Type 2 Diabetes Mellitus"
 * formatDiseaseName("HIV/AIDS")              // "HIV/AIDS"
 * formatDiseaseName("cancer of the liver")   // "Cancer of the Liver"
 */
export function formatDiseaseName(name: string): string {
  if (!name) return name
  return name
    .split(' ')
    .map((word, i) => {
      if (!word) return word
      // Preserve acronyms: 2+ consecutive uppercase letters at word start
      if (/^[A-Z]{2,}/.test(word)) return word
      const lower = word.toLowerCase()
      // Minor words stay lowercase except as the first word
      if (i > 0 && MINOR_WORDS.has(lower)) return lower
      return lower.charAt(0).toUpperCase() + lower.slice(1)
    })
    .join(' ')
}
