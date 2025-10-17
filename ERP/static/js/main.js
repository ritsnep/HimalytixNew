const root = document.body;
function setTheme(t){
  root.setAttribute('data-layout-mode', t);
}

document.addEventListener('DOMContentLoaded', () => {
  setTheme(localStorage.getItem('theme') || 'light');
  const toggle = document.querySelector('#mode-setting-btn');
  if (toggle){
    toggle.addEventListener('click', () => {
      const next = root.getAttribute('data-layout-mode') === 'dark' ? 'light' : 'dark';
      setTheme(next);
      localStorage.setItem('theme', next);
    });
  }
});

htmx.on('htmx:beforeSwap', () => setTheme(localStorage.getItem('theme') || 'light'));

const overlay = document.getElementById('loading-overlay');
htmx.on('htmx:requestStart', () => overlay.classList.add('show'));
htmx.on('htmx:responseError', () => overlay.classList.remove('show'));
htmx.on('htmx:afterSwap', () => overlay.classList.remove('show'));