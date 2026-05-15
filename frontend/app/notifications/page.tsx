"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { clearAuthSession, fetchCurrentUser, getAccessToken, getStoredUser } from "@/lib/auth";
import {
  fetchNotificationEventTypes,
  fetchNotificationPreferences,
  fetchNotifications,
  markNotificationRead,
  saveNotificationPreference,
  type NotificationEventType,
  type NotificationItem,
  type NotificationPreference,
} from "@/lib/notifications";

type StoredUser = {
  id?: number;
  email?: string;
  role?: string;
};

const CATEGORY_ORDER = ["Imports", "Exports", "POE review", "Billing", "System", "Campaigns", "Other"];

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
  const [preferences, setPreferences] = useState<NotificationPreference[]>([]);
  const [eventTypes, setEventTypes] = useState<NotificationEventType[]>([]);
  const [filter, setFilter] = useState({ severity: "", unreadOnly: false });
  const [error, setError] = useState("");
  const [preferenceMessage, setPreferenceMessage] = useState("");
  const [preferenceError, setPreferenceError] = useState("");
  const [savingPreference, setSavingPreference] = useState("");
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
        const [profile, notifications, preferencePayload, eventTypePayload] = await Promise.all([
          fetchCurrentUser(),
          fetchNotifications(),
          fetchNotificationPreferences(),
          fetchNotificationEventTypes(),
        ]);
        setUser(profile);
        setItems(notifications);
        setPreferences(preferencePayload);
        setEventTypes(eventTypePayload.event_types);
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

  const preferenceGroups = useMemo(() => {
    const grouped = eventTypes.reduce<Record<string, NotificationEventType[]>>((groups, eventType) => {
      const category = eventType.category || "Other";
      groups[category] = [...(groups[category] ?? []), eventType];
      return groups;
    }, {});
    return Object.entries(grouped).sort(([left], [right]) => {
      const leftIndex = CATEGORY_ORDER.indexOf(left);
      const rightIndex = CATEGORY_ORDER.indexOf(right);
      return (leftIndex === -1 ? CATEGORY_ORDER.length : leftIndex) - (rightIndex === -1 ? CATEGORY_ORDER.length : rightIndex);
    });
  }, [eventTypes]);

  async function handleMarkRead(id: number) {
    const updated = await markNotificationRead(id);
    setItems((current) => current.map((item) => (item.id === id ? updated : item)));
  }

  async function handlePreferenceToggle(eventType: string, field: "in_app_enabled" | "email_enabled", enabled: boolean) {
    if (!user?.id) {
      return;
    }
    setPreferenceMessage("");
    setPreferenceError("");
    setSavingPreference(`${eventType}-${field}`);
    const existing = preferences.find((item) => item.notification_type === eventType);
    try {
      const updated = await saveNotificationPreference({
        user: user.id,
        notification_type: eventType,
        in_app_enabled: field === "in_app_enabled" ? enabled : existing?.in_app_enabled ?? true,
        email_enabled: field === "email_enabled" ? enabled : existing?.email_enabled ?? true,
      });
      setPreferences((current) => {
        const others = current.filter((item) => item.notification_type !== eventType);
        return [...others, updated].sort((a, b) => a.notification_type.localeCompare(b.notification_type));
      });
      if (field === "in_app_enabled") {
        setItems(await fetchNotifications());
      }
      setPreferenceMessage("Notification preference saved.");
    } catch (saveError) {
      setPreferenceError(saveError instanceof Error ? saveError.message : "Unable to save notification preference.");
    } finally {
      setSavingPreference("");
    }
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
        <div className="module-head">
          <h2>Preferences</h2>
          <span>{preferences.length} saved</span>
        </div>
        <p className="section-copy">Choose which operational events should appear in your inbox or be sent by email. Existing inbox history is preserved.</p>
        {preferenceMessage ? <p className="success compact-message">{preferenceMessage}</p> : null}
        {preferenceError ? <p className="error compact-message">{preferenceError}</p> : null}
        <div className="notification-preference-grid">
          {preferenceGroups.map(([category, categoryEvents]) => (
            <article className="notification-preference-group" key={category}>
              <div className="module-head">
                <h3>{category}</h3>
                <span>{categoryEvents.length} categories</span>
              </div>
              <div className="notification-preference-list">
                {categoryEvents.map((eventType) => {
                  const preference = preferences.find((item) => item.notification_type === eventType.value);
                  const isSavingInApp = savingPreference === `${eventType.value}-in_app_enabled`;
                  const isSavingEmail = savingPreference === `${eventType.value}-email_enabled`;
                  return (
                    <div className="notification-preference-card" key={eventType.value}>
                      <div>
                        <p className="site-code">{eventType.value.replaceAll("_", " ")}</p>
                        <h4>{eventType.label}</h4>
                        <p className="site-copy">{eventType.description || "Operational notification category."}</p>
                      </div>
                      <div className="notification-toggle-row">
                        <label className="filter-toggle">
                          <input
                            type="checkbox"
                            checked={preference?.in_app_enabled ?? true}
                            disabled={Boolean(savingPreference)}
                            onChange={(event) => void handlePreferenceToggle(eventType.value, "in_app_enabled", event.target.checked)}
                          />
                          <span className="filter-toggle-control" />
                          <span className="filter-toggle-copy">
                            <strong>Inbox</strong>
                            <small>{isSavingInApp ? "Saving..." : (preference?.in_app_enabled ?? true) ? "On" : "Off"}</small>
                          </span>
                        </label>
                        <label className="filter-toggle">
                          <input
                            type="checkbox"
                            checked={preference?.email_enabled ?? true}
                            disabled={Boolean(savingPreference)}
                            onChange={(event) => void handlePreferenceToggle(eventType.value, "email_enabled", event.target.checked)}
                          />
                          <span className="filter-toggle-control" />
                          <span className="filter-toggle-copy">
                            <strong>Email</strong>
                            <small>{isSavingEmail ? "Saving..." : (preference?.email_enabled ?? true) ? "On" : "Off"}</small>
                          </span>
                        </label>
                      </div>
                    </div>
                  );
                })}
              </div>
            </article>
          ))}
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
