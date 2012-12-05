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
from tornado import ioloop
from . import task, wp_post, out_mgr

DEFAULT_CONFIG_SECTION = 'wp-mass-news'

class UserError(Exception):
    pass

class TaskConfig:
    pass

def task_begin_handle(task_cfg, task):
    msg = '[{!r}/{!r}] {!r}: begin'.format(task.i, task_cfg.count, task.blog_id)
    
    print(msg)
    task_cfg.out.write(msg, ext='log')

def task_end_handle(task_cfg, task):
    if task.error is not None:
        e_type, e_value, e_tb = task.error
        msg = '[{!r}/{!r}] {!r}: error: {!r}: {}'.format(
                task.i, task_cfg.count, task.blog_id, e_type, e_value)
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
    
    anc = '<a href="{}">{}</a>'.format(
            html.escape(task.result), html.escape(task.title))
    
    task_cfg.out.write(task.result)
    task_cfg.out.write(anc, ext='anc.txt')
    
    try:
        acc_save = task.acc_save
    except AttributeError:
        pass
    else:
        acc_save()
    
    msg = '[{!r}/{!r}] {!r}: result: {!r}'.format(
            task.i, task_cfg.count, task.blog_id, task.result)
    
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
        
        task_cfg.ua_name = config.get(DEFAULT_CONFIG_SECTION, 'ua-name', fallback=None)
        
        task_cfg.use_tor = config.getboolean(DEFAULT_CONFIG_SECTION, 'use_tor', fallback=None)
        if task_cfg.use_tor is None:
            task_cfg.use_tor == False
        conc = config.getint(DEFAULT_CONFIG_SECTION, 'conc', fallback=None)
        
        out_file = config.get(DEFAULT_CONFIG_SECTION, 'out', fallback=None)
        if out_file is not None:
            out_file = os.path.join(cfg_dir, out_file)
        
        task_cfg.accs = os.path.join(cfg_dir, config.get(DEFAULT_CONFIG_SECTION, 'accs'))
        
        task_cfg.acc_fmt = config.get(DEFAULT_CONFIG_SECTION, 'acc-fmt')
        
        task_cfg.count = config.getint(DEFAULT_CONFIG_SECTION, 'count')
        
        task_cfg.titles = config.get(DEFAULT_CONFIG_SECTION, 'titles')
        if task_cfg.titles != '__use_first_line__':
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
    
    if task_cfg.use_tor:
        # TODO: this is dirty hack :-( .. need pure HTTP-over-SOCKS implementation
        
        from socks import PROXY_TYPE_SOCKS5, setdefaultproxy, wrapmodule as socks_wrap
        from http import client as http_client
        setdefaultproxy(PROXY_TYPE_SOCKS5, 'localhost', 9050)
        socks_wrap(http_client)
    
    get_task_list = lambda get_task_list_func: get_task_list_func(
            task_cfg,
            task_begin_handle=lambda task: task_begin_handle(task_cfg, task),
            task_end_handle=lambda task: task_end_handle(task_cfg, task),
            )
    
    if task_cfg.acc_fmt.startswith('lj-'):
        from . import lj_post
        
        task_func = lj_post.lj_post_task
        task_list = get_task_list(lj_post.get_lj_post_task_list)
    else:
        task_func = wp_post.wp_post_task
        task_list = get_task_list(wp_post.get_wp_post_task_list)
    
    task.bulk_task(
            task_func,
            task_list,
            conc=conc,
            callback=lambda: finish_handle(task_cfg),
            )
    
    ioloop.IOLoop.instance().start()
