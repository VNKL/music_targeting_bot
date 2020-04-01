""" Use python 3.7 """

import logging

from telegram.ext import ConversationHandler, MessageHandler, CommandHandler, Filters
from telegram import ReplyKeyboardMarkup, ParseMode

from settings import MAIN_MANAGER_KEYBOARD, MAIN_SPECTATOR_KEYBOARD
from models.vk.targeting import *
from models.bot.handlers.command_handlers import reload


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
    logging.info(f'CS - {update.effective_user.username} trying to select campaign to get average stat')

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
            return 'get_camp_stats'
        else:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text='В базе данных нет кампаний, по которым можно получить стату',
                                     reply_markup=ReplyKeyboardMarkup(MAIN_MANAGER_KEYBOARD))
            return ConversationHandler.END


def _cs_get_camp_stats(update, context):

    if _is_user_known(context, update):
        text = update.message.text
        campaigns = get_campaigns_from_db(update)

        if text in list(camp_names.keys()):
            logging.info(f'CS - {update.effective_user.username} selected campaign to get stats')
            help_text = f'Получаю стату кампании <b>"{text}"</b>..\n\n'
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=help_text,
                                     parse_mode=ParseMode.HTML)

            campaign = campaigns[camp_names[text]]
            stat = get_campaign_average(campaign)
            answer = _answer_for_campaign_stat(text, stat)

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

            logging.info(f'CS - {update.effective_user.username} get campaign average stat')

            return ConversationHandler.END

        else:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text='Ты прислал что-то не то. Давай еще раз')
            return 'get_camp_stats'


def _answer_for_campaign_stat(text, stat):
    terms_dict = {'spent': 'Потрачено',
                  'listens': 'Клики на плей',
                  'saves': 'Добавления',
                  'listen_rate': 'Конверсия в клики из охвата',
                  'listen_cost': 'Стоимость одного клика',
                  'save_rate': 'Конверсия в добавления из охвата',
                  'save_cost': 'Стоимость одного добавления'}
    answer = f'<b>{text}</b>\n\n'

    for k, v in stat.items():
        answer += f'<b>{terms_dict[k]}</b>: {v}\n'

    return answer


def _cs_failback(update, context):
    logging.info(f'CS - {update.effective_user.username} get failback')

    if _is_user_known(context, update):
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text='Ты ввел не то, что я просил. Давай еще раз')


# Диалог по получению статы кампании
campaign_stats_handler = ConversationHandler(
    entry_points=[MessageHandler(Filters.regex('^(Получить статистику кампании)$'), _cs_select_campaign)],
    states={
        'get_camp_stats': [CommandHandler('reload', reload),
                           MessageHandler(Filters.text, _cs_get_camp_stats)]
    },
    fallbacks=[CommandHandler('reload', reload),
               MessageHandler(Filters.text, _cs_failback)]
)

