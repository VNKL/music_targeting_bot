""" Use python 3.7 """

import logging
from multiprocessing import Process
import os

from telegram.ext import ConversationHandler, MessageHandler, CommandHandler, Filters
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, ParseMode

from settings import MAIN_MANAGER_KEYBOARD
from models.vk.targeting import *
from models.bot.handlers.command_handlers import reload


campaign_settings = {}


def _is_user_known(context, update):
    # Ищет пользователя в БД, и если его там нет, то шлет нахуй
    user = DB.users.find_one({'user_id': update.effective_user.id})
    if not user:
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text='Я тебя не знаю. Напиши @vnkl_iam. '
                                      'Может быть, он нас познакомит.')
        return False
    # А если находит..
    else:
        return True


def _nc_start(update, context):
    logging.info(f'user_{update.effective_user.id} trying to start new campaign')

    if _is_user_known(context, update):
        user = DB.users.find_one({'user_id': update.effective_user.id})
        cabinets = []
        for cab_name, _ in user['user_cabinets'].items():
            cabinets.append([cab_name])
        for cab_name, _ in user['agency_cabinets'].items():
            cabinets.append([cab_name])
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text='Выбери рекламный кабинет👇🏻',
                                 reply_markup=ReplyKeyboardMarkup(cabinets))
        return 'select_cabinet'


def _nc_select_cabinet(update, context):
    logging.info(f'user_{update.effective_user.id} trying to select cabinet')

    if _is_user_known(context, update):
        user = DB.users.find_one({'user_id': update.effective_user.id})
        # Собирает в переменную все кабинеты
        cabinets = {}
        for cab_name, cab_info in user['user_cabinets'].items():
            cabinets[cab_name] = {'type': 'user', 'cabinet_id': cab_info['cabinet_id']}
        for cab_name, cab_info in user['agency_cabinets'].items():
            cabinets[cab_name] = {'type': 'agency', 'agency_id': cab_info['agency_id']}

        # Достает из переменной инфу о выбранном кабинете
        cab_name = update.message.text
        cab_info = cabinets[cab_name]
        global temp_agency_name
        temp_agency_name = cab_name

        # Если это оказался пользовательский кабинет - сразу запрашивает название релиза
        if cab_info['type'] == 'user':
            campaign_settings[user['user_id']] = {'cabinet_name': cab_name, 'cabinet_id': cab_info['cabinet_id'],
                                                      'client_name': None, 'client_id': None}
            context.bot.send_message(chat_id=user['chat_id'],
                                     text='Пришли имя артиста и название трека через " / ".\n'
                                          'Например: Мот / Капкан',
                                     reply_markup=ReplyKeyboardRemove())
            return 'get_release_name'

        # А если агентский - то сперва просит выбрать клиента
        elif cab_info['type'] == 'agency':
            campaign_settings[user['user_id']] = {'cabinet_name': cab_name, 'cabinet_id': cab_info['agency_id']}
            clients = []
            for client_name, _ in user['agency_cabinets'][cab_name]['agency_clients'].items():
                clients.append([client_name])
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=f'Выбери клиента агентского кабинета👇🏻',
                                     reply_markup=ReplyKeyboardMarkup(clients))
            return 'select_client'


def _nc_select_client(update, context):
    logging.info(f'user_{update.effective_user.id} trying to select client')

    if _is_user_known(context, update):
        user = DB.users.find_one({'user_id': update.effective_user.id})
        # Добавляет инфу в переменную
        clients = {}
        for client_name, client_info in user['agency_cabinets'][temp_agency_name]['agency_clients'].items():
            clients[client_name] = client_info['client_id']
        client_name = update.message.text
        client_id = clients[client_name]
        campaign_settings[user['user_id']].update({'client_name': client_name, 'client_id': client_id})
        # И запрашивает название релиза
        context.bot.send_message(chat_id=user['chat_id'],
                                 text=f'Пришли имя артиста и название трека через " / ".\n'
                                      f'Например: Мот / Капкан',
                                 reply_markup=ReplyKeyboardRemove())
        return 'get_release_name'


def _nc_get_release_name(update, context):
    logging.info(f'user_{update.effective_user.id} trying to set artist and track name')

    if _is_user_known(context, update):
        user = DB.users.find_one({'user_id': update.effective_user.id})
        # Если пользователь ввел все правильно - обновляет переменную и просит прислать бюджет кампании
        if update.message.text.find(' / '):
            text = update.message.text
            d = text.find(' / ')
            artist = text[:d]
            track = text[d + 3:]
            campaign_settings[user['user_id']].update({'artist_name': artist, 'track_name': track})
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text='Пришли цитату из трека, которую добавим в объявления\n'
                                          'Если не хочешь добавлять цитату, пришли минус')
            return 'get_citation'
        # Если пользователь ввел что-то не то, зацикливает его на этом шаге
        else:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text='Ты ввел что-то не то, введи нормально, как попросили')
            return 'get_release_name'


def _nc_get_citation(update, context):
    logging.info(f'user_{update.effective_user.id} trying to set citation')

    if _is_user_known(context, update):
        # Обновляет переменную
        user = DB.users.find_one({'user_id': update.effective_user.id})
        citation = update.message.text
        if citation == '-':
            campaign_settings[user['user_id']].update({'citation': None})
        else:
            campaign_settings[user['user_id']].update({'citation': citation})
        # ..и просит прислать айди группы артиста, из которой будут созданы объявления
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text='Пришли бюджет кампании в рублях и без пробелов.\n'
                                      'Например: 100500')
        return 'get_campaign_budget'


def _nc_get_campaign_budget(update, context):
    logging.info(f'user_{update.effective_user.id} trying to set campaign budget')

    if _is_user_known(context, update):
        # Делает бюджет интом, обновляет переменную и просит прислать цитату
        user = DB.users.find_one({'user_id': update.effective_user.id})
        budget = int(update.message.text)
        campaign_settings[user['user_id']].update({'campaign_budget': budget})
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text='Пришли id группы, из которой будут создаваться объявления')
        return 'get_artist_group'


def _nc_get_artist_group(update, context):
    logging.info(f'user_{update.effective_user.id} trying to set artist group id')

    if _is_user_known(context, update):
        user = DB.users.find_one({'user_id': update.effective_user.id})
        artist_group_id = int(update.message.text)
        campaign_settings[user['user_id']].update({'artist_group_id': artist_group_id})
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text='Пришли id фейк-группы, в которой будут создаваться плейлисты.'
                                      'В эту группу уже должен быть добавлен целевой трек.\n'
                                      'Пришли "0", если группу нужно создать автоматически')
        return 'get_fake_group'


def _nc_get_fake_group(update, context):
    logging.info(f'user_{update.effective_user.id} trying to set fake group id')

    if _is_user_known(context, update):
        user = DB.users.find_one({'user_id': update.effective_user.id})
        text = int(update.message.text)
        if text == 0:
            campaign_settings[user['user_id']].update({'fake_group_id': None})
        else:
            campaign_settings[user['user_id']].update({'fake_group_id': text})
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text='Будем сужать аудитории по интересу "музыка"?',
                                 reply_markup=ReplyKeyboardMarkup([['Да', 'Нет']], one_time_keyboard=True))
        return 'get_music_interest'


def _nc_get_music_interest(update, context):
    logging.info(f'user_{update.effective_user.id} trying to set music interest filter')

    if _is_user_known(context, update):
        user = DB.users.find_one({'user_id': update.effective_user.id})
        text = update.message.text
        if not text == 'Да' and not text == 'Нет':
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text='Ты ввел что-то не то.\nБудем сужать аудитории по интересу "музыка"?',
                                     reply_markup=ReplyKeyboardMarkup([['Да', 'Нет']], one_time_keyboard=True))
            return 'get_music_interest'
        else:
            if text == 'Да':
                campaign_settings[user['user_id']].update({'music_interest_filter': True})
            elif text == 'Нет':
                campaign_settings[user['user_id']].update({'music_interest_filter': False})
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text='Пришли изображением (не файлом!) обложку для плейлистов.'
                                          'Или введи команду /skip_cover, если не будем грузить свою обложку.')
            return 'get_cover_img'


def _nc_get_cover_img(update, context):
    logging.info(f'user_{update.effective_user.id} trying to set cover image')

    if _is_user_known(context, update):
        user = DB.users.find_one({'user_id': update.effective_user.id})
        # Скачивает обложку
        os.getcwd()
        os.chdir('..')
        os.chdir('..')
        os.makedirs('cover_images', exist_ok=True)
        photo = context.bot.get_file(update.message.photo[-1].file_id)
        path = f'cover_images\{photo.file_id}.jpg'
        photo.download(path)
        full_path = f'{os.getcwd()}\{path}'
        # Обновляет переменую
        campaign_settings[user['user_id']].update({'cover_path': full_path})

        # Просит подтвердить создание кампании или начать заново
        text = _nc_preparation_summary(update)
        keyboard = [['Да, создавай кампанию'], ['Нет, давай начнем с начала'], ['Нет, выведи основное меню']]
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=text,
                                 parse_mode=ParseMode.HTML,
                                 reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))
        return 'get_end_decision'


def _nc_skip_cover_img(update, context):
    logging.info(f'user_{update.effective_user.id} trying to skip cover image')

    if _is_user_known(context, update):
        user = DB.users.find_one({'user_id': update.effective_user.id})
        # Обновляет переменую
        campaign_settings[user['user_id']].update({'cover_path': None})

        # Просит подтвердить создание кампании или начать заново
        text = _nc_preparation_summary(update)
        keyboard = [['Да, создавай кампанию'], ['Нет, давай начнем с начала'], ['Нет, выведи основное меню']]
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=text,
                                 parse_mode=ParseMode.HTML,
                                 reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))
        return 'get_end_decision'


def _nc_get_end_decision(update, context):
    logging.info(f'user_{update.effective_user.id} trying to set end decision')

    if _is_user_known(context, update):
        user = DB.users.find_one({'user_id': update.effective_user.id})
        text = update.message.text
        camp_settings = campaign_settings[user['user_id']]
        if text == 'Да, создавай кампанию':
            add_campaign_setting_to_db(update, campaign_settings)
            campaign_name = f'{camp_settings["artist_name"].upper()} / {camp_settings["track_name"]}'
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=f'Кампания "{campaign_name}" создана в базе данных. '
                                          f'Теперь ты можешь запустить ее из основного меню',
                                     reply_markup=ReplyKeyboardMarkup(MAIN_MANAGER_KEYBOARD))
            return ConversationHandler.END

        elif text == 'Нет, давай начнем с начала':
            cabinets = []
            for cab_name, _ in user['user_cabinets'].items():
                cabinets.append([cab_name])
            for cab_name, _ in user['agency_cabinets'].items():
                cabinets.append([cab_name])
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text='Выбери рекламный кабинет👇🏻',
                                     reply_markup=ReplyKeyboardMarkup(cabinets))
            return 'select_cabinet'

        elif text == 'Нет, выведи основное меню':
            context.bot.send_message(chat_id=user['chat_id'],
                                     text='Окей, чем займемся?',
                                     reply_markup=ReplyKeyboardMarkup(MAIN_MANAGER_KEYBOARD))
            return ConversationHandler.END

        else:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text='Ты ввел что-то не то. Давай еще раз.')
            return 'get_end_decision'


def _nc_preparation_summary(update):
    user = DB.users.find_one({'user_id': update.effective_user.id})
    text = 'Вот что у нас получилось:\n\n'
    campaign_summary = campaign_settings[user['user_id']]
    for k, v in campaign_summary.items():
        text += f'<b>{k}:</b> {v}\n'
    text += '\nВсе ок, подтвержадем?'
    return text


def _nc_failback(update, context):
    logging.info(f'user_{update.effective_user.id} trying to set cover image')

    if _is_user_known(context, update):
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text='Ты ввел не то, что я просил. Давай еще раз')


# Диалог по настройке новой кампании
new_campaign_handler = ConversationHandler(
    entry_points=[MessageHandler(Filters.regex('^(Создать новую кампанию)$'), _nc_start)],
    states={
        'select_cabinet': [CommandHandler('reload', reload),
                           MessageHandler(Filters.text, _nc_select_cabinet)],
        'select_client': [CommandHandler('reload', reload),
                          MessageHandler(Filters.text, _nc_select_client)],
        'get_release_name': [CommandHandler('reload', reload),
                             MessageHandler(Filters.regex('.+[/].+'), _nc_get_release_name)],
        'get_citation': [CommandHandler('reload', reload),
                         MessageHandler(Filters.text, _nc_get_citation)],
        'get_campaign_budget': [CommandHandler('reload', reload),
                                MessageHandler(Filters.regex('\d+'), _nc_get_campaign_budget)],
        'get_artist_group': [CommandHandler('reload', reload),
                             MessageHandler(Filters.regex('\d+'), _nc_get_artist_group)],
        'get_fake_group': [CommandHandler('reload', reload),
                           MessageHandler(Filters.regex('\d+'), _nc_get_fake_group)],
        'get_music_interest': [CommandHandler('reload', reload),
                               MessageHandler(Filters.text, _nc_get_music_interest)],
        'get_cover_img': [CommandHandler('reload', reload),
                          MessageHandler(Filters.photo, _nc_get_cover_img),
                          CommandHandler('skip_cover', _nc_skip_cover_img)],
        'get_end_decision': [CommandHandler('reload', reload),
                             MessageHandler(Filters.text, _nc_get_end_decision)]
    },
    fallbacks=[CommandHandler('reload', reload),
               MessageHandler(Filters.text, _nc_failback)]
)
