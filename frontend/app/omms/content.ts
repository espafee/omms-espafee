export type OmmsPageContent = {
  slug: string;
  eyebrow: string;
  title: string;
  intro: string;
  heroStat: string;
  heroStatLabel: string;
  sections: Array<{
    title: string;
    copy: string;
    bullets: string[];
  }>;
  cta: string;
};

export const navLinks = [
  { href: "/omms", label: "Home" },
  { href: "/omms/features", label: "Platform" },
  { href: "/omms/workflows", label: "Workflow" },
  { href: "/omms/mobile", label: "Mobile" },
  { href: "/omms/billing", label: "Billing" },
  { href: "/omms/operations", label: "Operations" },
  { href: "/omms/training", label: "Training" },
];

export const lifecycle = [
  "Campaign Estimate",
  "Client Approval",
  "Booking",
  "Assignment",
  "POE",
  "Issue",
  "Invoice",
  "Payment",
];

export const featureCards = [
  {
    title: "Inventory control",
    copy: "Create sites, media units, dimensions, photos, availability, and verified location records.",
  },
  {
    title: "Campaign execution",
    copy: "Move from planning to booking, field assignment, proof upload, issue handling, and closure.",
  },
  {
    title: "Finance clarity",
    copy: "Use estimates, GST-ready invoices, payment tracking, client statements, and audit history.",
  },
  {
    title: "Mobile POE",
    copy: "Field teams capture fresh photos, GPS, timestamp, upload status, and issue reports from mobile.",
  },
  {
    title: "Operational intelligence",
    copy: "Track suspicious POE, slow requests, alerts, notifications, audit timeline, and role activity.",
  },
  {
    title: "Client trust",
    copy: "Share approval links, proof records, public issue links, and clean reports without exposing admin data.",
  },
];

export const proofPoints = [
  "Outdoor media teams work from one source of truth.",
  "Bookings are protected from date conflicts and manual confusion.",
  "POE is linked to GPS, timestamp, booking, campaign, and reviewer decision.",
  "Invoices are based on confirmed bookings after campaign start.",
  "Managers see alerts, audit history, diagnostics, and operational risk.",
];

export const pages: Record<string, OmmsPageContent> = {
  features: {
    slug: "features",
    eyebrow: "Platform modules",
    title: "Every major outdoor media operation in one connected workspace.",
    intro:
      "OMMS is built around the way outdoor media companies actually work: inventory, campaigns, booking, field proof, billing, issue resolution, and reporting.",
    heroStat: "6+",
    heroStatLabel: "core operating modules",
    sections: [
      {
        title: "Inventory and media units",
        copy: "Maintain a clean record of every sellable asset. A site can include multiple units, faces, panels, or screens.",
        bullets: ["Site photos and dimensions", "Media type and availability", "Optional GPS during creation", "Verified GPS from first approved POE"],
      },
      {
        title: "Campaigns and bookings",
        copy: "Plan client campaigns and reserve media units only when the business flow is ready.",
        bullets: ["Client-linked campaign records", "Date-aware booking flow", "Assignment to field staff", "Running campaign visibility"],
      },
      {
        title: "Execution, issues, and proof",
        copy: "Field execution becomes traceable through assigned work, POE uploads, issue tasks, and review comments.",
        bullets: ["Mobile assigned work", "POE image upload", "GPS and timestamp validation", "Issue to task to resolution workflow"],
      },
    ],
    cta: "Explore the workflow",
  },
  workflows: {
    slug: "workflows",
    eyebrow: "Business lifecycle",
    title: "OMMS follows the correct outdoor media lifecycle from estimate to payment.",
    intro:
      "The platform separates proposed work from confirmed work. This keeps sales, operations, and finance aligned.",
    heroStat: "8",
    heroStatLabel: "linked lifecycle stages",
    sections: [
      {
        title: "Estimate before booking",
        copy: "A campaign estimate is shared with the client before inventory is booked. Once approved, teams can move toward confirmed bookings.",
        bullets: ["Campaign Estimate", "Client approval link", "Approved or rejected status", "Clean handoff to booking"],
      },
      {
        title: "Execution after booking",
        copy: "Bookings are assigned to field staff. POE confirms what was executed, and issues become trackable tasks.",
        bullets: ["Booking assignment", "Field staff mobile work", "POE upload and review", "Issue reporting and SLA tracking"],
      },
      {
        title: "Invoice after campaign start",
        copy: "Invoices are generated from confirmed bookings after the campaign start date, not from unconfirmed estimates.",
        bullets: ["Invoice from confirmed bookings", "GST-aware calculation", "Payment status tracking", "Client statement exports"],
      },
    ],
    cta: "See billing controls",
  },
  mobile: {
    slug: "mobile",
    eyebrow: "Mobile execution",
    title: "Field staff and owners get the right mobile workflow for their role.",
    intro:
      "The mobile app supports assigned work, POE upload, GPS capture, issue reporting, and owner-level operational visibility.",
    heroStat: "GPS",
    heroStatLabel: "captured at field level",
    sections: [
      {
        title: "Field staff workflow",
        copy: "Field staff see the work assigned to them and upload proof from the actual site.",
        bullets: ["Assigned work list", "Camera and GPS capture", "Upload retry safety", "Issue reporting from the field"],
      },
      {
        title: "First verified POE location",
        copy: "Latitude and longitude are not mandatory during inventory creation. The first verified POE can lock the true field location.",
        bullets: ["Optional manual coordinates", "First POE captures GPS", "Admin verification", "Future POEs checked against locked GPS"],
      },
      {
        title: "Admin mobile view",
        copy: "Owners and super admins can monitor operations without being pushed into field-staff screens.",
        bullets: ["Operations dashboard", "Running campaigns", "POE tracker", "Daily activity and alerts"],
      },
    ],
    cta: "Review operations intelligence",
  },
  billing: {
    slug: "billing",
    eyebrow: "Finance workflow",
    title: "Billing is built around estimates, invoices, GST, payments, and statements.",
    intro:
      "OMMS helps finance teams avoid confusing estimate and invoice flows while keeping payment history traceable.",
    heroStat: "Rs",
    heroStatLabel: "from estimate to collection",
    sections: [
      {
        title: "Campaign estimates",
        copy: "Estimates are pre-booking documents shared with clients for approval.",
        bullets: ["Draft, sent, approved, rejected", "Public approval link", "Proposed sites and rates", "Client-safe data exposure"],
      },
      {
        title: "Invoices",
        copy: "Invoices are generated after campaign start and are based on confirmed bookings.",
        bullets: ["Draft and issued status", "GST summary", "Professional PDF", "Void and audit controls"],
      },
      {
        title: "Payments and statements",
        copy: "Payments can be partial or full, and outstanding balances stay visible for follow-up.",
        bullets: ["Record payment", "Paid, partially paid, overdue", "Payment history", "Client statement export"],
      },
    ],
    cta: "Open platform features",
  },
  operations: {
    slug: "operations",
    eyebrow: "Operational intelligence",
    title: "Managers can see risk, delays, proof quality, and system health.",
    intro:
      "OMMS adds an intelligence layer over daily work so managers can act before clients escalate.",
    heroStat: "Live",
    heroStatLabel: "alerts and audit signals",
    sections: [
      {
        title: "POE analytics",
        copy: "Review suspicious proof, missing GPS, outside-radius uploads, duplicate or replacement POEs, and overdue review queues.",
        bullets: ["Suspicious POE count", "Geofence checks", "Review SLA", "Drill-down filters"],
      },
      {
        title: "Audit and notifications",
        copy: "Important actions become visible through audit events and in-app notifications.",
        bullets: ["Invoice issued", "Payment recorded", "POE uploaded", "Issue escalated"],
      },
      {
        title: "Diagnostics and health",
        copy: "Admin users can see request logs, slow requests, health checks, and background job readiness.",
        bullets: ["Request logging", "Slow request threshold", "Health endpoint", "Notification retry readiness"],
      },
    ],
    cta: "View training material",
  },
  training: {
    slug: "training",
    eyebrow: "Training and rollout",
    title: "OMMS includes beginner-friendly material for operators, finance, field teams, and admins.",
    intro:
      "The training manual and role decks explain not only how to use the system, but why each step matters.",
    heroStat: "6",
    heroStatLabel: "role guides and training decks",
    sections: [
      {
        title: "Master manual",
        copy: "A layman-friendly operations handbook explains the complete OMMS lifecycle.",
        bullets: ["Dashboard", "Inventory", "Campaigns", "Bookings", "POE", "Billing", "Mobile", "Troubleshooting"],
      },
      {
        title: "Role-based guides",
        copy: "Shorter guides help each team learn only the workflows they need.",
        bullets: ["Field Staff", "Finance Team", "Operations Team", "Inventory Team", "Admin and Super Admin"],
      },
      {
        title: "Client and enterprise demos",
        copy: "Presentation decks can be used for client demos, new employee onboarding, and enterprise training.",
        bullets: ["Client presentation", "Module training PPTs", "Workflow demos", "Future custom rollout material"],
      },
    ],
    cta: "Start with the homepage",
  },
};
