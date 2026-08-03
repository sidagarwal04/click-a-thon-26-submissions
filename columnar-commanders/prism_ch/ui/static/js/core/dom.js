export const $ = s => document.querySelector(s);

export const esc = s => String(s ?? '').replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));

export const spin = (el, on) => { el.innerHTML = on ? '<span class="spin"></span>' : ''; };
