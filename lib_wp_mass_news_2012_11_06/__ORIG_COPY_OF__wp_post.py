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

import sys
import os, os.path
import json
from urllib import parse as url
from http import cookiejar
from urllib import request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'wp-mass-news'))
from lib_wp_mass_news_2012_11_06 import lib_html_parse
html_parse = lib_html_parse.import_module('html_parse')

DEFAULT_TIMEOUT = 20.0
DEFAULT_RESPONSE_LIMIT = 10000000

class WpError(Exception):
    pass

class AuthWpError(WpError):
    pass

class PublishWpError(WpError):
    pass

def open_with_headers(opener, *args, headers=None, new_headers=None, **kwargs):
    if headers is not None:
        spec_headers = headers
    else:
        spec_headers = opener.addheaders
    
    if new_headers is not None:
        spec_headers = list(spec_headers)
        spec_headers += new_headers
    
    orig_headers = opener.addheaders
    opener.addheaders = spec_headers
    try:
        return opener.open(*args, **kwargs)
    finally:
        opener.addheaders = orig_headers

def wp_post(blog_url=None, username=None, password=None,
        title=None, content=None, slug=None):
    assert blog_url is not None
    assert username is not None
    assert password is not None
    assert title is not None
    assert content is not None
    
    blog_url_parsed = url.urlparse(blog_url)
    
    assert blog_url_parsed.scheme in ('https', 'http')
    
    print('\n\n\n{} PHASE init {}\n\n\n'.format('*' * 20, '*' * 20)) # TEST!!!
    
    wp_login_url = url.urljoin(blog_url, 'wp-login.php')
    wp_admin_url = url.urljoin(blog_url, 'wp-admin/')
    wp_post_url = url.urljoin(blog_url, 'wp-admin/post-new.php')
    wp_edit_url = url.urljoin(blog_url, 'wp-admin/edit.php')
    wp_ajax_url = url.urljoin(blog_url, 'wp-admin/admin-ajax.php')
    
    cookies = cookiejar.CookieJar()
    opener = request.build_opener(
            request.HTTPCookieProcessor(cookiejar=cookies),
            )
    
    print('\n\n\n{} PHASE auth {}\n\n\n'.format('*' * 20, '*' * 20)) # DEBUG!!!
    
    resp = opener.open(
            wp_login_url,
            data=url.urlencode({
                    'wp-submit': 'Log In',
                    'testcookie': '1',
                    'redirect_to': wp_admin_url,
                    'pwd': password,
                    'log': username,
                    }).encode(),
            timeout=DEFAULT_TIMEOUT,
            )
    print('resp.getcode() is {!r}'.format(resp.getcode())) # DEBUG!!!
    print('resp.geturl() is {!r}'.format(resp.geturl())) # DEBUG!!!
    
    if resp.getcode() != 200 or resp.geturl() != wp_admin_url:
        raise AuthWpError('wp auth error')
    
    print('auth ok!') # DEBUG!!!
    
    print('\n\n\n{} PHASE get params {}\n\n\n'.format('*' * 20, '*' * 20)) # DEBUG!!!
    
    resp = opener.open(
            wp_post_url,
            timeout=DEFAULT_TIMEOUT,
            )
    
    print('resp.getcode() is {!r}'.format(resp.getcode())) # DEBUG!!!
    print('resp.geturl() is {!r}'.format(resp.geturl())) # DEBUG!!!
    
    if resp.getcode() != 200 or resp.geturl() != wp_post_url:
        raise WpError('wp get params error')
    
    data = resp.read(DEFAULT_RESPONSE_LIMIT).decode()
    
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
    
    print('params is {!r}'.format(params)) # DEBUG!!!
    
    print('\n\n\n{} PHASE autosave {}\n\n\n'.format('*' * 20, '*' * 20)) # DEBUG!!!
    
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
    
    resp = open_with_headers(
            opener,
            wp_ajax_url,
            data=url.urlencode(post_data).encode(),
            timeout=DEFAULT_TIMEOUT,
            )
    print('resp.getcode() is {!r}'.format(resp.getcode())) # DEBUG!!!
    print('resp.geturl() is {!r}'.format(resp.geturl())) # DEBUG!!!
    
    if resp.getcode() != 200 or resp.geturl() != wp_ajax_url:
        raise WpError('wp autosave error')
    
    print('\n\n\n{} PHASE get edit-param {}\n\n\n'.format('*' * 20, '*' * 20)) # DEBUG!!!
    
    resp = opener.open(
            wp_edit_url,
            timeout=DEFAULT_TIMEOUT,
            )
    
    print('resp.getcode() is {!r}'.format(resp.getcode())) # DEBUG!!!
    print('resp.geturl() is {!r}'.format(resp.geturl())) # DEBUG!!!
    
    if resp.getcode() != 200 or resp.geturl() != wp_edit_url:
        raise WpError('wp get edit-param error')
    
    data = resp.read(DEFAULT_RESPONSE_LIMIT).decode()
    
    inline_edit_param_node = next(iter(html_parse.find_tags(
            (html_parse.html_parse(data),),
            'input',
            attrs={
                    'id': '_inline_edit',
                    },
            )), None)
    assert inline_edit_param_node is not None
    
    inline_edit_param = inline_edit_param_node.attrs['value']
    
    print('inline_edit_param is {!r}'.format(inline_edit_param)) # DEBUG!!!
    
    print('\n\n\n{} PHASE publish {}\n\n\n'.format('*' * 20, '*' * 20)) # DEBUG!!!
    
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
    
    resp = open_with_headers(
            opener,
            wp_ajax_url,
            data=url.urlencode(post_data).encode(),
            timeout=DEFAULT_TIMEOUT,
            )
    print('resp.getcode() is {!r}'.format(resp.getcode())) # DEBUG!!!
    print('resp.geturl() is {!r}'.format(resp.geturl())) # DEBUG!!!
    
    if resp.getcode() != 200 or resp.geturl() != wp_ajax_url:
        raise PublishWpError('wp publish error')
    
    print('\n\n\n{} END {}\n\n\n'.format('*' * 20, '*' * 20)) # DEBUG!!!

def main():
    wp_post(
            #blog_url='http://cujoyoqu.edublogs.org',
            #username='cujoyoqu',
            #password='xqwxxwri',
            
            #blog_url='http://somiflap.blog.com',
            #username='deonnexcn677@yahoo.com',
            #password='jqieeba',
            
            blog_url='https://polymorphmtest1233.wordpress.com',
            username='polymorphmtest1233',
            password='x112244',
            
            title='test subject ФИГНЯЯЯЯЯ',
            content='test\nthe text!\n\n\nпроверка! 123Ы',
            )

if __name__ == '__main__':
   main()
