import datetime


def now() -> datetime.datetime:
    return datetime.datetime.now().astimezone()


def today() -> datetime.date:
    return now().date()
