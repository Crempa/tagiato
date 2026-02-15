// Select all checkbox
document.getElementById('selectAll').addEventListener('change', (e) => {
    const isChecked = e.target.checked;
    document.querySelectorAll('.photo-select').forEach(cb => {
        cb.checked = isChecked;
        if (isChecked) {
            selectedPhotos.add(cb.dataset.filename);
        } else {
            selectedPhotos.delete(cb.dataset.filename);
        }
    });
    updateProcessSelectedButton();
});

function updateSelectAllState() {
    const allCheckboxes = document.querySelectorAll('.photo-select');
    const checkedCount = document.querySelectorAll('.photo-select:checked').length;
    const selectAllCb = document.getElementById('selectAll');

    if (checkedCount === 0) {
        selectAllCb.checked = false;
        selectAllCb.indeterminate = false;
    } else if (checkedCount === allCheckboxes.length) {
        selectAllCb.checked = true;
        selectAllCb.indeterminate = false;
    } else {
        selectAllCb.checked = false;
        selectAllCb.indeterminate = true;
    }
}

function updateProcessSelectedButton() {
    // Legacy - dropdown buttons for selected photos don't need this anymore
}

// Filter and sort
document.querySelectorAll('input[name="filter"], input[name="sort"]').forEach(input => {
    input.addEventListener('change', loadPhotos);
});
