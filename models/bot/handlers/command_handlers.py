""" Use python 3.7 """

import logging

from telegram import ReplyKeyboardMarkup, ParseMode
from telegram.ext import ConversationHandler

from models.database import *
from settings import MAIN_MANAGER_KEYBOARD, MAIN_SPECTATOR_KEYBOARD


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


def start(update, context):
    logging.info(f'user_{update.effective_user.id} sent "/start"')

    # Тянет пользователя из БД или создает в ней нового пользователя или шлет нахуй
    user = get_or_create_user(update)
    if user['permissions'] == 'manager':
        if user['vk_token'] is None:
            context.bot.send_message(chat_id=user['chat_id'],
                                     text=f'Привет, @{user["user_name"]}!\n'
                                          f'У меня нет твоего токена от ВК((\n'
                                          f'Пришли мне токен через пробел после команды /set_token')
        else:
            context.bot.send_message(chat_id=user['chat_id'],
                                     text=f'Привет, @{user["user_name"]}!\nЧем займемся?',
                                     reply_markup=ReplyKeyboardMarkup(MAIN_MANAGER_KEYBOARD))

    elif user['permissions'] == 'spectator':
        if _check_spectators_manager(user):
            context.bot.send_message(chat_id=user['chat_id'],
                                     text=f'Привет, @{user["user_name"]}!\nЧто хочешь узнать?',
                                     reply_markup=ReplyKeyboardMarkup(MAIN_SPECTATOR_KEYBOARD))
        else:
            context.bot.send_message(chat_id=user['chat_id'],
                                     text=f'Привет, @{user["user_name"]}!\nПопроси менеджера добавить тебя в '
                                          f'наблюдатели.')

    else:
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
    text = update.message.text
    text = text.rstrip().split(' ')

    logging.info(f'user_{update.effective_user.id} sent vk_token')

    # Ищет пользователя в БД, и если его там нет, то шлет нахуй
    user = DB.users.find_one({'user_id': update.effective_user.id})
    if not user:
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=f'Я тебя не знаю. Напиши @vnkl_iam. '
                                      f'Может быть, он нас познакомит.')
    # А если находит..
    else:
        # ..но пользователь прислал что-то не то, просит прислать еще раз
        if len(text) != 2:
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


def update_cabinets(update, context):
    logging.info(f'user_{update.effective_user.id} sent update_cabinets')

    # Ищет пользователя в БД, и если его там нет, то шлет нахуй
    user = DB.users.find_one({'user_id': update.effective_user.id})
    if not user:
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


def get_campaign_statuses(update, context):
    logging.info(f'user_{update.effective_user.id} trying to get campaigns statuses')

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


def reload(update, context):
    logging.info(f'user_{update.effective_user.id} trying to set cover image')

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


def help_message(update, context):
    logging.info(f'user_{update.effective_user.id} sent "/help"')

    # Тянет пользователя из БД или создает в ней нового пользователя или шлет нахуй
    user = get_or_create_user(update)
    if user['permissions'] == 'manager':
        context.bot.send_message(chat_id=user['chat_id'],
                                 text='Обратись за помощью к @vnkl_iam',
                                 reply_markup=ReplyKeyboardMarkup(MAIN_MANAGER_KEYBOARD))

    elif user['permissions'] == 'spectator':
        if _check_spectators_manager(user):
            context.bot.send_message(chat_id=user['chat_id'],
                                     text='Оьратись за помощью к @vnkl_iam',
                                     reply_markup=ReplyKeyboardMarkup(MAIN_SPECTATOR_KEYBOARD))
        else:
            context.bot.send_message(chat_id=user['chat_id'],
                                     text=f'Попроси менеджера добавить тебя в наблюдатели. '
                                          f'После этого все должно стать понятно')

    else:
        context.bot.send_message(chat_id=user['chat_id'],
                                 text=f'Привет, @{user["user_name"]}!\nЯ тебя не знаю. Напиши @vnkl_iam. '
                                      f'Может быть, он нас познакомит.')


