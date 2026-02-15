// Language switcher
document.getElementById('currentLang').textContent = LANG.toUpperCase();
document.querySelectorAll('[data-lang]').forEach(el => {
    el.addEventListener('click', (e) => {
        e.preventDefault();
        switchLanguage(el.dataset.lang);
    });
});

// Initial load with translations
(async () => {
    await loadTranslations(LANG);
    applyTranslations();
    loadPhotos();
})();
