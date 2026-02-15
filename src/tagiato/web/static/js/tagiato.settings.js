// --- Provider Settings ---
const PROVIDER_MODELS = {
    claude: [
        { value: 'sonnet', label: 'Sonnet (default)' },
        { value: 'opus', label: 'Opus (reasoning)' },
        { value: 'haiku', label: 'Haiku (fast)' },
        { value: 'sonnet[1m]', label: 'Sonnet 1M context' },
    ],
    gemini: [
        { value: 'flash', label: 'Flash (default)' },
        { value: 'gemini-3-flash-preview', label: 'Gemini 3 Flash Preview' },
        { value: 'pro', label: 'Pro' },
        { value: 'ultra', label: 'Ultra' },
    ],
    openai: [
        { value: 'o3', label: 'o3 (reasoning)' },
        { value: 'o4-mini', label: 'o4-mini (fast)' },
        { value: 'gpt-5.2', label: 'GPT-5.2' },
        { value: 'gpt-5.2-pro', label: 'GPT-5.2 Pro' },
        { value: 'gpt-5-mini', label: 'GPT-5 Mini' },
        { value: 'codex-mini-latest', label: 'Codex Mini' },
    ],
};

function updateModelOptions(providerSelect, modelSelect, currentModel) {
    const provider = providerSelect.value;
    const models = PROVIDER_MODELS[provider] || [];

    modelSelect.innerHTML = models.map(m =>
        `<option value="${m.value}" ${m.value === currentModel ? 'selected' : ''}>${m.label}</option>`
    ).join('');
}

async function loadProviderSettings() {
    try {
        const [providerRes, contextRes] = await Promise.all([
            fetch('/api/settings/providers'),
            fetch('/api/settings/context'),
        ]);

        const settings = await providerRes.json();
        const contextSettings = await contextRes.json();

        document.getElementById('describeProvider').value = settings.describe_provider;
        document.getElementById('locateProvider').value = settings.locate_provider;

        updateModelOptions(
            document.getElementById('describeProvider'),
            document.getElementById('describeModel'),
            settings.describe_model
        );
        updateModelOptions(
            document.getElementById('locateProvider'),
            document.getElementById('locateModel'),
            settings.locate_model
        );

        updateProviderSummary(settings);

        // Load context settings
        document.getElementById('contextEnabled').checked = contextSettings.enabled;
        document.getElementById('contextRadius').value = contextSettings.radius_km;
        document.getElementById('contextMaxCount').value = contextSettings.max_count;
    } catch (error) {
        console.error('Failed to load provider settings:', error);
    }
}

function updateProviderSummary(settings) {
    const summary = document.getElementById('providerSummary');
    summary.textContent = `${settings.describe_provider}/${settings.locate_provider}`;
}

// Update model options when provider changes
document.getElementById('describeProvider').addEventListener('change', (e) => {
    const defaultModel = PROVIDER_MODELS[e.target.value]?.[0]?.value || 'sonnet';
    updateModelOptions(e.target, document.getElementById('describeModel'), defaultModel);
});

document.getElementById('locateProvider').addEventListener('change', (e) => {
    const defaultModel = PROVIDER_MODELS[e.target.value]?.[0]?.value || 'sonnet';
    updateModelOptions(e.target, document.getElementById('locateModel'), defaultModel);
});

// Save settings
document.getElementById('btnSaveSettings').addEventListener('click', async () => {
    const settings = {
        describe_provider: document.getElementById('describeProvider').value,
        describe_model: document.getElementById('describeModel').value,
        locate_provider: document.getElementById('locateProvider').value,
        locate_model: document.getElementById('locateModel').value,
    };

    const contextSettings = {
        enabled: document.getElementById('contextEnabled').checked,
        radius_km: parseFloat(document.getElementById('contextRadius').value),
        max_count: parseInt(document.getElementById('contextMaxCount').value),
    };

    try {
        // Save both provider and context settings
        const [providerRes, contextRes] = await Promise.all([
            fetch('/api/settings/providers', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            }),
            fetch('/api/settings/context', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(contextSettings)
            }),
        ]);

        if (providerRes.ok && contextRes.ok) {
            updateProviderSummary(settings);
            bootstrap.Modal.getInstance(document.getElementById('settingsModal')).hide();
            showToast(t('toast.settings_saved'));
        } else {
            const error = await (providerRes.ok ? contextRes : providerRes).json();
            showToast(t('toast.error', {message: error.detail}), 'error');
        }
    } catch (error) {
        showToast(t('toast.error', {message: error.message}), 'error');
    }
});

// Load settings when modal opens
document.getElementById('settingsModal').addEventListener('show.bs.modal', loadProviderSettings);
