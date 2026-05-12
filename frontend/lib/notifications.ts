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

export type NotificationPreference = {
  id: number;
  user: number;
  notification_type: string;
  in_app_enabled: boolean;
  email_enabled: boolean;
};

export type NotificationEventType = {
  value: string;
  label: string;
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

export async function fetchNotificationPreferences() {
  return list<NotificationPreference>("notifications/preferences/");
}

export async function fetchNotificationEventTypes() {
  return apiFetch<{ event_types: NotificationEventType[] }>("notifications/preferences/event-types/");
}

export async function saveNotificationPreference(input: {
  user: number;
  notification_type: string;
  in_app_enabled: boolean;
  email_enabled: boolean;
}) {
  return apiFetch<NotificationPreference>("notifications/preferences/", {
    method: "POST",
    body: JSON.stringify(input),
  });
}
