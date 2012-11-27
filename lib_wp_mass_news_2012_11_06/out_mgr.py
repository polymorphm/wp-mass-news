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

import os, os.path

DEFAULT_EXT = 'txt'

def normalize_ext(txt_file, ext=None):
    if not txt_file:
        return
    
    if ext is None:
        ext = DEFAULT_EXT
    
    if txt_file.endswith('.{}'.format(ext)):
        return txt_file
    
    return '{}.{}'.format(txt_file, ext)

def change_ext(txt_file, new_ext):
    if not txt_file:
        return
    
    return '{}.{}'.format(txt_file.rsplit('.', 1)[0], new_ext)

def rename_to_last(path):
    dirname = os.path.dirname(path)
    basename = os.path.basename(path)
    prefix = 0
    
    while True:
        prefix += 1
        new_basename = 'last-{}.{}'.format(prefix, basename)
        new_path = os.path.join(dirname, new_basename)
        
        if os.path.exists(new_path):
            continue
        
        try:
            os.rename(path, new_path)
            
            return
        except EnvironmentError:
            if os.path.exists(new_path):
                continue
            
            raise

def create_file(path):
    tempnam = os.path.join(
            os.path.dirname(path),
            'new.{}'.format(os.path.basename(path)),
            )
    
    while True:
        if os.path.exists(path):
            rename_to_last(path)
        
        try:
            open(tempnam, 'wb').close()
            os.rename(tempnam, path)
            
            break
        except EnvironmentError:
            if os.path.exists(path):
                continue
            
            raise
    
    return open(path, 'w', encoding='utf-8', newline='\n', errors='replace')

class OutMgr(object):
    def __init__(self, out_file=None, ext=None):
        if ext is not None:
            self._ext = ext
        else:
            self._ext = DEFAULT_EXT
        self._out_file = normalize_ext(out_file, self._ext)
        self._fd_map = {}
    
    def write(self, text, ext=None, end=None):
        if ext is None:
            ext = self._ext
        if end is None:
            end = '\n'
        
        out_file = self._out_file
        
        if out_file is None:
            return
        
        if ext != self._ext:
            out_file = change_ext(out_file, ext)
        
        if ext in self._fd_map:
            fd = self._fd_map[ext]
        else:
            fd = self._fd_map[ext] = create_file(out_file)
        
        fd.write('{}{}'.format(text, end))
        fd.flush()
