type AppConfig = {
  appName: string;
  dataEndpoint: string;
  runId: string;
};

function getConfig(): AppConfig {
  const apiUrl = import.meta.env.VITE_API_URL || "http://localhost:5000";
  return (window as any).__APP_CONFIG__ || {
    appName: "terrapulse",
    dataEndpoint: `${apiUrl}/rpc`,
    runId: "local-dev"
  };
}

type RpcParams = {
  func: string;
  args?: Record<string, any>;
  module?: string;
};

function getUserFacingErrorMessage(status: number): string {
  if (status === 401) return "Authentication required. Please sign in again.";
  if (status === 403) return "You do not have access to this app workspace.";
  if (status === 404) return "Requested app resource was not found.";
  if (status >= 500) return "Server error while loading app data. Please try again.";
  return "Request failed. Please try again.";
}

function cacheKey(func: string, args: Record<string, any>, module: string): string {
  return `rpc:${module}:${func}:${JSON.stringify(args)}`;
}

function getCached<T>(key: string): T | undefined {
  try {
    const raw = sessionStorage.getItem(key);
    if (!raw) return undefined;
    return JSON.parse(raw) as T;
  } catch {
    return undefined;
  }
}

function setCache(key: string, data: unknown): void {
  try {
    sessionStorage.setItem(key, JSON.stringify(data));
  } catch {
    // Storage full or unavailable — ignore
  }
}

async function fetchRpc<T>(config: AppConfig, resolvedModule: string, func: string, args: Record<string, any>): Promise<T> {
  const res = await fetch(config.dataEndpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Run-Id": config.runId || "" },
    body: JSON.stringify({ module: resolvedModule, func, args }),
    credentials: "include",
  });

  const contentType = res.headers.get("content-type") || "";
  console.log("[FETCH_RESPONSE]", { status: res.status, contentType });

  const raw = await res.text();
  if (!res.ok) {
    console.error("[FETCH_ERROR]", raw.slice(0, 200));
    throw new Error(getUserFacingErrorMessage(res.status));
  }

  if (!contentType.includes("application/json")) {
    console.error("[PARSE_ERROR]", `Unexpected content-type: ${contentType}`);
    console.log("[PARSE_ERROR_PREVIEW]", raw.slice(0, 200));
    throw new Error(`Expected JSON response, got '${contentType || "unknown"}'`);
  }

  try {
    const data = JSON.parse(raw);
    console.log("[PARSE_SUCCESS]", { keys: Object.keys(data ?? {}) });
    return data as T;
  } catch (err) {
    console.error("[PARSE_ERROR]", err);
    console.log("[PARSE_ERROR_PREVIEW]", raw.slice(0, 200));
    throw err;
  }
}

/**
 * Clear cached query results. Call after mutations to prevent stale data.
 * @param funcNames - Specific function names to invalidate (e.g., ['get_items', 'get_stats']). Omit to clear all.
 */
export function invalidateCache(funcNames?: string[]): void {
  const keysToRemove: string[] = [];
  for (let i = 0; i < sessionStorage.length; i++) {
    const key = sessionStorage.key(i);
    if (key && key.startsWith("rpc:")) {
      if (!funcNames || funcNames.some((fn) => key.includes(`:${fn}:`))) {
        keysToRemove.push(key);
      }
    }
  }
  keysToRemove.forEach((k) => sessionStorage.removeItem(k));
  console.log("[CACHE_INVALIDATE]", { funcs: funcNames || "*", cleared: keysToRemove.length });
}

export async function rpcCall<T = any>({ func, args = {}, module }: RpcParams): Promise<T> {
  const config = getConfig();
  const resolvedModule = module || `apps.${config.appName}.backend.main`;
  const key = cacheKey(func, args, resolvedModule);

  const cached = getCached<T>(key);
  if (cached !== undefined) {
    console.log("[CACHE_HIT]", { func, module: resolvedModule });
    // Return cached data immediately, refresh in background
    fetchRpc<T>(config, resolvedModule, func, args)
      .then((fresh) => setCache(key, fresh))
      .catch(() => {});
    return cached;
  }

  console.log("[FETCH_START]", { func, module: resolvedModule });
  const data = await fetchRpc<T>(config, resolvedModule, func, args);
  setCache(key, data);
  return data;
}

export async function streamCall<T = any>({
  func,
  args = {},
  module,
  onChunk,
  onError,
}: RpcParams & {
  onChunk: (chunk: T) => void;
  onError?: (err: Error) => void;
}): Promise<void> {
  const config = getConfig();
  const resolvedModule = module || `apps.${config.appName}.backend.main`;

  console.log("[STREAM_START]", { func, module: resolvedModule });

  try {
    const res = await fetch(config.dataEndpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Run-Id": config.runId || "",
        Accept: "text/event-stream",
      },
      body: JSON.stringify({ module: resolvedModule, func, args, stream: true }),
      credentials: "include",
    });

    if (!res.ok) {
      throw new Error(getUserFacingErrorMessage(res.status));
    }

    const reader = res.body?.getReader();
    if (!reader) throw new Error("Response body is not a stream");

    console.log("[STREAM_OPEN]", { func });

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (!line.trim()) continue;
        const cleanLine = line.startsWith("data: ") ? line.slice(6) : line;
        try {
          const data = JSON.parse(cleanLine);
          console.log("[STREAM_CHUNK]", { func });
          onChunk(data as T);
        } catch (err) {
          console.error("[STREAM_PARSE_ERROR]", err, { line: cleanLine.slice(0, 50) });
        }
      }
    }
    console.log("[STREAM_DONE]", { func });
  } catch (err: any) {
    console.error("[STREAM_ERROR]", err);
    if (onError) onError(err);
    throw err;
  }
}

export type RiskPredictionRequest = {
  cell_id: string;
  lat?: number | null;
  lon?: number | null;
  rainfall_1h?: number | null;
  rainfall_3h?: number | null;
  rainfall_6h?: number | null;
  rainfall_24h?: number | null;
  antecedent_rainfall?: number | null;
  soil_moisture?: number | null;
  elevation?: number | null;
  slope?: number | null;
  aspect?: number | null;
  historical_susceptibility?: number | null;
};

export type RiskBatchResponse<T = any> = {
  predictions: T[];
  predictor: string;
  predictor_type: string;
};

function getRiskEndpoint(path: string): string {
  const config = getConfig();
  return config.dataEndpoint.replace(/\/rpc$/, path);
}

async function postApi<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(getRiskEndpoint(path), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Run-Id": getConfig().runId || "",
    },
    body: JSON.stringify(body),
    credentials: "include",
  });

  const raw = await res.text();
  if (!res.ok) {
    let detail = "Request failed. Please try again.";
    try {
      detail = JSON.parse(raw).detail || detail;
    } catch {
      // Preserve the fallback when the server response is not JSON.
    }
    throw new Error(detail);
  }

  return JSON.parse(raw) as T;
}

export type CellBroadcastPreparation = {
  simulation: boolean;
  status: string;
  warning_id: number;
  target: {
    warning_id: number;
    geometry: any | null;
    district?: string | null;
    state?: string | null;
    region?: string | null;
    affected_infrastructure?: string[];
    source: "warning_geometry" | "risk_cells" | "event_geometry" | "selected_cell" | "demo";
  };
  protocol: { service: string; standard: string };
  payload: {
    format: string;
    identifier: string;
    sender: string;
    sent: string;
    status: string;
    msgType: string;
    scope: string;
    languages: string[];
    severity: string;
    urgency: string;
    certainty: string;
    effective: string;
    expires: string;
    area: string;
    polygon: any | null;
    circle: any | null;
    messages: { language: string; headline: string; description: string; instruction: string }[];
  };
  prepared_at: string;
  expires_at: string;
  audit: { mode: string; live_network_connected: boolean };
};

export type CellBroadcastSimulation = CellBroadcastPreparation & {
  broadcast_id: string;
  network_simulation: {
    status: string;
    target_cells: string[];
    estimated_devices: number | null;
  };
  escalation: { entity: string; status: string }[];
  simulation_logs: string[];
  dispatched_at: string;
  audit: {
    mode: string;
    live_network_connected: boolean;
    target_geometry_source?: string;
  };
};

export function prepareCellBroadcast(warningId: number): Promise<CellBroadcastPreparation> {
  return postApi<CellBroadcastPreparation>("/api/alerts/cell-broadcast/prepare", { warning_id: warningId });
}

export function simulateCellBroadcast(warningId: number): Promise<CellBroadcastSimulation> {
  return postApi<CellBroadcastSimulation>("/api/alerts/cell-broadcast/simulate", { warning_id: warningId });
}

export type VerificationReport = {
  id: number;
  warning_id?: number | null;
  location_id?: string | null;
  location_name?: string | null;
  reported_at: string;
  observed_at?: string | null;
  reporter_id?: string | null;
  reporter_role?: string | null;
  submitted_hazard_type?: string | null;
  hazard_type: string;
  classification?: string | null;
  submitted_event_presence?: string | null;
  event_presence?: string | null;
  description?: string | null;
  severity?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  geometry?: any | null;
  photo_reference?: string | null;
  infrastructure_impact?: string[];
  location_accuracy?: number | null;
  source_type: string;
  source_reference?: string | null;
  status: string;
  curator_id?: string | null;
  curator_reviewed_at?: string | null;
  curator_notes?: string | null;
  rejection_reason?: string | null;
  training_eligibility: string;
  dataset_version?: string | null;
  model_target?: string | null;
  location_quality?: string | null;
  temporal_quality?: string | null;
  evidence_quality?: string | null;
  duplicate_of?: number | null;
  possible_duplicate_ids?: number[];
  audit_events?: any[];
};

export type VerificationStats = {
  pending_review: number;
  approved_today: number;
  needs_more_evidence: number;
  rejected_today: number;
  training_buffer: number;
};

export type TrainingBuffer = {
  hazard_type: string;
  model_target: string;
  count: number;
};

export type TrainingDatasetManifest = {
  dataset_version: string;
  hazard_type: string;
  created_at: string;
  record_count: number;
  source_reports: number[];
  source_datasets: string[];
  feature_schema_version: string;
  label_policy_version: string;
  curator_version: string;
  training_status: string;
  model_updated: boolean;
};

export async function getVerificationReports(status?: string): Promise<VerificationReport[]> {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  const res = await fetch(getRiskEndpoint(`/api/verifications${query}`), { credentials: "include" });
  if (!res.ok) throw new Error("Unable to load verification reports.");
  const data = await res.json();
  return data.reports as VerificationReport[];
}

export async function getVerificationStats(): Promise<VerificationStats> {
  const res = await fetch(getRiskEndpoint("/api/verifications/stats"), { credentials: "include" });
  if (!res.ok) throw new Error("Unable to load verification statistics.");
  return res.json();
}

export async function getTrainingBuffer(): Promise<TrainingBuffer[]> {
  const res = await fetch(getRiskEndpoint("/api/training-buffer"), { credentials: "include" });
  if (!res.ok) throw new Error("Unable to load training buffer.");
  const data = await res.json();
  return data.buffers as TrainingBuffer[];
}

export function reviewVerificationReport(
  reportId: number,
  decision: {
    decision: "approved" | "rejected" | "needs_more_evidence" | "superseded";
    curator_id: string;
    curator_role: "curator" | "admin" | "model_admin";
    hazard_type?: string;
    event_presence?: string;
    evidence_quality?: string;
    location_quality?: string;
    reason?: string;
    notes?: string;
  }
): Promise<VerificationReport> {
  return postApi<VerificationReport>(`/api/verifications/${reportId}/review`, decision);
}

export function buildTrainingDataset(hazardType: string, curatorId: string): Promise<TrainingDatasetManifest> {
  return postApi<TrainingDatasetManifest>("/api/training-datasets/build", {
    hazard_type: hazardType,
    curator_id: curatorId,
  });
}

export async function predictRiskBatch<T = any>(cells: RiskPredictionRequest[]): Promise<RiskBatchResponse<T>> {
  const config = getConfig();
  const res = await fetch(getRiskEndpoint("/api/risk/predict-batch"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Run-Id": config.runId || "",
    },
    body: JSON.stringify({ cells }),
    credentials: "include",
  });

  const raw = await res.text();
  if (!res.ok) {
    let detail = "Risk prediction request failed.";
    try {
      const parsed = JSON.parse(raw);
      detail = parsed.detail || detail;
    } catch {
      // Preserve the user-facing fallback when the server did not return JSON.
    }
    throw new Error(detail);
  }

  return JSON.parse(raw) as RiskBatchResponse<T>;
}
