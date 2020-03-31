""" Use python 3.7 """

import pymongo


MAIN_MANAGER_KEYBOARD = [['Создать новую кампанию', 'Запустить созданную кампанию'],
                         ['Автоматизировать кампанию', 'Получить статусы кампаний'],
                         ['Получить статистику кампании', 'Получить детализацию кампании'],
                         ['Добавить наблюдателя', 'Обновить кабинеты']]

MAIN_SPECTATOR_KEYBOARD = [['Получить статусы кампаний'],
                           ['Получить статистику кампании'],
                           ['Получить детализацию кампании']]


vk_support_login = 'smm4@black-star.ru'
vk_support_password = 'BS0880BSaBS0880BSa'
vk_support_token = '2c1b8b928d83d6407f9d81671a26818edc4ab7c950159a3e644fc8fd792fbc1bb44625cc732a61b0a665c'
vk_support_user_id = 451369253
VK_SUPPORT_ACCOUNT = {'login': vk_support_login,
                      'password': vk_support_password,
                      'token': vk_support_token,
                      'user_id': vk_support_user_id}


TELEGRAM_TOKEN = '1122634627:AAFRWfpTDbizg05s1S5GWs2JF3SznIFVQsE'


prx = '172.96.138.248:49873:DJhQuD0qDD:wxBT69FYfZ'
prx = prx.split(':')
PROXY = {'proxy_url': f'socks5://{prx[0]}:{prx[1]}',
         'urllib3_proxy_kwargs': {'username': prx[2], 'password': prx[3]}}


db = pymongo.MongoClient("mongodb+srv://MusicTargetingBot:BS0880BSa@"
                         "musictargetingbot-6n12v.mongodb.net/music_targeting_bot?retryWrites=true&w=majority")
DB = db.music_targeting_bot
