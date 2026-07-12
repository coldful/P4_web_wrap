# P4 Web Wrap

`P4_web_wrap-main` объединяет три части:

- `P4_web` - backend на FastAPI.
- `P4_web_client` - простой browser client.
- `P4_legacy_runner` - адаптер для запуска legacy-операций из `P4_app`.

Ниже описан запуск на новой машине с нуля.

## Что должно быть установлено

- Linux/macOS shell c `bash`
- `python3` версии 3.12 или новее
- `python3-venv`
- `docker`

Также рядом с этой папкой должен лежать legacy-проект `P4_app`, потому что
`run_p4_stack.sh` по умолчанию ищет его здесь:

```text
../P4_app/interface.py
```

Пример структуры:

```text
wp4/
├── P4_app/
└── P4_web_wrap-main/
```

## Подготовка окружения для `run_p4_stack.sh`

Из корня `P4_web_wrap-main`:

```bash
chmod +x ./prepare_p4_stack.sh ./run_p4_stack.sh
./prepare_p4_stack.sh
```

`prepare_p4_stack.sh`:

- создаёт `P4_web/venv`
- ставит Python-зависимости из `requirements.txt`
- создаёт `P4_web/.env` из шаблона, если файла ещё нет
- инициализирует SQLite-базу через `p4web init-db`
- проверяет, что рядом доступен `P4_app` и работает Docker

После этого wrapper готов к запуску через `run_p4_stack.sh`.

## Быстрый запуск полного стека

Из корня `P4_web_wrap-main`:

```bash
./prepare_p4_stack.sh
./run_p4_stack.sh
```

После запуска будут доступны:

- frontend: `http://127.0.0.1:5173`
- reduced frontend: `http://127.0.0.1:5173/reduced/`
- backend API: `http://127.0.0.1:8000`
- OpenAPI: `http://127.0.0.1:8000/docs`
- health check: `http://127.0.0.1:8000/api/health`

Остановка: `Ctrl+C` в том же терминале, где запущен `run_p4_stack.sh`.

## Что делает этот запуск

`run_p4_stack.sh`:

- находит `uvicorn` в `P4_web/venv`, `P4_web/.venv` или в `PATH`
- собирает Docker image для `P4_legacy_runner`
- на Linux запускает legacy runner c `--network=host`, а на macOS автоматически
  переключается на обычную Docker bridge-сеть
- если frontend или backend уже слушают целевые порты, останавливает их и
  запускает заново
- поднимает backend на `127.0.0.1:8000`
- поднимает frontend на `127.0.0.1:5173`

Если нужно принудительно переопределить режим сети для legacy runner:

```bash
P4_STACK_LEGACY_DOCKER_NETWORK_MODE=bridge ./run_p4_stack.sh
```

Поддерживаемые значения: `auto`, `host`, `bridge`.

Если base image для `P4_legacy_runner` недоступен из текущей сети, можно
переопределить его без редактирования `Dockerfile`:

```bash
P4_STACK_LEGACY_BASE_IMAGE=my-registry/heinz_p4:latest ./run_p4_stack.sh
```

По умолчанию используется `s.egorkin/heinz_p4:latest`. Если этот registry не
доступен, сборка legacy runner не стартует, пока не будет указан рабочий образ.

## Если нужен только backend + frontend без legacy

Этот вариант полезен, если хочется просто открыть web UI и API без запуска
legacy-команд через Docker.

```bash
python3 -m venv P4_web/venv
P4_web/venv/bin/pip install -r requirements.txt
cp P4_web/.env.example P4_web/.env
cd P4_web
./venv/bin/p4web init-db
./venv/bin/uvicorn p4_web.main:app --host 127.0.0.1 --port 8000
```

Во втором терминале:

```bash
cd P4_web_client
python3 -m http.server 5173 --bind 127.0.0.1
```

В этом режиме UI и API работают, но операции, которым нужен legacy runner,
не будут выполняться автоматически через `run_p4_stack.sh`.

## Файлы и настройки

- Общие Python-зависимости wrapper'а описаны в [requirements.txt](requirements.txt).
- Базовая конфигурация backend лежит в [P4_web/.env.example](P4_web/.env.example).
- По умолчанию backend использует SQLite:
  `sqlite+aiosqlite:///./var/p4_web.db`
- Локальные данные backend пишет в `P4_web/var/`.


## Деплой на production

Один раз настроить:

```bash
cp deploy/config.env.example deploy/config.env
# указать P4_DEPLOY_HOST и пути на сервере
```

Полный деплой синхронизирует frontend (включая `/reduced/`), backend,
`pyproject.toml`, legacy runner, пересобирает Docker-образ и проверяет health.

### A. Прямой деплой (рекомендуется)

```bash
./deploy/deploy.sh
```

### B. SFTP + staging

Однократно на сервере:

```bash
sudo ./deploy/setup_server.sh
```

Загрузка через SFTP (пользователь `p4deploy`, каталог `/updates/`), затем:

```bash
/srv/p4/bin/apply-update all
```

Или с рабочей машины:

```bash
./deploy/push_update.sh all
```

Частичный деплой:

```bash
./deploy/deploy.sh frontend
./deploy/deploy.sh backend
./deploy/deploy.sh legacy
```

Файл `.env` на сервере не перезаписывается.

Для nginx используйте [deploy/nginx-p4.conf.example](deploy/nginx-p4.conf.example).
Импорт папки проекта требует `client_max_body_size` больше стандартного 1 MB.


## Частые проблемы

### Импорт папки проекта на сервере (`NetworkError`)

Браузер отправляет всю выбранную папку на `POST /api/sync/import-upload`.

1. **Лимит nginx** — по умолчанию `client_max_body_size` = 1 MB. Маленькие проекты
   проходят, большие — нет. Исправление:

   ```bash
   ./deploy/deploy.sh nginx
   ```

2. **Неверный API URL** — на сервере должен быть `http://IP_СЕРВЕРА/api`, не
   `http://localhost:8000/api`. Очистите localStorage:

   ```javascript
   localStorage.removeItem('p4web.client.apiBase');
   location.reload();
   ```

### `Missing required path: ../P4_app/interface.py`

Скрипт не нашёл legacy-папку `P4_app` рядом с wrapper-проектом. Проверь
структуру директорий или задай переменную:

```bash
P4_STACK_LEGACY_APP_DIR=/abs/path/to/P4_app ./run_p4_stack.sh
```

### `Missing uvicorn`

Не создано виртуальное окружение или не установлены Python-зависимости.
Запусти `./prepare_p4_stack.sh`.

### Порт `8000` или `5173` уже занят

По умолчанию `run_p4_stack.sh` сам остановит старый listener на этом порту и
поднимет новый. Если нужен параллельный запуск, задай другие порты:

```bash
P4_STACK_BACKEND_PORT=8001 P4_STACK_FRONTEND_PORT=5174 ./run_p4_stack.sh
```

### Docker не запускается

Проверь, что daemon Docker поднят и текущий пользователь имеет право его
использовать.
