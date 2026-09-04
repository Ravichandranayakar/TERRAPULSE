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
