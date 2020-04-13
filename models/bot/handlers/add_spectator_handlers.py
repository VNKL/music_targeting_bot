""" Use python 3.7 """

import logging

from telegram.ext import ConversationHandler, MessageHandler, CommandHandler, Filters
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, ParseMode

from settings import MAIN_MANAGER_KEYBOARD, MAIN_SPECTATOR_KEYBOARD
from models.vk.targeting import *
from models.bot.handlers.command_handlers import reload


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


def _sp_get_name(update, context):
    logging.info(f'SP - {update.effective_user.username} trying to add spectator')

    if _is_user_known(context, update):
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=f'Пришли юзернейм наблюдателя, начиная с символа "@".',
                                 reply_markup=ReplyKeyboardRemove())
        return 'add_spectator'


def _sp_add_spectator(update, context):
    logging.info(f'SP - {update.effective_user.username} trying to send spectator username')

    if _is_user_known(context, update):
        text = update.message.text
        if text[0] == '@':
            spec_name = add_spectator_to_user(update)
            spec_user = DB.users.find_one({'user_name': spec_name})
            user_name = DB.users.find_one({'user_id': update.effective_user.id})['user_name']

            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=f'Наблюдатель добавлен',
                                     reply_markup=ReplyKeyboardMarkup(MAIN_MANAGER_KEYBOARD))
            logging.info(f'SP - {update.effective_user.username} added the spectator')

            context.bot.send_message(chat_id=spec_user['chat_id'],
                                     text=f'@{user_name} добавил тебя в наблюдатели',
                                     reply_markup=ReplyKeyboardMarkup(MAIN_SPECTATOR_KEYBOARD))

            return ConversationHandler.END

        else:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=f'Ты прислал что-то не то. Давай еще раз')
            return 'add_spectator'


def _sp_failback(update, context):
    logging.info(f'SP - {update.effective_user.username} get failback')

    if _is_user_known(context, update):
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=f'Ты прислал что-то не то. Давай еще раз')


# Диалог по автоматизации запущенной кампании
add_spectator_handler = ConversationHandler(
    entry_points=[MessageHandler(Filters.regex('^(Добавить наблюдателя)$'), _sp_get_name)],
    states={
        'add_spectator': [CommandHandler('reload', reload),
                          MessageHandler(Filters.text, _sp_add_spectator)],
    },
    fallbacks=[CommandHandler('reload', reload),
               MessageHandler(Filters.text, _sp_failback)]
)
