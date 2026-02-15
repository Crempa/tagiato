// --- Prompt Preview ---
async function showPromptPreview(filename, promptType) {
    // Get user hint based on prompt type
    let userHint = '';
    if (promptType === 'locate') {
        userHint = document.getElementById(`locate-hint-${filename}`)?.value || '';
    } else {
        userHint = document.getElementById(`describe-hint-${filename}`)?.value || '';
    }

    // Get include_image checkbox state based on prompt type
    const checkboxId = promptType === 'locate'
        ? `include-image-locate-${filename}`
        : `include-image-describe-${filename}`;
    const includeImageCheckbox = document.getElementById(checkboxId);
    const includeImage = includeImageCheckbox ? includeImageCheckbox.checked : true;

    try {
        const response = await fetch(`/api/photos/${encodeURIComponent(filename)}/prompt-preview`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: promptType, user_hint: userHint, include_image: includeImage })
        });

        if (!response.ok) {
            throw new Error(t('toast.prompt_load_error'));
        }

        const data = await response.json();

        // Update modal title
        const title = promptType === 'locate' ? t('preview.title_locate') : t('preview.title_describe');
        const imageIndicator = includeImage ? ' ' + t('preview.with_image') : ' ' + t('preview.without_image');
        document.getElementById('promptPreviewTitle').textContent = title + imageIndicator;

        // Update modal content
        document.getElementById('promptPreviewContent').textContent = data.prompt;

        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('promptPreviewModal'));
        modal.show();
    } catch (error) {
        showToast(t('toast.error', {message: error.message}), 'error');
    }
}

// Copy prompt to clipboard
document.getElementById('btnCopyPrompt').addEventListener('click', async () => {
    const content = document.getElementById('promptPreviewContent').textContent;
    try {
        await navigator.clipboard.writeText(content);
        showToast(t('toast.prompt_copied'));
    } catch (error) {
        showToast(t('toast.copy_failed'), 'error');
    }
});
