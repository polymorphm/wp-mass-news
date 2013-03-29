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

import datetime
from tornado import ioloop, stack_context, gen
import yieldpoints

DEFAULT_CONCURRENCE = 20

@gen.engine
def task_thread(task_func, task_list,
        delay=None, error_delay=None, callback=None):
    callback = stack_context.wrap(callback)
    
    io_loop = ioloop.IOLoop.instance()
    
    for task in task_list:
        if delay is not None:
            delay_wait_key = object()
            io_loop.add_timeout(
                    datetime.timedelta(seconds=delay),
                    (yield gen.Callback(delay_wait_key)),
                    )
        
        if error_delay is not None:
            error_delay_wait_key = object()
            error_delay_id = io_loop.add_timeout(
                    datetime.timedelta(seconds=error_delay),
                    (yield gen.Callback(error_delay_wait_key)),
                    )
        
        is_error = yield gen.Task(task_func, task)
        
        if delay is not None:
            yield gen.Wait(delay_wait_key)
        
        if error_delay is not None:
            if is_error:
                yield gen.Wait(error_delay_wait_key)
            else:
                io_loop.remove_timeout(error_delay_id)
                yield yieldpoints.Cancel(error_delay_wait_key)
    
    if callback is not None:
        callback()

@gen.engine
def bulk_task(task_func, task_list, error_retry_list,
        conc=None, delay=None, error_delay=None, callback=None):
    callback = stack_context.wrap(callback)
    
    if conc is None:
        conc = DEFAULT_CONCURRENCE
    
    is_first_time = True
    while is_first_time or error_retry_list:
        if is_first_time:
            is_first_time = False
            
            task_iter = iter(task_list)
        else:
            error_retry_list_copy = error_retry_list[:]
            error_retry_list[:] = ()
            task_iter = iter(error_retry_list_copy)
        
        wait_key_list = []
        
        for thread_i in range(conc):
            wait_key = object()
            wait_key_list.append(wait_key)
            task_thread(task_func, task_iter, delay=delay, error_delay=error_delay,
                    callback=(yield gen.Callback(wait_key)))
        
        for wait_key in wait_key_list:
            yield gen.Wait(wait_key)
    
    if callback is not None:
        callback()
