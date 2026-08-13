async function checkHealth() {
  const statusEl = document.getElementById("status");
  try {
    const res = await fetch("http://localhost:8000/health");
    const data = await res.json();
    statusEl.textContent = "Backend says: " + data.status;
  } catch (err) {
    statusEl.textContent = "Could not reach backend. Is uvicorn running?";
  }
}
document.getElementById("check-btn").addEventListener("click", checkHealth);