from typing import Type

from loguru import logger


def get_logger():
    # central logging setup point.
    # dummy for now
    # will see if we need to add more later
    return logger


class Singleton(type):
    """
    Singleton metaclass.
    Usage example:
    class MyClass(BaseClass, metaclass=Singleton):
        pass
    """

    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]

    @classmethod
    def get_instance(cls, TargetClass: Type):
        return cls._instances[TargetClass]
