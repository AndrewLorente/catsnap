from __future__ import unicode_literals

import threading
import logging
from functools import wraps
from tests import TestCase as BaseTestCase
from werkzeug.serving import make_server
from flask import g, session, redirect
from catsnap.web import app
from nose.tools import nottest
from splinter import Browser
from splinter.exceptions import ElementDoesNotExist
from selenium.webdriver.remote.remote_connection import LOGGER

web_actors = {}


class TestCase(BaseTestCase):
    def setUp(self):
        super(TestCase, self).setUp()
        self.browser = web_actors['browser']

    def tearDown(self):
        try:
            self.visit_url('/logout')
        finally:
            super(TestCase, self).tearDown()

    def visit_url(self, path):
        self.browser.visit('http://localhost:65432' + path)


class App(object):
    def __init__(self):
        self.app = app

    def start(self):
        self.server = make_server('0.0.0.0', 65432, self.app)
        self.server.serve_forever()

    def stop(self):
        if hasattr(self, 'server'):
            self.server.shutdown()


def setUpPackage():
    test_app = App()
    thread = threading.Thread(target=test_app.start)
    thread.daemon = True
    thread.start()
    web_actors['server'] = test_app

    web_actors['browser'] = Browser()
    LOGGER.setLevel(logging.WARNING)


def tearDownPackage():
    web_actors['browser'].quit()
    web_actors['server'].stop()


@nottest
@app.route('/become_logged_in')
def become_logged_in():
    g.user = 1
    session['logged_in'] = True
    return redirect('/')

@nottest
@app.before_request
def indicate_test_server():
    g.test_server = True

@nottest
def logged_in(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        web_actors['browser'].visit('http://localhost:65432/become_logged_in')
        fn(*args, **kwargs)
    return wrapper
