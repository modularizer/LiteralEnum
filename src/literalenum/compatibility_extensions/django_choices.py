def django_choices(cls):
    return [(v, name) for name, v in cls.items()] 