""" Use python 3.7 """

import selenium
from selenium import webdriver
from bs4 import BeautifulSoup
import re
import time
import json
import requests
import pickle

from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class VkBackend:

    def __init__(self, ads_token, support_account, headless=True):
        """
        Общий класс для работы как с API ВК, так и с аудио пабликов

        Support Account - аккаунт для работы с фейк-группами и их аудиозаписями

        :param ads_token: str - токен для работы с рекламным кабинетом
        :param support_account: dict - {'login': .., 'password': .., 'token': .., 'user_id': ..}
        :param headless: True - браузер запустится без интерфейса, False - с интерфейсом
        """
        self.AdsBackend = VkAdsBackend(ads_token)
        self.AudioBackend = VkAudioBackend(support_account, headless)
        self.Bagosi = Bagosi(support_account['login'], support_account['password'], headless=headless)

    def create_group(self, group_name):
        """
        Создает новый паблик и удаляет из контактов его создателя

        :param group_name: str - название нового паблика
        :return: int - group_id
        """
        return self.AudioBackend.create_group(group_name)

    def add_audio_in_group(self, group_id, track_name):
        """
        Ищет трек в поиске по аудиозаписям ВК и, если находит, добавляет его в аудио паблика

        :param group_id: int - айди группы, в которую будет добавлен трек
        :param track_name: str - название трека в формате "artist_name - track_name"
        :return: True - если трек успешно добавлен, False - если не добавлен
        """
        return self.AudioBackend.add_audio_in_group(group_id, track_name)

    def get_playlist_listens(self, group_id, playlist_name):
        """
        Возвращает прослушивания плейлистов

        :param group_id: int - айди паблика, в котором находятся плейлисты
        :param playlist_name: str - название плейлистов
        :return: dict - {playlist_url: playlist_listens}
        """
        return self.AudioBackend.get_playlists_listens(group_id, playlist_name)

    def get_audio_savers(self, group_id):
        """
        Возвращает количество людей, добавивших себе последний трек из аудио паблика

        :param group_id: int - айди паблика, из которого смотрим добавления
        :return: int - количество людей, добавивших себе последний трек в паблике
        """
        return self.Bagosi.get_savers_count(url=f'https://vk.com/public{group_id}')

    def get_retarget(self, cabinet_id, client_id=None, size=650000):
        """
        Возвращает базы ретаргета из кабинета

        :param cabinet_id: int - айди кабинета, пользовательского или агентского
        :param client_id: int - айди клиента агентского кабинета, None - если в cabinet_id пользовательский кабинет
        :param size: int - нижний порог размера базы ретаргета (кол-во человек)
        :return: dict - {retarget_name: retarget_id}
        """
        return self.AdsBackend.get_retarget(cabinet_id, client_id, size)

    def get_campaigns(self, cabinet_id, client_id=None):
        """
        Получение кампаний из рекламног кабинета

        :param cabinet_id: int - айди рекламного кабинета (личного или агентского)
        :param client_id: int - айди клиента, если передеается cabinet_id агентства

        :return: dict - {campaign_name: campaign_id}
        """
        return self.AdsBackend.get_campaigns(cabinet_id, client_id)

    def get_ads(self, cabinet_id, campaign_id, include_deleted=False, client_id=None):
        """
        Возвращает айди объявлений и их названий из рекламной кампании

        :param cabinet_id: int - айди рекламного кабинета (личного или агентского)
        :param client_id: int - айди клиента, если передеается cabinet_id агентства
        :param campaign_id: int - айди рекламной кампании, из которой будут получены объявления
        :param include_deleted: True - включая архивированные объявления, False - не включая

        :return: dict - {ad_id, {'name': ad_name, 'cpm': ad_cpm, 'status': 1/0}
                        cpm - в копейках, status 1 - запущено, status 0 - остановлено
        """
        return self.AdsBackend.get_ads(cabinet_id, campaign_id, include_deleted, client_id)

    def get_cabinets(self):
        """
        Возвращает словарь имен кабинетов с их айди

        :return: dict - {cabinet_id: [cabinet_name, cabinet_type]}
        """
        self.AdsBackend.get_cabinets()

    def get_clients(self, cabinet_id):
        """
        Возвращает словарь имен клиентов кабинета с их айди

        :param cabinet_id: int - айди рекламного кабинета (личного или агентского)
        :return: dict - {client_name: client_id}
        """
        return self.AdsBackend.get_clients(cabinet_id)

    def get_ads_stat(self, cabinet_id, campaign_id, ad_ids, ad_names, client_id=None):
        """
        Возвращает стату с рекламных объявлений

        :param cabinet_id: int - айди рекламного кабинета (личного или агентского)
        :param client_id: int - айди клиента, если в cabinet_id передан агентский кабинет
        :param campaign_id: int - айди кампании
        :param ad_ids: list of int - список айди объявлений
        :param ad_names: dict - {ad_id: ad_name}
        :return: dict - {ad_id: {'name': str, 'spent': float, 'reach': int, 'cpm': cpm}}
        """
        return self.AdsBackend.get_ads_stat(cabinet_id, campaign_id, ad_ids, ad_names, client_id)

    def get_campaign_stat(self, cabinet_id, campaign_id):
        """
        Возвращает стату по кампании

        :param cabinet_id: int - айди кабинета (пользовательского или агентского)
        :param campaign_id: int - айди кампании
        :return: dict - {campaign_id: {'spent': spent, 'reach': reach}}
        """
        return self.AdsBackend.get_campaign_stat(cabinet_id, campaign_id)

    def create_dark_posts(self, group_id, playlists, text):
        """ Создание дарк-постов в паблике для последующего их использования в таргете

        :param group_id: str или int - айди паблика артиста
        :param playlists: list of str - список полноценных ссылок на плейлисты для постов
        :param text: str - тест для постов со всеми отступами, отметками и эмодзи (как в ВК)
        :return: dict - {post_url: playlist_url}
        """
        return self.AdsBackend.create_dark_posts(group_id, playlists, text)

    def create_campaign(self, cabinet_id, campaign_name, money_limit, client_id=None):
        """
        Создание новой кампании в кабинете

        :param cabinet_id: int - айди рекламного кабинета (личного или агентского)
        :param client_id: int - айди клиента, если передеается cabinet_id агентства
        :param campaign_name: str - название рекламной кампании
        :param money_limit: int - лимит по бюджету для рекламной кампании
        :return: int - campaign_id
        """
        return self.AdsBackend.create_campaign(cabinet_id, campaign_name, money_limit, client_id)

    def create_ads(self, cabinet_id, campaign_id, retarget, posts, music=True, client_id=None):
        """
        Создание объявлений в выбранной кампании

        :param cabinet_id: int - айди рекламного кабинета (личного или агентского)
        :param client_id: int - айди клиента, если передеается cabinet_id агентства
        :param campaign_id: int - айди кампании, в которой создаются объявления
        :param retarget: dict - {retarget_name: retarget_id}
        :param posts: list of str - список полных ссылок на дарк-посты
        :param music: True - с сужением по интересу музыка, False - без сужения
        :return: dict - {ad_id: post_url}
        """
        return self.AdsBackend.create_ads(cabinet_id, campaign_id, retarget, posts, music, client_id)

    def create_playlists(self, group_id, playlist_name, cover_path=None, count=1):
        """
        Создает плейлисты в паблике с последним добавленным в аудио паблика треком

        :param group_id: int - айди паблика, в котором будут созданы плейлисты
        :param playlist_name: str - название для плейлиста
        :param cover_path: str - путь до файла обложки на диске, если None - подтянет официальную обложку трека
        :param count: int - количество плейлистов, которые будут созданы
        :return: list - список полных ссылок на созданные плейлисты
        """
        return self.AudioBackend.create_playlists(group_id, playlist_name, cover_path, count)

    def delete_ads(self, cabinet_id, ad_ids):
        """
        Удаление объявлений по их айди

        :param cabinet_id: int - айди рекламного кабинета (личного или агентского)
        :param ad_ids: list of int - список айди объявлений, не более 100
        """
        self.AdsBackend.delete_ads(cabinet_id, ad_ids)

    def limit_ads(self, cabinet_id, ad_ids, limit):
        """
        Устанавливает ограничения по бюджету на объявления, 0 - без ограничения

        :param cabinet_id: int - айди рекламного кабинета (личного или агентского)
        :param ad_ids: list of int - список айди объявлений
        :param limit: int - ограничение по бюджету на каждое объявление в рублях
        """
        self.AdsBackend.limit_ads(cabinet_id, ad_ids, limit)

    def stop_ads(self, cabinet_id, ad_ids):
        """
        Останавливает активные объявления

        :param cabinet_id: int - айди рекламного кабинета (личного или агентского)
        :param ad_ids: list of int - список айди объявлений
        """
        self.AdsBackend.stop_ads(cabinet_id, ad_ids)

    def start_ads(self, cabinet_id, ad_ids):
        """
        Запускает остановленные объявления

        :param cabinet_id: int - айди рекламного кабинета (личного или агентского)
        :param ad_ids: list of int - список айди объявлений
        """
        self.AdsBackend.start_ads(cabinet_id, ad_ids)

    def update_cpm(self, cabinet_id, cpm_dict):
        """
        Останавливает активные объявления

        :param cabinet_id: int - айди рекламного кабинета (личного или агентского)
        :param cpm_dict: dict - {ad_id: cpm}, cpm - float в рублях с копейками после точки
        """
        self.AdsBackend.update_cpm(cabinet_id, cpm_dict)


class VkAudioBackend:

    def __init__(self, support_account, headless=True):
        self.login = support_account['login']
        self.password = support_account['password']
        self.token = support_account['token']
        self.user_id = support_account['user_id']
        self.browser = self._config_selenium(headless)
        self.session = requests.session()
        self.is_auth = False

    def _config_selenium(self, headless):
        """
        Конфигурация selenium (headless или с интерфейсом)

        """
        chrome_options = webdriver.ChromeOptions()
        prefs = {"profile.managed_default_content_settings.images": 2}
        chrome_options.add_experimental_option("prefs", prefs)
        if headless is True:
            chrome_options.add_argument('headless')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/'
                                    '537.36 (KHTML, like Gecko) Chrome/64.0.3282.140 Safari/537.36 Edge/18.17763')
        browser = webdriver.Chrome('chromedriver\chromedriver.exe', options=chrome_options)
        return browser

    def _auth_without_coockies(self):
        self.browser.get('http://www.vk.com')
        login = WebDriverWait(self.browser, 10).until(EC.presence_of_element_located((By.ID, 'index_email')))
        password = WebDriverWait(self.browser, 10).until(EC.presence_of_element_located((By.ID, 'index_pass')))
        enter = WebDriverWait(self.browser, 10).until(EC.presence_of_element_located((By.ID, 'index_login_button')))
        login.send_keys(self.login)
        password.send_keys(self.password)
        enter.click()
        time.sleep(1)
        if self.browser.current_url == 'https://vk.com/feed':
            print('successfully auth on vk.com')
            cookies = self.browser.get_cookies()
            with open(f'chromedriver/coockies_{self.login}.pkl', 'wb') as file:
                pickle.dump(cookies, file)
        elif self.browser.current_url == 'https://vk.com/login?act=authcheck':
            two_fact_form = self.browser.find_element_by_xpath('//*[@id="authcheck_code"]')
            two_fact_code = input('Введи код двухфакторной аутентификации: ')
            two_fact_form.send_keys(two_fact_code)
            submit_btn = self.browser.find_element_by_xpath('//*[@id="login_authcheck_submit_btn"]')
            submit_btn.click()
            time.sleep(3)
            if self.browser.current_url == 'https://vk.com/feed':
                print('successfully auth on vk.com')
                cookies = self.browser.get_cookies()
                with open(f'chromedriver/coockies_{self.login}.pkl', 'wb') as file:
                    pickle.dump(cookies, file)
            else:
                raise RuntimeError('something wrong with login on vk.com, run with headless=False to see it')
        else:
            raise RuntimeError('something wrong with login on vk.com, run with headless=False to see it')

    def _auth_with_coockies(self):
        with open(f'chromedriver/coockies_{self.login}.pkl', 'rb') as file:
            cookies_load = pickle.load(file)
            for cookie in cookies_load:
                if 'expiry' in cookie:
                    del cookie['expiry']

            self.browser.get('https://vk.com/blank.php?code=40&gid=646266266')
            time.sleep(1)
            for i in cookies_load:
                self.browser.add_cookie(i)

            self.browser.get('https://vk.com/feed')
            time.sleep(1)
            if self.browser.current_url == 'https://vk.com/feed':
                print('successfully auth on vk.com')
            else:
                self._auth_without_coockies()

    def _set_group_params(self, group_id, user_id):
        time.sleep(1)
        url = f'https://api.vk.com/method/groups.edit?group_id={group_id}&' \
              f'audio=1&' \
              f'access_token={self.token}&v=5.103'
        resp = self.session.get(url).json()
        try:
            if resp['response']:
                pass
        except KeyError:
            print(resp)

        time.sleep(1)
        url = f'https://api.vk.com/method/groups.editManager?group_id={group_id}&' \
              f'user_id={user_id}&' \
              f'is_contact=0&' \
              f'access_token={self.token}&v=5.103'
        resp = self.session.get(url).json()
        try:
            if resp['response']:
                pass
        except KeyError:
            print(resp)

    def _playlists_page_scroll(self, group_id):
        self._check_browser_auth()
        self.browser.get(f'https://vk.com/audios-{group_id}?section=playlists')
        time.sleep(1)

        # Scroll to page bottom
        last_height = self.browser.execute_script("return document.body.scrollHeight")
        while True:
            # Scroll down to bottom
            self.browser.execute_script("window.scrollTo(0, document.body.scrollHeight);")

            # Wait to load page
            time.sleep(0.5)

            # Calculate new scroll height and compare with last scroll height
            new_height = self.browser.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

    def _create_playlist_without_cover(self, group_id, playlist_name):
        """
        Добавляет в аудиозаписи паблика плейлист без обложки
        (обложка тянется из единственного трека в этом плейлсите)

        """
        if self.browser.current_url != f'https://vk.com/audios-{group_id}':
            self.browser.get(f'https://vk.com/audios-{group_id}')

        try:
            # Click on "add playlist" button
            add_btn = WebDriverWait(self.browser, 1).until(EC.presence_of_element_located(
                (By.XPATH, '//*[@id="content"]/div/div[2]/div[1]/h2/ul/button[2]')))
            add_btn.click()

            # Paste playlist_name in form
            form = WebDriverWait(self.browser, 1).until(EC.presence_of_element_located(
                (By.XPATH, '//*[@id="ape_pl_name"]')))
            form.send_keys(playlist_name)

            # Select last group audio and create playlist
            select_btn = WebDriverWait(self.browser, 1).until(EC.presence_of_element_located(
                (By.XPATH, '//*[@id="ape_add_audios_btn"]')))
            select_btn.click()
            audio_flag = WebDriverWait(self.browser, 1).until(EC.presence_of_element_located(
                (By.XPATH, '//*[@id="box_layer"]/div[2]/div/div[2]/div/div[5]/div/div[1]')))
            audio_flag.click()
            save_btn = WebDriverWait(self.browser, 1).until(EC.presence_of_element_located(
                (By.XPATH, '//*[@id="box_layer"]/div[2]/div/div[3]/div[1]/table/tbody/tr/td/button')))
            save_btn.click()

        except selenium.common.exceptions.TimeoutException:
            self.browser.refresh()
            self._create_playlist_without_cover(group_id, playlist_name)

        except selenium.common.exceptions.ElementClickInterceptedException:
            self.browser.refresh()
            self._create_playlist_without_cover(group_id, playlist_name)

    def _create_playlist_with_cover(self, group_id, playlist_name, cover_path):
        """" Добавление в аудиозаписи паблика плейлиста со своей обложкой """

        if self.browser.current_url != f'https://vk.com/audios-{group_id}':
            self.browser.get(f'https://vk.com/audios-{group_id}')

        try:
            # Click on "add playlist" button
            add_btn = WebDriverWait(self.browser, 1).until(EC.presence_of_element_located(
                (By.XPATH, '//*[@id="content"]/div/div[2]/div[1]/h2/ul/button[2]')))
            add_btn.click()

            # Upload cover from cover_path
            cover_btn = WebDriverWait(self.browser, 1).until(EC.presence_of_element_located(
                (By.XPATH, '//*[@id="box_layer"]/div[2]/div/div[2]/div/div[1]/div[2]/input')))
            cover_btn.send_keys(cover_path)
            time.sleep(2)

            # Paste playlist_name in form
            form = WebDriverWait(self.browser, 1).until(EC.presence_of_element_located(
                (By.XPATH, '//*[@id="ape_pl_name"]')))
            form.send_keys(playlist_name)

            # Select last group audio and create playlist
            select_btn = WebDriverWait(self.browser, 1).until(EC.presence_of_element_located(
                (By.XPATH, '//*[@id="ape_add_audios_btn"]')))
            select_btn.click()
            audio_flag = WebDriverWait(self.browser, 1).until(EC.presence_of_element_located(
                (By.XPATH, '//*[@id="box_layer"]/div[2]/div/div[2]/div/div[5]/div/div[1]')))
            audio_flag.click()
            save_btn = WebDriverWait(self.browser, 1).until(EC.presence_of_element_located(
                (By.XPATH, '//*[@id="box_layer"]/div[2]/div/div[3]/div[1]/table/tbody/tr/td/button')))
            save_btn.click()

        except selenium.common.exceptions.TimeoutException:
            self.browser.refresh()
            self._create_playlist_with_cover(group_id, playlist_name, cover_path)

        except selenium.common.exceptions.ElementClickInterceptedException:
            self.browser.refresh()
            self._create_playlist_with_cover(group_id, playlist_name, cover_path)

    def _add_audio_from_users_audio(self, group_id, track_name):
        self.browser.get(f'https://vk.com/audios-{group_id}')
        time.sleep(1)

        try:
            add_btn = WebDriverWait(self.browser, 1).until(EC.presence_of_element_located(
                (By.XPATH, '//*[@id="content"]/div/div[2]/div[1]/h2/ul/button[1]')))
            add_btn.click()

            # Click on "choise from my audios"
            add_btn = WebDriverWait(self.browser, 1).until(EC.presence_of_element_located(
                (By.XPATH, '//*[@id="box_layer"]/div[2]/div/div[3]/div[1]/div[2]/a')))
            add_btn.click()

            # Past audio_name in search form
            search_form = WebDriverWait(self.browser, 1).until(EC.presence_of_element_located(
                (By.XPATH, '//*[@id="ape_edit_playlist_search"]')))
            search_form.send_keys(track_name)

            # Click on most relevant search result
            add_btn = WebDriverWait(self.browser, 1).until(EC.presence_of_element_located(
                (By.XPATH, '//*[@id="box_layer"]/div[3]/div/div[2]/div/div[5]/div[1]/div[1]')))
            add_btn.click()

            # Check for success
            self.browser.refresh()
            time.sleep(1)
            html = self.browser.page_source
            if html.lower().find(track_name.lower()):
                print(f'successfully added "{track_name}" in group audios')
                return True
            else:
                return False

        except selenium.common.exceptions.ElementClickInterceptedException:
            print('add audio in group error')
            return False

        except selenium.common.exceptions.TimeoutException:
            print('add audio in group error')
            return False

    def _check_browser_auth(self):
        if self.is_auth is False:
            self.browser_auth()
            self.is_auth = True

    def browser_auth(self):
        """
        Авторизация selenium на vk.vom

        """
        try:
            self._auth_with_coockies()
        except Exception:
            self._auth_without_coockies()

    def create_group(self, group_name):
        """
        Создает новый паблик, открывает в нем аудиозаписи, удаляет создателя из блока контактов

        :param group_name:      str - название нового паблика

        :return:                int - group_id

        """
        url = f'https://api.vk.com/method/groups.create?title={group_name}&' \
              f'type=public&' \
              f'public_category=1002&' \
              f'subtype=3&' \
              f'access_token={self.token}&v=5.103'

        resp = self.session.get(url).json()
        try:
            group_id = resp['response']['id']
            self._set_group_params(group_id, self.user_id)
            return group_id
        except KeyError:
            print('Something wrong with create_group')
            print(resp)

    def add_audio_in_group(self, group_id, track_name):
        """ Поиск и добавление трека в аудиозаписи паблика """
        self._check_browser_auth()
        self.browser.get(f'https://vk.com/audios-{group_id}')
        time.sleep(1)

        # Click on "add audio" button
        try:
            add_btn = WebDriverWait(self.browser, 1).until(EC.presence_of_element_located(
                (By.XPATH, '//*[@id="content"]/div/div[2]/div[1]/h2/ul/button[1]')))
            add_btn.click()

            # Click on "choise from my audios"
            add_btn = WebDriverWait(self.browser, 1).until(EC.presence_of_element_located(
                (By.XPATH, '//*[@id="box_layer"]/div[2]/div/div[3]/div[1]/div[2]/a')))
            add_btn.click()

            # Past audio_name in search form
            search_form = WebDriverWait(self.browser, 1).until(EC.presence_of_element_located(
                (By.XPATH, '//*[@id="ape_edit_playlist_search"]')))
            search_form.send_keys(track_name)

            # Click on most relevant search result
            add_btn = WebDriverWait(self.browser, 1).until(EC.presence_of_element_located(
                (By.XPATH, '//*[@id="box_layer"]/div[3]/div/div[2]/div/div[5]/div[2]/div[1]')))
            add_btn.click()

            # Check for success
            self.browser.refresh()
            time.sleep(1)
            html = self.browser.page_source
            if html.lower().find(track_name.lower()):
                print(f'successfully added "{track_name}" in group audios')
                return True
            else:
                return False

        except selenium.common.exceptions.ElementClickInterceptedException:
            return self._add_audio_from_users_audio(group_id, track_name)

        except selenium.common.exceptions.TimeoutException:
            return self._add_audio_from_users_audio(group_id, track_name)

    def create_playlists(self, group_id, playlist_name, cover_path=None, count=1):
        """ Создание плейлистов в паблике """
        self._check_browser_auth()
        playlists_old = self.get_playlists_urls(group_id, playlist_name)

        self.browser.get(f'https://vk.com/audios-{group_id}')
        time.sleep(1)

        for n in range(count):
            if cover_path is None:
                self._create_playlist_without_cover(group_id, playlist_name)
                print(f'playlist {n + 1} / {count} created')
            else:
                self._create_playlist_with_cover(group_id, playlist_name, cover_path)
                print(f'playlist {n + 1} / {count} created')

        playlists_all = self.get_playlists_urls(group_id, playlist_name)

        if playlists_old is not None:
            playlist_new = list(set(playlists_all) - set(playlists_old))
            return playlist_new
        else:
            return playlists_all

    def get_playlists_urls(self, group_id, playlist_name):
        """ Получение ссылок на все плейлисты с указанным названем """
        self._check_browser_auth()
        self._playlists_page_scroll(group_id)
        html = self.browser.page_source

        soup = BeautifulSoup(html, 'lxml')
        playlist_objects = soup.find_all(class_='audio_item__title')

        playlist_urls = []
        for playlist in playlist_objects:
            if playlist.get_text().lower() == playlist_name.lower():
                link = playlist['href']
                url = f'https://vk.com{link}'
                playlist_urls.append(url)

        if playlist_urls:
            return playlist_urls
        else:
            print(f'Group {group_id} have no playlists with name "{playlist_name}"')
            return None

    def get_playlists_listens(self, group_id, playlist_name):
        """ Получение количества прослушиваний со всех плейлитов с заданным названием """
        self._check_browser_auth()
        self._playlists_page_scroll(group_id)
        html = self.browser.page_source

        soup = BeautifulSoup(html, 'lxml')
        playlists = soup.find_all('div', class_=re.compile('^audio_pl_item2'))
        listens = {}
        for playlist in playlists:
            name = playlist.find(class_='audio_item__title').get_text()
            if name.lower() == playlist_name.lower():
                link = playlist.find(class_='audio_pl__cover')['href']
                url = f'https://vk.com{link}'
                strm_1 = playlist.find(class_='audio_pl__stats_listens').get_text()
                try:
                    strm_2 = playlist.find(class_='num_delim').get_text()
                    clicks = f'{strm_1}{strm_2}'
                    clicks = clicks.replace(' ', '')
                except AttributeError:
                    clicks = strm_1.replace(' ', '')
                    if 'K' in clicks:
                        clicks = int(clicks[:-1]) * 1000
                listens[url] = clicks

        return listens

    def __del__(self):
        try:
            self.browser.close()
        except AttributeError:
            pass


class VkAdsBackend:

    def __init__(self, token):

        self.token = token
        self.session = requests.session()
        self.ad_names = {}

    def _url_for_get_campaigns(self, cabinet_id, client_id):
        # Если получаем из личного кабинета
        if client_id is None:
            url = f'https://api.vk.com/method/ads.getCampaigns?account_id={cabinet_id}&' \
                  f'access_token={self.token}&v=5.103'
        # Если получаем из кабинета агентства
        else:
            url = f'https://api.vk.com/method/ads.getCampaigns?account_id={cabinet_id}&' \
                  f'client_id={client_id}&' \
                  f'access_token={self.token}&v=5.103'
        return url

    def _url_for_get_retarget(self, cabinet_id, client_id):
        # Если получаем из личного кабинета
        if client_id is None:
            url = f'https://api.vk.com/method/ads.getTargetGroups?account_id={cabinet_id}&' \
                  f'access_token={self.token}&v=5.103'
        # Если получаем из кабинета агентства
        else:
            url = f'https://api.vk.com/method/ads.getTargetGroups?account_id={cabinet_id}&' \
                  f'client_id={client_id}&' \
                  f'access_token={self.token}&v=5.103'
        return url

    def _url_for_get_ads(self, cabinet_id, client_id, campaign_id, include_deleted):
        # Если получаем из личного кабинета
        if client_id is None:
            url = f'https://api.vk.com/method/ads.getAds?account_id={cabinet_id}&' \
                  f'campaign_ids=[{campaign_id}]&' \
                  f'include_deleted={include_deleted}&' \
                  f'access_token={self.token}&v=5.103'
        # Если получаем из кабинета агентства
        else:
            url = f'https://api.vk.com/method/ads.getAds?account_id={cabinet_id}&' \
                  f'client_id={client_id}&' \
                  f'campaign_ids=[{campaign_id}]&' \
                  f'include_deleted={include_deleted}&' \
                  f'access_token={self.token}&v=5.103'
        return url

    def _url_for_create_campaign(self, cabinet_id, client_id, campaign_name, money_limit):
        # Если кампания создается в личном кабинете (не передается айди клиента)
        if client_id is None:
            # JSON массив с параметрами создаваемой кампании
            data = [{
                'type': 'promoted_posts',  # Для продвижения дарк-постов
                'name': campaign_name,  # Название кампании
                'all_limit': money_limit,  # Бюджет кампании
                'status': 1  # 1 - запущена, 0 - остановлена
            }]
            data = json.dumps(data)
            url = f'https://api.vk.com/method/ads.createCampaigns?account_id={cabinet_id}&' \
                  f'data={data}&' \
                  f'access_token={self.token}&v=5.103'
        # Если кампания создается в кабинете агентства (передается айди клиента)
        else:
            # JSON массив с параметрами создаваемой кампании
            data = [{
                'client_id': client_id,
                'type': 'promoted_posts',  # Для продвижения дарк-постов
                'name': campaign_name,  # Название кампании
                'all_limit': money_limit,  # Бюджет кампании
                'status': 1  # 1 - запущена, 0 - остановлена
            }]
            data = json.dumps(data)
            url = f'https://api.vk.com/method/ads.createCampaigns?account_id={cabinet_id}&' \
                  f'data={data}&' \
                  f'access_token={self.token}&v=5.103'
        return url

    def _url_for_create_ads(self, cabinet_id, client_id, data):
        # Если делаем в личном кабинете
        if client_id is None:
            url = f'https://api.vk.com/method/ads.createAds?account_id={cabinet_id}&' \
                  f'data={data}&' \
                  f'access_token={self.token}&v=5.103'
        # Если делаем в кабинете агентства
        else:
            url = f'https://api.vk.com/method/ads.createAds?account_id={cabinet_id}&' \
                  f'client_id={client_id}&' \
                  f'data={data}&' \
                  f'access_token={self.token}&v=5.103'
        return url

    def _data_for_ads_without_music(self, base_id, base_name, campaign_id, post):
        data = [{
            'campaign_id': campaign_id,             # Айди кампании
            'ad_format': 9,                         # Формат объявления, 9 - посты
            'autobidding': 0,                       # Автоуправление ценой
            'cost_type': 1,                         # Способ оплаты, 1 - СРМ
            'cpm': 30.,                             # CPM
            'impressions_limit': 1,                 # Показы на одного человека
            'ad_platform': 'mobile',                # Площадки показа
            'all_limit': 100,                       # Лимит по бюджету
            'category1_id': 51,                     # Тематика объявления, 51 - музыка
            'age_restriction': 1,                   # Возрастной дисклеймер, 1 - 0+
            'status': 1,                            # Статус объявления, 1 - запущено
            'name': base_name,                      # Название объявления
            'link_url': post,                       # Ссылка на дарк-пост
            'country': 0,                           # Страна, 0 - не задана
            'user_devices': 1001,                   # Устройства, 1001 - смартфоны
            'retargeting_groups': base_id           # База ретаргета
        }]
        return data

    def _data_for_ads_with_music(self, base_id, base_name, campaign_id, post):
        data = [{
            'campaign_id': campaign_id,             # Айди кампании
            'ad_format': 9,                         # Формат объявления, 9 - посты
            'autobidding': 0,                       # Автоуправление ценой
            'cost_type': 1,                         # Способ оплаты, 1 - СРМ
            'cpm': 30.,                             # CPM
            'impressions_limit': 1,                 # Показы на одного человека
            'ad_platform': 'mobile',                # Площадки показа
            'all_limit': 100,                       # Лимит по бюджету
            'category1_id': 51,                     # Тематика объявления, 51 - музыка
            'age_restriction': 1,                   # Возрастной дисклеймер, 1 - 0+
            'status': 1,                            # Статус объявления, 1 - запущено
            'name': base_name,                      # Название объявления
            'link_url': post,                       # Ссылка на дарк-пост
            'country': 0,                           # Страна, 0 - не задана
            'interest_categories': 10010,           # Категории интересов, 10010 - музыка
            'user_devices': 1001,                   # Устройства, 1001 - смартфоны
            'retargeting_groups': base_id           # База ретаргета
        }]
        return data

    def get_campaigns(self, cabinet_id, client_id=None):
        """
        Получение кампаний из рекламног кабинета

        :param cabinet_id: int - айди рекламного кабинета (личного или агентского)
        :param client_id: int - айди клиента, если передеается cabinet_id агентства

        :return: dict - {campaign_name: campaign_id}

        """
        url = self._url_for_get_campaigns(cabinet_id, client_id)
        resp = self.session.get(url).json()
        try:
            campaigns = {}
            for campaign in resp['response']:
                campaigns[campaign['name']] = campaign['id']
            return campaigns
        except Exception:
            print('Some error with get_camaigns:')
            print(resp)

    def get_retarget(self, cabinet_id, client_id=None, minimal_size=650000):
        """
        Получение баз ретаргета из рекламного кабинета

        :param cabinet_id:      int - айди рекламного кабинета (личного или агентского)
        :param client_id:       int - айди клиента, если передеается cabinet_id агентства
        :return:                dict = {retarget_name: retarget_id}

        """
        url = self._url_for_get_retarget(cabinet_id, client_id)
        resp = self.session.get(url).json()
        try:
            retarget = {}
            n = 0
            for base in resp['response']:
                if base['audience_count'] >= minimal_size:
                    retarget[base['name']] = base['id']
                    n += 1
                    if n == 100:
                        return retarget
            return retarget
        except Exception:
            print('Some error with get_retarget:')
            print(resp)

    def get_ads(self, cabinet_id, campaign_id, include_deleted=False, client_id=None):
        """
        Получение айди объявлений и их названий из рекламной кампании

        :param cabinet_id:      int - айди рекламного кабинета (личного или агентского)
        :param client_id:       int - айди клиента, если передеается cabinet_id агентства
        :param campaign_id:     int - айди рекламной кампании, из которой будут получены объявления
        :param include_deleted: True - включая архивированные объявления, False - не включая

        :return:                dict - {ad_id, {'name': ad_name, 'cpm': ad_cpm, 'status': 1/0}
                                       cpm - в копейках, status 1 - запущено, status 0 - остановлено

        """
        if include_deleted is False:
            include_deleted = 0
        else:
            include_deleted = 1

        url = self._url_for_get_ads(cabinet_id, client_id, campaign_id, include_deleted)
        resp = self.session.get(url).json()
        try:
            ads = {}
            for i in resp['response']:
                ad_id = int(i['id'])
                ad_name = i['name']
                ad_cpm = i['cpm']
                ad_status = i['status']
                ads[ad_id] = {'name': ad_name, 'cpm': ad_cpm, 'status': ad_status}
            return ads
        except KeyError:
            print(resp)

    def get_cabinets(self):
        """
        Возвращает словарь имен кабинетов с их айди

        :return:        dict - {cabinet_id: [cabinet_name, cabinet_type]}

        """
        url = f'https://api.vk.com/method/ads.getAccounts?access_token={self.token}&v=5.103'
        resp = self.session.get(url).json()
        cabinets = {}
        for cabinet in resp['response']:
            cabinets[cabinet['account_id']] = [cabinet['account_name'], cabinet['account_type']]
        return cabinets

    def get_clients(self, cabinet_id):
        """
        Возвращает словарь имен клиентов кабинета с их айди

        :param cabinet_id:      int - айди рекламного кабинета (личного или агентского)

        :return:                dict - {client_name: client_id}

        """
        url = f'https://api.vk.com/method/ads.getClients?&' \
              f'account_id={cabinet_id}&' \
              f'access_token={self.token}&v=5.103'
        resp = self.session.get(url).json()
        clients = {}
        try:
            for client in resp['response']:
                clients[client['name']] = client['id']
        except KeyError:
            print(resp)
        return clients

    def get_ads_stat(self, cabinet_id, campaign_id, ad_ids, ad_names, client_id=None):
        """
        Получаем необходимую стату с рекламных объявлений

        :param cabinet_id:      int - айди рекламного кабинета (личного или агентского)
        :param client_id:       int - айди клиента, если в cabinet_id передан агентский кабинет
        :param campaign_id:     int - айди кампании
        :param ad_ids:          list of int - список айди объявлений
        :param ad_names:        dict - {ad_id: ad_name}

        :return:                dict - {ad_id: {'name': str, 'spent': float, 'reach': int, 'cpm': cpm}}

        """
        ads_list = ''
        for ad in ad_ids:
            ads_list += f'{ad},'
        ads_list = ads_list[:-1]
        url = f'https://api.vk.com/method/ads.getStatistics?&ids_type=ad&period=overall&date_from=0&date_to=0&' \
              f'account_id={cabinet_id}&' \
              f'ids={ads_list}&' \
              f'access_token={self.token}&v=5.103'
        resp = self.session.get(url).json()

        get_ads = self.get_ads(cabinet_id, campaign_id, client_id=client_id, include_deleted=True)

        ads_stats = {}
        for i in resp['response']:
            if i['stats']:
                cpm = float(get_ads[i['id']]['cpm']) / 100
                ads_stats[i['id']] = {'name': ad_names[i['id']],
                                      'spent': float(i['stats'][0]['spent']),
                                      'reach': i['stats'][0]['impressions'],
                                      'cpm': cpm}
            else:
                cpm = float(get_ads[i['id']]['cpm']) / 100
                ads_stats[i['id']] = {'name': ad_names[i['id']],
                                      'spent': 0,
                                      'reach': 0,
                                      'cpm': cpm}

        return ads_stats

    def get_campaign_stat(self, cabinet_id, campaign_id):
        """
        Возвращает стату по кампании

        :param cabinet_id:      int - айди кабинета (пользовательского или агентского)
        :param campaign_id:     int - айди кампании

        :return:                dict - {campaign_id: {'spent': spent, 'reach': reach}}

        """
        url = f'https://api.vk.com/method/ads.getStatistics?&ids_type=campaign&period=overall&date_from=0&date_to=0&' \
              f'account_id={cabinet_id}&' \
              f'ids={campaign_id}&' \
              f'access_token={self.token}&v=5.103'
        resp = self.session.get(url).json()

        campaign_stat = {}
        try:
            stat = resp['response'][0]['stats'][0]
            temp = {'spent': stat['spent'], 'reach': stat['impressions']}
            campaign_stat[campaign_id] = temp
            return campaign_stat
        except IndexError:
            temp = {'spent': 0, 'reach': 0}
            campaign_stat[campaign_id] = temp
            return campaign_stat
        except KeyError:
            print(resp)

    def create_dark_posts(self, group_id, playlists, text):
        """ Создание дарк-постов в паблике для последующего их использования в таргете

        :param group_id:        str или int - айди паблика артиста
        :param playlists:       list of str - список полноценных ссылок на плейлисты для постов
        :param text:            str - тест для постов со всеми отступами, отметками и эмодзи (как в ВК)

        :return:                dict - {post_url: playlist_url}

        """
        playlists_ids = [x[27:] for x in playlists]

        posts_and_playlists = {}
        for i in range(len(playlists)):
            url = f'https://api.vk.com/method/wall.postAdsStealth?owner_id=-{group_id}&' \
                  f'message={text}&' \
                  f'attachments=audio_playlist{playlists_ids[i]}&' \
                  f'signed=0&access_token={self.token}&v=5.103'
            resp = self.session.get(url).json()
            try:
                post_id = resp['response']['post_id']
                post_link = f'https://vk.com/wall-{group_id}_{post_id}'
                posts_and_playlists[post_link] = playlists[i]
                print(f'post {i + 1} / {(len(playlists))} created')
                time.sleep(0.4)
            except KeyError:
                print(resp)

        return posts_and_playlists

    def create_campaign(self, cabinet_id, campaign_name, money_limit, client_id=None):
        """
        Создание новой кампании в кабинете

        :param cabinet_id:      int - айди рекламного кабинета (личного или агентского)
        :param client_id:       int - айди клиента, если передеается cabinet_id агентства
        :param campaign_name:   str - название рекламной кампании
        :param money_limit:     int - лимит по бюджету для рекламной кампании

        :return:                int - campaign_id

        """


        url = self._url_for_create_campaign(cabinet_id, client_id, campaign_name, money_limit)
        resp = self.session.get(url).json()
        print(resp)
        try:
            campaign_id = resp['response'][0]['id']
            return campaign_id
        except Exception:
            print('Some error with create_campaign')
            print(resp)

    def create_ads(self, cabinet_id, campaign_id, retarget, posts, music=True, client_id=None):
        """
        Создание объявлений в выбранной кампании

        :param cabinet_id:      int - айди рекламного кабинета (личного или агентского)
        :param client_id:       int - айди клиента, если передеается cabinet_id агентства
        :param campaign_id:     int - айди кампании, в которой создаются объявления
        :param retarget:        dict - {retarget_name: retarget_id}
        :param posts:           list of str - список полных ссылок на дарк-посты
        :param music:           True - с сужением по интересу музыка, False - без сужения

        :return:                dict - {ad_id: post_url}

        """
        # Цикл для создания объявлений для каждой базы ретаргета
        ads_and_posts = {}
        for n, (base_name, base_id) in enumerate(retarget.items()):
            # С сужением по интересу "музыка"
            if music is True:
                data = self._data_for_ads_with_music(base_id, base_name, campaign_id, posts[n])
            else:
                # Без сужения по интересу
                data = self._data_for_ads_without_music(base_id, base_name, campaign_id, posts[n])

            data = json.dumps(data)
            url = self._url_for_create_ads(cabinet_id, client_id, data)
            resp = self.session.get(url).json()
            try:
                ad_id = resp['response'][0]['id']
                ads_and_posts[ad_id] = posts[n]
                self.ad_names[ad_id] = base_name
                print(f'ad {n + 1} / {len(retarget)} created')
            except KeyError:
                print('Some error with create_ads')
                print(resp)

            time.sleep(3)

        return ads_and_posts

    def delete_ads(self, cabinet_id, ad_ids):
        """
        Удаление объявлений по их айди

        :param cabinet_id:      int - айди рекламного кабинета (личного или агентского)
        :param ad_ids:          list of int - список айди объявлений, не более 100

        """
        ids = json.dumps(ad_ids)
        url = f'https://api.vk.com/method/ads.deleteAds?account_id={cabinet_id}&' \
              f'ids={ids}&' \
              f'access_token={self.token}&v=5.103'

        resp = self.session.get(url).json()
        try:
            if resp['response']:
                return True
            else:
                print(resp)
        except Exception:
            print('Something wrong with delete_ads')
            print(resp)

    def limit_ads(self, cabinet_id, ad_ids, limit):
        """
        Устанавливает ограничения по бюджету на объявления, 0 - без ограничения

        :param cabinet_id:      int - айди рекламного кабинета (личного или агентского)
        :param ad_ids:          list of int - список айди объявлений
        :param limit:           int - ограничение по бюджету на каждое объявление в рублях

        """
        for i in range(0, len(ad_ids), 5):
            try:
                ids = ad_ids[i: i + 5]
            except IndexError:
                ids = ad_ids[i:]
            data_list = []
            for x in ids:
                data = {'ad_id': x, 'all_limit': limit}
                data_list.append(data)
            data = json.dumps(data_list)
            url = f'https://api.vk.com/method/ads.updateAds?account_id={cabinet_id}&' \
                  f'data={data}&' \
                  f'access_token={self.token}&v=5.103'
            resp = self.session.get(url).json()
            time.sleep(1)

    def stop_ads(self, cabinet_id, ad_ids):
        """
        Останавливает активные объявления

        :param cabinet_id:      int - айди рекламного кабинета (личного или агентского)
        :param ad_ids:          list of int - список айди объявлений

        """
        for i in range(0, len(ad_ids), 5):
            try:
                ids = ad_ids[i: i + 5]
            except IndexError:
                ids = ad_ids[i:]
            data_list = []
            for x in ids:
                data = {'ad_id': x, 'status': 0}
                data_list.append(data)
            data = json.dumps(data_list)
            url = f'https://api.vk.com/method/ads.updateAds?account_id={cabinet_id}&' \
                  f'data={data}&' \
                  f'access_token={self.token}&v=5.103'
            resp = self.session.get(url).json()
            time.sleep(1)

    def start_ads(self, cabinet_id, ad_ids):
        """
        Запускает остановленные объявления

        :param cabinet_id:      int - айди рекламного кабинета (личного или агентского)
        :param ad_ids:          list of int - список айди объявлений

        """
        for i in range(0, len(ad_ids), 5):
            try:
                ids = ad_ids[i: i + 5]
            except IndexError:
                ids = ad_ids[i:]
            data_list = []
            for x in ids:
                data = {'ad_id': x, 'status': 1}
                data_list.append(data)
            data = json.dumps(data_list)
            url = f'https://api.vk.com/method/ads.updateAds?account_id={cabinet_id}&' \
                  f'data={data}&' \
                  f'access_token={self.token}&v=5.103'
            resp = self.session.get(url).json()
            time.sleep(1)

    def update_cpm(self, cabinet_id, cpm_dict):
        """
        Останавливает активные объявления

        :param cabinet_id:      int - айди рекламного кабинета (личного или агентского)
        :param cpm_dict:        dict - {ad_id: cpm}, cpm - float в рублях с копейками после точки

        """
        data_list = []
        for ad_id, cpm in cpm_dict.items():
            if len(data_list) < 4:
                data = {'ad_id': ad_id, 'cpm': cpm}
                data_list.append(data)
            else:
                data = {'ad_id': ad_id, 'cpm': cpm}
                data_list.append(data)
                data = json.dumps(data_list)
                url = f'https://api.vk.com/method/ads.updateAds?account_id={cabinet_id}&' \
                      f'data={data}&' \
                      f'access_token={self.token}&v=5.103'
                resp = self.session.get(url).json()
                data_list = []
                time.sleep(1)
        if data_list:
            data = json.dumps(data_list)
            url = f'https://api.vk.com/method/ads.updateAds?account_id={cabinet_id}&' \
                  f'data={data}&' \
                  f'access_token={self.token}&v=5.103'
            resp = self.session.get(url).json()


class Bagosi:

    def __init__(self, login=None, password=None, headless=True):
        """
        Инициализация объекта. Нужно передавать логин и пароль от ВК аккаунта,
        которому оплачен полный доступ к bago.si

        :param: login           логин от ВК аккаунта
        :param: password        пароль от ВК аккаунта
        :return:                ничего не возвращает
        """
        self.login = login
        self.password = password
        self.browser = self._config_selenium(headless)

    def _config_selenium(self, headless):

        chromeOptions = webdriver.ChromeOptions()
        prefs = {"profile.managed_default_content_settings.images": 2}
        chromeOptions.add_experimental_option("prefs", prefs)
        if headless is True:
            chromeOptions.add_argument('headless')
        chromeOptions.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/'
                                   '537.36 (KHTML, like Gecko) Chrome/64.0.3282.140 Safari/537.36 Edge/18.17763')
        browser = webdriver.Chrome('C:\chromedriver\chromedriver.exe', options=chromeOptions)
        return browser

    def get_savers_count(self, url):

        try:
            # Логинимся в ВК
            self.browser.get('http://www.vk.com')
            login = WebDriverWait(self.browser, 10).until(EC.presence_of_element_located(
                (By.XPATH, '//*[@id="index_email"]')))
            password = WebDriverWait(self.browser, 10).until(EC.presence_of_element_located(
                (By.XPATH, '//*[@id="index_pass"]')))
            enter = WebDriverWait(self.browser, 10).until(EC.presence_of_element_located(
                (By.XPATH, '//*[@id="index_login_button"]')))
            login.send_keys(self.login)
            password.send_keys(self.password)
            enter.click()
            time.sleep(1)
            print('vk.com is logged\n')
        except selenium.common.exceptions.NoSuchElementException:
            pass

        # Логинимся в багосах и переходим на нужную страницу
        self.browser.get('https://bago.si/login?n=vk')
        time.sleep(1)
        self.browser.get('https://bago.si/audio_savers')

        # Вставляем ссылку
        linkform = WebDriverWait(self.browser, 10).until(EC.presence_of_element_located((By.ID, 'id')))
        button = WebDriverWait(self.browser, 10).until(EC.presence_of_element_located((By.XPATH, '//*[@id="submit"]')))
        linkform.send_keys(url)
        button.click()
        time.sleep(3)

        # Получаем список аудио из url
        page = self.browser.page_source
        soup = BeautifulSoup(page, 'lxml')
        audios = soup.find_all(class_='mt-2')

        # Получаем количество сейверов последнего аудио
        count = audios[0].find(class_='sub_text float-right').get_text()
        count = int(count.replace(' ', ''))

        return count

    def __del__(self):
        self.browser.close()

