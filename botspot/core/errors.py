from typing import Optional


class BotspotError(Exception):
    def __init__(
        self,
        message: str,
        report_to_dev: bool = True,
        include_traceback: bool = True,
        user_message: Optional[str] = None,
        easter_eggs: bool = True,
        *args: object
    ) -> None:
        self.message = message
        self.report_to_dev = report_to_dev
        self.include_traceback = include_traceback
        self.user_message = user_message
        self.easter_eggs = easter_eggs
        super().__init__(*args)
