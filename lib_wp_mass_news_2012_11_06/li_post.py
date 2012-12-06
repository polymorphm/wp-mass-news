# -*- mode: python; coding: utf-8 -*-
#
# Copyright 2012 Andrej A Antonov <polymorphm@gmail.com>.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

assert str is not bytes

import sys
import threading
import json
import csv
import random
from urllib import parse as url
from http import cookiejar
from urllib import request
from tornado import ioloop, stack_context, gen
from . import get_items
from . import urllib_request_helper
from . import lib_html_parse
html_parse = lib_html_parse.import_module('html_parse')

LI_HTTPS_URL = 'https://www.liveinternet.ru'
LI_HTTP_URL = 'http://www.liveinternet.ru'

TAGS_RANDOM_MU = 4
TAGS_RANDOM_SIGMA = 1

class LiError(Exception):
    pass

class AuthLiError(LiError):
    pass

class PublishLiError(LiError):
    pass

class Task:
    pass

def li_post_blocking(username=None, password=None,
        title=None, content=None, tags=None, ua_name=None):
    assert username is not None
    assert password is not None
    assert title is not None
    assert content is not None
    
    if tags is None:
        tags = ''
    
    if ua_name is None:
        ua_name = urllib_request_helper.DEFAULT_USER_AGENT_NAME
    
    li_login_url = url.urljoin(LI_HTTPS_URL, 'member.php')
    li_pda_url = url.urljoin(LI_HTTPS_URL, 'interface/pda/')
    
    cookies = cookiejar.CookieJar()
    opener = request.build_opener(
            request.HTTPCookieProcessor(cookiejar=cookies),
            )
    
    # *** PHASE: auth ***
    
    resp = urllib_request_helper.ext_open(
            opener,
            li_login_url,
            headers=(
                ('User-Agent', ua_name),
                ('Referer', LI_HTTPS_URL),
                ),
            data=url.urlencode({
                    'username': username,
                    'password': password,
                    'charset': 'utf',
                    'action': 'login',
                    }).encode(),
            timeout=urllib_request_helper.DEFAULT_TIMEOUT,
            )
    
    if resp.getcode() != 200 or \
            (resp.geturl() != LI_HTTPS_URL and resp.geturl() != LI_HTTPS_URL + '/'):
        raise AuthLiError('li auth error')
    
    # *** PHASE: get params ***
    
    user_id = cookies._cookies['www.liveinternet.ru']['/']['bbuserid'].value
    addpost_url = url.urljoin(li_pda_url,
            '?jid={}&act=addpostform'.format(url.quote_plus(user_id)))
    blog_url = url.urljoin(LI_HTTPS_URL,
            'users/{}/'.format(url.quote_plus(user_id)))
    
    # *** PHASE: publishing ***
    
    print('*** tags is {!r} ***'.format(tags))
    
    resp = urllib_request_helper.ext_open(
            opener,
            addpost_url,
            headers=(
                ('User-Agent', ua_name),
                ('Referer', addpost_url),
                ),
            data=url.urlencode({
                    'tags': tags.encode('windows-1251', 'replace'),
                    'postmessage': content.encode('windows-1251', 'replace'),
                    'postheader': title.encode('windows-1251', 'replace'),
                    'jid': user_id,
                    'close_level': '0',
                    'act': 'addpost',
                    }).encode(),
            timeout=urllib_request_helper.DEFAULT_TIMEOUT,
            )
    
    if resp.getcode() != 200 or resp.geturl() != addpost_url:
        raise PublishLiError('li publishing error')
    
    # *** PHASE: get post url ***
    
    resp = urllib_request_helper.ext_open(
            opener,
            blog_url,
            headers=(
                ('User-Agent', ua_name),
                ),
            timeout=urllib_request_helper.DEFAULT_TIMEOUT,
            )
    
    data = resp.read(urllib_request_helper.DEFAULT_RESPONSE_LIMIT).decode(
            'windows-1251', 'replace')
    
    post_link_nodes = tuple(html_parse.find_tags(
            (html_parse.html_parse(data),),
            'a', in_attrs={'class': 'GL_LNXMAR22'}))
    
    if not post_link_nodes:
        raise LiError('li publishing error (PHASE: get post url)')
    
    post_url = post_link_nodes[0].attrs['href']
    
    # *** END ***
    
    return post_url

def li_post(*args, callback=None, **kwargs):
    callback = stack_context.wrap(callback)
    
    def li_post_thread():
        result = None
        error = None
        
        try:
            result = li_post_blocking(*args, **kwargs)
        except:
            error = sys.exc_info()
        
        if callback is not None:
            ioloop.IOLoop.instance().add_callback(lambda: callback(result, error))
    
    t = threading.Thread(target=li_post_thread)
    t.daemon = True
    t.start()

def li_acc_save(task_cfg, task, excl_list):
    acc_row = task._acc_row
    
    if acc_row in excl_list:
        return
    
    fd = task_cfg.out.get_fd(ext='accs.csv')
    csv_writer = csv.writer(fd)
    
    csv_writer.writerow(acc_row)
    fd.flush()
    excl_list.append(acc_row)

def get_li_post_task_list(task_cfg, task_begin_handle=None, task_end_handle=None):
    task_begin_handle = stack_context.wrap(task_begin_handle)
    task_end_handle = stack_context.wrap(task_end_handle)
    
    raw_accs_iter = get_items.get_random_infinite_items(task_cfg.accs, is_csv=True)
    titles_iter = get_items.get_random_infinite_items(task_cfg.titles)
    if task_cfg.tags is not None:
        tags_iter = get_items.get_random_infinite_items(task_cfg.tags)
    else:
        tags_iter = None
    content_iter = get_items.get_random_infinite_items(task_cfg.content)
    
    acc_save_excl_list = []
    
    def next_acc():
        if 'li:0' == task_cfg.acc_fmt:
            while True:
                acc_row = next(raw_accs_iter)
                
                if len(acc_row) != 4:
                    raise NotImplementedError(
                            'invalid or not implemented account format')
                
                email, email_password, username, password = acc_row
                
                return username, password, acc_row
        
        # if 'li:...' == task_cfg.acc_fmt:
        #  ...
        #  return
        
        raise NotImplementedError('not implemented account format')
    
    for task_i in range(task_cfg.count):
        task = Task()
        
        task.i = task_i
        task.username, task.password, task._acc_row = next_acc()
        task.blog_id = 'li:{}'.format(task.username)
        task.title = next(titles_iter)
        task.content = next(content_iter)
        task.ua_name = task_cfg.ua_name
        
        if tags_iter is not None:
            tags_list = []
            for tag_i in range(max(round(random.gauss(TAGS_RANDOM_MU, TAGS_RANDOM_SIGMA)), 0)):
                tag = next(tags_iter)
                if tag in tags_list:
                    continue
                tags_list.append(tag)
            task.tags = ', '.join(tags_list)
        else:
            task.tags = None
        
        task.acc_save = lambda _task=task: li_acc_save(
                task_cfg,
                _task,
                acc_save_excl_list,
                )
        
        task.task_begin_handle = task_begin_handle
        task.task_end_handle = task_end_handle
        
        yield task

@gen.engine
def li_post_task(task, callback=None):
    callback = stack_context.wrap(callback)
    
    if task.task_begin_handle is not None:
        task.task_begin_handle(task)
    
    task.result, task.error = (yield gen.Task(
            li_post,
            username=task.username,
            password=task.password,
            title=task.title,
            tags=task.tags,
            content=task.content,
            ua_name=task.ua_name
            )).args
    
    if task.task_end_handle is not None:
        task.task_end_handle(task)
    
    if callback is not None:
        callback()
