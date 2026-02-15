// Map modal
function openMapModal(filename) {
    currentMapPhotoFilename = filename;
    const photo = photos.find(p => p.filename === filename);

    const modal = new bootstrap.Modal(document.getElementById('mapModal'));
    modal.show();

    // Initialize map after modal is shown
    document.getElementById('mapModal').addEventListener('shown.bs.modal', function initMap() {
        if (!map) {
            map = L.map('map').setView([50.0755, 14.4378], 10);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; OpenStreetMap contributors'
            }).addTo(map);

            map.on('click', (e) => {
                setMapMarker(e.latlng.lat, e.latlng.lng);
            });
        }

        // Set initial view based on photo GPS
        if (photo && photo.gps) {
            map.setView([photo.gps.lat, photo.gps.lng], 15);
            setMapMarker(photo.gps.lat, photo.gps.lng);
        } else {
            map.setView([50.0755, 14.4378], 5);
            if (mapMarker) {
                map.removeLayer(mapMarker);
                mapMarker = null;
            }
            mapSelectedCoords = null;
        }

        setTimeout(() => map.invalidateSize(), 100);
        this.removeEventListener('shown.bs.modal', initMap);
    }, { once: true });
}

function setMapMarker(lat, lng) {
    if (mapMarker) {
        mapMarker.setLatLng([lat, lng]);
    } else {
        mapMarker = L.marker([lat, lng]).addTo(map);
    }
    mapSelectedCoords = { lat, lng };
}

// Map search
let searchTimeout;
document.getElementById('mapSearch').addEventListener('input', (e) => {
    clearTimeout(searchTimeout);
    const query = e.target.value.trim();

    if (query.length < 2) {
        document.getElementById('searchResults').classList.add('d-none');
        return;
    }

    searchTimeout = setTimeout(async () => {
        try {
            const response = await fetch(`/api/geocode/search?q=${encodeURIComponent(query)}`);
            const data = await response.json();

            const resultsEl = document.getElementById('searchResults');
            if (data.results.length === 0) {
                resultsEl.classList.add('d-none');
                return;
            }

            resultsEl.innerHTML = data.results.map(r => `
                <div class="search-result-item" data-lat="${r.lat}" data-lng="${r.lng}">
                    ${r.display_name}
                </div>
            `).join('');
            resultsEl.classList.remove('d-none');

            resultsEl.querySelectorAll('.search-result-item').forEach(item => {
                item.addEventListener('click', () => {
                    const lat = parseFloat(item.dataset.lat);
                    const lng = parseFloat(item.dataset.lng);
                    map.setView([lat, lng], 15);
                    setMapMarker(lat, lng);
                    resultsEl.classList.add('d-none');
                    document.getElementById('mapSearch').value = '';
                });
            });
        } catch (error) {
            console.error('Search failed:', error);
        }
    }, 300);
});

// Confirm location button
document.getElementById('btnConfirmLocation').addEventListener('click', () => {
    if (!mapSelectedCoords || !currentMapPhotoFilename) return;

    const gpsInput = document.getElementById(`gps-${currentMapPhotoFilename}`);
    if (gpsInput) {
        gpsInput.value = `${mapSelectedCoords.lat.toFixed(6)}, ${mapSelectedCoords.lng.toFixed(6)}`;
    }

    bootstrap.Modal.getInstance(document.getElementById('mapModal')).hide();
    showToast(t('toast.gps_updated'));
});
