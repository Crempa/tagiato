// Batch processing - Descriptions
document.getElementById('btnDescribeAll').addEventListener('click', async (e) => {
    e.preventDefault();
    await startBatch(null, 'describe');
});

document.getElementById('btnDescribeSelected').addEventListener('click', async (e) => {
    e.preventDefault();
    if (selectedPhotos.size === 0) {
        showToast(t('toast.no_photos_selected'), 'warning');
        return;
    }
    await startBatch(Array.from(selectedPhotos), 'describe');
});

// Batch processing - Locate
document.getElementById('btnLocateAll').addEventListener('click', async (e) => {
    e.preventDefault();
    await startBatch(null, 'locate');
});

document.getElementById('btnLocateSelected').addEventListener('click', async (e) => {
    e.preventDefault();
    if (selectedPhotos.size === 0) {
        showToast(t('toast.no_photos_selected'), 'warning');
        return;
    }
    await startBatch(Array.from(selectedPhotos), 'locate');
});

// Save all
document.getElementById('btnSaveAll').addEventListener('click', async (e) => {
    e.preventDefault();
    await savePhotos(null);
});

document.getElementById('btnSaveSelected').addEventListener('click', async (e) => {
    e.preventDefault();
    if (selectedPhotos.size === 0) {
        showToast(t('toast.no_photos_selected'), 'warning');
        return;
    }
    await savePhotos(Array.from(selectedPhotos));
});

async function savePhotos(photosList) {
    try {
        const response = await fetch('/api/photos/save-all', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ photos: photosList })
        });

        const data = await response.json();

        if (data.success) {
            showToast(t('toast.saved_count', {saved: data.saved, total: data.total}));
            if (data.errors && data.errors.length > 0) {
                console.error('Save errors:', data.errors);
            }
            await loadPhotos();
        } else {
            showToast(t('toast.save_failed'), 'error');
        }
    } catch (error) {
        showToast(t('toast.error', {message: error.message}), 'error');
    }
}

document.getElementById('btnStop').addEventListener('click', async () => {
    try {
        await fetch('/api/batch/stop', { method: 'POST' });
        showToast(t('toast.stopping'));
    } catch (error) {
        showToast(t('toast.error', {message: error.message}), 'error');
    }
});

async function startBatch(photosList, operation = 'describe') {
    try {
        const response = await fetch('/api/batch/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ photos: photosList, operation: operation })
        });

        if (!response.ok) {
            const error = await response.json();
            showToast(error.detail, 'error');
            return;
        }

        document.getElementById('btnDescribeDropdown').classList.add('d-none');
        document.getElementById('btnLocateDropdown').classList.add('d-none');
        document.getElementById('btnSaveDropdown').classList.add('d-none');
        document.getElementById('btnStop').classList.remove('d-none');
        document.getElementById('batchStatus').classList.add('active');
        updatePromptsButtonState(true);

        pollBatchStatus();
    } catch (error) {
        showToast(t('toast.error', {message: error.message}), 'error');
    }
}

async function pollBatchStatus() {
    try {
        const response = await fetch('/api/batch/status');
        const status = await response.json();

        const opLabel = status.operation === 'locate' ? t('batch.locate') : t('batch.descriptions');
        document.getElementById('batchStatusText').textContent =
            t('batch.status', {operation: opLabel, completed: status.completed_count, queued: status.queue_count});

        if (status.is_running) {
            // Refresh photos to show current status
            await loadPhotos();
            setTimeout(pollBatchStatus, 1000);
        } else {
            // Batch finished
            document.getElementById('btnDescribeDropdown').classList.remove('d-none');
            document.getElementById('btnLocateDropdown').classList.remove('d-none');
            document.getElementById('btnSaveDropdown').classList.remove('d-none');
            document.getElementById('btnStop').classList.add('d-none');
            document.getElementById('batchStatus').classList.remove('active');
            updatePromptsButtonState(false);
            showToast(t('toast.batch_complete'));
            await loadPhotos();
        }
    } catch (error) {
        console.error('Poll error:', error);
    }
}
