import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { Input } from '@/components/ui/input'
import { PARAM_DEFAULTS } from '@/lib/stage-params'

// ============================================================================
// Types & defaults
// ============================================================================

export interface AdvancedParams {
  // ADME (Stage 2)
  max_mw: number
  max_logp: number
  max_hbd: number
  max_hba: number
  max_tpsa: number
  max_rotatable_bonds: number
  apply_veber: boolean
  apply_pains: boolean
  np_exception_threshold: number
  apply_adme_to_manual: boolean

  // Targets (Stage 3)
  min_pchembl: number
  human_only: boolean
  min_assay_confidence: number

  // Disease Targets (Stage 4)
  min_score: number

  // Network (Stage 6)
  min_confidence: number

  // Hub Genes (Stage 7)
  top_n: number
  use_hub_bottleneck: boolean

  // Enrichment (Stage 8)
  fdr_threshold: number
  sources: string[]
}

// Single source of truth: the flat setup-form defaults are derived field-by-field
// from the nested PARAM_DEFAULTS (lib/stage-params.ts), which mirror the backend
// analysis/models.py defaults exactly. Reading from PARAM_DEFAULTS prevents drift
// (e.g. min_assay_confidence must be 7 — the backend/stage default — not 0).
export const DEFAULT_PARAMS: AdvancedParams = {
  // ADME (Stage 2)
  max_mw: PARAM_DEFAULTS.adme.max_mw as number,
  max_logp: PARAM_DEFAULTS.adme.max_logp as number,
  max_hbd: PARAM_DEFAULTS.adme.max_hbd as number,
  max_hba: PARAM_DEFAULTS.adme.max_hba as number,
  max_tpsa: PARAM_DEFAULTS.adme.max_tpsa as number,
  max_rotatable_bonds: PARAM_DEFAULTS.adme.max_rotatable_bonds as number,
  apply_veber: PARAM_DEFAULTS.adme.apply_veber as boolean,
  apply_pains: PARAM_DEFAULTS.adme.apply_pains as boolean,
  np_exception_threshold: PARAM_DEFAULTS.adme.np_exception_threshold as number,
  apply_adme_to_manual: PARAM_DEFAULTS.adme.apply_adme_to_manual as boolean,

  // Targets (Stage 3)
  min_pchembl: PARAM_DEFAULTS.target.min_pchembl as number,
  human_only: PARAM_DEFAULTS.target.human_only as boolean,
  min_assay_confidence: PARAM_DEFAULTS.target.min_assay_confidence as number,

  // Disease Targets (Stage 4)
  min_score: PARAM_DEFAULTS.disease_targets.min_score as number,

  // Network (Stage 6)
  min_confidence: PARAM_DEFAULTS.ppi.min_confidence as number,

  // Hub Genes (Stage 7)
  top_n: PARAM_DEFAULTS.hub_genes.top_n as number,
  use_hub_bottleneck: PARAM_DEFAULTS.hub_genes.use_hub_bottleneck as boolean,

  // Enrichment (Stage 8)
  fdr_threshold: PARAM_DEFAULTS.enrichment.fdr_threshold as number,
  sources: PARAM_DEFAULTS.enrichment.sources as string[],
}

const PATHWAY_SOURCES = ['GO:BP', 'GO:MF', 'GO:CC', 'KEGG'] as const

// STRING confidence presets (Szklarczyk et al., Nucleic Acids Res. 2023)
const STRING_CONFIDENCE_PRESETS = [
  { label: 'Low', value: 0.15 },
  { label: 'Medium', value: 0.4 },
  { label: 'High', value: 0.7 },
  { label: 'Highest', value: 0.9 },
] as const

// ============================================================================
// Sub-components
// ============================================================================

interface NumberFieldProps {
  label: string
  value: number
  onChange: (v: number) => void
  step?: number
  min?: number
}

function NumberField({ label, value, onChange, step = 1, min }: NumberFieldProps) {
  return (
    <div className="flex items-center justify-between gap-4">
      <label className="text-sm text-hf-fg2 flex-1">{label}</label>
      <Input
        type="number"
        value={value}
        step={step}
        min={min}
        onChange={(e) => {
          const parsed = parseFloat(e.target.value)
          if (!isNaN(parsed)) onChange(parsed)
        }}
        className="w-28 h-8 text-sm border-hf-border bg-hf-surface text-hf-fg1 rounded-sm"
      />
    </div>
  )
}

interface CheckboxFieldProps {
  label: string
  value: boolean
  onChange: (v: boolean) => void
}

function CheckboxField({ label, value, onChange }: CheckboxFieldProps) {
  return (
    <div className="flex items-center gap-2">
      <input
        type="checkbox"
        checked={value}
        onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4 rounded-sm border-hf-border accent-hf-sage"
        id={`checkbox-${label.replace(/\s+/g, '-').toLowerCase()}`}
      />
      <label
        htmlFor={`checkbox-${label.replace(/\s+/g, '-').toLowerCase()}`}
        className="text-sm text-hf-fg2 cursor-pointer"
      >
        {label}
      </label>
    </div>
  )
}

interface StringConfidenceSelectorProps {
  value: number
  onChange: (v: number) => void
}

function StringConfidenceSelector({ value, onChange }: StringConfidenceSelectorProps) {
  return (
    <div className="flex items-center justify-between gap-4">
      <label className="text-sm text-hf-fg2 flex-1">STRING confidence</label>
      <div className="flex gap-1" role="group" aria-label="STRING confidence preset">
        {STRING_CONFIDENCE_PRESETS.map((preset) => {
          const isActive = value === preset.value
          return (
            <button
              key={preset.label}
              type="button"
              onClick={() => onChange(preset.value)}
              aria-pressed={isActive}
              className={`px-2 py-1 rounded-sm text-xs border transition-colors ${
                isActive
                  ? 'bg-hf-fg1 text-white border-hf-fg1'
                  : 'bg-hf-surface text-hf-fg2 border-hf-border hover:border-hf-border-strong'
              }`}
            >
              {preset.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}

// ============================================================================
// Main component
// ============================================================================

interface AdvancedParametersProps {
  value: AdvancedParams
  onChange: (params: AdvancedParams) => void
}

export function AdvancedParameters({ value, onChange }: AdvancedParametersProps) {
  function set<K extends keyof AdvancedParams>(key: K, v: AdvancedParams[K]) {
    onChange({ ...value, [key]: v })
  }

  function toggleSource(source: string) {
    const current = value.sources
    if (current.includes(source)) {
      onChange({ ...value, sources: current.filter((s) => s !== source) })
    } else {
      onChange({ ...value, sources: [...current, source] })
    }
  }

  return (
    <div className="rounded-lg bg-hf-surface border border-hf-border px-4">
      <Accordion type="multiple">
        {/* ADME Screening */}
        <AccordionItem value="adme">
          <AccordionTrigger className="text-sm text-hf-fg1">
            ADME Screening
          </AccordionTrigger>
          <AccordionContent>
            <div className="flex flex-col gap-3 pt-1">
              <NumberField
                label="Max molecular weight (Da)"
                value={value.max_mw}
                onChange={(v) => set('max_mw', v)}
                min={0}
              />
              <NumberField
                label="Max LogP"
                value={value.max_logp}
                onChange={(v) => set('max_logp', v)}
                step={0.1}
              />
              <NumberField
                label="Max H-bond donors"
                value={value.max_hbd}
                onChange={(v) => set('max_hbd', v)}
                min={0}
              />
              <NumberField
                label="Max H-bond acceptors"
                value={value.max_hba}
                onChange={(v) => set('max_hba', v)}
                min={0}
              />
              <NumberField
                label="Max TPSA (Å²)"
                value={value.max_tpsa}
                onChange={(v) => set('max_tpsa', v)}
                min={0}
              />
              <NumberField
                label="Max rotatable bonds"
                value={value.max_rotatable_bonds}
                onChange={(v) => set('max_rotatable_bonds', v)}
                min={0}
              />
              <NumberField
                label="NP exception threshold"
                value={value.np_exception_threshold}
                onChange={(v) => set('np_exception_threshold', v)}
                step={0.05}
                min={0}
              />
              <CheckboxField
                label="Apply Veber rules"
                value={value.apply_veber}
                onChange={(v) => set('apply_veber', v)}
              />
              <CheckboxField
                label="Flag PAINS (pan-assay interference compounds)"
                value={value.apply_pains}
                onChange={(v) => set('apply_pains', v)}
              />
              <CheckboxField
                label="Apply ADME screening to manually added compounds"
                value={value.apply_adme_to_manual}
                onChange={(v) => set('apply_adme_to_manual', v)}
              />
            </div>
          </AccordionContent>
        </AccordionItem>

        {/* Target Identification */}
        <AccordionItem value="targets">
          <AccordionTrigger className="text-sm text-hf-fg1">
            Target Identification
          </AccordionTrigger>
          <AccordionContent>
            <div className="flex flex-col gap-3 pt-1">
              <NumberField
                label="Min pChEMBL value"
                value={value.min_pchembl}
                onChange={(v) => set('min_pchembl', v)}
                step={0.1}
                min={0}
              />
              <CheckboxField
                label="Human targets only"
                value={value.human_only}
                onChange={(v) => set('human_only', v)}
              />
              <NumberField
                label="Min assay confidence (0–9)"
                value={value.min_assay_confidence}
                onChange={(v) => set('min_assay_confidence', Math.round(v))}
                step={1}
                min={0}
              />
            </div>
          </AccordionContent>
        </AccordionItem>

        {/* Disease Targets */}
        <AccordionItem value="disease-targets">
          <AccordionTrigger className="text-sm text-hf-fg1">
            Disease Targets
          </AccordionTrigger>
          <AccordionContent>
            <div className="flex flex-col gap-3 pt-1">
              <NumberField
                label="Min association score"
                value={value.min_score}
                onChange={(v) => set('min_score', v)}
                step={0.05}
                min={0}
              />
            </div>
          </AccordionContent>
        </AccordionItem>

        {/* Network */}
        <AccordionItem value="network">
          <AccordionTrigger className="text-sm text-hf-fg1">
            Network
          </AccordionTrigger>
          <AccordionContent>
            <div className="flex flex-col gap-3 pt-1">
              <StringConfidenceSelector
                value={value.min_confidence}
                onChange={(v) => set('min_confidence', v)}
              />
            </div>
          </AccordionContent>
        </AccordionItem>

        {/* Hub Genes */}
        <AccordionItem value="hub-genes">
          <AccordionTrigger className="text-sm text-hf-fg1">
            Hub Genes
          </AccordionTrigger>
          <AccordionContent>
            <div className="flex flex-col gap-3 pt-1">
              <NumberField
                label="Top N hub genes"
                value={value.top_n}
                onChange={(v) => set('top_n', Math.round(v))}
                min={1}
              />
              <CheckboxField
                label="Use hub+bottleneck composite scoring"
                value={value.use_hub_bottleneck}
                onChange={(v) => set('use_hub_bottleneck', v)}
              />
            </div>
          </AccordionContent>
        </AccordionItem>

        {/* Pathway Enrichment */}
        <AccordionItem value="enrichment" className="border-b-0">
          <AccordionTrigger className="text-sm text-hf-fg1">
            Pathway Enrichment
          </AccordionTrigger>
          <AccordionContent>
            <div className="flex flex-col gap-3 pt-1">
              <NumberField
                label="FDR threshold"
                value={value.fdr_threshold}
                onChange={(v) => set('fdr_threshold', v)}
                step={0.01}
                min={0.001}
              />
              <div className="flex flex-col gap-2">
                <span className="text-sm text-hf-fg2">Sources</span>
                <div className="flex flex-wrap gap-3">
                  {PATHWAY_SOURCES.map((source) => (
                    <div key={source} className="flex items-center gap-1.5">
                      <input
                        type="checkbox"
                        id={`source-${source}`}
                        checked={value.sources.includes(source)}
                        onChange={() => toggleSource(source)}
                        className="h-4 w-4 rounded-sm border-hf-border accent-hf-sage"
                      />
                      <label
                        htmlFor={`source-${source}`}
                        className="text-sm text-hf-fg2 cursor-pointer font-mono"
                      >
                        {source}
                      </label>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </div>
  )
}
