// API client for the ParetoFly backend.
//
// The streaming endpoint is a POST SSE endpoint, so the browser's native
// EventSource (GET-only) cannot be used. We use @microsoft/fetch-event-source
// to POST the TripQuery and parse the server-sent events.

import { fetchEventSource } from "@microsoft/fetch-event-source";
import type {
  ProgressEvent,
  SearchResult,
  TripQuery,
} from "@/types/api";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export interface StreamHandlers {
  onProgress?: (event: ProgressEvent) => void;
  onResult?: (result: SearchResult) => void;
  onError?: (error: Error) => void;
  signal?: AbortSignal;
}

/** Thrown when the server responds with a fatal (non-retryable) status. */
class FatalStreamError extends Error {}

/**
 * Run a search against POST /search/stream, invoking handlers as `progress`
 * and `result` events arrive. Resolves when the stream completes.
 */
export async function searchStream(
  query: TripQuery,
  handlers: StreamHandlers,
): Promise<void> {
  await fetchEventSource(`${API_BASE_URL}/search/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(query),
    signal: handlers.signal,
    openWhenHidden: true,
    async onopen(response) {
      if (response.ok) return;
      throw new FatalStreamError(
        `Search failed (${response.status} ${response.statusText})`,
      );
    },
    onmessage(msg) {
      if (!msg.data) return;
      if (msg.event === "progress") {
        handlers.onProgress?.(JSON.parse(msg.data) as ProgressEvent);
      } else if (msg.event === "result") {
        handlers.onResult?.(JSON.parse(msg.data) as SearchResult);
      }
    },
    onerror(err) {
      // Rethrow to stop the retry loop and surface the error to the caller.
      throw err instanceof Error ? err : new Error(String(err));
    },
  });
}

/** Non-streaming fallback: POST /search and return the final result. */
export async function search(query: TripQuery): Promise<SearchResult> {
  const response = await fetch(`${API_BASE_URL}/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(query),
  });
  if (!response.ok) {
    throw new Error(`Search failed (${response.status} ${response.statusText})`);
  }
  return (await response.json()) as SearchResult;
}
