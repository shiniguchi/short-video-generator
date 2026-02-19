// Web UI client-side logic

/* SSE client for generation progress page */
function connectSSE(jobId) {
    const evtSource = new EventSource("/ui/generate/" + jobId + "/events");
    const statusEl = document.getElementById("status");
    const progressBar = document.getElementById("progress-bar");
    const errorEl = document.getElementById("error");

    evtSource.onmessage = function(event) {
        const data = JSON.parse(event.data);
        if (statusEl) statusEl.textContent = data.message || data.status;
        if (progressBar) progressBar.style.width = (data.progress || 0) + "%";

        if (data.status === "done") {
            evtSource.close();
            window.location.href = "/ui/preview/" + data.run_id;
        } else if (data.status === "error") {
            evtSource.close();
            if (errorEl) {
                errorEl.textContent = "Error: " + (data.error || "Unknown error");
                errorEl.style.display = "block";
            }
        }
    };

    evtSource.onerror = function() {
        evtSource.close();
        if (statusEl) statusEl.textContent = "Connection lost. Check server logs.";
    };
}
