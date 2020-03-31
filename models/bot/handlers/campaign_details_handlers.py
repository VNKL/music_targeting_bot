""" Use python 3.7 """

import logging

from telegram.ext import ConversationHandler, MessageHandler, Filters
from telegram import ReplyKeyboardMarkup, ParseMode

from settings import MAIN_MANAGER_KEYBOARD, MAIN_SPECTATOR_KEYBOARD
from models.vk.targeting import *


camp_names = {}


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


def _cd_select_campaign(update, context):
    logging.info(f'user_{update.effective_user.id} trying to get select campaign')

    if _is_user_known(context, update):
        campaigns = get_campaigns_from_db(update)
        keyboard = [[f'{name} (is {v["campaign_status"]})'] for name, v in campaigns.items() if
                                                            v['campaign_status'] != 'created']

        for name, v in campaigns.items():
            camp_names[f'{name} (is {v["campaign_status"]})'] = name

        if len(keyboard) != 0:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text='Выбери кампанию👇🏻',
                                     reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))
            return 'get_camp_details'
        else:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text='В базе данных нет кампаний, по которым можно получить стату',
                                     reply_markup=ReplyKeyboardMarkup(MAIN_MANAGER_KEYBOARD))
            return ConversationHandler.END


def _cs_get_camp_details(update, context):
    logging.info(f'user_{update.effective_user.id} trying to get campaign stat')

    if _is_user_known(context, update):
        text = update.message.text
        campaigns = get_campaigns_from_db(update)

        if text in list(camp_names.keys()):
            help_text = f'Получаю детализацию кампании <b>"{text}"</b>..'
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=help_text,
                                     parse_mode=ParseMode.HTML)

            campaign = campaigns[camp_names[text]]
            stat = get_campaign_details(campaign)
            answer = _answer_for_campaign_details(text, stat)

            user = DB.users.find_one({'user_id': update.effective_user.id})
            if user['permissions'] == 'manager':
                context.bot.send_message(chat_id=update.effective_chat.id,
                                         text=answer,
                                         parse_mode=ParseMode.HTML,
                                         reply_markup=ReplyKeyboardMarkup(MAIN_MANAGER_KEYBOARD))

            elif user['permissions'] == 'spectator':
                context.bot.send_message(chat_id=update.effective_chat.id,
                                         text=answer,
                                         parse_mode=ParseMode.HTML,
                                         reply_markup=ReplyKeyboardMarkup(MAIN_SPECTATOR_KEYBOARD))

            return ConversationHandler.END

        else:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text='Ты прислал что-то не то. Давай еще раз')
            return 'get_camp_details'


def _answer_for_campaign_details(text, stat):
    answer = f'<b>{text}</b>\n\n'
    for _, v in stat.items():
        listens = v['listens']
        reach = v['reach']
        spent = v['spent']
        if listens != 0:
            cost = round((spent / listens), 2)
        else:
            cost = 0
        if reach != 0:
            rate = round((listens / reach * 100), 2)
        else:
            rate = 0

        answer += f'<b>{v["name"]}</b>: {listens} кликов по {cost} руб, конверсия {rate}%\n'

    return answer


def _cd_failback(update, context):
    logging.info(f'user_{update.effective_user.id} trying to set cover image')

    if _is_user_known(context, update):
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text='Ты ввел не то, что я просил. Давай еще раз')


# Диалог по получению статы кампании
campaign_details_handler = ConversationHandler(
    entry_points=[MessageHandler(Filters.regex('^(Получить детализацию кампании)$'), _cd_select_campaign)],
    states={
        'get_camp_details': [MessageHandler(Filters.text, _cs_get_camp_details)]
    },
    fallbacks=[MessageHandler(Filters.text, _cd_failback)]
)
