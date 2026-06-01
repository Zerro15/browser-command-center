(() => {
  const normalize = (s) => (s || '').replace(/\s+/g, ' ').trim();
  const candidates = Array.from(document.querySelectorAll('button,a'))
    .map((el) => ({
      el,
      text: normalize(el.innerText),
      disabled: !!el.disabled || el.getAttribute('aria-disabled') === 'true',
      class: (el.className || '').toString(),
    }))
    .filter((x) => x.text === 'Сохранить');

  if (!candidates.length) {
    return { ok: false, error: 'Save button not found' };
  }

  const enabled = candidates.find((x) => !x.disabled) || candidates[0];
  enabled.el.scrollIntoView({ block: 'center', inline: 'center' });
  enabled.el.click();
  return { ok: true, clicked: enabled.text, disabled: enabled.disabled, class: enabled.class };
})()
