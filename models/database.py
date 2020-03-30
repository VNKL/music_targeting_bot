""" Use python 3.7 """

from models.vk.backend import VkAdsBackend
from settings import DB


def get_or_create_user(update):

    permissions = DB.permissions.find_one({'company': 'Black Star'})

    # Проверка пользователя на увроень доступа
    if update.effective_user.username in permissions['managers']:
        permission = 'manager'
    elif update.effective_user.username in permissions['spectators']:
        permission = 'spectator'
    else:
        permission = 'unknown'

    # Проверка на наличие пользователя в БД и если нет, то создание его
    user = DB.users.find_one({'user_id': update.effective_user.id})
    if not user:
        user = {'user_id': update.effective_user.id,
                'chat_id': update.effective_chat.id,
                'user_name': update.effective_user.username,
                'first_name': update.effective_user.first_name,
                'last_name': update.effective_user.last_name,
                'permissions': permissions,
                'vk_token': None}
        DB.users.insert_one(user)

    return user


def add_spectator_to_user(update):
    user = DB.users.find_one({'user_id': update.effective_user.id})
    updated_user = user.copy()
    spectator = update.message.text[1]

    try:
        spectators = user['spectators']
        spectators.append(spectator)
    except KeyError:
        spectators = [spectator]
    updated_user['spectators'] = spectators
    DB.users.update({'_id': user['_id']}, {'$set': updated_user})

    spect_from_db = DB.users.find_one({'user_name': spectator})
    updated_spectator = spect_from_db.copy()
    try:
        managers = updated_spectator['managers']
        managers.append(user['user_id'])
    except KeyError:
        managers = [user['user_id']]
    updated_spectator['managers'] = managers
    DB.users.update({'_id': spect_from_db['_id']}, {'$set': updated_spectator})


def add_token_to_user(update, token):
    # Обвновляет значение vk_token пользователя в БД
    user = DB.users.find_one({'user_id': update.effective_user.id})
    DB.users.update({'_id': user['_id']}, {'$set': {'vk_token': token}})


def add_cabinets_to_user(update, cabinets):
    # Добавляет кабинеты к пользователю в БД
    user = DB.users.find_one({'user_id': update.effective_user.id})

    # Получает списки старых кабинетов
    try:
        old_user_cabinets = list(user['user_cabinets'].keys())
    except KeyError:
        old_user_cabinets = []
    try:
        old_agency_cabinets = list(user['agency_cabinets'].keys())
    except KeyError:
        old_agency_cabinets = []

    # Добавляет новые кабинеты
    new_user_cabinets = {}
    new_agency_cabinets = {}
    for cab_id, cab_info in cabinets.items():
        if cab_info[1] == 'general' and not cab_info[0] in old_user_cabinets:
            new_user_cabinets[cab_info[0]] = {'cabinet_id': cab_id}
        elif cab_info[1] == 'agency' and not cab_info[0] in old_agency_cabinets:
            new_agency_cabinets[cab_info[0]] = {'agency_id': cab_id}
    if new_user_cabinets:
        DB.users.update({'_id': user['_id']}, {'$set': {'user_cabinets': new_user_cabinets}})
    if new_agency_cabinets:
        DB.users.update({'_id': user['_id']}, {'$set': {'agency_cabinets': new_agency_cabinets}})

    # Добавляет новых клиентов
    user = DB.users.find_one({'user_id': update.effective_user.id})
    agency_cabinets = user['agency_cabinets']
    vk = VkAdsBackend(user['vk_token'])
    for agency_name, agency_info in agency_cabinets.items():
        try:
            old_clients = list(agency_cabinets[agency_name]['agency_clients'].keys())
        except KeyError:
            old_clients = []
        new_clients = vk.get_clients(agency_info['agency_id'])
        for client_name, client_id in new_clients.items():
            if client_name not in old_clients:
                DB.users.update({'_id': user['_id']}, {'$set':
                                                           {f'agency_cabinets.{agency_name}.agency_clients':
                                                                {client_name: {'client_id': client_id}}}})


def add_campaign_setting_to_db(update, campaign_settings):
    user = DB.users.find_one({'user_id': update.effective_user.id})
    settings = campaign_settings[user['user_id']]

    # Если прилетели настройки для пользовательского кабинета
    if settings['client_name'] is None:
        cabinet_name = settings["cabinet_name"]
        cab_path = f'user_cabinets.{cabinet_name}.campaigns'
        try:
            camp_old = user['user_cabinets'][settings['cabinet_name']]['campaigns']
        except KeyError:
            camp_old = {}
    # Если прилетели настройки для агентского кабинета
    else:
        cabinet_name = settings["cabinet_name"]
        client_name = settings["client_name"]
        cab_path = f'agency_cabinets.{cabinet_name}.agency_clients.{client_name}.campaigns'
        try:
            camp_old = user['agency_cabinets'][cabinet_name]['agency_clients'][client_name]['campaigns']
        except KeyError:
            camp_old = {}

    settings_new = {
        f'{settings["artist_name"].upper()} / {settings["track_name"]}': {
            'campaign_id': None,
            'campaign_status': 'created',
            'cabinet_id': settings['cabinet_id'],
            'cabinet_name': settings['cabinet_name'],
            'client_id': settings['client_id'],
            'client_name': settings['client_name'],
            'artist_name': settings['artist_name'],
            'track_name': settings['track_name'],
            'citation': settings['citation'],
            'campaign_budget': settings['campaign_budget'],
            'artist_group_id': settings['artist_group_id'],
            'fake_group_id': settings['fake_group_id'],
            'music_interest_filter': settings['music_interest_filter'],
            'cover_path': settings['cover_path']}}

    settings_to_set = camp_old.copy()
    settings_to_set.update(settings_new)
    DB.users.update({'_id': user['_id']}, {'$set': {cab_path: settings_to_set}})


def add_campaign_details_to_db(update, detailed_campaign):
    user = DB.users.find_one({'user_id': update.effective_user.id})

    settings = [v for k, v in detailed_campaign.items()][0]

    # Если прилетели настройки для пользовательского кабинета
    if settings['client_name'] is None:
        cabinet_name = settings['cabinet_name']
        cab_path = f'user_cabinets.{cabinet_name}.campaigns'
        try:
            camp_old = user['user_cabinets'][settings['cabinet_name']]['campaigns']
        except KeyError:
            camp_old = {}
    # Если прилетели настройки для агентского кабинета
    else:
        cabinet_name = settings['cabinet_name']
        client_name = settings["client_name"]
        cab_path = f'agency_cabinets.{cabinet_name}.agency_clients.{client_name}.campaigns'
        try:
            camp_old = user['agency_cabinets'][cabinet_name]['agency_clients'][client_name]['campaigns']
        except KeyError:
            camp_old = {}

    settings_to_set = camp_old.copy()
    settings_to_set.update(detailed_campaign)
    DB.users.update({'_id': user['_id']}, {'$set': {cab_path: settings_to_set}})


def get_campaigns_from_db(update):
    user = DB.users.find_one({'user_id': update.effective_user.id})
    campaigns = {}

    user_cabinets = user['user_cabinets']
    for cab_name, cab_details in user_cabinets.items():
        try:
            campaigns.update(cab_details['campaigns'])
        except KeyError:
            pass

    agency_cabinets = user['agency_cabinets']
    for ag_name, ag_details in agency_cabinets.items():
        for cl_name, cl_details in ag_details['agency_clients'].items():
            try:
                campaigns.update(cl_details['campaigns'])
            except KeyError:
                pass

    return campaigns

