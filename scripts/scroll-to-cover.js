(() => {
  const isVisible = (el) => {
    const rect = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
  };

  const candidates = Array.from(document.querySelectorAll('h1,h2,h3,div,span'))
    .map((el) => ({ el, text: (el.innerText || '').replace(/\s+/g, ' ').trim() }))
    .filter((x) => x.text === 'Обложка кворка' || x.text.includes('Загрузить обложку'))
    .filter((x) => isVisible(x.el));

  if (candidates.length) {
    candidates[0].el.scrollIntoView({ block: 'center', inline: 'center' });
    return { ok: true, scrolledTo: candidates[0].text };
  }

  window.scrollTo(0, 0);
  return { ok: false, error: 'cover section not found (visible)' };
})()
