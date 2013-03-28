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

from __future__ import absolute_import

assert str is not bytes

import sys
import os, os.path
import csv
import itertools
import random
import re

class NotFoundError(IOError):
    pass

def file_items_open(path):
    with open(path, 'r', encoding='utf-8', newline='\n', errors='replace') \
            as fd:
        for line in fd:
            if not line:
                continue
            
            item = line.strip()
            
            if not item:
                continue
            
            yield item

def dir_items_open(path):
    for name in os.listdir(path):
        file_path = os.path.join(path, name)
        
        if not file_path.endswith('.txt'):
            continue
        
        with open(file_path, 'r', encoding='utf-8', newline='\n', errors='replace') \
                as fd:
            data = fd.read()
            
            if not data:
                continue
            
            item = data.strip()
            
            if not item:
                continue
            
            yield item

def csv_items_open(path):
    with open(path, 'r', encoding='utf-8', newline='\n', errors='replace') \
            as fd:
        csv_reader = csv.reader(fd)
        
        for csv_row in csv_reader:
            # TODO: for Python-3.3+ -- need fix to PEP-0380
            yield csv_row

def items_open(path, is_csv=None):
    if is_csv is None:
        is_csv = False
    
    if is_csv:
        if not os.path.isfile(path):
            path = '{}.csv'.format(path)
        
        return csv_items_open(path)
    
    if os.path.isdir(path):
        return dir_items_open(path)
    
    if os.path.isfile(path):
        return file_items_open(path)
    
    d_path = '{}.d'.format(path)
    txt_path = '{}.txt'.format(path)
    
    if os.path.isdir(d_path):
        return dir_items_open(d_path)
    
    if os.path.isfile(txt_path):
        return file_items_open(txt_path)
    
    raise NotFoundError('No such file or directory: ' + repr(path))

def get_finite_items(path, is_csv=None):
    return items_open(path, is_csv=is_csv)

def get_infinite_items(path, is_csv=None):
    for item in itertools.cycle(items_open(path, is_csv=is_csv)):
        # TODO: for Python-3.3+ -- need fix to PEP-0380
        yield item

def get_random_finite_items(path, is_csv=None):
    items = []
    
    for item in items_open(path, is_csv=is_csv):
        items.append(item)
    
    random.shuffle(items)
    
    for item in items:
        # TODO: for Python-3.3+ -- need fix to PEP-0380
        yield item

def get_random_infinite_items(path, is_csv=None):
    items = []
    
    for item in items_open(path, is_csv=is_csv):
        items.append(item)
    
    if not items:
        return
    
    while True:
        random.shuffle(items)
        
        for item in items:
            # TODO: for Python-3.3+ -- need fix to PEP-0380
            yield item

def clean_title(title):
    m = re.match(
            r'^\<h1\>(?P<h1>[^<>]*)\<\/h1\>$',
            title,
            re.S | re.U,
            )
    
    if m is None:
        return title
    
    h1 = m.group('h1')
    
    if h1:
        return h1
    
    return title

def split_title_and_content(items_iter):
    for item in items_iter:
        spl_item = item.lstrip().split('\n', 1)
        
        if len(spl_item) != 2:
            continue
        
        title, body = spl_item
        
        title = clean_title(title.rstrip())
        body = body.lstrip()
        
        if not title or not body:
            continue
        
        yield title, body

def get_title_and_content(get_func, title_path, content_path):
    content_iter = get_func(content_path)
    
    if title_path == '__use_first_line__':
        for title, content in split_title_and_content(content_iter):
            # TODO: for Python-3.3+ -- need fix to PEP-0380
            yield title, content
    
    title_iter = get_func(title_path)
    
    while True:
        yield next(title_iter), next(content_iter)
