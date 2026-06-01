(() => {
  const save = document.querySelector('.js-save-kwork');
  if (!save) return { ok: false, error: 'save-not-found' };
  save.scrollIntoView({ block: 'center', inline: 'center' });
  const rect = save.getBoundingClientRect();
  return {
    ok: true,
    text: (save.innerText || save.textContent || '').replace(/\s+/g, ' ').trim(),
    rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
  };
})()
