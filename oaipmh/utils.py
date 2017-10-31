import datetime


def parse_date(datestamp):
    fmts = ['%Y-%m-%d', '%Y-%m', '%Y']
    for fmt in fmts:
        try:
            return datetime.datetime.strptime(datestamp, fmt)
        except ValueError:
            continue
    else:
        raise ValueError("time data '%s' does not match formats '%s'" % (
            datestamp, fmts))


class lazyproperty:
    def __init__(self, func):
        self.func = func

    def __get__(self, instance, cls):
        if instance is None:
            return self
        else:
            value = self.func(instance)
            setattr(instance, self.func.__name__, value)
            return value

