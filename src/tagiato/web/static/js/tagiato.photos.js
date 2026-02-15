// Copy value from one photo's input to neighbor (up or down)
function copyValueToNeighbor(filename, fieldType, direction) {
    const currentIndex = photos.findIndex(p => p.filename === filename);
    if (currentIndex === -1) return;

    const neighborIndex = direction === 'up' ? currentIndex - 1 : currentIndex + 1;
    if (neighborIndex < 0 || neighborIndex >= photos.length) return;

    const neighborFilename = photos[neighborIndex].filename;

    // Get source value
    const sourceInput = document.getElementById(`${fieldType}-${filename}`);
    if (!sourceInput) return;

    const value = sourceInput.value;

    // Set target value
    const targetInput = document.getElementById(`${fieldType}-${neighborFilename}`);
    if (!targetInput) return;

    targetInput.value = value;

    // Trigger unsaved changes detection on the target photo
    targetInput.dispatchEvent(new Event('input', { bubbles: true }));

    // Visual feedback - briefly highlight the target input
    targetInput.classList.add('border-success');
    setTimeout(() => targetInput.classList.remove('border-success'), 500);
}

// Render copy arrows for an input field
function renderCopyArrows(filename, fieldType) {
    const currentIndex = photos.findIndex(p => p.filename === filename);
    const isFirst = currentIndex === 0;
    const isLast = currentIndex === photos.length - 1;

    const upArrow = isFirst ? '' :
        `<button type="button" class="copy-arrow-btn" onclick="copyValueToNeighbor('${filename}', '${fieldType}', 'up')" title="${t('photo.copy_up')}">↑</button>`;
    const downArrow = isLast ? '' :
        `<button type="button" class="copy-arrow-btn" onclick="copyValueToNeighbor('${filename}', '${fieldType}', 'down')" title="${t('photo.copy_down')}">↓</button>`;

    if (!upArrow && !downArrow) return '';

    return `<div class="copy-arrows">${upArrow}${downArrow}</div>`;
}

// Render photo card
function renderPhotoCard(photo) {
    const gpsStatus = photo.gps ? 'bi-check-circle-fill text-success' : 'bi-x-circle-fill text-danger';

    let aiStatus, aiBadge;
    if (photo.ai_empty_response) {
        aiStatus = 'bi-exclamation-circle-fill text-warning';
        aiBadge = `<span class="badge badge-warning">${t('photo.badge_unrecognized')}</span>`;
    } else if (photo.description) {
        aiStatus = 'bi-check-circle-fill text-success';
        aiBadge = '';
    } else {
        aiStatus = 'bi-x-circle-fill text-danger';
        aiBadge = '';
    }

    const gpsValue = photo.gps ? `${photo.gps.lat.toFixed(6)}, ${photo.gps.lng.toFixed(6)}` : '';

    const isSelected = selectedPhotos.has(photo.filename);

    let aiIndicator = '';
    if (photo.ai_status === 'processing') {
        aiIndicator = '<i class="bi bi-arrow-repeat status-processing ms-1"></i>';
    }

    let locateIndicator = '';
    if (photo.locate_status === 'processing') {
        locateIndicator = '<i class="bi bi-arrow-repeat status-processing ms-1"></i>';
    } else if (photo.locate_status === 'done' && photo.locate_confidence) {
        const confIcon = photo.locate_confidence === 'high' ? 'text-success' :
                        photo.locate_confidence === 'medium' ? 'text-warning' : 'text-secondary';
        locateIndicator = `<i class="bi bi-geo-alt-fill ${confIcon} ms-1" title="${t('photo.located_title', {confidence: t('confidence.' + photo.locate_confidence)})}"></i>`;
    }

    return `
        <div class="photo-card" data-filename="${photo.filename}">
            <div class="photo-card-header">
                <input type="checkbox" class="form-check-input photo-checkbox photo-select"
                       data-filename="${photo.filename}" ${isSelected ? 'checked' : ''}>
                <strong>${photo.filename}</strong>
                <span class="ms-auto">
                    <span class="me-2" title="GPS"><i class="bi ${gpsStatus} status-icon"></i> GPS${locateIndicator}</span>
                    <span title="AI"><i class="bi ${aiStatus} status-icon"></i> AI${aiIndicator}</span>
                    ${aiBadge}
                </span>
            </div>
            <div class="photo-card-body">
                <div class="photo-image-container">
                    <img src="/api/photos/${encodeURIComponent(photo.filename)}/thumbnail"
                         class="photo-image" alt="${photo.filename}"
                         loading="lazy">
                </div>
                <div class="photo-details">
                    <div class="mb-3">
                        <label class="form-label">${t('photo.gps_label')}</label>
                        <div class="input-with-arrows">
                            <div class="input-group">
                                <input type="text" class="form-control gps-input"
                                       id="gps-${photo.filename}" value="${gpsValue}"
                                       placeholder="${t('photo.gps_placeholder')}">
                                <button class="btn btn-outline-secondary map-btn"
                                        data-filename="${photo.filename}" title="${t('photo.map_btn_title')}">
                                    <i class="bi bi-map"></i>
                                </button>
                            </div>
                            ${renderCopyArrows(photo.filename, 'gps')}
                        </div>
                        <small class="text-muted">${t('photo.gps_source', {source: t('photo.gps_source_' + (photo.gps_source || 'none'))})}</small>
                    </div>

                    <div class="mb-3">
                        <label class="form-label">${t('photo.place_label')}</label>
                        <div class="input-with-arrows">
                            <input type="text" class="form-control location-input"
                                   id="loc-${photo.filename}" value="${photo.location_name || ''}"
                                   placeholder="${t('photo.place_placeholder')}">
                            ${renderCopyArrows(photo.filename, 'loc')}
                        </div>
                    </div>

                    <div class="mb-3">
                        <label class="form-label">${t('photo.description_label')}</label>
                        <div class="input-with-arrows">
                            <textarea class="form-control description-textarea"
                                      id="desc-${photo.filename}">${photo.description || ''}</textarea>
                            ${renderCopyArrows(photo.filename, 'desc')}
                        </div>
                    </div>

                    <div class="row g-2 mb-3">
                        <div class="col-6">
                            <label class="form-label small text-muted">${t('photo.locate_hint_label')}</label>
                            <div class="input-with-arrows">
                                <input type="text" class="form-control form-control-sm locate-hint-input"
                                       id="locate-hint-${photo.filename}"
                                       placeholder="${t('photo.locate_hint_placeholder')}">
                                ${renderCopyArrows(photo.filename, 'locate-hint')}
                            </div>
                        </div>
                        <div class="col-6">
                            <label class="form-label small text-muted">${t('photo.describe_hint_label')}</label>
                            <div class="input-with-arrows">
                                <input type="text" class="form-control form-control-sm describe-hint-input"
                                       id="describe-hint-${photo.filename}"
                                       placeholder="${t('photo.describe_hint_placeholder')}">
                                ${renderCopyArrows(photo.filename, 'describe-hint')}
                            </div>
                        </div>
                    </div>

                    <div class="d-flex gap-2 flex-wrap align-items-center">
                        <div class="d-flex align-items-center gap-1">
                            <div class="btn-group btn-group-sm">
                                <button class="btn btn-outline-secondary btn-locate"
                                        data-filename="${photo.filename}">
                                    <i class="bi bi-geo-alt me-1"></i>${t('photo.btn_locate')}
                                </button>
                                <button class="btn btn-outline-secondary btn-prompt-preview"
                                        data-filename="${photo.filename}" data-type="locate"
                                        title="${t('photo.btn_show_prompt')}">
                                    <i class="bi bi-code"></i>
                                </button>
                            </div>
                            <div class="form-check form-check-inline mb-0 ms-1">
                                <input class="form-check-input" type="checkbox"
                                       id="include-image-locate-${photo.filename}" checked
                                       title="${t('photo.include_image_title')}">
                                <label class="form-check-label small" for="include-image-locate-${photo.filename}">
                                    <i class="bi bi-image"></i>
                                </label>
                            </div>
                        </div>
                        <div class="d-flex align-items-center gap-1">
                            <div class="btn-group btn-group-sm">
                                <button class="btn btn-outline-primary btn-generate"
                                        data-filename="${photo.filename}">
                                    <i class="bi bi-stars me-1"></i>${t('photo.btn_generate')}
                                </button>
                                <button class="btn btn-outline-primary btn-prompt-preview"
                                        data-filename="${photo.filename}" data-type="describe"
                                        title="${t('photo.btn_show_prompt')}">
                                    <i class="bi bi-code"></i>
                                </button>
                            </div>
                            <div class="form-check form-check-inline mb-0 ms-1">
                                <input class="form-check-input" type="checkbox"
                                       id="include-image-describe-${photo.filename}" checked
                                       title="${t('photo.include_image_title')}">
                                <label class="form-check-label small" for="include-image-describe-${photo.filename}">
                                    <i class="bi bi-image"></i>
                                </label>
                            </div>
                        </div>
                        <button class="btn btn-outline-success btn-sm btn-save"
                                data-filename="${photo.filename}"
                                data-original-gps="${gpsValue}"
                                data-original-desc="${(photo.description || '').replace(/"/g, '&quot;')}"
                                data-original-loc="${(photo.location_name || '').replace(/"/g, '&quot;')}">
                            <i class="bi bi-check-lg me-1"></i>${t('photo.btn_save')}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
}

// Load and render photos
async function loadPhotos() {
    const filter = document.querySelector('input[name="filter"]:checked').value;
    const sort = document.querySelector('input[name="sort"]:checked').value;

    try {
        const response = await fetch(`/api/photos?filter=${filter}&sort=${sort}`);
        const data = await response.json();
        photos = data.photos;

        const container = document.getElementById('photosList');
        if (photos.length === 0) {
            container.innerHTML = `<div class="text-center py-5 text-muted">${t('photo.no_photos')}</div>`;
            return;
        }

        container.innerHTML = photos.map(renderPhotoCard).join('');
        updateSelectAllState();
    } catch (error) {
        console.error('Failed to load photos:', error);
        showToast(t('toast.photo_load_error'), 'error');
    }
}
