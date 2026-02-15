// --- Log Panel ---
let logEventSource = null;

function formatLogTime(isoString) {
    const date = new Date(isoString);
    const locale = LANG === 'cs' ? 'cs-CZ' : 'en-US';
    return date.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function renderLogEntry(entry) {
    const time = formatLogTime(entry.timestamp);
    const levelClass = `log-${entry.level}`;

    let dataHtml = '';
    if (entry.data) {
        const hasLongData = entry.data.prompt || entry.data.response;
        if (hasLongData) {
            const dataId = 'data-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
            const content = entry.data.prompt || entry.data.response || '';
            dataHtml = `
                <span class="log-toggle-data" onclick="toggleLogData('${dataId}')">${t('log.show_detail')}</span>
                <div class="log-data d-none" id="${dataId}">${escapeHtml(content)}</div>
            `;
        }
    }

    return `
        <div class="log-entry ${levelClass}">
            <span class="log-time">${time}</span>
            <span>${escapeHtml(entry.message)}</span>
            ${dataHtml}
        </div>
    `;
}

function toggleLogData(id) {
    const el = document.getElementById(id);
    if (el) {
        el.classList.toggle('d-none');
    }
}

function addLogEntry(entry) {
    const content = document.getElementById('logContent');
    content.insertAdjacentHTML('beforeend', renderLogEntry(entry));
    // Auto-scroll to bottom
    content.scrollTop = content.scrollHeight;
}

function connectToLogStream() {
    if (logEventSource) {
        logEventSource.close();
    }

    const content = document.getElementById('logContent');
    content.innerHTML = `<div class="log-entry log-info">${t('log.connecting')}</div>`;

    logEventSource = new EventSource('/api/logs/stream');

    logEventSource.onopen = () => {
        content.innerHTML = '';
    };

    logEventSource.onmessage = (event) => {
        try {
            const entry = JSON.parse(event.data);
            addLogEntry(entry);
        } catch (e) {
            console.error('Failed to parse log entry:', e);
        }
    };

    logEventSource.onerror = () => {
        content.insertAdjacentHTML('beforeend',
            `<div class="log-entry log-error">${t('log.connection_error')}</div>`);
        setTimeout(connectToLogStream, 3000);
    };
}

function toggleLogPanel() {
    const panel = document.getElementById('logPanel');
    const isHidden = panel.classList.contains('d-none');

    if (isHidden) {
        panel.classList.remove('d-none');
        document.body.classList.add('log-open');
        connectToLogStream();
    } else {
        panel.classList.add('d-none');
        document.body.classList.remove('log-open');
        if (logEventSource) {
            logEventSource.close();
            logEventSource = null;
        }
    }
}

// Log panel buttons
document.getElementById('btnToggleLog').addEventListener('click', toggleLogPanel);
document.getElementById('btnCloseLog').addEventListener('click', toggleLogPanel);
document.getElementById('btnClearLog').addEventListener('click', async () => {
    await fetch('/api/logs', { method: 'DELETE' });
    document.getElementById('logContent').innerHTML =
        `<div class="log-entry log-info">${t('log.cleared')}</div>`;
});
