import os
import json
import logging
import requests
from datetime import datetime


class Logger:
    def __init__(self, name: str, log_file_name: str):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        logger_handler = logging.FileHandler(log_file_name)
        logger_handler.setLevel(logging.INFO)
        logger_formatter = logging.Formatter('%(asctime)s: %(name)s - %(levelname)s - %(message)s')
        logger_handler.setFormatter(logger_formatter)
        self.logger.addHandler(logger_handler)
        self.logger.info('[Logger] msg: class has initialized successfully')


class Client:
    def __init__(self, token_path: str, logger: Logger):
        self.logger = logger.logger
        self.token = self.read_token(path=token_path)
        self.logger.info(f'[{self.__class__.__name__}] msg: class has initialized successfully')

    def read_token(self, path: str) -> str:
        try:
            file_name = os.path.basename(path)
            with open(path, 'r') as file:
                file_name = os.path.basename(path)
                self.logger.info(f'[{self.__class__.__name__}.read_token] msg: token from file "{file_name}" ' +
                                 'has uploaded successfully')
                return file.read().strip()
        except Exception as error:
            self.logger.error(f'[{self.__class__.__name__}.read_token] error_msg for file "{file_name}": {error}')


class YaClient(Client):
    url = 'https://cloud-api.yandex.net/v1/disk/resources/'

    def upload(self, file, file_path: str) -> int | None:
        url = self.get_upload_link(file_path=file_path)
        if url is not None:
            files = {
                'file': file
            }
            try:
                response = requests.post(url=url, files=files)
                if response.ok:
                    self.logger.info(f'[YaClient.upload] response status code: {response.status_code}')
                    return response.status_code
                else:
                    response.raise_for_status()
            except Exception as error:
                self.logger.error(f'[YaClient.upload] error_msg: {error}')

    def get_upload_link(self, file_path: str) -> str | None:
        url = self.url + 'upload'
        params = {
            'path': file_path,
            'overwrite': False
        }
        try:
            response = requests.get(url=url, params=params, headers=self.get_headers())
            if response.ok:
                self.logger.info(f'[YaClient.get_upload_link] response status code: {response.status_code}')
                return response.json()['href']
            else:
                response.raise_for_status()
        except Exception as error:
            self.logger.error(f'[YaClient.get_upload_link] error_msg: {error}')

    def create_folder(self, folder_name: str) -> int | None:
        params = {
            'path': f'{folder_name}'
        }
        try:
            response = requests.put(url=self.url, params=params, headers=self.get_headers())
            if response.ok:
                self.logger.info(f'[YaClient.create_folder] response status code: {response.status_code}')
                return response.status_code
            else:
                response.raise_for_status()
        except Exception as error:
            self.logger.error(f'[YaClient.create_folder] error_msg: {error}')

    def get_headers(self):
        return {
            'Content-Type': 'application/json',
            'Authorization': f'OAuth {self.token}'
        }


class VkClient(Client):
    url = 'https://api.vk.com/method/'

    def get_profile_photos(self, owner_id: int, count=5) -> dict | None:
        url = self.url + 'photos.get'
        params = {
            'access_token': self.token,
            'v': '5.131',
            'owner_id': owner_id,
            'album_id': 'profile',
            'extended': 1,
            'photo_sizes': 1,
            'count': count
        }
        try:
            response = requests.get(url=url, params=params)
            if response.ok:
                if 'error' in response.json():
                    error_msg = response.json()['error']['error_msg']
                    raise Exception(f'[VkClient.get_profile_photos] error_msg: {error_msg}')
                else:
                    self.logger.info(f'[VkClient.get_profile_photos] response status code: {response.status_code}')
                    return response.json()['response']['items']
            else:
                response.raise_for_status()
        except Exception as error:
            self.logger.error(f'[VkClient.get_profile_photos] error_msg: {error}')


if __name__ == '__main__':
    vk_token_path = 'vk_token.txt'
    ya_token_path = 'ya_token.txt'
    upload_folder = 'vk_profile_photos'
    count_photos = 10  # default count in fc is 5
    account_id = 552934290  # https://vk.com/begemot_korovin

    my_logger = Logger(name='backup_profile_photos', log_file_name='backup_profile_photos.log')
    vk_client = VkClient(token_path=vk_token_path, logger=my_logger)
    ya_client = YaClient(token_path=ya_token_path, logger=my_logger)

    if not os.path.exists('uploaded_files.json'):
        with open('uploaded_files.json', 'w') as file:
            json.dump([], file)
            my_logger.logger.info(f'[{__name__}] msg: file "uploaded_files.json" has created')

    profile_photos = vk_client.get_profile_photos(owner_id=account_id, count=count_photos)
    if profile_photos is None:
        my_logger.logger.error(f'[{__name__}] error_msg: failed to get profile photos for account id {account_id}')

    ya_client.create_folder(folder_name=upload_folder)

    uploaded_files = set()
    for profile_photo in profile_photos:
        photo_likes = profile_photo['likes']['count']
        photo_url = profile_photo['sizes'][-1]['url']
        photo_size = profile_photo['sizes'][-1]['type']
        if str(photo_likes) not in uploaded_files:
            photo_name = str(photo_likes)
        else:
            date = datetime.now().date()
            photo_name = f'{photo_likes}_{date}'

        photo = None
        try:
            photo = requests.get(url=photo_url).content
        except Exception as error:
            my_logger.logger.error(f'[{__name__}] error_msg: file "{photo_name}.jpg" has not downloaded')

        my_logger.logger.info(f'[{__name__}] msg: uploading file "{photo_name}.jpg"')
        status_code = ya_client.upload(file=photo, file_path=f'{upload_folder}/{photo_name}.jpg')
        if status_code == 201:
            my_logger.logger.info(f'[{__name__}] msg: file "{photo_name}.jpg" has uploaded successfully')
        else:
            my_logger.logger.error(f'[{__name__}] error_msg: file "{photo_name}.jpg" has not uploaded')
            continue

        with open('uploaded_files.json', 'r') as file:
            files_info = json.load(file)

        file_info = {'file_name': f'{photo_name}.jpg', 'size': photo_size}
        files_info += [file_info]

        with open('uploaded_files.json', 'w') as file:
            json.dump(files_info, file, indent=4)
            my_logger.logger.info(f'[{__name__}] msg: information about file "{photo_name}.jpg" has added to ' +
                                  '"uploaded_files.json"')

        uploaded_files.add(str(photo_likes))