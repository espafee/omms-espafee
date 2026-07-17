"use client";

import { type ChangeEvent, type FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { ImageManagerCard } from "@/components/image-manager-card";
import { SafeImage } from "@/components/safe-image";
import { clearAuthSession, fetchCurrentUser, getAccessToken, getStoredUser } from "@/lib/auth";
import { deleteMediaUnitImage, getMediaUnitImageMutationError, updateMediaUnitImage, uploadMediaUnitImage } from "@/lib/media-unit-images";
import {
  createMediaUnit,
  createSite,
  deleteSite,
  fetchInventoryData,
  fetchInventorySiteList,
  formatMediaUnitSiteType,
  getInventorySiteMutationError,
  getInventoryUnitMutationError,
  type InventorySiteListFilters,
  MEDIA_UNIT_SITE_TYPE_OPTIONS,
  type InventoryPayload,
  type InventorySiteCreateInput,
  type InventoryUnitMutationInput,
  updateMediaUnit,
} from "@/lib/inventory";
import { deleteSiteImage, getSiteImageMutationError, updateSiteImage, uploadSiteImage } from "@/lib/site-images";

type StoredUser = {
  email?: string;
  role?: string;
};

const WRITE_ROLES = new Set(["admin", "operations"]);
const ADMIN_ROLES = new Set(["admin"]);
const SITE_LIST_PAGE_SIZE = 10;

const INITIAL_SITE_FORM: InventorySiteCreateInput = {
  name: "",
  code: "",
  site_type: "billboard",
  address: "",
  city: "",
  state: "",
  latitude: "",
  longitude: "",
};

const INITIAL_UNIT_FORM: InventoryUnitMutationInput = {
  site: 0,
  unit_code: "",
  face_count: 1,
  width: "",
  height: "",
  status: "available",
  is_illuminated: false,
  monthly_rate: "",
  facing_direction: "",
  site_type: "single_side",
};

type UnitFilters = {
  city: string;
  status: string;
  facing_direction: string;
  site_type: string;
};

type PendingUnitImage = {
  id: string;
  file: File;
  previewUrl: string;
  caption: string;
};

const INITIAL_UNIT_FILTERS: UnitFilters = {
  city: "",
  status: "",
  facing_direction: "",
  site_type: "",
};

const INITIAL_SITE_LIST_FILTERS: InventorySiteListFilters = {
  search: "",
  city: "",
  status: "",
  media_type: "",
  facing_direction: "",
  site_type: "",
  page: 1,
  page_size: SITE_LIST_PAGE_SIZE,
};

const SITE_LIST_STATUS_OPTIONS = ["available", "reserved", "maintenance", "retired", "no_units"];

function formatChoice(value: string | null | undefined) {
  if (!value) {
    return "Pending";
  }
  return value.replaceAll("_", " ");
}

function formatSiteListStatus(value: string) {
  return value === "no_units" ? "No units" : formatChoice(value);
}

function formatUnitSiteTypes(value: string) {
  if (!value) {
    return "Type pending";
  }
  return value.split(", ").map(formatMediaUnitSiteType).join(", ");
}

function formatDate(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "Date unavailable";
  }
  return parsed.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

export default function InventoryPage() {
  const router = useRouter();
  const unitFormSectionRef = useRef<HTMLElement | null>(null);
  const unitCodeInputRef = useRef<HTMLInputElement | null>(null);
  const unitFormHighlightTimeoutRef = useRef<number | null>(null);
  const [user, setUser] = useState<StoredUser | null>(null);
  const [inventory, setInventory] = useState<InventoryPayload | null>(null);
  const [error, setError] = useState("");
  const [siteForm, setSiteForm] = useState<InventorySiteCreateInput>(INITIAL_SITE_FORM);
  const [siteFieldErrors, setSiteFieldErrors] = useState<Record<string, string[]>>({});
  const [siteMutationError, setSiteMutationError] = useState("");
  const [siteMutationSuccess, setSiteMutationSuccess] = useState("");
  const [unitForm, setUnitForm] = useState<InventoryUnitMutationInput>(INITIAL_UNIT_FORM);
  const [editingUnitId, setEditingUnitId] = useState<number | null>(null);
  const [unitFieldErrors, setUnitFieldErrors] = useState<Record<string, string[]>>({});
  const [unitMutationError, setUnitMutationError] = useState("");
  const [unitMutationSuccess, setUnitMutationSuccess] = useState("");
  const [unitEditHint, setUnitEditHint] = useState("");
  const [unitLibraryNotice, setUnitLibraryNotice] = useState("");
  const [pendingUnitImages, setPendingUnitImages] = useState<PendingUnitImage[]>([]);
  const [primaryPendingUnitImageId, setPrimaryPendingUnitImageId] = useState<string | null>(null);
  const [unitImageUploadProgress, setUnitImageUploadProgress] = useState(0);
  const [unitFilters, setUnitFilters] = useState<UnitFilters>(INITIAL_UNIT_FILTERS);
  const [siteListFilters, setSiteListFilters] = useState<InventorySiteListFilters>(INITIAL_SITE_LIST_FILTERS);
  const [siteList, setSiteList] = useState<Awaited<ReturnType<typeof fetchInventorySiteList>> | null>(null);
  const [siteListError, setSiteListError] = useState("");
  const [isUnitFormHighlighted, setIsUnitFormHighlighted] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSiteListLoading, setIsSiteListLoading] = useState(true);
  const [isSiteSubmitting, setIsSiteSubmitting] = useState(false);
  const [isUnitSubmitting, setIsUnitSubmitting] = useState(false);
  const [activeSiteId, setActiveSiteId] = useState<number | null>(null);

  const canManageImages = WRITE_ROLES.has(user?.role ?? "");
  const canManageSites = ADMIN_ROLES.has(user?.role ?? "");
  const canManageUnits = WRITE_ROLES.has(user?.role ?? "");

  useEffect(() => {
    return () => {
      for (const image of pendingUnitImages) {
        URL.revokeObjectURL(image.previewUrl);
      }
    };
  }, [pendingUnitImages]);

  useEffect(() => {
    return () => {
      if (unitFormHighlightTimeoutRef.current) {
        window.clearTimeout(unitFormHighlightTimeoutRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!editingUnitId) {
      return;
    }

    const scrollToEditor = () => {
      const editor = document.getElementById("media-unit-editor");
      if (editor) {
        editor.scrollIntoView({ behavior: "smooth", block: "start" });
        unitCodeInputRef.current?.focus({ preventScroll: true });
        triggerUnitFormHighlight();
        return;
      }

      window.location.hash = "media-unit-editor";
    };

    const frameId = window.requestAnimationFrame(() => {
      window.setTimeout(scrollToEditor, 0);
    });

    return () => window.cancelAnimationFrame(frameId);
  }, [editingUnitId]);

  function triggerUnitFormHighlight() {
    setIsUnitFormHighlighted(true);
    if (unitFormHighlightTimeoutRef.current) {
      window.clearTimeout(unitFormHighlightTimeoutRef.current);
    }
    unitFormHighlightTimeoutRef.current = window.setTimeout(() => {
      setIsUnitFormHighlighted(false);
      unitFormHighlightTimeoutRef.current = null;
    }, 3000);
  }

  const loadInventory = useCallback(async (profileHint?: StoredUser | null) => {
    setIsLoading(true);
    setError("");

    try {
      const profile = profileHint ?? (await fetchCurrentUser());
      if (profile) {
        setUser(profile);
      }

      const payload = await fetchInventoryData();
      setInventory(payload);
      setUnitForm((current) => ({
        ...current,
        site: current.site || payload.sites[0]?.id || 0,
      }));
    } catch (loadError) {
      const message = loadError instanceof Error ? loadError.message : "Unable to load inventory.";
      setError(message);
      if (message.includes("sign in again")) {
        router.replace("/login");
      }
    } finally {
      setIsLoading(false);
    }
  }, [router]);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) {
      router.replace("/login");
      return;
    }

    const storedUser = getStoredUser();
    if (storedUser) {
      setUser(storedUser);
    }

    void loadInventory(storedUser);
  }, [loadInventory, router]);

  function handleLogout() {
    clearAuthSession();
    router.replace("/login");
  }

  const inventoryStats = useMemo(() => {
    const units = inventory?.units ?? [];
    const sites = inventory?.sites ?? [];

    return {
      totalSites: sites.length,
      totalUnits: units.length,
      availableUnits: units.filter((unit) => unit.status === "available").length,
      imagedSites: sites.filter((site) => (site.image_gallery ?? []).length > 0).length,
    };
  }, [inventory]);

  const siteMap = useMemo(() => {
    const mapping = new Map<number, { label: string; city: string; name: string; code: string }>();
    for (const site of inventory?.sites ?? []) {
      mapping.set(site.id, {
        label: `${site.code} • ${site.name}`,
        city: site.city,
        name: site.name,
        code: site.code,
      });
    }
    return mapping;
  }, [inventory]);

  const sortedSites = inventory?.sites ?? [];
  const filteredUnits = useMemo(() => {
    return (inventory?.units ?? []).filter((unit) => {
      const site = siteMap.get(unit.site);
      const direction = (unit.facing_direction ?? "").toLowerCase();
      const directionFilter = unitFilters.facing_direction.trim().toLowerCase();

      if (unitFilters.city && site?.city !== unitFilters.city) {
        return false;
      }
      if (unitFilters.status && unit.status !== unitFilters.status) {
        return false;
      }
      if (unitFilters.site_type && (unit.site_type ?? "") !== unitFilters.site_type) {
        return false;
      }
      if (directionFilter && !direction.includes(directionFilter)) {
        return false;
      }

      return true;
    });
  }, [inventory?.units, siteMap, unitFilters]);

  const filterCities = useMemo(
    () => Array.from(new Set((inventory?.sites ?? []).map((site) => site.city).filter(Boolean))).sort(),
    [inventory?.sites],
  );
  const filterStatuses = useMemo(
    () => Array.from(new Set((inventory?.units ?? []).map((unit) => unit.status).filter(Boolean))).sort(),
    [inventory?.units],
  );
  const filterMediaTypes = useMemo(
    () => Array.from(new Set((inventory?.sites ?? []).map((site) => site.site_type).filter(Boolean))).sort(),
    [inventory?.sites],
  );
  const filterFacingDirections = useMemo(
    () => Array.from(new Set((inventory?.units ?? []).map((unit) => unit.facing_direction).filter(Boolean))).sort(),
    [inventory?.units],
  );
  const siteListTotalPages = Math.max(1, Math.ceil((siteList?.count ?? 0) / SITE_LIST_PAGE_SIZE));

  const loadSiteList = useCallback(async (filters: InventorySiteListFilters) => {
    setIsSiteListLoading(true);
    setSiteListError("");

    try {
      const payload = await fetchInventorySiteList(filters);
      setSiteList(payload);
    } catch (loadError) {
      const message = loadError instanceof Error ? loadError.message : "Unable to load all sites.";
      setSiteListError(message);
      if (message.includes("sign in again")) {
        router.replace("/login");
      }
    } finally {
      setIsSiteListLoading(false);
    }
  }, [router]);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) {
      return;
    }

    void loadSiteList(siteListFilters);
  }, [loadSiteList, siteListFilters]);

  async function handleSiteImageUpload(
    siteId: number,
    payload: { file: File; caption: string; isPrimary: boolean; onProgress?: (progress: number) => void },
  ) {
    try {
      await uploadSiteImage({
        site: siteId,
        image: payload.file,
        caption: payload.caption,
        is_primary: payload.isPrimary,
        onProgress: payload.onProgress,
      });
      await loadInventory(user);
      await loadSiteList(siteListFilters);
    } catch (error) {
      throw new Error(getSiteImageMutationError(error).message);
    }
  }

  async function handleSitePrimary(imageId: number) {
    try {
      await updateSiteImage(imageId, { is_primary: true });
      await loadInventory(user);
      await loadSiteList(siteListFilters);
    } catch (error) {
      throw new Error(getSiteImageMutationError(error).message);
    }
  }

  async function handleSiteDelete(imageId: number) {
    try {
      await deleteSiteImage(imageId);
      await loadInventory(user);
      await loadSiteList(siteListFilters);
    } catch (error) {
      throw new Error(getSiteImageMutationError(error).message);
    }
  }

  async function handleUnitImageUpload(
    unitId: number,
    payload: { file: File; caption: string; isPrimary: boolean; onProgress?: (progress: number) => void },
  ) {
    try {
      await uploadMediaUnitImage({
        media_unit: unitId,
        image: payload.file,
        caption: payload.caption,
        is_primary: payload.isPrimary,
        onProgress: payload.onProgress,
      });
      await loadInventory(user);
      await loadSiteList(siteListFilters);
    } catch (error) {
      throw new Error(getMediaUnitImageMutationError(error).message);
    }
  }

  async function handleUnitPrimary(imageId: number) {
    try {
      await updateMediaUnitImage(imageId, { is_primary: true });
      await loadInventory(user);
      await loadSiteList(siteListFilters);
    } catch (error) {
      throw new Error(getMediaUnitImageMutationError(error).message);
    }
  }

  async function handleUnitDelete(imageId: number) {
    try {
      await deleteMediaUnitImage(imageId);
      await loadInventory(user);
      await loadSiteList(siteListFilters);
    } catch (error) {
      throw new Error(getMediaUnitImageMutationError(error).message);
    }
  }

  function updateSiteForm<K extends keyof InventorySiteCreateInput>(field: K, value: InventorySiteCreateInput[K]) {
    setSiteMutationError("");
    setSiteMutationSuccess("");
    setSiteFieldErrors({});
    setSiteForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  function resetUnitForm(nextSiteId?: number) {
    setEditingUnitId(null);
    setUnitFieldErrors({});
    setUnitMutationError("");
    setUnitMutationSuccess("");
    setUnitEditHint("");
    setUnitLibraryNotice("");
    setIsUnitFormHighlighted(false);
    setUnitImageUploadProgress(0);
    if (unitFormHighlightTimeoutRef.current) {
      window.clearTimeout(unitFormHighlightTimeoutRef.current);
      unitFormHighlightTimeoutRef.current = null;
    }
    for (const image of pendingUnitImages) {
      URL.revokeObjectURL(image.previewUrl);
    }
    setPendingUnitImages([]);
    setPrimaryPendingUnitImageId(null);
    setUnitForm({
      ...INITIAL_UNIT_FORM,
      site: nextSiteId ?? inventory?.sites?.[0]?.id ?? 0,
    });
  }

  function updateUnitForm<K extends keyof InventoryUnitMutationInput>(field: K, value: InventoryUnitMutationInput[K]) {
    setUnitMutationError("");
    setUnitMutationSuccess("");
    setUnitFieldErrors({});
    setUnitForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  async function handleCreateSite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isSiteSubmitting) {
      return;
    }

    setSiteMutationError("");
    setSiteMutationSuccess("");
    setSiteFieldErrors({});
    setIsSiteSubmitting(true);

    try {
      await createSite({
        ...siteForm,
        latitude: siteForm.latitude || null,
        longitude: siteForm.longitude || null,
      });
      setSiteMutationSuccess("Site created successfully.");
      setSiteForm(INITIAL_SITE_FORM);
      await loadInventory(user);
      await loadSiteList(siteListFilters);
    } catch (siteError) {
      const normalized = getInventorySiteMutationError(siteError);
      setSiteMutationError(normalized.message);
      setSiteFieldErrors(normalized.fieldErrors);
    } finally {
      setIsSiteSubmitting(false);
    }
  }

  async function handleDeleteSite(siteId: number, siteName: string) {
    if (activeSiteId) {
      return;
    }

    const confirmed = window.confirm(
      `Delete ${siteName}? This will also remove its units, images, and related inventory data that is not protected by active bookings.`,
    );
    if (!confirmed) {
      return;
    }

    setSiteMutationError("");
    setSiteMutationSuccess("");
    setSiteFieldErrors({});
    setActiveSiteId(siteId);

    try {
      await deleteSite(siteId);
      setSiteMutationSuccess("Site deleted successfully.");
      await loadInventory(user);
      await loadSiteList(siteListFilters);
    } catch (siteError) {
      const normalized = getInventorySiteMutationError(siteError);
      setSiteMutationError(normalized.message);
      setSiteFieldErrors(normalized.fieldErrors);
    } finally {
      setActiveSiteId(null);
    }
  }

  function handleEditUnit(unitId: number) {
    const unit = inventory?.units.find((entry) => entry.id === unitId);
    if (!unit) {
      return;
    }

    for (const image of pendingUnitImages) {
      URL.revokeObjectURL(image.previewUrl);
    }
    setEditingUnitId(unit.id);
    setUnitFieldErrors({});
    setUnitMutationError("");
    setUnitMutationSuccess("");
    setUnitEditHint("Unit details loaded. Update the fields and click Save Changes.");
    setUnitLibraryNotice("Unit loaded for editing. Taking you to the edit form...");
    setPendingUnitImages([]);
    setPrimaryPendingUnitImageId(null);
    setUnitImageUploadProgress(0);
    setUnitForm({
      site: unit.site,
      unit_code: unit.unit_code,
      face_count: unit.face_count,
      width: unit.width,
      height: unit.height,
      status: unit.status,
      is_illuminated: unit.is_illuminated,
      monthly_rate: unit.monthly_rate,
      facing_direction: unit.facing_direction ?? "",
      site_type: unit.site_type ?? "",
    });
  }

  async function handleSubmitUnit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isUnitSubmitting) {
      return;
    }

    setUnitMutationError("");
    setUnitMutationSuccess("");
    setUnitFieldErrors({});
    setIsUnitSubmitting(true);

    try {
      let savedUnit;
      if (editingUnitId) {
        savedUnit = await updateMediaUnit(editingUnitId, {
          ...unitForm,
          facing_direction: unitForm.facing_direction || "",
          site_type: unitForm.site_type || "single_side",
          monthly_rate: Number(unitForm.monthly_rate).toFixed(2),
        });
      } else {
        savedUnit = await createMediaUnit({
          ...unitForm,
          facing_direction: unitForm.facing_direction || "",
          site_type: unitForm.site_type || "single_side",
          monthly_rate: Number(unitForm.monthly_rate).toFixed(2),
        });
      }

      const uploadedCount = await uploadPendingImagesForUnit(savedUnit.id);
      setUnitMutationSuccess(
        editingUnitId
          ? uploadedCount > 0
            ? `Media unit updated and ${uploadedCount} image(s) uploaded successfully.`
            : "Media unit updated successfully."
          : uploadedCount > 0
            ? `Media unit created and ${uploadedCount} image(s) uploaded successfully.`
            : "Media unit created successfully.",
      );
      await loadInventory(user);
      await loadSiteList(siteListFilters);
      resetUnitForm(savedUnit.site || unitForm.site || inventory?.sites?.[0]?.id);
    } catch (unitError) {
      const normalized = getInventoryUnitMutationError(unitError);
      setUnitMutationError(normalized.message);
      setUnitFieldErrors(normalized.fieldErrors);
    } finally {
      setIsUnitSubmitting(false);
    }
  }

  function updateUnitFilter<K extends keyof UnitFilters>(field: K, value: UnitFilters[K]) {
    setUnitFilters((current) => ({
      ...current,
      [field]: value,
    }));
  }

  function updateSiteListFilter<K extends keyof InventorySiteListFilters>(field: K, value: InventorySiteListFilters[K]) {
    setSiteListFilters((current) => ({
      ...current,
      [field]: value,
      page: 1,
      page_size: SITE_LIST_PAGE_SIZE,
    }));
  }

  function handlePendingUnitImagesChange(event: ChangeEvent<HTMLInputElement>) {
    for (const image of pendingUnitImages) {
      URL.revokeObjectURL(image.previewUrl);
    }

    const nextImages = Array.from(event.target.files ?? []).map((file, index) => ({
      id: `${file.name}-${file.size}-${index}`,
      file,
      previewUrl: URL.createObjectURL(file),
      caption: file.name.replace(/\.[^.]+$/, ""),
    }));

    setPendingUnitImages(nextImages);
    setPrimaryPendingUnitImageId(nextImages[0]?.id ?? null);
    setUnitImageUploadProgress(0);
  }

  function updatePendingUnitImageCaption(imageId: string, caption: string) {
    setPendingUnitImages((current) =>
      current.map((image) => (image.id === imageId ? { ...image, caption } : image)),
    );
  }

  async function uploadPendingImagesForUnit(unitId: number) {
    if (pendingUnitImages.length === 0) {
      return 0;
    }

    const primaryId = primaryPendingUnitImageId ?? pendingUnitImages[0]?.id ?? null;

    for (let index = 0; index < pendingUnitImages.length; index += 1) {
      const image = pendingUnitImages[index];
      await uploadMediaUnitImage({
        media_unit: unitId,
        image: image.file,
        caption: image.caption.trim(),
        is_primary: image.id === primaryId,
        onProgress: (progress) => {
          const aggregate = Math.round(((index + progress / 100) / pendingUnitImages.length) * 100);
          setUnitImageUploadProgress(aggregate);
        },
      });
    }

    setUnitImageUploadProgress(100);
    return pendingUnitImages.length;
  }

  return (
    <AppShell
      active="inventory"
      roleLabel={user?.role ?? "Team member"}
      userEmail={user?.email ?? "Loading user..."}
      title="Inventory command"
      eyebrow="Inventory"
      description="Manage live site and media-unit imagery alongside operational inventory details for planning and booking."
      onLogout={handleLogout}
    >
      {error ? <p className="error dashboard-error">{error}</p> : null}

      {canManageSites ? (
        <section className="module-card creation-panel">
          <div className="module-head">
            <h2>Create site</h2>
            <span>Admin only</span>
          </div>
          <p className="section-copy creation-copy">
            Add a new inventory site without leaving the dashboard. Deletion stays protected if the site is tied to active bookings.
            Location coordinates are optional and will be auto-captured during the first verified POE upload.
          </p>
          {siteMutationError ? <p className="error">{siteMutationError}</p> : null}
          {siteMutationSuccess ? <p className="success">{siteMutationSuccess}</p> : null}
          <form className="site-form-grid" onSubmit={handleCreateSite}>
            <div className="field field-full">
              <label htmlFor="site-name">Site name</label>
              <input
                id="site-name"
                value={siteForm.name}
                onChange={(event) => updateSiteForm("name", event.target.value)}
                placeholder="Airport Arrival Billboard"
                required
              />
              {siteFieldErrors.name?.length ? <p className="field-help field-help-error">{siteFieldErrors.name[0]}</p> : null}
            </div>
            <div className="field">
              <label htmlFor="site-code">Site code</label>
              <input
                id="site-code"
                value={siteForm.code}
                onChange={(event) => updateSiteForm("code", event.target.value.toUpperCase())}
                placeholder="SITE-003"
                required
              />
              {siteFieldErrors.code?.length ? <p className="field-help field-help-error">{siteFieldErrors.code[0]}</p> : null}
            </div>
            <div className="field">
              <label htmlFor="site-type">Site type</label>
              <select
                id="site-type"
                value={siteForm.site_type}
                onChange={(event) => updateSiteForm("site_type", event.target.value)}
              >
                <option value="billboard">Billboard</option>
                <option value="transit">Transit</option>
                <option value="street_furniture">Street furniture</option>
                <option value="digital">Digital</option>
              </select>
              {siteFieldErrors.site_type?.length ? <p className="field-help field-help-error">{siteFieldErrors.site_type[0]}</p> : null}
            </div>
            <div className="field field-full">
              <label htmlFor="site-address">Address</label>
              <input
                id="site-address"
                value={siteForm.address}
                onChange={(event) => updateSiteForm("address", event.target.value)}
                placeholder="Airport Road, Terminal 2 approach"
                required
              />
              {siteFieldErrors.address?.length ? <p className="field-help field-help-error">{siteFieldErrors.address[0]}</p> : null}
            </div>
            <div className="field">
              <label htmlFor="site-city">City</label>
              <input
                id="site-city"
                value={siteForm.city}
                onChange={(event) => updateSiteForm("city", event.target.value)}
                placeholder="Pune"
                required
              />
              {siteFieldErrors.city?.length ? <p className="field-help field-help-error">{siteFieldErrors.city[0]}</p> : null}
            </div>
            <div className="field">
              <label htmlFor="site-state">State</label>
              <input
                id="site-state"
                value={siteForm.state}
                onChange={(event) => updateSiteForm("state", event.target.value)}
                placeholder="Maharashtra"
                required
              />
              {siteFieldErrors.state?.length ? <p className="field-help field-help-error">{siteFieldErrors.state[0]}</p> : null}
            </div>
            <div className="field">
              <label htmlFor="site-latitude">Latitude</label>
              <input
                id="site-latitude"
                value={siteForm.latitude ?? ""}
                onChange={(event) => updateSiteForm("latitude", event.target.value)}
                placeholder="18.520430"
              />
              {siteFieldErrors.latitude?.length ? (
                <p className="field-help field-help-error">{siteFieldErrors.latitude[0]}</p>
              ) : (
                <p className="field-help">Auto-captured during first verified POE if left blank.</p>
              )}
            </div>
            <div className="field">
              <label htmlFor="site-longitude">Longitude</label>
              <input
                id="site-longitude"
                value={siteForm.longitude ?? ""}
                onChange={(event) => updateSiteForm("longitude", event.target.value)}
                placeholder="73.856743"
              />
              {siteFieldErrors.longitude?.length ? (
                <p className="field-help field-help-error">{siteFieldErrors.longitude[0]}</p>
              ) : (
                <p className="field-help">Coordinates lock after POE verification.</p>
              )}
            </div>
            <div className="form-actions field-full">
              <button className="submit" type="submit" disabled={isSiteSubmitting || isLoading}>
                {isSiteSubmitting ? "Creating site..." : "Create site"}
              </button>
            </div>
          </form>
        </section>
      ) : null}

      <section className="summary-row" aria-label="Inventory stats">
        <article className="summary-card">
          <p className="stat-label">Sites</p>
          <p className="summary-value">{isLoading ? "..." : inventoryStats.totalSites}</p>
        </article>
        <article className="summary-card">
          <p className="stat-label">Units</p>
          <p className="summary-value">{isLoading ? "..." : inventoryStats.totalUnits}</p>
        </article>
        <article className="summary-card">
          <p className="stat-label">Available</p>
          <p className="summary-value">{isLoading ? "..." : inventoryStats.availableUnits}</p>
        </article>
        <article className="summary-card">
          <p className="stat-label">Sites with imagery</p>
          <p className="summary-value">{isLoading ? "..." : inventoryStats.imagedSites}</p>
        </article>
      </section>

      <section className="module-grid">
        <article className="module-card">
          <div className="module-head">
            <h2>Image operations</h2>
            <span>{canManageImages ? "Write access" : "View only"}</span>
          </div>
          <div className="module-stats">
            <div className="module-stat">
              <p className="stat-label">Site galleries</p>
              <p className="stat-value">{isLoading ? "..." : inventory?.sites?.length ?? 0}</p>
            </div>
            <div className="module-stat">
              <p className="stat-label">Unit galleries</p>
              <p className="stat-value">{isLoading ? "..." : inventory?.units?.length ?? 0}</p>
            </div>
          </div>
        </article>

        <article className="module-card">
          <div className="module-head">
            <h2>Primary image coverage</h2>
            <span>Inventory</span>
          </div>
          <div className="module-stats">
            <div className="module-stat">
              <p className="stat-label">Sites with primary image</p>
              <p className="stat-value">
                {isLoading ? "..." : (inventory?.sites ?? []).filter((site) => Boolean(site.primary_image)).length}
              </p>
            </div>
            <div className="module-stat">
              <p className="stat-label">Units with primary image</p>
              <p className="stat-value">
                {isLoading ? "..." : (inventory?.units ?? []).filter((unit) => Boolean(unit.primary_image)).length}
              </p>
            </div>
          </div>
        </article>

        <article className="module-card module-card-highlight">
          <div className="module-head">
            <h2>Workflow note</h2>
            <span>Bookings + POE</span>
          </div>
          <div className="module-stats">
            <div className="module-stat">
              <p className="stat-label">Downstream usage</p>
              <p className="table-wrap">
                These images are reused in booking previews and field proof-of-execution capture so operations teams can verify the right location before installation.
              </p>
            </div>
          </div>
        </article>
      </section>

      <section className="inventory-section" aria-labelledby="all-sites-heading">
        <div className="module-head">
          <div>
            <h2 id="all-sites-heading">All Sites</h2>
            <p className="site-copy">Inventory list</p>
          </div>
          <span>{isSiteListLoading ? "Loading" : `${siteList?.count ?? 0} sites`}</span>
        </div>

        <section className="module-card inventory-filter-panel">
          <div className="inventory-filter-grid inventory-list-filter-grid">
            <div className="field">
              <label htmlFor="site-list-search">Search</label>
              <input
                id="site-list-search"
                value={siteListFilters.search ?? ""}
                onChange={(event) => updateSiteListFilter("search", event.target.value)}
                placeholder="Site, unit, city, address"
              />
            </div>
            <div className="field">
              <label htmlFor="site-list-city">City</label>
              <select
                id="site-list-city"
                value={siteListFilters.city ?? ""}
                onChange={(event) => updateSiteListFilter("city", event.target.value)}
              >
                <option value="">All cities</option>
                {filterCities.map((city) => (
                  <option key={city} value={city}>
                    {city}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="site-list-status">Status</label>
              <select
                id="site-list-status"
                value={siteListFilters.status ?? ""}
                onChange={(event) => updateSiteListFilter("status", event.target.value)}
              >
                <option value="">All statuses</option>
                {SITE_LIST_STATUS_OPTIONS.map((status) => (
                  <option key={status} value={status}>
                    {formatSiteListStatus(status)}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="site-list-media-type">Media type</label>
              <select
                id="site-list-media-type"
                value={siteListFilters.media_type ?? ""}
                onChange={(event) => updateSiteListFilter("media_type", event.target.value)}
              >
                <option value="">All media</option>
                {filterMediaTypes.map((mediaType) => (
                  <option key={mediaType} value={mediaType}>
                    {formatChoice(mediaType)}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="site-list-facing-direction">Facing direction</label>
              <input
                id="site-list-facing-direction"
                list="site-list-facing-options"
                value={siteListFilters.facing_direction ?? ""}
                onChange={(event) => updateSiteListFilter("facing_direction", event.target.value)}
                placeholder="Toward Jammu City"
              />
              <datalist id="site-list-facing-options">
                {filterFacingDirections.map((direction) => (
                  <option key={direction} value={direction} />
                ))}
              </datalist>
            </div>
            <div className="field">
              <label htmlFor="site-list-unit-site-type">Site type</label>
              <select
                id="site-list-unit-site-type"
                value={siteListFilters.site_type ?? ""}
                onChange={(event) => updateSiteListFilter("site_type", event.target.value)}
              >
                <option value="">All types</option>
                {MEDIA_UNIT_SITE_TYPE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-actions field-full">
              <button className="ghost" type="button" onClick={() => setSiteListFilters(INITIAL_SITE_LIST_FILTERS)}>
                Clear filters
              </button>
            </div>
          </div>
        </section>

        {siteListError ? <p className="error">{siteListError}</p> : null}
        {isSiteListLoading ? <p className="empty-state">Loading inventory list...</p> : null}
        {!isSiteListLoading && !siteListError && (siteList?.results?.length ?? 0) === 0 ? (
          <p className="empty-state">No sites match the current filters.</p>
        ) : null}

        {!isSiteListLoading && !siteListError && (siteList?.results?.length ?? 0) > 0 ? (
          <>
            <div className="inventory-table-wrap all-sites-table-wrap">
              <table className="inventory-table all-sites-table">
                <thead>
                  <tr>
                    <th>Image</th>
                    <th>Site</th>
                    <th>Location</th>
                    <th>Media</th>
                    <th>Status</th>
                    <th>Updated</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {siteList?.results.map((site) => {
                    const primaryUnitId = site.unit_ids[0] ?? null;
                    return (
                      <tr key={site.site_id}>
                        <td>
                          <SafeImage
                            src={site.thumbnail_url}
                            alt={`${site.title} thumbnail`}
                            className="all-sites-thumb"
                            fallback={<div className="all-sites-thumb all-sites-thumb-empty">No image</div>}
                          />
                        </td>
                        <td>
                          <div className="table-primary">
                            <strong>{site.title}</strong>
                            <span>{site.site_code}</span>
                          </div>
                          <p className="site-copy all-sites-unit-codes">
                            {site.unit_codes.length > 0 ? site.unit_codes.join(", ") : "No units yet"}
                          </p>
                        </td>
                        <td>
                          <strong>{site.city || "City pending"}</strong>
                          <p className="site-copy">{[site.address, site.state].filter(Boolean).join(", ")}</p>
                        </td>
                        <td>
                          <p>{formatChoice(site.media_type)}</p>
                          <p className="site-copy">{site.dimensions || "Size pending"}</p>
                          <p className="site-copy">{site.facing_direction || "Direction pending"}</p>
                          <p className="site-copy">{formatUnitSiteTypes(site.unit_site_type)}</p>
                        </td>
                        <td>
                          <span className={`status-pill status-${site.status}`}>{formatSiteListStatus(site.status)}</span>
                        </td>
                        <td>{formatDate(site.updated_at)}</td>
                        <td>
                          <div className="all-sites-actions">
                            <a className="ghost table-action" href={`#site-image-${site.site_id}-file`}>
                              View
                            </a>
                            {canManageUnits && primaryUnitId ? (
                              <button className="ghost table-action" type="button" onClick={() => handleEditUnit(primaryUnitId)}>
                                Edit
                              </button>
                            ) : null}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="pagination-row">
              <button
                className="ghost"
                type="button"
                disabled={(siteListFilters.page ?? 1) <= 1 || isSiteListLoading}
                onClick={() =>
                  setSiteListFilters((current) => ({
                    ...current,
                    page: Math.max(1, (current.page ?? 1) - 1),
                    page_size: SITE_LIST_PAGE_SIZE,
                  }))
                }
              >
                Previous
              </button>
              <span>
                Page {siteListFilters.page ?? 1} of {siteListTotalPages}
              </span>
              <button
                className="ghost"
                type="button"
                disabled={(siteListFilters.page ?? 1) >= siteListTotalPages || isSiteListLoading}
                onClick={() =>
                  setSiteListFilters((current) => ({
                    ...current,
                    page: Math.min(siteListTotalPages, (current.page ?? 1) + 1),
                    page_size: SITE_LIST_PAGE_SIZE,
                  }))
                }
              >
                Next
              </button>
            </div>
          </>
        ) : null}
      </section>

      {canManageUnits ? (
        <section
          id="media-unit-editor"
          className={`module-card creation-panel${isUnitFormHighlighted ? " creation-panel-active" : ""}`}
          ref={unitFormSectionRef}
        >
          <div className="module-head">
            <h2>{editingUnitId ? `Editing Media Unit${unitForm.unit_code ? `: ${unitForm.unit_code}` : ""}` : "Create media unit"}</h2>
            <span>{editingUnitId ? "Update unit" : "Admin + operations"}</span>
          </div>
          <p className="section-copy creation-copy">
            Use one site for the physical structure, and create a separate media unit for each sellable face or direction.
          </p>
          {unitEditHint ? <p className="info">{unitEditHint}</p> : null}
          {unitMutationError ? <p className="error">{unitMutationError}</p> : null}
          {unitMutationSuccess ? <p className="success">{unitMutationSuccess}</p> : null}
          <form className="site-form-grid" onSubmit={handleSubmitUnit}>
            <div className="field">
              <label htmlFor="unit-site">Site</label>
              <select
                id="unit-site"
                value={unitForm.site || ""}
                onChange={(event) => updateUnitForm("site", Number(event.target.value))}
                required
              >
                <option value="" disabled>
                  Select site
                </option>
                {sortedSites.map((site) => (
                  <option key={site.id} value={site.id}>
                    {site.name} ({site.code})
                  </option>
                ))}
              </select>
              {unitFieldErrors.site?.length ? <p className="field-help field-help-error">{unitFieldErrors.site[0]}</p> : null}
            </div>
            <div className="field">
              <label htmlFor="unit-code">Media unit code</label>
              <input
                id="unit-code"
                ref={unitCodeInputRef}
                value={unitForm.unit_code}
                onChange={(event) => updateUnitForm("unit_code", event.target.value.toUpperCase())}
                placeholder="SIDCO-A"
                required
              />
              {unitFieldErrors.unit_code?.length ? <p className="field-help field-help-error">{unitFieldErrors.unit_code[0]}</p> : null}
            </div>
            <div className="field field-full">
              <label htmlFor="unit-facing-direction">Facing direction</label>
              <input
                id="unit-facing-direction"
                value={unitForm.facing_direction ?? ""}
                onChange={(event) => updateUnitForm("facing_direction", event.target.value)}
                placeholder="Example: Toward Jammu City"
              />
              <p className="field-help">Use the direction visible to traffic or pedestrians for this sellable face.</p>
              {unitFieldErrors.facing_direction?.length ? <p className="field-help field-help-error">{unitFieldErrors.facing_direction[0]}</p> : null}
            </div>
            <div className="field">
              <label htmlFor="unit-site-type">Media unit site type</label>
              <select
                id="unit-site-type"
                value={unitForm.site_type ?? ""}
                onChange={(event) => updateUnitForm("site_type", event.target.value)}
              >
                <option value="">Select type</option>
                {MEDIA_UNIT_SITE_TYPE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              <p className="field-help">Choose whether this unit sells one side or both sides.</p>
              {unitFieldErrors.site_type?.length ? <p className="field-help field-help-error">{unitFieldErrors.site_type[0]}</p> : null}
            </div>
            <div className="field">
              <label htmlFor="unit-face-count">Face count</label>
              <input
                id="unit-face-count"
                type="number"
                min="1"
                step="1"
                value={unitForm.face_count}
                onChange={(event) => updateUnitForm("face_count", Number(event.target.value))}
                required
              />
              {unitFieldErrors.face_count?.length ? <p className="field-help field-help-error">{unitFieldErrors.face_count[0]}</p> : null}
            </div>
            <div className="field">
              <label htmlFor="unit-status">Status</label>
              <select
                id="unit-status"
                value={unitForm.status}
                onChange={(event) => updateUnitForm("status", event.target.value)}
              >
                <option value="available">Available</option>
                <option value="reserved">Reserved</option>
                <option value="maintenance">Maintenance</option>
                <option value="retired">Retired</option>
              </select>
              {unitFieldErrors.status?.length ? <p className="field-help field-help-error">{unitFieldErrors.status[0]}</p> : null}
            </div>
            <div className="field">
              <label htmlFor="unit-width">Width</label>
              <input
                id="unit-width"
                type="number"
                min="0"
                step="0.01"
                value={unitForm.width}
                onChange={(event) => updateUnitForm("width", event.target.value)}
                placeholder="20.00"
                required
              />
              {unitFieldErrors.width?.length ? <p className="field-help field-help-error">{unitFieldErrors.width[0]}</p> : null}
            </div>
            <div className="field">
              <label htmlFor="unit-height">Height</label>
              <input
                id="unit-height"
                type="number"
                min="0"
                step="0.01"
                value={unitForm.height}
                onChange={(event) => updateUnitForm("height", event.target.value)}
                placeholder="10.00"
                required
              />
              {unitFieldErrors.height?.length ? <p className="field-help field-help-error">{unitFieldErrors.height[0]}</p> : null}
            </div>
            <div className="field">
              <label htmlFor="unit-rate">Monthly rate</label>
              <input
                id="unit-rate"
                type="number"
                min="0"
                step="0.01"
                value={unitForm.monthly_rate}
                onChange={(event) => updateUnitForm("monthly_rate", event.target.value)}
                placeholder="50000.00"
                required
              />
              {unitFieldErrors.monthly_rate?.length ? <p className="field-help field-help-error">{unitFieldErrors.monthly_rate[0]}</p> : null}
            </div>
            <label className="checkbox-field" htmlFor="unit-illuminated">
              <input
                id="unit-illuminated"
                type="checkbox"
                checked={unitForm.is_illuminated}
                onChange={(event) => updateUnitForm("is_illuminated", event.target.checked)}
              />
              <span>Illuminated face</span>
            </label>
            <div className="field field-full">
              <label htmlFor="unit-images">Media unit images</label>
              <input
                id="unit-images"
                type="file"
                accept="image/*"
                multiple
                onChange={handlePendingUnitImagesChange}
              />
              <p className="field-help">
                {editingUnitId
                  ? "Add new images while editing. They will upload automatically after the unit update is saved."
                  : "Choose one or more images. The unit will be created first, then the selected images will upload automatically."}
              </p>
              {isUnitSubmitting && pendingUnitImages.length > 0 ? (
                <p className="field-help">Uploading selected images... {unitImageUploadProgress}%</p>
              ) : null}
            </div>
            {pendingUnitImages.length > 0 ? (
              <div className="field field-full unit-upload-preview-grid">
                {pendingUnitImages.map((image) => (
                  <article className="upload-preview-card upload-preview-card-stacked" key={image.id}>
                    <img className="upload-preview-image" src={image.previewUrl} alt={image.file.name} />
                    <div className="upload-preview-copy">
                      <p className="site-copy">{image.file.name}</p>
                      <label className="field">
                        <span>Caption</span>
                        <input
                          value={image.caption}
                          onChange={(event) => updatePendingUnitImageCaption(image.id, event.target.value)}
                          placeholder="Optional caption"
                        />
                      </label>
                      <label className="checkbox-field">
                        <input
                          type="radio"
                          name="primary-unit-upload-image"
                          checked={primaryPendingUnitImageId === image.id}
                          onChange={() => setPrimaryPendingUnitImageId(image.id)}
                        />
                        <span>Set as primary image</span>
                      </label>
                    </div>
                  </article>
                ))}
              </div>
            ) : null}
            <div className="form-actions field-full">
              {editingUnitId ? (
                <button className="ghost" type="button" onClick={() => resetUnitForm(unitForm.site)}>
                  Cancel Edit
                </button>
              ) : null}
              <button className="submit" type="submit" disabled={isUnitSubmitting || isLoading || sortedSites.length === 0}>
                {isUnitSubmitting ? (editingUnitId ? "Saving changes..." : "Creating unit...") : editingUnitId ? "Save Changes" : "Create Media Unit"}
              </button>
            </div>
          </form>
        </section>
      ) : null}

      <section className="inventory-section">
        <div className="module-head">
          <h2>Site image library</h2>
          <span>{inventory?.sites?.length ?? 0} sites</span>
        </div>
        {siteMutationError && !canManageSites ? <p className="error">{siteMutationError}</p> : null}
        {siteMutationSuccess && !canManageSites ? <p className="success">{siteMutationSuccess}</p> : null}
        <div className="image-manager-grid">
          {(inventory?.sites ?? []).map((site) => (
            <ImageManagerCard
              key={site.id}
              formIdPrefix={`site-image-${site.id}`}
              title={site.name}
              eyebrow={site.code}
              description={site.address}
              meta={`${site.city}, ${site.state} • ${site.site_type.replaceAll("_", " ")}`}
              images={site.image_gallery ?? []}
              primaryImage={site.primary_image ?? null}
              showHeroPreview={false}
              canManage={canManageImages}
              uploadLabel="Upload site photo"
              emptyCopy="No site photos have been uploaded yet."
              headerAction={
                canManageSites ? (
                  <button
                    className="ghost ghost-danger"
                    type="button"
                    disabled={activeSiteId === site.id}
                    onClick={() => void handleDeleteSite(site.id, site.name)}
                  >
                    {activeSiteId === site.id ? "Deleting..." : "Delete site"}
                  </button>
                ) : null
              }
              onUpload={(payload) => handleSiteImageUpload(site.id, payload)}
              onMarkPrimary={handleSitePrimary}
              onDelete={handleSiteDelete}
            />
          ))}
        </div>
        {!isLoading && (inventory?.sites?.length ?? 0) === 0 ? (
          <p className="empty-state">No sites are visible for the current account.</p>
        ) : null}
      </section>

      <section className="inventory-section">
        <div className="module-head">
          <h2>Media unit image library</h2>
          <span>{filteredUnits.length} of {inventory?.units?.length ?? 0} units</span>
        </div>
        {unitLibraryNotice ? <p className="info inventory-section-notice">{unitLibraryNotice}</p> : null}
        {unitMutationError && !canManageUnits ? <p className="error">{unitMutationError}</p> : null}
        {unitMutationSuccess && !canManageUnits ? <p className="success">{unitMutationSuccess}</p> : null}
        <section className="module-card inventory-filter-panel">
          <div className="module-head">
            <h2>Sales filters</h2>
            <span>Unit finder</span>
          </div>
          <div className="inventory-filter-grid">
            <div className="field">
              <label htmlFor="filter-city">City</label>
              <select
                id="filter-city"
                value={unitFilters.city}
                onChange={(event) => updateUnitFilter("city", event.target.value)}
              >
                <option value="">All cities</option>
                {filterCities.map((city) => (
                  <option key={city} value={city}>
                    {city}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="filter-status">Status</label>
              <select
                id="filter-status"
                value={unitFilters.status}
                onChange={(event) => updateUnitFilter("status", event.target.value)}
              >
                <option value="">All statuses</option>
                {filterStatuses.map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="filter-direction">Facing direction</label>
              <input
                id="filter-direction"
                value={unitFilters.facing_direction}
                onChange={(event) => updateUnitFilter("facing_direction", event.target.value)}
                placeholder="Example: Toward Jammu City"
              />
            </div>
            <div className="field">
              <label htmlFor="filter-site-type">Media unit site type</label>
              <select
                id="filter-site-type"
                value={unitFilters.site_type}
                onChange={(event) => updateUnitFilter("site_type", event.target.value)}
              >
                <option value="">All types</option>
                {MEDIA_UNIT_SITE_TYPE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-actions field-full">
              <button className="ghost" type="button" onClick={() => setUnitFilters(INITIAL_UNIT_FILTERS)}>
                Clear filters
              </button>
            </div>
          </div>
        </section>
        <div className="image-manager-grid">
          {filteredUnits.map((unit) => (
            <ImageManagerCard
              key={unit.id}
              formIdPrefix={`unit-image-${unit.id}`}
              title={unit.unit_code}
              eyebrow={siteMap.get(unit.site)?.label ?? `Site #${unit.site}`}
              description={`${unit.width} x ${unit.height} • ${unit.face_count} face(s)${unit.facing_direction ? ` • ${unit.facing_direction}` : ""}`}
              meta={`${formatMediaUnitSiteType(unit.site_type)} • ${unit.is_illuminated ? "Illuminated" : "Standard"} • ${unit.status} • INR ${Number(unit.monthly_rate).toLocaleString("en-IN")}${siteMap.get(unit.site)?.city ? ` • ${siteMap.get(unit.site)?.city}` : ""}`}
              badges={[
                { label: unit.status.replaceAll("_", " "), tone: unit.status },
                { label: unit.facing_direction || "Direction pending" },
                { label: formatMediaUnitSiteType(unit.site_type) },
              ]}
              images={unit.image_gallery ?? []}
              primaryImage={unit.primary_image ?? null}
              showHeroPreview={false}
              canManage={canManageImages}
              uploadLabel="Upload media unit photo"
              emptyCopy="No media unit photos have been uploaded yet."
              headerAction={
                canManageUnits ? (
                  <button
                    className="ghost"
                    type="button"
                    disabled={isUnitSubmitting}
                    onClick={() => handleEditUnit(unit.id)}
                  >
                    Edit unit
                  </button>
                ) : null
              }
              onUpload={(payload) => handleUnitImageUpload(unit.id, payload)}
              onMarkPrimary={handleUnitPrimary}
              onDelete={handleUnitDelete}
            />
          ))}
        </div>
        {!isLoading && (inventory?.units?.length ?? 0) === 0 ? (
          <p className="empty-state">No media units are visible for the current account.</p>
        ) : null}
        {!isLoading && (inventory?.units?.length ?? 0) > 0 && filteredUnits.length === 0 ? (
          <p className="empty-state">No media units match the current filters.</p>
        ) : null}
      </section>
    </AppShell>
  );
}
