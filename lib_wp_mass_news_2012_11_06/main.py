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
from tornado import ioloop
from . import task, wp_post, out_mgr

DEFAULT_CONFIG_SECTION = 'wp-mass-news'

class UserError(Exception):
    pass

class TaskConfig:
    pass

def task_begin_handle(out, task):
    msg = '[{!r}] {!r}: begin'.format(task.i, task.blog_url)
    
    print(msg)
    out.write(msg, ext='log')

def task_end_handle(out, task):
    if task.error is not None:
        msg = '[{!r}] {!r}: error: {!r}: {}'.format(
                task.i, task.blog_url, task.error[0], task.error[1])
        
        print(msg)
        out.write(msg, ext='log')
        out.write(msg, ext='err.log')
        
        return
    
    out.write(task.result)
    
    msg = '[{!r}] {!r}: result: {!r}'.format(
            task.i, task.blog_url, task.result)
    
    print(msg)
    out.write(msg, ext='log')

def finish_handle(out):
    msg = 'done!'
    print(msg)
    out.write(msg, ext='log')
    
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
        task_cfg.content = os.path.join(cfg_dir, config.get(DEFAULT_CONFIG_SECTION, 'content'))
    except configparser.Error as e:
        raise UserError('config error: {}'.format(e))
    
    out = out_mgr.OutMgr(out_file=out_file)
    
    task.bulk_task(
            wp_post.wp_post_task,
            wp_post.get_wp_post_task_list(
                    task_cfg,
                    task_begin_handle=lambda task: task_begin_handle(out, task),
                    task_end_handle=lambda task: task_end_handle(out, task),
                    ),
            conc=conc,
            callback=lambda: finish_handle(out),
            )
    
    ioloop.IOLoop.instance().start()
