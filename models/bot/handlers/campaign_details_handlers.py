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


def _cd_select_cabinet(update, context):
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


def _cd_select_camp_status(update, context):
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


def _cd_select_campaign(update, context):
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
            return 'get_sort_type'
        else:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text='В базе данных нет кампаний, по которым можно получить стату',
                                     reply_markup=ReplyKeyboardMarkup(MAIN_MANAGER_KEYBOARD))
            return ConversationHandler.END


def _cd_get_sort_type(update, context):
    logging.info(f'CD - {update.effective_user.username} trying to choose sort type')

    if _is_user_known(context, update):
        text = update.message.text
        if text in camp_names:
            global camp_name
            camp_name = text
            keyboard = [['Сортировка по названию базы'],
                        ['Сортировка по кликам на плей'],
                        ['Сортировка по стоимости клика'],
                        ['Сортировка по конверсии в клики']]
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text='Выбери тип сортировки👇🏻',
                                     reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))
            return 'get_camp_details'
        else:
            global camps_for_selected_cab
            campaigns = camps_for_selected_cab
            keyboard = [[f'{name} (is {v["campaign_status"]})'] for name, v in campaigns.items() if
                        v['campaign_status'] != 'created']
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text='Ты прислал что-то не то. Выбери кампанию👇🏻',
                                     reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))
            return 'get_sort_type'


def _cd_get_camp_details(update, context):

    if _is_user_known(context, update):
        text = update.message.text
        global camps_for_selected_cab
        campaigns = camps_for_selected_cab

        sort_types = ['Сортировка по названию базы', 'Сортировка по кликам на плей',
                      'Сортировка по стоимости клика', 'Сортировка по конверсии в клики']

        if text in sort_types:
            logging.info(f'CD - {update.effective_user.username} selected sort type')

            help_text = f'Получаю детализацию кампании <b>"{camp_name}"</b>..'
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=help_text,
                                     parse_mode=ParseMode.HTML)

            campaign = campaigns[camp_name]
            stat = get_campaign_details(campaign)
            answer = _answer_for_campaign_details(stat, text)

            user = DB.users.find_one({'user_id': update.effective_user.id})
            for batch in answer:
                if user['permissions'] == 'manager':
                    context.bot.send_message(chat_id=update.effective_chat.id,
                                             text=batch,
                                             parse_mode=ParseMode.HTML,
                                             reply_markup=ReplyKeyboardMarkup(MAIN_MANAGER_KEYBOARD))
                elif user['permissions'] == 'spectator':
                    context.bot.send_message(chat_id=update.effective_chat.id,
                                             text=batch,
                                             parse_mode=ParseMode.HTML,
                                             reply_markup=ReplyKeyboardMarkup(MAIN_SPECTATOR_KEYBOARD))
            logging.info(f'CD - {update.effective_user.username} get campaign details: {camp_name}')
            return ConversationHandler.END

        else:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text='Ты прислал что-то не то. Давай еще раз')
            return 'get_camp_details'


def _answer_for_campaign_details(stat, key):

    stat_list = _stat_to_list(stat)

    if key == 'Сортировка по названию базы':
        stat_list.sort(key=_sort_by_name, reverse=False)
    elif key == 'Сортировка по кликам на плей':
        stat_list.sort(key=_sort_by_listens, reverse=True)
    elif key == 'Сортировка по стоимости клика':
        stat_list.sort(key=_sort_by_cost, reverse=False)
    elif key == 'Сортировка по конверсии в клики':
        stat_list.sort(key=_sort_by_rate, reverse=True)
    else:
        stat_list.sort(key=_sort_by_listens, reverse=True)

    text = ''
    for segment in stat_list:
        text += f'<b>{segment[0]}</b>: {segment[1]} кликов по {segment[2]} руб, конверсия {segment[3]}%\n'

    return _message_to_batches(text)


def _message_to_batches(text):
    answer = []
    if len(text) > 4096:
        lines = text.split('\n')
        temp_text = ''
        for line in lines:
            if len(temp_text) + len(line) < 4096:
                temp_text += line + '\n'
            else:
                answer.append(temp_text)
                temp_text = line + '\n'
        answer.append(temp_text)
    else:
        answer.append(text)
    return answer


def _stat_to_list(stat):
    stat_list = []
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
        stat_list.append([v['name'], listens, cost, rate])
    return stat_list


def _sort_by_name(x):
    return x[0]


def _sort_by_listens(x):
    return x[1]


def _sort_by_cost(x):
    return x[2]


def _sort_by_rate(x):
    return x[3]


def _cd_failback(update, context):
    logging.info(f'CD - {update.effective_user.username} get failback')

    if _is_user_known(context, update):
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text='Ты ввел не то, что я просил. Давай еще раз')


# Диалог по получению статы кампании
campaign_details_handler = ConversationHandler(
    entry_points=[MessageHandler(Filters.regex('^(Получить детализацию кампании)$'), _cd_select_cabinet)],
    states={
        'select_camp_status': [CommandHandler('reload', reload),
                               MessageHandler(Filters.text, _cd_select_camp_status)],
        'select_campaign': [CommandHandler('reload', reload),
                            MessageHandler(Filters.text, _cd_select_campaign)],
        'get_sort_type': [CommandHandler('reload', reload),
                          MessageHandler(Filters.text, _cd_get_sort_type)],
        'get_camp_details': [CommandHandler('reload', reload),
                             MessageHandler(Filters.text, _cd_get_camp_details)]
    },
    fallbacks=[CommandHandler('reload', reload),
               MessageHandler(Filters.text, _cd_failback)]
)

