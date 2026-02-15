// Poll task status until done
async function pollTaskStatus(taskId, filename, operation, btn) {
    const pollInterval = 500; // ms

    async function poll() {
        try {
            const response = await fetch(`/api/tasks/${taskId}`);
            const task = await response.json();

            if (task.status === 'running' || task.status === 'pending') {
                setTimeout(poll, pollInterval);
                return;
            }

            if (task.status === 'done') {
                const result = task.result;

                if (operation === 'describe') {
                    // Reset checkbox to default (checked)
                    const describeCheckbox = document.getElementById(`include-image-describe-${filename}`);
                    if (describeCheckbox) describeCheckbox.checked = true;

                    if (result.empty) {
                        updatePhotoInUI(filename, { ai_status: 'done', ai_empty_response: true });
                        showToast(t('toast.ai_unrecognized_content'), 'warning');
                    } else {
                        updatePhotoInUI(filename, {
                            description: result.description,
                            ai_status: 'done',
                            ai_empty_response: false
                        });
                        showToast(t('toast.description_generated'));
                    }
                } else if (operation === 'locate') {
                    // Reset checkbox to default (checked)
                    const locateCheckbox = document.getElementById(`include-image-locate-${filename}`);
                    if (locateCheckbox) locateCheckbox.checked = true;

                    if (result.gps) {
                        const confidenceText = t('confidence.' + result.confidence);
                        showToast(t('toast.located', {location: result.location_name || '?', confidence: confidenceText}));

                        updatePhotoInUI(filename, {
                            gps: result.gps,
                            gps_source: 'ai',
                            locate_status: 'done',
                            locate_confidence: result.confidence,
                            location_name: result.location_name
                        });
                    } else if (result.location_name) {
                        showToast(t('toast.located_no_coords', {location: result.location_name}), 'warning');
                        updatePhotoInUI(filename, {
                            locate_status: 'done',
                            locate_confidence: result.confidence,
                            location_name: result.location_name
                        });
                    } else {
                        showToast(t('toast.ai_unrecognized_place'), 'warning');
                        resetButton(btn, operation);
                        return;
                    }
                }
            } else if (task.status === 'error') {
                showToast(t('toast.error', {message: task.error}), 'error');
                resetButton(btn, operation);
                return;
            }
        } catch (error) {
            showToast(t('toast.status_check_error', {message: error.message}), 'error');
            resetButton(btn, operation);
        }
    }

    poll();
}

function resetButton(btn, operation) {
    btn.disabled = false;
    if (operation === 'describe') {
        btn.innerHTML = `<i class="bi bi-stars me-1"></i>${t('photo.btn_generate')}`;
    } else {
        btn.innerHTML = `<i class="bi bi-geo-alt me-1"></i>${t('photo.btn_locate')}`;
    }
}
