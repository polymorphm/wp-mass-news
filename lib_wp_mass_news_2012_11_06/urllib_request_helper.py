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

import time
from http import client as http_client

DEFAULT_USER_AGENT_NAME = 'Python'
DEFAULT_TIMEOUT = 20.0
DEFAULT_RESPONSE_LIMIT = 10000000

DEFAULT_ERROR_RETRY_LIST = (
        http_client.BadStatusLine,
        )
DEFAULT_ERROR_RETRY_COUNT = 5
DEFAULT_ERROR_RETRY_DELAY = 0.5
DEFAULT_ERROR_RETRY_DELAY_MULTIPLIER = 2.0

def ext_open(opener, *args,
        headers=None, new_headers=None,
        error_retry_list=None,
        error_retry_count=None, error_retry_delay=None,
        error_retry_delay_multiplier=None,
        **kwargs):
    if headers is not None:
        spec_headers = headers
    else:
        spec_headers = opener.addheaders
    
    if new_headers is not None:
        spec_headers = list(spec_headers)
        spec_headers += new_headers
    
    if error_retry_list is None:
        error_retry_list = DEFAULT_ERROR_RETRY_LIST
    
    if error_retry_count is None:
        error_retry_count = DEFAULT_ERROR_RETRY_COUNT
    
    if error_retry_delay is None:
        error_retry_delay = DEFAULT_ERROR_RETRY_DELAY
    
    if error_retry_delay_multiplier is None:
        error_retry_delay_multiplier = DEFAULT_ERROR_RETRY_DELAY_MULTIPLIER
    
    orig_headers = opener.addheaders
    opener.addheaders = spec_headers
    try:
        while True:
            try:
                return opener.open(*args, **kwargs)
            except error_retry_list:
                if error_retry_count <= 0:
                    raise
                
                error_retry_count -= 1
                time.sleep(error_retry_delay)
                error_retry_delay *= error_retry_delay_multiplier
                
                continue
    finally:
        opener.addheaders = orig_headers
