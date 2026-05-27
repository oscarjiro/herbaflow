import { describe, it, expect } from 'vitest'
import { formatDiseaseName } from './format'

describe('formatDiseaseName', () => {
  it('title-cases normal disease names', () => {
    expect(formatDiseaseName('breast cancer')).toBe('Breast Cancer')
  })
  it('preserves already-uppercase acronyms', () => {
    expect(formatDiseaseName('HIV/AIDS')).toBe('HIV/AIDS')
  })
  it('uppercases known acronyms stored as lowercase', () => {
    expect(formatDiseaseName('copd')).toBe('COPD')
    expect(formatDiseaseName('masld')).toBe('MASLD')
    expect(formatDiseaseName('nafld')).toBe('NAFLD')
    expect(formatDiseaseName('t2dm')).toBe('T2DM')
  })
  it('handles mixed case in disease names', () => {
    expect(formatDiseaseName('type 2 diabetes mellitus')).toBe('Type 2 Diabetes Mellitus')
  })
})
