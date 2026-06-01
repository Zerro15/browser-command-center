(() => {
  const text = [
    'Здравствуйте. Да, могу взяться. Предлагаю начать с первого этапа: привести Docker-запуск в рабочее состояние для фронта, админки, бэка и Postgres, чтобы проект поднимался одной командой и база корректно инициализировалась.',
    '',
    'Для оценки пришлите, пожалуйста, доступ к репозиторию и кратко: как сейчас запускаете локально, какие env нужны, какие ошибки в Docker видите. После просмотра скажу точную цену и срок. Если без сильных проблем по коду, ориентир по Docker-этапу 3000-5000 ₽, CI/CD можно сделать вторым этапом.',
  ].join('\n');

  const editor = document.querySelector('.trumbowyg-editor[contenteditable="true"]');
  const textarea = document.querySelector('#message_body');
  const submit = document.querySelector('#new-desktop-submit button, #new-desktop-submit');

  if (!editor || !textarea || !submit) {
    return {
      ok: false,
      reason: 'message editor not found',
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

  submit.click();

  return {
    ok: true,
    textLength: text.length,
    textareaLength: textarea.value.length,
  };
})();
