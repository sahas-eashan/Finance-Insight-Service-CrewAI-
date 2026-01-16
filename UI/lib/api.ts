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
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:5000";

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
  
  // Use fetch with streaming for POST
  const response = await fetch(`${baseUrl}/chat`, {
    method: "POST",
    headers: buildHeaders(apiKey),
    body: JSON.stringify({ message, threadId }),
  });

  if (!response.ok) {
    throw new Error("Failed to send message");
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("No response stream");
  }

  const decoder = new TextDecoder();
  const traces: any[] = [];
  let finalResponse: ChatResponse | null = null;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value, { stream: true });
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            
            if (data.type === "trace") {
              traces.push(data.detail);
              if (onTrace) {
                onTrace(data.message, data.detail);
              }
            } else if (data.type === "response") {
              const normalizedMessages = (data.messages ?? []).map(
                (entry: any) => normalizeMessage(entry, "assistant"),
              );
              
              finalResponse = {
                reply: data.reply ?? "",
                messages: normalizedMessages.length ? normalizedMessages : undefined,
                threadId: data.threadId,
                traces: data.traces ?? traces,
              };
            }
          } catch (e) {
            // Ignore malformed JSON
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }

  if (!finalResponse) {
    throw new Error("No response received");
  }

  return finalResponse;
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
  const { baseUrl, apiKey } = getApiConfig();
  const response = await fetch(`${baseUrl}/threads`, {
    headers: buildHeaders(apiKey),
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Failed to load threads");
  }

  const data = await response.json();
  return Array.isArray(data) ? data : [];
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
