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

import traceback
import threading
import json
import csv
import weakref
from urllib import parse as url
from http import cookiejar
from urllib import request
from tornado import ioloop, stack_context, gen
from . import get_items
from . import urllib_request_helper
from . import lib_html_parse
html_parse = lib_html_parse.import_module('html_parse')

FF_HTTPS_URL = 'https://friendfeed.com'
FF_HTTP_URL = 'http://friendfeed.com'

_ff_acc_save_excl_list = weakref.WeakKeyDictionary()

class FfError(Exception):
    pass

class AuthFfError(FfError):
    pass

class PublishFfError(FfError):
    pass

class Task:
    pass

def ff_post_blocking(username=None, password=None,
        content=None, ua_name=None):
    assert username is not None
    assert password is not None
    assert content is not None
    
    if ua_name is None:
        ua_name = urllib_request_helper.DEFAULT_USER_AGENT_NAME
    
    ff_login_url = url.urljoin(FF_HTTPS_URL, 'account/login?v=2')
    ff_share_url = url.urljoin(FF_HTTP_URL, 'a/share')
    
    cookies = cookiejar.CookieJar()
    opener = request.build_opener(
            request.HTTPCookieProcessor(cookiejar=cookies),
            )
    
    # *** PHASE: get params for auth ***
    
    resp = urllib_request_helper.ext_open(
            opener,
            ff_login_url,
            headers=(
                    ('User-Agent', ua_name),
                    ),
            timeout=urllib_request_helper.DEFAULT_TIMEOUT,
            )
    
    if resp.getcode() != 200 or resp.geturl() != ff_login_url:
        raise FfError('phase: get params for auth: http-error')
    
    data = resp.read(urllib_request_helper.DEFAULT_RESPONSE_LIMIT).decode()
    
    at_nodes = tuple(html_parse.find_tags(
            html_parse.find_tags(
                    (html_parse.html_parse(data),),
                    'form',
                    attrs={
                            'method': 'post',
                            'action': '/account/login?v=2',
                            },
                    ),
            'input',
            attrs={
                    'name': 'at',
                    },
            ))
    
    if not at_nodes:
        raise FfError('phase -- get params for auth: not found at_param')
    
    at_param = at_nodes[0].attrs.get('value')
    
    # *** PHASE: auth ***
    
    resp = urllib_request_helper.ext_open(
            opener,
            ff_login_url,
            headers=(
                    ('User-Agent', ua_name),
                    ('Referer', ff_login_url),
                    ),
            data=url.urlencode({
                    'email': username,
                    'password': password,
                    'at': at_param,
                    'next': FF_HTTP_URL,
                    }).encode(),
            timeout=urllib_request_helper.DEFAULT_TIMEOUT,
            )
    
    if resp.getcode() != 200 or \
            (resp.geturl() != FF_HTTP_URL and resp.geturl() != FF_HTTP_URL + '/'):
        raise AuthFfError('ff auth error')
    
    # *** PHASE: publish ***
    
    data = resp.read(urllib_request_helper.DEFAULT_RESPONSE_LIMIT).decode()
    
    form_nodes = tuple(html_parse.find_tags(
            (html_parse.html_parse(data),),
            'form',
            attrs={
                    'method': 'post',
                    'action': '/a/share',
                    },
            ))
    streams_nodes = tuple(html_parse.find_tags(
            form_nodes,
            'input',
            attrs={
                    'name': 'streams',
                    },
            ))
    at_nodes = tuple(html_parse.find_tags(
            form_nodes,
            'input',
            attrs={
                    'name': 'at',
                    },
            ))
    
    if not streams_nodes or not at_nodes :
        raise FfError('phase -- publish: not found -- streams_param or/and at_param')
    
    streams_param = streams_nodes[0].attrs.get('value')
    at_param = at_nodes[0].attrs.get('value')
    
    resp = urllib_request_helper.ext_open(
            opener,
            ff_share_url,
            headers=(
                    ('User-Agent', ua_name),
                    ('X-Requested-With', 'XMLHttpRequest'),
                    ),
            data=url.urlencode({
                    'title': content,
                    'streams': '+'.join((
                            streams_param,
                            'friends',
                            )),
                    'at': at_param,
                    '_nano': 1, # what is that?
                    }).encode(),
            timeout=urllib_request_helper.DEFAULT_TIMEOUT,
            )
    
    if resp.getcode() != 200 or resp.geturl() != ff_share_url:
        raise PublishFfError('ff publish error')
    
    data = resp.read(urllib_request_helper.DEFAULT_RESPONSE_LIMIT).decode()
    data_json = json.loads(data)
    
    publish_ok = data_json.get('success')
    
    if publish_ok is None or not isinstance(publish_ok, bool) or not publish_ok:
        raise PublishFfError('ff publish error (shared, but not success)')
    
    publish_html = str(data_json.get('html', ''))
    
    publish_nodes = tuple(html_parse.find_tags(
            (html_parse.html_parse(publish_html),),
            'a', attrs={'class': 'date'},
            ))
    
    if not publish_nodes:
        raise PublishFfError('ff publish error (can not get post_url)')
    
    post_url = url.urljoin(FF_HTTP_URL, publish_nodes[0].attrs.get('href'))
    
    # *** PHASE: end ***
    
    return post_url

def ff_post(*args, callback=None, **kwargs):
    callback = stack_context.wrap(callback)
    
    def ff_post_thread():
        result = None
        error = None
        
        try:
            result = ff_post_blocking(*args, **kwargs)
        except Exception as e:
            error = type(e), e, traceback.format_exc()
        
        if callback is not None:
            ioloop.IOLoop.instance().add_callback(lambda: callback(result, error))
    
    t = threading.Thread(target=ff_post_thread)
    t.daemon = True
    t.start()

def ff_acc_save(task_cfg, task):
    fd = task_cfg.out.get_fd(ext='accs.csv')
    try:
        excl_list = _ff_acc_save_excl_list[fd]
    except KeyError:
        _ff_acc_save_excl_list[fd] = excl_list = []
    acc_row = task._acc_row
    
    if acc_row in excl_list:
        return
    
    csv_writer = csv.writer(fd)
    
    csv_writer.writerow(acc_row)
    fd.flush()
    excl_list.append(acc_row)

def get_ff_post_task_list(task_cfg, task_begin_handle=None, task_end_handle=None):
    task_begin_handle = stack_context.wrap(task_begin_handle)
    task_end_handle = stack_context.wrap(task_end_handle)
    
    raw_accs_iter = get_items.get_random_infinite_items(task_cfg.accs, is_csv=True)
    content_iter = get_items.get_random_infinite_items(task_cfg.content)
    
    def next_acc():
        if 'ff:0' == task_cfg.acc_fmt:
            while True:
                acc_row = next(raw_accs_iter)
                
                if len(acc_row) != 4:
                    raise NotImplementedError(
                            'invalid or not implemented account format')
                
                email, email_password, username, password = acc_row
                
                return username, password, acc_row
        
        # if 'ff:...' == task_cfg.acc_fmt:
        #  ...
        #  return
        
        raise NotImplementedError('not implemented account format')
    
    for task_i in range(task_cfg.count):
        task = Task()
        
        task.i = task_i
        task.username, task.password, task._acc_row = next_acc()
        task.blog_id = 'ff:{}'.format(task.username)
        task.content = next(content_iter)
        task.ua_name = task_cfg.ua_name
        
        task.acc_save = lambda _task=task: ff_acc_save(
                task_cfg,
                _task,
                )
        
        task.task_begin_handle = task_begin_handle
        task.task_end_handle = task_end_handle
        
        yield task

@gen.engine
def ff_post_task(task, callback=None):
    callback = stack_context.wrap(callback)
    
    if task.task_begin_handle is not None:
        task.task_begin_handle(task)
    
    task.result, task.error = (yield gen.Task(
            ff_post,
            username=task.username,
            password=task.password,
            content=task.content,
            ua_name=task.ua_name
            )).args
    
    if task.task_end_handle is not None:
        task.task_end_handle(task)
    
    if callback is not None:
        callback(task.error)
