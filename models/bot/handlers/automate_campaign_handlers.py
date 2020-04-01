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


def _ac_select_campaign(update, context):
    logging.info(f'AC - {update.effective_user.username} trying to select campaign to automate')

    if _is_user_known(context, update):
        campaigns = get_campaigns_from_db(update)
        camp_names = [[x] for x in list(campaigns.keys()) if campaigns[x]['campaign_status'] != 'automate' and
                                                             campaigns[x]['campaign_status'] != 'created']
        if len(camp_names) != 0:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=f'Какую кампанию автоматизируем?',
                                     reply_markup=ReplyKeyboardMarkup(camp_names, one_time_keyboard=True))
            return 'select_campaign_to_start'
        else:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=f'В базе данных нет кампаний, которые можно автоматизировать. '
                                          f'Они либо уже автоматизированы, либо еще не запущены в рекламном кабинете. ',
                                     reply_markup=ReplyKeyboardMarkup(MAIN_MANAGER_KEYBOARD))
            return ConversationHandler.END


def _ac_select_campaign_to_start(update, context):

    if _is_user_known(context, update):
        user = DB.users.find_one({'user_id': update.effective_user.id})
        text = update.message.text
        campaigns = get_campaigns_from_db(update)
        if text in list(campaigns.keys()):
            logging.info(f'AC - {update.effective_user.username} selected campaign to automate ')

            start_campaign_settings[user['user_id']] = {'campaign_name': text}
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=f'Пришли через пробел целевую и минимальную конверсии для теста. '
                                          f'Целевая - та, что считается нормальной для этого релиза. '
                                          f'Минимальная - ниже которой сегменты не пройдут тест. '
                                          f'Конверсии присылай в долях от единицы, то есть 4% = 0.04.\n'
                                          f'Например: 0.04 0.03')
            return 'get_rates'
        else:
            logging.info(f'AC - {update.effective_user.username} get text error on selecting campaign')
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=f'Ты прислал что-то не то. Давай еще раз.')
            return 'select_campaign_to_start'


def _ac_get_rates(update, context):
    logging.info(f'AC - {update.effective_user.username} trying to set rates')

    if _is_user_known(context, update):
        user = DB.users.find_one({'user_id': update.effective_user.id})
        text = update.message.text
        text = text.split(' ')

        if len(text) != 2:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=f'Ты прислал что-то не то. Давай еще раз.')
            return 'get_rates'
        else:
            try:
                target_rate = float(text[0])
                stop_rate = float(text[1])
                start_campaign_settings[user['user_id']].update({'target_rate': target_rate, 'stop_rate': stop_rate})
                context.bot.send_message(chat_id=update.effective_chat.id,
                                         text=f'Пришли через пробел целевую и максимальную стоиомсть клика на плей в '
                                              f'рублях. Я буду управлять кампанией, стараясь удерживать целевую '
                                              f'стоимость клика, и буду останавливать сегменты, по которым не '
                                              f'получается сделать стоиомость ниже максимальной.\n'
                                              f'Например: 0.9 1.3')
                logging.info(f'AC - {update.effective_user.username} set rates')
                return 'get_costs'

            except ValueError:
                context.bot.send_message(chat_id=update.effective_chat.id,
                                         text=f'Ты прислал что-то не то. Давай еще раз.')
                return 'get_rates'


def _ac_get_costs(update, context):
    logging.info(f'AC - {update.effective_user.username} trying to set costs')

    if _is_user_known(context, update):
        user = DB.users.find_one({'user_id': update.effective_user.id})
        text = update.message.text
        text = text.split(' ')

        if len(text) != 2:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=f'Ты прислал что-то не то. Давай еще раз.')
            return 'get_costs'
        else:
            try:
                target_cost = float(text[0])
                stop_cost = float(text[1])
                start_campaign_settings[user['user_id']].update({'target_cost': target_cost, 'stop_cost': stop_cost})
                context.bot.send_message(chat_id=update.effective_chat.id,
                                         text=f'Пришли через пробел шаг обновления СРМ и макисмальную ставку СРМ '
                                              f'в рублях. С заданным шагом я буду обновлять СРМ, но никогда не сделаю '
                                              f'его выше максимального.\n'
                                              f'Например: 5.4 118.3')
                logging.info(f'AC - {update.effective_user.username} set costs')
                return 'get_cpm_step_and_limit'

            except ValueError:
                context.bot.send_message(chat_id=update.effective_chat.id,
                                         text=f'Ты прислал что-то не то. Давай еще раз.')
                return 'get_costs'


def _ac_get_cpm_step_and_limit(update, context):
    logging.info(f'AC - {update.effective_user.username} trying to set cpm step and cpm limit')

    if _is_user_known(context, update):
        user = DB.users.find_one({'user_id': update.effective_user.id})
        text = update.message.text
        text = text.split(' ')

        if len(text) != 2:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=f'Ты прислал что-то не то. Давай еще раз.')
            return 'get_cpm_step_and_limit'
        else:
            try:
                cpm_step = float(text[0])
                cpm_limit = float(text[1])
                start_campaign_settings[user['user_id']].update({'cpm_step': cpm_step, 'cpm_limit': cpm_limit})
                context.bot.send_message(chat_id=update.effective_chat.id,
                                         text=f'Пришли интервал, с которым мне обновлять ставки, в минутах.')
                logging.info(f'AC - {update.effective_user.username} set cpm step and cpm limit')
                return 'get_cpm_update_interval'

            except ValueError:
                context.bot.send_message(chat_id=update.effective_chat.id,
                                         text=f'Ты прислал что-то не то. Давай еще раз.')
                return 'get_cpm_step_and_limit'


def _ac_get_cpm_update_interval(update, context):
    logging.info(f'AC - {update.effective_user.username} trying to set cpm update interval')

    if _is_user_known(context, update):
        user = DB.users.find_one({'user_id': update.effective_user.id})
        text = update.message.text

        try:
            cpm_update_interval = int(text) * 60
            start_campaign_settings[user['user_id']].update({'cpm_update_interval': cpm_update_interval})
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=_ac_preparation_summary(update),
                                     parse_mode=ParseMode.HTML,
                                     reply_markup=ReplyKeyboardMarkup([['Да, запускай автоматизацию'],
                                                                       ['Нет, давай заново']],
                                                                      one_time_keyboard=True))
            logging.info(f'AC - {update.effective_user.username} set cpm step and cpm limit')
            return 'confirm_automate'

        except ValueError:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=f'Ты прислал что-то не то. Давай еще раз.')
            return 'get_cpm_update_interval'


def _ac_confirm_automate(update, context):
    logging.info(f'AC - {update.effective_user.username} trying to end dialog')

    if _is_user_known(context, update):
        user = DB.users.find_one({'user_id': update.effective_user.id})
        text = update.message.text

        if text == 'Нет, давай заново':
            campaigns = get_campaigns_from_db(update)
            camp_names = [[x] for x in list(campaigns.keys()) if campaigns[x]['campaign_status'] == 'created']
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=f'Какую кампанию запускаем?',
                                     reply_markup=ReplyKeyboardMarkup(camp_names, one_time_keyboard=True))
            logging.info(f'AC - {update.effective_user.username} choose to start dialog again')
            return 'select_campaign_to_start'

        elif text == 'Да, запускай автоматизацию':
            logging.info(f'AC - {update.effective_user.username} confirmed automate')
            campaigns = get_campaigns_from_db(update)
            campaign = campaigns[start_campaign_settings[user['user_id']]['campaign_name']]
            process = Process(target=automate_started_campaign, args=(
                update,
                campaign,
                start_campaign_settings[user['user_id']]['target_rate'],
                start_campaign_settings[user['user_id']]['stop_rate'],
                start_campaign_settings[user['user_id']]['target_cost'],
                start_campaign_settings[user['user_id']]['stop_cost'],
                start_campaign_settings[user['user_id']]['cpm_step'],
                start_campaign_settings[user['user_id']]['cpm_limit'],
                start_campaign_settings[user['user_id']]['cpm_update_interval']
            ))
            process.start()

            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=f'Автоматизация запускается..',
                                     reply_markup=ReplyKeyboardMarkup(MAIN_MANAGER_KEYBOARD))
            logging.info(f'AC - {update.effective_user.username} started campaign automate')

            return ConversationHandler.END

        else:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=f'Ты прислал что-то не то. Давай еще раз.')
            return 'confirm_automate'


def _ac_preparation_summary(update):
    user = DB.users.find_one({'user_id': update.effective_user.id})
    text = 'Вот что у нас получилось:\n\n'
    summary = start_campaign_settings[user['user_id']]
    for k, v in summary.items():
        text += f'<b>{k}:</b> {v}\n'
    text += '\nВсе ок, подтвержадем?'
    return text


def _ac_failback(update, context):
    logging.info(f'AC - {update.effective_user.username} get failback')

    if _is_user_known(context, update):
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text='Ты ввел не то, что я просил. Давай еще раз')


# Диалог по автоматизации запущенной кампании
automate_campaign_handler = ConversationHandler(
    entry_points=[MessageHandler(Filters.regex('^(Автоматизировать кампанию)$'), _ac_select_campaign)],
    states={
        'select_campaign_to_start': [CommandHandler('reload', reload),
                                     MessageHandler(Filters.text, _ac_select_campaign_to_start)],
        'get_rates': [CommandHandler('reload', reload),
                      MessageHandler(Filters.text, _ac_get_rates)],
        'get_costs': [CommandHandler('reload', reload),
                      MessageHandler(Filters.text, _ac_get_costs)],
        'get_cpm_step_and_limit': [CommandHandler('reload', reload),
                                   MessageHandler(Filters.text, _ac_get_cpm_step_and_limit)],
        'get_cpm_update_interval': [CommandHandler('reload', reload),
                                    MessageHandler(Filters.text, _ac_get_cpm_update_interval)],
        'confirm_automate': [CommandHandler('reload', reload),
                             MessageHandler(Filters.text, _ac_confirm_automate)]
    },
    fallbacks=[CommandHandler('reload', reload),
               MessageHandler(Filters.text, _ac_failback)]
)

