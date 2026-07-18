"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { ApiError, clearAuthSession, fetchCurrentUser, getAccessToken, getStoredUser, type AuthUser } from "@/lib/auth";
import {
  createTeamUser,
  deactivateTeamUser,
  fetchTeamRoles,
  fetchTeamUsers,
  reactivateTeamUser,
  sendTeamUserSetup,
  updateTeamUser,
  type TeamRoleDirectory,
  type TeamUser,
  type TeamUserInput,
} from "@/lib/team";

const EMPTY_FORM: TeamUserInput = {
  email: "",
  first_name: "",
  last_name: "",
  phone_number: "",
  role: "field_staff",
  region: "",
  reports_to: null,
  send_setup: true,
};

const EMPTY_FILTERS = { search: "", role: "", is_active: "", region: "" };

function formatDateTime(value: string | null) {
  if (!value) {
    return "Never";
  }
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function statusLabel(user: TeamUser) {
  if (user.account_status === "setup_pending") {
    return "Setup pending";
  }
  return user.account_status === "inactive" ? "Access removed" : "Active";
}

export default function TeamAccessPage() {
  const router = useRouter();
  const [profile, setProfile] = useState<AuthUser | null>(null);
  const [users, setUsers] = useState<TeamUser[]>([]);
  const [directory, setDirectory] = useState<TeamRoleDirectory | null>(null);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [isLoading, setIsLoading] = useState(true);
  const [pageError, setPageError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [editingUser, setEditingUser] = useState<TeamUser | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [form, setForm] = useState<TeamUserInput>(EMPTY_FORM);
  const [formError, setFormError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [isSaving, setIsSaving] = useState(false);
  const [activeAction, setActiveAction] = useState<string | null>(null);

  const canManageTeam = Boolean(
    profile?.role === "admin" || profile?.is_company_admin || profile?.is_platform_admin,
  );

  const loadTeam = useCallback(async (nextFilters: Record<string, string>) => {
    setIsLoading(true);
    setPageError("");
    try {
      const [currentUser, roleDirectory, teamDirectory] = await Promise.all([
        fetchCurrentUser(),
        fetchTeamRoles(),
        fetchTeamUsers(nextFilters),
      ]);
      setProfile(currentUser);
      setDirectory(roleDirectory);
      setUsers(teamDirectory.results);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to load team access.";
      setPageError(message);
      if (error instanceof ApiError && error.status === 403) {
        router.replace("/dashboard");
      }
    } finally {
      setIsLoading(false);
    }
  }, [router]);

  useEffect(() => {
    if (!getAccessToken()) {
      router.replace("/login");
      return;
    }
    setProfile(getStoredUser());
    void loadTeam(EMPTY_FILTERS);
  }, [loadTeam, router]);

  const regions = useMemo(
    () => Array.from(new Set(users.map((user) => user.region).filter(Boolean))).sort(),
    [users],
  );

  const selectedTenant = form.tenant ?? directory?.tenants[0]?.id;
  const managerOptions = users.filter(
    (user) => user.is_active && user.tenant === selectedTenant && user.id !== editingUser?.id,
  );

  function handleLogout() {
    clearAuthSession();
    router.replace("/login");
  }

  function openCreate() {
    setEditingUser(null);
    setForm({ ...EMPTY_FORM, tenant: directory?.tenants[0]?.id });
    setFormError("");
    setFieldErrors({});
    setIsFormOpen(true);
  }

  function openEdit(user: TeamUser) {
    setEditingUser(user);
    setForm({
      email: user.email,
      first_name: user.first_name,
      last_name: user.last_name,
      phone_number: user.phone_number,
      role: user.role,
      region: user.region,
      reports_to: user.reports_to,
      tenant: user.tenant,
      send_setup: false,
    });
    setFormError("");
    setFieldErrors({});
    setIsFormOpen(true);
  }

  function closeForm() {
    if (!isSaving) {
      setIsFormOpen(false);
      setEditingUser(null);
    }
  }

  function updateForm<K extends keyof TeamUserInput>(key: K, value: TeamUserInput[K]) {
    setForm((current) => ({ ...current, [key]: value }));
    setFieldErrors((current) => ({ ...current, [key]: [] }));
  }

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSaving(true);
    setFormError("");
    setFieldErrors({});
    try {
      const saved = editingUser
        ? await updateTeamUser(editingUser.id, form)
        : await createTeamUser(form);
      setFeedback(
        editingUser
          ? "Team member access updated."
          : saved.setup_delivery === "failed"
            ? "Team member created, but the setup email could not be delivered. Send it again from Actions."
            : "Team member created and account setup sent.",
      );
      setIsFormOpen(false);
      setEditingUser(null);
      await loadTeam(filters);
    } catch (error) {
      if (error instanceof ApiError) {
        setFieldErrors(error.fieldErrors);
        setFormError(error.message);
      } else {
        setFormError("Unable to save this team member.");
      }
    } finally {
      setIsSaving(false);
    }
  }

  async function handleAccessAction(user: TeamUser, action: "deactivate" | "reactivate" | "setup") {
    if (action === "deactivate") {
      const confirmed = window.confirm(
        `Remove access for ${user.full_name}? They will no longer be able to sign in, but all historical activity and assignments will be retained.`,
      );
      if (!confirmed) {
        return;
      }
    }

    setActiveAction(`${action}-${user.id}`);
    setPageError("");
    try {
      if (action === "deactivate") {
        await deactivateTeamUser(user.id);
        setFeedback("Access removed. Historical activity remains available.");
      } else if (action === "reactivate") {
        await reactivateTeamUser(user.id);
        setFeedback("Team member access restored.");
      } else {
        await sendTeamUserSetup(user.id);
        setFeedback("Account setup instructions sent.");
      }
      await loadTeam(filters);
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "Unable to update team access.");
    } finally {
      setActiveAction(null);
    }
  }

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void loadTeam(filters);
  }

  const renderActions = (user: TeamUser, mobile = false) => {
    const controls = (
      <>
        <button type="button" className="ghost table-action" onClick={() => openEdit(user)}>
          View / Edit
        </button>
        <button
          type="button"
          className="ghost table-action"
          disabled={!user.is_active || activeAction === `setup-${user.id}`}
          onClick={() => void handleAccessAction(user, "setup")}
        >
          {activeAction === `setup-${user.id}` ? "Sending..." : "Send account setup"}
        </button>
        {user.is_active ? (
          <button
            type="button"
            className="ghost ghost-danger table-action"
            disabled={activeAction === `deactivate-${user.id}`}
            onClick={() => void handleAccessAction(user, "deactivate")}
          >
            {activeAction === `deactivate-${user.id}` ? "Removing..." : "Remove access"}
          </button>
        ) : (
          <button
            type="button"
            className="ghost table-action"
            disabled={activeAction === `reactivate-${user.id}`}
            onClick={() => void handleAccessAction(user, "reactivate")}
          >
            {activeAction === `reactivate-${user.id}` ? "Restoring..." : "Restore access"}
          </button>
        )}
      </>
    );
    return mobile ? <details className="team-mobile-menu"><summary>Actions</summary><div>{controls}</div></details> : <div className="team-row-actions">{controls}</div>;
  };

  return (
    <AppShell
      active="team"
      roleLabel={profile?.role ?? "admin"}
      userEmail={profile?.email ?? "Loading user..."}
      title="Team & access"
      eyebrow="Company settings"
      description="Invite people, assign the work they need, and remove access without losing operational history."
      onLogout={handleLogout}
    >
      <section className="team-command-bar">
        <div>
          <p className="site-code">Secure tenant directory</p>
          <h2>{directory?.can_select_tenant ? "Company teams" : profile?.organization_name || "Your company team"}</h2>
          <p className="site-copy">Backend permissions remain authoritative for every role and company boundary.</p>
        </div>
        <button className="submit team-add-button" type="button" onClick={openCreate} disabled={!canManageTeam || isLoading}>
          Add team member
        </button>
      </section>

      {pageError ? <p className="error dashboard-error">{pageError}</p> : null}
      {feedback ? <p className="success team-feedback" role="status">{feedback}</p> : null}

      <section className="team-directory-card">
        <form className="team-filter-bar" onSubmit={applyFilters}>
          <label className="team-search-field">
            <span>Search team</span>
            <input
              value={filters.search}
              onChange={(event) => setFilters((current) => ({ ...current, search: event.target.value }))}
              placeholder="Name or email"
            />
          </label>
          <label>
            <span>Role</span>
            <select value={filters.role} onChange={(event) => setFilters((current) => ({ ...current, role: event.target.value }))}>
              <option value="">All roles</option>
              {directory?.roles.map((role) => <option key={role.value} value={role.value}>{role.label}</option>)}
            </select>
          </label>
          <label>
            <span>Status</span>
            <select value={filters.is_active} onChange={(event) => setFilters((current) => ({ ...current, is_active: event.target.value }))}>
              <option value="">All statuses</option>
              <option value="true">Active</option>
              <option value="false">Access removed</option>
            </select>
          </label>
          <label>
            <span>Region</span>
            <select value={filters.region} onChange={(event) => setFilters((current) => ({ ...current, region: event.target.value }))}>
              <option value="">All regions</option>
              {regions.map((region) => <option key={region} value={region}>{region}</option>)}
            </select>
          </label>
          <button className="ghost team-filter-button" type="submit">Apply</button>
        </form>

        <div className="inventory-table-wrap team-table-wrap">
          <table className="inventory-table team-table">
            <thead><tr><th>Team member</th><th>Role</th><th>Region</th><th>Assigned work</th><th>Last active</th><th>Status</th><th>Actions</th></tr></thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id}>
                  <td><div className="table-primary"><strong>{user.full_name}</strong><span>{user.email}</span>{directory?.can_select_tenant ? <small>{user.tenant_name}</small> : null}</div></td>
                  <td><span className="team-role-label">{user.role_label}</span></td>
                  <td>{user.region || "Not assigned"}</td>
                  <td><span className="team-work-summary">{user.assigned_work_summary}</span></td>
                  <td>{formatDateTime(user.last_login)}</td>
                  <td><span className={`status-pill team-status-${user.account_status}`}>{statusLabel(user)}</span></td>
                  <td>{renderActions(user)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="team-mobile-list">
          {users.map((user) => (
            <article className="team-mobile-card" key={user.id}>
              <div className="team-mobile-head"><div><strong>{user.full_name}</strong><span>{user.email}</span></div><span className={`status-pill team-status-${user.account_status}`}>{statusLabel(user)}</span></div>
              <dl><div><dt>Role</dt><dd>{user.role_label}</dd></div><div><dt>Region</dt><dd>{user.region || "Not assigned"}</dd></div><div><dt>Assigned work</dt><dd>{user.assigned_work_summary}</dd></div><div><dt>Last active</dt><dd>{formatDateTime(user.last_login)}</dd></div></dl>
              {renderActions(user, true)}
            </article>
          ))}
        </div>

        {!isLoading && users.length === 0 ? <p className="empty-state">No team members match these filters.</p> : null}
        {isLoading ? <p className="empty-state">Loading team access...</p> : null}
      </section>

      {isFormOpen ? (
        <div className="team-modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && closeForm()}>
          <section className="team-modal" role="dialog" aria-modal="true" aria-labelledby="team-form-title">
            <div className="team-modal-head"><div><p className="site-code">Tenant-safe access</p><h2 id="team-form-title">{editingUser ? "Edit team access" : "Add team member"}</h2></div><button className="ghost" type="button" onClick={closeForm}>Close</button></div>
            <form className="team-form-grid" onSubmit={handleSave}>
              <label><span>First name</span><input value={form.first_name} onChange={(event) => updateForm("first_name", event.target.value)} required />{fieldErrors.first_name?.map((message) => <small className="field-error" key={message}>{message}</small>)}</label>
              <label><span>Last name</span><input value={form.last_name} onChange={(event) => updateForm("last_name", event.target.value)} required />{fieldErrors.last_name?.map((message) => <small className="field-error" key={message}>{message}</small>)}</label>
              <label className="team-form-span"><span>Email</span><input type="email" value={form.email ?? ""} onChange={(event) => updateForm("email", event.target.value)} readOnly={Boolean(editingUser)} required />{fieldErrors.email?.map((message) => <small className="field-error" key={message}>{message}</small>)}</label>
              <label><span>Phone</span><input value={form.phone_number} onChange={(event) => updateForm("phone_number", event.target.value)} /></label>
              <label><span>Region / location</span><input value={form.region} onChange={(event) => updateForm("region", event.target.value)} placeholder="Jammu, North region" /></label>
              {directory?.can_select_tenant ? <label className="team-form-span"><span>Company</span><select value={form.tenant ?? ""} onChange={(event) => updateForm("tenant", Number(event.target.value))} disabled={Boolean(editingUser)} required><option value="" disabled>Select company</option>{directory.tenants.map((tenant) => <option key={tenant.id} value={tenant.id}>{tenant.name}</option>)}</select></label> : null}
              <label><span>Role</span><select value={form.role} onChange={(event) => updateForm("role", event.target.value)} required>{editingUser && !directory?.roles.some((role) => role.value === editingUser.role) ? <option value={editingUser.role}>{editingUser.role_label} (legacy)</option> : null}{directory?.roles.map((role) => <option key={role.value} value={role.value}>{role.label}</option>)}</select>{fieldErrors.role?.map((message) => <small className="field-error" key={message}>{message}</small>)}</label>
              <label><span>Reporting manager</span><select value={form.reports_to ?? ""} onChange={(event) => updateForm("reports_to", event.target.value ? Number(event.target.value) : null)}><option value="">Not assigned</option>{managerOptions.map((manager) => <option key={manager.id} value={manager.id}>{manager.full_name}</option>)}</select></label>
              {!editingUser ? <label className="team-form-check team-form-span"><input type="checkbox" checked={Boolean(form.send_setup)} onChange={(event) => updateForm("send_setup", event.target.checked)} /><span>Send secure account setup invitation now</span></label> : null}
              {formError ? <p className="error team-form-span">{formError}</p> : null}
              <div className="team-form-actions team-form-span"><button className="ghost" type="button" onClick={closeForm} disabled={isSaving}>Cancel</button><button className="submit" type="submit" disabled={isSaving}>{isSaving ? "Saving..." : editingUser ? "Save access" : "Add team member"}</button></div>
            </form>
          </section>
        </div>
      ) : null}
    </AppShell>
  );
}
