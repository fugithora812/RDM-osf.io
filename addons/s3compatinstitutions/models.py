# -*- coding: utf-8 -*-
import six
import logging
import re

from django.db import models

import boto3

from addons.base import exceptions
from addons.base import institutions_utils as inst_utils
from addons.base.institutions_utils import (
    InstitutionsNodeSettings,
    InstitutionsStorageAddon
)
from addons.s3compatinstitutions import settings, apps
from osf.models.external import BasicAuthProviderMixin
from osf.models.files import File, Folder, BaseFileNode
#from osf.utils.permissions import ADMIN, READ, WRITE

logger = logging.getLogger(__name__)

FULL_NAME = apps.FULL_NAME
SHORT_NAME = apps.SHORT_NAME

ENABLE_DEBUG = False

def DEBUG(msg):
    if ENABLE_DEBUG:
        logger.error(u'DEBUG_{}: {}'.format(SHORT_NAME, msg))
    else:
        logger.debug(msg)

if not ENABLE_DEBUG:
    logging.getLogger('botocore.vendored.requests.packages.urllib3.connectionpool').setLevel(logging.CRITICAL)

class S3CompatInstitutionsFileNode(BaseFileNode):
    _provider = SHORT_NAME


class S3CompatInstitutionsFolder(S3CompatInstitutionsFileNode, Folder):
    pass


class S3CompatInstitutionsFile(S3CompatInstitutionsFileNode, File):
    pass


class S3CompatInstitutionsProvider(BasicAuthProviderMixin):
    name = FULL_NAME
    short_name = SHORT_NAME


class S3Path(object):
    def __init__(self, bucket, key):
        self.bucket = bucket
        self.key = key

    def __unicode__(self):
        return u'{}:{}'.format(self.bucket, self.key)


class NodeSettings(InstitutionsNodeSettings, InstitutionsStorageAddon):
    FULL_NAME = FULL_NAME
    SHORT_NAME = SHORT_NAME

    folder_id = models.TextField(blank=True, null=True)

    @classmethod
    def addon_settings(cls):
        return settings

    @classmethod
    def get_provider(cls, external_account):
        return S3CompatInstitutionsProvider(external_account)

    @classmethod
    def get_debug_provider(cls):
        if not (settings.DEBUG_URL
                and settings.DEBUG_USER
                and settings.DEBUG_PASSWORD):
            return None

        class DebugProvider(object):
            host = settings.DEBUG_URL
            username = settings.DEBUG_USER
            password = settings.DEBUG_PASSWORD
        return DebugProvider()

    @classmethod
    def get_client(cls, provider):
        port = 443
        scheme = 'https'
        m = re.match(r'^(.+)\:([0-9]+)$', provider.host)
        if m is not None:
            # host = m.group(1)
            port = int(m.group(2))
            if port != 443:
                scheme = 'http'
        client = boto3.client('s3',
            aws_access_key_id=provider.username,
            aws_secret_access_key=provider.password,
            endpoint_url='{}://{}'.format(scheme, provider.host))
        return client

    @classmethod
    def _list_count(cls, client, path):
        # may raise
        res = client.list_objects(Bucket=path.backet, Prefix=path.key)
        contents = res.get('Contents')
        return len(contents)

    @classmethod
    def can_access(cls, client):
        # access check
        client.list_buckets()  # may raise

    @classmethod
    def create_folder(cls, client, path):
        logger.info(u'create folder: {}'.format(path))
        folder = path.key + '/'
        client.put_object(Bucket=path.bucket, Key=folder)  # may raise
        return path

    @classmethod
    def remove_folder(cls, client, path):
        count = cls._list_count(client, path)
        if count != 0:
            raise exceptions.AddonError(u'cannot delete folder (not empty): {}'.format(path))
        logger.info(u'delete folder: {}'.format(path))
        client.delete_object(Bucket=path.bucket, Key=path.key)  # may raise
        return path

    @classmethod
    def rename_folder(cls, client, path_src, path_target):
        logger.info(u'rename operation is not supported in s3compatinstitutions')

    @classmethod
    def root_folder_format(cls):
        return settings.ROOT_FOLDER_FORMAT

    # bucket=BASE_FOLDER, key=ROOT_FOLDER/key_to_objects
    # override
    @classmethod
    def root_folder(cls, addon_option, node):
        base_folder = cls.base_folder(addon_option)
        title = cls.filename_filter(node.title)
        fmt = six.u(cls.root_folder_format())
        return S3Path(base_folder, fmt.format(title=title, guid=node._id))

    # override
    def set_folder(self, folder, auth=None):
        self.folder_id = folder.key

    # override
    def sync_title(self):
        # S3 and S3 compat cannot rename buckets and folders.
        pass

    def sync_contributors(self):
        # TODO bucket policy API?
        pass

    @property
    def bucket(self):
        return self.base_folder(self.addon_option)

    @property
    def root_prefix(self):
        return self.folder_id

    def serialize_waterbutler_credentials_impl(self):
        return {
            'host': self.provider.host,
            'access_key': self.provider.username,
            'secret_key': self.provider.password,
        }

    def serialize_waterbutler_settings(self):
        return {
            'bucket': self.bucket,
            'prefix': self.root_prefix,
            'encrypt_uploads': settings.ENCRYPT_UPLOADS
        }

    def copy_folders(self, dest_addon):
        c = self.client
        destc = dest_addon.client
        res = c.list_objects(Bucket=self.bucket, Prefix=self.root_prefix,
                             MaxKeys=1000)  # may raise
        contents = res.get('Contents')
        # logger.debug(u'Contents: {}'.format(contents))
        if not contents:
            return
        for item in contents:
            key = item.get('Key')
            if not key:
                continue
            parts = key.split('/')
            if len(parts) <= 1:
                continue
            if parts[0] != self.root_prefix:
                continue
            # A/B/C/ -> B/C/
            # A/B/C/file -> B/C/
            key = '/'.join(parts[1:-1]) + '/'
            if key == '/':
                continue
            key = dest_addon.root_prefix + '/' + key
            logger.debug(u'copy_folders: put_object({})'.format(key))
            destc.put_object(Bucket=dest_addon.bucket, Key=key)  # may raise


inst_utils.register(NodeSettings)
