document.addEventListener("DOMContentLoaded", () => {
  bindLoginForm();
  bindSignupForm();
});

function bindLoginForm() {
  const form = document.getElementById("loginForm");
  const msg = document.getElementById("loginMsg");
  if (!form || !msg) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    msg.textContent = "Signing in…";

    const payload = Object.fromEntries(new FormData(form).entries());
    try {
      const { response, data } = await KingsmanApi.apiFetch("/auth/login", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      if (!response.ok || !data?.ok) {
        msg.textContent = data?.error || data?.errors?.join(" ") || "Login failed.";
        return;
      }

      KingsmanApi.saveAuth(data);
      msg.textContent = `Welcome ${data.user.full_name || data.user.email}`;
      const dest = data.user.role === "admin" ? "admin-portal.html" : "portal.html";
      setTimeout(() => { window.location.href = dest; }, 500);
    } catch {
      msg.textContent = "Network error. Please try again.";
    }
  });
}

function bindSignupForm() {
  const form = document.getElementById("signupForm");
  const msg = document.getElementById("signupMsg");
  if (!form || !msg) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    msg.textContent = "Creating account…";

    const payload = Object.fromEntries(new FormData(form).entries());
    try {
      const { response, data } = await KingsmanApi.apiFetch("/auth/signup", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      if (!response.ok || !data?.ok) {
        msg.textContent = data?.error || data?.errors?.join(" ") || "Signup failed.";
        return;
      }

      msg.textContent = "Account created. Redirecting to login…";
      setTimeout(() => { window.location.href = "login.html"; }, 700);
    } catch {
      msg.textContent = "Network error. Please try again.";
    }
  });
}
