""" Use python 3.7 """

import logging

from telegram.ext import ConversationHandler, MessageHandler, CommandHandler, Filters
from telegram import ReplyKeyboardMarkup, ParseMode

from settings import MAIN_MANAGER_KEYBOARD, MAIN_SPECTATOR_KEYBOARD
from models.vk.targeting import *
from models.bot.handlers.command_handlers import reload


camp_names = {}
camp_name = None
camps_for_cabinets = {}
camps_for_selected_cab = {}
selected_campaign = {}


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


def _ccs_select_cabinet(update, context):
    logging.info(f'CD - {update.effective_user.username} trying to select cabinet to get campaign details')

    if _is_user_known(context, update):
        campaigns = get_campaigns_from_db(update)
        for name, params in campaigns.items():
            try:
                cab_name = params['client_name']
            except KeyError:
                cab_name = params['cabinet_name']
            global camps_for_cabinets
            try:
                camps_for_cabinets_temp = camps_for_cabinets[cab_name]
                camps_for_cabinets_temp.update({name: params})
                camps_for_cabinets.update({cab_name: camps_for_cabinets_temp})
            except KeyError:
                camps_for_cabinets[cab_name] = {name: params}
            global camp_names
            camp_names.update({name: params})

        keyboard = [[cabinet] for cabinet in list(camps_for_cabinets.keys())]
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text='Выбери кабинет👇🏻',
                                 reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))
        return 'select_camp_status'


def _ccs_select_camp_status(update, context):
    logging.info(f'CD - {update.effective_user.username} trying to select campaign status to get campaign details')

    if _is_user_known(context, update):
        cab_name = update.message.text
        global camps_for_cabinets
        global camps_for_selected_cab
        campaigns = camps_for_cabinets[cab_name]
        camps_for_selected_cab = campaigns
        statuses = [params['campaign_status'] for _, params in campaigns.items()]
        keyboard = [[status] for status in set(statuses)]

        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text='Выбери статус кампании👇🏻',
                                 reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))
        return 'select_campaign'


def _ccs_select_campaign(update, context):
    logging.info(f'CD - {update.effective_user.username} trying to select campaign to get details')

    if _is_user_known(context, update):
        global camps_for_selected_cab
        campaigns = camps_for_selected_cab
        status = update.message.text
        keyboard = [[name] for name, params in campaigns.items() if params['campaign_status'] == status]

        for name, v in campaigns.items():
            camp_names[f'{name} (is {v["campaign_status"]})'] = name

        if len(keyboard) != 0:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text='Выбери кампанию👇🏻',
                                     reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))
            return 'select_status'
        else:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text='В базе данных нет кампаний, которым можно изменить статус',
                                     reply_markup=ReplyKeyboardMarkup(MAIN_MANAGER_KEYBOARD))
            return ConversationHandler.END


def _ccs_select_status(update, context):

    if _is_user_known(context, update):
        text = update.message.text
        global camps_for_selected_cab
        campaigns = camps_for_selected_cab

        if text in list(camp_names.keys()):
            logging.info(f'CS - {update.effective_user.username} selected campaign to get stats')
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text='Выбери статус, который поставим👇🏻',
                                     reply_markup=ReplyKeyboardMarkup([['started'],
                                                                       ['finished'],
                                                                       ['created'],
                                                                       ['archived']], one_time_keyboard=True))
            global selected_campaign
            selected_campaign[text] = campaigns[text]
            return 'change_status'

        else:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text='Ты прислал что-то не то. Давай еще раз')
            return 'select_status'


def _ccs_change_status(update, context):

    if _is_user_known(context, update):
        text = update.message.text
        if text == 'started' or text == 'finished' or text == 'created' or text == 'archived':
            new_status = text
            updated_campaign = {}
            for c_name, c_settings in selected_campaign.items():
                updated_settings = c_settings.copy()
                updated_settings['campaign_status'] = new_status
                updated_campaign[c_name] = updated_settings
            add_campaign_details_to_db(update, updated_campaign)

            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text='Статус кампании изменен',
                                     reply_markup=ReplyKeyboardMarkup(MAIN_MANAGER_KEYBOARD))

        else:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text='Ты прислал что-то не то. Давай еще раз')
            return 'select_status'


def _ccs_failback(update, context):
    logging.info(f'CS - {update.effective_user.username} get failback')

    if _is_user_known(context, update):
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text='Ты ввел не то, что я просил. Давай еще раз')


# Диалог по получению статы кампании
change_status_handler = ConversationHandler(
    entry_points=[MessageHandler(Filters.regex('^(Изменить статус кампании)$'), _ccs_select_cabinet)],
    states={
        'select_camp_status': [CommandHandler('reload', reload),
                               MessageHandler(Filters.text, _ccs_select_camp_status)],
        'select_campaign': [CommandHandler('reload', reload),
                            MessageHandler(Filters.text, _ccs_select_campaign)],
        'select_status': [CommandHandler('reload', reload),
                           MessageHandler(Filters.text, _ccs_select_status)],
        'change_status': [CommandHandler('reload', reload),
                    MessageHandler(Filters.text, _ccs_change_status)]
    },
    fallbacks=[CommandHandler('reload', reload),
               MessageHandler(Filters.text, _ccs_failback)]
)

