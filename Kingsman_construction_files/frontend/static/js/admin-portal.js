document.addEventListener("DOMContentLoaded", async () => {
  const msg = document.getElementById("portalMsg");
  const welcome = document.getElementById("portalWelcome");
  const jobsBody = document.getElementById("portalJobsBody");

  const me = await KingsmanApi.apiFetch("/auth/me", { method: "GET" });
  if (!me.response.ok || !me.data?.ok) {
    KingsmanApi.clearAuth();
    window.location.href = "login.html";
    return;
  }

  const user = me.data.user;
  if (user.role !== "admin") {
    window.location.href = "portal.html";
    return;
  }

  KingsmanApi.saveAuth(me.data);
  welcome.textContent = `Welcome, ${user.full_name || user.email}.`;

  const [overview, jobsRes] = await Promise.all([
    KingsmanApi.apiFetch("/admin/overview", { method: "GET" }),
    KingsmanApi.apiFetch("/jobs", { method: "GET" }),
  ]);

  if (!overview.response.ok) {
    msg.textContent = overview.data?.error || "Could not load admin metrics.";
  } else {
    const m = overview.data.metrics || {};
    document.getElementById("mMessages").textContent = m.message_count ?? 0;
    document.getElementById("mUsers").textContent = m.user_count ?? 0;
    document.getElementById("mOpenJobs").textContent = m.open_jobs ?? 0;
    document.getElementById("mEmployees").textContent = m.active_employees ?? 0;
  }

  if (!jobsRes.response.ok) {
    jobsBody.innerHTML = "<tr><td colspan='5'>Failed to load jobs.</td></tr>";
  } else {
    const items = jobsRes.data?.items || [];
    jobsBody.innerHTML = items.length ? items.map((j) => `
      <tr>
        <td>${String(j.job_number).padStart(3, "0")}</td>
        <td>${j.title || "—"}</td>
        <td>${j.client_name || "—"}</td>
        <td>${j.status || "—"}</td>
        <td>${j.updated_at || "—"}</td>
      </tr>
    `).join("") : "<tr><td colspan='5'>No jobs found.</td></tr>";
  }

  document.getElementById("logoutBtn")?.addEventListener("click", (e) => {
    e.preventDefault();
    KingsmanApi.clearAuth();
    window.location.href = "login.html";
  });
});
