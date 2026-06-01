(() => {
  const offer = {
    title: 'Подключу OpenAI GPT к сайту, боту или CRM',
    description: `<p>Подключу OpenAI/GPT к вашему сайту, Telegram-боту, CRM, Google Sheets или внутреннему сервису.</p>
<p><strong>Что можно сделать:</strong></p>
<p>• AI-ответы клиентам в боте или на сайте</p>
<p>• анализ заявок, сообщений, отзывов и документов</p>
<p>• генерация текстов, писем, описаний и отчетов</p>
<p>• классификация обращений и передача результата менеджеру</p>
<p>• webhook/API-интеграция с вашим сервисом</p>
<p>• простая админ-настройка промпта и правил ответа</p>
<p>Работаю аккуратно: сначала уточняю сценарий, затем делаю минимальный рабочий вариант, проверяю на ваших примерах и объясняю, как пользоваться.</p>
<p>Могу подключить OpenAI, OpenRouter, Gemini или другой совместимый API. Стоимость API оплачивается отдельно на стороне выбранного сервиса.</p>`,
    instruction: `<p>Опишите, куда нужно подключить AI: сайт, бот, CRM, таблица или другой сервис.</p>
<p>Пришлите пример входных данных и желаемого результата.</p>
<p>Укажите, какой API использовать: OpenAI, OpenRouter, Gemini или другой.</p>
<p>Напишите, нужен ли webhook, база данных, логирование, ограничения по ответам.</p>
<p>API-ключи и доступы передавайте только внутри заказа.</p>`,
    serviceSize: '1 AI-интеграция или один рабочий сценарий',
  };

  function fire(el) {
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    if (window.jQuery) window.jQuery(el).trigger('change').trigger('chosen:updated');
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
    fire(el);
    return true;
  }

  function setTrumbowyg(textareaSelector, htmlValue) {
    const textarea = document.querySelector(textareaSelector);
    if (!textarea) return false;
    const editor = textarea.previousElementSibling;
    if (editor && editor.classList && editor.classList.contains('trumbowyg-editor')) {
      editor.focus();
      editor.innerHTML = htmlValue;
      fire(editor);
    }
    textarea.value = htmlValue;
    fire(textarea);
    return true;
  }

  const parent = document.querySelector('.js-category_parent');
  const sub = document.querySelector('.js-category_sub');
  if (parent) {
    parent.value = '11';
    fire(parent);
  }
  if (sub) {
    sub.value = '41';
    fire(sub);
  }

  const aiBot = document.querySelector('#attribute_item_4158112');
  if (aiBot) {
    aiBot.checked = true;
    fire(aiBot);
  }

  const price = document.querySelector('#min_volume_price');
  if (price) {
    price.value = '5000';
    fire(price);
  }
  const time = document.querySelector('#step2-work-time');
  if (time) {
    time.value = '3';
    fire(time);
  }

  return {
    ok: true,
    title: setTextField('#editor-title', offer.title),
    description: setTrumbowyg('#step1-description', offer.description),
    instruction: setTrumbowyg('#step1-instruction', offer.instruction),
    serviceSize: setTextField('#editor-service_size', offer.serviceSize) && setTextField('#step2-service-size', offer.serviceSize),
    volume: setTextField('#step2-volume', '1'),
    category: { parent: parent?.value || null, sub: sub?.value || null },
    type: aiBot?.checked || false,
    price: price?.value || null,
    workTime: time?.value || null,
  };
})()
