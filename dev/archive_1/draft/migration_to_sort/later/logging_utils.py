import os
import sys

import loguru
import mongoengine


class LogItem(mongoengine.Document):
    # level, message, timestamp, exception, traceback
    level = mongoengine.StringField()
    message = mongoengine.StringField()
    timestamp = mongoengine.DateTimeField()
    exception = mongoengine.StringField()
    traceback = mongoengine.StringField()
    # extra info, optional
    component = mongoengine.StringField()
    user = mongoengine.StringField()
    data = mongoengine.StringField()

    meta = {"collection": os.getenv("LOG_MONGO_COLLECTION", "logs")}


def mongo_sink(message):
    log_item = LogItem(
        level=message.record["level"].name,
        message=message.record["message"],
        timestamp=message.record["time"],
        exception=str(message.record["exception"]),
        traceback=(
            message.record["exception"].__traceback__ if message.record["exception"] else None
        ),
        component=message.record["extra"].get("component", None),
        user=message.record["extra"].get("user", None),
        data=message.record["extra"].get("data", None),
    )
    log_item.save()


DATA_CUTOFF = 100

# Customized formatter
custom_formatter = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level> | "
    "<yellow>Data (Total length: {extra[data_length]}):</yellow> "
    "<level>{extra[truncated_data]}</level>"
)


def data_filter(record):
    if "data" not in record["extra"]:
        return False
    data = record["extra"]["data"]
    total_length = len(data)
    truncated_data = data[:DATA_CUTOFF]
    truncated_data += "..." if total_length > DATA_CUTOFF else ""

    # Add these to the record so they can be used in the formatter
    record["extra"]["data_length"] = total_length
    record["extra"]["truncated_data"] = truncated_data

    return True  # Allow the log message to be processed further


def no_data_filter(record):
    return "data" not in record["extra"]


logger_initialized = False


def setup_logger(
    log_to_stderr: bool = None,
    log_to_file: bool = None,
    log_to_db: bool = None,
    file_path: str = None,
    remove_existing_handlers: bool = True,
):
    """
    Setup logger to
    0) remove all existing handlers
    1) Write to stdout

    Unsure about this:
    2) if there's a db connection - log to it
    3) if there's no db - log to file

    For now, let's make this explicit:
    2) if log_to_file=True - log to file
    3) if log_to_db=True - log to db
    :return:
    """
    global logger_initialized
    if logger_initialized:
        return

    logger = loguru.logger
    if remove_existing_handlers:
        logger.remove()

    if log_to_stderr is None:
        log_to_stderr = os.getenv("LOG_TO_STDERR", True)
    if log_to_stderr:
        logger.add(sys.stderr, level="DEBUG", filter=no_data_filter)
        logger.add(sys.stderr, level="DEBUG", filter=data_filter, format=custom_formatter)

    if log_to_file is None:
        log_to_file = os.getenv("LOG_TO_FILE", False)
    if log_to_file:
        if file_path is None:
            file_path = os.getenv("LOG_FILE_PATH", "logs/log.txt")
        logger.add(
            file_path,
            rotation="1 week",
            # retention="10 days",
            level="DEBUG",
        )

    if log_to_db is None:
        log_to_db = os.getenv("LOG_TO_DB", False)
    if log_to_db:
        logger.add(mongo_sink, level="INFO")

    # return logger
    logger_initialized = True


def load_logs(limit=100, **filters):
    result = LogItem.objects
    result = result.filter(**filters)
    return result.order_by("-timestamp").limit(limit).as_pymongo()


# Test the logger
if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    conn = mongoengine.connect(
        db=os.getenv("DATABASE_NAME"),
        # alias='default',
        host=os.getenv("DATABASE_CONN_STR"),
    )

    logger = loguru.logger
    setup_logger(log_to_db=True, log_to_file=True)
    logger.info("This is an info message")
    logger.info("This is an extra info message")
    logger.error("This is an error message")

    items = load_logs(level="INFO", message="This is an extra info message")
    import pandas as pd

    df = pd.DataFrame(items)
    print(df.head())
