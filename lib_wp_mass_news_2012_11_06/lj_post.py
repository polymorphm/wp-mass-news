# -*- mode: python; coding: utf-8 -*-
#
# Copyright 2012, 2013 Andrej A Antonov <polymorphm@gmail.com>.
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

import traceback
import threading
import json
import csv
import weakref
import random
from urllib import parse as url
from http import cookiejar
from urllib import request
from tornado import ioloop, stack_context, gen
from . import get_items
from . import urllib_request_helper
from . import lib_html_parse
html_parse = lib_html_parse.import_module('html_parse')

LJ_HTTPS_URL = 'https://www.livejournal.com'
LJ_HTTP_URL = 'http://www.livejournal.com'

TAGS_RANDOM_MU = 4
TAGS_RANDOM_SIGMA = 1

_lj_acc_save_excl_list = weakref.WeakKeyDictionary()

class LjError(Exception):
    pass

class AuthLjError(LjError):
    pass

class PublishLjError(LjError):
    pass

class Task:
    pass

def lj_post_blocking(username=None, password=None,
        title=None, content=None, tags=None, ua_name=None, proxy_kwargs=None):
    assert username is not None
    assert password is not None
    assert title is not None
    assert content is not None
    
    if tags is None:
        tags = ''
    
    if ua_name is None:
        ua_name = urllib_request_helper.DEFAULT_USER_AGENT_NAME
    
    lj_login_url = url.urljoin(LJ_HTTPS_URL, 'login.bml?ret=1')
    lj_update_url = url.urljoin(LJ_HTTP_URL, 'update.bml')
    
    cookies = cookiejar.CookieJar()
    opener = request.build_opener(
            request.HTTPCookieProcessor(cookiejar=cookies),
            )
    
    # *** PHASE: auth ***
    
    resp = urllib_request_helper.ext_open(
            opener,
            lj_login_url,
            headers=(
                    ('User-Agent', ua_name),
                    ('Referer', lj_login_url),
                    ),
            data=url.urlencode({
                    'user': username,
                    'remember_me': '1',
                    'ref': lj_update_url,
                    'password': password,
                    'action:login': 'Log in',
                    }).encode(),
            timeout=urllib_request_helper.DEFAULT_TIMEOUT,
            proxy_kwargs=proxy_kwargs,
            )
    
    if resp.getcode() != 200 or resp.geturl() != lj_update_url:
        raise AuthLjError('lj auth error')
    
    # *** PHASE: get params ***
    
    data = resp.read(urllib_request_helper.DEFAULT_RESPONSE_LIMIT).decode('utf-8', 'replace')
    
    form_html_nodes = tuple(html_parse.find_tags(
            (html_parse.html_parse(data),),
            'form',
            attrs={
                    'id': 'post',
                    'method': 'post',
                    'action': '',
                    },
            ))
    
    def get_params():
        params = {}
        for node in html_parse.find_tags(
                form_html_nodes,
                'input',
                ):
            name = node.attrs.get('name')
            if not name:
                continue
            value = node.attrs.get('value')
            if not value:
                continue
            
            params[name] = value
        
        return params
    
    params = get_params()
    
    # *** PHASE: publishing ***
    
    resp = urllib_request_helper.ext_open(
            opener,
            lj_update_url,
            headers=(
                    ('User-Agent', ua_name),
                    ('Referer', lj_update_url),
                    ),
            data=url.urlencode({
                    'timezone': params['timezone'],
                    'time': params['time'],
                    'subject': title,
                    'security': 'public',
                    'rte_on': params['rte_on'],
                    'prop_taglist': tags,
                    'prop_adult_content': 'default',
                    'postto': 'journal',
                    'postas': 'remote',
                    'lj_form_auth': params['lj_form_auth'],
                    'date_format': params['date_format'],
                    'date_diff': params['date_diff'],
                    'date': params['date'],
                    'custom_time': params['custom_time'],
                    'comment_settings': 'default',
                    'body': content,
                    'action:update': '1',         
                    }).encode(),
            timeout=urllib_request_helper.DEFAULT_TIMEOUT,
            proxy_kwargs=proxy_kwargs,
            )
    
    if resp.getcode() != 200 or resp.geturl() == lj_update_url:
        raise PublishLjError('lj publishing error')
    
    # *** END ***
    
    post_url = resp.geturl()
    
    return post_url

def lj_post(*args, callback=None, **kwargs):
    callback = stack_context.wrap(callback)
    
    def lj_post_thread():
        result = None
        error = None
        
        try:
            result = lj_post_blocking(*args, **kwargs)
        except Exception as e:
            error = type(e), str(e), traceback.format_exc()
        
        if callback is not None:
            ioloop.IOLoop.instance().add_callback(lambda: callback(result, error))
    
    t = threading.Thread(target=lj_post_thread)
    t.daemon = True
    t.start()

def lj_acc_save(task_cfg, task):
    fd = task_cfg.out.get_fd(ext='accs.csv')
    try:
        excl_list = _lj_acc_save_excl_list[fd]
    except KeyError:
        _lj_acc_save_excl_list[fd] = excl_list = []
    acc_row = task._acc_row
    
    if acc_row in excl_list:
        return
    
    csv_writer = csv.writer(fd)
    
    csv_writer.writerow(acc_row)
    fd.flush()
    excl_list.append(acc_row)

def get_lj_post_task_list(task_cfg, task_begin_handle=None, task_end_handle=None):
    task_begin_handle = stack_context.wrap(task_begin_handle)
    task_end_handle = stack_context.wrap(task_end_handle)
    
    raw_accs_iter = get_items.get_random_infinite_items(task_cfg.accs, is_csv=True)
    if task_cfg.tags is not None:
        tags_iter = get_items.get_random_infinite_items(task_cfg.tags)
    else:
        tags_iter = None
    title_and_content_iter = get_items.get_title_and_content(\
            get_items.get_random_infinite_items, task_cfg.titles, task_cfg.content)
    
    def next_acc():
        if 'lj:0' == task_cfg.acc_fmt:
            while True:
                acc_row = next(raw_accs_iter)
                
                if len(acc_row) != 4:
                    raise NotImplementedError(
                            'invalid or not implemented account format')
                
                email, email_password, username, password = acc_row
                
                return username, password, acc_row
        
        # if 'lj:...' == task_cfg.acc_fmt:
        #  ...
        #  return
        
        raise NotImplementedError('not implemented account format')
    
    for task_i in range(task_cfg.count):
        task = Task()
        
        task.i = task_i
        task.username, task.password, task._acc_row = next_acc()
        task.blog_id = 'lj:{}'.format(task.username)
        task.title, task.content = next(title_and_content_iter)
        task.ua_name = task_cfg.ua_name
        task.proxy_kwargs = task_cfg.proxy_kwargs
        
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
        
        task.acc_save = lambda _task=task: lj_acc_save(
                task_cfg,
                _task,
                )
        
        task.task_begin_handle = task_begin_handle
        task.task_end_handle = task_end_handle
        
        yield task

@gen.engine
def lj_post_task(task, callback=None):
    callback = stack_context.wrap(callback)
    
    if task.task_begin_handle is not None:
        task.task_begin_handle(task)
    
    task.result, task.error = (yield gen.Task(
            lj_post,
            username=task.username,
            password=task.password,
            title=task.title,
            content=task.content,
            tags=task.tags,
            ua_name=task.ua_name,
            proxy_kwargs=task.proxy_kwargs,
            )).args
    
    if task.task_end_handle is not None:
        task.task_end_handle(task)
    
    if callback is not None:
        callback(task.error)
