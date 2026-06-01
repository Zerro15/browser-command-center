(() => {
  const offers = {
    51213284: {
      title: 'Подключу OpenAI GPT к сайту, боту или CRM',
      typeId: '4158112',
      serviceSize: '1 AI-интеграция или рабочий сценарий',
      standard: 'Подключу AI к одному месту: бот, сайт, CRM или таблица.',
      medium: 'AI + webhook/API + обработка ошибок и тесты на ваших примерах.',
      premium: 'AI-сценарий под ключ: логика, интеграции, деплой и инструкция.',
      prices: [4000, 8000, 16000],
      time: 3,
      description: `<p>Подключу OpenAI/GPT или совместимый AI API к вашему сайту, Telegram-боту, CRM, Google Sheets или внутреннему сервису.</p><p><strong>Что можно сделать:</strong> AI-ответы клиентам, анализ заявок и сообщений, генерация текстов и отчетов, классификация обращений, webhook/API-интеграция, настройка роли и правил ответа.</p><p><strong>Почему удобно:</strong> сначала фиксируем один понятный сценарий, затем делаю рабочий прототип, проверяю на ваших примерах и оставляю инструкцию.</p><p>Могу работать с OpenAI, OpenRouter, Gemini и совместимыми API. Стоимость сторонних API оплачивается отдельно.</p>`,
      instruction: `<p>Опишите, куда подключить AI: сайт, бот, CRM, таблица или другой сервис.</p><p>Пришлите пример входных данных и желаемого результата.</p><p>Укажите API, доступы, ограничения ответа и нужен ли сервер.</p>`,
    },
    40740429: {
      title: 'Создам Telegram-бота с AI, GPT или OpenAI под ключ',
      typeId: '4158112',
      serviceSize: '1 Telegram-бот или один сценарий бота',
      standard: 'Базовый Telegram-бот: меню, команды, заявки или FAQ.',
      medium: 'Telegram-бот + AI/GPT, база или Google Sheets/CRM.',
      premium: 'Бот под ключ: AI, интеграции, сервер, инструкция и правки.',
      prices: [4000, 9600, 20000],
      time: 4,
      description: `<p>Разработаю Telegram-бота под задачу бизнеса: заявки, поддержка, FAQ, продажи, запись, внутренний помощник или AI-консультант.</p><p><strong>Могу сделать:</strong> меню и кнопки, сценарии диалога, подключение OpenAI/GPT/Gemini/OpenRouter, прием заявок, уведомления администратору, хранение данных, Google Sheets, CRM, сайт, webhook и запуск на сервере.</p><p>Работаю по этапам: уточняю сценарий, собираю рабочий минимальный вариант, показываю результат и дорабатываю в рамках согласованного объема.</p>`,
      instruction: `<p>Опишите сценарий бота и кто им будет пользоваться.</p><p>Пришлите список команд, кнопок, пример диалога и токен BotFather.</p><p>Укажите, нужны ли AI, база, админка, Sheets, CRM, оплата или сервер.</p>`,
    },
    45979524: {
      title: 'Напишу Python-парсер, скрипт или автоматизацию рутины',
      typeId: '7352',
      serviceSize: '1 скрипт, парсер или сценарий обработки',
      standard: 'Простой скрипт или парсер одного источника с выгрузкой в файл.',
      medium: 'Парсер/автоматизация с фильтрами, обработкой и уведомлениями.',
      premium: 'Сложная автоматизация: несколько источников, API, расписание.',
      prices: [4000, 8000, 16000],
      time: 3,
      description: `<p>Сделаю Python-скрипт для сбора данных, обработки файлов, автоматизации сайта, отчетов или повторяющихся действий.</p><p><strong>Примеры:</strong> парсинг товаров, цен, контактов и карточек; Excel/CSV/JSON/XML; проверка сайтов и кабинетов; отчеты; загрузка и сортировка файлов; Telegram-уведомления; простые API-интеграции.</p><p>В базовый объем входит один понятный сценарий: входные данные, обработка и результат. Не беру взлом, спам, обход приватных данных и незаконный сбор информации.</p>`,
      instruction: `<p>Пришлите ссылку на сайт или пример файла.</p><p>Опишите, какие данные нужны и в каком формате: XLSX, CSV, JSON, Sheets.</p><p>Напишите, нужен разовый запуск или регулярная автоматизация.</p>`,
    },
    46004001: {
      title: 'Настрою интеграцию API, webhook, CRM, Telegram или Sheets',
      typeId: '7352',
      serviceSize: '1 интеграция API или webhook-сценарий',
      standard: 'Одна простая интеграция: API, webhook или отправка данных.',
      medium: 'Интеграция двух сервисов с проверкой ошибок и уведомлениями.',
      premium: 'Цепочка API + Telegram/Sheets/CRM + серверная настройка.',
      prices: [5600, 12000, 24000],
      time: 4,
      description: `<p>Свяжу сервисы между собой, чтобы данные передавались автоматически без ручного копирования.</p><p><strong>Примеры:</strong> заявка с сайта уходит в Telegram и Google Sheets; CRM уведомляет менеджера; webhook принимает данные и передает дальше; бот создает заявку; OpenAI анализирует текст; один API передает данные в другой.</p><p>В работу входит разбор API-документации, настройка запросов, обработка ответа, базовые ошибки, логика сценария и инструкция.</p>`,
      instruction: `<p>Напишите, какие сервисы нужно связать.</p><p>Опишите вход, выход и приложите ссылку на API-документацию.</p><p>Укажите, нужны ли Telegram, Sheets, CRM, OpenAI, webhook или сервер.</p>`,
    },
    45587052: {
      title: 'Исправлю ошибку и доработаю скрипт, бота или парсер',
      typeId: '7352',
      serviceSize: '1 ошибка или небольшая доработка кода',
      standard: 'Диагностика и небольшое исправление одной ошибки.',
      medium: 'Исправление + доработка команды, выгрузки или интеграции.',
      premium: 'Глубокая доработка: несколько ошибок, запуск и инструкция.',
      prices: [2800, 6400, 12000],
      time: 2,
      description: `<p>Найду причину ошибки и доработаю существующий код: Python/JavaScript-скрипт, Telegram-бот, парсер, интеграцию, небольшой сайт или локальный инструмент.</p><p><strong>Могу:</strong> исправить запуск, обновить зависимости, починить парсер после изменения сайта, добавить команду или выгрузку, подключить API/Telegram/Sheets, настроить окружение и написать инструкцию запуска.</p><p>Сначала смотрю ошибку и код, затем фиксирую реальный объем. Большие задачи предлагаю делать этапами.</p>`,
      instruction: `<p>Пришлите архив проекта или ссылку на репозиторий.</p><p>Приложите текст ошибки, лог или скриншот.</p><p>Опишите, что должно работать после исправления и какие файлы нельзя трогать.</p>`,
    },
    27194497: {
      title: 'Сделаю мини-сайт, личный кабинет или веб-инструмент',
      typeId: '7352',
      serviceSize: '1 веб-инструмент или рабочий экран',
      standard: 'Простой веб-инструмент или форма с одним сценарием.',
      medium: 'Мини-сервис с хранением данных, Telegram/API и интерфейсом.',
      premium: 'Кабинет/панель под ключ: роли, база, интеграции, деплой.',
      prices: [5600, 12000, 24000],
      time: 5,
      description: `<p>Разработаю небольшой рабочий веб-инструмент: форму, панель, личный кабинет, калькулятор, генератор, мини-CRM или внутренний сервис.</p><p><strong>Примеры:</strong> форма заявки с отправкой в Telegram или таблицу, мини-CRM, кабинет клиента, генератор документов или отчетов, панель управления ботом, калькулятор стоимости, прототип сервиса.</p><p>Делаю не просто страницу, а рабочий инструмент. Авторизация, база, роли, платежи, API и деплой оцениваются отдельно.</p>`,
      instruction: `<p>Опишите, что пользователь должен делать на странице.</p><p>Пришлите поля, кнопки, данные и пример похожего интерфейса.</p><p>Укажите, нужны ли вход, роли, база, Telegram, API, админка или сервер.</p>`,
    },
    51213619: {
      title: 'Автоматизирую Google Sheets, отчеты и Telegram',
      typeId: '7352',
      serviceSize: '1 автоматизация таблицы или отчета',
      standard: 'Одна автоматизация Google Sheets или простой отчет.',
      medium: 'Sheets + Telegram/API + обработка данных и статусов.',
      premium: 'Система отчетов: Sheets, скрипты, API, расписание, инструкция.',
      prices: [3200, 7200, 16000],
      time: 3,
      description: `<p>Настрою автоматизацию Google Sheets, отчетов, заявок и уведомлений в Telegram.</p><p><strong>Могу сделать:</strong> заявки из формы или сайта в таблицу, автоматические отчеты, уведомления при новых строках и статусах, обработку CSV/Excel, Apps Script или Python-скрипт, связку таблицы с API, CRM или ботом.</p><p>Подходит, если данные ведутся руками и нужно убрать повторяющуюся рутину.</p>`,
      instruction: `<p>Пришлите ссылку или пример таблицы без приватных данных.</p><p>Опишите, какие действия должны выполняться автоматически.</p><p>Укажите источник данных, результат, Telegram, API, CRM, форму или расписание.</p>`,
    },
    51213975: {
      title: 'Обработаю Excel CSV, отчеты, базы и таблицы',
      typeId: '7352',
      serviceSize: '1 файл или один сценарий обработки',
      standard: 'Очистка, объединение или преобразование одного набора файлов.',
      medium: 'Обработка + сводный отчет, фильтры и повторяемый скрипт.',
      premium: 'Регулярная обработка: много файлов, правила, отчет и инструкция.',
      prices: [2400, 5600, 12000],
      time: 2,
      description: `<p>Обработаю Excel, CSV, JSON или другие таблицы: очищу, объединю, преобразую, найду ошибки и подготовлю отчет.</p><p><strong>Примеры:</strong> объединить файлы, удалить дубли и мусор, привести данные к формату, сделать фильтры и группировки, подготовить файл для CRM/магазина/сервиса, написать повторяемый скрипт обработки.</p><p>Если задача повторяется регулярно, сделаю так, чтобы вы могли запускать обработку сами.</p>`,
      instruction: `<p>Пришлите пример файла или тестовую выборку.</p><p>Опишите, что нужно получить на выходе.</p><p>Укажите формат результата: XLSX, CSV, JSON, Google Sheets, и приложите эталон, если есть.</p>`,
    },
    51214672: {
      title: 'Настрою браузерную автоматизацию сайта или кабинета',
      typeId: '7352',
      serviceSize: '1 браузерный сценарий автоматизации',
      standard: 'Один сценарий: открыть страницы, собрать данные или сделать отчет.',
      medium: 'Автоматизация с авторизацией вручную, файлами и уведомлениями.',
      premium: 'Сложный сценарий: Playwright/Puppeteer, отчеты, расписание.',
      prices: [4000, 9600, 20000],
      time: 4,
      description: `<p>Сделаю автоматизацию действий в браузере: открыть сайт, собрать данные, нажать кнопки, заполнить формы, сделать скриншоты или проверить состояние страниц.</p><p><strong>Что можно автоматизировать:</strong> проверку сайта или кабинета, сбор данных в таблицу, однотипные формы, скриншоты и отчеты, тестовый сценарий, локальный инструмент на Playwright/Puppeteer/CDP.</p><p>Не занимаюсь обходом капчи, взломом, спамом и действиями против правил сервиса. Если нужен ручной вход, можно сделать сценарий после ручной авторизации.</p>`,
      instruction: `<p>Пришлите ссылку на сайт и сценарий действий.</p><p>Укажите, нужен сбор данных, скриншоты, формы или проверка.</p><p>Напишите про авторизацию, капчу, ограничения и покажите пример результата.</p>`,
    },
  };

  const id = new URL(location.href).searchParams.get('id');
  const offer = offers[id];
  if (!offer) return { ok: false, error: `No profit offer for id=${id}` };

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
    const a = setText(editorSelector, value);
    const storage = document.querySelector(storageSelector);
    if (storage) {
      storage.value = value;
      fire(storage);
    }
    return a || Boolean(storage);
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

  function setSelectByRubles(selector, rubles) {
    const select = document.querySelector(selector);
    if (!select) return false;
    const wanted = String(rubles);
    const options = Array.from(select.options);
    const match = options.find((option) => option.textContent.replace(/\D/g, '') === wanted)
      || options.find((option) => option.value === wanted);
    if (!match) return false;
    select.value = match.value;
    if (window.jQuery) window.jQuery(select).val(match.value);
    fire(select);
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

  function grossValue(netRubles) {
    return String(Math.round(Number(netRubles) * 1.25));
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
      const match = Array.from(priceSelect.options).find((option) => option.textContent.replace(/\D/g, '') === String(price));
      if (match) priceSelect.value = match.value;
      fire(priceSelect);
    }
    const durationSelect = durations[index];
    if (durationSelect) {
      durationSelect.value = String(days);
      fire(durationSelect);
    }
    return true;
  }

  function setTextLike(el, value) {
    el.focus();
    if ('value' in el) el.value = value;
    el.innerHTML = value;
    el.textContent = value;
    fire(el);
  }

  // Do not reset category/attributes for existing kworks. Kwork reloads the
  // price block asynchronously after category changes and can revert prices.

  const results = {
    id,
    title: setStorage('#editor-title', '#step1-name', offer.title),
    description: setHtml('#step1-description', offer.description),
    instruction: setHtml('#step1-instruction', offer.instruction),
    serviceSize: setStorage('#editor-service_size', '#step2-service-size', offer.serviceSize),
    volume: setText('#step2-volume', '1'),
    bundle: setCheckbox('#bundle-switch', false),
    standard: setStorage('#editor-bundle-standard-description', '#bundle-standard-description', offer.standard),
    medium: setStorage('#editor-bundle-medium-description', '#bundle-medium-description', offer.medium),
    premium: setStorage('#editor-bundle-premium-description', '#bundle-premium-description', offer.premium),
    minVolumePrice: setSelectValue('#min_volume_price', grossValue(offer.prices[0])),
    priceMain: setSelectByRubles('#typicalPriceSelect', offer.prices[0]),
    priceStandard: setSelectByRubles('#priceStandardSelect', offer.prices[0]),
    priceMedium: setSelectByRubles('#priceMediumSelect', offer.prices[1]),
    pricePremium: setSelectByRubles('#pricePremiumSelect', offer.prices[2]),
    time: setSelectValue('#step2-work-time', offer.time),
    standardDays: setSelectValue('#bundle-standard-days', offer.time),
    mediumDays: setSelectValue('#bundle-medium-days', Math.min(offer.time + 2, 30)),
    premiumDays: setSelectValue('#bundle-premium-days', Math.min(offer.time + 5, 30)),
    extraRush: setExtra(0, 'Срочное выполнение', 'Приоритетная работа по задаче после согласования объема.', 4000, 1),
    extraDeploy: setExtra(1, 'Запуск на сервере', 'Помогу развернуть результат на VPS или хостинге заказчика.', 8000, 1),
  };

  setSelectByRubles('#typicalPriceSelect', offer.prices[0]);
  setSelectByRubles('#priceStandardSelect', offer.prices[0]);
  setSelectByRubles('#priceMediumSelect', offer.prices[1]);
  setSelectByRubles('#pricePremiumSelect', offer.prices[2]);
  setSelectValue('#step2-work-time', offer.time);
  setCheckbox('#bundle-switch', false);

  return results;
})()
