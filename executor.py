""" Use python 3.7 """

from telegram.ext import Updater, CommandHandler, MessageHandler, ConversationHandler, Filters

from models.bot.handlers.command_handlers import *
from models.bot.handlers.create_campaign_handlers import new_campaign_handler
from models.bot.handlers.start_campaign_handlers import start_campaign_handler
from models.bot.handlers.automate_campaign_handlers import automate_campaign_handler
from models.bot.handlers.campaign_stat_handlers import campaign_stats_handler
from models.bot.handlers.add_spectator_handlers import add_spectator_handler
from models.bot.handlers.campaign_details_handlers import campaign_details_handler
import settings


logging.basicConfig(format=f'%(asctime)s - %(levelname)s - %(message)s',
                    level=logging.INFO,
                    filename='bot.log')


def main():

    bot = Updater(token=settings.TELEGRAM_TOKEN, request_kwargs=settings.PROXY, use_context=True)
    dp = bot.dispatcher

    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(CommandHandler('set_token', set_token))
    dp.add_handler(new_campaign_handler)
    dp.add_handler(start_campaign_handler)
    dp.add_handler(automate_campaign_handler)
    dp.add_handler(campaign_stats_handler)
    dp.add_handler(campaign_details_handler)
    dp.add_handler(add_spectator_handler)
    dp.add_handler(MessageHandler(Filters.regex('^(Получить статусы кампаний)$'), get_campaign_statuses))
    dp.add_handler(MessageHandler(Filters.regex('^(Обновить кабинеты)$'), update_cabinets))

    bot.start_polling()     # Собсно начинаем обращаться к телеге за апдейтами
    bot.idle()              # Означает, что бот работает до принудительной остановки


if __name__ == '__main__':
    main()
