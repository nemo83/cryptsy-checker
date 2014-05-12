import simplejson


class Foo:
    def __init__(self, name):
        self.name = name


a = [Foo("Giovanni"), Foo("Lisa")]

print a[0].name

print simplejson.dumps(Foo("Giovanni").__dict__)
