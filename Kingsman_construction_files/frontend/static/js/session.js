window.KingsmanApi = (() => {
  const API_BASE = (window.CONSTRUCTION_API_BASE || "http://localhost:8000/api/kingsman/v1").replace(/\/$/, "");

  function getToken() {
    return localStorage.getItem("kingsman_token") || "";
  }

  function getUser() {
    try {
      return JSON.parse(localStorage.getItem("kingsman_user") || "null");
    } catch {
      return null;
    }
  }

  function saveAuth(data) {
    if (data?.token) localStorage.setItem("kingsman_token", data.token);
    if (data?.user) localStorage.setItem("kingsman_user", JSON.stringify(data.user));
  }

  function clearAuth() {
    localStorage.removeItem("kingsman_token");
    localStorage.removeItem("kingsman_user");
  }

  async function apiFetch(path, options = {}) {
    const token = getToken();
    const headers = new Headers(options.headers || {});
    if (!headers.has("Content-Type") && options.body && !(options.body instanceof FormData)) {
      headers.set("Content-Type", "application/json");
    }
    if (token) headers.set("Authorization", `Bearer ${token}`);

    const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
    let data = null;
    try { data = await response.json(); } catch {}
    return { response, data };
  }

  return { API_BASE, getToken, getUser, saveAuth, clearAuth, apiFetch };
})();
