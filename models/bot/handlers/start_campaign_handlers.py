""" Use python 3.7 """

import logging
from multiprocessing import Process

from telegram.ext import ConversationHandler, MessageHandler, CommandHandler, Filters
from telegram import ReplyKeyboardMarkup, ParseMode

from settings import MAIN_MANAGER_KEYBOARD
from models.vk.targeting import *
from models.bot.handlers.command_handlers import reload


start_campaign_settings = {}


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


def _sc_select_campaign(update, context):
    logging.info(f'SC - {update.effective_user.username} trying to select campaign to start')

    if _is_user_known(context, update):
        campaigns = get_campaigns_from_db(update)
        camp_names = [[x] for x in list(campaigns.keys()) if campaigns[x]['campaign_status'] == 'created']
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=f'Какую кампанию запускаем?',
                                 reply_markup=ReplyKeyboardMarkup(camp_names, one_time_keyboard=True))
        return 'select_campaign_to_start'


def _sc_select_campaign_to_start(update, context):
    logging.info(f'SC - {update.effective_user.username} trying to choose automate campaign or only start')

    if _is_user_known(context, update):
        text = update.message.text
        campaigns = get_campaigns_from_db(update)
        if text in list(campaigns.keys()):
            campaign = campaigns[text]
            campaign_name = f'{campaign["artist_name"].upper()} / {campaign["track_name"]}'
            process = Process(target=start_campaign_from_db, args=(update, campaign))
            process.start()
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=f'Кампания "{campaign_name}" запускается..',
                                     reply_markup=ReplyKeyboardMarkup(MAIN_MANAGER_KEYBOARD))
            logging.info(f'SC - {update.effective_user.username} started campaign {campaign_name}')
            return ConversationHandler.END
        else:
            camp_names = [[x] for x in list(campaigns.keys()) if campaigns[x]['campaign_status'] == 'created']
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=f'Ты прислал что-то не то. Давай еще раз.',
                                     reply_markup=ReplyKeyboardMarkup(camp_names, one_time_keyboard=True))
            return 'select_campaign_to_start'


def _sc_failback(update, context):
    logging.info(f'SC - {update.effective_user.username} get failback')

    if _is_user_known(context, update):
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text='Ты ввел не то, что я просил. Давай еще раз')


# Диалог по запуску настроенной кампании
start_campaign_handler = ConversationHandler(
    entry_points=[MessageHandler(Filters.regex('^(Запустить созданную кампанию)$'), _sc_select_campaign)],
    states={
        'select_campaign_to_start': [CommandHandler('reload', reload),
                                     MessageHandler(Filters.text, _sc_select_campaign_to_start)]
    },
    fallbacks=[CommandHandler('reload', reload),
               MessageHandler(Filters.text, _sc_failback)]
)

