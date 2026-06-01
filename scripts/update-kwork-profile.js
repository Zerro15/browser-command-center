(() => {
  const profession = 'Python, боты и небольшие автоматизации';
  const details = `<div>Помогаю с небольшими и понятными задачами: исправить ошибку в коде, обработать Excel или CSV, сделать мини-парсер, настроить Telegram-уведомление, собрать простого бота для заявок.</div>
<div>Работаю с Python, JavaScript, Telegram Bot API, Google Sheets, API, webhook и простыми серверными настройками. Беру задачи, где можно быстро показать рабочий результат и не растягивать процесс.</div>
<div>Перед заказом уточняю входные данные, результат и ограничения. Если задача больше базового объема или я не смогу сделать ее качественно, скажу об этом до начала работы.</div>
<div>Не беру спам, взлом, обход капчи, сбор закрытых данных и действия против правил сервисов.</div>`;

  function setTrumbowygByName(name, htmlValue) {
    const textarea = document.querySelector(`textarea[name="${name}"]`);
    if (!textarea) return false;
    const editor = textarea.previousElementSibling;
    if (editor && editor.classList && editor.classList.contains('trumbowyg-editor')) {
      editor.focus();
      editor.innerHTML = htmlValue;
      editor.dispatchEvent(new Event('input', { bubbles: true }));
      editor.dispatchEvent(new Event('change', { bubbles: true }));
    }
    textarea.value = htmlValue;
    textarea.dispatchEvent(new Event('input', { bubbles: true }));
    textarea.dispatchEvent(new Event('change', { bubbles: true }));
    return true;
  }

  return {
    ok: true,
    profession: setTrumbowygByName('profession', `<div>${profession}</div>`),
    details: setTrumbowygByName('details', details),
  };
})()
