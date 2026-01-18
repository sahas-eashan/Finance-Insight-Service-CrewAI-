export type ChatRole = "user" | "assistant" | "system";

export type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  createdAt?: string;
};

export type ApiConfig = {
  baseUrl: string;
  apiKey?: string;
};

export type ChatResponse = {
  reply?: string;
  messages?: ChatMessage[];
  threadId?: string;
  traces?: any[];
};

export type Thread = {
  id: string;
  title: string;
  summary?: string;
  createdAt: string;
  updatedAt: string;
};

export type ServiceCapabilities = {
  services: {
    openai: boolean;
    serper: boolean;
    serpapi: boolean;
    twelveData: boolean;
    alphaVantage: boolean;
  };
  capabilities: {
    news_search: boolean | string;
    market_data: boolean | string;
    fundamentals: boolean;
    ai_agents: boolean;
  };
};

const STORAGE_KEY = "agentSettings";
export const DEFAULT_API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://default.localhost:9080/financeinsightservice";

const createId = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;

const normalizeMessage = (value: unknown, fallbackRole: ChatRole): ChatMessage => {
  const data = value as {
    id?: string;
    role?: ChatRole;
    content?: string;
    message?: string;
    text?: string;
    createdAt?: string;
    created_at?: string;
  };

  return {
    id: data?.id ?? createId(),
    role:
      data?.role === "user" || data?.role === "assistant" || data?.role === "system"
        ? data.role
        : fallbackRole,
    content:
      data?.content ?? data?.message ?? data?.text ?? "",
    createdAt: data?.createdAt ?? data?.created_at,
  };
};

const buildHeaders = (apiKey?: string) => {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (apiKey) {
    headers.Authorization = `Bearer ${apiKey}`;
    headers["X-API-Key"] = apiKey;
  }

  return headers;
};

export const getApiConfig = (): ApiConfig => {
  if (typeof window === "undefined") {
    return { baseUrl: DEFAULT_API_BASE_URL };
  }

  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (!stored) {
    return { baseUrl: DEFAULT_API_BASE_URL };
  }

  try {
    const parsed = JSON.parse(stored) as ApiConfig;
    return {
      baseUrl: parsed.baseUrl || DEFAULT_API_BASE_URL,
      apiKey: parsed.apiKey || "",
    };
  } catch {
    return { baseUrl: DEFAULT_API_BASE_URL };
  }
};

export const setApiConfig = (config: ApiConfig) => {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
};

export const fetchHistory = async (threadId?: string): Promise<ChatMessage[]> => {
  const { baseUrl, apiKey } = getApiConfig();
  const url = threadId ? `${baseUrl}/history?threadId=${threadId}` : `${baseUrl}/history`;
  const response = await fetch(url, {
    headers: buildHeaders(apiKey),
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Failed to load history");
  }

  const data = (await response.json()) as
    | ChatMessage[]
    | { messages?: ChatMessage[] }
    | { data?: ChatMessage[] };
  const rawMessages = Array.isArray(data)
    ? data
    : data?.messages ?? data?.data ?? [];

  return rawMessages
    .map((message) => normalizeMessage(message, "assistant"))
    .filter((message) => message.content);
};

export const sendMessage = async (
  message: string,
  threadId?: string,
  onTrace?: (message: string, detail: any) => void,
): Promise<ChatResponse> => {
  const { baseUrl, apiKey } = getApiConfig();
  
  console.log('[API] Starting async job:', `${baseUrl}/chat/async`);
  
  // Start async job
  let startResponse: Response;
  try {
    startResponse = await fetch(`${baseUrl}/chat/async`, {
      method: "POST",
      headers: buildHeaders(apiKey),
      body: JSON.stringify({ message, threadId }),
    });
  } catch (error) {
    console.error('[API] Fetch error:', error);
    throw new Error("Cannot connect to backend. Make sure the API server is running.");
  }

  if (!startResponse.ok) {
    console.error('[API] Response not OK:', startResponse.status, startResponse.statusText);
    throw new Error(`Server error: ${startResponse.status} ${startResponse.statusText}`);
  }

  const startData = await startResponse.json();
  const { jobId, threadId: actualThreadId } = startData;
  console.log('[API] Job started:', jobId, 'thread:', actualThreadId);

  // Poll for status
  const seenTraces = new Set<string>();
  let lastTraceCount = 0;

  const pollStatus = async (): Promise<ChatResponse> => {
    while (true) {
      await new Promise(resolve => setTimeout(resolve, 2000)); // Poll every 2 seconds

      try {
        const statusResponse = await fetch(`${baseUrl}/chat/async/${jobId}/status`, {
          headers: buildHeaders(apiKey),
        });

        if (!statusResponse.ok) {
          console.error('[API] Status check failed:', statusResponse.status);
          throw new Error(`Failed to check job status: ${statusResponse.status}`);
        }

        const statusData = await statusResponse.json();
        console.log('[API] Job status:', statusData.status, 'traces:', statusData.traceCount);

        // Emit new traces
        if (onTrace && statusData.traces) {
          for (const trace of statusData.traces) {
            const traceKey = `${trace.timestamp}-${trace.message}`;
            if (!seenTraces.has(traceKey) && statusData.traceCount > lastTraceCount) {
              seenTraces.add(traceKey);
              onTrace(trace.message, trace);
            }
          }
          lastTraceCount = statusData.traceCount;
        }

        // Check if job is complete
        if (statusData.status === 'completed' || statusData.status === 'failed') {
          console.log('[API] Job finished:', statusData.status);
          
          // Get final result
          const resultResponse = await fetch(`${baseUrl}/chat/async/${jobId}/result`, {
            headers: buildHeaders(apiKey),
          });

          if (!resultResponse.ok) {
            const errorData = await resultResponse.json().catch(() => ({ error: 'Unknown error' }));
            console.error('[API] Result fetch failed:', errorData);
            throw new Error(errorData.error || 'Failed to get result');
          }

          const resultData = await resultResponse.json();
          console.log('[API] Final result received');

          return {
            reply: resultData.result?.reply ?? "",
            threadId: actualThreadId,
            traces: resultData.traces ?? [],
          };
        }

      } catch (error) {
        console.error('[API] Polling error:', error);
        throw error;
      }
    }
  };

  return await pollStatus();
};

export const testConnection = async (config?: ApiConfig): Promise<boolean> => {
  const resolved = config ?? getApiConfig();
  try {
    const response = await fetch(`${resolved.baseUrl}/health`, {
      headers: buildHeaders(resolved.apiKey),
      cache: "no-store",
    });
    return response.ok;
  } catch {
    return false;
  }
};

export const fetchTrace = async (threadId: string): Promise<any[]> => {
  const { baseUrl, apiKey } = getApiConfig();
  const response = await fetch(`${baseUrl}/trace?threadId=${threadId}`, {
    headers: buildHeaders(apiKey),
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Failed to load trace");
  }

  const data = await response.json();
  return Array.isArray(data) ? data : [];
};

export const fetchThreads = async (): Promise<Thread[]> => {
  try {
    const { baseUrl, apiKey } = getApiConfig();
    const response = await fetch(`${baseUrl}/threads`, {
      headers: buildHeaders(apiKey),
      cache: "no-store",
    });

    if (!response.ok) {
      console.error(`[API] Failed to fetch threads: ${response.status} ${response.statusText}`);
      throw new Error("Failed to load threads");
    }

    const data = await response.json();
    return Array.isArray(data) ? data : [];
  } catch (error) {
    console.error('[API] fetchThreads error:', error);
    // Return empty array instead of throwing to prevent UI breakage
    return [];
  }
};

export const fetchConfig = async (): Promise<ServiceCapabilities | null> => {
  try {
    const { baseUrl, apiKey } = getApiConfig();
    const response = await fetch(`${baseUrl}/config`, {
      headers: buildHeaders(apiKey),
    });

    if (!response.ok) {
      return null;
    }

    return await response.json();
  } catch (error) {
    console.error("Failed to fetch config:", error);
    return null;
  }
};
