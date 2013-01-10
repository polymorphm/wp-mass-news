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
import argparse
import configparser
import os, os.path
import traceback
import html
import weakref
from tornado import ioloop
from . import task, wp_post, out_mgr

DEFAULT_CONFIG_SECTION = 'wp-mass-news'
DEFAULT_TOR_PORT = 9050

class UserError(Exception):
    pass

class TaskConfig:
    pass

def task_begin_handle(task_cfg, task):
    try:
        error_counter = task_cfg.task_error_counter[task]
    except KeyError:
        error_counter = 0
    
    msg = '[{!r}/{!r}, tr{!r}] {!r}: begin'.format(
            task.i, task_cfg.count, error_counter, task.blog_id)
    
    print(msg)
    task_cfg.out.write(msg, ext='log')

def task_end_handle(task_cfg, task):
    try:
        error_counter = task_cfg.task_error_counter[task]
    except KeyError:
        error_counter = 0
    
    if task.error is not None:
        task_cfg.task_error_counter[task] = error_counter + 1
        if error_counter < task_cfg.error_retry_count:
            task_cfg.error_retry_list.append(task)
        
        e_type, e_value, e_tb = task.error
        msg = '[{!r}/{!r}, tr{!r}] {!r}: error: {!r}: {}'.format(
                task.i, task_cfg.count, error_counter, task.blog_id, e_type, e_value)
        tb_msg = '{}\n\n{}\n\n'.format(
                msg, 
                '\n'.join(map(
                        lambda s: s.rstrip(),
                        traceback.format_exception(e_type, e_value, e_tb),
                        )),
                )
        
        print(msg)
        task_cfg.out.write(msg, ext='log')
        task_cfg.out.write(msg, ext='err.log')
        task_cfg.out.write(tb_msg, ext='err-tb.log')
        
        return
    
    try:
        task_result = task.result
    except AttributeError:
        task_result = None
    
    try:
        task_title = task.title
    except AttributeError:
        task_title = None
    
    if task_result is not None:
        task_cfg.out.write(task_result)
        
        if task_title is not None:
            anc = '<a href="{}">{}</a>'.format(
                    html.escape(task_result), html.escape(task_title))
            task_cfg.out.write(anc, ext='anc.txt')
    
    try:
        acc_save = task.acc_save
    except AttributeError:
        pass
    else:
        acc_save()
    
    msg = '[{!r}/{!r}, tr{!r}] {!r}: result: {!r}'.format(
            task.i, task_cfg.count, error_counter, task.blog_id, task_result)
    
    print(msg)
    task_cfg.out.write(msg, ext='log')

def finish_handle(task_cfg):
    msg = 'done!'
    print(msg)
    task_cfg.out.write(msg, ext='log')
    
    ioloop.IOLoop.instance().stop()

def main():
    parser = argparse.ArgumentParser(
            description='utility for massive posting news to WordPress blogs.')
    parser.add_argument('cfg', metavar='CONFIG-FILE',
            help='config file for task process')
    args = parser.parse_args()
    
    cfg_dir = os.path.dirname(args.cfg)
    config = configparser.ConfigParser()
    task_cfg = TaskConfig()
    try:
        config.read(args.cfg, encoding='utf-8')
        
        task_cfg.ua_name = config.get(DEFAULT_CONFIG_SECTION, 'ua_name', fallback=None)
        
        task_cfg.use_tor = config.getboolean(DEFAULT_CONFIG_SECTION, 'use_tor', fallback=None)
        if task_cfg.use_tor is None:
            task_cfg.use_tor = False
        
        task_cfg.tor_port = config.getint(DEFAULT_CONFIG_SECTION, 'tor_port', fallback=None)
        if task_cfg.tor_port is None:
            task_cfg.tor_port = DEFAULT_TOR_PORT
        
        conc = config.getint(DEFAULT_CONFIG_SECTION, 'conc', fallback=None)
        
        delay = config.getfloat(DEFAULT_CONFIG_SECTION, 'delay', fallback=None)
        
        error_delay = config.getfloat(DEFAULT_CONFIG_SECTION, 'error_delay', fallback=None)
        
        out_file = config.get(DEFAULT_CONFIG_SECTION, 'out', fallback=None)
        if out_file is not None:
            out_file = os.path.join(cfg_dir, out_file)
        
        task_cfg.accs = os.path.join(cfg_dir, config.get(DEFAULT_CONFIG_SECTION, 'accs'))
        
        task_cfg.acc_fmt = config.get(DEFAULT_CONFIG_SECTION, 'acc_fmt')
        
        task_cfg.count = config.getint(DEFAULT_CONFIG_SECTION, 'count')
        
        task_cfg.error_retry_count = config.getint(
                DEFAULT_CONFIG_SECTION, 'error_retry_count', fallback=None)
        if task_cfg.error_retry_count is None:
            task_cfg.error_retry_count = 0
        
        if not task_cfg.acc_fmt.startswith('ff:'):
            task_cfg.titles = config.get(DEFAULT_CONFIG_SECTION, 'titles')
        else:
            task_cfg.titles = config.get(DEFAULT_CONFIG_SECTION, 'titles', fallback=None)
        
        if task_cfg.titles is not None and task_cfg.titles != '__use_first_line__':
            task_cfg.titles = os.path.join(cfg_dir, task_cfg.titles)
        
        task_cfg.tags = config.get(DEFAULT_CONFIG_SECTION, 'tags', fallback=None)
        if task_cfg.tags is not None:
            task_cfg.tags = os.path.join(cfg_dir, task_cfg.tags)
        
        task_cfg.content = os.path.join(cfg_dir, config.get(DEFAULT_CONFIG_SECTION, 'content'))
    except configparser.Error as e:
        raise UserError('config error: {}'.format(e))
    
    task_cfg.out = out_mgr.OutMgr(out_file=out_file)
    task_cfg.out.get_fd()
    task_cfg.out.get_fd(ext='log')
    task_cfg.out.get_fd(ext='anc.txt')
    task_cfg.out.get_fd(ext='err.log')
    task_cfg.out.get_fd(ext='err-tb.log')
    task_cfg.out.get_fd(ext='accs.csv')
    
    task_cfg.task_error_counter = weakref.WeakKeyDictionary()
    task_cfg.error_retry_list = []
    
    if task_cfg.use_tor:
        # TODO: this is dirty hack :-( .. need pure HTTP-over-SOCKS implementation
        
        from socks import PROXY_TYPE_SOCKS5, setdefaultproxy, wrapmodule as socks_wrap
        from http import client as http_client
        setdefaultproxy(PROXY_TYPE_SOCKS5, 'localhost', task_cfg.tor_port)
        socks_wrap(http_client)
    
    get_task_list = lambda get_task_list_func: get_task_list_func(
            task_cfg,
            task_begin_handle=lambda task: task_begin_handle(task_cfg, task),
            task_end_handle=lambda task: task_end_handle(task_cfg, task),
            )
    
    if task_cfg.acc_fmt.startswith('lj:'):
        from . import lj_post
        
        task_func = lj_post.lj_post_task
        task_list = get_task_list(lj_post.get_lj_post_task_list)
    elif task_cfg.acc_fmt.startswith('li:'):
        from . import li_post
        
        task_func = li_post.li_post_task
        task_list = get_task_list(li_post.get_li_post_task_list)
    elif task_cfg.acc_fmt.startswith('ff:'):
        from . import ff_post
        
        task_func = ff_post.ff_post_task
        task_list = get_task_list(ff_post.get_ff_post_task_list)
    else:
        task_func = wp_post.wp_post_task
        task_list = get_task_list(wp_post.get_wp_post_task_list)
    
    task.bulk_task(
            task_func,
            task_list,
            task_cfg.error_retry_list,
            conc=conc,
            delay=delay,
            error_delay=error_delay,
            callback=lambda: finish_handle(task_cfg),
            )
    
    ioloop.IOLoop.instance().start()
