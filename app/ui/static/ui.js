// Web UI client-side logic

/* Generic detail modal — reusable for any table detail view */
function openDetailModal(title, url, columns) {
    var overlay = document.getElementById("detail-modal-overlay");
    var titleEl = document.getElementById("detail-modal-title");
    var table = document.getElementById("detail-modal-table");
    var emptyEl = document.getElementById("detail-modal-empty");

    titleEl.textContent = title;
    table.querySelector("thead").innerHTML = "";
    table.querySelector("tbody").innerHTML = "";
    emptyEl.style.display = "none";
    overlay.style.display = "flex";

    fetch(url)
        .then(function(r) { return r.json(); })
        .then(function(rows) {
            if (!rows.length) {
                emptyEl.style.display = "block";
                table.style.display = "none";
                return;
            }
            table.style.display = "";
            // Build header
            var headRow = "<tr>" + columns.map(function(c) { return "<th>" + c.label + "</th>"; }).join("") + "</tr>";
            table.querySelector("thead").innerHTML = headRow;
            // Build body
            var bodyHtml = rows.map(function(row) {
                return "<tr>" + columns.map(function(c) {
                    var val = row[c.key];
                    return "<td>" + (val != null ? val : "") + "</td>";
                }).join("") + "</tr>";
            }).join("");
            table.querySelector("tbody").innerHTML = bodyHtml;
        });
}

function closeDetailModal(e) {
    if (e && e.target !== e.currentTarget) return;
    document.getElementById("detail-modal-overlay").style.display = "none";
}

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

/* Auto-save all text fields in the analysis form, returns a Promise */
function saveAnalysisFields(jobId) {
    var form = document.querySelector('form[action$="/update-analysis"]');
    if (!form) return Promise.resolve();
    var fd = new FormData(form);
    return fetch("/ui/ugc/" + jobId + "/update-analysis", {
        method: "POST",
        body: fd,
        redirect: "manual"  // don't follow the 303 redirect
    });
}

/* Regenerate a single analysis item via Celery task, poll until changed */
function regenItem(jobId, item, btn) {
    var card = btn.closest(".stage-card");
    btn.disabled = true;
    btn.textContent = "Saving...";

    // Show spinner overlay on the card
    var overlay = document.createElement("div");
    overlay.className = "regen-overlay";
    overlay.innerHTML = '<div class="regen-spinner"></div><div class="regen-status">Saving fields...</div>';
    card.style.position = "relative";
    card.appendChild(overlay);

    // Always save current form values first, then queue regen
    saveAnalysisFields(jobId).then(function() {
        var statusEl = overlay.querySelector(".regen-status");
        statusEl.textContent = "Regenerating...";

        var fd = new FormData();
        fd.append("item", item);
        // Include reference photos + sketch paths for hero regen
        if (item === "hero_image") {
            var refContainer = document.getElementById("ref-images-data");
            if (refContainer && refContainer.dataset.refPhotoPaths) {
                fd.append("reference_paths", refContainer.dataset.refPhotoPaths);
            }
            if (refContainer && refContainer.dataset.sketchPaths) {
                fd.append("sketch_paths", refContainer.dataset.sketchPaths);
            }
        }
        return fetch("/ui/ugc/" + jobId + "/regen-item", { method: "POST", body: fd });
    })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.status !== "queued") {
                throw new Error(data.detail || "Failed to queue");
            }
            var oldValue = data.old_value;
            var taskId = data.task_id;
            var statusEl = overlay.querySelector(".regen-status");
            statusEl.textContent = item === "hero_image" ? "Generating image..." : "Generating...";

            // Poll for value change + check task status
            var attempts = 0;
            var maxAttempts = 60; // 2 min max
            var poll = setInterval(function() {
                attempts++;
                if (attempts > maxAttempts) {
                    clearInterval(poll);
                    statusEl.textContent = "Timeout — refresh page";
                    btn.textContent = "Regenerate";
                    btn.disabled = false;
                    return;
                }
                // Check task status for early failure detection
                if (taskId) {
                    fetch("/ui/ugc/task-status/" + taskId)
                        .then(function(r) { return r.json(); })
                        .then(function(t) {
                            if (t.state === "FAILURE") {
                                clearInterval(poll);
                                statusEl.textContent = "Failed: " + (t.error || "unknown error");
                                btn.textContent = "Regenerate";
                                btn.disabled = false;
                            }
                        });
                }
                fetch("/ui/ugc/" + jobId + "/field-value?item=" + item)
                    .then(function(r) { return r.json(); })
                    .then(function(d) {
                        if (d.value !== oldValue) {
                            clearInterval(poll);
                            statusEl.textContent = "Done!";
                            setTimeout(function() { window.location.reload(); }, 500);
                        }
                    });
            }, 2000);
        })
        .catch(function(err) {
            overlay.remove();
            btn.textContent = "Regenerate";
            btn.disabled = false;
        });
}

/* Show upload overlay on a card element. Returns overlay element for later removal. */
function showUploadOverlay(card, label) {
    if (!card) return null;
    // Ensure card is positioned for absolute overlay
    if (getComputedStyle(card).position === "static") card.style.position = "relative";
    var overlay = document.createElement("div");
    overlay.className = "regen-overlay upload-overlay";
    overlay.innerHTML = '<div class="regen-spinner"></div><div class="regen-status">' + (label || "Uploading…") + '</div>';
    card.appendChild(overlay);
    return overlay;
}

function hideUploadOverlay(overlay) {
    if (overlay && overlay.parentNode) overlay.remove();
}

/* Upload reference sketches for hero image generation */
function uploadSketch(jobId, input) {
    var files = input.files;
    if (!files.length) return;
    var status = document.getElementById("sketch-status");
    var thumbsContainer = document.getElementById("sketch-thumbs");

    // Client-side limit: max 1 sketch
    var existing = thumbsContainer ? thumbsContainer.querySelectorAll(".ref-upload-thumb").length : 0;
    if (existing >= 1) {
        if (status) status.textContent = "Max 1 sketch";
        input.value = "";
        return;
    }

    Array.from(files).forEach(function(file) {
        if (status) status.textContent = "Uploading...";
        var fd = new FormData();
        fd.append("sketch", file);

        fetch("/ui/ugc/" + jobId + "/upload-sketch", { method: "POST", body: fd })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.status === "ok") {
                    if (status) status.textContent = "Uploaded!";
                    var thumb = document.createElement("div");
                    thumb.className = "ref-upload-thumb sketch-thumb";
                    thumb.dataset.path = data.path;
                    thumb.innerHTML = '<img src="/' + data.path + '?t=' + Date.now() + '" alt="Sketch">' +
                        '<button type="button" class="ref-upload-remove" onclick="removeSketchThumb(' +
                        jobId + ', this)">&times;</button>';
                    if (thumbsContainer) thumbsContainer.appendChild(thumb);
                    syncRefPaths();
                    // Disable input if at limit
                    updateSketchLimit();
                } else {
                    if (status) status.textContent = "Upload failed: " + (data.detail || "unknown error");
                }
            })
            .catch(function(err) {
                if (status) status.textContent = "Upload error: " + err.message;
            });
    });
    input.value = "";
}

/* Remove a sketch thumbnail and delete file on server */
function removeSketchThumb(jobId, btn) {
    var thumb = btn.closest(".ref-upload-thumb");
    var path = thumb ? thumb.dataset.path : "";
    if (thumb) thumb.remove();
    // Delete file via server
    var fd = new FormData();
    fd.append("path", path);
    fetch("/ui/ugc/" + jobId + "/remove-sketch", { method: "POST", body: fd });
    syncRefPaths();
    updateSketchLimit();
}

/* Upload reference photos for subject-referenced hero generation */
function uploadRefPhoto(jobId, input) {
    var files = input.files;
    if (!files.length) return;
    var status = document.getElementById("ref-photo-status");
    var thumbsContainer = document.getElementById("ref-photo-thumbs");

    // Client-side limit: max 2 ref photos
    var existing = thumbsContainer ? thumbsContainer.querySelectorAll(".ref-upload-thumb").length : 0;
    if (existing >= 2) {
        if (status) status.textContent = "Max 2 reference photos";
        input.value = "";
        return;
    }

    Array.from(files).forEach(function(file) {
        if (status) status.textContent = "Uploading...";
        var fd = new FormData();
        fd.append("file", file);

        fetch("/ui/ugc/" + jobId + "/upload-ref-photo", { method: "POST", body: fd })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.status === "ok") {
                    // Show crop warning or plain success
                    if (data.cropped) {
                        if (status) status.textContent = "Uploaded (auto-cropped from " +
                            data.orig_width + "x" + data.orig_height + " to square)";
                    } else {
                        if (status) status.textContent = "Uploaded!";
                    }
                    var thumb = document.createElement("div");
                    thumb.className = "ref-upload-thumb ref-photo-thumb";
                    thumb.dataset.path = data.path;
                    thumb.innerHTML = '<img src="/' + data.path + '?t=' + Date.now() + '" alt="Reference">' +
                        '<button type="button" class="ref-upload-remove" onclick="removeRefPhoto(' +
                        jobId + ', this)">&times;</button>';
                    if (thumbsContainer) thumbsContainer.appendChild(thumb);
                    syncRefPaths();
                    // Disable input if at limit
                    updateRefPhotoLimit();
                } else {
                    if (status) status.textContent = "Upload failed: " + (data.detail || "unknown error");
                }
            })
            .catch(function(err) {
                if (status) status.textContent = "Upload error: " + err.message;
            });
    });
    input.value = "";
}

/* Remove a reference photo thumbnail and delete file on server */
function removeRefPhoto(jobId, btn) {
    var thumb = btn.closest(".ref-upload-thumb");
    var path = thumb ? thumb.dataset.path : "";
    if (thumb) thumb.remove();
    var fd = new FormData();
    fd.append("path", path);
    fetch("/ui/ugc/" + jobId + "/remove-ref-photo", { method: "POST", body: fd });
    syncRefPaths();
    updateRefPhotoLimit();
}

/* Enable/disable ref photo input based on current count */
function updateRefPhotoLimit() {
    var thumbs = document.getElementById("ref-photo-thumbs");
    var input = document.querySelector(".ref-photo-upload-input");
    if (!thumbs || !input) return;
    var count = thumbs.querySelectorAll(".ref-upload-thumb").length;
    input.disabled = count >= 2;
}

/* Enable/disable sketch input based on current count */
function updateSketchLimit() {
    var thumbs = document.getElementById("sketch-thumbs");
    var input = document.querySelector(".sketch-upload-input");
    if (!thumbs || !input) return;
    var count = thumbs.querySelectorAll(".ref-upload-thumb").length;
    input.disabled = count >= 1;
}

/* Generic debounced auto-save for a form */
function setupAutoSave(formSelector, statusElId) {
    var timer = null;
    document.addEventListener("DOMContentLoaded", function() {
        var form = document.querySelector(formSelector);
        if (!form) return;
        var statusEl = document.getElementById(statusElId);

        function autoSave() {
            if (statusEl) statusEl.textContent = "Saving...";
            fetch(form.action, {
                method: "POST",
                body: new FormData(form),
                redirect: "manual"
            }).then(function() {
                if (statusEl) statusEl.textContent = "Saved";
                setTimeout(function() {
                    if (statusEl && statusEl.textContent === "Saved") statusEl.textContent = "";
                }, 2000);
                // Show "inputs changed" hint on Hero Image card
                var hint = document.getElementById("hero-inputs-changed");
                if (hint) hint.style.display = "";
            }).catch(function() {
                if (statusEl) statusEl.textContent = "Save failed";
            });
        }

        form.addEventListener("input", function() {
            clearTimeout(timer);
            if (statusEl) statusEl.textContent = "";
            timer = setTimeout(autoSave, 800);
        });

        form.addEventListener("submit", function(e) {
            e.preventDefault();
            autoSave();
        });
    });
}

/* Auto-save for analysis form */
setupAutoSave('form[action$="/update-analysis"]', "autosave-status");

/* Auto-save for script form */
setupAutoSave('form[action$="/update-script"]', "script-autosave-status");

/* Init: sync ref paths on page load */
document.addEventListener("DOMContentLoaded", function() {
    syncRefPaths();
});

/* Toggle a generated hero thumbnail as reference */
function toggleHeroRef(thumb) {
    thumb.classList.toggle("selected");
    syncRefPaths();
}

/* Rebuild #ref-images-data with separate ref photo + sketch paths */
function syncRefPaths() {
    var container = document.getElementById("ref-images-data");
    if (!container) return;
    // Reference photo thumbnails
    var refPhotoPaths = Array.from(
        document.querySelectorAll("#ref-photo-thumbs .ref-upload-thumb")
    ).map(function(el) { return el.dataset.path; });
    // Selected generated hero history images count as ref photos too
    var heroPaths = Array.from(
        document.querySelectorAll("#hero-thumb-grid .hero-thumb.selected")
    ).map(function(el) { return el.dataset.path; });
    // Sketch thumbnails (hand-drawn only)
    var sketchPaths = Array.from(
        document.querySelectorAll("#sketch-thumbs .ref-upload-thumb")
    ).map(function(el) { return el.dataset.path; });
    container.dataset.refPhotoPaths = JSON.stringify(refPhotoPaths.concat(heroPaths));
    container.dataset.sketchPaths = JSON.stringify(sketchPaths);
}

/* Upload a custom creator image for A-Roll */
function uploadArollImage(jobId, sceneIndex, input) {
    var file = input.files[0];
    if (!file) return;
    var card = input.closest(".stage-card, .scene-image-card");
    var overlay = showUploadOverlay(card, "Uploading…");
    var fd = new FormData();
    fd.append("file", file);
    fd.append("scene_index", sceneIndex);
    fetch("/ui/ugc/" + jobId + "/upload-aroll-image", {
        method: "POST",
        body: fd,
        redirect: "manual"
    }).then(function() {
        window.location.reload();
    }).catch(function(err) {
        hideUploadOverlay(overlay);
        alert("Upload failed: " + err.message);
    });
}

/* Upload an external image as hero image */
function uploadHeroImage(jobId, input) {
    var file = input.files[0];
    if (!file) return;
    var card = input.closest(".stage-card, .scene-image-card, .hero-card");
    var overlay = showUploadOverlay(card, "Uploading…");
    var fd = new FormData();
    fd.append("file", file);
    fetch("/ui/ugc/" + jobId + "/upload-hero-image", {
        method: "POST",
        body: fd,
        redirect: "manual"
    }).then(function() {
        window.location.reload();
    }).catch(function(err) {
        hideUploadOverlay(overlay);
        alert("Upload failed: " + err.message);
    });
}

/* Restore a previous hero image from history */
function restoreHeroImage(jobId, path) {
    if (!confirm("Restore this image as the current hero image?")) return;
    var fd = new FormData();
    fd.append("path", path);
    fetch("/ui/ugc/" + jobId + "/restore-hero-image", {
        method: "POST",
        body: fd,
        redirect: "manual"
    }).then(function() {
        window.location.reload();
    }).catch(function(err) {
        alert("Restore failed: " + err.message);
    });
}

/* Regenerate a single scene/shot image, poll until changed */
function regenSceneImage(jobId, sceneType, index, btn) {
    var card = btn.closest(".scene-image-card");
    btn.disabled = true;
    btn.textContent = "Regenerating...";

    // Show spinner overlay on the card
    var overlay = document.createElement("div");
    overlay.className = "regen-overlay";
    overlay.innerHTML = '<div class="regen-spinner"></div><div class="regen-status">Generating image...</div>';
    card.style.position = "relative";
    card.appendChild(overlay);

    var fd = new FormData();
    fd.append("scene_type", sceneType);
    fd.append("scene_index", index);

    // Send edited prompt if the user changed it
    var promptEl = card.querySelector('.scene-prompt-edit');
    if (promptEl) {
        fd.append("updated_prompt", promptEl.value);
    }

    fetch("/ui/ugc/" + jobId + "/regen-scene-image", { method: "POST", body: fd })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.status !== "queued") {
                throw new Error(data.detail || "Failed to queue");
            }
            var oldValue = data.old_value;
            var taskId = data.task_id;
            var itemName = sceneType === "aroll" ? "aroll_image_paths" : "broll_image_paths";

            // Poll for value change + check task status
            var attempts = 0;
            var maxAttempts = 60;
            var poll = setInterval(function() {
                attempts++;
                if (attempts > maxAttempts) {
                    clearInterval(poll);
                    overlay.querySelector(".regen-status").textContent = "Timeout — refresh page";
                    btn.textContent = "Regenerate";
                    btn.disabled = false;
                    return;
                }
                // Check task status for early failure detection
                if (taskId) {
                    fetch("/ui/ugc/task-status/" + taskId)
                        .then(function(r) { return r.json(); })
                        .then(function(t) {
                            if (t.state === "FAILURE") {
                                clearInterval(poll);
                                overlay.querySelector(".regen-status").textContent = "Failed: " + (t.error || "unknown error");
                                btn.textContent = "Regenerate";
                                btn.disabled = false;
                            }
                        });
                }
                fetch("/ui/ugc/" + jobId + "/field-value?item=" + itemName + "&index=" + index)
                    .then(function(r) { return r.json(); })
                    .then(function(d) {
                        if (d.value !== oldValue) {
                            clearInterval(poll);
                            overlay.querySelector(".regen-status").textContent = "Done!";
                            setTimeout(function() { window.location.reload(); }, 500);
                        }
                    });
            }, 2000);
        })
        .catch(function(err) {
            overlay.remove();
            btn.textContent = "Regenerate";
            btn.disabled = false;
        });
}

/* Regenerate a single A-Roll video clip */
function regenSceneVideo(jobId, sceneType, index, btn) {
    var card = btn.closest(".scene-video-card");
    btn.disabled = true;
    btn.textContent = "Regenerating...";

    var overlay = document.createElement("div");
    overlay.className = "regen-overlay";
    overlay.innerHTML = '<div class="regen-spinner"></div><div class="regen-status">Generating video...</div>';
    card.style.position = "relative";
    card.appendChild(overlay);

    var fd = new FormData();
    fd.append("scene_type", sceneType);
    fd.append("scene_index", index);

    // Send edited prompt if user changed it
    var promptEl = card.querySelector('.scene-prompt-edit');
    if (promptEl) {
        fd.append("updated_prompt", promptEl.value);
    }

    fetch("/ui/ugc/" + jobId + "/regen-scene-video", { method: "POST", body: fd })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.status !== "queued") {
                throw new Error(data.detail || "Failed to queue");
            }
            var oldValue = data.old_value;
            var taskId = data.task_id;

            var attempts = 0;
            var maxAttempts = 90; // videos take longer
            var poll = setInterval(function() {
                attempts++;
                if (attempts > maxAttempts) {
                    clearInterval(poll);
                    overlay.querySelector(".regen-status").textContent = "Timeout — refresh page";
                    btn.textContent = "Regenerate";
                    btn.disabled = false;
                    return;
                }
                if (taskId) {
                    fetch("/ui/ugc/task-status/" + taskId)
                        .then(function(r) { return r.json(); })
                        .then(function(t) {
                            if (t.state === "SUCCESS") {
                                clearInterval(poll);
                                overlay.querySelector(".regen-status").textContent = "Done!";
                                setTimeout(function() { window.location.reload(); }, 500);
                            }
                            if (t.state === "FAILURE") {
                                clearInterval(poll);
                                overlay.querySelector(".regen-status").textContent = "Failed: " + (t.error || "unknown error");
                                btn.textContent = "Regenerate";
                                btn.disabled = false;
                            }
                        });
                }
            }, 3000);
        })
        .catch(function(err) {
            overlay.remove();
            btn.textContent = "Regenerate";
            btn.disabled = false;
        });
}

/* Regenerate all A-Roll video clips */
function regenAllSceneVideos(jobId) {
    var allBtn = document.querySelector(".btn-regen-all-videos");
    var perClipBtns = document.querySelectorAll('.scene-video-card .btn-regen');
    var cards = document.querySelectorAll('.scene-video-card');

    if (allBtn) { allBtn.disabled = true; allBtn.textContent = "Regenerating All..."; }
    perClipBtns.forEach(function(b) { b.disabled = true; });
    showRegenProgress("Regenerating all A-Roll videos...");

    cards.forEach(function(card) {
        card.style.position = "relative";
        var overlay = document.createElement("div");
        overlay.className = "regen-overlay regen-all-video-overlay";
        overlay.innerHTML = '<div class="regen-spinner"></div><div class="regen-status">Regenerating all clips...</div>';
        card.appendChild(overlay);
    });

    var fd = new FormData();
    fetch("/ui/ugc/" + jobId + "/regen-all-scene-videos", { method: "POST", body: fd })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.status !== "queued") {
                throw new Error(data.detail || "Failed to queue");
            }
            var taskId = data.task_id;
            var attempts = 0;
            var maxAttempts = 150; // ~7.5 min
            var poll = setInterval(function() {
                attempts++;
                if (attempts > maxAttempts) {
                    clearInterval(poll);
                    document.querySelectorAll(".regen-all-video-overlay .regen-status").forEach(function(el) {
                        el.textContent = "Timeout — refresh page";
                    });
                    if (allBtn) { allBtn.textContent = "Regenerate All Clips"; allBtn.disabled = false; }
                    perClipBtns.forEach(function(b) { b.disabled = false; });
                    hideRegenProgress();
                    return;
                }
                fetch("/ui/ugc/task-status/" + taskId)
                    .then(function(r) { return r.json(); })
                    .then(function(t) {
                        if (t.state === "SUCCESS") {
                            clearInterval(poll);
                            document.querySelectorAll(".regen-all-video-overlay .regen-status").forEach(function(el) {
                                el.textContent = "Done!";
                            });
                            hideRegenProgress();
                            setTimeout(function() { window.location.reload(); }, 500);
                        } else if (t.state === "FAILURE") {
                            clearInterval(poll);
                            var errMsg = t.error || "unknown error";
                            document.querySelectorAll(".regen-all-video-overlay .regen-status").forEach(function(el) {
                                el.textContent = "Failed: " + errMsg;
                            });
                            if (allBtn) { allBtn.textContent = "Regenerate All Clips"; allBtn.disabled = false; }
                            perClipBtns.forEach(function(b) { b.disabled = false; });
                            hideRegenProgress();
                        }
                    });
            }, 3000);
        })
        .catch(function(err) {
            document.querySelectorAll(".regen-all-video-overlay").forEach(function(el) { el.remove(); });
            if (allBtn) { allBtn.textContent = "Regenerate All Clips"; allBtn.disabled = false; }
            perClipBtns.forEach(function(b) { b.disabled = false; });
            hideRegenProgress();
        });
}

/* Regenerate all A-Roll scene images together for character consistency */
function regenAllSceneImages(jobId, sceneType) {
    var allBtn = document.querySelector(".btn-regen-all");
    var perSceneBtns = document.querySelectorAll('.scene-image-card[data-scene-type="' + sceneType + '"] .btn-regen');
    var cards = document.querySelectorAll('.scene-image-card[data-scene-type="' + sceneType + '"]');

    // Disable all buttons + show global progress
    if (allBtn) { allBtn.disabled = true; allBtn.textContent = "Regenerating All..."; }
    perSceneBtns.forEach(function(b) { b.disabled = true; });
    showRegenProgress("Regenerating all " + sceneType + " images...");

    // Show spinner overlay on all scene cards
    cards.forEach(function(card) {
        card.style.position = "relative";
        var overlay = document.createElement("div");
        overlay.className = "regen-overlay regen-all-overlay";
        overlay.innerHTML = '<div class="regen-spinner"></div><div class="regen-status">Regenerating all scenes...</div>';
        card.appendChild(overlay);
    });

    var fd = new FormData();
    fd.append("scene_type", sceneType);

    fetch("/ui/ugc/" + jobId + "/regen-all-scene-images", { method: "POST", body: fd })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.status !== "queued") {
                throw new Error(data.detail || "Failed to queue");
            }
            var taskId = data.task_id;

            // Poll task status every 3s
            var attempts = 0;
            var maxAttempts = 100; // ~5 min max
            var poll = setInterval(function() {
                attempts++;
                if (attempts > maxAttempts) {
                    clearInterval(poll);
                    document.querySelectorAll(".regen-all-overlay .regen-status").forEach(function(el) {
                        el.textContent = "Timeout — refresh page";
                    });
                    if (allBtn) { allBtn.textContent = "Regenerate All Scenes"; allBtn.disabled = false; }
                    perSceneBtns.forEach(function(b) { b.disabled = false; });
                    hideRegenProgress();
                    return;
                }
                fetch("/ui/ugc/task-status/" + taskId)
                    .then(function(r) { return r.json(); })
                    .then(function(t) {
                        if (t.state === "SUCCESS") {
                            clearInterval(poll);
                            document.querySelectorAll(".regen-all-overlay .regen-status").forEach(function(el) {
                                el.textContent = "Done!";
                            });
                            hideRegenProgress();
                            setTimeout(function() { window.location.reload(); }, 500);
                        } else if (t.state === "FAILURE") {
                            clearInterval(poll);
                            var errMsg = t.error || "unknown error";
                            document.querySelectorAll(".regen-all-overlay .regen-status").forEach(function(el) {
                                el.textContent = "Failed: " + errMsg;
                            });
                            if (allBtn) { allBtn.textContent = "Regenerate All Scenes"; allBtn.disabled = false; }
                            perSceneBtns.forEach(function(b) { b.disabled = false; });
                            hideRegenProgress();
                        }
                    });
            }, 3000);
        })
        .catch(function(err) {
            document.querySelectorAll(".regen-all-overlay").forEach(function(el) { el.remove(); });
            if (allBtn) { allBtn.textContent = "Regenerate All Scenes"; allBtn.disabled = false; }
            perSceneBtns.forEach(function(b) { b.disabled = false; });
            hideRegenProgress();
        });
}

/* Regenerate a single script field/scene/shot */
function regenScriptField(jobId, fieldType, fieldIndex, btn) {
    var card = btn.closest(".stage-card");
    btn.disabled = true;
    btn.textContent = "Regenerating...";

    card.style.position = "relative";
    var overlay = document.createElement("div");
    overlay.className = "regen-overlay";
    overlay.innerHTML = '<div class="regen-spinner"></div><div class="regen-status">Regenerating...</div>';
    card.appendChild(overlay);

    var fd = new FormData();
    fd.append("field_type", fieldType);
    fd.append("field_index", fieldIndex);

    fetch("/ui/ugc/" + jobId + "/regen-script-field", { method: "POST", body: fd })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.status !== "queued") { throw new Error(data.detail || "Failed to queue"); }
            var taskId = data.task_id;
            var attempts = 0;
            var maxAttempts = 100;
            var poll = setInterval(function() {
                attempts++;
                if (attempts > maxAttempts) {
                    clearInterval(poll);
                    overlay.querySelector(".regen-status").textContent = "Timeout — refresh page";
                    btn.textContent = "Regenerate"; btn.disabled = false;
                    return;
                }
                fetch("/ui/ugc/task-status/" + taskId)
                    .then(function(r) { return r.json(); })
                    .then(function(t) {
                        if (t.state === "SUCCESS") {
                            clearInterval(poll);
                            overlay.querySelector(".regen-status").textContent = "Done!";
                            setTimeout(function() { window.location.reload(); }, 500);
                        } else if (t.state === "FAILURE") {
                            clearInterval(poll);
                            overlay.querySelector(".regen-status").textContent = "Failed: " + (t.error || "unknown");
                            btn.textContent = "Regenerate"; btn.disabled = false;
                        }
                    });
            }, 3000);
        })
        .catch(function(err) {
            overlay.remove();
            btn.textContent = "Regenerate"; btn.disabled = false;
        });
}

/* Regenerate entire script */
function regenAllScript(jobId) {
    var allBtn = document.querySelector(".btn-regen-all-script");
    var section = document.querySelector(".stage-section");

    if (allBtn) { allBtn.disabled = true; allBtn.textContent = "Regenerating..."; }
    showRegenProgress("Regenerating entire script...");

    // Overlay on section
    if (section) {
        section.style.position = "relative";
        var overlay = document.createElement("div");
        overlay.className = "regen-overlay regen-all-script-overlay";
        overlay.innerHTML = '<div class="regen-spinner"></div><div class="regen-status">Regenerating script...</div>';
        section.appendChild(overlay);
    }

    var fd = new FormData();
    fetch("/ui/ugc/" + jobId + "/regen-all-script", { method: "POST", body: fd })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.status !== "queued") { throw new Error(data.detail || "Failed to queue"); }
            var taskId = data.task_id;
            var attempts = 0;
            var maxAttempts = 100;
            var poll = setInterval(function() {
                attempts++;
                if (attempts > maxAttempts) {
                    clearInterval(poll);
                    document.querySelectorAll(".regen-all-script-overlay .regen-status").forEach(function(el) { el.textContent = "Timeout — refresh page"; });
                    if (allBtn) { allBtn.textContent = "Regenerate Script"; allBtn.disabled = false; }
                    hideRegenProgress();
                    return;
                }
                fetch("/ui/ugc/task-status/" + taskId)
                    .then(function(r) { return r.json(); })
                    .then(function(t) {
                        if (t.state === "SUCCESS") {
                            clearInterval(poll);
                            document.querySelectorAll(".regen-all-script-overlay .regen-status").forEach(function(el) { el.textContent = "Done!"; });
                            hideRegenProgress();
                            setTimeout(function() { window.location.reload(); }, 500);
                        } else if (t.state === "FAILURE") {
                            clearInterval(poll);
                            document.querySelectorAll(".regen-all-script-overlay .regen-status").forEach(function(el) { el.textContent = "Failed: " + (t.error || "unknown"); });
                            if (allBtn) { allBtn.textContent = "Regenerate Script"; allBtn.disabled = false; }
                            hideRegenProgress();
                        }
                    });
            }, 3000);
        })
        .catch(function(err) {
            document.querySelectorAll(".regen-all-script-overlay").forEach(function(el) { el.remove(); });
            if (allBtn) { allBtn.textContent = "Regenerate Script"; allBtn.disabled = false; }
            hideRegenProgress();
        });
}

/* Regenerate all B-Roll shot images */
function toggleBrollCreator(jobId, enabled) {
    var fd = new FormData();
    fd.append("enabled", enabled);
    fetch("/ui/ugc/" + jobId + "/toggle-broll-creator", { method: "POST", body: fd })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (!data.ok) { console.error("toggle failed", data); }
        })
        .catch(function(err) { console.error("toggle error", err); });
}

function regenAllBrollImages(jobId) {
    var allBtn = document.querySelector(".btn-regen-all-broll-images");
    var perShotBtns = document.querySelectorAll('.scene-image-card[data-scene-type="broll"] .btn-regen');
    var cards = document.querySelectorAll('.scene-image-card[data-scene-type="broll"]');

    if (allBtn) { allBtn.disabled = true; allBtn.textContent = "Regenerating All..."; }
    perShotBtns.forEach(function(b) { b.disabled = true; });
    showRegenProgress("Regenerating all B-Roll images...");

    cards.forEach(function(card) {
        card.style.position = "relative";
        var overlay = document.createElement("div");
        overlay.className = "regen-overlay regen-all-broll-img-overlay";
        overlay.innerHTML = '<div class="regen-spinner"></div><div class="regen-status">Regenerating all shots...</div>';
        card.appendChild(overlay);
    });

    var fd = new FormData();
    fetch("/ui/ugc/" + jobId + "/regen-all-broll-images", { method: "POST", body: fd })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.status !== "queued") { throw new Error(data.detail || "Failed to queue"); }
            var taskId = data.task_id;
            var attempts = 0;
            var maxAttempts = 100;
            var poll = setInterval(function() {
                attempts++;
                if (attempts > maxAttempts) {
                    clearInterval(poll);
                    document.querySelectorAll(".regen-all-broll-img-overlay .regen-status").forEach(function(el) { el.textContent = "Timeout — refresh page"; });
                    if (allBtn) { allBtn.textContent = "Regenerate All Shots"; allBtn.disabled = false; }
                    perShotBtns.forEach(function(b) { b.disabled = false; });
                    hideRegenProgress();
                    return;
                }
                fetch("/ui/ugc/task-status/" + taskId)
                    .then(function(r) { return r.json(); })
                    .then(function(t) {
                        if (t.state === "SUCCESS") {
                            clearInterval(poll);
                            document.querySelectorAll(".regen-all-broll-img-overlay .regen-status").forEach(function(el) { el.textContent = "Done!"; });
                            hideRegenProgress();
                            setTimeout(function() { window.location.reload(); }, 500);
                        } else if (t.state === "FAILURE") {
                            clearInterval(poll);
                            document.querySelectorAll(".regen-all-broll-img-overlay .regen-status").forEach(function(el) { el.textContent = "Failed: " + (t.error || "unknown"); });
                            if (allBtn) { allBtn.textContent = "Regenerate All Shots"; allBtn.disabled = false; }
                            perShotBtns.forEach(function(b) { b.disabled = false; });
                            hideRegenProgress();
                        }
                    });
            }, 3000);
        })
        .catch(function(err) {
            document.querySelectorAll(".regen-all-broll-img-overlay").forEach(function(el) { el.remove(); });
            if (allBtn) { allBtn.textContent = "Regenerate All Shots"; allBtn.disabled = false; }
            perShotBtns.forEach(function(b) { b.disabled = false; });
            hideRegenProgress();
        });
}

/* Regenerate all B-Roll video clips */
function regenAllBrollVideos(jobId) {
    var allBtn = document.querySelector(".btn-regen-all-broll-videos");
    var perClipBtns = document.querySelectorAll('.broll-video-card .btn-regen');
    var cards = document.querySelectorAll('.broll-video-card');

    if (allBtn) { allBtn.disabled = true; allBtn.textContent = "Regenerating All..."; }
    perClipBtns.forEach(function(b) { b.disabled = true; });
    showRegenProgress("Regenerating all B-Roll videos...");

    cards.forEach(function(card) {
        card.style.position = "relative";
        var overlay = document.createElement("div");
        overlay.className = "regen-overlay regen-all-broll-vid-overlay";
        overlay.innerHTML = '<div class="regen-spinner"></div><div class="regen-status">Regenerating all clips...</div>';
        card.appendChild(overlay);
    });

    var fd = new FormData();
    fetch("/ui/ugc/" + jobId + "/regen-all-broll-videos", { method: "POST", body: fd })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.status !== "queued") { throw new Error(data.detail || "Failed to queue"); }
            var taskId = data.task_id;
            var attempts = 0;
            var maxAttempts = 150;
            var poll = setInterval(function() {
                attempts++;
                if (attempts > maxAttempts) {
                    clearInterval(poll);
                    document.querySelectorAll(".regen-all-broll-vid-overlay .regen-status").forEach(function(el) { el.textContent = "Timeout — refresh page"; });
                    if (allBtn) { allBtn.textContent = "Regenerate All Clips"; allBtn.disabled = false; }
                    perClipBtns.forEach(function(b) { b.disabled = false; });
                    hideRegenProgress();
                    return;
                }
                fetch("/ui/ugc/task-status/" + taskId)
                    .then(function(r) { return r.json(); })
                    .then(function(t) {
                        if (t.state === "SUCCESS") {
                            clearInterval(poll);
                            document.querySelectorAll(".regen-all-broll-vid-overlay .regen-status").forEach(function(el) { el.textContent = "Done!"; });
                            hideRegenProgress();
                            setTimeout(function() { window.location.reload(); }, 500);
                        } else if (t.state === "FAILURE") {
                            clearInterval(poll);
                            document.querySelectorAll(".regen-all-broll-vid-overlay .regen-status").forEach(function(el) { el.textContent = "Failed: " + (t.error || "unknown"); });
                            if (allBtn) { allBtn.textContent = "Regenerate All Clips"; allBtn.disabled = false; }
                            perClipBtns.forEach(function(b) { b.disabled = false; });
                            hideRegenProgress();
                        }
                    });
            }, 3000);
        })
        .catch(function(err) {
            document.querySelectorAll(".regen-all-broll-vid-overlay").forEach(function(el) { el.remove(); });
            if (allBtn) { allBtn.textContent = "Regenerate All Clips"; allBtn.disabled = false; }
            perClipBtns.forEach(function(b) { b.disabled = false; });
            hideRegenProgress();
        });
}

/* Regenerate a single B-Roll video clip */
function regenBrollVideo(jobId, shotIndex, btn) {
    var card = btn.closest('.broll-video-card');
    btn.disabled = true;
    btn.textContent = "Regenerating...";

    card.style.position = "relative";
    var overlay = document.createElement("div");
    overlay.className = "regen-overlay";
    overlay.innerHTML = '<div class="regen-spinner"></div><div class="regen-status">Regenerating clip...</div>';
    card.appendChild(overlay);

    var fd = new FormData();
    fd.append("shot_index", shotIndex);

    fetch("/ui/ugc/" + jobId + "/regen-broll-video", { method: "POST", body: fd })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.status !== "queued") { throw new Error(data.detail || "Failed to queue"); }
            var taskId = data.task_id;
            var attempts = 0;
            var maxAttempts = 100;
            var poll = setInterval(function() {
                attempts++;
                if (attempts > maxAttempts) {
                    clearInterval(poll);
                    overlay.querySelector(".regen-status").textContent = "Timeout — refresh page";
                    btn.textContent = "Regenerate"; btn.disabled = false;
                    return;
                }
                fetch("/ui/ugc/task-status/" + taskId)
                    .then(function(r) { return r.json(); })
                    .then(function(t) {
                        if (t.state === "SUCCESS") {
                            clearInterval(poll);
                            overlay.querySelector(".regen-status").textContent = "Done!";
                            setTimeout(function() { window.location.reload(); }, 500);
                        } else if (t.state === "FAILURE") {
                            clearInterval(poll);
                            overlay.querySelector(".regen-status").textContent = "Failed: " + (t.error || "unknown");
                            btn.textContent = "Regenerate"; btn.disabled = false;
                        }
                    });
            }, 3000);
        })
        .catch(function(err) {
            overlay.remove();
            btn.textContent = "Regenerate"; btn.disabled = false;
        });
}

/* Auto-sync full_script from section fields (hook, problem, proof, cta) */
document.addEventListener("DOMContentLoaded", function() {
    var sectionFields = ["script_hook", "script_problem", "script_proof", "script_cta"];
    var fullScriptEl = document.querySelector('textarea[name="script_full_script"]');
    if (!fullScriptEl) return;

    var sectionEls = sectionFields.map(function(name) {
        return document.querySelector('textarea[name="' + name + '"]');
    }).filter(Boolean);

    if (sectionEls.length === 0) return;

    function syncFullScript() {
        var parts = sectionEls.map(function(el) { return el.value.trim(); }).filter(Boolean);
        fullScriptEl.value = parts.join("\n\n");
    }

    sectionEls.forEach(function(el) {
        el.addEventListener("input", syncFullScript);
    });
});

/* Global regen progress bar helpers */
function showRegenProgress(label) {
    var el = document.getElementById("regen-progress");
    if (!el) return;
    el.style.display = "";
    var labelEl = document.getElementById("regen-label");
    if (labelEl) labelEl.textContent = label || "Regenerating...";
}
function hideRegenProgress() {
    var el = document.getElementById("regen-progress");
    if (el) el.style.display = "none";
}

/* Trigger file picker for B-Roll image upload */
function triggerBrollUpload(jobId, shotIndex) {
    var input = document.createElement("input");
    input.type = "file";
    input.accept = "image/*";
    input.onchange = function () {
        if (!input.files || !input.files[0]) return;
        var cards = document.querySelectorAll('.scene-image-card[data-scene-type="broll"]');
        var card = cards[shotIndex] || null;
        var overlay = showUploadOverlay(card, "Uploading…");
        var fd = new FormData();
        fd.append("file", input.files[0]);
        fd.append("shot_index", shotIndex);
        fetch("/ui/ugc/" + jobId + "/upload-broll-image", {
            method: "POST", body: fd, redirect: "manual"
        }).then(function () {
            window.location.reload();
        }).catch(function (err) {
            hideUploadOverlay(overlay);
            alert("Upload failed: " + err.message);
        });
    };
    input.click();
}

/* Save active form edits, then advance (with optional rewind via from_stage) */
function saveAndAdvance(jobId, fromStage) {
    var savePromise = Promise.resolve();

    // Save analysis form if present
    var analysisForm = document.querySelector('form[action$="/update-analysis"]');
    if (analysisForm) {
        savePromise = fetch(analysisForm.action, {
            method: "POST", body: new FormData(analysisForm), redirect: "manual"
        });
    }
    // Save script form if present
    var scriptForm = document.querySelector('form[action$="/update-script"]');
    if (scriptForm) {
        savePromise = fetch(scriptForm.action, {
            method: "POST", body: new FormData(scriptForm), redirect: "manual"
        });
    }

    savePromise.then(function() {
        var fd = new FormData();
        fd.append("from_stage", fromStage);
        // Global "skip all" checkbox
        var skipCb = document.querySelector('.skip-video-gen-cb:checked');
        if (skipCb) fd.append("skip_video_gen", "true");
        // Per-image skip checkboxes
        var skipItems = document.querySelectorAll('.skip-video-item-cb:checked');
        if (skipItems.length && !skipCb) {
            var indices = Array.from(skipItems).map(function(cb) { return cb.dataset.clipIndex; });
            fd.append("skip_video_indices", indices.join(","));
        }
        return fetch("/ui/ugc/" + jobId + "/advance", {
            method: "POST", body: fd
        });
    }).then(function(r) {
        if (r.ok) {
            var redirect = r.headers.get("X-Redirect");
            window.location.href = redirect || ("/ui/ugc/" + jobId + "/review");
        } else {
            r.text().then(function(t) { alert("Advance failed"); });
        }
    }).catch(function(err) {
        alert("Error: " + err.message);
    });
}

/* Deploy LP — sends POST to /ui/deploy/{run_id}, shows deployed URL or error */
async function deployLP(runId) {
    const btn = document.getElementById("deploy-btn");
    const result = document.getElementById("deploy-result");
    btn.disabled = true;
    btn.textContent = "Deploying...";

    try {
        const resp = await fetch("/ui/deploy/" + runId, { method: "POST" });
        const data = await resp.json();
        if (data.status === "deployed") {
            // Show deployed URL as clickable link
            if (result) {
                result.innerHTML = 'Deployed! <a href="' + data.url + '" target="_blank">' + data.url + '</a>';
                result.style.display = "block";
                result.style.color = "";
            }
            // Update #deployed-url element if present
            const deployedUrl = document.getElementById("deployed-url");
            if (deployedUrl && data.url) {
                deployedUrl.innerHTML = '<span class="deployed-label">Live at:</span> <a href="' + data.url + '" target="_blank">' + data.url + '</a>';
                deployedUrl.style.display = "block";
            }
            btn.textContent = "Re-deploy";
        } else {
            // Show error message in red
            if (result) {
                result.textContent = data.message || "Deploy failed";
                result.style.display = "block";
                result.style.color = "#c0392b";
            }
            btn.textContent = "Deploy to Cloudflare";
        }
    } catch (err) {
        if (result) {
            result.textContent = "Error: " + err.message;
            result.style.display = "block";
            result.style.color = "#c0392b";
        }
        btn.textContent = "Deploy to Cloudflare";
    }
    btn.disabled = false;
}

// ---- Video Trim Tool ----
// Ranges to cut: [{start, end}, ...] — each is a time range in seconds
var _trimRanges = [];
var _dragState = null; // {startTime} while dragging

function _initTrimTool() {
    var video = document.getElementById('trim-video');
    var timeline = document.getElementById('trim-timeline');
    var playhead = document.getElementById('trim-playhead');
    var durLabel = document.getElementById('trim-duration-label');
    if (!video || !timeline) return;

    video.addEventListener('loadedmetadata', function() {
        durLabel.textContent = _fmtTime(video.duration);
    });

    video.addEventListener('timeupdate', function() {
        if (!video.duration) return;
        playhead.style.left = (video.currentTime / video.duration) * 100 + '%';
    });

    // Drag to select a range
    timeline.addEventListener('mousedown', function(e) {
        if (!video.duration) return;
        e.preventDefault();
        var t = _timeFromEvent(e, timeline, video.duration);
        _dragState = {startTime: t};
        // Show live preview
        _showDragPreview(timeline, t, t, video.duration);
    });

    document.addEventListener('mousemove', function(e) {
        if (!_dragState || !video.duration) return;
        var rect = timeline.getBoundingClientRect();
        var pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
        var t = pct * video.duration;
        _showDragPreview(timeline, _dragState.startTime, t, video.duration);
    });

    document.addEventListener('mouseup', function(e) {
        if (!_dragState || !video.duration) return;
        var rect = timeline.getBoundingClientRect();
        var pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
        var endTime = pct * video.duration;
        var s = Math.min(_dragState.startTime, endTime);
        var en = Math.max(_dragState.startTime, endTime);
        // Remove drag preview
        var preview = timeline.querySelector('.trim-drag-preview');
        if (preview) preview.remove();
        _dragState = null;
        // Minimum 0.1s selection
        if (en - s < 0.1) return;
        _addRange(Math.round(s * 10) / 10, Math.round(en * 10) / 10);
    });
}

function _timeFromEvent(e, timeline, duration) {
    var rect = timeline.getBoundingClientRect();
    var pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    return pct * duration;
}

function _showDragPreview(timeline, t1, t2, duration) {
    var preview = timeline.querySelector('.trim-drag-preview');
    if (!preview) {
        preview = document.createElement('div');
        preview.className = 'trim-drag-preview';
        timeline.appendChild(preview);
    }
    var s = Math.min(t1, t2), en = Math.max(t1, t2);
    preview.style.left = (s / duration) * 100 + '%';
    preview.style.width = ((en - s) / duration) * 100 + '%';
}

function _fmtTime(s) {
    var m = Math.floor(s / 60);
    var sec = Math.floor(s % 60);
    var ms = Math.round((s % 1) * 10);
    return m + ':' + (sec < 10 ? '0' : '') + sec + '.' + ms;
}

function _addRange(start, end) {
    // Merge with existing overlapping ranges
    _trimRanges.push({start: start, end: end});
    _trimRanges.sort(function(a, b) { return a.start - b.start; });
    // Merge overlapping
    var merged = [_trimRanges[0]];
    for (var i = 1; i < _trimRanges.length; i++) {
        var last = merged[merged.length - 1];
        if (_trimRanges[i].start <= last.end) {
            last.end = Math.max(last.end, _trimRanges[i].end);
        } else {
            merged.push(_trimRanges[i]);
        }
    }
    _trimRanges = merged;
    _renderCuts();
}

function clearAllCuts() {
    _trimRanges = [];
    _renderCuts();
}

function _renderCuts() {
    var timeline = document.getElementById('trim-timeline');
    var video = document.getElementById('trim-video');
    var applyBtn = document.getElementById('apply-cuts-btn');
    if (!timeline || !video) return;

    timeline.querySelectorAll('.trim-cut-marker').forEach(function(el) { el.remove(); });

    var dur = video.duration || 1;
    var totalCut = 0;
    _trimRanges.forEach(function(r, idx) {
        var leftPct = (r.start / dur) * 100;
        var widthPct = ((r.end - r.start) / dur) * 100;
        totalCut += r.end - r.start;

        var marker = document.createElement('div');
        marker.className = 'trim-cut-marker';
        marker.style.left = leftPct + '%';
        marker.style.width = widthPct + '%';
        marker.title = _fmtTime(r.start) + ' – ' + _fmtTime(r.end) + ' (click to remove)';
        marker.innerHTML = '<span class="trim-cut-label">' + _fmtTime(r.start) + '–' + _fmtTime(r.end) + '</span>';
        marker.addEventListener('click', function(e) {
            e.stopPropagation();
            _trimRanges.splice(idx, 1);
            _renderCuts();
        });
        timeline.appendChild(marker);
    });

    applyBtn.disabled = _trimRanges.length === 0;
    var status = document.getElementById('trim-status');
    if (status) {
        if (_trimRanges.length) {
            status.textContent = _trimRanges.length + ' region(s), ' + totalCut.toFixed(1) + 's to cut';
        } else {
            status.textContent = '';
        }
    }
}

async function applyCuts(jobId) {
    if (_trimRanges.length === 0) return;
    var btn = document.getElementById('apply-cuts-btn');
    var status = document.getElementById('trim-status');
    btn.disabled = true;
    btn.textContent = 'Trimming...';
    if (status) status.textContent = 'Processing...';

    try {
        var resp = await fetch('/ui/ugc/' + jobId + '/trim-video', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ranges: _trimRanges})
        });
        if (!resp.ok) {
            var err = await resp.json();
            throw new Error(err.detail || 'Trim failed');
        }
        var data = await resp.json();
        var video = document.getElementById('trim-video');
        video.src = data.video_path;
        video.load();
        _trimRanges = [];
        _renderCuts();
        if (status) status.textContent = 'Trimmed successfully!';
        btn.textContent = 'Apply Cuts';
        var undoBtn = document.getElementById('undo-trim-btn');
        if (undoBtn) undoBtn.style.display = '';
    } catch (err) {
        if (status) { status.textContent = 'Error: ' + err.message; status.style.color = '#c0392b'; }
        btn.textContent = 'Apply Cuts';
        btn.disabled = false;
    }
}

async function undoTrim(jobId) {
    var btn = document.getElementById('undo-trim-btn');
    var status = document.getElementById('trim-status');
    btn.disabled = true;
    btn.textContent = 'Restoring...';

    try {
        var resp = await fetch('/ui/ugc/' + jobId + '/undo-trim', {method: 'POST'});
        if (!resp.ok) {
            var err = await resp.json();
            throw new Error(err.detail || 'Undo failed');
        }
        var data = await resp.json();
        var video = document.getElementById('trim-video');
        video.src = data.video_path;
        video.load();
        _trimRanges = [];
        _renderCuts();
        if (status) status.textContent = 'Restored previous version';
        if (!data.has_previous) btn.style.display = 'none';
        btn.textContent = 'Undo Trim';
        btn.disabled = false;
    } catch (err) {
        if (status) { status.textContent = 'Error: ' + err.message; status.style.color = '#c0392b'; }
        btn.textContent = 'Undo Trim';
        btn.disabled = false;
    }
}

// Init trim tool on page load
document.addEventListener('DOMContentLoaded', _initTrimTool);

/* Show skeleton placeholders during regen operations */
function showSkeletons(containerSelector, count) {
    var container = document.querySelector(containerSelector);
    if (!container) return;
    count = count || 3;
    container.innerHTML = '';
    for (var i = 0; i < count; i++) {
        var skel = document.createElement('div');
        skel.className = 'stage-card';
        skel.innerHTML = '<div class="skeleton skeleton-image"></div>'
            + '<div class="skeleton skeleton-text" style="margin-top:10px"></div>'
            + '<div class="skeleton skeleton-text"></div>';
        container.appendChild(skel);
    }
}

// Select a previous image from history
async function selectHistoryImage(jobId, sceneType, sceneIndex, historyIndex) {
    const thumb = event.target;
    thumb.style.border = "2px solid var(--primary)";
    thumb.style.opacity = "1";

    const fd = new FormData();
    fd.append("scene_type", sceneType);
    fd.append("scene_index", sceneIndex);
    fd.append("history_index", historyIndex);

    const resp = await fetch(`/ui/ugc/${jobId}/select-history-image`, {
        method: "POST", body: fd
    });
    if (resp.ok) {
        location.reload();
    } else {
        thumb.style.border = "2px solid #c0392b";
        const err = await resp.json();
        alert("Failed: " + (err.detail || "unknown error"));
    }
}


/* ---- Section Image Editor (Preview LP page) ---- */

async function regenSectionImage(runId, section, index, btn) {
    var card = document.getElementById("si-card-" + section + "-" + index);
    if (!card) return;
    btn.disabled = true;

    // Show spinner overlay
    var overlay = card.querySelector(".regen-overlay");
    overlay.style.display = "flex";

    // Get current image URL to detect change
    var img = card.querySelector(".section-image-preview");
    var oldUrl = img ? img.src : "";

    // Trigger regen task
    var fd = new FormData();
    fd.append("section", section);
    fd.append("index", index);

    try {
        var resp = await fetch("/ui/lp/" + runId + "/regen-section-image", { method: "POST", body: fd });
        var data = await resp.json();
        if (!data.task_id) throw new Error("No task_id returned");

        // Poll until image changes
        var attempts = 0;
        var poll = setInterval(async function() {
            attempts++;
            if (attempts > 90) { // 3 min max
                clearInterval(poll);
                overlay.style.display = "none";
                btn.disabled = false;
                return;
            }

            // Check task status for early failure
            var statusResp = await fetch("/ui/ugc/task-status/" + data.task_id);
            var statusData = await statusResp.json();
            if (statusData.state === "FAILURE") {
                clearInterval(poll);
                overlay.querySelector(".regen-status").textContent = "Failed";
                setTimeout(function() { overlay.style.display = "none"; btn.disabled = false; }, 2000);
                return;
            }

            // Check if image value changed
            var valResp = await fetch("/ui/lp/" + runId + "/section-image-value?section=" + section + "&index=" + index);
            var valData = await valResp.json();
            if (valData.image_url && valData.image_url !== oldUrl) {
                clearInterval(poll);
                // Update image in place
                if (img) {
                    img.src = valData.image_url + "?t=" + Date.now();
                } else {
                    // Replace placeholder with img
                    var placeholder = card.querySelector(".section-image-placeholder");
                    if (placeholder) {
                        var newImg = document.createElement("img");
                        newImg.className = "section-image-preview";
                        newImg.src = valData.image_url + "?t=" + Date.now();
                        placeholder.replaceWith(newImg);
                    }
                }
                overlay.style.display = "none";
                btn.disabled = false;
            }
        }, 2000);
    } catch (e) {
        overlay.querySelector(".regen-status").textContent = "Error: " + e.message;
        setTimeout(function() { overlay.style.display = "none"; btn.disabled = false; }, 2000);
    }
}


function uploadSectionImage(runId, section, index) {
    var input = document.createElement("input");
    input.type = "file";
    input.accept = "image/*";
    input.onchange = function () {
        if (!input.files || !input.files[0]) return;
        var card = document.getElementById("si-card-" + section + "-" + index);
        var overlay = showUploadOverlay(card, "Uploading…");
        var fd = new FormData();
        fd.append("file", input.files[0]);
        fd.append("section", section);
        fd.append("index", index);
        fetch("/ui/lp/" + runId + "/upload-section-image", {
            method: "POST", body: fd
        }).then(function (resp) {
            return resp.json();
        }).then(function (data) {
            hideUploadOverlay(overlay);
            if (!data.image_url) throw new Error("No image_url returned");
            var img = card ? card.querySelector(".section-image-preview") : null;
            if (img) {
                img.src = data.image_url + "?t=" + Date.now();
            } else if (card) {
                var placeholder = card.querySelector(".section-image-placeholder");
                if (placeholder) {
                    var newImg = document.createElement("img");
                    newImg.className = "section-image-preview";
                    newImg.src = data.image_url + "?t=" + Date.now();
                    placeholder.replaceWith(newImg);
                }
            }
        }).catch(function (err) {
            hideUploadOverlay(overlay);
            alert("Upload failed: " + err.message);
        });
    };
    input.click();
}


async function rebuildLP(runId, btn) {
    btn.disabled = true;
    btn.textContent = "Rebuilding...";

    try {
        var resp = await fetch("/ui/lp/" + runId + "/rebuild-html-ajax", { method: "POST" });
        var data = await resp.json();
        if (data.status === "ok") {
            // Refresh iframe with cache-bust
            var iframe = document.getElementById("lp-iframe");
            if (iframe) {
                iframe.src = "/output/" + runId + "/landing-page.html?t=" + Date.now();
            }
            btn.textContent = "Done!";
            setTimeout(function() { btn.textContent = "Rebuild LP"; btn.disabled = false; }, 1500);
            return;
        }
    } catch (e) {
        console.error("Rebuild failed:", e);
    }

    btn.textContent = "Rebuild LP";
    btn.disabled = false;
}


async function generateAllSectionImages(runId, btn) {
    btn.disabled = true;
    btn.textContent = "Generating...";

    try {
        var resp = await fetch("/ui/lp/" + runId + "/generate-section-images", { method: "POST" });
        var data = await resp.json();
        if (!data.task_id) throw new Error("No task_id");

        // Poll task status until done
        var poll = setInterval(async function() {
            var statusResp = await fetch("/ui/ugc/task-status/" + data.task_id);
            var statusData = await statusResp.json();

            if (statusData.state === "SUCCESS") {
                clearInterval(poll);
                location.reload();
            } else if (statusData.state === "FAILURE") {
                clearInterval(poll);
                btn.textContent = "Failed — retry?";
                btn.disabled = false;
            }
        }, 3000);
    } catch (e) {
        btn.textContent = "Error — retry?";
        btn.disabled = false;
    }
}

/* Select a previous video from history */
function selectHistoryVideo(jobId, sceneType, clipIndex, historyIndex) {
    var fd = new FormData();
    fd.append("scene_type", sceneType);
    fd.append("clip_index", clipIndex);
    fd.append("history_index", historyIndex);
    fetch("/ui/ugc/" + jobId + "/select-history-video", {
        method: "POST", body: fd
    }).then(function(r) {
        if (r.ok) window.location.reload();
        else r.text().then(function(t) { alert("Failed: " + t); });
    });
}

/* Toggle all per-image skip checkboxes when the global "skip all" checkbox changes */
function toggleAllSkipItems(globalCb) {
    var section = globalCb.closest('.stage-section');
    if (!section) return;
    var items = section.querySelectorAll('.skip-video-item-cb');
    items.forEach(function(cb) { cb.checked = globalCb.checked; });
}

/* ── Bulk Delete ── */

// Select-all toggle
function toggleSelectAll(masterCb) {
    document.querySelectorAll('.row-cb').forEach(function(cb) { cb.checked = masterCb.checked; });
    updateBulkBar();
}

// Show/hide bulk bar and update count
function updateBulkBar() {
    var checked = document.querySelectorAll('.row-cb:checked');
    var bar = document.getElementById('bulkBar');
    if (!bar) return;
    bar.style.display = checked.length ? 'flex' : 'none';
    document.getElementById('bulkCount').textContent = checked.length;
}

// Confirm + POST delete
function bulkDelete() {
    var ids = Array.from(document.querySelectorAll('.row-cb:checked')).map(function(cb) { return cb.value; });
    if (!ids.length) return;
    if (!confirm('Delete ' + ids.length + ' item(s)? This cannot be undone.')) return;
    var fd = new FormData();
    fd.append('ids', ids.join(','));
    fetch(BULK_DELETE_URL, { method: 'POST', body: fd })
        .then(function(r) { if (r.redirected) { window.location.href = r.url; } else if (r.ok) { window.location.reload(); } else { r.text().then(function(t) { alert('Delete failed: ' + t); }); } });
}

/* Upload a video file to a specific clip slot */
function uploadVideo(jobId, sceneType, clipIndex, input) {
    var file = input.files[0];
    if (!file) return;
    var card = input.closest(".stage-card, .media-card");
    var overlay = showUploadOverlay(card, "Uploading & processing…");
    var fd = new FormData();
    fd.append("file", file);
    fd.append("scene_type", sceneType);
    fd.append("clip_index", clipIndex);
    fetch("/ui/ugc/" + jobId + "/upload-video", {
        method: "POST",
        body: fd
    }).then(function(r) {
        if (r.ok) {
            window.location.reload();
        } else {
            hideUploadOverlay(overlay);
            r.text().then(function(t) { alert("Upload failed: " + t); });
        }
    }).catch(function(err) {
        hideUploadOverlay(overlay);
        alert("Upload failed: " + err.message);
    });
}
