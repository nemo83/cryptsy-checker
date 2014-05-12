import requests

def login():
    url = 'https://my.meteor.ie/meteor/transactional/login?'

    form_data = {
    'username': 'gargiulo.gianni@gmail.com',
    'password': 'Giannig83',
    'submit': 'submit',
    }

    requests.post(url, form_data)



# https://my.meteor.ie/meteor/transactional/secure/webText


