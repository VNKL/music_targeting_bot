""" Use python 3.7 """

import datetime
import time

from models.vk.backend import VkBackend
from models.database import *
from models.vk.tools import CPMCalculator
from settings import VK_SUPPORT_ACCOUNT


def _wait_campaign_start(start_time):
    time_now = datetime.datetime.now()
    while time_now < start_time:
        time.sleep(300)
        time_now = datetime.datetime.now()


def _cpm_updating(ad_ids, ad_names, calculator, campaign, cpm_update_interval, end_time, vk):
    time_now = datetime.datetime.now()
    while time_now < end_time:
        ads_stat = vk.get_ads_stat(cabinet_id=campaign['cabinet_id'], client_id=campaign['client_id'],
                                   campaign_id=campaign['campaign_id'], ad_ids=ad_ids, ad_names=ad_names)
        cpm_dict, stop_ads = calculator.updates_for_target_cost(ads_stat)
        vk.update_cpm(cabinet_id=campaign['cabinet_id'], cpm_dict=cpm_dict)
        vk.stop_ads(cabinet_id=campaign['cabinet_id'], ad_ids=stop_ads)
        time.sleep(cpm_update_interval)
        time_now = datetime.datetime.now()


def _campaign_average_calculator(camp_stat, campaign, full_ads_stat, savers):

    spent = camp_stat[campaign['campaign_id']]['spent']
    reach = 0
    listens = 0

    for _, stats in full_ads_stat.items():
        listens += stats['listens']
        reach += stats['reach']

    if reach != 0:
        listens_rate = f'{round((listens / reach * 100), 2)} %'
        save_rate = f'{round((savers / reach * 100), 2)} %'
    else:
        listens_rate = None
        save_rate = None

    if listens != 0:
        listens_cost = f'{round((spent / listens), 2)} руб.'
    else:
        listens_cost = None

    if savers != 0:
        save_cost = f'{round((spent / savers), 2)} руб.'
    else:
        save_cost = None

    campaign_average = {'spent': spent, 'listens': listens, 'saves': savers,
                        'listen_rate': listens_rate, 'listen_cost': listens_cost,
                        'save_rate': save_rate, 'save_cost': save_cost}

    return campaign_average


def start_campaign_from_db(update, campaign, size=8000000, status='testing'):
    """
    Создает и запускает в рекламном кабинете кампанию, предварительно созданную в БД

    :param status: str - статус кампании для записи в БД, 'testing' - если функция запускается непосредственно
    :param size: int - минимальный размер базы ретаргета (количество человек)
    :param update: dict - словарь с обновляениями из телеги
    :param campaign: dict - кампания из базы данных в виде словаря
    :return: nothing
    """
    user = DB.users.find_one({'user_id': update.effective_user.id})
    vk = VkBackend(ads_token=user['vk_token'], support_account=VK_SUPPORT_ACCOUNT, headless=True)

    cabinet_name = campaign['cabinet_name']
    cabinet_id = campaign['cabinet_id']
    client_name = campaign['client_name']
    client_id = campaign['client_id']
    artist_name = campaign['artist_name']
    track_name = campaign['track_name']
    citation = campaign['citation']
    campaign_budget = campaign['campaign_budget']
    artist_group_id = campaign['artist_group_id']
    fake_group_id = campaign['fake_group_id']
    music_interest_filter = campaign['music_interest_filter']
    cover_path = campaign['cover_path']

    # Создает фейк паблик, если его не передали
    if fake_group_id is None:
        fake_group_id = vk.create_group(group_name=artist_name)

    # Добавляет трек в фейк паблик
    vk.add_audio_in_group(group_id=fake_group_id, track_name=f'{artist_name} - {track_name}')

    # Получает базы ретаргета {retarget_name: retarget_id}
    retarget = vk.get_retarget(cabinet_id=cabinet_id, client_id=client_id, size=size)

    # Создает плейлисты [playlist_url]
    playlists = vk.create_playlists(group_id=fake_group_id, playlist_name=track_name,
                                    cover_path=cover_path, count=len(retarget))

    # Создает дарк-посты {post_url: playlist_url}
    if citation is not None:
        text = f'ПРЕМЕЬРА\n \n' \
               f'@public{artist_group_id} ({artist_name.upper()} - {track_name})\n \n' \
               f'{citation}\n \n' \
               f'Слушай в ВК👇🏻'
    else:
        text = f'ПРЕМЕЬРА\n \n' \
               f'@public{artist_group_id} ({artist_name.upper()} - {track_name})\n \n' \
               f'Слушай в ВК👇🏻'

    dark_posts = vk.create_dark_posts(group_id=artist_group_id, playlists=playlists, text=text)

    # Создает новую кампанию в кабинете
    campaign_id = vk.create_campaign(cabinet_id=cabinet_id, client_id=client_id, money_limit=campaign_budget,
                                     campaign_name=f'{artist_name.upper()} / {track_name}')

    # Создает объявления в новой кампании {ad_id: post_url}
    created_ads = vk.create_ads(cabinet_id=cabinet_id, client_id=client_id, campaign_id=campaign_id,
                                retarget=retarget, posts=list(dark_posts.keys()), music=music_interest_filter)

    # Получает инфу о созданных объявлениях {ad_id, {'name': ad_name, 'cpm': ad_cpm, 'status': 1/0}
    ads_info = vk.get_ads(cabinet_id=cabinet_id, client_id=client_id, campaign_id=campaign_id)

    # Собирает полную инфу по объявлениям для записи в БД
    ads_full_info = {}
    for ad_id, post_url in created_ads.items():
        ad_info = {'ad_id': ad_id, 'post_url': post_url, 'playlist_url': dark_posts[post_url]}
        ad_name = ads_info[ad_id]['name']
        ads_full_info[ad_name] = ad_info

    detailed_campaign = {
        f'{artist_name.upper()} / {track_name}': {
            'campaign_id': campaign_id,
            'campaign_status': status,
            'cabinet_id': cabinet_id,
            'cabinet_name': cabinet_name,
            'client_id': client_id,
            'client_name': client_name,
            'artist_name': artist_name,
            'track_name': track_name,
            'citation': citation,
            'campaign_budget': campaign_budget,
            'artist_group_id': artist_group_id,
            'fake_group_id': fake_group_id,
            'music_interest_filter': music_interest_filter,
            'cover_path': cover_path,
            'ads': ads_full_info}}

    add_campaign_details_to_db(update, detailed_campaign)


def automate_campaign_test(update, campaign, target_rate=0.04, stop_rate=0.03):
    """
    Автоматизирует тест кампании по заданным параметрам конверсии, удаляет плохие сегменты,
    снимает лимиты с хороших сегментов, обновляет кампанию в БД

    :param update: dict - словарь с обновляениями из телеги
    :param campaign: dict - кампания из базы данных в виде словаря
    :param target_rate: float - целевая конверсия в клик на плей из охвата
    :param stop_rate: float - конверсия, ниже которой тест считается непройденным
    :return: nothing
    """
    user = DB.users.find_one({'user_id': update.effective_user.id})
    vk = VkBackend(ads_token=user['vk_token'], support_account=VK_SUPPORT_ACCOUNT, headless=True)
    calculator = CPMCalculator(target_rate=target_rate, stop_rate=stop_rate)

    # Достает объявления из БД {ad_name: {'ad_id': int, 'post_url': str, 'playlist_url'}}
    ad_ids = [x['ad_id'] for _, x in campaign['ads'].items()]
    ad_names = {name: x['ad_id'] for name, x in campaign['ads'].items()}
    ad_playlists = {x['ad_id']: x['playlist_url'] for _, x in campaign['ads'].items()}

    # Ожидание заверения теста
    campaign_spent = 0
    while campaign_spent < len(ad_ids) * 100:
        campaign_stat = vk.get_campaign_stat(cabinet_id=campaign['cabinet_id'], campaign_id=campaign['campaign_id'])
        campaign_spent = campaign_stat[campaign['campaign_id']]['spent']

    # Получает стату объявлений {ad_id: {'name': str, 'spent': float, 'reach': int, 'cpm': cpm}}
    ads_stat = vk.get_ads_stat(cabinet_id=campaign['cabinet_id'], client_id=campaign['client_id'],
                               campaign_id=campaign['campaign_id'], ad_ids=ad_ids, ad_names=ad_names)

    # Получает прослушивания плейлистов {playlist_url: playlist_listens}
    listens = vk.get_playlist_listens(group_id=campaign['fake_group_id'], playlist_name=campaign['track_name'])

    # Добавляет к стате объявлений прослушивания их плейлистов
    ads_listens_stat = {}
    for ad_id, ad_stat in ads_stat.items():
        ad_listens = listens[ad_playlists[ad_id]]
        ads_listens_stat[ad_id] = ad_stat
        ads_listens_stat[ad_id].update({'listens': ad_listens})

    # Получает объявления, которые прошли и не прошли тест
    bad_ads = calculator.failed_ads(ads_stat)
    good_ads = set(ad_ids) - set(bad_ads)

    # Удаляет объявления, не прошедшие тест, и снимает ограничения с прошедших
    vk.delete_ads(cabinet_id=campaign['cabinet_id'], ad_ids=bad_ads)
    vk.limit_ads(cabinet_id=campaign['cabinet_id'], ad_ids=good_ads, limit=0)

    # Обновляет кампанию в БД
    updated_ads = {k: v for k, v in campaign['ads'].items() if v['ad_id'] in good_ads}
    updated_campaign = campaign.copy()
    updated_campaign['campaign_status'] = 'tested'
    updated_campaign['ads'] = updated_ads
    add_campaign_details_to_db(update, updated_campaign)


def automate_started_campaign(update, campaign, target_rate=0.04, stop_rate=0.03, target_cost=1., stop_cost=1.5,
                              cpm_step=10., cpm_limit=120., cpm_update_interval=1200):
    user = DB.users.find_one({'user_id': update.effective_user.id})
    vk = VkBackend(ads_token=user['vk_token'], support_account=VK_SUPPORT_ACCOUNT, headless=True)
    calculator = CPMCalculator(target_rate=target_rate, stop_rate=stop_rate, target_cost=target_cost,
                               stop_cost=stop_cost, cpm_step=cpm_step, cpm_limit=cpm_limit)
    ad_ids = [x['ad_id'] for _, x in campaign['ads'].items()]
    ad_names = {name: x['ad_id'] for name, x in campaign['ads'].items()}

    # Снятие лимитов и запуск объявлений
    vk.limit_ads(cabinet_id=campaign['cabinet_id'], ad_ids=ad_ids, limit=0)
    vk.start_ads(cabinet_id=campaign['cabinet_id'], ad_ids=ad_ids)

    # Установка параметров остановки основной кампании
    today = datetime.datetime.combine(datetime.date.today(), datetime.datetime.min.time())
    end_time = today + datetime.timedelta(days=1)

    # Обновление СРМ
    updated_campaign = campaign.copy()
    updated_campaign['campaign_status'] = 'automate'
    add_campaign_details_to_db(update, updated_campaign)
    _cpm_updating(ad_ids, ad_names, calculator, campaign, cpm_update_interval, end_time, vk)

    # Остановка всех объявлений
    vk.stop_ads(cabinet_id=campaign['cabinet_id'], ad_ids=ad_ids)
    updated_campaign = campaign.copy()
    updated_campaign['campaign_status'] = 'finished'
    add_campaign_details_to_db(update, updated_campaign)


def fully_automate_campaign(update, campaign, target_rate=0.04, stop_rate=0.03, target_cost=1., stop_cost=1.5,
                            cpm_step=10., cpm_update_interval=1200, cpm_limit=120.):

    user = DB.users.find_one({'user_id': update.effective_user.id})
    vk = VkBackend(ads_token=user['vk_token'], support_account=VK_SUPPORT_ACCOUNT, headless=True)
    calculator = CPMCalculator(target_rate=target_rate, stop_rate=stop_rate, target_cost=target_cost,
                               stop_cost=stop_cost, cpm_step=cpm_step, cpm_limit=cpm_limit)
    campaign_name = f'{campaign["artist_name"].upper()} / {campaign["track_name"]}'

    # Создание и запуск кампании в кабинете
    start_campaign_from_db(update, campaign, status='automate')
    campaign = get_campaigns_from_db(update)[campaign_name]

    # Автоматизация теста кампании
    automate_campaign_test(update, campaign, target_rate, stop_rate)

    # Обновление кампании, записанной в БД после завершения теста
    campaign = get_campaigns_from_db(update)[campaign_name]

    # Установка параметров времени запуска и остановки основной части кампании
    today = datetime.datetime.combine(datetime.date.today(), datetime.datetime.min.time())
    start_time = today + datetime.timedelta(days=1, hours=7)
    end_time = today + datetime.timedelta(days=2)

    # Ожидание наступления времени запуска основной части кампании и ее запуск
    _wait_campaign_start(start_time)
    ad_ids = [x['ad_id'] for _, x in campaign['ads'].items()]
    ad_names = {name: x['ad_id'] for name, x in campaign['ads'].items()}
    vk.start_ads(cabinet_id=campaign['cabinet_id'], ad_ids=ad_ids)

    # Обвновление стату кампании в БД
    camp_update = campaign.copy()
    camp_update['campaign_status'] = 'automate'
    add_campaign_details_to_db(update, camp_update)

    # Обновление СРМ
    _cpm_updating(ad_ids, ad_names, calculator, campaign, cpm_update_interval, end_time, vk)

    # Остановка всех объявлений
    vk.stop_ads(cabinet_id=campaign['cabinet_id'], ad_ids=ad_ids)
    camp_update = campaign.copy()
    camp_update['campaign_status'] = 'finished'
    add_campaign_details_to_db(update, camp_update)


def get_campaign_average(update, campaign):

    user = DB.users.find_one({'user_id': update.effective_user.id})
    vk = VkBackend(ads_token=user['vk_token'], support_account=VK_SUPPORT_ACCOUNT, headless=True)
    ad_ids = [x['ad_id'] for _, x in campaign['ads'].items()]
    ad_playlists = {x['ad_id']: x['playlist_url'] for _, x in campaign['ads'].items()}
    ad_names = {x['ad_id']: name for name, x in campaign['ads'].items()}

    ads_stat = vk.get_ads_stat(cabinet_id=campaign['cabinet_id'], client_id=campaign['client_id'],
                               campaign_id=campaign['campaign_id'], ad_ids=ad_ids, ad_names=ad_names)
    listens = vk.get_playlist_listens(group_id=campaign['fake_group_id'], playlist_name=campaign['track_name'])
    savers = vk.get_audio_savers(group_id=campaign['fake_group_id'])
    camp_stat = vk.get_campaign_stat(cabinet_id=campaign['cabinet_id'], campaign_id=campaign['campaign_id'])

    full_ads_stat = {}
    for ad_id, ad_stat in ads_stat.items():
        stat = ad_stat.copy()
        playlist_url = ad_playlists[ad_id]
        stat['listens'] = int(listens[playlist_url])
        full_ads_stat[ad_id] = stat

    campaign_average = _campaign_average_calculator(camp_stat, campaign, full_ads_stat, savers)
    vk.get_audio_savers(campaign['fake_group_id'])

    return campaign_average




