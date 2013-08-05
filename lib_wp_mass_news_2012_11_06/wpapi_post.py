# -*- mode: python; coding: utf-8 -*-
#
# Copyright 2013 Andrej A Antonov <polymorphm@gmail.com>.
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
import csv
import weakref
from xmlrpc import client as xmlrpc
from urllib import parse as url
from urllib import request
from tornado import ioloop, stack_context, gen
from . import get_items
from . import urllib_request_helper

_wpapi_acc_save_excl_list = weakref.WeakKeyDictionary()

class WpapiError(Exception):
    pass

class HttpWpapiError(WpapiError):
    pass
    
class ResultWpapiError(WpapiError):
    pass

class Task:
    pass

def wpapi_post_blocking(blog_url=None, username=None, password=None,
        title=None, content=None, slug=None, ua_name=None):
    assert blog_url is not None
    assert username is not None
    assert password is not None
    assert title is not None
    assert content is not None
    
    if ua_name is None:
        ua_name = urllib_request_helper.DEFAULT_USER_AGENT_NAME
    
    xmlrpc_url = url.urljoin(blog_url, 'xmlrpc.php')
    opener = request.build_opener()
    
    xmlrpc_data_content = {
            'title': title,
            'description': content,
            }
    if slug is not None:
        xmlrpc_data_content['wp_slug'] = slug
    xmlrpc_data = xmlrpc.dumps(
            (0, username, password, xmlrpc_data_content, True),
            'metaWeblog.newPost',
            )
    
    resp = urllib_request_helper.ext_open(
            opener,
            request.Request(
                    xmlrpc_url,
                    data=xmlrpc_data.encode('utf-8', 'replace'),
                    headers={
                            'User-Agent': ua_name,
                            'Content-Type': 'application/xml;charset=utf-8',
                            },
                    ),
            timeout=urllib_request_helper.DEFAULT_TIMEOUT,
            )
    
    if resp.getcode() != 200 or resp.geturl() != xmlrpc_url:
        raise HttpWpapiError('http error')
    
    data = resp.read(urllib_request_helper.DEFAULT_RESPONSE_LIMIT).decode('utf-8', 'replace')
    xmlrpc_resp_params, xmlrpc_resp_method = xmlrpc.loads(data) # or raise xmlrpc.client.Fault
    
    if len(xmlrpc_resp_params) != 1 or not isinstance(xmlrpc_resp_params[0], str):
        raise ResultWpapiError('invalid result')
    
    post_url = url.urljoin(blog_url, '?{}'.format(url.urlencode({
            'page_id': xmlrpc_resp_params[0],
            })))
    
    return post_url

def wpapi_post(*args, callback=None, **kwargs):
    callback = stack_context.wrap(callback)
    
    def wpapi_post_thread():
        result = None
        error = None
        
        try:
            result = wpapi_post_blocking(*args, **kwargs)
        except Exception as e:
            error = type(e), str(e), traceback.format_exc()
        
        if callback is not None:
            ioloop.IOLoop.instance().add_callback(lambda: callback(result, error))
    
    t = threading.Thread(target=wpapi_post_thread)
    t.daemon = True
    t.start()

def wpapi_acc_save(task_cfg, task):
    fd = task_cfg.out.get_fd(ext='accs.csv')
    try:
        excl_list = _wpapi_acc_save_excl_list[fd]
    except KeyError:
        excl_list = _wpapi_acc_save_excl_list[fd] = []
    acc_row = task._acc_row
    
    if acc_row in excl_list:
        return
    
    csv_writer = csv.writer(fd)
    
    csv_writer.writerow(acc_row)
    fd.flush()
    excl_list.append(acc_row)

def get_wpapi_post_task_list(task_cfg, task_begin_handle=None, task_end_handle=None):
    task_begin_handle = stack_context.wrap(task_begin_handle)
    task_end_handle = stack_context.wrap(task_end_handle)
    
    raw_accs_iter = get_items.get_random_infinite_items(task_cfg.accs, is_csv=True)
    title_and_content_iter = get_items.get_title_and_content(\
            get_items.get_random_infinite_items, task_cfg.titles, task_cfg.content)
    
    def next_acc():
        if 'wpapi:0' == task_cfg.acc_fmt:
            while True:
                acc_row = next(raw_accs_iter)
                
                if len(acc_row) != 5:
                    raise NotImplementedError(
                            'invalid or not implemented account format')
                
                email, email_password, blog_url, username, password = acc_row
                
                return blog_url, username, password, acc_row
        
        # if 'wpapi:...' == task_cfg.acc_fmt:
        #  ...
        #  return
        
        raise NotImplementedError('not implemented account format')
    
    for task_i in range(task_cfg.count):
        task = Task()
        
        task.i = task_i
        task.blog_url, task.username, task.password, task._acc_row = next_acc()
        task.blog_id = task.blog_url
        task.title, task.content = next(title_and_content_iter)
        task.ua_name = task_cfg.ua_name
        
        task.acc_save = lambda _task=task: wpapi_acc_save(
                task_cfg,
                _task,
                )
        
        task.task_begin_handle = task_begin_handle
        task.task_end_handle = task_end_handle
        
        yield task

@gen.engine
def wpapi_post_task(task, callback=None):
    callback = stack_context.wrap(callback)
    
    if task.task_begin_handle is not None:
        task.task_begin_handle(task)
    
    task.result, task.error = (yield gen.Task(
            wpapi_post,
            blog_url=task.blog_url,
            username=task.username,
            password=task.password,
            title=task.title,
            content=task.content,
            ua_name=task.ua_name,
            )).args
    
    if task.task_end_handle is not None:
        task.task_end_handle(task)
    
    if callback is not None:
        callback(task.error)
