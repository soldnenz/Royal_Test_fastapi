# Отключение 2FA

## Как отключить 2FA в production

2FA теперь управляется через переменную окружения `REQUIRE_2FA` в файле `.env`.

### Шаг 1: Отредактируйте .env файл

В вашем `.env` файле для production окружения добавьте или измените:

```env
REQUIRE_2FA=false
```

### Шаг 2: Перезапустите backend

```bash
docker-compose -f docker-compose.prod.yml restart backend
```

## Настройки

- `REQUIRE_2FA=false` - 2FA **отключена** (по умолчанию)
- `REQUIRE_2FA=true` - 2FA **включена** (требуется при смене IP или User-Agent)

## Проверка

После перезапуска проверьте логи:

```bash
docker logs royal_backend_prod --tail 50 | grep -i "2fa\|two_factor"
```

Если 2FA отключена, вы не увидите сообщений о "Требуется 2FA".

## Важно!

⚠️ **Безопасность**: Отключение 2FA снижает уровень безопасности админ-панели.
Рекомендуется использовать другие методы защиты:
- Сильные пароли
- VPN доступ
- IP whitelist в nginx
- Rate limiting
