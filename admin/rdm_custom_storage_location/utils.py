# -*- coding: utf-8 -*-

import traceback

from boxsdk import Client as BoxClient, OAuth2
from boxsdk.exception import BoxAPIException
from furl import furl
import httplib
import requests
from swiftclient import exceptions as swift_exceptions
import os
import owncloud
from django.core.exceptions import ValidationError

from admin.rdm_addons.utils import get_rdm_addon_option
from addons.googledrive.client import GoogleDriveClient
from addons.osfstorage.models import Region
from addons.box import settings as box_settings
from addons.owncloud import settings as owncloud_settings
from addons.nextcloud import settings as nextcloud_settings
from addons.s3 import utils as s3_utils
from addons.s3compat import utils as s3compat_utils
from addons.swift import settings as swift_settings, utils as swift_utils
from addons.swift.provider import SwiftProvider
from addons.dropboxbusiness import utils as dropboxbusiness_utils
from addons.nextcloudinstitutions.models import NextcloudInstitutionsProvider
from addons.nextcloudinstitutions import settings as nextcloudinstitutions_settings
from addons.nextcloudinstitutions import KEYNAME_NOTIFICATION_SECRET
from addons.s3compatinstitutions.models import S3CompatInstitutionsProvider
from addons.s3compatinstitutions import settings as s3compatinstitutions_settings
from addons.base.institutions_utils import (KEYNAME_BASE_FOLDER,
                                            KEYNAME_USERMAP,
                                            KEYNAME_USERMAP_TMP,
                                            sync_all)
from framework.exceptions import HTTPError
from website import settings as osf_settings
from osf.models.external import ExternalAccountTemporary, ExternalAccount
from osf.utils import external_util
import datetime


providers = None

enabled_providers_forinstitutions_list = [
    'dropboxbusiness',
    'nextcloudinstitutions',
    's3compatinstitutions',
]

enabled_providers_list = [
    's3', 'box', 'googledrive', 'osfstorage',
    'nextcloud', 'swift', 'owncloud', 's3compat',
]
enabled_providers_list.extend(enabled_providers_forinstitutions_list)

no_storage_name_providers = ['osfstorage']

def have_storage_name(provider_name):
    return provider_name not in no_storage_name_providers

def get_providers():
    provider_list = []
    for provider in osf_settings.ADDONS_AVAILABLE:
        if 'storage' in provider.categories and provider.short_name in enabled_providers_list:
            provider.icon_url_admin = \
                '/custom_storage_location/icon/{}/comicon.png'.format(provider.short_name)
            provider.modal_path = get_modal_path(provider.short_name)
            provider_list.append(provider)
    provider_list.sort(key=lambda x: x.full_name.lower())
    return provider_list

def get_addon_by_name(addon_short_name):
    """get Addon object from Short Name."""
    for addon in osf_settings.ADDONS_AVAILABLE:
        if addon.short_name == addon_short_name:
            return addon

def get_modal_path(short_name):
    base_path = os.path.join('rdm_custom_storage_location', 'providers')
    return os.path.join(base_path, '{}_modal.html'.format(short_name))

def get_oauth_info_notification(institution_id, provider_short_name):
    temp_external_account = ExternalAccountTemporary.objects.filter(
        _id=institution_id, provider=provider_short_name
    ).first()
    if temp_external_account and \
            temp_external_account.modified >= datetime.datetime.now(
                temp_external_account.modified.tzinfo
            ) - datetime.timedelta(seconds=60 * 30):
        return {
            'display_name': temp_external_account.display_name,
            'oauth_key': temp_external_account.oauth_key,
            'provider': temp_external_account.provider,
            'provider_id': temp_external_account.provider_id,
            'provider_name': temp_external_account.provider_name,
        }

def set_allowed(institution, provider_name, is_allowed):
    addon_option = get_rdm_addon_option(institution.id, provider_name)
    addon_option.is_allowed = is_allowed
    addon_option.save()
    # NOTE: ExternalAccounts is not cleared even if other storage is selected.
    # if not is_allowed:
    #     addon_option.external_accounts.clear()

def change_allowed_for_institutions(institution, provider_name):
    if provider_name in enabled_providers_forinstitutions_list:
        set_allowed(institution, provider_name, True)

    # disable other storages for Institutions
    for p in get_providers():
        if p.short_name == provider_name:
            continue  # skip this provider
        if p.for_institutions:
            set_allowed(institution, p.short_name, False)

def set_default_storage(institution_id):
    default_region = Region.objects.first()
    try:
        region = Region.objects.get(_id=institution_id)
        # copy
        region.name = default_region.name
        region.waterbutler_credentials = default_region.waterbutler_credentials
        region.waterbutler_settings = default_region.waterbutler_settings
        region.waterbutler_url = default_region.waterbutler_url
        region.mfr_url = default_region.mfr_url
        region.save()
    except Region.DoesNotExist:
        region = Region.objects.create(
            _id=institution_id,
            name=default_region.name,
            waterbutler_credentials=default_region.waterbutler_credentials,
            waterbutler_settings=default_region.waterbutler_settings,
            waterbutler_url=default_region.waterbutler_url,
            mfr_url=default_region.mfr_url,
        )
    return region

def update_storage(institution_id, storage_name, wb_credentials, wb_settings):
    try:
        region = Region.objects.get(_id=institution_id)
    except Region.DoesNotExist:
        default_region = Region.objects.first()
        region = Region.objects.create(
            _id=institution_id,
            name=storage_name,
            waterbutler_credentials=wb_credentials,
            waterbutler_url=default_region.waterbutler_url,
            mfr_url=default_region.mfr_url,
            waterbutler_settings=wb_settings,
        )
    else:
        region.name = storage_name
        region.waterbutler_credentials = wb_credentials
        region.waterbutler_settings = wb_settings
        region.save()
    return region

def transfer_to_external_account(user, institution_id, provider_short_name):
    temp_external_account = ExternalAccountTemporary.objects.filter(_id=institution_id, provider=provider_short_name).first()
    account, _ = ExternalAccount.objects.get_or_create(
        provider=temp_external_account.provider,
        provider_id=temp_external_account.provider_id,
    )

    # ensure that provider_name is correct
    account.provider_name = temp_external_account.provider_name
    # required
    account.oauth_key = temp_external_account.oauth_key
    # only for OAuth1
    account.oauth_secret = temp_external_account.oauth_secret
    # only for OAuth2
    account.expires_at = temp_external_account.expires_at
    account.refresh_token = temp_external_account.refresh_token
    account.date_last_refreshed = temp_external_account.date_last_refreshed
    # additional information
    account.display_name = temp_external_account.display_name
    account.profile_url = temp_external_account.profile_url
    account.save()

    temp_external_account.delete()

    # add it to the user's list of ``ExternalAccounts``
    if not user.external_accounts.filter(id=account.id).exists():
        user.external_accounts.add(account)
        user.save()
    return account

def oauth_validation(provider, institution_id, folder_id):
    """Checks if the folder_id is not empty, and that a temporary external account exists
    in the database.
    """
    if not folder_id:
        return ({
            'message': 'Folder ID is missing.'
        }, httplib.BAD_REQUEST)

    if not ExternalAccountTemporary.objects.filter(_id=institution_id, provider=provider).exists():
        return ({
            'message': 'Oauth data was not found. Please reload the page and try again.'
        }, httplib.BAD_REQUEST)

    return True

def test_s3_connection(access_key, secret_key, bucket):
    """Verifies new external account credentials and adds to user's list"""
    if not (access_key and secret_key and bucket):
        return ({
            'message': 'All the fields above are required.'
        }, httplib.BAD_REQUEST)
    user_info = s3_utils.get_user_info(access_key, secret_key)
    if not user_info:
        return ({
            'message': 'Unable to access account.\n'
            'Check to make sure that the above credentials are valid,'
            'and that they have permission to list buckets.'
        }, httplib.BAD_REQUEST)

    if not s3_utils.can_list(access_key, secret_key):
        return ({
            'message': 'Unable to list buckets.\n'
            'Listing buckets is required permission that can be changed via IAM'
        }, httplib.BAD_REQUEST)

    if not s3_utils.bucket_exists(access_key, secret_key, bucket):
        return ({
            'message': 'Invalid bucket.'
        }, httplib.BAD_REQUEST)

    s3_response = {
        'id': user_info.id,
        'display_name': user_info.display_name,
        'Owner': user_info.Owner,
    }

    return ({
        'message': 'Credentials are valid',
        'data': s3_response
    }, httplib.OK)

def test_s3compat_connection(host_url, access_key, secret_key, bucket):
    host = host_url.rstrip('/').replace('https://', '').replace('http://', '')
    if not (host and access_key and secret_key and bucket):
        return ({
            'message': 'All the fields above are required.'
        }, httplib.BAD_REQUEST)

    try:
        user_info = s3compat_utils.get_user_info(host, access_key, secret_key)
        e_message = ''
    except Exception as e:
        user_info = None
        e_message = traceback.format_exception_only(type(e), e)[0].rstrip('\n')
    if not user_info:
        return ({
            'message': 'Unable to access account.\n'
            'Check to make sure that the above credentials are valid, '
            'and that they have permission to list buckets.',
            'e_message': e_message
        }, httplib.BAD_REQUEST)

    try:
        res = s3compat_utils.can_list(host, access_key, secret_key)
        e_message = ''
    except Exception as e:
        res = False
        e_message = traceback.format_exception_only(type(e), e)[0].rstrip('\n')
    if not res:
        return ({
            'message': 'Unable to list buckets.\n'
            'Listing buckets is required permission that can be changed via IAM',
            'e_message': e_message
        }, httplib.BAD_REQUEST)

    try:
        res = s3compat_utils.bucket_exists(host, access_key, secret_key, bucket)
        e_message = ''
    except Exception as e:
        res = False
        e_message = traceback.format_exception_only(type(e), e)[0].rstrip('\n')
    if not res:
        return ({
            'message': 'Invalid bucket.',
            'e_message': e_message
        }, httplib.BAD_REQUEST)

    return ({
        'message': 'Credentials are valid',
        'data': {
            'id': user_info.id,
            'display_name': user_info.display_name,
        }
    }, httplib.OK)

def test_box_connection(institution_id, folder_id):
    validation_result = oauth_validation('box', institution_id, folder_id)
    if isinstance(validation_result, tuple):
        return validation_result

    access_token = ExternalAccountTemporary.objects.get(
        _id=institution_id, provider='box'
    ).oauth_key
    oauth = OAuth2(
        client_id=box_settings.BOX_KEY,
        client_secret=box_settings.BOX_SECRET,
        access_token=access_token
    )
    client = BoxClient(oauth)

    try:
        client.folder(folder_id).get()
    except BoxAPIException:
        return ({
            'message': 'Invalid folder ID.'
        }, httplib.BAD_REQUEST)

    return ({
        'message': 'Credentials are valid'
    }, httplib.OK)

def test_googledrive_connection(institution_id, folder_id):
    validation_result = oauth_validation('googledrive', institution_id, folder_id)
    if isinstance(validation_result, tuple):
        return validation_result

    access_token = ExternalAccountTemporary.objects.get(
        _id=institution_id, provider='googledrive'
    ).oauth_key
    client = GoogleDriveClient(access_token)

    try:
        client.folders(folder_id)
    except HTTPError:
        return ({
            'message': 'Invalid folder ID.'
        }, httplib.BAD_REQUEST)

    return ({
        'message': 'Credentials are valid'
    }, httplib.OK)

def test_owncloud_connection(host_url, username, password, folder, provider):
    """ This method is valid for both ownCloud and Nextcloud """
    provider_name = None
    provider_setting = None
    if provider == 'owncloud':
        provider_name = 'ownCloud'
        provider_setting = owncloud_settings
    elif provider == 'nextcloud':
        provider_name = 'Nextcloud'
        provider_setting = nextcloud_settings
    elif provider == 'nextcloudinstitutions':
        provider_name = NextcloudInstitutionsProvider.name
        provider_setting = nextcloudinstitutions_settings

    host = use_https(host_url)

    try:
        client = owncloud.Client(host.url, verify_certs=provider_setting.USE_SSL)
        client.login(username, password)
    except requests.exceptions.ConnectionError:
        return ({
            'message': 'Invalid {} server.'.format(provider_name) + host.url
        }, httplib.BAD_REQUEST)
    except owncloud.owncloud.HTTPResponseError:
        return ({
            'message': '{} Login failed.'.format(provider_name)
        }, httplib.UNAUTHORIZED)

    try:
        client.list(folder)
    except owncloud.owncloud.HTTPResponseError:
        client.logout()
        return ({
            'message': 'Invalid folder.'
        }, httplib.BAD_REQUEST)

    client.logout()

    return ({
        'message': 'Credentials are valid'
    }, httplib.OK)

def test_swift_connection(auth_version, auth_url, access_key, secret_key, tenant_name,
                          user_domain_name, project_domain_name, container):
    """Verifies new external account credentials and adds to user's list"""
    if not (auth_version and auth_url and access_key and secret_key and tenant_name and container):
        return ({
            'message': 'All the fields above are required.'
        }, httplib.BAD_REQUEST)
    if auth_version == '3' and not user_domain_name:
        return ({
            'message': 'The field `user_domain_name` is required when you choose identity V3.'
        }, httplib.BAD_REQUEST)
    if auth_version == '3' and not project_domain_name:
        return ({
            'message': 'The field `project_domain_name` is required when you choose identity V3.'
        }, httplib.BAD_REQUEST)

    user_info = swift_utils.get_user_info(auth_version, auth_url, access_key,
                                    user_domain_name, secret_key, tenant_name,
                                    project_domain_name)

    if not user_info:
        return ({
            'message': 'Unable to access account.\n'
            'Check to make sure that the above credentials are valid, '
            'and that they have permission to list containers.'
        }, httplib.BAD_REQUEST)

    try:
        _, containers = swift_utils.connect_swift(
            auth_version, auth_url, access_key, user_domain_name, secret_key, tenant_name,
            timeout=swift_settings.TEST_TIMEOUT
        ).get_account()
    except swift_exceptions.ClientException:
        return ({
            'message': 'Unable to list containers.\n'
            'Listing containers is required permission.'
        }, httplib.BAD_REQUEST)

    if container not in map(lambda c: c['name'], containers):
        return ({
            'message': 'Invalid container name.'
        }, httplib.BAD_REQUEST)

    provider = SwiftProvider(account=None, auth_version=auth_version,
                             auth_url=auth_url, tenant_name=tenant_name,
                             project_domain_name=project_domain_name,
                             username=access_key,
                             user_domain_name=user_domain_name,
                             password=secret_key)
    swift_response = {
        'id': provider.account.id,
        'display_name': provider.account.display_name,
    }
    return ({
        'message': 'Credentials are valid',
        'data': swift_response
    }, httplib.OK)

def test_dropboxbusiness_connection(institution):
    fm = dropboxbusiness_utils.get_two_addon_options(institution.id,
                                                     allowed_check=False)
    if fm is None:
        return ({
            'message': u'Invalid Institution ID.: {}'.format(institution.id)
        }, httplib.BAD_REQUEST)

    f_option, m_option = fm
    f_token = dropboxbusiness_utils.addon_option_to_token(f_option)
    m_token = dropboxbusiness_utils.addon_option_to_token(m_option)
    if f_token is None or m_token is None:
        return ({
            'message': 'No tokens.'
        }, httplib.BAD_REQUEST)
    try:
        # use two tokens and connect
        dropboxbusiness_utils.TeamInfo(f_token, m_token, connecttest=True)
        return ({
            'message': 'Credentials are valid',
        }, httplib.OK)
    except Exception:
        return ({
            'message': 'Invalid tokens.'
        }, httplib.BAD_REQUEST)

def save_s3_credentials(institution_id, storage_name, access_key, secret_key, bucket):
    test_connection_result = test_s3_connection(access_key, secret_key, bucket)
    if test_connection_result[1] != httplib.OK:
        return test_connection_result

    wb_credentials = {
        'storage': {
            'access_key': access_key,
            'secret_key': secret_key,
        },
    }
    wb_settings = {
        'storage': {
            'folder': {
                'encrypt_uploads': True,
            },
            'bucket': bucket,
            'provider': 's3',
        },
    }

    region = update_storage(institution_id, storage_name, wb_credentials, wb_settings)
    external_util.remove_region_external_account(region)

    return ({
        'message': 'Saved credentials successfully!!'
    }, httplib.OK)

def save_s3compat_credentials(institution_id, storage_name, host_url, access_key, secret_key,
                              bucket):

    test_connection_result = test_s3compat_connection(host_url, access_key, secret_key, bucket)
    if test_connection_result[1] != httplib.OK:
        return test_connection_result

    host = host_url.rstrip('/').replace('https://', '').replace('http://', '')

    wb_credentials = {
        'storage': {
            'access_key': access_key,
            'secret_key': secret_key,
            'host': host,
        }
    }
    wb_settings = {
        'storage': {
            'folder': {
                'encrypt_uploads': True,
            },
            'bucket': bucket,
            'provider': 's3compat',
        }
    }

    region = update_storage(institution_id, storage_name, wb_credentials, wb_settings)
    external_util.remove_region_external_account(region)

    return ({
        'message': 'Saved credentials successfully!!'
    }, httplib.OK)

def save_box_credentials(user, storage_name, folder_id):
    institution_id = user.affiliated_institutions.first()._id

    test_connection_result = test_box_connection(institution_id, folder_id)
    if test_connection_result[1] != httplib.OK:
        return test_connection_result

    account = transfer_to_external_account(user, institution_id, 'box')
    wb_credentials = {
        'storage': {
            'token': account.oauth_key,
        },
    }
    wb_settings = {
        'storage': {
            'bucket': '',
            'folder': folder_id,
            'provider': 'box',
        }
    }
    region = update_storage(institution_id, storage_name, wb_credentials, wb_settings)
    external_util.set_region_external_account(region, account)

    return ({
        'message': 'OAuth was set successfully'
    }, httplib.OK)

def save_googledrive_credentials(user, storage_name, folder_id):
    institution_id = user.affiliated_institutions.first()._id

    test_connection_result = test_googledrive_connection(institution_id, folder_id)
    if test_connection_result[1] != httplib.OK:
        return test_connection_result

    account = transfer_to_external_account(user, institution_id, 'googledrive')
    wb_credentials = {
        'storage': {
            'token': account.oauth_key,
        },
    }
    wb_settings = {
        'storage': {
            'bucket': '',
            'folder': {
                'id': folder_id
            },
            'provider': 'googledrive',
        }
    }
    region = update_storage(institution_id, storage_name, wb_credentials, wb_settings)
    external_util.set_region_external_account(region, account)

    return ({
        'message': 'OAuth was set successfully'
    }, httplib.OK)

def save_nextcloud_credentials(institution_id, storage_name, host_url, username, password,
                              folder, provider):
    test_connection_result = test_owncloud_connection(host_url, username, password, folder,
                                                      provider)
    if test_connection_result[1] != httplib.OK:
        return test_connection_result

    # Ensure that NextCloud uses https
    host = furl()
    host.host = host_url.rstrip('/').replace('https://', '').replace('http://', '')
    host.scheme = 'https'

    wb_credentials = {
        'storage': {
            'host': host.url,
            'username': username,
            'password': password,
        },
    }
    wb_settings = {
        'storage': {
            'bucket': '',
            'folder': '/{}/'.format(folder.strip('/')),
            'verify_ssl': False,
            'provider': provider
        },
    }

    region = update_storage(institution_id, storage_name, wb_credentials, wb_settings)
    external_util.remove_region_external_account(region)

    return ({
        'message': 'Saved credentials successfully!!'
    }, httplib.OK)

def save_osfstorage_credentials(institution_id):
    region = set_default_storage(institution_id)
    external_util.remove_region_external_account(region)
    return ({
        'message': 'NII storage was set successfully'
    }, httplib.OK)

def save_swift_credentials(institution_id, storage_name, auth_version, access_key, secret_key,
                           tenant_name, user_domain_name, project_domain_name, auth_url,
                           container):

    test_connection_result = test_swift_connection(auth_version, auth_url, access_key, secret_key,
        tenant_name, user_domain_name, project_domain_name, container)
    if test_connection_result[1] != httplib.OK:
        return test_connection_result

    wb_credentials = {
        'storage': {
            'auth_version': auth_version,
            'username': access_key,
            'password': secret_key,
            'tenant_name': tenant_name,
            'user_domain_name': user_domain_name,
            'project_domain_name': project_domain_name,
            'auth_url': auth_url,
        },
    }
    wb_settings = {
        'storage': {
            'bucket': '',
            'folder': '',
            'container': container,
            'provider': 'swift',
        }

    }

    region = update_storage(institution_id, storage_name, wb_credentials, wb_settings)
    external_util.remove_region_external_account(region)

    return ({
        'message': 'Saved credentials successfully!!'
    }, httplib.OK)

def save_owncloud_credentials(institution_id, storage_name, host_url, username, password,
                              folder, provider):
    test_connection_result = test_owncloud_connection(host_url, username, password, folder,
                                                      provider)
    if test_connection_result[1] != httplib.OK:
        return test_connection_result

    # Ensure that ownCloud uses https
    host = furl()
    host.host = host_url.rstrip('/').replace('https://', '').replace('http://', '')
    host.scheme = 'https'

    wb_credentials = {
        'storage': {
            'host': host.url,
            'username': username,
            'password': password,
        },
    }
    wb_settings = {
        'storage': {
            'bucket': '',
            'folder': '/{}/'.format(folder.strip('/')),
            'verify_ssl': True,
            'provider': provider
        },
    }

    region = update_storage(institution_id, storage_name, wb_credentials, wb_settings)
    external_util.remove_region_external_account(region)

    return ({
        'message': 'Saved credentials successfully!!'
    }, httplib.OK)

def wd_info_for_institutions(provider_name):
    wb_credentials = {
        'storage': {
        },
    }
    wb_settings = {
        'disabled': True,  # used in rubeus.py
        'storage': {
            'provider': provider_name
        },
    }
    return (wb_credentials, wb_settings)

def use_https(url):
    # Ensure that NextCloud uses https
    host = furl()
    host.host = url.rstrip('/').replace('https://', '').replace('http://', '')
    host.scheme = 'https'
    return host

def save_dropboxbusiness_credentials(institution, storage_name, provider_name):
    test_connection_result = test_dropboxbusiness_connection(institution)
    if test_connection_result[1] != httplib.OK:
        return test_connection_result

    wb_credentials, wb_settings = wd_info_for_institutions(provider_name)
    region = update_storage(institution._id,  # not institution.id
                            storage_name,
                            wb_credentials, wb_settings)
    external_util.remove_region_external_account(region)
    ### sync_all() is not supported by Dropbox Business Addon
    # sync_all(institution._id, target_addons=[provider_name])

    return ({
        'message': 'Dropbox Business was set successfully!!'
    }, httplib.OK)

def save_basic_storage_institutions_credentials_common(
        institution, storage_name, folder, provider_name, provider, separator=':', extended_data=None):
    try:
        provider.account.save()
    except ValidationError:
        host = provider.host
        username = provider.username
        password = provider.password
        # ... or get the old one
        provider.account = ExternalAccount.objects.get(
            provider=provider_name,
            provider_id='{}{}{}'.format(host, separator, username).lower()
        )
        if provider.account.oauth_key != password:
            provider.account.oauth_key = password
            provider.account.save()

    # Storage Addons for Institutions must have only one ExternalAccont.
    rdm_addon_option = get_rdm_addon_option(institution.id, provider_name)
    if rdm_addon_option.external_accounts.count() > 0:
        rdm_addon_option.external_accounts.clear()
    rdm_addon_option.external_accounts.add(provider.account)

    rdm_addon_option.extended[KEYNAME_BASE_FOLDER] = folder
    if type(extended_data) is dict:
        rdm_addon_option.extended.update(extended_data)
    rdm_addon_option.save()

    wb_credentials, wb_settings = wd_info_for_institutions(provider_name)
    region = update_storage(institution._id,  # not institution.id
                            storage_name,
                            wb_credentials, wb_settings)
    external_util.remove_region_external_account(region)

    save_usermap_from_tmp(provider_name, institution)
    sync_all(institution._id, target_addons=[provider_name])

    return ({
        'message': 'Saved credentials successfully!!'
    }, httplib.OK)

def save_nextcloudinstitutions_credentials(
        institution, storage_name, host_url, username, password, folder, notification_secret, provider_name):
    test_connection_result = test_owncloud_connection(
        host_url, username, password, folder, provider_name)
    if test_connection_result[1] != httplib.OK:
        return test_connection_result

    host = use_https(host_url)
    provider = NextcloudInstitutionsProvider(
        account=None, host=host.url,
        username=username, password=password)
    extended_data = {}
    extended_data[KEYNAME_NOTIFICATION_SECRET] = notification_secret
    return save_basic_storage_institutions_credentials_common(
        institution, storage_name, folder, provider_name, provider, extended_data=extended_data)

def save_s3compatinstitutions_credentials(institution, storage_name, host_url, access_key, secret_key, bucket, provider_name):
    host = host_url.rstrip('/').replace('https://', '').replace('http://', '')
    test_connection_result = test_s3compat_connection(
        host, access_key, secret_key, bucket)
    if test_connection_result[1] != httplib.OK:
        return test_connection_result

    separator = '\t'
    provider = S3CompatInstitutionsProvider(
        account=None, host=host,
        username=access_key, password=secret_key, separator=separator)

    return save_basic_storage_institutions_credentials_common(
        institution, storage_name, bucket, provider_name, provider, separator)

def get_credentials_common(institution, provider_name):
    clear_usermap_tmp(provider_name, institution)
    rdm_addon_option = get_rdm_addon_option(institution.id, provider_name,
                                            create=False)
    if not rdm_addon_option:
        return None
    exacc = rdm_addon_option.external_accounts.first()
    if not exacc:
        return None
    return rdm_addon_option, exacc

def get_nextcloudinstitutions_credentials(institution):
    provider_name = 'nextcloudinstitutions'
    res = get_credentials_common(institution, provider_name)
    if res:
        opt, exacc = res
        provider = NextcloudInstitutionsProvider(exacc)
        host = use_https(provider.host).host
        username = provider.username
        password = provider.password
        notification_secret = opt.extended.get(KEYNAME_NOTIFICATION_SECRET)
        folder = opt.extended.get(KEYNAME_BASE_FOLDER)
    else:
        host = ''
        username = ''
        password = ''
        notification_secret = None
        folder = None
    if not folder:
        folder = nextcloudinstitutions_settings.DEFAULT_BASE_FOLDER
    data = {}
    data[provider_name + '_host'] = host
    data[provider_name + '_username'] = username
    data[provider_name + '_password'] = password
    data[provider_name + '_notification_secret'] = notification_secret
    data[provider_name + '_folder'] = folder
    return data

def get_s3compatinstitutions_credentials(institution):
    provider_name = 's3compatinstitutions'
    res = get_credentials_common(institution, provider_name)
    if res:
        opt, exacc = res
        provider = S3CompatInstitutionsProvider(exacc)
        host = provider.host  # host:port
        access_key = provider.username
        secret_key = provider.password
        bucket = opt.extended.get(KEYNAME_BASE_FOLDER)
    else:
        host = ''
        access_key = ''
        secret_key = ''
        bucket = None
    if not bucket:
        bucket = s3compatinstitutions_settings.DEFAULT_BASE_BUCKET
    data = {}
    data[provider_name + '_endpoint_url'] = host
    data[provider_name + '_access_key'] = access_key
    data[provider_name + '_secret_key'] = secret_key
    data[provider_name + '_bucket'] = bucket
    return data

def extuser_exists(provider_name, post_params, extuser):
    # return "error reason", None means existence
    if provider_name == 'nextcloudinstitutions':
        provider_setting = nextcloudinstitutions_settings
        host_url = post_params.get(provider_name + '_host')
        username = post_params.get(provider_name + '_username')
        password = post_params.get(provider_name + '_password')
        # folder = post_params.get(provider_name + '_folder')
        try:
            host = use_https(host_url)
            client = owncloud.Client(host.url,
                                     verify_certs=provider_setting.USE_SSL)
            client.login(username, password)
            if client.user_exists(extuser):
                return None  # exist
            return 'not exist'
        except Exception as e:
            return str(e)
    else:  # unsupported
        return None  # ok

def get_usermap(provider_name, institution):
    rdm_addon_option = get_rdm_addon_option(institution.id, provider_name,
                                            create=False)
    if not rdm_addon_option:
        return None
    return rdm_addon_option.extended.get(KEYNAME_USERMAP)

def save_usermap_to_tmp(provider_name, institution, usermap):
    rdm_addon_option = get_rdm_addon_option(institution.id, provider_name)
    rdm_addon_option.extended[KEYNAME_USERMAP_TMP] = usermap
    rdm_addon_option.save()

def clear_usermap_tmp(provider_name, institution):
    rdm_addon_option = get_rdm_addon_option(institution.id, provider_name,
                                            create=False)
    if not rdm_addon_option:
        return
    new_usermap = rdm_addon_option.extended.get(KEYNAME_USERMAP_TMP)
    if new_usermap:
        del rdm_addon_option.extended[KEYNAME_USERMAP_TMP]
        rdm_addon_option.save()

def save_usermap_from_tmp(provider_name, institution):
    rdm_addon_option = get_rdm_addon_option(institution.id, provider_name)
    new_usermap = rdm_addon_option.extended.get(KEYNAME_USERMAP_TMP)
    if new_usermap:
        rdm_addon_option.extended[KEYNAME_USERMAP] = new_usermap
        del rdm_addon_option.extended[KEYNAME_USERMAP_TMP]
        rdm_addon_option.save()
