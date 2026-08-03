// Tab switching. `onShow(tab)` lets main.js trigger each tab's own load call
// (e.g. the Context and Schema tabs fetch on first view, not on page load).
export function initNav(onShow) {
  document.querySelectorAll('nav button').forEach(b => b.onclick = () => {
    document.querySelectorAll('nav button').forEach(x => x.classList.toggle('on', x === b));
    document.querySelectorAll('section').forEach(s => s.classList.toggle('on', s.id === b.dataset.tab));
    onShow(b.dataset.tab);
  });
}
