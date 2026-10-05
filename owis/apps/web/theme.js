// Light/dark theme switch shared by the OWIS pages.
// Loaded in <head> so the saved theme applies before the page paints.
(function () {
  const KEY = 'owisTheme';
  const root = document.documentElement;
  const media = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;

  function saved() {
    try { return localStorage.getItem(KEY); } catch (error) { return null; }
  }

  function current() {
    const choice = root.dataset.theme;
    if (choice === 'light' || choice === 'dark') return choice;
    return media && media.matches ? 'dark' : 'light';
  }

  function label(button) {
    const dark = current() === 'dark';
    button.textContent = dark ? 'Light mode' : 'Dark mode';
    button.setAttribute('aria-pressed', String(dark));
  }

  const initial = saved();
  if (initial === 'light' || initial === 'dark') root.dataset.theme = initial;

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-theme-toggle]').forEach(button => {
      label(button);
      button.addEventListener('click', () => {
        const next = current() === 'dark' ? 'light' : 'dark';
        root.dataset.theme = next;
        try { localStorage.setItem(KEY, next); } catch (error) { /* theme still applies for this visit */ }
        document.querySelectorAll('[data-theme-toggle]').forEach(label);
      });
    });
    if (media && media.addEventListener) {
      media.addEventListener('change', () => document.querySelectorAll('[data-theme-toggle]').forEach(label));
    }
  });
})();
