/**
 * Manifest of every backend HTTP route (veyra/backend/http_api/app.py),
 * verified against veyra/midend.md. Powers the raw-analysis console —
 * the frontend's complete, generic access to the deterministic backend
 * (VEYRA_FRONTEND_MIDEND_PLAN.md §2/§7A "raw backend" surface). The
 * MIDEND (AI-orchestration) surface is a separate, not-yet-built layer.
 */

export interface BackendEndpoint {
  method: "GET" | "POST";
  path: string;
  category: string;
  description: string;
  /** Example request body (POST) or path already filled with a sample ID (GET with {param}). */
  exampleBody?: Record<string, unknown>;
  needsGenome?: boolean;
}

export const BACKEND_ENDPOINTS: BackendEndpoint[] = [
  { method: "GET", path: "/health", category: "Infrastructure", description: "Service health check." },
  {
    method: "POST",
    path: "/ingest",
    category: "Ingestion",
    description: "Parse a FASTA/FASTQ/GenBank file already present on the backend host.",
    exampleBody: { input_path: "example.fasta", pam_scan: false },
  },
  {
    method: "POST",
    path: "/pam/scan",
    category: "PAM Discovery",
    description: "Scan a raw sequence for PAM sites on both strands.",
    exampleBody: { sequence: "ACGTGACCTGAGGCTGATCCGTAGGCTAGCTAGG", pam_pattern: "NGG" },
  },
  {
    method: "POST",
    path: "/pam/scan-region",
    category: "PAM Discovery",
    description: "Scan a genomic coordinate range for PAM sites.",
    exampleBody: { genome_id: "example_genome", chrom: "chr1", start: 1000, end: 2000 },
    needsGenome: true,
  },
  {
    method: "POST",
    path: "/index/build",
    category: "Off-Target Indexing",
    description: "Build/retrieve the BWA index for a registered genome.",
    exampleBody: { genome_id: "example_genome" },
    needsGenome: true,
  },
  {
    method: "POST",
    path: "/offtarget/search",
    category: "Off-Target Search",
    description: "Genome-wide off-target search (BWA or Cas-OFFinder).",
    exampleBody: { spacer_sequence: "GACCTGAGGCTGATCCGTAG", genome_id: "example_genome", backend: "bwa" },
    needsGenome: true,
  },
  {
    method: "POST",
    path: "/offtarget/score",
    category: "Off-Target Scoring",
    description: "CFD-score a list of candidate off-target sites.",
    exampleBody: {
      spacer_sequence: "GACCTGAGGCTGATCCGTAG",
      candidates: [{ protospacer: "GACCTGAGGCTGATCCGTAG", pam: "CGG" }],
    },
  },
  {
    method: "POST",
    path: "/offtarget/analyze-seed",
    category: "Off-Target Scoring",
    description: "Classify mismatch positions between a spacer and a candidate (seed vs distal).",
    exampleBody: { spacer_sequence: "GACCTGAGGCTGATCCGTAG", candidate_sequence: "GACCTGAGGCTGATCCGTAC" },
  },
  {
    method: "POST",
    path: "/rank",
    category: "Ranking",
    description: "Rank guide candidates by composite/off-target/on-target criteria.",
    exampleBody: { guides: [{ id: "g1", sequence: "GACCTGAGGCTGATCCGTAG" }], sort_by: "composite" },
  },
  { method: "GET", path: "/genomes", category: "Genome Registry", description: "List registered reference genomes." },
  {
    method: "GET",
    path: "/genomes/example_genome",
    category: "Genome Registry",
    description: "Metadata for one registered genome (edit the id in the path).",
    needsGenome: true,
  },
  { method: "GET", path: "/cache/status", category: "Cache", description: "SQLite cache hit/miss statistics." },
  {
    method: "POST",
    path: "/cache/clear",
    category: "Cache",
    description: "Clear the disk cache, globally or for one tool.",
    exampleBody: {},
  },
  { method: "GET", path: "/tools", category: "Introspection", description: "List all MCP-registered tools with cost tiers." },
  {
    method: "POST",
    path: "/sequence/gc",
    category: "Sequence Features",
    description: "GC content — overall, sliding window, 5'/3' split.",
    exampleBody: { sequence: "ACGTGACCTGAGGCTGATCCGTAGGCTAGCTAGG" },
  },
  {
    method: "POST",
    path: "/sequence/homopolymer",
    category: "Sequence Features",
    description: "Poly-T/poly-G/poly-A/poly-C run detection.",
    exampleBody: { sequence: "ACGTGACCTGAGGCTGATCCGTAGGCTAGCTAGG" },
  },
  {
    method: "POST",
    path: "/sequence/tm",
    category: "Sequence Features",
    description: "Melting temperature (nearest-neighbor/Wallace).",
    exampleBody: { sequence: "GACCTGAGGCTGATCCGTAG" },
  },
  {
    method: "POST",
    path: "/sequence/secondary-structure",
    category: "Sequence Features",
    description: "MFE secondary structure via ViennaRNA (may be unavailable depending on deployment).",
    exampleBody: { sequence: "GACCTGAGGCTGATCCGTAG" },
  },
  {
    method: "POST",
    path: "/sequence/positional-features",
    category: "Sequence Features",
    description: "One-hot nucleotide encoding + position-20 G-bias check.",
    exampleBody: { sequence: "GACCTGAGGCTGATCCGTAG" },
  },
  {
    method: "POST",
    path: "/sequence/dinucleotide-composition",
    category: "Sequence Features",
    description: "Dinucleotide counts/frequencies/transition matrix.",
    exampleBody: { sequence: "GACCTGAGGCTGATCCGTAG" },
  },
  {
    method: "POST",
    path: "/sequence/seed-gc",
    category: "Sequence Features",
    description: "PAM-proximal seed-region GC content.",
    exampleBody: { sequence: "GACCTGAGGCTGATCCGTAG" },
  },
  {
    method: "POST",
    path: "/sequence/cut-site",
    category: "Sequence Features",
    description: "Canonical cleavage coordinate math (-3bp from PAM).",
    exampleBody: { spacer_start: 10, spacer_length: 20, strand: "+" },
  },
  {
    method: "POST",
    path: "/score/ontarget",
    category: "On-Target Prediction",
    description: "Predict cleavage efficiency (Rule Set 3 / Doench 2014 auto-fallback).",
    exampleBody: { context_sequence: "ACGTGACCTGAGGCTGATCCGTAGGCTAGC", model: "auto" },
  },
  { method: "GET", path: "/models", category: "Model Runtime", description: "List all model runtimes and their status." },
  { method: "GET", path: "/models/doench_2014", category: "Model Runtime", description: "One model's detailed status (edit the id)." },
  {
    method: "POST",
    path: "/models/rule_set_2/setup",
    category: "Model Runtime",
    description: "Provision an isolated venv for a model (expensive; edit the id).",
    exampleBody: {},
  },
  {
    method: "POST",
    path: "/models/doench_2014/verify",
    category: "Model Runtime",
    description: "Run a model's verification test case (edit the id).",
    exampleBody: {},
  },
  { method: "GET", path: "/models/doench_2014/status", category: "Model Runtime", description: "Runtime provisioning state for one model." },
];
