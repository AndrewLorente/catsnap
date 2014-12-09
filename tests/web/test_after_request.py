from __future__ import unicode_literals

from contextlib import contextmanager
from redis.exceptions import ConnectionError
from tests import TestCase
from nose.tools import eq_
from mock import Mock
import sqlalchemy.exc
from catsnap import Client
from catsnap.web import app
from catsnap.web.formatted_routes import formatted_route, abort
from catsnap.worker.web import delay
from catsnap.table.album import Album

class TestAfterRequestHandler(TestCase):
    def test_unsuccessful_responses_trigger_rollbacks(self):
        session = Client().session()
        def trigger_error(request_format):
            abort(request_format, 500, "No Mr. Bond, I expect you to die.")

        with session_cleanup():
            mock_rollback = Mock()
            session.rollback = mock_rollback
            with delay_on_request([], after=trigger_error):
                response = self.app.get('/trigger_for_test')
            eq_(response.status_code, 500)

            mock_rollback.assert_called_with()

    def test_unsuccessful_responses_prevent_sending_delayed_jobs(self):
        do_the_thing = Mock()
        def trigger_error(request_format):
            abort(request_format, 500, "Hasta la vista, baby.")

        with delay_on_request([do_the_thing], after=trigger_error):
            response = self.app.get('/trigger_for_test')
        eq_(response.status_code, 500)

        do_the_thing.delay.assert_has_calls([])

    def test_errors_attempting_to_flush_trigger_rollbacks(self):
        session = Client().session()
        with session_cleanup():
            mock_rollback = Mock()
            session.rollback = mock_rollback
            album = Album(name=None)
            session.add(album)
            with raises(sqlalchemy.exc.IntegrityError):
                self.app.get('/public/css/layout.css')

            mock_rollback.assert_called_with()

    def test_connection_errors_during_flush_do_not_trigger_rollback(self):
        session = Client().session()
        with session_cleanup():
            mock_rollback = Mock()
            mock_flush = Mock()
            session.rollback = mock_rollback
            session.flush = mock_flush
            mock_flush.side_effect = sqlalchemy.exc.DatabaseError('', [], None)
            with raises(sqlalchemy.exc.DatabaseError):
                self.app.get('/public/css/layout.css')

            mock_rollback.assert_has_calls([])

    def test_error_enqueuing_a_task_causes_rollback(self):
        session = Client().session()
        with session_cleanup():
            mock_rollback = Mock()
            session.rollback = mock_rollback

            do_the_thing = Mock()
            do_the_thing.delay.side_effect = DeliberateError(
                'You must lower me into the steel.')
            with delay_on_request([do_the_thing]):
                with raises(DeliberateError):
                    self.app.get('/trigger_for_test')

            mock_rollback.assert_called_with()

    def test_error_enqueuing_a_task_revokes_previous_tasks(self):
        enqueued = Mock()
        enqueueable = Mock()
        enqueueable.delay.return_value = enqueued
        unenqueueable = Mock()
        unenqueueable.delay.side_effect = DeliberateError(
            "I'm not sure how much longer I can hold this")

        with delay_on_request([enqueueable, unenqueueable]):
            with raises(DeliberateError):
                self.app.get('/trigger_for_test')

        enqueued.revoke.assert_called_with()

    def test_connection_errors_on_enqueue_attempt_no_further_connection(self):
        enqueued = Mock()
        enqueueable = Mock()
        enqueueable.delay.return_value = enqueued
        unenqueueable = Mock()
        unenqueueable.delay.side_effect = ConnectionError(
            "I spent the last few years building up an immunity "
            "to iocane powder.")
        with delay_on_request([enqueueable, unenqueueable]):
            with raises(ConnectionError):
                self.app.get('trigger_for_test')

        enqueued.revoke.assert_has_calls([])

    def test_errors_during_commit_cancel_delayed_tasks(self):
        session = Client().session()
        with session_cleanup():
            mock_commit = Mock()
            session.commit = mock_commit
            mock_commit.side_effect = DeliberateError(
                "I just think we should take things slow.")
            result = Mock()
            do_the_thing = Mock()
            do_the_thing.delay.return_value = result

            with delay_on_request([do_the_thing]):
                with raises(DeliberateError):
                    self.app.get('/trigger_for_test')

            mock_commit.assert_called_with()
            result.revoke.assert_called_with()

@contextmanager
def raises(exception_class):
    try:
        yield
    except exception_class:
        pass
    else:
        raise AssertionError("Expected to raise a {0}, but nothing was raised".
                             format(exception_class))

@contextmanager
def session_cleanup():
    session = Client().session()
    commit = session.commit
    rollback = session.rollback
    flush = session.flush
    try:
        yield
    finally:
        session.commit = commit
        session.rollback = rollback
        session.flush = flush

@contextmanager
def delay_on_request(tasks, after=None):
    try:
        @formatted_route('/trigger_for_test')
        def trigger_for_test(request_format):
            for task in tasks:
                delay(task)
            if after is not None:
                after(request_format)
            return ''

        yield
    finally:
        del(app.url_map._rules_by_endpoint['trigger_for_test'])

class DeliberateError(StandardError):
    pass

