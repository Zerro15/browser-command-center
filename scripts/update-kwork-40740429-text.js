(() => {
  const title = 'Сделаю Telegram-бота под ключ: заявки, платежи, админка';
  const description = `<p>Разработаю Telegram-бота под вашу задачу: от простого FAQ до полноценного сервиса с меню, заявками, оплатой и админ-панелью.</p>
<p><strong>Подходит для:</strong></p>
<p>• лидогенерации и заявок</p>
<p>• поддержки клиентов и FAQ</p>
<p>• записи/броней, напоминаний</p>
<p>• продаж и оплаты (по условиям Telegram и платёжных систем)</p>
<p>• интеграций: Google Sheets, CRM, API, вебхуки</p>
<p><strong>Что сделаю:</strong></p>
<p>• сценарий диалога и структуру меню</p>
<p>• команды, кнопки, состояния, проверку ввода</p>
<p>• хранение данных (по необходимости) и логи</p>
<p>• деплой на сервер и инструкцию (если нужен)</p>
<p><strong>Стек:</strong> Python/Node.js, aiogram/pyTelegramBotAPI или Telegraf, webhook/long polling.</p>
<p>Пишу аккуратно, объясняю, что и как работает. Делаю так, чтобы потом можно было расширять.</p>`;

  const instruction = `<p>Опишите задачу в 2–3 предложениях (что бот должен делать)</p>
<p>Примеры сообщений/сценариев и список кнопок (если есть)</p>
<p>Нужны ли: заявки, оплата, админка, интеграции (Sheets/CRM/API)</p>
<p>Токен бота (BotFather) или просьба помочь создать</p>
<p>Где размещаем: ваш сервер/VPS или помогу подобрать</p>`;

  const standard = 'Соберу базовый бот: меню, команды, простые сценарии без оплат.';
  const medium = 'Бот + хранение данных/интеграции + доработка сценариев.';
  const premium = 'Бот под ключ: сложная логика + деплой + инструкция и поддержка.';

  function setTrumbowyg(textareaSelector, htmlValue) {
    const textarea = document.querySelector(textareaSelector);
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

  function setTextField(selector, value) {
    const el = document.querySelector(selector);
    if (!el) return false;
    el.focus();
    if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {
      el.value = value;
    } else {
      el.innerHTML = value;
      el.textContent = value;
    }
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    return true;
  }

  return {
    title: setTextField('#editor-title', title),
    description: setTrumbowyg('#step1-description', description),
    instruction: setTrumbowyg('#step1-instruction', instruction),
    standard: setTextField('#editor-bundle-standard-description', standard),
    medium: setTextField('#editor-bundle-medium-description', medium),
    premium: setTextField('#editor-bundle-premium-description', premium),
  };
})()
