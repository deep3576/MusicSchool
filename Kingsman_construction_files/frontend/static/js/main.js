document.addEventListener("DOMContentLoaded", () => {
  const yearEl = document.getElementById("year");
  if (yearEl) yearEl.textContent = String(new Date().getFullYear());

  hydrateAuthNav();
  loadHealth();
  loadServices();
  bindContactForm();
});

function hydrateAuthNav() {
  const menu = document.querySelector(".menu");
  if (!menu || !window.KingsmanApi) return;
  const user = KingsmanApi.getUser();
  if (!user) return;

  const login = menu.querySelector('a[href="login.html"]');
  const signup = menu.querySelector('a[href="signup.html"]');
  if (login) login.remove();
  if (signup) signup.remove();

  const portalLink = document.createElement("a");
  portalLink.href = user.role === "admin" ? "admin-portal.html" : "portal.html";
  portalLink.textContent = user.role === "admin" ? "Admin Portal" : "Portal";

  const logout = document.createElement("a");
  logout.href = "#";
  logout.textContent = "Log out";
  logout.addEventListener("click", (e) => {
    e.preventDefault();
    KingsmanApi.clearAuth();
    window.location.href = "login.html";
  });

  menu.appendChild(portalLink);
  menu.appendChild(logout);
}

async function loadHealth() {
  const statusEl = document.getElementById("apiStatus");
  if (!statusEl) return;

  try {
    const { response } = await KingsmanApi.apiFetch("/health", { method: "GET" });
    if (!response.ok) throw new Error("unhealthy");
    statusEl.textContent = `API connected: ${KingsmanApi.API_BASE}`;
  } catch {
    statusEl.textContent = "API unavailable right now. Update window.CONSTRUCTION_API_BASE for your backend host.";
  }
}

async function loadServices() {
  const listEl = document.getElementById("serviceList");
  if (!listEl) return;

  try {
    const { response, data } = await KingsmanApi.apiFetch("/services", { method: "GET" });
    if (!response.ok) return;
    const services = data.items || [];
    if (!services.length) return;

    listEl.innerHTML = services.map((service) => `
      <article class="card">
        <h3>${service.title}</h3>
        <p>${service.description}</p>
      </article>
    `).join("");
  } catch {
    // keep static fallback cards rendered in HTML
  }
}

function bindContactForm() {
  const form = document.getElementById("contactForm");
  const msg = document.getElementById("formMsg");
  if (!form || !msg) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    msg.textContent = "Sending…";

    const payload = Object.fromEntries(new FormData(form).entries());

    try {
      const { response, data } = await KingsmanApi.apiFetch("/contact", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      if (response.ok && data?.ok) {
        msg.textContent = data.message || "Thanks! We'll get back to you shortly.";
        form.reset();
        return;
      }

      msg.textContent = data?.errors?.join(" ") || data?.error || "Something went wrong.";
    } catch {
      msg.textContent = "Network error. Please try again.";
    }
  });
}
