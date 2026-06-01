(() => {
  const offers = {
    sheets: {
      title: 'Автоматизирую Google Sheets, отчеты и Telegram',
      typeId: '7352',
      cover: '46004001-smartsender-capi.png',
      description: `<p>Настрою автоматизацию Google Sheets, отчетов, заявок и уведомлений в Telegram.</p>
<p><strong>Что могу сделать:</strong></p>
<p>• заявки из формы или сайта в Google Sheets</p>
<p>• автоматические отчеты и сводные таблицы</p>
<p>• уведомления в Telegram при новых строках или статусах</p>
<p>• обработку CSV/Excel и загрузку в таблицу</p>
<p>• простые скрипты Google Apps Script или Python</p>
<p>• связку таблицы с API, CRM или ботом</p>
<p>Подходит, если вы ведете данные руками и хотите, чтобы часть рутины происходила автоматически.</p>`,
      instruction: `<p>Пришлите ссылку или пример таблицы без приватных данных.</p>
<p>Опишите, какие действия должны выполняться автоматически.</p>
<p>Укажите, откуда приходят данные и куда отправлять результат.</p>
<p>Напишите, нужен ли Telegram, API, CRM, форма или расписание.</p>
<p>Доступы передавайте только внутри заказа.</p>`,
      serviceSize: '1 автоматизация Google Sheets или отчетов',
    },
    excel: {
      title: 'Обработаю Excel CSV, отчеты, базы и таблицы',
      typeId: '7352',
      cover: '45979524-telegram-docx-csv.png',
      description: `<p>Помогу обработать Excel, CSV, JSON или другие таблицы: очистить, объединить, преобразовать, найти ошибки и подготовить отчет.</p>
<p><strong>Примеры задач:</strong></p>
<p>• объединить несколько файлов в один</p>
<p>• удалить дубли, мусор, пустые строки и неправильные значения</p>
<p>• привести данные к нужному формату</p>
<p>• сделать фильтры, группировки и сводный отчет</p>
<p>• подготовить файл для загрузки в CRM, магазин или сервис</p>
<p>• написать повторяемый скрипт обработки</p>
<p>Если задача повторяется регулярно, сделаю скрипт, чтобы вы могли запускать обработку сами.</p>`,
      instruction: `<p>Пришлите пример файла или небольшую тестовую выборку.</p>
<p>Опишите, что именно нужно получить на выходе.</p>
<p>Укажите формат результата: XLSX, CSV, JSON, Google Sheets.</p>
<p>Напишите, разовая это задача или нужна регулярная обработка.</p>
<p>Если есть эталонный пример результата, приложите его.</p>`,
      serviceSize: '1 обработка файла или один сценарий обработки',
    },
    browser: {
      title: 'Настрою браузерную автоматизацию сайта или кабинета',
      typeId: '7352',
      cover: '27194497-cicd-docker-devops.png',
      description: `<p>Сделаю автоматизацию действий в браузере: открыть сайт, авторизоваться вручную, собрать данные, нажать кнопки, заполнить формы или проверить состояние страниц.</p>
<p><strong>Что можно автоматизировать:</strong></p>
<p>• регулярную проверку сайта или личного кабинета</p>
<p>• сбор данных со страниц в таблицу</p>
<p>• заполнение однотипных форм</p>
<p>• скриншоты и отчеты по страницам</p>
<p>• тестовый сценарий для сайта</p>
<p>• локальный инструмент на Playwright/Puppeteer/CDP</p>
<p>Не занимаюсь обходом капчи, взломом, спамом и действиями против правил сервиса. Если сайт просит ручной вход, можно сделать сценарий с ручным входом и дальнейшей автоматизацией.</p>`,
      instruction: `<p>Пришлите ссылку на сайт и опишите нужный сценарий действий.</p>
<p>Укажите, нужен ли сбор данных, скриншоты, заполнение форм или проверка.</p>
<p>Напишите, есть ли авторизация, капча, ограничения или антибот.</p>
<p>Покажите пример результата: файл, таблица, отчет или скриншот.</p>
<p>Доступы передавайте только внутри заказа и только если они нужны.</p>`,
      serviceSize: '1 браузерный сценарий автоматизации',
    },
  };

  const key = new URL(location.href).searchParams.get('offer') || sessionStorage.getItem('newKworkOffer') || 'sheets';
  const offer = offers[key];
  if (!offer) return { ok: false, error: `Unknown offer: ${key}` };

  function fire(el) {
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    if (window.jQuery) window.jQuery(el).trigger('change').trigger('chosen:updated');
  }

  function setTextField(selector, value) {
    const el = document.querySelector(selector);
    if (!el) return false;
    el.focus();
    if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') el.value = value;
    else {
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

  const type = document.querySelector(`#attribute_item_${offer.typeId}`);
  if (type) {
    type.checked = true;
    type.setAttribute('checked', 'checked');
    fire(type);
  }

  const price = document.querySelector('#min_volume_price');
  if (price) {
    price.value = '3000';
    fire(price);
  }
  const time = document.querySelector('#step2-work-time');
  if (time) {
    time.value = '2';
    fire(time);
  }

  return {
    ok: true,
    key,
    title: setTextField('#editor-title', offer.title),
    description: setTrumbowyg('#step1-description', offer.description),
    instruction: setTrumbowyg('#step1-instruction', offer.instruction),
    serviceSize: setTextField('#editor-service_size', offer.serviceSize) && setTextField('#step2-service-size', offer.serviceSize),
    volume: setTextField('#step2-volume', '1'),
    category: { parent: parent?.value || null, sub: sub?.value || null },
    type: type?.checked || false,
    cover: offer.cover,
  };
})()
