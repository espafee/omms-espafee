const API_ROOT = process.env.NEXT_PUBLIC_API_ROOT ?? "http://127.0.0.1:8000/api/v1";

function getApiOrigin() {
  try {
    return new URL(API_ROOT).origin;
  } catch {
    return typeof window !== "undefined" ? window.location.origin : "";
  }
}

export function normalizeMediaUrl(url: null | string | undefined) {
  if (!url) {
    return null;
  }

  if (/^(https?:)?\/\//i.test(url) || url.startsWith("data:") || url.startsWith("blob:")) {
    return url;
  }

  const origin = getApiOrigin();
  if (!origin) {
    return url;
  }

  try {
    return new URL(url, `${origin}/`).toString();
  } catch {
    return url;
  }
}
