// Fixture data matching the backend API schemas exactly.
import type { PlantResponse, DiseaseResponse } from '@/types/api'

export const plantsFixture: PlantResponse[] = [
  {
    plant_id: 'pl_knapsack_C00001234',
    canonical_scientific_name: 'Andrographis paniculata',
    family_name: 'Acanthaceae',
    compound_count: 42,
    plant_aliases: [],
  },
  {
    plant_id: 'pl_knapsack_C00005678',
    canonical_scientific_name: 'Curcuma longa',
    family_name: 'Zingiberaceae',
    compound_count: 87,
    plant_aliases: [],
  },
]

export const diseasesFixture: DiseaseResponse[] = [
  {
    disease_id: 'dtg_mondo_0005148',
    disease_name: 'type 2 diabetes mellitus',
    ontology_id: 'MONDO:0005148',
    ontology_source: 'mondo',
    disease_aliases: [],
  },
  {
    disease_id: 'dtg_mondo_0004981',
    disease_name: 'atrial fibrillation',
    ontology_id: 'MONDO:0004981',
    ontology_source: 'mondo',
    disease_aliases: [],
  },
]

export const analysisFixture = {
  analysis_id: 'test-id-1',
  analysis_name: 'Andrographis × T2D — 2026-05-19',
  mode: 'guided',
  status: 'stage_3_awaiting_approval',
  current_stage: 3,
  created_at: '2026-05-19T10:00:00Z',
  updated_at: '2026-05-19T10:05:00Z',
  plant_ids: ['pl_knapsack_C00001234'],
  disease_id: 'dtg_mondo_0005148',
  parameters: {},
  stage_results: {
    stage_1: {
      total_compounds: 42,
      plants_covered: 1,
      compounds: [],
    },
    stage_2: {
      passed: 30,
      failed: 12,
      np_exceptions: 3,
      compounds: [],
    },
    stage_3: {
      target_count: 18,
      coverage_pct: 85.7,
      targets: [],
      compound_sources: {
        'mock-uncovered-1': [],
        'mock-uncovered-2': [],
      },
      uncovered_compounds: [
        {
          compound_id: 'mock-uncovered-1',
          canonical_name: 'Quercetin',
          smiles: 'OC1=CC=CC(O)=C1O',
        },
        {
          compound_id: 'mock-uncovered-2',
          canonical_name: 'Kaempferol',
          smiles: null,
        },
      ],
    },
    stage_4: null,
    stage_5: {
      compound_only_count: 24,
      overlap_count: 18,
      disease_only_count: 42,
      jaccard_index: 0.214,
      p_value: 0.0023,
      overlap_genes: [
        'TP53', 'AKT1', 'EGFR', 'VEGFA', 'TNF',
        'IL6', 'CASP3', 'BCL2', 'MYC', 'CCND1',
        'CDK2', 'MAPK1', 'PIK3CA', 'PTEN', 'MTOR',
        'HSP90AA1', 'STAT3', 'NF1'
      ],
    },
    stage_6: {
      node_count: 12,
      edge_count: 18,
      nodes: [
        { data: { id: 'TP53', label: 'TP53', type: 'hub', degree: 8 } },
        { data: { id: 'AKT1', label: 'AKT1', type: 'hub', degree: 6 } },
        { data: { id: 'EGFR', label: 'EGFR', type: 'overlap', degree: 5 } },
        { data: { id: 'VEGFA', label: 'VEGFA', type: 'overlap', degree: 4 } },
        { data: { id: 'TNF', label: 'TNF', type: 'overlap', degree: 4 } },
        { data: { id: 'IL6', label: 'IL6', type: 'other', degree: 3 } },
        { data: { id: 'CASP3', label: 'CASP3', type: 'other', degree: 3 } },
        { data: { id: 'BCL2', label: 'BCL2', type: 'other', degree: 2 } },
        { data: { id: 'MYC', label: 'MYC', type: 'other', degree: 2 } },
        { data: { id: 'CCND1', label: 'CCND1', type: 'other', degree: 2 } },
        { data: { id: 'CDK2', label: 'CDK2', type: 'other', degree: 2 } },
        { data: { id: 'MAPK1', label: 'MAPK1', type: 'other', degree: 2 } },
      ],
      edges: [
        { data: { id: 'e1', source: 'TP53', target: 'AKT1', weight: 4, combined_score: 0.9 } },
        { data: { id: 'e2', source: 'TP53', target: 'EGFR', weight: 3, combined_score: 0.8 } },
        { data: { id: 'e3', source: 'TP53', target: 'BCL2', weight: 5, combined_score: 0.95 } },
        { data: { id: 'e4', source: 'TP53', target: 'CASP3', weight: 3, combined_score: 0.75 } },
        { data: { id: 'e5', source: 'AKT1', target: 'VEGFA', weight: 4, combined_score: 0.85 } },
        { data: { id: 'e6', source: 'AKT1', target: 'EGFR', weight: 3, combined_score: 0.7 } },
        { data: { id: 'e7', source: 'AKT1', target: 'MYC', weight: 2, combined_score: 0.6 } },
        { data: { id: 'e8', source: 'EGFR', target: 'VEGFA', weight: 3, combined_score: 0.72 } },
        { data: { id: 'e9', source: 'EGFR', target: 'TNF', weight: 2, combined_score: 0.65 } },
        { data: { id: 'e10', source: 'TNF', target: 'IL6', weight: 4, combined_score: 0.88 } },
        { data: { id: 'e11', source: 'TNF', target: 'CASP3', weight: 3, combined_score: 0.76 } },
        { data: { id: 'e12', source: 'BCL2', target: 'CASP3', weight: 4, combined_score: 0.82 } },
        { data: { id: 'e13', source: 'MYC', target: 'CCND1', weight: 3, combined_score: 0.78 } },
        { data: { id: 'e14', source: 'MYC', target: 'CDK2', weight: 2, combined_score: 0.61 } },
        { data: { id: 'e15', source: 'CCND1', target: 'CDK2', weight: 3, combined_score: 0.73 } },
        { data: { id: 'e16', source: 'VEGFA', target: 'MAPK1', weight: 2, combined_score: 0.58 } },
        { data: { id: 'e17', source: 'MAPK1', target: 'EGFR', weight: 2, combined_score: 0.62 } },
        { data: { id: 'e18', source: 'IL6', target: 'MAPK1', weight: 2, combined_score: 0.55 } },
      ],
    },
    stage_7: {
      hub_genes: [
        { rank: 1, gene_symbol: 'TP53', degree: 8, betweenness_centrality: 0.4521, closeness_centrality: 0.7234, eigenvector_centrality: 0.9812, is_hub: true, is_bottleneck: true },
        { rank: 2, gene_symbol: 'AKT1', degree: 6, betweenness_centrality: 0.3214, closeness_centrality: 0.6891, eigenvector_centrality: 0.8743, is_hub: true, is_bottleneck: false },
        { rank: 3, gene_symbol: 'EGFR', degree: 5, betweenness_centrality: 0.2876, closeness_centrality: 0.6543, eigenvector_centrality: 0.7654, is_hub: true, is_bottleneck: false },
        { rank: 4, gene_symbol: 'VEGFA', degree: 4, betweenness_centrality: 0.1987, closeness_centrality: 0.6012, eigenvector_centrality: 0.6543, is_hub: true, is_bottleneck: false },
        { rank: 5, gene_symbol: 'TNF', degree: 4, betweenness_centrality: 0.1765, closeness_centrality: 0.5987, eigenvector_centrality: 0.6234, is_hub: true, is_bottleneck: false },
        { rank: 6, gene_symbol: 'IL6', degree: 3, betweenness_centrality: 0.0987, closeness_centrality: 0.5234, eigenvector_centrality: 0.4321, is_hub: false, is_bottleneck: false },
        { rank: 7, gene_symbol: 'CASP3', degree: 3, betweenness_centrality: 0.0876, closeness_centrality: 0.5123, eigenvector_centrality: 0.4123, is_hub: false, is_bottleneck: false },
        { rank: 8, gene_symbol: 'BCL2', degree: 2, betweenness_centrality: 0.0543, closeness_centrality: 0.4567, eigenvector_centrality: 0.3456, is_hub: false, is_bottleneck: false },
        { rank: 9, gene_symbol: 'MYC', degree: 2, betweenness_centrality: 0.0432, closeness_centrality: 0.4321, eigenvector_centrality: 0.3234, is_hub: false, is_bottleneck: false },
        { rank: 10, gene_symbol: 'CCND1', degree: 2, betweenness_centrality: 0.0321, closeness_centrality: 0.4123, eigenvector_centrality: 0.2987, is_hub: false, is_bottleneck: false },
        { rank: 11, gene_symbol: 'CDK2', degree: 2, betweenness_centrality: 0.0234, closeness_centrality: 0.3987, eigenvector_centrality: 0.2765, is_hub: false, is_bottleneck: false },
        { rank: 12, gene_symbol: 'MAPK1', degree: 2, betweenness_centrality: 0.0198, closeness_centrality: 0.3876, eigenvector_centrality: 0.2543, is_hub: false, is_bottleneck: false },
      ],
      threshold_degree: 4,
      threshold_betweenness: 0.15,
    },
    stage_8: {
      significant_count: 24,
      terms: [
        // GO:BP
        { term_id: 'GO:0006915', term_name: 'apoptotic process', source: 'GO:BP', p_value: 0.00001, fdr: 0.00023, intersection_size: 12, gene_list: ['TP53', 'BCL2', 'CASP3', 'AKT1', 'TNF', 'MYC', 'VEGFA', 'IL6', 'CCND1', 'CDK2', 'EGFR', 'MAPK1'] },
        { term_id: 'GO:0008283', term_name: 'cell population proliferation', source: 'GO:BP', p_value: 0.00003, fdr: 0.00045, intersection_size: 10, gene_list: ['TP53', 'MYC', 'CCND1', 'CDK2', 'EGFR', 'AKT1', 'VEGFA', 'MAPK1', 'TNF', 'IL6'] },
        { term_id: 'GO:0042981', term_name: 'regulation of apoptotic process', source: 'GO:BP', p_value: 0.00005, fdr: 0.00067, intersection_size: 9, gene_list: ['TP53', 'BCL2', 'AKT1', 'TNF', 'CASP3', 'MYC', 'IL6', 'VEGFA', 'EGFR'] },
        { term_id: 'GO:0016049', term_name: 'cell growth', source: 'GO:BP', p_value: 0.0001, fdr: 0.0012, intersection_size: 8, gene_list: ['MYC', 'CCND1', 'CDK2', 'EGFR', 'AKT1', 'VEGFA', 'TP53', 'MAPK1'] },
        { term_id: 'GO:0007165', term_name: 'signal transduction', source: 'GO:BP', p_value: 0.0002, fdr: 0.0021, intersection_size: 11, gene_list: ['EGFR', 'AKT1', 'MAPK1', 'VEGFA', 'TNF', 'IL6', 'TP53', 'MYC', 'CCND1', 'CDK2', 'BCL2'] },
        { term_id: 'GO:0006954', term_name: 'inflammatory response', source: 'GO:BP', p_value: 0.0003, fdr: 0.003, intersection_size: 7, gene_list: ['TNF', 'IL6', 'EGFR', 'AKT1', 'CASP3', 'TP53', 'MAPK1'] },
        // GO:MF
        { term_id: 'GO:0004672', term_name: 'protein kinase activity', source: 'GO:MF', p_value: 0.00002, fdr: 0.00034, intersection_size: 8, gene_list: ['EGFR', 'AKT1', 'CDK2', 'MAPK1', 'CCND1', 'MYC', 'TP53', 'IL6'] },
        { term_id: 'GO:0005515', term_name: 'protein binding', source: 'GO:MF', p_value: 0.0001, fdr: 0.0011, intersection_size: 12, gene_list: ['TP53', 'AKT1', 'EGFR', 'BCL2', 'CASP3', 'MYC', 'VEGFA', 'TNF', 'IL6', 'CCND1', 'CDK2', 'MAPK1'] },
        { term_id: 'GO:0003700', term_name: 'DNA-binding transcription factor activity', source: 'GO:MF', p_value: 0.0004, fdr: 0.004, intersection_size: 5, gene_list: ['TP53', 'MYC', 'IL6', 'VEGFA', 'TNF'] },
        // GO:CC
        { term_id: 'GO:0005654', term_name: 'nucleoplasm', source: 'GO:CC', p_value: 0.0001, fdr: 0.0013, intersection_size: 9, gene_list: ['TP53', 'MYC', 'CCND1', 'CDK2', 'AKT1', 'EGFR', 'BCL2', 'CASP3', 'MAPK1'] },
        { term_id: 'GO:0005886', term_name: 'plasma membrane', source: 'GO:CC', p_value: 0.0002, fdr: 0.0022, intersection_size: 8, gene_list: ['EGFR', 'AKT1', 'TNF', 'IL6', 'VEGFA', 'BCL2', 'CASP3', 'MAPK1'] },
        { term_id: 'GO:0016020', term_name: 'membrane', source: 'GO:CC', p_value: 0.0005, fdr: 0.005, intersection_size: 7, gene_list: ['EGFR', 'BCL2', 'TNF', 'IL6', 'VEGFA', 'AKT1', 'MAPK1'] },
        // KEGG
        { term_id: 'hsa05200', term_name: 'Pathways in cancer', source: 'KEGG', p_value: 0.000001, fdr: 0.00002, intersection_size: 12, gene_list: ['TP53', 'AKT1', 'EGFR', 'BCL2', 'MYC', 'VEGFA', 'CASP3', 'CCND1', 'CDK2', 'MAPK1', 'TNF', 'IL6'] },
        { term_id: 'hsa04151', term_name: 'PI3K-Akt signaling pathway', source: 'KEGG', p_value: 0.000005, fdr: 0.00008, intersection_size: 9, gene_list: ['AKT1', 'EGFR', 'TP53', 'VEGFA', 'MYC', 'CCND1', 'CDK2', 'MAPK1', 'BCL2'] },
        { term_id: 'hsa04010', term_name: 'MAPK signaling pathway', source: 'KEGG', p_value: 0.00002, fdr: 0.00031, intersection_size: 7, gene_list: ['EGFR', 'MAPK1', 'AKT1', 'TNF', 'IL6', 'TP53', 'MYC'] },
        { term_id: 'hsa04064', term_name: 'NF-kappa B signaling pathway', source: 'KEGG', p_value: 0.00005, fdr: 0.00072, intersection_size: 6, gene_list: ['TNF', 'IL6', 'AKT1', 'BCL2', 'CASP3', 'TP53'] },
        { term_id: 'hsa04115', term_name: 'p53 signaling pathway', source: 'KEGG', p_value: 0.0001, fdr: 0.0014, intersection_size: 8, gene_list: ['TP53', 'BCL2', 'CASP3', 'CCND1', 'CDK2', 'AKT1', 'MYC', 'MAPK1'] },
        { term_id: 'hsa04068', term_name: 'FoxO signaling pathway', source: 'KEGG', p_value: 0.0003, fdr: 0.0038, intersection_size: 5, gene_list: ['AKT1', 'TP53', 'EGFR', 'CCND1', 'IL6'] },
      ],
    },
  },
  error_message: null,
}

export const statusFixture = {
  analysis_id: 'test-id-1',
  status: 'stage_3_awaiting_approval',
  current_stage: 3,
  stage_statuses: {
    '1': 'complete',
    '2': 'complete',
    '3': 'awaiting_approval',
    '4': 'pending',
    '5': 'pending',
    '6': 'pending',
    '7': 'pending',
    '8': 'pending',
  },
  error_message: null,
  elapsed_seconds: 45.2,
}
