export function saveSession(data) {
  localStorage.setItem("askdb_access", data.access_token);
  localStorage.setItem("askdb_refresh", data.refresh_token);
  localStorage.setItem("askdb_user", JSON.stringify(data.user));
}

export function clearSession() {
  localStorage.removeItem("askdb_access");
  localStorage.removeItem("askdb_refresh");
  localStorage.removeItem("askdb_user");
}

export function readStoredUser() {
  try {
    const raw = localStorage.getItem("askdb_user");
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function errorMessage(data, status) {
  const detail = data?.detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail.message === "string") return detail.message;
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || "Check the form and try again.").join(" ");
  }
  if (status === 429) return "Too many requests. Wait a moment and try again.";
  return "Request failed.";
}

let refreshPromise = null;

async function tryRefresh() {
  const refresh = localStorage.getItem("askdb_refresh");
  if (!refresh) return false;
  if (!refreshPromise) {
    refreshPromise = fetch("/api/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
    })
      .then(async (response) => {
        if (!response.ok) {
          clearSession();
          return false;
        }
        saveSession(await response.json());
        return true;
      })
      .catch(() => false)
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

export async function api(path, options = {}, retry = true) {
  const headers = { ...(options.headers || {}) };
  const token = localStorage.getItem("askdb_access");
  if (token) headers.Authorization = `Bearer ${token}`;
  const isForm = typeof FormData !== "undefined" && options.body instanceof FormData;
  if (options.body && !isForm && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(path, { ...options, headers });
  const skipRefresh =
    path.startsWith("/api/auth/login") ||
    path.startsWith("/api/auth/register") ||
    path.startsWith("/api/auth/refresh");
  if (response.status === 401 && retry && !skipRefresh) {
    const refreshed = await tryRefresh();
    if (refreshed) return api(path, options, false);
    clearSession();
    if (!window.location.pathname.startsWith("/login")) {
      window.location.assign("/login");
    }
    throw new Error("Your session expired. Sign in again.");
  }

  if (response.status === 204) return null;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(errorMessage(data, response.status));
    error.status = response.status;
    throw error;
  }
  return data;
}
