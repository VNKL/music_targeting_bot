""" Use python 3.7 """

import logging

from telegram import ReplyKeyboardMarkup, ParseMode
from telegram.ext import ConversationHandler

from models.database import *
from settings import MAIN_MANAGER_KEYBOARD, MAIN_SPECTATOR_KEYBOARD


def _is_user_known(context, update):
    # Ищет пользователя в БД, и если его там нет, то шлет нахуй
    user = DB.users.find_one({'user_id': update.effective_user.id})
    if not user or user['permissions'] == 'unknown':
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text='Я тебя не знаю. Напиши @vnkl_iam. '
                                      'Может быть, он нас познакомит.')
        return False
    # А если находит..
    else:
        return True


def start(update, context):
    logging.info(f'/start - {update.effective_user.username} sent command /start')

    # Тянет пользователя из БД или создает в ней нового пользователя или шлет нахуй
    user = get_or_create_user(update)
    if user['permissions'] == 'manager':
        if user['vk_token'] is None:
            logging.info(f'{update.effective_user.username} have no vk token')
            context.bot.send_message(chat_id=user['chat_id'],
                                     text=f'Привет, @{user["user_name"]}!\n'
                                          f'У меня нет твоего токена от ВК((\n'
                                          f'Пришли мне токен через пробел после команды /set_token')
        else:
            logging.info(f'/start - {update.effective_user.username} get main manager menu')
            context.bot.send_message(chat_id=user['chat_id'],
                                     text=f'Привет, @{user["user_name"]}!\nЧем займемся?',
                                     reply_markup=ReplyKeyboardMarkup(MAIN_MANAGER_KEYBOARD))

    elif user['permissions'] == 'spectator':
        if _check_spectators_manager(user):
            logging.info(f'/start - {update.effective_user.username} get main spectator menu')
            context.bot.send_message(chat_id=user['chat_id'],
                                     text=f'Привет, @{user["user_name"]}!\nЧто хочешь узнать?',
                                     reply_markup=ReplyKeyboardMarkup(MAIN_SPECTATOR_KEYBOARD))
        else:
            logging.info(f'/start - {update.effective_user.username} have no manager as spectator')
            context.bot.send_message(chat_id=user['chat_id'],
                                     text=f'Привет, @{user["user_name"]}!\nПопроси менеджера добавить тебя в '
                                          f'наблюдатели.')

    else:
        logging.info(f'/start - {update.effective_user.username} is unknown')
        context.bot.send_message(chat_id=user['chat_id'],
                                 text=f'Привет, @{user["user_name"]}!\nЯ тебя не знаю. Напиши @vnkl_iam. '
                                      f'Может быть, он нас познакомит.')


def _check_spectators_manager(user):
    try:
        if user['manager']:
            return True
        else:
            return False
    except KeyError:
        return False


def set_token(update, context):
    logging.info(f'/set_token - {update.effective_user.username} sent command /set_token')

    text = update.message.text
    text = text.rstrip().split(' ')

    # Ищет пользователя в БД, и если его там нет, то шлет нахуй
    user = DB.users.find_one({'user_id': update.effective_user.id})
    if not user:
        logging.info(f'/set_token - {update.effective_user.username} is unknown')
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=f'Я тебя не знаю. Напиши @vnkl_iam. '
                                      f'Может быть, он нас познакомит.')
    # А если находит..
    else:
        # ..но пользователь прислал что-то не то, просит прислать еще раз
        if len(text) != 2:
            logging.info(f'/set_token - {update.effective_user.username} failed with sent token')
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=f'Ты не прислал токен, давай еще раз')
        # ..и пользователь прислал все верно, то обновляет запись в БД
        else:
            token = text[1]
            add_token_to_user(update, token)
            # Получает кабинеты пользователя и добавляет их в БД
            vk = VkAdsBackend(token=token)
            cabinets = vk.get_cabinets()
            add_cabinets_to_user(update, cabinets)
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=f'Отлично, теперь у нас есть токен!\nЧем займемся?',
                                     reply_markup=ReplyKeyboardMarkup(MAIN_MANAGER_KEYBOARD))
            logging.info(f'/set_token - {update.effective_user.username} sent token and update cabinets automatically')


def update_cabinets(update, context):
    logging.info(f'/update_cabinets - {update.effective_user.username} sent command /update_cabinets')

    # Ищет пользователя в БД, и если его там нет, то шлет нахуй
    user = DB.users.find_one({'user_id': update.effective_user.id})
    if not user:
        logging.info(f'/update_cabinets - {update.effective_user.username} is unknown')
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=f'Я тебя не знаю. Напиши @vnkl_iam. '
                                      f'Может быть, он нас познакомит.')
    # А если находит..
    else:
        # Получает актуальные кабинеты пользователя и записывает их в БД
        token = user['vk_token']
        vk = VkAdsBackend(token=token)
        cabinets = vk.get_cabinets()
        add_cabinets_to_user(update, cabinets)
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=f'Кабинеты обновлены',
                                 reply_markup=ReplyKeyboardMarkup(MAIN_MANAGER_KEYBOARD))
        logging.info(f'/update_cabinets - {update.effective_user.username} updated his cabinets')


def get_campaign_statuses(update, context):
    logging.info(f'/get_campaign_statuses - {update.effective_user.username} trying to get campaign statuses')

    if _is_user_known(context, update):
        campaigns = get_campaigns_from_db(update)
        camp_statuses = {name: v['campaign_status'] for name, v in campaigns.items()}
        text = ''
        for name, status in camp_statuses.items():
            text += f'<b>{name}</b> is {status}\n'

        user = DB.users.find_one({'user_id': update.effective_user.id})

        if user['permissions'] == 'manager':
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=text,
                                     parse_mode=ParseMode.HTML,
                                     reply_markup=ReplyKeyboardMarkup(MAIN_MANAGER_KEYBOARD))

        elif user['permissions'] == 'spectator':
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=text,
                                     parse_mode=ParseMode.HTML,
                                     reply_markup=ReplyKeyboardMarkup(MAIN_SPECTATOR_KEYBOARD))

        logging.info(f'/get_campaign_statuses - {update.effective_user.username} get campaign statuses')


def reload(update, context):
    logging.info(f'/reload - {update.effective_user.username} trying to reload bot')

    if _is_user_known(context, update):
        user = DB.users.find_one({'user_id': update.effective_user.id})
        if user['permissions'] == 'manager':
            context.bot.send_message(chat_id=user['chat_id'],
                                     text='Бот перезагружен',
                                     reply_markup=ReplyKeyboardMarkup(MAIN_MANAGER_KEYBOARD))
            return ConversationHandler.END
        elif user['permissions'] == 'spectator':
            if _check_spectators_manager(user):
                context.bot.send_message(chat_id=user['chat_id'],
                                         text='Бот перезагружен',
                                         reply_markup=ReplyKeyboardMarkup(MAIN_SPECTATOR_KEYBOARD))
            return ConversationHandler.END

        logging.info(f'/reload - {update.effective_user.username} reloaded bot')


def help_message(update, context):
    logging.info(f'/help - {update.effective_user.username} trying to get help')

    # Тянет пользователя из БД или создает в ней нового пользователя или шлет нахуй
    user = get_or_create_user(update)
    if user['permissions'] == 'manager':
        context.bot.send_message(chat_id=user['chat_id'],
                                 text='Обратись за помощью к @vnkl_iam',
                                 reply_markup=ReplyKeyboardMarkup(MAIN_MANAGER_KEYBOARD))
        logging.info(f'/help - {update.effective_user.username} get help')

    elif user['permissions'] == 'spectator':
        if _check_spectators_manager(user):
            context.bot.send_message(chat_id=user['chat_id'],
                                     text='Оьратись за помощью к @vnkl_iam',
                                     reply_markup=ReplyKeyboardMarkup(MAIN_SPECTATOR_KEYBOARD))
            logging.info(f'/help - {update.effective_user.username} get help')
        else:
            context.bot.send_message(chat_id=user['chat_id'],
                                     text=f'Попроси менеджера добавить тебя в наблюдатели. '
                                          f'После этого все должно стать понятно')
            logging.info(f'/help - {update.effective_user.username} dont have a manager as spectator')

    else:
        logging.info(f'/help - {update.effective_user.username} is unknown')
        context.bot.send_message(chat_id=user['chat_id'],
                                 text=f'Привет, @{user["user_name"]}!\nЯ тебя не знаю. Напиши @vnkl_iam. '
                                      f'Может быть, он нас познакомит.')


