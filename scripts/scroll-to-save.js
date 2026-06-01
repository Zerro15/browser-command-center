(() => {
  const isVisible = (el) => {
    const rect = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
  };

  const candidates = Array.from(document.querySelectorAll('button,a'))
    .map((el) => ({ el, text: (el.innerText || '').replace(/\s+/g, ' ').trim() }))
    .filter((x) => x.text === 'Сохранить')
    .filter((x) => isVisible(x.el));

  if (candidates.length) {
    candidates[0].el.scrollIntoView({ block: 'center', inline: 'center' });
    return { ok: true, found: 'visible' };
  }

  const any = Array.from(document.querySelectorAll('button,a'))
    .map((el) => ({ el, text: (el.innerText || '').replace(/\s+/g, ' ').trim() }))
    .filter((x) => x.text === 'Сохранить');

  if (any.length) {
    any[0].el.scrollIntoView({ block: 'center', inline: 'center' });
    return { ok: true, found: 'hidden-or-offscreen' };
  }

  window.scrollTo(0, document.body.scrollHeight);
  return { ok: false, error: 'not-found' };
})()
