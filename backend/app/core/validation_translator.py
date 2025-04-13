FIELD_LABELS = {
    "full_name": "ФИО",
    "iin": "ИИН",
    "phone": "Телефон",
    "email": "Email",
    "password": "Пароль",
    "confirm_password": "Подтверждение пароля",
    "referred_by": "Реферальный код",
    "referred_use": "Флаг использования рефералки",
    "money": "Сумма",
}

def translate_error_ru(errors: list[dict]) -> str:
    translations = {
        "string_too_short": "Поле «{field}» — слишком короткое значение. Минимум {min_length} символов.",
        "string_too_long": "Поле «{field}» — слишком длинное значение. Максимум {max_length} символов.",
        "value_error.missing": "Поле «{field}» обязательно для заполнения.",
        "type_error.email": "Поле «{field}» должно быть корректным email.",
        "value_error.any_str.min_length": "Поле «{field}» — минимум {min_length} символов.",
        "value_error.any_str.max_length": "Поле «{field}» — максимум {max_length} символов.",
        "value_error.number.not_ge": "Поле «{field}» — значение должно быть не меньше {ge}.",
        "value_error.number.not_le": "Поле «{field}» — значение должно быть не больше {le}.",
        "value_error": "Поле «{field}» — некорректное значение.",
        "type_error.integer": "Поле «{field}» — должно быть целым числом.",
        "type_error.string": "Поле «{field}» — должно быть строкой.",
        "type_error.dict": "Поле «{field}» — ожидается словарь.",
        "type_error.list": "Поле «{field}» — ожидается список.",
        "value_error.email": "Поле «{field}» — неверный формат email.",
    }
    messages = []
    for err in errors:
        err_type = err.get("type")
        field_key = str(err.get("loc", ["поле"])[-1])
        field_name = FIELD_LABELS.get(field_key, field_key.capitalize())
        msg_template = translations.get(err_type, err.get("msg", "Ошибка ввода"))
        ctx = err.get("ctx", {})
        try:
            message = msg_template.format(field=field_name, **ctx)
        except Exception:
            message = f"Поле «{field_name}» — некорректное значение."
        messages.append(message)
    return "; ".join(messages)

