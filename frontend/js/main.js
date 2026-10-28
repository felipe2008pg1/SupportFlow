// API base URL is hardcoded for local development. Once we introduce
// environment-specific builds (staging/production), this will be injected
// at build/deploy time instead of hardcoded here.
const API_BASE_URL = "http://localhost:8000";

async function checkApiHealth() {
  const statusEl = document.getElementById("api-status");

  try {
    const response = await fetch(`${API_BASE_URL}/health`, {
      method: "GET",
      // No credentials are sent: this is a public, unauthenticated check.
      credentials: "omit",
    });

    if (!response.ok) {
      throw new Error(`Unexpected status: ${response.status}`);
    }

    const data = await response.json();

    // textContent (not innerHTML) — never render server data as HTML.
    statusEl.textContent = data.status === "ok" ? "Online" : "Unknown";
    statusEl.className = data.status === "ok" ? "status-ok" : "status-error";
  } catch (error) {
    statusEl.textContent = "Unavailable";
    statusEl.className = "status-error";
    // Logged for local debugging only; never surface raw error details to
    // the user (avoids leaking internal information).
    console.error("Health check failed:", error);
  }
}

document.addEventListener("DOMContentLoaded", checkApiHealth);
