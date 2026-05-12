import { apiFetch } from "@/lib/auth";

type Paginated<T> = {
  results: T[];
};

export type NotificationItem = {
  id: number;
  event_type: string;
  title: string;
  message: string;
  severity: string;
  is_read: boolean;
  delivery_status: string;
  created_at: string;
};

async function list<T>(path: string) {
  const payload = await apiFetch<Paginated<T> | T[]>(path);
  return Array.isArray(payload) ? payload : payload.results;
}

export async function fetchNotifications(query = "") {
  return list<NotificationItem>(`notifications/inbox/${query}`);
}

export async function fetchUnreadNotificationCount() {
  return apiFetch<{ unread_count: number }>("notifications/inbox/unread-count/");
}

export async function markNotificationRead(id: number) {
  return apiFetch<NotificationItem>(`notifications/inbox/${id}/mark-read/`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}
