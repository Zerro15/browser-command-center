(() => {
  const title = 'Настрою CI/CD, Docker и автодеплой для вашего проекта';
  const description = `<p>Настрою CI/CD и Docker-процессы под ваш проект так, чтобы сборка, тесты и деплой работали стабильно и без ручной рутины.</p><p><strong>Что вы получите:</strong></p><p>• CI/CD пайплайн под ваш стек: GitHub Actions, GitLab CI или Jenkins</p><p>• Docker / Docker Compose для локального и серверного запуска</p><p>• Автосборку, проверку и при необходимости автодеплой</p><p>• Понятную структуру файлов конфигурации и инструкцию по использованию</p><p><strong>С чем работаю:</strong></p><p>• Linux, Docker, Git</p><p>• C++, Python, Bash, Node.js-проекты</p><p>• VPS, облака, staging / production окружения</p><p><strong>Дополнительно могу:</strong></p><p>• подключить тесты в пайплайн</p><p>• настроить деплой на сервер</p><p>• помочь разобраться в текущем пайплайне и убрать узкие места</p><p>Подходит, если вам нужно быстро запустить надёжный процесс сборки и выката без хаоса и ручных действий.</p>`;
  const instruction = `<p>Ссылка на репозиторий или архив проекта</p><p>Что нужно автоматизировать: сборка, тесты, деплой или всё вместе</p><p>Какой стек и где будет запуск: Linux, Docker, VPS, облако</p><p>Есть ли уже текущий CI/CD или всё делаем с нуля</p><p>Нужен ли доступ к серверу, staging или production</p><p>Особые требования: GitHub Actions, GitLab CI, Jenkins, Docker Compose и т.д.</p>`;
  const standard = 'Настрою базовый CI/CD для сборки, проверки или деплоя одного сервиса.';
  const medium = 'CI/CD + Docker + автоматизация тестов и сборки для одного проекта.';
  const premium = 'CI/CD + Docker + автодеплой + тесты + инструкция по запуску под ключ.';

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
