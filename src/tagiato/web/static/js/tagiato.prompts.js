// --- Prompts Settings ---
let promptsState = {
    describePrompt: '',
    locatePrompt: '',
    defaultDescribePrompt: '',
    defaultLocatePrompt: '',
    activePreset: null,
    activePresetName: null,
    presets: {},
    originalDescribe: '',
    originalLocate: '',
};

async function loadPromptsSettings() {
    try {
        const [promptsRes, presetsRes] = await Promise.all([
            fetch('/api/settings/prompts'),
            fetch('/api/settings/presets'),
        ]);

        const prompts = await promptsRes.json();
        const presets = await presetsRes.json();

        promptsState.describePrompt = prompts.describe_prompt || prompts.default_describe_prompt;
        promptsState.locatePrompt = prompts.locate_prompt || prompts.default_locate_prompt;
        promptsState.defaultDescribePrompt = prompts.default_describe_prompt;
        promptsState.defaultLocatePrompt = prompts.default_locate_prompt;
        promptsState.activePreset = prompts.active_preset;
        promptsState.activePresetName = prompts.active_preset_name;
        promptsState.presets = presets.presets || {};

        // Store original values for unsaved changes detection
        promptsState.originalDescribe = promptsState.describePrompt;
        promptsState.originalLocate = promptsState.locatePrompt;

        // Update UI
        document.getElementById('describePromptText').value = promptsState.describePrompt;
        document.getElementById('locatePromptText').value = promptsState.locatePrompt;

        updatePresetDropdown();
        updatePresetBadge();
        updateDeletePresetButton();

    } catch (error) {
        console.error('Failed to load prompts settings:', error);
    }
}

function updatePresetDropdown() {
    const select = document.getElementById('presetSelect');
    select.innerHTML = `<option value="">${t('prompts.preset_none')}</option>`;

    for (const [key, preset] of Object.entries(promptsState.presets)) {
        const option = document.createElement('option');
        option.value = key;
        option.textContent = preset.name;
        if (key === promptsState.activePreset) {
            option.selected = true;
        }
        select.appendChild(option);
    }
}

function updatePresetBadge() {
    const badge = document.getElementById('presetBadge');
    if (promptsState.activePresetName) {
        badge.textContent = promptsState.activePresetName;
        badge.classList.remove('d-none');
    } else {
        badge.classList.add('d-none');
    }
}

function updateDeletePresetButton() {
    const btn = document.getElementById('btnDeletePreset');
    btn.disabled = !promptsState.activePreset;
}

function hasUnsavedPromptChanges() {
    const currentDescribe = document.getElementById('describePromptText').value;
    const currentLocate = document.getElementById('locatePromptText').value;
    return currentDescribe !== promptsState.originalDescribe ||
           currentLocate !== promptsState.originalLocate;
}

// Preset dropdown change
document.getElementById('presetSelect').addEventListener('change', async (e) => {
    const key = e.target.value;

    if (!key) {
        // Reset to defaults
        promptsState.describePrompt = promptsState.defaultDescribePrompt;
        promptsState.locatePrompt = promptsState.defaultLocatePrompt;
        promptsState.activePreset = null;
        promptsState.activePresetName = null;

        document.getElementById('describePromptText').value = promptsState.describePrompt;
        document.getElementById('locatePromptText').value = promptsState.locatePrompt;

        promptsState.originalDescribe = promptsState.describePrompt;
        promptsState.originalLocate = promptsState.locatePrompt;

        updatePresetBadge();
        updateDeletePresetButton();
        return;
    }

    try {
        const response = await fetch(`/api/settings/presets/${key}/activate`, { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            promptsState.describePrompt = data.describe_prompt || promptsState.defaultDescribePrompt;
            promptsState.locatePrompt = data.locate_prompt || promptsState.defaultLocatePrompt;
            promptsState.activePreset = key;
            promptsState.activePresetName = promptsState.presets[key]?.name;

            document.getElementById('describePromptText').value = promptsState.describePrompt;
            document.getElementById('locatePromptText').value = promptsState.locatePrompt;

            promptsState.originalDescribe = promptsState.describePrompt;
            promptsState.originalLocate = promptsState.locatePrompt;

            updatePresetBadge();
            updateDeletePresetButton();
        }
    } catch (error) {
        showToast(t('toast.preset_activate_error'), 'error');
    }
});

// Reset buttons
document.getElementById('btnResetDescribe').addEventListener('click', () => {
    document.getElementById('describePromptText').value = promptsState.defaultDescribePrompt;
});

document.getElementById('btnResetLocate').addEventListener('click', () => {
    document.getElementById('locatePromptText').value = promptsState.defaultLocatePrompt;
});

// Save prompts to session
document.getElementById('btnSavePrompts').addEventListener('click', async () => {
    const describePrompt = document.getElementById('describePromptText').value;
    const locatePrompt = document.getElementById('locatePromptText').value;

    try {
        const response = await fetch('/api/settings/prompts', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                describe_prompt: describePrompt,
                locate_prompt: locatePrompt,
            })
        });

        if (response.ok) {
            promptsState.describePrompt = describePrompt;
            promptsState.locatePrompt = locatePrompt;
            promptsState.originalDescribe = describePrompt;
            promptsState.originalLocate = locatePrompt;

            bootstrap.Modal.getInstance(document.getElementById('promptsModal')).hide();
            showToast(t('toast.prompts_saved'));
        } else {
            const error = await response.json();
            showToast(t('toast.error', {message: error.detail}), 'error');
        }
    } catch (error) {
        showToast(t('toast.error', {message: error.message}), 'error');
    }
});

// Save as preset button
document.getElementById('btnSaveAsPreset').addEventListener('click', () => {
    document.getElementById('presetName').value = '';
    const savePresetModal = new bootstrap.Modal(document.getElementById('savePresetModal'));
    savePresetModal.show();
});

// Confirm save preset
document.getElementById('btnConfirmSavePreset').addEventListener('click', async () => {
    const name = document.getElementById('presetName').value.trim();
    if (!name) {
        showToast(t('toast.enter_preset_name'), 'warning');
        return;
    }

    // Generate key from name
    const key = name.toLowerCase()
        .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-|-$/g, '');

    const describePrompt = document.getElementById('describePromptText').value;
    const locatePrompt = document.getElementById('locatePromptText').value;

    try {
        const response = await fetch('/api/settings/presets', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                key: key,
                name: name,
                describe_prompt: describePrompt,
                locate_prompt: locatePrompt,
            })
        });

        if (response.ok) {
            const data = await response.json();

            // Update local state
            promptsState.presets[key] = {
                name: name,
                describe_prompt: describePrompt,
                locate_prompt: locatePrompt,
            };
            promptsState.activePreset = key;
            promptsState.activePresetName = name;
            promptsState.describePrompt = describePrompt;
            promptsState.locatePrompt = locatePrompt;
            promptsState.originalDescribe = describePrompt;
            promptsState.originalLocate = locatePrompt;

            updatePresetDropdown();
            updatePresetBadge();
            updateDeletePresetButton();

            bootstrap.Modal.getInstance(document.getElementById('savePresetModal')).hide();
            showToast(t('toast.preset_saved', {name: name}));
        } else {
            const error = await response.json();
            showToast(t('toast.error', {message: error.detail}), 'error');
        }
    } catch (error) {
        showToast(t('toast.error', {message: error.message}), 'error');
    }
});

// Delete preset
document.getElementById('btnDeletePreset').addEventListener('click', async () => {
    if (!promptsState.activePreset) return;

    const presetName = promptsState.activePresetName || promptsState.activePreset;
    if (!confirm(t('confirm.delete_preset', {name: presetName}))) {
        return;
    }

    try {
        const response = await fetch(`/api/settings/presets/${promptsState.activePreset}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            delete promptsState.presets[promptsState.activePreset];
            promptsState.activePreset = null;
            promptsState.activePresetName = null;

            // Reset to defaults
            promptsState.describePrompt = promptsState.defaultDescribePrompt;
            promptsState.locatePrompt = promptsState.defaultLocatePrompt;
            document.getElementById('describePromptText').value = promptsState.describePrompt;
            document.getElementById('locatePromptText').value = promptsState.locatePrompt;
            promptsState.originalDescribe = promptsState.describePrompt;
            promptsState.originalLocate = promptsState.locatePrompt;

            updatePresetDropdown();
            updatePresetBadge();
            updateDeletePresetButton();

            showToast(t('toast.preset_deleted', {name: presetName}));
        } else {
            showToast(t('toast.preset_delete_error'), 'error');
        }
    } catch (error) {
        showToast(t('toast.error', {message: error.message}), 'error');
    }
});

// Prompts modal - load on show
document.getElementById('promptsModal').addEventListener('show.bs.modal', loadPromptsSettings);

// Prompts modal - check unsaved changes on hide
document.getElementById('promptsModal').addEventListener('hide.bs.modal', (e) => {
    if (hasUnsavedPromptChanges()) {
        if (!confirm(t('confirm.unsaved_prompts'))) {
            e.preventDefault();
        }
    }
});

// Disable prompts button during batch processing
function updatePromptsButtonState(batchRunning) {
    const btn = document.getElementById('btnPrompts');
    btn.disabled = batchRunning;
    btn.title = batchRunning ? t('prompts.btn_disabled_title') : t('prompts.btn_title');
}
