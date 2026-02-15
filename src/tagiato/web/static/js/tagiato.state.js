// Global state
let photos = [];
let selectedPhotos = new Set();
let map = null;
let mapMarker = null;
let currentMapPhotoFilename = null;
let mapSelectedCoords = null;

// Toast helper
function showToast(message, type = 'success') {
    const container = document.getElementById('toastContainer');
    const toastId = 'toast-' + Date.now();

    const bgClass = type === 'success' ? 'bg-success' : type === 'error' ? 'bg-danger' : 'bg-warning';
    const textClass = type === 'warning' ? 'text-dark' : 'text-white';

    container.innerHTML += `
        <div id="${toastId}" class="toast ${bgClass} ${textClass}" role="alert">
            <div class="toast-body d-flex align-items-center">
                <span>${message}</span>
                <button type="button" class="btn-close btn-close-white ms-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `;

    const toastEl = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastEl, { delay: 3000 });
    toast.show();

    toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
}
