(() => {
  const offers = {
    45587052: {
      title: 'Исправлю одну ошибку в Python, JS, боте или парсере',
      serviceSize: '1 небольшая ошибка или понятная правка',
      price: 1500,
      time: 1,
      description: `<p>Исправлю одну конкретную ошибку в скрипте, Telegram-боте, парсере, небольшом сайте или автоматизации.</p><p><strong>Подходит для быстрого заказа:</strong> скрипт не запускается, появилась ошибка в консоли, парсер перестал собирать данные, бот не отвечает, сломалась команда, нужно поправить небольшой участок кода.</p><p>В базовый кворк входит диагностика одной проблемы, исправление в коде и короткое объяснение, что было не так. Если после просмотра окажется, что задача больше базового объема, заранее скажу и предложу вариант без навязывания.</p><p>Не беру взлом, спам, обход капчи и действия против правил сервисов.</p>`,
      instruction: `<p>Пришлите архив проекта или ссылку на репозиторий.</p><p>Приложите текст ошибки, лог или скриншот.</p><p>Напишите, что должно работать после исправления.</p><p>Если есть ограничения по файлам или доступам, укажите их сразу.</p>`,
      extras: [
        ['Срочно сегодня', 'Постараюсь разобрать задачу в приоритете после согласования объема.', 1500, 0],
        ['Запуск у вас', 'Помогу запустить исправленный проект на вашем компьютере или сервере.', 2500, 1],
      ],
    },
    51213975: {
      title: 'Обработаю один Excel CSV файл или таблицу',
      serviceSize: '1 файл или один простой сценарий обработки',
      price: 1500,
      time: 1,
      description: `<p>Обработаю один Excel, CSV или Google Sheets файл: очищу данные, удалю дубли, приведу столбцы к нужному виду, объединю строки или подготовлю файл для загрузки в CRM, магазин или другой сервис.</p><p><strong>Базовый объем:</strong> один понятный файл или небольшая выборка, один результат на выходе: XLSX, CSV, JSON или таблица.</p><p>Подходит, если нужно быстро привести данные в порядок без большого проекта. Если файлов много или правила сложные, сначала оценю объем и предложу безопасный вариант.</p>`,
      instruction: `<p>Пришлите файл или тестовую выборку без приватных данных.</p><p>Опишите, что нужно получить на выходе.</p><p>Укажите формат результата: XLSX, CSV, JSON или Google Sheets.</p><p>Если есть пример правильного результата, приложите его.</p>`,
      extras: [
        ['Повторяемый скрипт', 'Сделаю небольшой скрипт, чтобы вы могли запускать обработку повторно.', 2500, 1],
        ['Несколько файлов', 'Обработаю набор однотипных файлов по тем же правилам.', 2500, 1],
      ],
    },
    45979524: {
      title: 'Сделаю мини-парсер одной страницы на Python',
      serviceSize: '1 мини-парсер одного источника',
      price: 2500,
      time: 2,
      description: `<p>Сделаю небольшой Python-парсер для одной страницы или одного простого источника и выгружу результат в CSV, Excel, JSON или текстовый файл.</p><p><strong>Базовый объем:</strong> собрать понятные данные с открытой страницы: названия, цены, ссылки, контакты, статусы, карточки или другой видимый текст.</p><p>Сначала проверю, можно ли корректно получить данные. Не занимаюсь обходом капчи, закрытых личных кабинетов, спамом и сбором приватной информации.</p>`,
      instruction: `<p>Пришлите ссылку на страницу.</p><p>Напишите, какие поля нужно собрать.</p><p>Укажите формат результата: CSV, XLSX, JSON или Google Sheets.</p><p>Покажите пример 2-3 строк результата, если он уже есть.</p>`,
      extras: [
        ['Запуск по расписанию', 'Добавлю простой запуск по расписанию на вашем компьютере или сервере.', 2500, 1],
        ['Уведомление в Телеграм', 'Добавлю отправку результата или статуса в Telegram.', 2500, 1],
      ],
    },
    51213619: {
      title: 'Настрою уведомление в Telegram из Google Sheets',
      serviceSize: '1 уведомление или один сценарий таблицы',
      price: 2500,
      time: 2,
      description: `<p>Настрою простое уведомление в Telegram из Google Sheets или похожей таблицы: новая строка, изменение статуса, заявка, отчет или напоминание.</p><p><strong>Базовый объем:</strong> один сценарий уведомления, один чат или один администратор, понятный текст сообщения и проверка на тестовых данных.</p><p>Подходит для быстрого наведения порядка в заявках и отчетах. Сложные CRM, несколько ролей, много условий и регулярные отчеты можно добавить отдельным этапом.</p>`,
      instruction: `<p>Пришлите пример таблицы или структуру столбцов.</p><p>Опишите, при каком событии нужно отправлять уведомление.</p><p>Напишите текст сообщения или поля, которые должны попадать в Telegram.</p><p>Доступы передавайте только внутри заказа.</p>`,
      extras: [
        ['Несколько условий', 'Добавлю дополнительные условия отправки уведомлений.', 2500, 1],
        ['Отчет по расписанию', 'Настрою регулярный отчет в Telegram по данным таблицы.', 3500, 1],
      ],
    },
    40740429: {
      title: 'Создам простого Telegram-бота для заявок',
      serviceSize: '1 простой Telegram-бот или сценарий заявок',
      price: 2500,
      time: 2,
      description: `<p>Создам простого Telegram-бота для заявок, вопросов или уведомлений. Это маленький стартовый кворк без сложной логики, чтобы быстро получить рабочий результат.</p><p><strong>В базовый объем входит:</strong> команда старт, короткое меню или кнопка, прием заявки от пользователя и отправка заявки администратору в Telegram.</p><p>Если нужны AI/GPT, база данных, оплата, личный кабинет, сложные сценарии или серверный деплой, оценю отдельно до начала работы.</p>`,
      instruction: `<p>Опишите, какую заявку должен принимать бот.</p><p>Пришлите список полей: имя, телефон, сообщение, услуга и т.д.</p><p>Пришлите токен BotFather и ID администратора, если заказ уже создан.</p><p>Напишите, нужен ли запуск на вашем сервере или достаточно кода и инструкции.</p>`,
      extras: [
        ['Запуск на сервере', 'Помогу запустить бота на VPS или хостинге заказчика.', 3500, 1],
        ['Запись в таблицу', 'Добавлю запись заявок в Google Sheets.', 2500, 1],
      ],
    },
  };

  const id = new URL(location.href).searchParams.get('id');
  const offer = offers[id];
  if (!offer) return { ok: false, error: `No recovery offer for id=${id}` };

  function fire(el) {
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    if (window.jQuery) window.jQuery(el).trigger('change').trigger('chosen:updated');
  }

  function setText(selector, value) {
    const el = document.querySelector(selector);
    if (!el) return false;
    el.focus();
    if ('value' in el) el.value = value;
    el.innerHTML = value;
    el.textContent = value;
    fire(el);
    return true;
  }

  function setStorage(editorSelector, storageSelector, value) {
    const ok = setText(editorSelector, value);
    const storage = document.querySelector(storageSelector);
    if (storage) {
      storage.value = value;
      fire(storage);
    }
    return ok || Boolean(storage);
  }

  function setHtml(textareaSelector, html) {
    const textarea = document.querySelector(textareaSelector);
    if (!textarea) return false;
    const editor = textarea.previousElementSibling;
    if (editor && editor.classList.contains('trumbowyg-editor')) {
      editor.focus();
      editor.innerHTML = html;
      fire(editor);
    }
    textarea.value = html;
    fire(textarea);
    return true;
  }

  function setSelectValue(selector, value) {
    const select = document.querySelector(selector);
    if (!select) return false;
    select.value = String(value);
    if (window.jQuery) window.jQuery(select).val(String(value));
    fire(select);
    return true;
  }

  function setCheckbox(selector, checked) {
    const el = document.querySelector(selector);
    if (!el) return false;
    el.checked = checked;
    if (checked) el.setAttribute('checked', 'checked');
    else el.removeAttribute('checked');
    fire(el);
    return true;
  }

  function setTextLike(el, value) {
    el.focus();
    if ('value' in el) el.value = value;
    el.innerHTML = value;
    el.textContent = value;
    fire(el);
  }

  function setExtra(index, name, description, price, days) {
    const names = Array.from(document.querySelectorAll('[name="my_extras_name[]"]'));
    const descs = Array.from(document.querySelectorAll('[name="my_extras_description[]"]'));
    const prices = Array.from(document.querySelectorAll('[name="my_extras_price[]"]'));
    const durations = Array.from(document.querySelectorAll('[name="my_extras_duration[]"]'));
    const nameInput = names[index];
    const descInput = descs[index];
    if (!nameInput || !descInput) return false;

    nameInput.value = name;
    descInput.value = description;
    fire(nameInput);
    fire(descInput);

    const nameEditor = nameInput.previousElementSibling;
    const descEditor = descInput.previousElementSibling;
    if (nameEditor) setTextLike(nameEditor, name);
    if (descEditor) setTextLike(descEditor, description);

    const priceSelect = prices[index];
    if (priceSelect) {
      priceSelect.value = String(price);
      if (window.jQuery) window.jQuery(priceSelect).val(String(price));
      fire(priceSelect);
    }
    const durationSelect = durations[index];
    if (durationSelect) {
      durationSelect.value = String(days);
      if (window.jQuery) window.jQuery(durationSelect).val(String(days));
      fire(durationSelect);
    }
    return true;
  }

  const results = {
    id,
    title: setStorage('#editor-title', '#step1-name', offer.title),
    description: setHtml('#step1-description', offer.description),
    instruction: setHtml('#step1-instruction', offer.instruction),
    serviceSize: setStorage('#editor-service_size', '#step2-service-size', offer.serviceSize),
    volume: setText('#step2-volume', '1'),
    singlePackage: setCheckbox('#bundle-switch', false),
    priceMain: setSelectValue('#typicalPriceSelect', offer.price),
    minVolumePrice: setSelectValue('#min_volume_price', offer.price),
    time: setSelectValue('#step2-work-time', offer.time),
    extraOne: setExtra(0, ...offer.extras[0]),
    extraTwo: setExtra(1, ...offer.extras[1]),
    extraThree: setExtra(2, 'Дополнительная правка', 'Добавлю одну небольшую правку после согласования объема.', 1500, 1),
  };

  setCheckbox('#bundle-switch', false);
  setSelectValue('#typicalPriceSelect', offer.price);
  setSelectValue('#min_volume_price', offer.price);
  setSelectValue('#step2-work-time', offer.time);

  return results;
})()
