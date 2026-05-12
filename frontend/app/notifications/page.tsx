"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { clearAuthSession, fetchCurrentUser, getAccessToken, getStoredUser } from "@/lib/auth";
import { fetchNotifications, markNotificationRead, type NotificationItem } from "@/lib/notifications";

type StoredUser = {
  email?: string;
  role?: string;
};

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

export default function NotificationsPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredUser | null>(null);
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [filter, setFilter] = useState({ severity: "", unreadOnly: false });
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!getAccessToken()) {
      router.replace("/login");
      return;
    }
    const storedUser = getStoredUser();
    if (storedUser) {
      setUser(storedUser);
    }

    async function load() {
      setIsLoading(true);
      setError("");
      try {
        const [profile, notifications] = await Promise.all([fetchCurrentUser(), fetchNotifications()]);
        setUser(profile);
        setItems(notifications);
      } catch (loadError) {
        const message = loadError instanceof Error ? loadError.message : "Unable to load notifications.";
        setError(message);
        if (message.includes("sign in again")) {
          router.replace("/login");
        }
      } finally {
        setIsLoading(false);
      }
    }

    void load();
  }, [router]);

  const visibleItems = useMemo(
    () =>
      items.filter((item) => {
        if (filter.severity && item.severity !== filter.severity) {
          return false;
        }
        if (filter.unreadOnly && item.is_read) {
          return false;
        }
        return true;
      }),
    [filter, items],
  );

  async function handleMarkRead(id: number) {
    const updated = await markNotificationRead(id);
    setItems((current) => current.map((item) => (item.id === id ? updated : item)));
  }

  function handleLogout() {
    clearAuthSession();
    router.replace("/login");
  }

  return (
    <AppShell
      active="notifications"
      roleLabel={user?.role ?? "Team member"}
      userEmail={user?.email ?? "Loading user..."}
      title="Notification center"
      description="Track internal alerts for invoices, payments, POE uploads, suspicious activity, and issue escalations."
      onLogout={handleLogout}
    >
      {error ? <p className="error dashboard-error">{error}</p> : null}
      <section className="module-card">
        <div className="module-head">
          <h2>Inbox</h2>
          <span>{visibleItems.length} visible</span>
        </div>
        <div className="site-form-grid">
          <div className="field">
            <label htmlFor="severity-filter">Severity</label>
            <select id="severity-filter" value={filter.severity} onChange={(event) => setFilter((current) => ({ ...current, severity: event.target.value }))}>
              <option value="">All</option>
              <option value="info">Info</option>
              <option value="warning">Warning</option>
              <option value="error">Error</option>
              <option value="critical">Critical</option>
            </select>
          </div>
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={filter.unreadOnly}
              onChange={(event) => setFilter((current) => ({ ...current, unreadOnly: event.target.checked }))}
            />
            Unread only
          </label>
        </div>
      </section>
      <section className="module-card">
        <div className="inventory-table-wrap">
          <table className="inventory-table">
            <thead>
              <tr>
                <th>Notification</th>
                <th>Type</th>
                <th>Severity</th>
                <th>Created</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {visibleItems.map((item) => (
                <tr key={item.id}>
                  <td>
                    <div className="table-primary">
                      <strong>{item.title}</strong>
                      <span>{item.message || "No additional message."}</span>
                    </div>
                  </td>
                  <td>{item.event_type.replaceAll("_", " ")}</td>
                  <td><span className={`status-pill status-${item.severity}`}>{item.severity}</span></td>
                  <td>{formatDateTime(item.created_at)}</td>
                  <td>
                    <button className="ghost" type="button" disabled={item.is_read} onClick={() => void handleMarkRead(item.id)}>
                      {item.is_read ? "Read" : "Mark read"}
                    </button>
                  </td>
                </tr>
              ))}
              {!isLoading && visibleItems.length === 0 ? (
                <tr>
                  <td colSpan={5}>No notifications match these filters.</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </AppShell>
  );
}
