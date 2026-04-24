"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { getAccessToken } from "@/lib/auth";

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    if (getAccessToken()) {
      router.replace("/dashboard");
      return;
    }
    router.replace("/login");
  }, [router]);

  return null;
}
