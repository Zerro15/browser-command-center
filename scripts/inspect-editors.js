(() => {
  function describe(el) {
    if (!el) return null;
    return {
      tag: el.tagName.toLowerCase(),
      id: el.id || '',
      name: el.getAttribute('name') || '',
      class: (el.className || '').toString(),
      contentEditable: el.isContentEditable || false,
      role: el.getAttribute('role') || '',
      ariaLabel: el.getAttribute('aria-label') || '',
    };
  }

  function around(selector) {
    const el = document.querySelector(selector);
    const parent = el ? el.parentElement : null;
    const next = el ? el.nextElementSibling : null;
    const prev = el ? el.previousElementSibling : null;
    const withinParent = parent ? Array.from(parent.querySelectorAll('*')).slice(0, 40).map(describe) : [];
    const contenteditables = parent ? Array.from(parent.querySelectorAll('[contenteditable],.trumbowyg-editor,.ql-editor,.cke_editable')).map(describe) : [];
    return {
      selector,
      self: describe(el),
      prev: describe(prev),
      next: describe(next),
      parent: describe(parent),
      contenteditables,
      withinParent,
    };
  }

  return {
    description: around('#step1-description'),
    instruction: around('#step1-instruction'),
  };
})()
