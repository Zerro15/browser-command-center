(() => {
  const text = [
    'Здравствуйте. Сейчас беру небольшие DevOps-задачи поэтапно. Если проект доставки ещё актуален, могу помочь не со всем продуктом сразу, а с инфраструктурным этапом: Docker, сервер, база, деплой backend/frontend, env, домены/SSL, базовый CI/CD.',
    '',
    'Чтобы оценить, пришлите стек, где лежит код, какие части уже готовы и что именно нужно запустить первым. После этого предложу короткий план и стоимость за первый этап.',
  ].join('\n');

  const editor = document.querySelector('.trumbowyg-editor[contenteditable="true"]');
  const textarea = document.querySelector('#message_body');
  const submit = document.querySelector('#new-desktop-submit button, #new-desktop-submit');

  if (!editor || !textarea || !submit) {
    return {
      ok: false,
      hasEditor: Boolean(editor),
      hasTextarea: Boolean(textarea),
      hasSubmit: Boolean(submit),
    };
  }

  const html = text
    .split('\n')
    .map((line) => `<div>${line ? line.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;') : '<br>'}</div>`)
    .join('');

  editor.focus();
  editor.innerHTML = html;
  editor.classList.remove('is-empty', 'is-empty-focus', 'force-placeholder');
  textarea.value = html;

  for (const el of [editor, textarea]) {
    el.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: text }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    el.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true, key: 'а' }));
  }

  submit.removeAttribute('disabled');
  submit.click();

  return { ok: true, textLength: text.length, textareaLength: textarea.value.length };
})();
