from .deps_getters import (
    get_bot,
    get_database,
    get_dispatcher,
    get_scheduler,
    get_telethon_client,
    get_telethon_manager,
    get_user_manager,
)
from .send_safe import answer_safe, reply_safe, send_safe
from .unsorted import get_message_text, get_name, get_user, strip_command
from .user_ops import compare_users, is_admin, is_friend, to_user_record
