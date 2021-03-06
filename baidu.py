#!/usr/bin/python
# -*- coding: utf8 -*-

from os import path

CONFIG_FILE = 'baidu.yaml'
CONFIG_FILE = path.join(path.dirname(path.realpath(__file__)), CONFIG_FILE)
MAX_SIGN_LIMIT = 100


import sys

py = sys.version_info
py3k = py >= (3, 0, 0)

default_encoding = sys.getfilesystemencoding()
if default_encoding.lower() == 'ascii':
    default_encoding = 'utf-8'

if py3k:
    from urllib.request import urlopen, build_opener, install_opener
    from urllib.request import Request, HTTPCookieProcessor
    from urllib.parse import urlencode
    from http.cookiejar import MozillaCookieJar, CookieJar
    from html.parser import HTMLParser
    from io import StringIO
    input = input
    U = lambda s: s
    def printu(x, *y):
        print(x % y)
    encode = lambda s: urlencode(s).encode('utf-8')
else:
    from urllib2 import urlopen, build_opener, install_opener
    from urllib2 import Request, HTTPCookieProcessor
    from urllib import urlencode
    from cookielib import MozillaCookieJar, CookieJar
    from HTMLParser import HTMLParser
    from StringIO import StringIO
    input = raw_input
    U = lambda s, encoding='utf-8': s.decode(encoding) if isinstance(s, str) else s
    B = lambda s, encoding='utf-8': U(s).encode(encoding) if isinstance(s, basestring) else s
    def printu(x, *y):
        print(U(x) % y)
    def encode(s):
        if isinstance(s, dict):
            d = {}
            for k, v in s.items():
                d[B(k)] = B(v)
            s = d
        return urlencode(s).encode('utf8')

import re
import json
from time import sleep
from base64 import standard_b64decode as b64decode
import yaml

CONFIG = yaml.load(open(CONFIG_FILE, 'r'))
FF_COOKIE_DB = CONFIG.get('ff_cookie_db', '')
if FF_COOKIE_DB:
    try:
        import sqlite3 as sqlite
    except ImportError:
        FF_COOKIE_DB = ''
LOGIN_METHOD = CONFIG.get('login_method', 'pc')
SIGN_INTERVAL = CONFIG.get('sign_interval', 0.5)
REPLY_INTERVAL = CONFIG.get('reply_interval', 1.0)
REPLIES = CONFIG.get('replies', [])
SIGN_TIEBAS = CONFIG.get('signs', [])
SIGN_TIEBAS = sum(SIGN_TIEBAS, [])

TBS_URL = 'http://tieba.baidu.com/dc/common/tbs'
SIGN_URL = 'http://tieba.baidu.com/sign/add'
LOGIN_URL = '\
https://passport.baidu.com/v2/api/?getapi&class=login&tpl=mn&tangram=false'

if len(SIGN_TIEBAS) > MAX_SIGN_LIMIT:
    printu('注意: 你只能签到 %s 个贴吧！', MAX_SIGN_LIMIT)
    input('Ctrl - C 终止，回车继续')


def find_field(pattern, s):
    return re.findall(U(pattern), s)[0]


def login(username, password, login_method=LOGIN_METHOD):
    if login_method == 'wap':
        data = {
            'login_username': username,
            'login_loginpass': password,
            }
        urlopen('http://wappass.baidu.com/passport/', encode(data))
    else:
    #elif login_method == 'pc':
        r = urlopen(LOGIN_URL).read().decode('gbk')
        data = {
                "username": username.encode("gbk"),
                "password": password,
                "token": find_field("login_token='(\w+)'", r),
                "verifycode": '',
                "mem_pass": "on",
                "charset": "gbk",
                "isPhone": "false",
                "index": "0",
                "safeflg": "0",
                "staticpage": "http://tieba.baidu.com/tb/v2Jump.html",
                "loginType": "1",
                "tpl": "mn",
                "codestring": '',
                "callback": "parent.bdPass.api.loginLite._submitCallBack"
                }
        urlopen('https://passport.baidu.com/v2/api/?login', encode(data))
    return


def get_tbs():
    tbs_json = urlopen(TBS_URL).read().decode('utf-8')
    tbs_data = json.loads(tbs_json)
    if tbs_data.get('is_login', None) != 1:  # not login
        username = CONFIG.get('username', '')
        if username:
            password = CONFIG.get('password', '')
            if password:
                pwdmethod = CONFIG.get('password_method', 'raw')
                if pwdmethod == 'base64':
                    password = b64decode(password.encode('utf-8'))
            else:
                password = input('请输入 %s 的密码：' % username)
        else:
            printu('你尚未登录！')
            username = input('Username:')
            password = input('Password:')
        login(username, password)
        tbs_json = urlopen(TBS_URL).read().decode('utf-8')
        tbs_data = json.loads(tbs_json)
        if tbs_data.get('is_login', None) != 1:
            raise Exception('登录失败！')
    assert 'tbs' in tbs_data
    return tbs_data['tbs']


def get_cookies_from_ff(db_filename):
    con = sqlite.connect(db_filename)
    con.execute("pragma journal_mode=WAL")
    cur = con.cursor()
    cur.execute(
            "select host, path, isSecure, expiry, name, value from moz_cookies"
            )
    container = []
    while True:
        try:
            row = cur.fetchone()
        except:
            continue
        if not row:
            break
        if not row[4].startswith('chkSlider'):  # FIXME: this is a dirty fix
            container.append(row)
    con.close()
    ftstr = ["FALSE", "TRUE"]
    s = StringIO()
    s.write("""\
# Netscape HTTP Cookie File
# http://www.netscape.com/newsref/std/cookie_spec.html
# This is a generated file!  Do not edit.
""")
    for item in container:
        v = "%s\t%s\t%s\t%s\t%s\t%s\t%s\n" % (
            item[0], ftstr[item[0].startswith('.')], item[1],
            ftstr[item[2]], item[3], item[4], item[5])
        s.write(v)
    s.seek(0)
    cookie_jar = MozillaCookieJar()
    cookie_jar._really_load(s, '', True, True)
    return cookie_jar


def fake_sign(name, tbs):
    print(name)
    import random
    r = random.randint(0, 8)
    if r != 8:
        return 0 , "签到果然成功"
    else:
        return -1 , "签到果然失败"


def sign(name, tbs):
    data = encode({'kw': name, 'ie': 'utf-8', 'tbs': tbs})
    req = Request(url=SIGN_URL, data=data)
    content = urlopen(req).read()
    try:
        content = content.decode('utf-8')
    except UnicodeDecodeError:
        try:
            content = content.decode('gbk')
            #printu(content)
        except UnicodeDecodeError:
            return -1, U('未知的响应编码')
        return -1, U('请求失败！')
    ret = json.loads(content)
    errno = ret.get('no', -1)
    if errno != 0:
        msg = U('XX 签到失败！: %s - %s') % (errno, ret.get('error', ''))
    else:
        msg = U('   签到成功！你是第 %s 个签到的人！') % \
                ret['data']['uinfo']['user_sign_rank']
    return errno, msg

content_utils = {
        'emotion': lambda s: '''\
<img width="40" height="40" \
src="http://static.tieba.baidu.com/tb/editor/images/%s.gif" \
class="BDE_Smiley">''' % s,
        }


def fake_reply(tid, tbs, content):
    print(tid, content)
    import random
    r = random.randint(0, 3)
    if r != 3:
        return 0 , "签到果然成功"
    else:
        return -1 , "签到果然失败"


def reply(tid, tbs, content):
    tbtext = urlopen("http://tieba.baidu.com/p/%s" % tid).read()
    try:
        tb = tbtext.decode('gbk')
    except UnicodeDecodeError:
        tb = tbtext.decode('gbk', errors='ignore')
    post_data = find_field('data : {([^}]+)}', tb)
    post_data = HTMLParser().unescape(post_data)
    fid = find_field("fid:'([^']+)'", post_data)
    kw = find_field("kw:'([^']+)'", post_data)
    data = {
            'kw': kw,
            'ie': 'utf-8',
            'rich_text': '1',
            'anonymous': '0',
            'content': content,
            'fid': fid,
            'tid': tid,
            'tbs': tbs,
            }
    req = urlopen("http://tieba.baidu.com/f/commit/post/add", encode(data))
    ret = json.loads(req.read().decode('gbk'))
    errno = ret.get('no', -1)
    if errno != 0:
        msg = U('XX 回复失败！: %s - %s') % (errno, ret.get('error', ''))
    else:
        msg = U('   回复成功！')
    return errno, msg


def main(replies, signs):
    # global reply, sign
    # reply, sign = fake_reply, fake_sign

    if FF_COOKIE_DB:
        try:
            cookie_jar = get_cookies_from_ff(FF_COOKIE_DB)
        except:
            printu('加载 FF Cookie 失败！')
            cookie_jar = CookieJar()
    else:
        cookie_jar = CookieJar()
    opener = build_opener(HTTPCookieProcessor(cookie_jar))
    opener.addheaders = [('User-agent', 'Opera/9.23')]
    install_opener(opener)
    tbs = get_tbs()

    retry_tasks(lambda tasks: reply_all(tasks, tbs), replies, '以下帖子回复失败：')
    retry_tasks(lambda tasks: sign_all(tasks, tbs), signs, '以下贴吧签到失败：')


def retry_tasks(do, tasks, msg=''):
    while True:
        failed_tasks = do(tasks)
        if len(failed_tasks) > 0:
            printu(msg)
            print(failed_tasks)
            r = input('输入r重试，输入其它退出:').strip().lower()
            if r == 'r':
                tasks = failed_tasks
                continue
        break
    return len(failed_tasks) == 0

def reply_all(replies, tbs=None):
    if tbs is None:
        tbs = get_tbs()
    failed_replies = replies[:]
    for item in replies:
        tid = item.get('tid', -1)
        if tid <= 0:
            failed_replies.remove(item)
            continue
        content = item.get('content', '')
        comment = item.get('comment', '')
        printu('正在回复: tid: %s - %s', tid, comment)
        if isinstance(content, (tuple, list)):
            func = content_utils.get(content[0], lambda *x: ''.join(str(x)))
            content = func(*content[1:])
        errno, msg = reply(tid, tbs, content)
        printu(msg)
        if errno == 0:
            failed_replies.remove(item)
        sleep(REPLY_INTERVAL)
    return failed_replies

def sign_all(signs, tbs=None):
    if tbs is None:
        tbs = get_tbs()
    failed_signs = signs[:]
    for name in signs:
        printu('正在签到: %s', name)
        errno, msg = sign(name, tbs)
        printu(msg)
        if errno in (1102, 1007):  # too often
            return failed_signs
        elif errno in (0, 1101):  # 1101: already signed
            failed_signs.remove(name)
        sleep(SIGN_INTERVAL)
    return failed_signs


if __name__ == '__main__':
    main(REPLIES, SIGN_TIEBAS)
