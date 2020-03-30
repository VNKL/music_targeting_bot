""" Use python 3.7 """

import logging

from telegram.ext import ConversationHandler, MessageHandler, Filters
from telegram import ReplyKeyboardMarkup, ParseMode

from settings import MAIN_MANAGER_KEYBOARD
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


def _cs_select_campaign(update, context):
    logging.info(f'user_{update.effective_user.id} trying to get select campaign')

    if _is_user_known(context, update):
        campaigns = get_campaigns_from_db(update)
        keyboard = [[f'{name} ({v["campaign_status"]})'] for name, v in campaigns.items() if
                                                            v['campaign_status'] != 'created']

        for name, v in campaigns.items():
            camp_names[f'{name} ({v["campaign_status"]})'] = name

        if len(keyboard) != 0:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text='Выбери кампанию👇🏻',
                                     reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))
            return 'get_camp_stats'
        else:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text='В базе данных нет кампаний, по которым можно получить стату',
                                     reply_markup=ReplyKeyboardMarkup(MAIN_MANAGER_KEYBOARD))
            return ConversationHandler.END


def _cs_get_camp_stats(update, context):
    logging.info(f'user_{update.effective_user.id} trying to get campaign stat')

    if _is_user_known(context, update):
        text = update.message.text
        campaigns = get_campaigns_from_db(update)

        if text in list(camp_names.keys()):
            help_text = f'Получаю стату кампании <b>"{text}"</b>..\n\n' \
                        f'Стата придет в таком формате:\n' \
                        f'<b>spent</b>: потраченный на данный момент бюджет\n' \
                        f'<b>listens</b>: сумма кликов на плей на данный момент\n' \
                        f'<b>save</b>: количетво людей, добавивших себе трек только из кампании\n' \
                        f'<b>listen_rate</b>: конверсия в клик на плей из охвата\n' \
                        f'<b>listen_cost</b>: стоимость одного клика на плей\n' \
                        f'<b>save_rate</b>: конверсия в добавление трека пользователем себе из охвата\n' \
                        f'<b>save_cost</b>: стоимость одного добавления трека себе пользователем'
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=help_text,
                                     parse_mode=ParseMode.HTML)

            campaign = campaigns[camp_names[text]]
            stat = get_campaign_average(update, campaign)
            answer = _answer_for_campaign_stat(text, stat)
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=answer,
                                     parse_mode=ParseMode.HTML,
                                     reply_markup=ReplyKeyboardMarkup(MAIN_MANAGER_KEYBOARD))
            return ConversationHandler.END

        else:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text='Ты прислал что-то не то. Давай еще раз')
            return 'get_camp_stats'


def _answer_for_campaign_stat(text, stat):
    answer = f'<b>{text}</b>\n\n'
    for k, v in stat.items():
        answer += f'<b>{k}</b>: {v}\n'
    return answer


def _cs_failback(update, context):
    logging.info(f'user_{update.effective_user.id} trying to set cover image')

    if _is_user_known(context, update):
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text='Ты ввел не то, что я просил. Давай еще раз')


# Диалог по получению статы кампании
campaign_stats_handler = ConversationHandler(
    entry_points=[MessageHandler(Filters.regex('^(Получить статистику кампании)$'), _cs_select_campaign)],
    states={
        'get_camp_stats': [MessageHandler(Filters.text, _cs_get_camp_stats)]
    },
    fallbacks=[MessageHandler(Filters.text, _cs_failback)]
)

