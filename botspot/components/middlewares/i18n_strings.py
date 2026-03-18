"""All botspot framework i18n strings (en/ru)."""

BOTSPOT_STRINGS: dict[str, dict[str, str]] = {
    # -- access_control --
    "access_control.add_friend_failed": {
        "en": "❌ Failed to get username. Operation cancelled.",
        "ru": "❌ Не удалось получить имя пользователя. Операция отменена.",
    },
    "access_control.add_friend_success": {
        "en": "✅ Successfully added {username} to friends list!",
        "ru": "✅ {username} успешно добавлен в список друзей!",
    },
    "access_control.add_friend_already_exists": {
        "en": "ℹ️ {username} is already in the friends list.",
        "ru": "ℹ️ {username} уже в списке друзей.",
    },
    "access_control.add_friend_error": {
        "en": "❌ Error adding friend: {error}",
        "ru": "❌ Ошибка добавления друга: {error}",
    },
    "access_control.remove_friend_failed": {
        "en": "❌ Failed to get username. Operation cancelled.",
        "ru": "❌ Не удалось получить имя пользователя. Операция отменена.",
    },
    "access_control.remove_friend_success": {
        "en": "✅ Successfully removed {username} from friends list!",
        "ru": "✅ {username} успешно удалён из списка друзей!",
    },
    "access_control.remove_friend_not_found": {
        "en": "ℹ️ {username} was not in the friends list.",
        "ru": "ℹ️ {username} не был в списке друзей.",
    },
    "access_control.remove_friend_error": {
        "en": "❌ Error removing friend: {error}",
        "ru": "❌ Ошибка удаления друга: {error}",
    },
    "access_control.list_friends_empty": {
        "en": "ℹ️ No friends in the list.",
        "ru": "ℹ️ Список друзей пуст.",
    },
    "access_control.list_friends_header": {
        "en": "<b>👥 Friends List:</b>\n\n",
        "ru": "<b>👥 Список друзей:</b>\n\n",
    },
    "access_control.list_friends_total": {
        "en": "\n<i>Total: {count} friends</i>",
        "ru": "\n<i>Всего: {count} друзей</i>",
    },
    "access_control.list_friends_error": {
        "en": "❌ Error listing friends: {error}",
        "ru": "❌ Ошибка получения списка друзей: {error}",
    },
    # -- chat_binder --
    "chat_binder.user_info_missing": {
        "en": "User information is missing.",
        "ru": "Информация о пользователе отсутствует.",
    },
    "chat_binder.message_text_missing": {
        "en": "Message text is missing.",
        "ru": "Текст сообщения отсутствует.",
    },
    "chat_binder.bound_success": {
        "en": "Chat bound successfully with key: {key}\n{access_status}",
        "ru": "Чат успешно привязан с ключом: {key}\n{access_status}",
    },
    "chat_binder.has_access": {
        "en": "✅ I have access to this chat.",
        "ru": "✅ У меня есть доступ к этому чату.",
    },
    "chat_binder.no_access": {
        "en": "❌ I don't have access to this chat.",
        "ru": "❌ У меня нет доступа к этому чату.",
    },
    "chat_binder.bind_error": {
        "en": "Error: {error}",
        "ru": "Ошибка: {error}",
    },
    "chat_binder.unbound_success": {
        "en": "Chat unbound successfully with key: {key}",
        "ru": "Чат успешно отвязан с ключом: {key}",
    },
    "chat_binder.unbind_not_found": {
        "en": "No chat was bound with key: {key}",
        "ru": "Нет чата, привязанного с ключом: {key}",
    },
    "chat_binder.not_bound": {
        "en": "This chat is not bound to you.",
        "ru": "Этот чат не привязан к вам.",
    },
    "chat_binder.status_single": {
        "en": "This chat is bound to you with key: '{key}'\nAccess status: {access_status}",
        "ru": "Этот чат привязан к вам с ключом: '{key}'\nСтатус доступа: {access_status}",
    },
    "chat_binder.status_has_access": {
        "en": "✅ Bot has access",
        "ru": "✅ Бот имеет доступ",
    },
    "chat_binder.status_no_access": {
        "en": "❌ Bot doesn't have access",
        "ru": "❌ Бот не имеет доступа",
    },
    "chat_binder.status_multiple": {
        "en": "This chat is bound to you with {count} keys:\n{details}",
        "ru": "Этот чат привязан к вам с {count} ключами:\n{details}",
    },
    "chat_binder.list_empty": {
        "en": "You don't have any bound chats.",
        "ru": "У вас нет привязанных чатов.",
    },
    "chat_binder.list_header": {
        "en": "Your bound chats:\n{chats_info}",
        "ru": "Ваши привязанные чаты:\n{chats_info}",
    },
    "chat_binder.list_error": {
        "en": "Error listing chats: {error}",
        "ru": "Ошибка получения списка чатов: {error}",
    },
    "chat_binder.get_chat_result": {
        "en": "Bound chat for key '{key}': {chat_id}",
        "ru": "Привязанный чат для ключа '{key}': {chat_id}",
    },
    "chat_binder.check_error": {
        "en": "Error checking binding status: {error}",
        "ru": "Ошибка проверки статуса привязки: {error}",
    },
    # -- user_interactions --
    "user_interactions.timeout": {
        "en": "\n\n⏰ No response received within the time limit.",
        "ru": "\n\n⏰ Ответ не получен в установленный срок.",
    },
    "user_interactions.timeout_auto_selected": {
        "en": "\n\n⏰ Auto-selected: {choice}",
        "ru": "\n\n⏰ Автоматически выбрано: {choice}",
    },
    "user_interactions.late_response": {
        "en": "Sorry, this response came too late or was for a different question. Please try again.",
        "ru": "Извините, этот ответ пришёл слишком поздно или был для другого вопроса. Попробуйте снова.",
    },
    "user_interactions.choice_invalid": {
        "en": "This choice is no longer valid.",
        "ru": "Этот выбор больше не действителен.",
    },
    "user_interactions.choice_recorded": {
        "en": "Your choice has already been recorded.",
        "ru": "Ваш выбор уже записан.",
    },
    "user_interactions.selected": {
        "en": "\n\nSelected: {choice}",
        "ru": "\n\nВыбрано: {choice}",
    },
    "user_interactions.hint": {
        "en": "\n\nTip: You can choose an option or type your own response.",
        "ru": "\n\nПодсказка: Вы можете выбрать вариант или ввести свой ответ.",
    },
    # -- bot_commands_menu --
    "commands_menu.public_header": {
        "en": "📝 Public commands:",
        "ru": "📝 Публичные команды:",
    },
    "commands_menu.hidden_header": {
        "en": "🕵️ Hidden commands:",
        "ru": "🕵️ Скрытые команды:",
    },
    "commands_menu.admin_header": {
        "en": "👑 Admin commands:",
        "ru": "👑 Команды администратора:",
    },
    "commands_menu.no_commands": {
        "en": "No commands available",
        "ru": "Нет доступных команд",
    },
    # -- auto_archive --
    "auto_archive.intro": {
        "en": (
            "🔔 Auto-archive is enabled! Your messages will be forwarded and deleted after a short delay.\n"
            "• Use {no_archive_tag} to prevent both forwarding and deletion\n"
            "• Use {no_delete_tag} to forward but keep the original message\n"
            "Use /autoarchive_help for more info."
        ),
        "ru": (
            "🔔 Автоархив включён! Ваши сообщения будут пересланы и удалены после короткой задержки.\n"
            "• Используйте {no_archive_tag} чтобы предотвратить пересылку и удаление\n"
            "• Используйте {no_delete_tag} чтобы переслать, но сохранить оригинал\n"
            "Используйте /autoarchive_help для информации."
        ),
    },
    "auto_archive.no_binding": {
        "en": "Auto-archive is enabled, but you don't have a bound chat for forwarding messages to.",
        "ru": "Автоархив включён, но у вас нет привязанного чата для пересылки сообщений.",
    },
    "auto_archive.supergroup_error": {
        "en": "⚠️ The bound chat was upgraded to supergroup. Please use /bind_auto_archive to bind the new supergroup.",
        "ru": "⚠️ Привязанный чат был обновлён до супергруппы. Используйте /bind_auto_archive чтобы привязать новую супергруппу.",
    },
    "auto_archive.bind_success": {
        "en": "Chat bound for auto-archiving",
        "ru": "Чат привязан для автоархива",
    },
    "auto_archive.help": {
        "en": (
            "🤖 Auto-Archive Help\n\n"
            "• Messages are automatically forwarded to your bound chat and deleted after a short delay\n"
            "• Use {no_archive_tag} to prevent both forwarding and deletion\n"
            "• Use {no_delete_tag} to forward but keep the original message\n"
            "• Use /bind_auto_archive to bind a chat for auto-archiving"
        ),
        "ru": (
            "🤖 Справка по автоархиву\n\n"
            "• Сообщения автоматически пересылаются в привязанный чат и удаляются после короткой задержки\n"
            "• Используйте {no_archive_tag} чтобы предотвратить пересылку и удаление\n"
            "• Используйте {no_delete_tag} чтобы переслать, но сохранить оригинал\n"
            "• Используйте /bind_auto_archive чтобы привязать чат для автоархива"
        ),
    },
    # -- telethon_manager --
    "telethon.phone_prompt": {
        "en": "Please enter your phone number (including country code, e.g., +1234567890):",
        "ru": "Введите номер телефона (включая код страны, например, +1234567890):",
    },
    "telethon.cancelled_no_phone": {
        "en": "Setup cancelled - no phone number provided.",
        "ru": "Настройка отменена — номер телефона не предоставлен.",
    },
    "telethon.code_prompt": {
        "en": "Please enter MODIFIED verification code as follows: YOUR CODE splitted with spaces e.g '21694' -> '2 1 6 9 4' or telegram WILL BLOCK IT",
        "ru": "Введите МОДИФИЦИРОВАННЫЙ код подтверждения: КОД разделённый пробелами, например '21694' -> '2 1 6 9 4', иначе Telegram ЗАБЛОКИРУЕТ",
    },
    "telethon.cancelled_no_code": {
        "en": "Setup cancelled - no verification code provided.",
        "ru": "Настройка отменена — код подтверждения не предоставлен.",
    },
    "telethon.code_no_spaces": {
        "en": "Setup cancelled - YOU DID NOT split the code with spaces like this: '2 1 6 9 4'",
        "ru": "Настройка отменена — вы НЕ разделили код пробелами: '2 1 6 9 4'",
    },
    "telethon.password_prompt": {
        "en": "Two-factor authentication is enabled. Please enter your 2FA password:",
        "ru": "Включена двухфакторная аутентификация. Введите пароль 2FA:",
    },
    "telethon.cancelled_no_password": {
        "en": "Setup cancelled - no password provided.",
        "ru": "Настройка отменена — пароль не предоставлен.",
    },
    "telethon.setup_success": {
        "en": "Successfully set up Telethon client! The session is saved and ready to use.",
        "ru": "Telethon клиент успешно настроен! Сеанс сохранён и готов к использованию.",
    },
    "telethon.setup_error": {
        "en": "Error during setup: {error}",
        "ru": "Ошибка при настройке: {error}",
    },
    "telethon.already_active": {
        "en": "You already have an active Telethon session! Use /setup_telethon_force to create a new one.",
        "ru": "У вас уже есть активный сеанс Telethon! Используйте /setup_telethon_force для создания нового.",
    },
    "telethon.active_session_found": {
        "en": "Active Telethon session found for {name}!",
        "ru": "Найден активный сеанс Telethon для {name}!",
    },
    "telethon.no_session": {
        "en": "No active Telethon session found. Use /setup_telethon to create one.",
        "ru": "Активный сеанс Telethon не найден. Используйте /setup_telethon для создания нового.",
    },
    "telethon.not_connected": {
        "en": "Client for user {user_id} not found. Please run the /setup_telethon command to authenticate.",
        "ru": "Клиент для пользователя {user_id} не найден. Запустите команду /setup_telethon для аутентификации.",
    },
    # -- trial_mode --
    "trial_mode.limit_reached": {
        "en": "You have reached your usage limit for the {func_name} command. Reset in: {remaining_time}.",
        "ru": "Вы достигли лимита команды {func_name}. Сброс через: {remaining_time}.",
    },
    "trial_mode.global_limit": {
        "en": "The {func_name} command has reached its global usage limit. Please try again later. Reset in: {remaining_time}.",
        "ru": "Команда {func_name} достигла глобального лимита. Попробуйте позже. Сброс через: {remaining_time}.",
    },
    "trial_mode.bot_limit": {
        "en": "The bot has reached its global usage limit. Please try again later. Reset in: {remaining_time}.",
        "ru": "Бот достиг глобального лимита использования. Попробуйте позже. Сброс через: {remaining_time}.",
    },
    "trial_mode.personal_limit": {
        "en": "You have reached your personal usage limit. Please try again later. Reset in: {remaining_time}.",
        "ru": "Вы достигли личного лимита. Попробуйте позже. Сброс через: {remaining_time}.",
    },
    # -- error_handler --
    "error_handler.something_went_wrong": {
        "en": "Oops, something went wrong :(",
        "ru": "Упс, что-то пошло не так :(",
    },
    "error_handler.easter_egg": {
        "en": "\nHere, take this instead: \n{easter_egg}",
        "ru": "\nВот, возьмите вместо этого: \n{easter_egg}",
    },
    # -- llm_provider --
    "llm_provider.no_access": {
        "en": "You don't have access to AI features",
        "ru": "У вас нет доступа к функциям AI",
    },
    "llm_provider.no_access_contact_admin": {
        "en": "You don't have access to AI features, please write to {admin_contact} to request access",
        "ru": "У вас нет доступа к функциям AI, напишите {admin_contact} для получения доступа",
    },
    "llm_provider.no_stats": {
        "en": "No LLM usage statistics available.",
        "ru": "Статистика использования LLM недоступна.",
    },
    # -- subscription_manager --
    "subscription.tier_required": {
        "en": "This feature requires <b>{required}</b> tier. Your current tier: <b>{current}</b>.",
        "ru": "Эта функция требует уровень <b>{required}</b>. Ваш текущий уровень: <b>{current}</b>.",
    },
    "subscription.my_tier": {
        "en": "Your subscription tier: <b>{tier}</b>",
        "ru": "Ваш уровень подписки: <b>{tier}</b>",
    },
    "subscription.set_tier_usage": {
        "en": "Usage: /set_tier <user_id> <tier>\nAvailable tiers: free, basic, pro, admin",
        "ru": "Использование: /set_tier <user_id> <tier>\nДоступные уровни: free, basic, pro, admin",
    },
    "subscription.invalid_tier": {
        "en": "Invalid tier: {tier}. Valid tiers: {valid}",
        "ru": "Недопустимый уровень: {tier}. Доступные: {valid}",
    },
    "subscription.user_not_found": {
        "en": "Could not resolve user: {target}",
        "ru": "Не удалось найти пользователя: {target}",
    },
    "subscription.tier_set": {
        "en": "Set tier for {target} to <b>{tier}</b>",
        "ru": "Уровень для {target} установлен: <b>{tier}</b>",
    },
    "subscription.list_empty": {
        "en": "No subscribers with explicit tiers.",
        "ru": "Нет подписчиков с явно заданным уровнем.",
    },
    "subscription.list_header": {
        "en": "<b>Subscribers:</b>\n{entries}",
        "ru": "<b>Подписчики:</b>\n{entries}",
    },
    # -- multi_forward --
    "multi_forward.message_count": {
        "en": "Received {count} messages",
        "ru": "Получено {count} сообщений",
    },
    "multi_forward.send_as_file_disabled": {
        "en": "Send as file disabled",
        "ru": "Отправка файлом отключена",
    },
    "multi_forward.send_as_file_enabled": {
        "en": "Send as file enabled",
        "ru": "Отправка файлом включена",
    },
}
