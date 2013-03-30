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

_wp_acc_save_excl_list = weakref.WeakKeyDictionary()

class WpError(Exception):
    pass

class AuthWpError(WpError):
    pass

class PublishWpError(WpError):
    pass

class Task:
    pass

def wp_post_blocking(blog_url=None, username=None, password=None,
        title=None, content=None, slug=None, ua_name=None):
    assert blog_url is not None
    assert username is not None
    assert password is not None
    assert title is not None
    assert content is not None
    
    if ua_name is None:
        ua_name = urllib_request_helper.DEFAULT_USER_AGENT_NAME
    
    blog_url_parsed = url.urlparse(blog_url)
    
    assert blog_url_parsed.scheme in ('https', 'http')
    
    wp_login_url = url.urljoin(blog_url, 'wp-login.php')
    wp_admin_url = url.urljoin(blog_url, 'wp-admin/')
    wp_post_url = url.urljoin(blog_url, 'wp-admin/post-new.php')
    wp_edit_url = url.urljoin(blog_url, 'wp-admin/edit.php')
    wp_ajax_url = url.urljoin(blog_url, 'wp-admin/admin-ajax.php')
    
    cookies = cookiejar.CookieJar()
    opener = request.build_opener(
            request.HTTPCookieProcessor(cookiejar=cookies),
            )
    
    # *** PHASE: auth ***
    
    resp = urllib_request_helper.ext_open(
            opener,
            wp_login_url,
            headers=(
                    ('User-Agent', ua_name),
                    
                    # header-line for Blog.Com:
                    ('Accept',
                            'text/html,application/xhtml+xml,'
                            'application/xml;q=0.9,*/*;q=0.8'),
                    ),
            data=url.urlencode({
                    'wp-submit': 'Log In',
                    'testcookie': '1',
                    'redirect_to': wp_admin_url,
                    'pwd': password,
                    'log': username,
                    }).encode(),
            timeout=urllib_request_helper.DEFAULT_TIMEOUT,
            )
    
    if resp.getcode() != 200 or resp.geturl() != wp_admin_url:
        raise AuthWpError('wp auth error')
    
    # *** PHASE: get params ***
    
    resp = urllib_request_helper.ext_open(
            opener,
            wp_post_url,
            headers=(
                    ('User-Agent', ua_name),
                    
                    # header-line for Blog.Com:
                    ('Accept',
                            'text/html,application/xhtml+xml,'
                            'application/xml;q=0.9,*/*;q=0.8'),
                    ),
            timeout=urllib_request_helper.DEFAULT_TIMEOUT,
            )
    
    if resp.getcode() != 200 or resp.geturl() != wp_post_url:
        raise WpError('wp get params error')
    
    data = resp.read(urllib_request_helper.DEFAULT_RESPONSE_LIMIT).decode()
    
    form_html_nodes = tuple(html_parse.find_tags(
            (html_parse.html_parse(data),),
            'form',
            attrs={
                    'id': 'post',
                    'method': 'post',
                    'action': 'post.php',
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
    
    # *** PHASE: autosave ***
    
    post_data = {
            'action': 'autosave',
            'post_ID': params['post_ID'],
            'autosavenonce': params['autosavenonce'],
            'post_type': 'post',
            'autosave': '1',
            'post_title': title,
            'content': content,
            'catslist': '',
            'comment_status': 'open',
            'ping_status': 'open',
            'excerpt': '',
            'post_author': params['post_author'],
            'user_ID': params['user_ID'],
            }
    
    resp = urllib_request_helper.ext_open(
            opener,
            wp_ajax_url,
            headers=(
                    ('User-Agent', ua_name),
                    ('X-Requested-With', 'XMLHttpRequest'),
                    
                    # header-line for Blog.Com:
                    ('Accept',
                            'text/html,application/xhtml+xml,'
                            'application/xml;q=0.9,*/*;q=0.8'),
                    ),
            data=url.urlencode(post_data).encode(),
            timeout=urllib_request_helper.DEFAULT_TIMEOUT,
            )
    
    if resp.getcode() != 200 or resp.geturl() != wp_ajax_url:
        raise WpError('wp autosave error')
    
    # *** PHASE: get edit-param ***
    
    resp = urllib_request_helper.ext_open(
            opener,
            wp_edit_url,
            headers=(
                    ('User-Agent', ua_name),
                    
                    # header-line for Blog.Com:
                    ('Accept',
                            'text/html,application/xhtml+xml,'
                            'application/xml;q=0.9,*/*;q=0.8'),
                    ),
            timeout=urllib_request_helper.DEFAULT_TIMEOUT,
            )
    
    if resp.getcode() != 200 or resp.geturl() != wp_edit_url:
        raise WpError('wp get edit-param error')
    
    data = resp.read(urllib_request_helper.DEFAULT_RESPONSE_LIMIT).decode()
    
    inline_edit_param_node = next(iter(html_parse.find_tags(
            (html_parse.html_parse(data),),
            'input',
            attrs={
                    'id': '_inline_edit',
                    },
            )), None)
    assert inline_edit_param_node is not None
    
    inline_edit_param = inline_edit_param_node.attrs['value']
    
    # *** PHASE: publish ***
    
    post_data = {
            'post_title': title,
            'post_name': slug if slug is not None else '',
            #NOT_NEED#'mm': params['cur_mm'],
            #NOT_NEED#'jj': params['cur_jj'],
            #NOT_NEED#'aa': params['cur_aa'],
            #NOT_NEED#'hh': params['cur_hh'],
            #NOT_NEED#'mn': params['cur_mn'],
            #NOT_NEED#'ss': params['ss'],
            'post_author': params['post_author'],
            'post_password': '',
            'post_category[]': params['post_category[]'],
            'tax_input[post_tag]': '',
            'comment_status': 'open',
            'ping_status': 'open',
            '_status': 'publish',
            'post_format': '0',
            '_inline_edit': inline_edit_param,
            'post_view': 'list',
            'screen': 'edit-post',
            'action': 'inline-save',
            'post_type': 'post',
            'post_ID': params['post_ID'],
            #NOT_NEED#'edit_date': 'true',
            'post_status': 'all',
            }
    
    resp = urllib_request_helper.ext_open(
            opener,
            wp_ajax_url,
            headers=(
                    ('User-Agent', ua_name),
                    ('X-Requested-With', 'XMLHttpRequest'),
                    
                    # header-line for Blog.Com:
                    ('Accept',
                            'text/html,application/xhtml+xml,'
                            'application/xml;q=0.9,*/*;q=0.8'),
                    ),
            data=url.urlencode(post_data).encode(),
            timeout=urllib_request_helper.DEFAULT_TIMEOUT,
            )
    
    if resp.getcode() != 200 or resp.geturl() != wp_ajax_url:
        raise PublishWpError('wp publish error')
    
    # *** END ***
    
    page_id = int(params['post_ID'])
    
    return url.urljoin(blog_url, '?{}'.format(url.urlencode({'page_id': page_id})))

def wp_post(*args, callback=None, **kwargs):
    callback = stack_context.wrap(callback)
    
    def wp_post_thread():
        result = None
        error = None
        
        try:
            result = wp_post_blocking(*args, **kwargs)
        except Exception as e:
            error = type(e), str(e), traceback.format_exc()
        
        if callback is not None:
            ioloop.IOLoop.instance().add_callback(lambda: callback(result, error))
    
    t = threading.Thread(target=wp_post_thread)
    t.daemon = True
    t.start()

def wp_acc_save(task_cfg, task):
    fd = task_cfg.out.get_fd(ext='accs.csv')
    try:
        excl_list = _wp_acc_save_excl_list[fd]
    except KeyError:
        _wp_acc_save_excl_list[fd] = excl_list = []
    acc_row = task._acc_row
    
    if acc_row in excl_list:
        return
    
    csv_writer = csv.writer(fd)
    
    csv_writer.writerow(acc_row)
    fd.flush()
    excl_list.append(acc_row)

def get_wp_post_task_list(task_cfg, task_begin_handle=None, task_end_handle=None):
    task_begin_handle = stack_context.wrap(task_begin_handle)
    task_end_handle = stack_context.wrap(task_end_handle)
    
    raw_accs_iter = get_items.get_random_infinite_items(task_cfg.accs, is_csv=True)
    title_and_content_iter = get_items.get_title_and_content(\
            get_items.get_random_infinite_items, task_cfg.titles, task_cfg.content)
    
    def next_acc():
        if 'wp:0' == task_cfg.acc_fmt:
            while True:
                acc_row = next(raw_accs_iter)
                
                if len(acc_row) != 5:
                    raise NotImplementedError(
                            'invalid or not implemented account format')
                
                email, email_password, blog_url, username, password = acc_row
                
                return blog_url, username, password, acc_row
        
        # if 'wp:...' == task_cfg.acc_fmt:
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
        
        task.acc_save = lambda _task=task: wp_acc_save(
                task_cfg,
                _task,
                )
        
        task.task_begin_handle = task_begin_handle
        task.task_end_handle = task_end_handle
        
        yield task

@gen.engine
def wp_post_task(task, callback=None):
    callback = stack_context.wrap(callback)
    
    if task.task_begin_handle is not None:
        task.task_begin_handle(task)
    
    task.result, task.error = (yield gen.Task(
            wp_post,
            blog_url=task.blog_url,
            username=task.username,
            password=task.password,
            title=task.title,
            content=task.content,
            ua_name=task.ua_name
            )).args
    
    if task.task_end_handle is not None:
        task.task_end_handle(task)
    
    if callback is not None:
        callback(task.error)
