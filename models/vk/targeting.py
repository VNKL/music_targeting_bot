""" Use python 3.7 """

import datetime
import time

from models.vk.backend import VkBackend
from models.database import *
from models.vk.tools import CPMCalculator
from settings import VK_SUPPORT_ACCOUNT


def _calculate_listens_cost(listens, spent):
    if listens != 0:
        listens_cost = f'{round((spent / listens), 2)} руб.'
    else:
        listens_cost = None
    return listens_cost


def _calculate_listens_rate_and_save_rate(listens, reach, savers):
    if reach != 0:
        listens_rate = f'{round((listens / reach * 100), 2)} %'
        if isinstance(savers, int):
            save_rate = f'{round((savers / reach * 100), 2)} %'
        else:
            save_rate = '[ошибка, вк заболел]'
    else:
        listens_rate = None
        save_rate = None
    return listens_rate, save_rate


def _calculate_save_cost(savers, spent):
    if savers != 0:
        if isinstance(savers, int):
            save_cost = f'{round((spent / savers), 2)} руб.'
        else:
            save_cost = '[ошибка, вк заболел]'
    else:
        save_cost = None
    return save_cost


def _campaign_average_calculator(camp_stat, campaign, full_ads_stat, savers):

    spent = camp_stat[campaign['campaign_id']]['spent']
    reach = 0
    listens = 0
    segments = 0

    for _, stats in full_ads_stat.items():
        listens += stats['listens']
        reach += stats['reach']
        if stats['listen_rate'] >= 3:
            segments += 1

    listens_rate, save_rate = _calculate_listens_rate_and_save_rate(listens, reach, savers)
    listens_cost = _calculate_listens_cost(listens, spent)
    save_cost = _calculate_save_cost(savers, spent)

    if savers is None:
        savers = '[ошибка, вк заболел]'

    campaign_average = {'reach': reach, 'spent': spent, 'listens': listens, 'saves': savers,
                        'listen_rate': listens_rate, 'segments': segments, 'listen_cost': listens_cost,
                        'save_rate': save_rate, 'save_cost': save_cost}

    return campaign_average


def _cpm_updating(ad_ids, calculator, campaign, cpm_update_interval, end_time, vk):
    # Снятие лимитов и запуск объявлений
    vk.limit_ads(cabinet_id=campaign['cabinet_id'], ad_ids=ad_ids, limit=0)
    time.sleep(3)
    vk.start_ads(cabinet_id=campaign['cabinet_id'], ad_ids=ad_ids)
    time.sleep(3)

    time_now = datetime.datetime.now()
    while time_now < end_time:
        ads_stat = get_campaign_details(campaign)
        cpm_dict, stop_ads = calculator.updates_for_target_cost(ads_stat)
        vk.update_cpm(cabinet_id=campaign['cabinet_id'], cpm_dict=cpm_dict)
        vk.stop_ads(cabinet_id=campaign['cabinet_id'], ad_ids=stop_ads)
        time.sleep(cpm_update_interval)
        time_now = datetime.datetime.now()


def _create_dark_posts(artist_group_id, artist_name, citation, playlists, track_name, vk):
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
    return dark_posts


def _create_detailed_campaign(ads_full_info, artist_group_id, artist_name, cabinet_id, cabinet_name, campaign_budget,
                              campaign_id, citation, client_id, client_name, cover_path, fake_group_id,
                              music_interest_filter, track_name, user):
    detailed_campaign = {
        f'{artist_name.upper()} / {track_name}': {
            'campaign_id': campaign_id,
            'campaign_status': 'started',
            'campaign_token': user['vk_token'],
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
    return detailed_campaign


def _get_ads_full_info(ads_info, created_ads, dark_posts):
    ads_full_info = {}
    for ad_id, post_url in created_ads.items():
        ad_info = {'ad_id': ad_id, 'post_url': post_url, 'playlist_url': dark_posts[post_url]}
        ad_name = ads_info[ad_id]['name']
        ads_full_info[ad_name] = ad_info
    return ads_full_info


def _get_campaign_end_time(start_day):
    if start_day == 'tomorrow':
        today = datetime.datetime.combine(datetime.date.today(), datetime.datetime.min.time())
        start_time = today + datetime.timedelta(days=1) - datetime.timedelta(minutes=1)
        now = datetime.datetime.now()
        while now < start_time:
            time.sleep(300)
            now = datetime.datetime.now()
        today = datetime.datetime.combine(datetime.date.today(), datetime.datetime.min.time())
    else:
        today = datetime.datetime.combine(datetime.date.today(), datetime.datetime.min.time())
    end_time = today + datetime.timedelta(days=1) - datetime.timedelta(minutes=1)
    return end_time


def _wait_campaign_start(start_time):
    time_now = datetime.datetime.now()
    while time_now < start_time:
        time.sleep(300)
        time_now = datetime.datetime.now()


def automate_started_campaign(update, campaign, target_cost=1., stop_cost=1.5, cpm_step=10., cpm_limit=120.,
                              cpm_update_interval=1200, start_day='today'):
    user = DB.users.find_one({'user_id': update.effective_user.id})
    vk = VkBackend(ads_token=user['vk_token'], support_account=VK_SUPPORT_ACCOUNT, headless=True)
    calculator = CPMCalculator(target_cost=target_cost, stop_cost=stop_cost, cpm_step=cpm_step, cpm_limit=cpm_limit)
    ad_ids = [x['ad_id'] for _, x in campaign['ads'].items()]

    # Установка параметров остановки основной кампании
    end_time = _get_campaign_end_time(start_day)

    # Обновление СРМ
    campaign_copy = campaign.copy()
    campaign_copy.update({'campaign_status': 'automate'})
    updated_campaign = {f'{campaign["artist_name"].upper()} / {campaign["track_name"]}': campaign_copy}
    add_campaign_details_to_db(update, updated_campaign)
    _cpm_updating(ad_ids, calculator, campaign, cpm_update_interval, end_time, vk)

    # Остановка всех объявлений
    vk.stop_ads(cabinet_id=campaign['cabinet_id'], ad_ids=ad_ids)
    campaign_copy.update({'campaign_status': 'finished'})
    updated_campaign = {f'{campaign["artist_name"].upper()} / {campaign["track_name"]}': campaign_copy}
    add_campaign_details_to_db(update, updated_campaign)


def get_campaign_average(campaign):

    vk = VkBackend(ads_token=campaign['campaign_token'], support_account=VK_SUPPORT_ACCOUNT, headless=True)
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
        ad_listens = int(listens[playlist_url])
        stat['listens'] = ad_listens
        reach = stat['reach']
        if reach != 0:
            stat['listen_rate'] = round((ad_listens / reach * 100), 2)
        else:
            stat['listen_rate'] = 0
        full_ads_stat[ad_id] = stat

    campaign_average = _campaign_average_calculator(camp_stat, campaign, full_ads_stat, savers)

    return campaign_average


def get_campaign_details(campaign):

    vk = VkBackend(ads_token=campaign['campaign_token'], support_account=VK_SUPPORT_ACCOUNT, headless=True)
    ad_ids = [x['ad_id'] for _, x in campaign['ads'].items()]
    ad_playlists = {x['ad_id']: x['playlist_url'] for _, x in campaign['ads'].items()}
    ad_names = {x['ad_id']: name for name, x in campaign['ads'].items()}

    ads_stat = vk.get_ads_stat(cabinet_id=campaign['cabinet_id'], client_id=campaign['client_id'],
                               campaign_id=campaign['campaign_id'], ad_ids=ad_ids, ad_names=ad_names)
    listens = vk.get_playlist_listens(group_id=campaign['fake_group_id'], playlist_name=campaign['track_name'])

    full_ads_stat = {}
    for ad_id, ad_stat in ads_stat.items():
        stat = ad_stat.copy()
        playlist_url = ad_playlists[ad_id]
        stat['listens'] = int(listens[playlist_url])
        full_ads_stat[ad_id] = stat

    return full_ads_stat


def start_campaign_from_db(update, campaign, size=500000):
    """
    Создает и запускает в рекламном кабинете кампанию, предварительно созданную в БД

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
    sex = campaign['sex']

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
    dark_posts = _create_dark_posts(artist_group_id, artist_name, citation, playlists, track_name, vk)

    # Создает новую кампанию в кабинете
    campaign_id = vk.create_campaign(cabinet_id=cabinet_id, client_id=client_id, money_limit=campaign_budget,
                                     campaign_name=f'{artist_name.upper()} / {track_name}')

    # Создает объявления в новой кампании {ad_id: post_url}
    created_ads = vk.create_ads(cabinet_id=cabinet_id, client_id=client_id, campaign_id=campaign_id, sex=sex,
                                retarget=retarget, posts=list(dark_posts.keys()), music=music_interest_filter)

    # Получает инфу о созданных объявлениях {ad_id, {'name': ad_name, 'cpm': ad_cpm, 'status': 1/0}
    ads_info = vk.get_ads(cabinet_id=cabinet_id, client_id=client_id, campaign_id=campaign_id)

    # Собирает полную инфу по объявлениям для записи в БД
    ads_full_info = _get_ads_full_info(ads_info, created_ads, dark_posts)

    # Записывает детализированную кампанию в БД
    detailed_campaign = _create_detailed_campaign(ads_full_info, artist_group_id, artist_name, cabinet_id, cabinet_name,
                                                  campaign_budget, campaign_id, citation, client_id, client_name,
                                                  cover_path, fake_group_id, music_interest_filter, track_name, user)
    add_campaign_details_to_db(update, detailed_campaign)


def _len_segments_with_rate_over_3(stat):
    segments_over_3 = 0
    for _, v in stat.items():
        listens = v['listens']
        reach = v['reach']
        if reach != 0:
            rate = round((listens / reach * 100), 2)
            if rate >= 3:
                segments_over_3 += 1
    return segments_over_3
