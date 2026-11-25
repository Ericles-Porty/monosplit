// Shapes of the JSON payloads built by src/monosplit/api/payloads.py.

export interface GraphStats {
  classes: number;
  edges?: number;
  calls_in_graph?: number;
  isolated_classes?: number;
  [key: string]: number | undefined;
}

export interface AppEntry {
  id: string;
  name: string;
  repository: string | null;
  tag: string | null;
  commit: string | null;
  graph: GraphStats | null;
}

export interface AttemptTotals {
  attempts: number;
  accepted: number;
  invalid: number;
  api_errors: number;
  input_tokens: number | null;
  output_tokens: number | null;
  latency_s: number | null;
  cost_usd: number | null;
}

export interface RunRef {
  run: number;
  k: number;
  attempt: number;
}

export interface VariantSummary extends AttemptTotals {
  variant: string;
  runs: RunRef[];
}

export interface StudyEntry {
  id: string;
  experiment: string;
  app: string;
  profile: string;
  provider: string | null;
  model: string | null;
  temperature: number | null;
  request_options: Record<string, unknown>;
  prompt_template: string | null;
  created_utc: string | null;
  evaluated: boolean;
  ah_selected: string | null;
  has_graph: boolean;
  variants: VariantSummary[];
}

export interface IndexPayload {
  version: string;
  apps: AppEntry[];
  studies: StudyEntry[];
}

export interface ClassInfo {
  id: string;
  simple: string;
  package: string;
  kind: string;
  source: string;
}

export interface Edge {
  source: string;
  target: string;
  calls: number;
}

export interface GraphPayload {
  app: string;
  meta: Record<string, unknown>;
  stats: GraphStats;
  classes: ClassInfo[];
  edges: Edge[];
  layout: { seed: number; positions: Record<string, [number, number]> };
}

export interface ServiceInfo {
  index: number;
  name: string | null;
  classes: string[];
  size: number;
  internal_edges: number;
  internal_calls: number;
  calls_out: number;
  calls_in: number;
  interfaces: string[];
}

export interface MetricValues {
  sm: number | null;
  ifn: number | null;
  icp: number | null;
  ned: number | null;
}

export interface Decomposition {
  method: string;
  seed: number | null;
  k: number;
  metrics: MetricValues;
  services: ServiceInfo[];
  assignment: Record<string, number>;
  interfaces: string[];
  service_edges: { source: number; target: number; edges: number; calls: number }[];
  cross_calls: number;
  cross_edges: number;
}

export interface AttemptRecord {
  attempt: number;
  run: number;
  try: number;
  timestamp_utc: string;
  status: "accepted" | "invalid" | "api_error";
  reason?: string | null;
  detail?: string;
  error?: string;
  k?: number | null;
  model_returned?: string | null;
  finish_reason?: string | null;
  input_tokens?: number | null;
  output_tokens?: number | null;
  reasoning_tokens?: number | null;
  latency_s?: number | null;
  cost_usd?: number | null;
}

export interface Stability {
  runs: number[];
  ari: number[][];
  moved: Record<string, Record<string, string[]>>;
}

export interface StudyVariant {
  variant: string;
  meta: Record<string, unknown>;
  summary: AttemptTotals;
  attempts: AttemptRecord[];
  runs: { run: number; attempt: number; k: number; services: { name: string; size: number }[] }[];
  stability: Stability | null;
}

export interface MetricRow extends MetricValues {
  variant: string;
  run: number | null;
  method: string;
  k: number;
  seed: number | null;
}

export interface StudyPayload {
  id: string;
  experiment: string;
  app: string;
  profile: string;
  evaluated: boolean;
  ah_selected: string | null;
  ah_selection: { variant: string; runs: number; median_sm: number | null; selected: boolean }[];
  variants: StudyVariant[];
  metrics: MetricRow[];
  references: Decomposition[];
}

export interface RunPayload {
  study: string;
  variant: string;
  run: number;
  attempt: AttemptRecord;
  k: number;
  output_text: string;
  prompt_names: Record<string, string>;
  ah_selected: string | null;
  decompositions: Decomposition[];
}

// ---------------------------------------------------------------- configuration (configstore.py)

export interface ClientFieldInfo {
  key: string;
  kind: "text" | "number";
  default: string | number | null;
  required: boolean;
}

export interface ProviderInfo {
  provider: string;
  default_key_env: string | null;
  client_fields: ClientFieldInfo[];
  accepts_temperature: boolean | null;
  request_example: Record<string, unknown>;
  pricing_url: string | null;
  /** False when no call is billed (fake client, local models): runs start without confirmation. */
  paid: boolean;
  /** True when each attempt gets a seed derived from the master seed (the profile seed stays empty). */
  per_attempt_seed: boolean;
}

export interface ProfileData {
  provider: string;
  model: string;
  temperature: number | null;
  max_output_tokens: number | null;
  seed: number | null;
  client: Record<string, string | number>;
  request: Record<string, unknown>;
  pricing: { input_per_mtok?: number | null; output_per_mtok?: number | null; source?: string; accessed?: string };
  note: string;
}

export interface ProfileEntry {
  name: string;
  template: boolean;
  data: ProfileData | null;
  valid: boolean;
  error: string | null;
  key_present?: boolean | null;
  used_by?: string[];
  default_of?: string[];
  updated_utc?: string | null;
  protected?: boolean;
}

export interface ExperimentData {
  name: string;
  app: string;
  seed: number | null;
  accepted_runs: number | null;
  max_retries: number;
  max_failed_runs: number | null;
  variants: string[];
  database: string;
  llm: string | null;
  prompt_template: string;
  ah_variants: string[];
  ah_primary: string;
  hdbscan_min_cluster_size: number;
  inferential: boolean;
  note: string;
}

export interface RunMetaRef {
  database: string;
  experiment: string;
  app: string;
  profile: string;
  variant: string;
  prompt_template: string | null;
  accepted: number;
}

export interface ExperimentEntry {
  id: string;
  data: ExperimentData | null;
  valid: boolean;
  error: string | null;
  runs: RunMetaRef[];
  studies?: string[];
  updated_utc?: string | null;
  protected?: boolean;
}

export interface PromptEntry {
  name: string;
  text: string;
  sha256: string;
  valid: boolean;
  error: string | null;
  used_by: string[];
  set_in?: string[];
  created_utc?: string | null;
  protected?: boolean;
}

export interface AppConfigEntry {
  id: string;
  name: string;
  note: string;
  repository: string;
  tag: string | null;
  commit: string;
  build: string;
  build_args: string[];
  source_roots: string[];
  class_dirs: string[];
  status: { fetched: boolean; build_log: boolean; graph: GraphStats | null; edge_check: boolean };
  studies: string[];
  experiments?: string[];
  updated_utc?: string | null;
  protected?: boolean;
}

export interface ConfigSummary {
  providers: ProviderInfo[];
  variants: string[];
  ah_variants: string[];
  build_types: string[];
  placeholders: string[];
  profiles: ProfileEntry[];
  experiments: ExperimentEntry[];
  prompts: PromptEntry[];
  apps: AppConfigEntry[];
  databases?: string[];
}

// ---------------------------------------------------------------- data page (api/data.py, dataedit.py)

export interface DatabaseInfo {
  name: string;
  main: boolean;
  counts: Record<string, number>;
}

export interface DataStudyVariant {
  variant: string;
  attempts: number;
  accepted: number;
  invalid: number;
  api_errors: number;
}

export interface DataStudy {
  id: string;
  experiment: string;
  app: string;
  profile: string;
  variants: DataStudyVariant[];
  evaluated_utc: string | null;
  note: string;
  note_updated_utc: string | null;
  configs: string[];
  documents: Record<string, number>;
}

export interface AttemptRow {
  experiment: string;
  app: string;
  profile: string;
  variant: string;
  attempt: number;
  run: number | null;
  try: number | null;
  status: string;
  reason: string | null;
  detail: string | null;
  k: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  cost_usd: number | null;
  latency_s: number | null;
  model_returned: string | null;
  timestamp_utc: string | null;
  [field: string]: unknown;
}

export interface AttemptPage {
  database: string;
  rows: AttemptRow[];
  total: number;
  skip: number;
  limit: number;
}

export interface AttemptDetail extends AttemptRow {
  database: string;
  raw: { text?: string; raw?: unknown; [field: string]: unknown } | null;
  accepted: { run: number; k: number; services: string[]; partition: { class: string; service: number }[] } | null;
}

export interface EdgeCheckRow {
  row: number;
  caller: string;
  callee: string;
  calls: number | null;
  call_sites: string;
  confirmed: "" | "yes" | "no";
  notes: string;
}

export interface EdgeCheck {
  app: string;
  name: string;
  commit: string | null;
  rows: EdgeCheckRow[];
  meta: { n?: number; seed?: number; created_utc?: string } | null;
  sampled: boolean;
  summary: { yes: number; no: number; unchecked: number };
}

export interface AuditEntry {
  id: string;
  utc: string;
  action: string;
  collection: string;
  target: string;
  source: string;
  before: unknown;
  after: unknown;
  detail: string | null;
}

export interface AuditPage {
  database: string;
  rows: AuditEntry[];
  total: number;
  skip: number;
  limit: number;
}

// ---------------------------------------------------------------- execution (estimate.py, api/jobs.py)

export interface EstimateRow {
  variant: string;
  accepted: number;
  target: number;
  missing: number;
  attempts_so_far: number;
  failed_runs: number;
  observed: boolean;
  input_tokens_per_attempt: number;
  output_tokens_per_attempt: number;
  output_cap: number;
  expected_attempts: number;
  max_attempts: number;
  expected_cost_usd: number | null;
  max_cost_usd: number | null;
  /** Mean time of the earlier answered attempts; null before the first one. */
  seconds_per_attempt: number | null;
  expected_seconds: number | null;
}

export interface Estimate {
  experiment: string;
  app: string;
  profile: string;
  provider: string;
  model: string;
  /** False when no call is billed: the job starts without confirmation. */
  paid: boolean;
  /** Why the model cannot be served now (local server down, model not downloaded); null when it can. */
  problem: string | null;
  priced: boolean;
  key_present: boolean | null;
  variants: EstimateRow[];
  missing_runs: number;
  expected_cost_usd: number | null;
  max_cost_usd: number | null;
  expected_seconds: number | null;
  defaults: { output_tokens: number; attempts_per_run: number };
  token: string;
}

export interface JobProgress {
  accepted: number;
  target: number;
  attempts: number;
  failed_runs: number;
  last: { attempt?: number; run?: number; status?: string; reason?: string | null; k?: number | null } | null;
}

export interface Job {
  id: string;
  kind: string;
  params: Record<string, unknown>;
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  created_utc: string;
  started_utc: string | null;
  finished_utc: string | null;
  progress: Record<string, JobProgress>;
  cost_usd: number;
  log: string[];
  result: Record<string, unknown> | null;
  error: string | null;
  cancel_requested: boolean;
}

// ---------------------------------------------------------------- results/<experiment>/<profile>

export type MetricKey = "sm" | "ifn" | "icp" | "ned";
export type ControlKey = "ah" | "random";

/** n, median, quartiles (numpy's linear interpolation), IQR, min and max, as in report.md. */
export interface Summary {
  n: number;
  median: number;
  q1: number;
  q3: number;
  iqr: number;
  min: number;
  max: number;
}

export interface ResultMetricRow extends MetricValues {
  app: string;
  variant: string | null;
  run: number | null;
  method: string;
  k: number;
  seed: number | null;
  noise_points: number | null;
}

export interface MetricSummary extends Summary {
  app: string;
  variant: string;
  method: string;
  metric: "k" | MetricKey;
}

export interface DifferenceRow {
  app: string;
  variant: string;
  run: number;
  control: ControlKey;
  control_method: string;
  k: number;
  d_sm: number | null;
  d_ifn: number | null;
  d_icp: number | null;
  d_ned: number | null;
}

export interface DifferenceSummary extends Summary {
  scope: string;
  variant: string;
  control: ControlKey;
  metric: MetricKey;
  positive: number;
  negative: number;
  zero: number;
}

export interface Comparison {
  control: ControlKey;
  metric: MetricKey;
  n: number;
  n_nonzero: number | null;
  normality_p: number | null;
  normal: boolean | null;
  test: "wilcoxon" | "t" | "none" | "insufficient";
  statistic: number | null;
  p_value: number | null;
  p_holm: number | null;
  significant: boolean;
  median_diff: number | null;
  mean_diff: number | null;
  cliffs_delta: number | null;
  magnitude: "negligible" | "small" | "medium" | "large" | null;
  favours: "llm" | "control" | "none";
}

export interface CriterionResult {
  sm_favours_llm: boolean;
  sm_effect_at_least_small: boolean;
  no_unfavourable_ifn_icp: boolean;
  no_unfavourable_ned: boolean;
  /** Criterion adopted for the full experiment: conditions (i) to (iv). */
  llm_superior: boolean;
  /** Criterion of the roteiro: conditions (i) to (iii), reported beside it. */
  llm_superior_roteiro: boolean;
}

export interface TestSet {
  scope: string;
  variant: string;
  apps: string[];
  comparisons: Comparison[];
  criterion: Partial<Record<ControlKey, CriterionResult | null>>;
}

export interface StabilityRow {
  variant: string;
  runs: number;
  distinct_partitions: number;
  groups_of_runs: string;
  mean_ari: number | null;
  min_ari: number | null;
}

export interface AttemptSummaryRow {
  variant: string;
  attempts: number;
  accepted: number;
  invalid: number;
  invalid_reasons: string;
  api_errors: number;
  k_accepted: string;
  input_tokens: number | null;
  output_tokens: number | null;
  latency_s: number | null;
  cost_usd: number | null;
  recorded_tokens: number;
  recorded_cost: number;
  stability: StabilityRow | null;
}

export interface ResultApp {
  app: string;
  name: string;
  graph: GraphStats | null;
  evaluated: boolean;
  ah_selected: string | null;
  ah_selection: { variant: string; runs: number; median_sm: number | null; selected: boolean; rule: string }[];
  variants: AttemptSummaryRow[];
}

export interface ResultsPayload {
  id: string;
  experiment: string;
  profile: string;
  provider: string | null;
  model: string | null;
  temperature: number | null;
  request_options: Record<string, unknown>;
  prompt_template: string | null;
  fake: boolean;
  analysis: { inferential: boolean; configs: string[]; alpha: number; direction: Record<MetricKey, 1 | -1> };
  variants: string[];
  scopes: string[];
  apps: ResultApp[];
  metrics: ResultMetricRow[];
  metric_summaries: MetricSummary[];
  differences: DifferenceRow[];
  difference_summaries: DifferenceSummary[];
  tests: TestSet[] | null;
}
