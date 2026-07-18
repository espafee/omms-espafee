"use client";

import {
  Suspense,
  type ChangeEvent,
  type FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { ImageManagerCard } from "@/components/image-manager-card";
import { InventoryImageViewer } from "@/components/inventory-image-viewer";
import { SafeImage } from "@/components/safe-image";
import {
  clearAuthSession,
  fetchCurrentUser,
  getAccessToken,
  getStoredUser,
} from "@/lib/auth";
import {
  deleteMediaUnitImage,
  getMediaUnitImageMutationError,
  updateMediaUnitImage,
  uploadMediaUnitImage,
} from "@/lib/media-unit-images";
import {
  createMediaUnit,
  createSite,
  deleteSite,
  fetchInventoryData,
  fetchInventorySite,
  fetchInventorySiteList,
  fetchInventoryUnit,
  fetchInventoryUnitList,
  formatMediaUnitSiteType,
  getInventorySiteMutationError,
  getInventoryUnitMutationError,
  type InventoryPayload,
  type InventorySite,
  type InventorySiteCreateInput,
  type InventorySiteListFilters,
  type InventoryUnit,
  type InventoryUnitListFilters,
  type InventoryUnitMutationInput,
  MEDIA_UNIT_SITE_TYPE_OPTIONS,
  updateMediaUnit,
  updateMediaUnitPublication,
  updateSite,
} from "@/lib/inventory";
import {
  deleteSiteImage,
  getSiteImageMutationError,
  updateSiteImage,
  uploadSiteImage,
} from "@/lib/site-images";

type StoredUser = { email?: string; role?: string };
type InventoryView = "overview" | "locations" | "units";
type AddMode = "choose" | "new-location" | "existing-location";
type DetailTarget =
  | { kind: "location"; item: InventorySite }
  | { kind: "unit"; item: InventoryUnit };
type PendingUnitImage = {
  id: string;
  file: File;
  previewUrl: string;
  caption: string;
};

const WRITE_ROLES = new Set(["admin", "operations", "inventory_manager"]);
const ADMIN_ROLES = new Set(["admin"]);
const PAGE_SIZE = 12;

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
  is_publicly_listed: false,
  public_description: "",
  public_features: [],
};
const INITIAL_LOCATION_FILTERS: InventorySiteListFilters = {
  search: "",
  city: "",
  media_type: "",
  photo_status: undefined,
  coordinate_status: undefined,
  page: 1,
  page_size: PAGE_SIZE,
};
const INITIAL_UNIT_FILTERS: InventoryUnitListFilters = {
  search: "",
  city: "",
  status: "",
  site_type: "",
  facing_direction: "",
  size: "",
  page: 1,
  page_size: PAGE_SIZE,
};

function formatChoice(value: string | null | undefined) {
  return value ? value.replaceAll("_", " ") : "Pending";
}

function formatMoney(value: string) {
  return `INR ${Number(value || 0).toLocaleString("en-IN")}`;
}

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Date unavailable"
    : date.toLocaleDateString("en-IN", {
        day: "2-digit",
        month: "short",
        year: "numeric",
      });
}

function getInitialView(value: string | null): InventoryView {
  return value === "overview" || value === "locations" || value === "units"
    ? value
    : "units";
}

function isInventoryView(value: string | null): value is InventoryView {
  return value === "overview" || value === "locations" || value === "units";
}

export default function InventoryPage() {
  return (
    <Suspense
      fallback={
        <main className="page-shell">
          <p className="empty-state">Loading inventory workspace...</p>
        </main>
      }
    >
      <InventoryWorkspace />
    </Suspense>
  );
}

function InventoryWorkspace() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [user, setUser] = useState<StoredUser | null>(null);
  const [view, setView] = useState<InventoryView>(() =>
    getInitialView(searchParams.get("view")),
  );
  const [locations, setLocations] = useState<Awaited<
    ReturnType<typeof fetchInventorySiteList>
  > | null>(null);
  const [units, setUnits] = useState<Awaited<
    ReturnType<typeof fetchInventoryUnitList>
  > | null>(null);
  const [directory, setDirectory] = useState<InventoryPayload | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLocationLoading, setIsLocationLoading] = useState(true);
  const [isUnitLoading, setIsUnitLoading] = useState(true);
  const [error, setError] = useState("");
  const [locationFilters, setLocationFilters] =
    useState<InventorySiteListFilters>(INITIAL_LOCATION_FILTERS);
  const [unitFilters, setUnitFilters] =
    useState<InventoryUnitListFilters>(INITIAL_UNIT_FILTERS);
  const [addMode, setAddMode] = useState<AddMode>("choose");
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [siteForm, setSiteForm] =
    useState<InventorySiteCreateInput>(INITIAL_SITE_FORM);
  const [unitForm, setUnitForm] =
    useState<InventoryUnitMutationInput>(INITIAL_UNIT_FORM);
  const [editingSiteId, setEditingSiteId] = useState<number | null>(null);
  const [editingUnitId, setEditingUnitId] = useState<number | null>(null);
  const [siteFieldErrors, setSiteFieldErrors] = useState<
    Record<string, string[]>
  >({});
  const [unitFieldErrors, setUnitFieldErrors] = useState<
    Record<string, string[]>
  >({});
  const [siteError, setSiteError] = useState("");
  const [unitError, setUnitError] = useState("");
  const [siteSuccess, setSiteSuccess] = useState("");
  const [unitSuccess, setUnitSuccess] = useState("");
  const [isSiteSubmitting, setIsSiteSubmitting] = useState(false);
  const [isUnitSubmitting, setIsUnitSubmitting] = useState(false);
  const [pendingLocationPhoto, setPendingLocationPhoto] = useState<File | null>(
    null,
  );
  const [pendingUnitImages, setPendingUnitImages] = useState<
    PendingUnitImage[]
  >([]);
  const [primaryPendingUnitImageId, setPrimaryPendingUnitImageId] = useState<
    string | null
  >(null);
  const [detailTarget, setDetailTarget] = useState<DetailTarget | null>(null);
  const [photoTarget, setPhotoTarget] = useState<DetailTarget | null>(null);
  const [viewerUnit, setViewerUnit] = useState<InventoryUnit | null>(null);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [activeSiteId, setActiveSiteId] = useState<number | null>(null);
  const [selectedUnitIds, setSelectedUnitIds] = useState<number[]>([]);
  const [isPublicationUpdating, setIsPublicationUpdating] = useState(false);

  const canManageImages = WRITE_ROLES.has(user?.role ?? "");
  const canManageSites = ADMIN_ROLES.has(user?.role ?? "");
  const canManageUnits = WRITE_ROLES.has(user?.role ?? "");
  const hasInventoryOverlay =
    isAddOpen || Boolean(detailTarget) || Boolean(photoTarget);

  const loadLocations = useCallback(
    async (filters: InventorySiteListFilters) => {
      setIsLocationLoading(true);
      try {
        setLocations(await fetchInventorySiteList(filters));
      } catch (loadError) {
        setError(
          loadError instanceof Error
            ? loadError.message
            : "Unable to load locations.",
        );
      } finally {
        setIsLocationLoading(false);
      }
    },
    [],
  );

  const loadUnits = useCallback(async (filters: InventoryUnitListFilters) => {
    setIsUnitLoading(true);
    try {
      setUnits(await fetchInventoryUnitList(filters));
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Unable to load advertising units.",
      );
    } finally {
      setIsUnitLoading(false);
    }
  }, []);

  const loadDirectory = useCallback(async () => {
    if (directory) return directory;
    const payload = await fetchInventoryData();
    setDirectory(payload);
    return payload;
  }, [directory]);

  const refreshWorkspace = useCallback(async () => {
    await Promise.all([loadLocations(locationFilters), loadUnits(unitFilters)]);
  }, [loadLocations, loadUnits, locationFilters, unitFilters]);

  useEffect(() => {
    if (!getAccessToken()) {
      router.replace("/login");
      return;
    }
    const storedUser = getStoredUser();
    if (storedUser) setUser(storedUser);
    void fetchCurrentUser()
      .then(setUser)
      .catch(() => undefined);
    setIsLoading(false);
  }, [router]);

  useEffect(() => {
    void loadLocations(locationFilters);
  }, [loadLocations, locationFilters]);
  useEffect(() => {
    void loadUnits(unitFilters);
  }, [loadUnits, unitFilters]);
  useEffect(() => {
    const requestedView = searchParams.get("view");
    if (!isInventoryView(requestedView)) {
      router.replace("/inventory?view=units");
      return;
    }
    setView(requestedView);
  }, [router, searchParams]);
  useEffect(
    () => () =>
      pendingUnitImages.forEach((image) =>
        URL.revokeObjectURL(image.previewUrl),
      ),
    [pendingUnitImages],
  );
  useEffect(() => {
    if (!hasInventoryOverlay) return undefined;
    document.body.classList.add("modal-open");
    return () => document.body.classList.remove("modal-open");
  }, [hasInventoryOverlay]);

  const locationCities = useMemo(
    () =>
      Array.from(
        new Set(
          (locations?.results ?? []).map((item) => item.city).filter(Boolean),
        ),
      ).sort(),
    [locations],
  );
  const unitCities = useMemo(
    () =>
      Array.from(
        new Set(
          (units?.results ?? []).map((item) => item.city).filter(Boolean),
        ),
      ).sort(),
    [units],
  );
  const locationTypes = useMemo(
    () =>
      Array.from(
        new Set(
          (locations?.results ?? [])
            .map((item) => item.media_type)
            .filter(Boolean),
        ),
      ).sort(),
    [locations],
  );
  const facingDirections = useMemo(
    () =>
      Array.from(
        new Set(
          (units?.results ?? [])
            .map((item) => item.facing_direction)
            .filter(Boolean),
        ),
      ).sort(),
    [units],
  );
  const unitSizes = useMemo(
    () =>
      Array.from(
        new Set(
          (units?.results ?? []).map((item) => `${item.width}x${item.height}`),
        ),
      ).sort(),
    [units],
  );
  const overview = useMemo(() => {
    const locationRows = locations?.results ?? [];
    const unitRows = units?.results ?? [];
    return {
      locations: locations?.count ?? 0,
      units: units?.count ?? 0,
      available: unitRows.filter((item) => item.status === "available").length,
      booked: unitRows.filter((item) => item.status === "reserved").length,
      unavailable: unitRows.filter((item) =>
        ["maintenance", "retired"].includes(item.status),
      ).length,
      missingLocationPhotos: locationRows.filter(
        (item) => item.image_count === 0,
      ).length,
      missingCoordinates: locationRows.filter((item) => !item.has_coordinates)
        .length,
    };
  }, [locations, units]);

  function selectView(next: InventoryView) {
    setView(next);
    router.replace(`/inventory?view=${next}`);
  }

  function handleLogout() {
    clearAuthSession();
    router.replace("/login");
  }

  function openAdd(mode: AddMode = "choose") {
    setIsAddOpen(true);
    setAddMode(mode);
    setSiteError("");
    setUnitError("");
    setSiteSuccess("");
    setUnitSuccess("");
    void loadDirectory().catch((loadError) =>
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Unable to prepare inventory form.",
      ),
    );
  }

  function closeAdd() {
    setIsAddOpen(false);
    setAddMode("choose");
    setEditingSiteId(null);
    setEditingUnitId(null);
    setSiteForm(INITIAL_SITE_FORM);
    setUnitForm(INITIAL_UNIT_FORM);
    setPendingLocationPhoto(null);
    pendingUnitImages.forEach((image) => URL.revokeObjectURL(image.previewUrl));
    setPendingUnitImages([]);
    setPrimaryPendingUnitImageId(null);
    setSiteFieldErrors({});
    setUnitFieldErrors({});
  }

  function updateSiteForm<K extends keyof InventorySiteCreateInput>(
    field: K,
    value: InventorySiteCreateInput[K],
  ) {
    setSiteFieldErrors({});
    setSiteError("");
    setSiteForm((current) => ({ ...current, [field]: value }));
  }

  function updateUnitForm<K extends keyof InventoryUnitMutationInput>(
    field: K,
    value: InventoryUnitMutationInput[K],
  ) {
    setUnitFieldErrors({});
    setUnitError("");
    setUnitForm((current) => ({ ...current, [field]: value }));
  }

  async function handleSubmitSite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isSiteSubmitting) return;
    setIsSiteSubmitting(true);
    setSiteError("");
    setSiteSuccess("");
    setSiteFieldErrors({});
    try {
      const payload = {
        ...siteForm,
        latitude: siteForm.latitude || null,
        longitude: siteForm.longitude || null,
      };
      const saved = editingSiteId
        ? await updateSite(editingSiteId, payload)
        : await createSite(payload);
      if (pendingLocationPhoto) {
        await uploadSiteImage({
          site: saved.id,
          image: pendingLocationPhoto,
          caption: "Location overview",
          is_primary: true,
        });
      }
      setDirectory((current) =>
        current
          ? {
              ...current,
              sites: [
                ...current.sites.filter((site) => site.id !== saved.id),
                saved,
              ],
            }
          : current,
      );
      await loadLocations(locationFilters);
      setSiteSuccess(
        editingSiteId
          ? "Location updated successfully."
          : "Location created. Continue with its advertising unit.",
      );
      if (!editingSiteId) {
        setUnitForm((current) => ({
          ...current,
          site: saved.id,
          unit_code: `${saved.code}-A`,
        }));
        setAddMode("existing-location");
      }
    } catch (mutationError) {
      const normalized = getInventorySiteMutationError(mutationError);
      setSiteError(normalized.message);
      setSiteFieldErrors(normalized.fieldErrors);
    } finally {
      setIsSiteSubmitting(false);
    }
  }

  function handlePendingUnitImagesChange(event: ChangeEvent<HTMLInputElement>) {
    pendingUnitImages.forEach((image) => URL.revokeObjectURL(image.previewUrl));
    const next = Array.from(event.target.files ?? []).map((file, index) => ({
      id: `${file.name}-${file.size}-${index}`,
      file,
      previewUrl: URL.createObjectURL(file),
      caption: file.name.replace(/\.[^.]+$/, ""),
    }));
    setPendingUnitImages(next);
    setPrimaryPendingUnitImageId(next[0]?.id ?? null);
  }

  async function uploadPendingImagesForUnit(unitId: number) {
    const primaryId = primaryPendingUnitImageId ?? pendingUnitImages[0]?.id;
    for (const image of pendingUnitImages) {
      await uploadMediaUnitImage({
        media_unit: unitId,
        image: image.file,
        caption: image.caption.trim(),
        is_primary: image.id === primaryId,
      });
    }
    return pendingUnitImages.length;
  }

  async function handleSubmitUnit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isUnitSubmitting) return;
    setIsUnitSubmitting(true);
    setUnitError("");
    setUnitSuccess("");
    setUnitFieldErrors({});
    try {
      const payload = {
        ...unitForm,
        facing_direction: unitForm.facing_direction || "",
        site_type: unitForm.site_type || "single_side",
        monthly_rate: Number(unitForm.monthly_rate).toFixed(2),
      };
      const saved = editingUnitId
        ? await updateMediaUnit(editingUnitId, payload)
        : await createMediaUnit(payload);
      const uploaded = await uploadPendingImagesForUnit(saved.id);
      await loadUnits(unitFilters);
      setDirectory(null);
      setUnitSuccess(
        editingUnitId
          ? "Advertising unit updated successfully."
          : `Advertising unit created${uploaded ? ` with ${uploaded} photo(s)` : ""}.`,
      );
      if (!editingUnitId) {
        setUnitForm((current) => ({
          ...INITIAL_UNIT_FORM,
          site: current.site,
          unit_code: "",
        }));
        setPendingUnitImages([]);
        setPrimaryPendingUnitImageId(null);
      }
    } catch (mutationError) {
      const normalized = getInventoryUnitMutationError(mutationError);
      setUnitError(normalized.message);
      setUnitFieldErrors(normalized.fieldErrors);
    } finally {
      setIsUnitSubmitting(false);
    }
  }

  async function openLocation(id: number, photos = false) {
    setIsDetailLoading(true);
    try {
      const item = await fetchInventorySite(id);
      const target: DetailTarget = { kind: "location", item };
      if (photos) setPhotoTarget(target);
      else setDetailTarget(target);
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Unable to load location details.",
      );
    } finally {
      setIsDetailLoading(false);
    }
  }

  async function openUnit(id: number, photos = false) {
    setIsDetailLoading(true);
    try {
      const item = await fetchInventoryUnit(id);
      const target: DetailTarget = { kind: "unit", item };
      if (photos) setPhotoTarget(target);
      else setDetailTarget(target);
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Unable to load advertising unit details.",
      );
    } finally {
      setIsDetailLoading(false);
    }
  }

  async function openUnitViewer(id: number) {
    setIsDetailLoading(true);
    try {
      setViewerUnit(await fetchInventoryUnit(id));
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Unable to load advertising unit photos.",
      );
    } finally {
      setIsDetailLoading(false);
    }
  }

  async function openLocationEditor(id: number) {
    try {
      editLocation(await fetchInventorySite(id));
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Unable to load location details.",
      );
    }
  }

  async function openUnitEditor(id: number) {
    try {
      editUnit(await fetchInventoryUnit(id));
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Unable to load advertising unit details.",
      );
    }
  }

  function editLocation(site: InventorySite) {
    setEditingSiteId(site.id);
    setSiteForm({
      name: site.name,
      code: site.code,
      site_type: site.site_type,
      address: site.address,
      city: site.city,
      state: site.state,
      latitude: site.latitude,
      longitude: site.longitude,
    });
    setIsAddOpen(true);
    setAddMode("new-location");
    setDetailTarget(null);
  }

  function editUnit(unit: InventoryUnit) {
    setEditingUnitId(unit.id);
    setUnitForm({
      site: unit.site,
      unit_code: unit.unit_code,
      face_count: unit.face_count,
      width: unit.width,
      height: unit.height,
      status: unit.status,
      is_illuminated: unit.is_illuminated,
      monthly_rate: unit.monthly_rate,
      facing_direction: unit.facing_direction,
      site_type: unit.site_type,
      is_publicly_listed: unit.is_publicly_listed,
      public_description: unit.public_description,
      public_features: unit.public_features,
    });
    setIsAddOpen(true);
    setAddMode("existing-location");
    setDetailTarget(null);
    void loadDirectory();
  }

  async function handleDeleteLocation(site: InventorySite) {
    if (
      activeSiteId ||
      !window.confirm(`Delete ${site.name}? Active bookings remain protected.`)
    )
      return;
    setActiveSiteId(site.id);
    setError("");
    try {
      await deleteSite(site.id);
      await refreshWorkspace();
      setDetailTarget(null);
    } catch (deleteError) {
      setError(getInventorySiteMutationError(deleteError).message);
    } finally {
      setActiveSiteId(null);
    }
  }

  async function handleSitePhotoUpload(
    siteId: number,
    payload: { file: File; caption: string; isPrimary: boolean },
  ) {
    try {
      await uploadSiteImage({
        site: siteId,
        image: payload.file,
        caption: payload.caption,
        is_primary: payload.isPrimary,
      });
      await loadLocations(locationFilters);
      const item = await fetchInventorySite(siteId);
      setPhotoTarget({ kind: "location", item });
    } catch (uploadError) {
      throw new Error(getSiteImageMutationError(uploadError).message);
    }
  }
  async function handleUnitPhotoUpload(
    unitId: number,
    payload: { file: File; caption: string; isPrimary: boolean },
  ) {
    try {
      await uploadMediaUnitImage({
        media_unit: unitId,
        image: payload.file,
        caption: payload.caption,
        is_primary: payload.isPrimary,
      });
      await loadUnits(unitFilters);
      const item = await fetchInventoryUnit(unitId);
      setPhotoTarget({ kind: "unit", item });
    } catch (uploadError) {
      throw new Error(getMediaUnitImageMutationError(uploadError).message);
    }
  }
  async function handleSitePrimary(imageId: number) {
    try {
      await updateSiteImage(imageId, { is_primary: true });
      if (photoTarget?.kind === "location")
        setPhotoTarget({
          kind: "location",
          item: await fetchInventorySite(photoTarget.item.id),
        });
      await loadLocations(locationFilters);
    } catch (mutationError) {
      throw new Error(getSiteImageMutationError(mutationError).message);
    }
  }
  async function handleUnitPrimary(imageId: number) {
    try {
      await updateMediaUnitImage(imageId, { is_primary: true });
      if (photoTarget?.kind === "unit")
        setPhotoTarget({
          kind: "unit",
          item: await fetchInventoryUnit(photoTarget.item.id),
        });
      await loadUnits(unitFilters);
    } catch (mutationError) {
      throw new Error(getMediaUnitImageMutationError(mutationError).message);
    }
  }
  async function handleSiteImageDelete(imageId: number) {
    try {
      await deleteSiteImage(imageId);
      if (photoTarget?.kind === "location")
        setPhotoTarget({
          kind: "location",
          item: await fetchInventorySite(photoTarget.item.id),
        });
      await loadLocations(locationFilters);
    } catch (mutationError) {
      throw new Error(getSiteImageMutationError(mutationError).message);
    }
  }
  async function handleUnitImageDelete(imageId: number) {
    try {
      await deleteMediaUnitImage(imageId);
      if (photoTarget?.kind === "unit")
        setPhotoTarget({
          kind: "unit",
          item: await fetchInventoryUnit(photoTarget.item.id),
        });
      await loadUnits(unitFilters);
    } catch (mutationError) {
      throw new Error(getMediaUnitImageMutationError(mutationError).message);
    }
  }

  async function updatePublication(unitIds: number[], isPubliclyListed: boolean) {
    if (!unitIds.length || isPublicationUpdating) return;
    setIsPublicationUpdating(true);
    setUnitError("");
    setUnitSuccess("");
    try {
      const result = await updateMediaUnitPublication(unitIds, isPubliclyListed);
      await loadUnits(unitFilters);
      setSelectedUnitIds([]);
      setUnitSuccess(
        `${result.updated_count} advertising unit${result.updated_count === 1 ? "" : "s"} ${
          isPubliclyListed ? "published to" : "removed from"
        } the Live Media Planner.`,
      );
    } catch (mutationError) {
      setUnitError(getInventoryUnitMutationError(mutationError).message);
    } finally {
      setIsPublicationUpdating(false);
    }
  }

  const locationPageCount = Math.max(
    1,
    Math.ceil((locations?.count ?? 0) / PAGE_SIZE),
  );
  const unitPageCount = Math.max(1, Math.ceil((units?.count ?? 0) / PAGE_SIZE));
  const locationRows = locations?.results ?? [];
  const unitRows = units?.results ?? [];
  const visibleUnitIds = unitRows.map((unit) => unit.id);
  const allVisibleUnitsSelected =
    visibleUnitIds.length > 0 &&
    visibleUnitIds.every((id) => selectedUnitIds.includes(id));

  return (
    <AppShell
      active="inventory"
      roleLabel={user?.role ?? "Team member"}
      userEmail={user?.email ?? ""}
      onLogout={handleLogout}
      title="Inventory workspace"
      description="Organize physical locations and the sellable advertising units they contain."
    >
      <section className="inventory-workspace-head">
        <div>
          <p className="site-code">
            LOCATION → ADVERTISING UNIT → BOOKINGS / CAMPAIGNS / POE
          </p>
          <p className="section-copy">
            Locations describe the physical place. Advertising Units are the
            sellable faces, directions, screens, or displays at that location.
          </p>
        </div>
        {canManageUnits || canManageSites ? (
          <button className="submit" type="button" onClick={() => openAdd()}>
            + Add Inventory
          </button>
        ) : null}
      </section>

      <nav className="inventory-tabs" aria-label="Inventory views">
        {(["overview", "locations", "units"] as InventoryView[]).map((tab) => (
          <button
            key={tab}
            type="button"
            className={view === tab ? "inventory-tab-active" : ""}
            aria-current={view === tab ? "page" : undefined}
            onClick={() => selectView(tab)}
          >
            {tab === "units"
              ? "Advertising Units"
              : tab[0].toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </nav>
      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}

      {view === "overview" ? (
        <section className="inventory-overview" aria-label="Inventory overview">
          <div className="inventory-summary-grid">
            {[
              ["Total Locations", overview.locations],
              ["Advertising Units", overview.units],
              ["Available Units", overview.available],
              ["Booked Units", overview.booked],
              ["Maintenance / Retired", overview.unavailable],
              ["Locations without photos", overview.missingLocationPhotos],
              ["Locations without coordinates", overview.missingCoordinates],
            ].map(([label, value]) => (
              <article className="summary-card" key={String(label)}>
                <span>{label}</span>
                <strong>{isLoading ? "..." : value}</strong>
              </article>
            ))}
          </div>
          <section className="module-card inventory-attention">
            <div className="module-head">
              <h2>Units needing attention</h2>
              <span>Operational follow-up</span>
            </div>
            {unitRows
              .filter((item) => item.status !== "available")
              .slice(0, 5)
              .map((unit) => (
                <button
                  className="inventory-attention-row"
                  type="button"
                  key={unit.id}
                  onClick={() => void openUnit(unit.id)}
                >
                  <span>
                    <strong>{unit.unit_code}</strong>
                    <small>
                      {unit.location_code} · {unit.location_name}
                    </small>
                  </span>
                  <span className={`status-pill status-${unit.status}`}>
                    {formatChoice(unit.status)}
                  </span>
                </button>
              ))}
            {unitRows.every((item) => item.status === "available") ? (
              <p className="empty-state">
                No units on this page need an operational follow-up.
              </p>
            ) : null}
          </section>
        </section>
      ) : null}

      {view === "locations" ? (
        <section
          className="inventory-list-section"
          aria-labelledby="locations-heading"
        >
          <div className="module-head">
            <div>
              <h2 id="locations-heading">Locations</h2>
              <p className="section-copy">
                A physical advertising structure or geographic place that may
                contain one or more sellable advertising units.
              </p>
            </div>
            <span>{locations?.count ?? 0} locations</span>
          </div>
          <section className="module-card inventory-filter-panel">
            <div className="inventory-filter-grid inventory-location-filter-grid">
              <label className="field">
                <span>Search</span>
                <input
                  value={locationFilters.search}
                  onChange={(event) =>
                    setLocationFilters((current) => ({
                      ...current,
                      search: event.target.value,
                      page: 1,
                    }))
                  }
                  placeholder="Name, code, city, or address"
                />
              </label>
              <label className="field">
                <span>City</span>
                <select
                  value={locationFilters.city}
                  onChange={(event) =>
                    setLocationFilters((current) => ({
                      ...current,
                      city: event.target.value,
                      page: 1,
                    }))
                  }
                >
                  <option value="">All cities</option>
                  {locationCities.map((city) => (
                    <option key={city}>{city}</option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Structure category</span>
                <select
                  value={locationFilters.media_type}
                  onChange={(event) =>
                    setLocationFilters((current) => ({
                      ...current,
                      media_type: event.target.value,
                      page: 1,
                    }))
                  }
                >
                  <option value="">All categories</option>
                  {locationTypes.map((type) => (
                    <option key={type} value={type}>
                      {formatChoice(type)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Photo status</span>
                <select
                  value={locationFilters.photo_status ?? ""}
                  onChange={(event) =>
                    setLocationFilters((current) => ({
                      ...current,
                      photo_status: event.target
                        .value as InventorySiteListFilters["photo_status"],
                      page: 1,
                    }))
                  }
                >
                  <option value="">Any photo status</option>
                  <option value="with_photos">Has photos</option>
                  <option value="missing_photos">Missing photos</option>
                </select>
              </label>
              <label className="field">
                <span>Coordinates</span>
                <select
                  value={locationFilters.coordinate_status ?? ""}
                  onChange={(event) =>
                    setLocationFilters((current) => ({
                      ...current,
                      coordinate_status: event.target
                        .value as InventorySiteListFilters["coordinate_status"],
                      page: 1,
                    }))
                  }
                >
                  <option value="">Any coordinate status</option>
                  <option value="coordinates_set">Coordinates set</option>
                  <option value="coordinates_missing">
                    Coordinates missing
                  </option>
                </select>
              </label>
              <div className="form-actions">
                <button
                  className="ghost"
                  type="button"
                  onClick={() => setLocationFilters(INITIAL_LOCATION_FILTERS)}
                >
                  Clear
                </button>
              </div>
            </div>
          </section>
          {isLocationLoading ? (
            <p className="empty-state">Loading locations...</p>
          ) : null}
          {!isLocationLoading && locationRows.length === 0 ? (
            <p className="empty-state">
              No locations match the selected filters.
            </p>
          ) : null}
          {locationRows.length ? (
            <div className="inventory-table-wrap all-sites-table-wrap">
              <table className="inventory-table all-sites-table inventory-workspace-table">
                <thead>
                  <tr>
                    <th>Photo</th>
                    <th>Location</th>
                    <th>City / Address</th>
                    <th>Category</th>
                    <th>Advertising units</th>
                    <th>Photos / Coordinates</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {locationRows.map((location) => (
                    <tr key={location.id}>
                      <td>
                        <SafeImage
                          src={location.thumbnail_url}
                          alt={`${location.title} thumbnail`}
                          className="all-sites-thumb"
                          fallback={
                            <div className="all-sites-thumb all-sites-thumb-empty">
                              No photo
                            </div>
                          }
                        />
                      </td>
                      <td>
                        <div className="table-primary">
                          <span>LOCATION</span>
                          <strong>{location.title}</strong>
                          <span>{location.site_code}</span>
                        </div>
                      </td>
                      <td>
                        <div className="table-primary">
                          <strong>{location.city}</strong>
                          <span>{location.address}</span>
                        </div>
                      </td>
                      <td>{formatChoice(location.media_type)}</td>
                      <td>
                        {location.available_unit_count} of {location.unit_count}{" "}
                        available
                      </td>
                      <td>
                        <span className="site-code">
                          {location.image_count} photo(s) ·{" "}
                          {location.has_coordinates
                            ? "Coordinates set"
                            : "Coordinates missing"}
                        </span>
                      </td>
                      <td>
                        <div className="all-sites-actions">
                          <button
                            className="ghost table-action"
                            type="button"
                            onClick={() => void openLocation(location.id)}
                          >
                            View
                          </button>
                          {canManageSites ? (
                            <button
                              className="ghost table-action"
                              type="button"
                              onClick={() =>
                                void openLocationEditor(location.id)
                              }
                            >
                              Edit
                            </button>
                          ) : null}
                          <details className="inventory-more">
                            <summary>More</summary>
                            <div>
                              {canManageImages ? (
                                <button
                                  type="button"
                                  onClick={() =>
                                    void openLocation(location.id, true)
                                  }
                                >
                                  Manage photos
                                </button>
                              ) : null}
                              {canManageSites ? (
                                <button
                                  className="ghost-danger"
                                  type="button"
                                  onClick={() =>
                                    void handleDeleteLocation({
                                      id: location.id,
                                      name: location.title,
                                    } as InventorySite)
                                  }
                                >
                                  Delete location
                                </button>
                              ) : null}
                            </div>
                          </details>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
          <Pagination
            page={locationFilters.page ?? 1}
            pageCount={locationPageCount}
            loading={isLocationLoading}
            onChange={(page) =>
              setLocationFilters((current) => ({ ...current, page }))
            }
          />
        </section>
      ) : null}

      {view === "units" ? (
        <section
          className="inventory-list-section"
          aria-labelledby="units-heading"
        >
          <div className="module-head">
            <div>
              <h2 id="units-heading">Advertising Units</h2>
              <p className="section-copy">
                A sellable advertising face, direction, screen, or display at a
                location.
              </p>
            </div>
            <span>{units?.count ?? 0} units</span>
          </div>
          <section className="module-card inventory-filter-panel">
            <div className="inventory-filter-grid inventory-unit-filter-grid">
              <label className="field">
                <span>Search</span>
                <input
                  value={unitFilters.search}
                  onChange={(event) =>
                    setUnitFilters((current) => ({
                      ...current,
                      search: event.target.value,
                      page: 1,
                    }))
                  }
                  placeholder="Unit, location, address, city, direction"
                />
              </label>
              <label className="field">
                <span>City</span>
                <select
                  value={unitFilters.city}
                  onChange={(event) =>
                    setUnitFilters((current) => ({
                      ...current,
                      city: event.target.value,
                      page: 1,
                    }))
                  }
                >
                  <option value="">All cities</option>
                  {unitCities.map((city) => (
                    <option key={city}>{city}</option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Availability</span>
                <select
                  value={unitFilters.status}
                  onChange={(event) =>
                    setUnitFilters((current) => ({
                      ...current,
                      status: event.target.value,
                      page: 1,
                    }))
                  }
                >
                  <option value="">All statuses</option>
                  {["available", "reserved", "maintenance", "retired"].map(
                    (status) => (
                      <option key={status} value={status}>
                        {formatChoice(status)}
                      </option>
                    ),
                  )}
                </select>
              </label>
              <label className="field">
                <span>Display format</span>
                <select
                  value={unitFilters.site_type}
                  onChange={(event) =>
                    setUnitFilters((current) => ({
                      ...current,
                      site_type: event.target.value,
                      page: 1,
                    }))
                  }
                >
                  <option value="">All formats</option>
                  {MEDIA_UNIT_SITE_TYPE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Facing direction</span>
                <select
                  value={unitFilters.facing_direction}
                  onChange={(event) =>
                    setUnitFilters((current) => ({
                      ...current,
                      facing_direction: event.target.value,
                      page: 1,
                    }))
                  }
                >
                  <option value="">All directions</option>
                  {facingDirections.map((direction) => (
                    <option key={direction}>{direction}</option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Illumination</span>
                <select
                  value={
                    unitFilters.is_illuminated === undefined
                      ? ""
                      : String(unitFilters.is_illuminated)
                  }
                  onChange={(event) =>
                    setUnitFilters((current) => ({
                      ...current,
                      is_illuminated:
                        event.target.value === ""
                          ? undefined
                          : event.target.value === "true",
                      page: 1,
                    }))
                  }
                >
                  <option value="">Any illumination</option>
                  <option value="true">Illuminated</option>
                  <option value="false">Standard</option>
                </select>
              </label>
              <label className="field">
                <span>Size</span>
                <select
                  value={unitFilters.size ?? ""}
                  onChange={(event) =>
                    setUnitFilters((current) => ({
                      ...current,
                      size: event.target.value,
                      page: 1,
                    }))
                  }
                >
                  <option value="">All sizes</option>
                  {unitSizes.map((size) => (
                    <option key={size} value={size}>
                      {size.replace("x", " × ")}
                    </option>
                  ))}
                </select>
              </label>
              <div className="form-actions">
                <button
                  className="ghost"
                  type="button"
                  onClick={() => setUnitFilters(INITIAL_UNIT_FILTERS)}
                >
                  Clear
                </button>
              </div>
            </div>
          </section>
          {canManageUnits && unitRows.length ? (
            <div className="inventory-publication-bar" aria-live="polite">
              <div>
                <label className="inventory-select-all">
                  <input
                    type="checkbox"
                    checked={allVisibleUnitsSelected}
                    onChange={(event) =>
                      setSelectedUnitIds((current) =>
                        event.target.checked
                          ? [...new Set([...current, ...visibleUnitIds])]
                          : current.filter((id) => !visibleUnitIds.includes(id)),
                      )
                    }
                  />
                  <strong>{selectedUnitIds.length} selected</strong>
                </label>
                <span>
                  Publish controls decide what clients can see in the Live Media
                  Planner.
                </span>
              </div>
              <button
                className="ghost"
                type="button"
                disabled={!selectedUnitIds.length || isPublicationUpdating}
                onClick={() => void updatePublication(selectedUnitIds, true)}
              >
                Publish
              </button>
              <button
                className="ghost"
                type="button"
                disabled={!selectedUnitIds.length || isPublicationUpdating}
                onClick={() => void updatePublication(selectedUnitIds, false)}
              >
                Unpublish
              </button>
            </div>
          ) : null}
          {unitError ? <p className="error">{unitError}</p> : null}
          {unitSuccess ? <p className="success">{unitSuccess}</p> : null}
          {isUnitLoading ? (
            <p className="empty-state">Loading advertising units...</p>
          ) : null}
          {!isUnitLoading && unitRows.length === 0 ? (
            <p className="empty-state">
              No advertising units match the selected filters.
            </p>
          ) : null}
          {unitRows.length ? (
            <div className="inventory-table-wrap inventory-workspace-table-wrap">
              <table className="inventory-table inventory-workspace-table inventory-units-table">
                <thead>
                  <tr>
                    <th>Photo</th>
                    <th>Advertising Unit</th>
                    <th>Location</th>
                    <th>Facing</th>
                    <th>Dimensions</th>
                    <th>Format</th>
                    <th>Illumination</th>
                    <th>Rate</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {unitRows.map((unit) => (
                    <tr key={unit.id}>
                      <td>
                        <button
                          className="inventory-thumbnail-button"
                          type="button"
                          onClick={() => void openUnitViewer(unit.id)}
                          aria-label={`View photos for advertising unit ${unit.unit_code}`}
                          disabled={!unit.thumbnail_url}
                        >
                          <SafeImage
                            src={unit.thumbnail_url}
                            alt={`${unit.unit_code} advertising unit`}
                            className="all-sites-thumb"
                            fallback={
                              <div className="all-sites-thumb all-sites-thumb-empty">
                                No photo
                              </div>
                            }
                          />
                        </button>
                      </td>
                      <td>
                        <div className="table-primary">
                          {canManageUnits ? (
                            <label className="inventory-row-select">
                              <input
                                type="checkbox"
                                aria-label={`Select advertising unit ${unit.unit_code}`}
                                checked={selectedUnitIds.includes(unit.id)}
                                onChange={(event) =>
                                  setSelectedUnitIds((current) =>
                                    event.target.checked
                                      ? [...new Set([...current, unit.id])]
                                      : current.filter((id) => id !== unit.id),
                                  )
                                }
                              />
                              <span>Select</span>
                            </label>
                          ) : null}
                          <span>ADVERTISING UNIT</span>
                          <strong>{unit.unit_code}</strong>
                          <span>{unit.image_count} photo(s)</span>
                          <span
                            className={`planner-publication-status ${
                              unit.is_publicly_listed
                                ? "is-published"
                                : "is-unpublished"
                            }`}
                          >
                            {unit.is_publicly_listed
                              ? "Published to Media Planner"
                              : "Not published"}
                          </span>
                        </div>
                      </td>
                      <td>
                        <button
                          className="inventory-location-link"
                          type="button"
                          onClick={() => void openLocation(unit.location_id)}
                        >
                          <span>LOCATION</span>
                          <strong>{unit.location_name}</strong>
                          <small>
                            {unit.location_code} · {unit.city}
                          </small>
                        </button>
                      </td>
                      <td>{unit.facing_direction || "Pending"}</td>
                      <td>
                        {unit.width} × {unit.height}
                        <br />
                        <span className="site-code">
                          {unit.face_count} face(s)
                        </span>
                      </td>
                      <td>{formatMediaUnitSiteType(unit.site_type)}</td>
                      <td>
                        {unit.is_illuminated ? "Illuminated" : "Standard"}
                      </td>
                      <td>{formatMoney(unit.monthly_rate)}</td>
                      <td>
                        <span className={`status-pill status-${unit.status}`}>
                          {formatChoice(unit.status)}
                        </span>
                      </td>
                      <td>
                        <div className="all-sites-actions">
                          <button
                            className="ghost table-action"
                            type="button"
                            onClick={() => void openUnit(unit.id)}
                          >
                            View
                          </button>
                          {canManageUnits ? (
                            <button
                              className="ghost table-action"
                              type="button"
                              onClick={() => void openUnitEditor(unit.id)}
                            >
                              Edit
                            </button>
                          ) : null}
                          {canManageUnits ? (
                            <button
                              className="ghost table-action"
                              type="button"
                              disabled={isPublicationUpdating}
                              onClick={() =>
                                void updatePublication(
                                  [unit.id],
                                  !unit.is_publicly_listed,
                                )
                              }
                            >
                              {unit.is_publicly_listed
                                ? "Unpublish"
                                : "Publish"}
                            </button>
                          ) : null}
                          <details className="inventory-more">
                            <summary>More</summary>
                            <div>
                              {canManageImages ? (
                                <button
                                  type="button"
                                  onClick={() => void openUnit(unit.id, true)}
                                >
                                  Manage photos
                                </button>
                              ) : null}
                            </div>
                          </details>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
          <Pagination
            page={unitFilters.page ?? 1}
            pageCount={unitPageCount}
            loading={isUnitLoading}
            onChange={(page) =>
              setUnitFilters((current) => ({ ...current, page }))
            }
          />
        </section>
      ) : null}

      {isAddOpen ? (
        <div
          className="inventory-modal-backdrop"
          role="presentation"
          onMouseDown={(event) =>
            event.target === event.currentTarget && closeAdd()
          }
        >
          <section
            className="inventory-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="add-inventory-title"
          >
            <div className="module-head">
              <div>
                <p className="site-code">ADD INVENTORY</p>
                <h2 id="add-inventory-title">
                  {editingSiteId
                    ? "Edit Location"
                    : editingUnitId
                      ? "Edit Advertising Unit"
                      : "Add Inventory"}
                </h2>
              </div>
              <button className="ghost" type="button" onClick={closeAdd}>
                Close
              </button>
            </div>
            {addMode === "choose" ? (
              <div className="inventory-choice-grid">
                <button
                  type="button"
                  onClick={() => setAddMode("existing-location")}
                >
                  <strong>Add advertising units</strong>
                  <span>Use an existing location.</span>
                </button>
                {canManageSites ? (
                  <button
                    type="button"
                    onClick={() => setAddMode("new-location")}
                  >
                    <strong>Create a new location</strong>
                    <span>Then add its sellable unit.</span>
                  </button>
                ) : null}
              </div>
            ) : null}
            {addMode === "new-location" ? (
              <form className="site-form-grid" onSubmit={handleSubmitSite}>
                <p className="section-copy field-full">
                  Location: a physical advertising structure or geographic place
                  that may contain one or more sellable advertising units.
                </p>
                <label className="field">
                  <span>Location name</span>
                  <input
                    value={siteForm.name}
                    onChange={(event) =>
                      updateSiteForm("name", event.target.value)
                    }
                    required
                  />
                </label>
                <label className="field">
                  <span>Location code</span>
                  <input
                    value={siteForm.code}
                    onChange={(event) =>
                      updateSiteForm("code", event.target.value.toUpperCase())
                    }
                    required
                  />
                </label>
                <label className="field">
                  <span>Structure category</span>
                  <select
                    value={siteForm.site_type}
                    onChange={(event) =>
                      updateSiteForm("site_type", event.target.value)
                    }
                  >
                    {[
                      "billboard",
                      "transit",
                      "street_furniture",
                      "digital",
                    ].map((type) => (
                      <option key={type} value={type}>
                        {formatChoice(type)}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  <span>City</span>
                  <input
                    value={siteForm.city}
                    onChange={(event) =>
                      updateSiteForm("city", event.target.value)
                    }
                    required
                  />
                </label>
                <label className="field field-full">
                  <span>Address</span>
                  <input
                    value={siteForm.address}
                    onChange={(event) =>
                      updateSiteForm("address", event.target.value)
                    }
                    required
                  />
                </label>
                <label className="field">
                  <span>State</span>
                  <input
                    value={siteForm.state}
                    onChange={(event) =>
                      updateSiteForm("state", event.target.value)
                    }
                    required
                  />
                </label>
                <label className="field">
                  <span>Latitude</span>
                  <input
                    type="number"
                    step="0.000001"
                    value={siteForm.latitude ?? ""}
                    onChange={(event) =>
                      updateSiteForm("latitude", event.target.value)
                    }
                  />
                </label>
                <label className="field">
                  <span>Longitude</span>
                  <input
                    type="number"
                    step="0.000001"
                    value={siteForm.longitude ?? ""}
                    onChange={(event) =>
                      updateSiteForm("longitude", event.target.value)
                    }
                  />
                </label>
                <label className="field field-full">
                  <span>Optional location photo</span>
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    onChange={(event) =>
                      setPendingLocationPhoto(event.target.files?.[0] ?? null)
                    }
                  />
                  <small>
                    Show the physical structure, surroundings, and approach.
                  </small>
                </label>
                {siteError ? (
                  <p className="error field-full">{siteError}</p>
                ) : null}
                {siteSuccess ? (
                  <p className="success field-full">{siteSuccess}</p>
                ) : null}
                <div className="form-actions field-full">
                  <button
                    className="ghost"
                    type="button"
                    onClick={() => setAddMode("choose")}
                  >
                    Back
                  </button>
                  <button
                    className="submit"
                    type="submit"
                    disabled={isSiteSubmitting}
                  >
                    {isSiteSubmitting
                      ? "Saving..."
                      : editingSiteId
                        ? "Save Location"
                        : "Create Location"}
                  </button>
                </div>
              </form>
            ) : null}
            {addMode === "existing-location" ? (
              <form className="site-form-grid" onSubmit={handleSubmitUnit}>
                <p className="section-copy field-full">
                  Advertising Unit: a sellable advertising face, direction,
                  screen, or display at a location.
                </p>
                <label className="field field-full">
                  <span>Parent Location</span>
                  <select
                    value={unitForm.site || ""}
                    onChange={(event) =>
                      updateUnitForm("site", Number(event.target.value))
                    }
                    required
                  >
                    <option value="" disabled>
                      Select a location
                    </option>
                    {(directory?.sites ?? []).map((site) => (
                      <option key={site.id} value={site.id}>
                        {site.code} · {site.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  <span>Unit code</span>
                  <input
                    value={unitForm.unit_code}
                    onChange={(event) =>
                      updateUnitForm(
                        "unit_code",
                        event.target.value.toUpperCase(),
                      )
                    }
                    required
                  />
                </label>
                <label className="field">
                  <span>Facing direction</span>
                  <input
                    value={unitForm.facing_direction}
                    onChange={(event) =>
                      updateUnitForm("facing_direction", event.target.value)
                    }
                  />
                </label>
                <label className="field">
                  <span>Display format / sides sold</span>
                  <select
                    value={unitForm.site_type}
                    onChange={(event) =>
                      updateUnitForm("site_type", event.target.value)
                    }
                  >
                    {MEDIA_UNIT_SITE_TYPE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  <span>Face count</span>
                  <input
                    type="number"
                    min="1"
                    value={unitForm.face_count}
                    onChange={(event) =>
                      updateUnitForm("face_count", Number(event.target.value))
                    }
                    required
                  />
                </label>
                <label className="field">
                  <span>Status</span>
                  <select
                    value={unitForm.status}
                    onChange={(event) =>
                      updateUnitForm("status", event.target.value)
                    }
                  >
                    {["available", "reserved", "maintenance", "retired"].map(
                      (status) => (
                        <option key={status} value={status}>
                          {formatChoice(status)}
                        </option>
                      ),
                    )}
                  </select>
                </label>
                <label className="field">
                  <span>Width</span>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={unitForm.width}
                    onChange={(event) =>
                      updateUnitForm("width", event.target.value)
                    }
                    required
                  />
                </label>
                <label className="field">
                  <span>Height</span>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={unitForm.height}
                    onChange={(event) =>
                      updateUnitForm("height", event.target.value)
                    }
                    required
                  />
                </label>
                <label className="field">
                  <span>Monthly rate</span>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={unitForm.monthly_rate}
                    onChange={(event) =>
                      updateUnitForm("monthly_rate", event.target.value)
                    }
                    required
                  />
                </label>
                <label className="checkbox-field">
                  <input
                    type="checkbox"
                    checked={unitForm.is_illuminated}
                    onChange={(event) =>
                      updateUnitForm("is_illuminated", event.target.checked)
                    }
                  />
                  <span>Illuminated</span>
                </label>
                <label className="checkbox-field">
                  <input
                    type="checkbox"
                    checked={unitForm.is_publicly_listed}
                    onChange={(event) =>
                      updateUnitForm("is_publicly_listed", event.target.checked)
                    }
                  />
                  <span>Publish in client media planners</span>
                </label>
                <label className="field field-full">
                  <span>Public description</span>
                  <textarea
                    rows={3}
                    value={unitForm.public_description}
                    onChange={(event) =>
                      updateUnitForm("public_description", event.target.value)
                    }
                    placeholder="Client-safe description of this advertising unit"
                  />
                </label>
                <label className="field field-full">
                  <span>Public features</span>
                  <input
                    value={unitForm.public_features.join(", ")}
                    onChange={(event) =>
                      updateUnitForm(
                        "public_features",
                        event.target.value
                          .split(",")
                          .map((value) => value.trim())
                          .filter(Boolean),
                      )
                    }
                    placeholder="High visibility, arterial road, illuminated"
                  />
                  <small>Comma-separated client-safe features.</small>
                </label>
                <label className="field field-full">
                  <span>Unit photos</span>
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    multiple
                    onChange={handlePendingUnitImagesChange}
                  />
                  <small>
                    Show the specific sellable advertising face or direction.
                  </small>
                </label>
                {pendingUnitImages.length ? (
                  <div className="unit-upload-preview-grid field-full">
                    {pendingUnitImages.map((image) => (
                      <article
                        className="upload-preview-card upload-preview-card-stacked"
                        key={image.id}
                      >
                        <img
                          className="upload-preview-image"
                          src={image.previewUrl}
                          alt={image.file.name}
                        />
                        <label className="field">
                          <span>Caption</span>
                          <input
                            value={image.caption}
                            onChange={(event) =>
                              setPendingUnitImages((current) =>
                                current.map((item) =>
                                  item.id === image.id
                                    ? { ...item, caption: event.target.value }
                                    : item,
                                ),
                              )
                            }
                          />
                        </label>
                        <label className="checkbox-field">
                          <input
                            type="radio"
                            name="unit-primary"
                            checked={primaryPendingUnitImageId === image.id}
                            onChange={() =>
                              setPrimaryPendingUnitImageId(image.id)
                            }
                          />
                          <span>Set as primary image</span>
                        </label>
                      </article>
                    ))}
                  </div>
                ) : null}
                {unitError ? (
                  <p className="error field-full">{unitError}</p>
                ) : null}
                {unitSuccess ? (
                  <p className="success field-full">{unitSuccess}</p>
                ) : null}
                <div className="form-actions field-full">
                  <button
                    className="ghost"
                    type="button"
                    onClick={() => setAddMode("choose")}
                  >
                    Back
                  </button>
                  <button
                    className="submit"
                    type="submit"
                    disabled={isUnitSubmitting || !unitForm.site}
                  >
                    {isUnitSubmitting
                      ? "Saving..."
                      : editingUnitId
                        ? "Save Advertising Unit"
                        : "Create Advertising Unit"}
                  </button>
                </div>
              </form>
            ) : null}
          </section>
        </div>
      ) : null}

      {detailTarget || isDetailLoading ? (
        <div
          className="inventory-drawer-backdrop"
          role="presentation"
          onMouseDown={(event) =>
            event.target === event.currentTarget && setDetailTarget(null)
          }
        >
          <aside
            className="inventory-drawer"
            role="dialog"
            aria-modal="true"
            aria-label="Inventory details"
          >
            {isDetailLoading ? (
              <p className="empty-state">Loading details...</p>
            ) : null}
            {detailTarget?.kind === "location" ? (
              <LocationDetail
                site={detailTarget.item}
                canManage={canManageSites}
                canManageImages={canManageImages}
                onClose={() => setDetailTarget(null)}
                onEdit={() => editLocation(detailTarget.item)}
                onPhotos={() => {
                  setPhotoTarget(detailTarget);
                  setDetailTarget(null);
                }}
                onDelete={() => void handleDeleteLocation(detailTarget.item)}
              />
            ) : null}
            {detailTarget?.kind === "unit" ? (
              <UnitDetail
                unit={detailTarget.item}
                canManage={canManageUnits}
                canManageImages={canManageImages}
                onClose={() => setDetailTarget(null)}
                onEdit={() => editUnit(detailTarget.item)}
                onPhotos={() => {
                  setPhotoTarget(detailTarget);
                  setDetailTarget(null);
                }}
                onViewer={() => setViewerUnit(detailTarget.item)}
                onLocation={() => void openLocation(detailTarget.item.site)}
              />
            ) : null}
          </aside>
        </div>
      ) : null}

      {photoTarget ? (
        <div
          className="inventory-drawer-backdrop"
          role="presentation"
          onMouseDown={(event) =>
            event.target === event.currentTarget && setPhotoTarget(null)
          }
        >
          <aside
            className="inventory-drawer inventory-photo-drawer"
            role="dialog"
            aria-modal="true"
            aria-label="Manage inventory photos"
          >
            <div className="module-head">
              <div>
                <p className="site-code">
                  {photoTarget.kind === "location"
                    ? "LOCATION PHOTOS"
                    : "UNIT PHOTOS"}
                </p>
                <h2>
                  {photoTarget.kind === "location"
                    ? photoTarget.item.name
                    : photoTarget.item.unit_code}
                </h2>
              </div>
              <button
                className="ghost"
                type="button"
                onClick={() => setPhotoTarget(null)}
              >
                Close
              </button>
            </div>
            <p className="section-copy">
              {photoTarget.kind === "location"
                ? "Show the physical structure, surroundings, and approach."
                : "Show the specific sellable advertising face or direction."}
            </p>
            <ImageManagerCard
              formIdPrefix={`${photoTarget.kind}-${photoTarget.item.id}-photo`}
              title={
                photoTarget.kind === "location"
                  ? photoTarget.item.name
                  : photoTarget.item.unit_code
              }
              eyebrow={
                photoTarget.kind === "location"
                  ? photoTarget.item.code
                  : "ADVERTISING UNIT"
              }
              description=""
              meta=""
              images={photoTarget.item.image_gallery}
              primaryImage={photoTarget.item.primary_image}
              canManage={canManageImages}
              uploadLabel="Upload image"
              emptyCopy="No photos have been uploaded yet."
              showHeroPreview
              onUpload={(payload) =>
                photoTarget.kind === "location"
                  ? handleSitePhotoUpload(photoTarget.item.id, payload)
                  : handleUnitPhotoUpload(photoTarget.item.id, payload)
              }
              onMarkPrimary={
                photoTarget.kind === "location"
                  ? handleSitePrimary
                  : handleUnitPrimary
              }
              onDelete={
                photoTarget.kind === "location"
                  ? handleSiteImageDelete
                  : handleUnitImageDelete
              }
            />
          </aside>
        </div>
      ) : null}
      <InventoryImageViewer
        unit={viewerUnit}
        allowDownload={canManageImages}
        onClose={() => setViewerUnit(null)}
      />
    </AppShell>
  );
}

function Pagination({
  page,
  pageCount,
  loading,
  onChange,
}: {
  page: number;
  pageCount: number;
  loading: boolean;
  onChange: (page: number) => void;
}) {
  return (
    <div className="pagination-row">
      <button
        className="ghost"
        type="button"
        disabled={loading || page <= 1}
        onClick={() => onChange(page - 1)}
      >
        Previous
      </button>
      <span>
        Page {page} of {pageCount}
      </span>
      <button
        className="ghost"
        type="button"
        disabled={loading || page >= pageCount}
        onClick={() => onChange(page + 1)}
      >
        Next
      </button>
    </div>
  );
}

function LocationDetail({
  site,
  canManage,
  canManageImages,
  onClose,
  onEdit,
  onPhotos,
  onDelete,
}: {
  site: InventorySite;
  canManage: boolean;
  canManageImages: boolean;
  onClose: () => void;
  onEdit: () => void;
  onPhotos: () => void;
  onDelete: () => void;
}) {
  return (
    <>
      <div className="module-head">
        <div>
          <p className="site-code">INVENTORY › LOCATIONS</p>
          <h2>{site.name}</h2>
          <p className="section-copy">
            {site.code} · {site.city}
          </p>
        </div>
        <button className="ghost" type="button" onClick={onClose}>
          Close
        </button>
      </div>
      <div className="inventory-detail-actions">
        <button className="ghost" type="button" onClick={onPhotos}>
          Manage Photos
        </button>
        {canManage ? (
          <button className="ghost" type="button" onClick={onEdit}>
            Edit
          </button>
        ) : null}
        {canManage ? (
          <details className="inventory-more">
            <summary>More</summary>
            <div>
              <button className="ghost-danger" type="button" onClick={onDelete}>
                Delete Location
              </button>
            </div>
          </details>
        ) : null}
      </div>
      <div className="inventory-detail-facts">
        <div>
          <span>Address</span>
          <strong>{site.address}</strong>
        </div>
        <div>
          <span>City / State</span>
          <strong>
            {site.city}, {site.state}
          </strong>
        </div>
        <div>
          <span>Coordinates</span>
          <strong>
            {site.latitude && site.longitude
              ? `${site.latitude}, ${site.longitude}`
              : "Not recorded"}
          </strong>
        </div>
        <div>
          <span>Category</span>
          <strong>{formatChoice(site.site_type)}</strong>
        </div>
        <div>
          <span>Photo completeness</span>
          <strong>{site.image_gallery.length} photo(s)</strong>
        </div>
        <div>
          <span>Updated</span>
          <strong>{formatDate(site.updated_at)}</strong>
        </div>
      </div>
      {canManageImages ? (
        <p className="field-help">
          Photo management uses safe public image URLs only. Existing booking
          and deletion safeguards remain unchanged.
        </p>
      ) : null}
    </>
  );
}

function UnitDetail({
  unit,
  canManage,
  canManageImages,
  onClose,
  onEdit,
  onPhotos,
  onViewer,
  onLocation,
}: {
  unit: InventoryUnit;
  canManage: boolean;
  canManageImages: boolean;
  onClose: () => void;
  onEdit: () => void;
  onPhotos: () => void;
  onViewer: () => void;
  onLocation: () => void;
}) {
  return (
    <>
      <div className="module-head">
        <div>
          <p className="site-code">INVENTORY › ADVERTISING UNITS</p>
          <h2>{unit.unit_code}</h2>
          <span className={`status-pill status-${unit.status}`}>
            {formatChoice(unit.status)}
          </span>
        </div>
        <button className="ghost" type="button" onClick={onClose}>
          Close
        </button>
      </div>
      <div className="inventory-detail-actions">
        <button className="ghost" type="button" onClick={onViewer} disabled={!unit.image_gallery.length}>
          View Photos
        </button>
        <button className="ghost" type="button" onClick={onPhotos}>
          Manage Photos
        </button>
        {canManage ? (
          <button className="ghost" type="button" onClick={onEdit}>
            Edit
          </button>
        ) : null}
      </div>
      <button
        className="inventory-parent-location"
        type="button"
        onClick={onLocation}
      >
        <span>LOCATION</span>
        <strong>View parent location</strong>
      </button>
      <div className="inventory-detail-facts">
        <div>
          <span>Facing direction</span>
          <strong>{unit.facing_direction || "Pending"}</strong>
        </div>
        <div>
          <span>Dimensions</span>
          <strong>
            {unit.width} × {unit.height}
          </strong>
        </div>
        <div>
          <span>Face count</span>
          <strong>{unit.face_count}</strong>
        </div>
        <div>
          <span>Display format</span>
          <strong>{formatMediaUnitSiteType(unit.site_type)}</strong>
        </div>
        <div>
          <span>Illumination</span>
          <strong>{unit.is_illuminated ? "Illuminated" : "Standard"}</strong>
        </div>
        <div>
          <span>Monthly rate</span>
          <strong>{formatMoney(unit.monthly_rate)}</strong>
        </div>
        <div>
          <span>Photos</span>
          <strong>{unit.image_gallery.length} photo(s)</strong>
        </div>
        <div>
          <span>Updated</span>
          <strong>{formatDate(unit.updated_at)}</strong>
        </div>
      </div>
      {canManageImages ? (
        <p className="field-help">
          Bookings, campaigns, POE, and public image URLs continue to use this
          unit’s existing identifiers and APIs.
        </p>
      ) : null}
    </>
  );
}
