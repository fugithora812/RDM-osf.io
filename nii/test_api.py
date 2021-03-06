# -*- coding: utf-8 -*-
#
# @COPYRIGHT@
#

import logging
import os
import sys
import json

# global setting
logger = logging.getLogger(__name__)
if __name__ == '__main__':
    logger = logging.getLogger('nii.mapcore')
    # stdout = logging.StreamHandler()  # log to stdio
    # logger.addHandler(stdout)
    logger.setLevel(level=logging.DEBUG)
    from website.app import init_app
    init_app(routes=False, set_backends=False)

from osf.models.user import OSFUser
from nii.mapcore_api import MAPCore, MAPCoreException, MAPCoreTokenExpired


"""
map_hostname = settings.MAPCORE_HOSTNAME
map_authcode_path = settings.MAPCORE_AUTHCODE_PATH
map_token_path = settings.MAPCORE_TOKEN_PATH
map_refresh_path = settings.MAPCORE_REFRESH_PATH
map_clientid = settings.MAPCORE_CLIENTID
map_secret = settings.MAPCORE_SECRET
map_redirect = settings.MAPCORE_REDIRECT
map_authcode_magic = settings.MAPCORE_AUTHCODE_MAGIC
my_home = settings.DOMAIN
"""

#
# テスト用メインプログラム
#
if __name__ == '__main__':
    print('In Main')
    os.environ['DJANGO_SETTINGS_MODULE'] = 'api.base.settings'

    #
    # Get OSFUser object for an account specified by argument.
    #
    user = OSFUser.objects.get(eppn=sys.argv[1])
    if not user:
        logger.info('No SUCH USER')
        sys.exit()

    print('name:', user.fullname)
    print('eppn:', user.eppn)
    '''
    if hasattr(user, 'map_profile'):
        #print('access_token:', user.map_profile.oauth_access_token)
        #print('refresh_token:', user.map_profile.oauth_refresh_token)
    else:
        logger.info('User does not have map_profile')
        sys.exit()
    '''

    group_name = u'mAP Coop Test 001'
    introduction = u'mAP Coop Test 001'
    user_eppn = 'jj1afp@openidp.nii.ac.jp'

    #
    # MAPCore interface object.
    #
    mapcore = MAPCore(user)

    #
    # API バージョン
    #
    try:
        j = mapcore.get_api_version()
    except MAPCoreTokenExpired as e:
        if e.caller == user:
            logger.info('FATAL ERROR: TOKEN EXPIRED (CALLER)')
        else:
            logger.info('FATAL ERROR: TOKEN EXPIRED')
        sys.exit()
    except MAPCoreException as e:
        logger.info('ERROR: ' + str(e))
        sys.exit()

    logger.info('version=' + str(j['result']['version']))
    logger.info('revision=' + j['result']['revision'])
    logger.info('author=' + j['result']['author'])

    #
    # 新規グループ作成 (group_name をグループ名として)
    #
    '''
    try:
        j = mapcore.create_group('BBBBB')
    except MAPCoreTokenExpired:
        logger.info('FATAL ERROR: TOKEN EXPIRED')
        sys.exit()
    except MAPCoreException as e:
        logger.info('ERROR: ' + str(e))
        sys.exit()

    logger.info(json.dumps(j, indent = 2))
    '''

    #
    # group_name を名前に持つグループを検索
    #
    try:
        j = mapcore.get_group_by_name(group_name)
    except MAPCoreTokenExpired:
        logger.info('FATAL ERROR: TOKEN EXPIRED')
        sys.exit()
    except MAPCoreException as e:
        logger.info('ERROR: ' + str(e))
        sys.exit()

    group_key = j['result']['groups'][0]['group_key']
    logger.info('Group key for ' + group_name + ' found, ' + group_key)
    logger.info(json.dumps(j, indent=2))

    #
    # group_key で指定したグループの名前、紹介文を変更
    #
    try:
        j = mapcore.edit_group(group_key, group_name, introduction)
    except MAPCoreTokenExpired:
        logger.info('FATAL ERROR: TOKEN EXPIRED')
        sys.exit()
    except MAPCoreException as e:
        logger.info('ERROR: ' + str(e))
        sys.exit()

    logger.info(json.dumps(j, indent=2))

    #
    # group_key で指定したグループの情報を取得
    #
    try:
        j = mapcore.get_group_by_key(group_key)
    except MAPCoreTokenExpired:
        logger.info('FATAL ERROR: TOKEN EXPIRED')
        sys.exit()
    except MAPCoreException as e:
        logger.info('ERROR: ' + str(e))
        sys.exit()

    logger.info(json.dumps(j, indent=2))

    #
    # user_eppn を一般会員としてメンバーに追加
    #
    try:
        j = mapcore.add_to_group(group_key, user_eppn, MAPCore.MODE_MEMBER)
    except MAPCoreTokenExpired:
        logger.info('FATAL ERROR: TOKEN EXPIRED')
        sys.exit()
    except MAPCoreException as e:
        logger.info('ERROR: ' + str(e))
        sys.exit()

    logger.info('Completed')

    #
    # user_eppn をグループ管理者に変更
    #
    try:
        j = mapcore.edit_member(group_key, user_eppn, MAPCore.MODE_ADMIN)
    except MAPCoreTokenExpired:
        logger.info('FATAL ERROR: TOKEN EXPIRED')
        sys.exit()
    except MAPCoreException as e:
        logger.info('ERROR: ' + str(e))
        sys.exit()

    logger.info('Completed')

    #
    # 上記グループのメンバーリストを取得
    #
    try:
        j = mapcore.get_group_members(group_key)
    except MAPCoreTokenExpired:
        logger.info('FATAL ERROR: TOKEN EXPIRED')
        sys.exit()
    except MAPCoreException as e:
        logger.info('ERROR: ' + str(e))
        sys.exit()

    # logger.info(json.dumps(j).encode('utf-8'))
    for i in range(len(j['result']['accounts'])):
        if 'eppn' in j['result']['accounts'][i]:
            eppn = j['result']['accounts'][i]['eppn'].encode('utf-8')
            if 'mail' in j['result']['accounts'][i]:
                mail = str(j['result']['accounts'][i]['mail'])
            else:
                mail = eppn
            admin = str(j['result']['accounts'][i]['admin'])
            logger.info('eppn=' + eppn + ', mail=' + mail + ', admin=' + admin)

    #
    # user_eppn をメンバーから追加
    #
    try:
        j = mapcore.remove_from_group(group_key, user_eppn)
    except MAPCoreTokenExpired:
        logger.info('FATAL ERROR: TOKEN EXPIRED')
        sys.exit()
    except MAPCoreException as e:
        logger.info('ERROR: ' + str(e))
        sys.exit()

    logger.info('Completed')

    #
    # 自身が所属しいているグループのリストを取得
    #
    try:
        j = mapcore.get_my_groups()
    except MAPCoreTokenExpired:
        logger.info('FATAL ERROR: TOKEN EXPIRED')
        sys.exit()
    except MAPCoreException as e:
        logger.info('ERROR: ' + str(e))
        sys.exit()

    for i in range(len(j['result']['groups'])):
        logger.info('    ' + j['result']['groups'][i]['group_name'] + ' (key=' + j['result']['groups'][i]['group_key'] + ')')

    #
    # 終了
    #
    logger.info('Function completed')
    sys.exit()
