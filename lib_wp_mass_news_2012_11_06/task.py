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

DEFAULT_CONCURRENCE = 20

@gen.engine
def task_thread(task_func, task_list, delay=None, callback=None):
    callback = stack_context.wrap(callback)
    
    for task in task_list:
        if delay is not None:
            delay_wait_key = object()
            ioloop.IOLoop.instance().add_timeout(
                    datetime.timedelta(seconds=delay),
                    (yield gen.Callback(delay_wait_key)),
                    )
        
        yield gen.Task(task_func, task)
        
        if delay is not None:
            yield gen.Wait(delay_wait_key)
    
    if callback is not None:
        callback()

@gen.engine
def bulk_task(task_func, task_list, conc=None, delay=None, callback=None):
    callback = stack_context.wrap(callback)
    
    if conc is None:
        conc = DEFAULT_CONCURRENCE
    
    task_iter = iter(task_list)
    wait_key_list = []
    
    for thread_i in range(conc):
        wait_key = object()
        wait_key_list.append(wait_key)
        task_thread(task_func, task_iter, delay=delay,
                callback=(yield gen.Callback(wait_key)))
    
    for wait_key in wait_key_list:
        yield gen.Wait(wait_key)
    
    if callback is not None:
        callback()
