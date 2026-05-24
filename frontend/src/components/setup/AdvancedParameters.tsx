import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { Input } from '@/components/ui/input'

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
  np_exception_threshold: number

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

export const DEFAULT_PARAMS: AdvancedParams = {
  max_mw: 500,
  max_logp: 5,
  max_hbd: 5,
  max_hba: 10,
  max_tpsa: 140,
  max_rotatable_bonds: 10,
  apply_veber: true,
  np_exception_threshold: 0.5,
  min_pchembl: 5.0,
  human_only: true,
  min_assay_confidence: 0,
  min_score: 0.3,
  min_confidence: 0.4,
  top_n: 20,
  use_hub_bottleneck: true,
  fdr_threshold: 0.05,
  sources: ['GO:BP', 'GO:MF', 'GO:CC', 'KEGG'],
}

const PATHWAY_SOURCES = ['GO:BP', 'GO:MF', 'GO:CC', 'KEGG'] as const

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
              <NumberField
                label="Min STRING confidence score"
                value={value.min_confidence}
                onChange={(v) => set('min_confidence', v)}
                step={0.05}
                min={0}
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
                min={0}
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
