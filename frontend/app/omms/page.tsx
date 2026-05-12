import type { Metadata } from "next";

import { OmmsHomePage } from "./components/OmmsMarketing";

export const metadata: Metadata = {
  title: "OMMS by VistaAi | Outdoor Media Management System",
  description:
    "OMMS is a VistaAi outdoor media operations platform for inventory, campaigns, bookings, POE, issues, billing, payments, and analytics.",
};

export default function OmmsPage() {
  return <OmmsHomePage />;
}
