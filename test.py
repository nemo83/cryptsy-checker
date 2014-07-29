from datetime import datetime

print datetime.now()
print datetime.utcnow()


class Person:
    def __init__(self, name, lastname):
        self.name = name
        self.lastname = lastname

    def __str__(self):
        return "name: {}, lastname: {}".format(self.name, self.lastname)


persons = [Person('giovanni', 'gargiulo'), Person('giovanni', 'trapattoni'), Person('lisa', 'hickey')]

filtered_persons = filter(
    lambda x: x.lastname == max([z.lastname for z in filter(lambda y: y.name == x.name, persons)]), persons)

filtered_persons_2 = filter(lambda x: x.lastname == map(lambda x: x.lastname, persons), persons)

# print filtered_persons

for filtered_person in filtered_persons:
    print filtered_person
