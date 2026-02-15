// Update single photo in UI - preserves manually edited values and original data-original-* attributes
function updatePhotoInUI(filename, updatedData) {
    const photo = photos.find(p => p.filename === filename);
    if (!photo) return;

    // Capture manually edited values from DOM before re-rendering
    const gpsInput = document.getElementById(`gps-${filename}`);
    const descInput = document.getElementById(`desc-${filename}`);
    const locInput = document.getElementById(`loc-${filename}`);
    const saveBtn = document.querySelector(`.btn-save[data-filename="${filename}"]`);

    const userEdits = {
        gps: gpsInput?.value,
        description: descInput?.value,
        location_name: locInput?.value,
    };

    // Capture original values from data attributes (for unsaved changes detection)
    const originalValues = {
        gps: saveBtn?.dataset.originalGps || '',
        desc: saveBtn?.dataset.originalDesc || '',
        loc: saveBtn?.dataset.originalLoc || '',
    };

    // Merge new data into object
    Object.assign(photo, updatedData);

    // Re-render the card
    const card = document.querySelector(`.photo-card[data-filename="${filename}"]`);
    if (card) {
        card.outerHTML = renderPhotoCard(photo);
    }

    // Restore manually edited values (if updatedData doesn't contain these fields)
    const newGpsInput = document.getElementById(`gps-${filename}`);
    const newDescInput = document.getElementById(`desc-${filename}`);
    const newLocInput = document.getElementById(`loc-${filename}`);
    const newSaveBtn = document.querySelector(`.btn-save[data-filename="${filename}"]`);

    // Restore GPS if user edited and updatedData doesn't contain new gps
    if (newGpsInput && userEdits.gps && !updatedData.gps) {
        newGpsInput.value = userEdits.gps;
    }
    // Restore description if user edited and updatedData doesn't contain description
    if (newDescInput && userEdits.description && !('description' in updatedData)) {
        newDescInput.value = userEdits.description;
    }
    // Restore location_name if user edited and updatedData doesn't contain location_name
    if (newLocInput && userEdits.location_name && !('location_name' in updatedData)) {
        newLocInput.value = userEdits.location_name;
    }

    // Restore original values in data attributes (for correct unsaved changes detection)
    if (newSaveBtn) {
        newSaveBtn.dataset.originalGps = originalValues.gps;
        newSaveBtn.dataset.originalDesc = originalValues.desc;
        newSaveBtn.dataset.originalLoc = originalValues.loc;
    }

    // Check and update Save button appearance
    checkUnsavedChanges(filename);
}

// Check if photo has unsaved changes and update save button appearance
function checkUnsavedChanges(filename) {
    const saveBtn = document.querySelector(`.btn-save[data-filename="${filename}"]`);
    if (!saveBtn) return;

    const gpsInput = document.getElementById(`gps-${filename}`);
    const descInput = document.getElementById(`desc-${filename}`);
    const locInput = document.getElementById(`loc-${filename}`);

    const originalGps = saveBtn.dataset.originalGps || '';
    const originalDesc = saveBtn.dataset.originalDesc || '';
    const originalLoc = saveBtn.dataset.originalLoc || '';

    const currentGps = gpsInput?.value || '';
    const currentDesc = descInput?.value || '';
    const currentLoc = locInput?.value || '';

    const hasChanges = currentGps !== originalGps ||
                       currentDesc !== originalDesc ||
                       currentLoc !== originalLoc;

    if (hasChanges) {
        saveBtn.classList.remove('btn-outline-success');
        saveBtn.classList.add('btn-warning');
        saveBtn.innerHTML = `<i class="bi bi-exclamation-circle me-1"></i>${t('photo.btn_save_changes')}`;
    } else {
        saveBtn.classList.remove('btn-warning');
        saveBtn.classList.add('btn-outline-success');
        saveBtn.innerHTML = `<i class="bi bi-check-lg me-1"></i>${t('photo.btn_save')}`;
    }
}
