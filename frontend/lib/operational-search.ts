import { apiFetch } from "@/lib/auth";

type Paginated<T> = {
  results: T[];
};

export type OperationalSearchResult = {
  module: string;
  id: string;
  title: string;
  subtitle: string;
  status: string;
  url: string;
  created_at: string | null;
  metadata: Record<string, unknown>;
};

export type OperationalSearchPayload = {
  query: string;
  total: number;
  results: OperationalSearchResult[];
  grouped: Record<string, OperationalSearchResult[]>;
};

export type SavedOperationalView = {
  id: number;
  name: string;
  view_type: string;
  module: string;
  search_query: string;
  filters: Record<string, string>;
  is_default: boolean;
  created_at: string;
  updated_at: string;
};

export type SavedOperationalViewInput = {
  name: string;
  view_type?: string;
  module?: string;
  search_query?: string;
  filters?: Record<string, string>;
  is_default?: boolean;
};

function buildQuery(params: Record<string, string | undefined>) {
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) {
      searchParams.set(key, value);
    }
  }
  const query = searchParams.toString();
  return query ? `?${query}` : "";
}

export async function fetchOperationalSearch(params: Record<string, string | undefined>) {
  return apiFetch<OperationalSearchPayload>(`/observability/operational-search/${buildQuery(params)}`);
}

export async function fetchSavedOperationalViews(params: Record<string, string | undefined> = {}) {
  const payload = await apiFetch<Paginated<SavedOperationalView> | SavedOperationalView[]>(
    `/observability/saved-views/${buildQuery(params)}`,
  );
  return Array.isArray(payload) ? payload : payload.results;
}

export async function createSavedOperationalView(input: SavedOperationalViewInput) {
  return apiFetch<SavedOperationalView>("/observability/saved-views/", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function deleteSavedOperationalView(id: number) {
  return apiFetch<void>(`/observability/saved-views/${id}/`, {
    method: "DELETE",
  });
}
