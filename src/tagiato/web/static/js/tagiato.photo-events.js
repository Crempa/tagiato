// Event delegation - handle all clicks on photosList container
document.getElementById('photosList').addEventListener('click', async (e) => {
    const btn = e.target.closest('button');
    if (!btn) return;

    const filename = btn.dataset.filename;
    if (!filename) return;

    // Locate button
    if (btn.classList.contains('btn-locate')) {
        btn.disabled = true;
        btn.innerHTML = `<i class="bi bi-arrow-repeat status-processing me-1"></i>${t('btn.searching')}`;

        try {
            const locateHint = document.getElementById(`locate-hint-${filename}`)?.value || '';
            const response = await fetch(`/api/photos/${encodeURIComponent(filename)}/locate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_hint: locateHint })
            });
            const data = await response.json();

            if (data.task_id) {
                // Async task - start polling
                pollTaskStatus(data.task_id, filename, 'locate', btn);
            } else {
                showToast(t('toast.locate_failed'), 'error');
                resetButton(btn, 'locate');
            }
        } catch (error) {
            showToast(t('toast.error', {message: error.message}), 'error');
            resetButton(btn, 'locate');
        }
        return;
    }

    // Generate AI button
    if (btn.classList.contains('btn-generate')) {
        btn.disabled = true;
        btn.innerHTML = `<i class="bi bi-arrow-repeat status-processing me-1"></i>${t('btn.generating')}`;

        try {
            const describeHint = document.getElementById(`describe-hint-${filename}`)?.value || '';
            const response = await fetch(`/api/photos/${encodeURIComponent(filename)}/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_hint: describeHint })
            });
            const data = await response.json();

            if (data.task_id) {
                // Async task - start polling
                pollTaskStatus(data.task_id, filename, 'describe', btn);
            } else {
                showToast(t('toast.generate_failed'), 'error');
                resetButton(btn, 'describe');
            }
        } catch (error) {
            showToast(t('toast.error', {message: error.message}), 'error');
            resetButton(btn, 'describe');
        }
        return;
    }

    // Save button
    if (btn.classList.contains('btn-save')) {
        const gpsInput = document.getElementById(`gps-${filename}`);
        const descInput = document.getElementById(`desc-${filename}`);
        const locInput = document.getElementById(`loc-${filename}`);

        const payload = {
            description: descInput.value,
            location_name: locInput.value || null
        };

        // Parse GPS if provided
        const gpsValue = gpsInput.value.trim();
        if (gpsValue) {
            const parts = gpsValue.split(',').map(s => parseFloat(s.trim()));
            if (parts.length === 2 && !isNaN(parts[0]) && !isNaN(parts[1])) {
                payload.gps = { lat: parts[0], lng: parts[1] };
            }
        }

        btn.disabled = true;
        try {
            const response = await fetch(`/api/photos/${encodeURIComponent(filename)}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                showToast(t('toast.saved_exif'));

                // Update original values in data attributes
                btn.dataset.originalGps = gpsInput.value;
                btn.dataset.originalDesc = descInput.value;
                btn.dataset.originalLoc = locInput.value;

                // Reset button appearance
                btn.classList.remove('btn-warning');
                btn.classList.add('btn-outline-success');
                btn.innerHTML = `<i class="bi bi-check-lg me-1"></i>${t('photo.btn_save')}`;

                // Update in-memory photo state for context
                const photo = photos.find(p => p.filename === filename);
                if (photo) {
                    photo.description = descInput.value;
                    photo.location_name = locInput.value;
                    if (payload.gps) {
                        photo.gps = payload.gps;
                    }
                }
            } else {
                const error = await response.json();
                showToast(t('toast.error', {message: error.detail}), 'error');
            }
        } catch (error) {
            showToast(t('toast.error', {message: error.message}), 'error');
        }

        btn.disabled = false;
        return;
    }

    // Map button
    if (btn.classList.contains('map-btn')) {
        openMapModal(filename);
        return;
    }

    // Prompt preview button
    if (btn.classList.contains('btn-prompt-preview')) {
        const promptType = btn.dataset.type;
        showPromptPreview(filename, promptType);
        return;
    }
});

// Event delegation for checkboxes
document.getElementById('photosList').addEventListener('change', (e) => {
    if (e.target.classList.contains('photo-select')) {
        const filename = e.target.dataset.filename;
        if (e.target.checked) {
            selectedPhotos.add(filename);
        } else {
            selectedPhotos.delete(filename);
        }
        updateProcessSelectedButton();
        updateSelectAllState();
    }
});

// Event delegation for input changes (detect unsaved changes)
document.getElementById('photosList').addEventListener('input', (e) => {
    const target = e.target;
    if (target.classList.contains('gps-input') ||
        target.classList.contains('description-textarea') ||
        target.classList.contains('location-input')) {

        // Extract filename from input ID
        const idParts = target.id.split('-');
        const filename = idParts.slice(1).join('-'); // Handle filenames with dashes
        checkUnsavedChanges(filename);
    }
});
