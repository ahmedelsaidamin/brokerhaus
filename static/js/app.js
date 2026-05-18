// === Brokerhaus shared JS ===

(function() {
  const langBtns = document.querySelectorAll('.lang-btn');
  const htmlEl = document.documentElement;

  function setLanguage(lang) {
    htmlEl.setAttribute('lang', lang);
    langBtns.forEach(b => b.classList.toggle('active', b.dataset.lang === lang));
    document.querySelectorAll('[data-en]').forEach(el => {
      const txt = lang === 'ar' ? el.dataset.ar : el.dataset.en;
      if (txt !== undefined) el.textContent = txt;
    });
    document.querySelectorAll('[data-en-html]').forEach(el => {
      const html = lang === 'ar' ? el.dataset.arHtml : el.dataset.enHtml;
      if (html !== undefined) el.innerHTML = html;
    });
    document.querySelectorAll('[data-en-placeholder]').forEach(el => {
      const p = lang === 'ar' ? el.dataset.arPlaceholder : el.dataset.enPlaceholder;
      if (p !== undefined) el.setAttribute('placeholder', p);
    });
    try { localStorage.setItem('brokerhaus-lang', lang); } catch(e) {}
  }
  window.setLanguage = setLanguage;

  langBtns.forEach(b => b.addEventListener('click', () => setLanguage(b.dataset.lang)));
  try {
    const saved = localStorage.getItem('brokerhaus-lang');
    if (saved === 'ar') setLanguage('ar');
  } catch(e) {}
})();

// === API helper ===
window.api = async function(url, options = {}) {
  const opts = {
    method: options.method || 'GET',
    headers: { 'Content-Type': 'application/json', ...options.headers },
    credentials: 'same-origin',
  };
  if (options.body) opts.body = typeof options.body === 'string' ? options.body : JSON.stringify(options.body);
  const r = await fetch(url, opts);
  let data = null;
  try { data = await r.json(); } catch(e) {}
  return { ok: r.ok, status: r.status, data };
};

// === Toast ===
window.toast = function(message, type = 'info') {
  let host = document.getElementById('toast-host');
  if (!host) {
    host = document.createElement('div');
    host.id = 'toast-host';
    host.style.cssText = 'position:fixed;top:20px;right:20px;z-index:9999;display:flex;flex-direction:column;gap:8px;';
    document.body.appendChild(host);
  }
  const t = document.createElement('div');
  const colors = {
    info: 'background:#161616;border:1px solid #2a2a2a;color:#ededed',
    success: 'background:rgba(74,222,128,0.12);border:1px solid rgba(74,222,128,0.4);color:#4ade80',
    error: 'background:rgba(255,92,92,0.12);border:1px solid rgba(255,92,92,0.4);color:#ff5c5c',
  };
  t.style.cssText = `padding:12px 18px;border-radius:6px;font-size:13px;max-width:340px;animation:toastIn .3s ease;${colors[type]||colors.info}`;
  t.textContent = message;
  host.appendChild(t);
  setTimeout(() => {
    t.style.opacity = '0';
    t.style.transition = 'opacity .3s';
    setTimeout(() => t.remove(), 300);
  }, 3500);
};

// Toast animation
if (!document.getElementById('bh-toast-style')) {
  const s = document.createElement('style');
  s.id = 'bh-toast-style';
  s.textContent = '@keyframes toastIn{from{opacity:0;transform:translateY(-8px)}to{opacity:1;transform:translateY(0)}}';
  document.head.appendChild(s);
}
