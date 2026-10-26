# Деплой на VPS (этап 2)

Бот работает одним контейнером Docker на VPS в РФ (ADR-12, ADR-16): long polling, входящие порты не нужны. Деплой ручной: заходите на сервер по SSH и обновляете код командой `git pull && docker compose up -d --build`.

В репозитории нет адреса сервера, токенов и паролей. Ниже `<...>` — значения, которые подставляете вы.

## 1. Выбор VPS

Требования:

- дата-центр **в РФ** — первичная база с персональными данными обязана лежать на территории РФ (ADR-07);
- 1 vCPU, 1–2 ГБ RAM, 10–20 ГБ SSD — для 50 брифов в сутки хватает с запасом;
- Ubuntu 24.04 LTS, вход по SSH-ключу, оплата в рублях.

Что сравнить у провайдеров (например, Timeweb Cloud, Selectel, Beget, REG.RU, VDSina): цену минимального тарифа, образ Ubuntu 24.04, SSH-ключ при создании сервера, пробный период или посуточную оплату, **доступ к `api.telegram.org` с этого сервера**. Цены и условия меняются, поэтому актуальные данные смотрите на сайтах провайдеров.

Последний пункт проверьте до оплаты на длительный срок: создайте самый дешёвый сервер и запустите проверку (раздел 3, шаг 1).

## 2. Первичная настройка сервера

Выполняется один раз. Под `root` или пользователем с `sudo`.

```bash
apt update && apt upgrade -y
adduser deploy                      # пароль можно задать любой, вход будет по ключу
usermod -aG sudo deploy
mkdir -p /home/deploy/.ssh && cp ~/.ssh/authorized_keys /home/deploy/.ssh/
chown -R deploy:deploy /home/deploy/.ssh && chmod 700 /home/deploy/.ssh
```

Откройте **второй** терминал и убедитесь, что `ssh deploy@<адрес сервера>` работает. Только после этого отключите вход root и по паролю:

```bash
sudo sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl restart ssh
```

Файрвол и автоматические обновления безопасности (бот сам портов не открывает):

```bash
sudo ufw allow OpenSSH && sudo ufw enable
sudo apt install -y unattended-upgrades && sudo dpkg-reconfigure -plow unattended-upgrades
```

Docker Engine и плагин Compose ставятся по официальной инструкции: <https://docs.docker.com/engine/install/ubuntu/>. После установки:

```bash
sudo systemctl enable docker
sudo usermod -aG docker deploy      # перезайдите по SSH, чтобы группа применилась
docker compose version
```

## 3. Первый деплой

Дальше — пользователь `deploy`.

**Шаг 1. Проверка доступности сервисов** (до установки бота, системный Python 3 уже есть в Ubuntu):

```bash
git clone https://github.com/vegorovmsk/brif_bot.git brief-bot
cd brief-bot
python3 tools/check_connectivity.py
```

`api.telegram.org` должен быть `OK`. Если `FAIL` — бот без прокси не заработает: задайте `TELEGRAM_PROXY` в `.env` (шаг 3) или выберите другого провайдера. `llm.api.cloud.yandex.net` нужен с этапа 3, Google и Яндекс Диск — с этапа 4.

**Шаг 2. Каталоги.** Контейнер работает не под root (uid 1000), поэтому каталог данных должен принадлежать этому пользователю, иначе SQLite не сможет писать:

```bash
mkdir -p data secrets
sudo chown 1000:1000 data
```

**Шаг 3. Конфигурация.** Создайте `.env` с правами только для владельца:

```bash
cp .env.example .env && chmod 600 .env
nano .env
```

Обязательно заполните:

| Переменная | Значение |
|---|---|
| `BOT_TOKEN` | токен **боевого** бота `@vegorovmsk_brief_bot` из @BotFather (не dev-бота) |
| `OWNER_TELEGRAM_ID`, `OWNER_CHAT_ID` | ваш числовой Telegram ID (узнать: @userinfobot); один раз нажмите `/start` у боевого бота, иначе он не сможет вам писать |
| `AUDIT_HASH_SALT` | случайная строка: `openssl rand -hex 32` |
| `PRIVACY_POLICY_URL` | адрес опубликованной политики (раздел 5) |
| `TELEGRAM_PROXY` | только если Telegram недоступен напрямую |

`ENV=prod` задаёт `docker-compose.yml`: логи будут в JSON.

**Шаг 4. Запуск.**

```bash
docker compose up -d --build
```

## 4. Проверка

```bash
docker compose ps                 # через ~1 минуту статус (healthy)
docker compose logs bot --tail 30 # миграция и «Run polling for bot @vegorovmsk_brief_bot»
```

В логах не должно быть токена. Затем:

1. Откройте `https://t.me/vegorovmsk_brief_bot?start=test` и пройдите бриф целиком с телефона.
2. В уведомлении должно быть «источник: test».
3. Перезапустите контейнер посреди диалога (`docker compose restart`) и продолжите — диалог должен идти с того же шага.

## 5. Профиль бота и политика конфиденциальности

**Профиль** (имя, описание, «О боте») берётся из `config/bot_profile.yaml`. Применяется к боту из `BOT_TOKEN`; скрипт сам покажет, к какому боту обращается, и попросит подтверждение. Локально, с установленным uv:

```bash
uv run python tools/setup_bot_profile.py --dry-run   # тексты и лимиты
BOT_TOKEN=<боевой токен> uv run python tools/setup_bot_profile.py
```

Аватар задаётся вручную: @BotFather → `/setuserpic`.

**Политика.** Откройте `docs/privacy_policy.md`, замените места `[ЗАПОЛНИТЬ: …]`, удалите плашку «ЧЕРНОВИК», опубликуйте на <https://telegra.ph>, вставьте адрес в `PRIVACY_POLICY_URL` на сервере и пересоздайте контейнер: `docker compose up -d --force-recreate`. Если текст политики меняется по существу, обновите и `CONSENT_VERSION`.

## 6. Обновление и откат

Обновление:

```bash
cd ~/brief-bot
git pull
docker compose up -d --build
docker compose ps
```

Перед обновлением с новыми миграциями сделайте копию БД (раздел 7). Откат:

```bash
git log --oneline -5
git checkout <коммит или тег>
docker compose up -d --build
```

Откат кода не откатывает схему БД: если миграция уже применилась, восстановите копию БД из раздела 7.

## 7. Ручной бэкап БД (до автоматических бэкапов этапа 5)

Копия без остановки бота (SQLite в режиме WAL, обычный `cp` ненадёжен):

```bash
docker compose exec bot python -c "
import sqlite3
src = sqlite3.connect('data/bot.db')
dst = sqlite3.connect('data/backup.db')
src.backup(dst)
"
mv data/backup.db data/backup-$(date +%Y%m%d).db
```

Скачайте файл на свой компьютер: `scp deploy@<адрес сервера>:brief-bot/data/backup-*.db .`.

Восстановление: `docker compose stop bot`, подменить `data/bot.db` копией (и удалить рядом `bot.db-wal`, `bot.db-shm`), `chown 1000:1000 data/bot.db`, `docker compose start bot`.

## 8. Диагностика

| Симптом | Причина и что делать |
|---|---|
| В логах `TelegramConflictError` | Тот же токен запущен ещё где-то (например, локально). У каждого окружения свой токен (ADR-12). Остановите лишний процесс |
| Статус `unhealthy` | Цикл событий завис или бот не стартовал: `docker compose logs bot --tail 100` |
| `permission denied` или `unable to open database file` | Каталог `data/` принадлежит не uid 1000: `sudo chown 1000:1000 data` |
| Бот молчит, в логах нет обновлений | Нет доступа к `api.telegram.org`: `python3 tools/check_connectivity.py`, при необходимости `TELEGRAM_PROXY` |
| Уведомление не приходит | Не задан `OWNER_CHAT_ID` или вы не нажимали `/start` у этого бота; в логах `owner_chat_id_not_set` |
| «Ошибка конфигурации» при старте | Не заполнен `BOT_TOKEN` или неверный формат переменной |

## 9. Безопасность

- `.env` и `secrets/` не попадают в git (`.gitignore`), права `.env` — `600`.
- Токен утёк: @BotFather → `/revoke`, новый токен в `.env`, `docker compose up -d --force-recreate`.
- Боевой и dev-токены разные; боевой токен не используют на своём компьютере.
- Входящих портов у бота нет, наружу открыт только SSH.

## Чек-лист владельца для приёмки этапа 2

- [ ] VPS в РФ арендован, `check_connectivity.py` показывает `OK` для Telegram
- [ ] Деплой с боевым токеном, `docker compose ps` — `healthy`
- [ ] Профиль бота применён, аватар задан в @BotFather
- [ ] Политика проверена, опубликована, `PRIVACY_POLICY_URL` задан
- [ ] `t.me/vegorovmsk_brief_bot?start=test` проходит весь сценарий, источник `test` в уведомлении
- [ ] Бот проработал 48 часов без вмешательства
