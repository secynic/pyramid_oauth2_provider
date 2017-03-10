#
# Copyright (c) Elliot Peele <elliot@bentlogic.net>
#
# This program is distributed under the terms of the MIT License as found
# in a file called LICENSE. If it is not present, the license
# is always available at http://www.opensource.org/licenses/mit-license.php.
#
# This program is distributed in the hope that it will be useful, but
# without any warrenty; without even the implied warranty of merchantability
# or fitness for a particular purpose. See the MIT License for full details.
#

import base64
import unittest
import transaction
from six.moves.urllib.parse import urlparse
from six.moves.urllib.parse import parse_qsl

from sqlalchemy import create_engine

from zope.interface import implementer

from pyramid import testing
from pyramid.response import Response

from . import jsonerrors
from .views import oauth2_token
from .views import oauth2_authorize
from .models import DBSession
from .models import Oauth2Token
from .models import Oauth2Client
from .models import Oauth2Code
from .models import Oauth2RedirectUri
from .models import initialize_sql
from .interfaces import IAuthCheck

_auth_value = None
_redirect_uri = None


@implementer(IAuthCheck)
class AuthCheck(object):
    def checkauth(self, username, password):
        return _auth_value


class TestCase(unittest.TestCase):
    def setUp(self):
        self.config = testing.setUp()
        self.config.registry.registerUtility(AuthCheck, IAuthCheck)

        engine = create_engine('sqlite://')
        initialize_sql(engine, self.config)

        self.auth = 1

        self.redirect_uri = u'http://localhost'

    def _get_auth(self):
        global _auth_value
        return _auth_value

    def _set_auth(self, value):
        global _auth_value
        _auth_value = value

    auth = property(_get_auth, _set_auth)

    def _get_redirect_uri(self):
        global _redirect_uri
        return _redirect_uri

    def _set_redirect_uri(self, uri):
        global _redirect_uri
        _redirect_uri = uri

    redirect_uri = property(_get_redirect_uri, _set_redirect_uri)

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def getAuthHeader(self, username, password, scheme='Basic'):
        encoded = base64.b64encode(('%s:%s' % (username, password)
                                    ).encode('utf-8'))
        return {'Authorization': '%s %s' % (scheme, encoded.decode('utf-8'))}


class TestAuthorizeEndpoint(TestCase):
    def setUp(self):
        TestCase.setUp(self)
        self.client = self._create_client()
        self.request = self._create_request()
        self.config.testing_securitypolicy(self.auth)

    def tearDown(self):
        TestCase.tearDown(self)
        self.client = None
        self.request = None

    def _create_client(self):
        with transaction.manager:
            client = Oauth2Client()
            DBSession.add(client)
            client_id = client.client_id

            redirect_uri = Oauth2RedirectUri(client, self.redirect_uri)
            DBSession.add(redirect_uri)

        client = DBSession.query(Oauth2Client).filter_by(client_id=client_id
                                                         ).first()
        return client

    def _create_request(self):
        data = {
            'response_type': 'code',
            'client_id': self.client.client_id
        }

        request = testing.DummyRequest(params=data)
        request.scheme = 'https'

        return request

    def _create_implicit_request(self):
        data = {
            'response_type': 'token',
            'client_id': self.client.client_id
        }

        request = testing.DummyRequest(post=data)
        request.scheme = 'https'

        return request

    def _process_view(self):
        with transaction.manager:
            token = oauth2_authorize(self.request)
        return token

    def _validate_authcode_response(self, response):
        self.assertTrue(isinstance(response, Response))
        self.assertEqual(response.status_int, 302)

        redirect = urlparse(self.redirect_uri)
        location = urlparse(response.location)
        self.assertEqual(location.scheme, redirect.scheme)
        self.assertEqual(location.hostname, redirect.hostname)
        self.assertEqual(location.path, redirect.path)
        self.assertFalse(location.fragment)

        params = dict(parse_qsl(location.query))

        self.assertTrue('code' in params)

        dbauthcodes = DBSession.query(Oauth2Code).filter_by(
            authcode=params.get('code')).all()

        self.assertTrue(len(dbauthcodes) == 1)

    def testAuthCodeRequest(self):
        response = self._process_view()
        self._validate_authcode_response(response)

    def testInvalidScheme(self):
        self.request.scheme = 'http'
        response = self._process_view()
        self.assertTrue(isinstance(response, jsonerrors.HTTPBadRequest))

    def testDisableSchemeCheck(self):
        self.request.scheme = 'http'
        self.config.get_settings()['oauth2_provider.require_ssl'] = False
        response = self._process_view()
        self._validate_authcode_response(response)

    def testNoClientCreds(self):
        self.request.params.pop('client_id')
        response = self._process_view()
        self.assertTrue(isinstance(response, jsonerrors.HTTPBadRequest))

    def testNoResponseType(self):
        self.request.params.pop('response_type')
        response = self._process_view()
        self.assertTrue(isinstance(response, jsonerrors.HTTPBadRequest))

    def testRedirectUriSupplied(self):
        self.request.params['redirect_uri'] = self.redirect_uri
        response = self._process_view()
        self._validate_authcode_response(response)

    def testMultipleRedirectUrisUnspecified(self):
        with transaction.manager:
            redirect_uri = Oauth2RedirectUri(
                self.client, 'https://otherhost.com')
            DBSession.add(redirect_uri)
        response = self._process_view()
        self.assertTrue(isinstance(response, jsonerrors.HTTPBadRequest))

    def testMultipleRedirectUrisSpecified(self):
        with transaction.manager:
            redirect_uri = Oauth2RedirectUri(
                self.client, 'https://otherhost.com')
            DBSession.add(redirect_uri)
        self.request.params['redirect_uri'] = u'https://otherhost.com'
        self.redirect_uri = u'https://otherhost.com'
        response = self._process_view()
        self._validate_authcode_response(response)

    def testRetainRedirectQueryComponent(self):
        uri = 'https://otherhost.com/and/path?some=value'
        with transaction.manager:
            redirect_uri = Oauth2RedirectUri(
                self.client, uri)
            DBSession.add(redirect_uri)
        self.request.params['redirect_uri'] = uri
        self.redirect_uri = uri
        response = self._process_view()
        self._validate_authcode_response(response)

        parts = urlparse(response.location)
        params = dict(parse_qsl(parts.query))

        self.assertTrue('some' in params)
        self.assertEqual(params['some'], 'value')

    def testState(self):
        state_value = 'testing'
        self.request.params['state'] = state_value
        response = self._process_view()
        self._validate_authcode_response(response)
        parts = urlparse(response.location)
        params = dict(parse_qsl(parts.query))
        self.assertTrue('state' in params)
        self.assertEqual(state_value, params['state'])


class TestTokenEndpoint(TestCase):
    def setUp(self):
        TestCase.setUp(self)
        self.client, self.client_secret = self._create_client()
        self.request = self._create_request()

    def tearDown(self):
        TestCase.tearDown(self)
        self.client = None
        self.request = None

    def _create_client(self):
        with transaction.manager:
            client = Oauth2Client()
            client_secret = client.new_client_secret()
            DBSession.add(client)
            client_id = client.client_id

        client = DBSession.query(Oauth2Client).filter_by(
            client_id=client_id).first()
        return client, client_secret

    def _create_request(self):
        headers = self.getAuthHeader(
            self.client.client_id,
            self.client_secret)

        data = {
            'grant_type': 'password',
            'username': 'john',
            'password': 'foo',
        }

        request = testing.DummyRequest(post=data, headers=headers)
        request.scheme = 'https'

        return request

    def _create_refresh_token_request(self, refresh_token, user_id):
        headers = self.getAuthHeader(
            self.client.client_id,
            self.client_secret)

        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'user_id': str(user_id),
        }

        request = testing.DummyRequest(post=data, headers=headers)
        request.scheme = 'https'

        return request

    def _process_view(self):
        with transaction.manager:
            token = oauth2_token(self.request)
        return token

    def _validate_token(self, token):
        self.assertTrue(isinstance(token, dict))
        self.assertEqual(token.get('user_id'), self.auth)
        self.assertEqual(token.get('expires_in'), 3600)
        self.assertEqual(token.get('token_type'), 'bearer')
        self.assertEqual(len(token.get('access_token')), 64)
        self.assertEqual(len(token.get('refresh_token')), 64)
        self.assertEqual(len(token), 5)

        dbtoken = DBSession.query(Oauth2Token).filter_by(
            access_token=token.get('access_token')).first()

        self.assertEqual(dbtoken.user_id, token.get('user_id'))
        self.assertEqual(dbtoken.expires_in, token.get('expires_in'))
        self.assertEqual(dbtoken.access_token, token.get('access_token'))
        self.assertEqual(dbtoken.refresh_token, token.get('refresh_token'))

    def testTokenRequest(self):
        self.auth = 500
        token = self._process_view()
        self._validate_token(token)

    def testInvalidMethod(self):
        self.request.method = 'GET'
        token = self._process_view()
        self.assertTrue(isinstance(token, jsonerrors.HTTPMethodNotAllowed))

    def testInvalidScheme(self):
        self.request.scheme = 'http'
        token = self._process_view()
        self.assertTrue(isinstance(token, jsonerrors.HTTPBadRequest))

    def testDisableSchemeCheck(self):
        self.request.scheme = 'http'
        self.config.get_settings()['oauth2_provider.require_ssl'] = False
        token = self._process_view()
        self._validate_token(token)

    def testNoClientCreds(self):
        self.request.headers = {}
        token = self._process_view()
        self.assertTrue(isinstance(token, jsonerrors.HTTPUnauthorized))

    def testInvalidClientCreds(self):
        self.request.headers = self.getAuthHeader(
            self.client.client_id, 'abcde')
        token = self._process_view()
        self.assertTrue(isinstance(token, jsonerrors.HTTPBadRequest))

    def testInvalidGrantType(self):
        self.request.POST['grant_type'] = 'foo'
        token = self._process_view()
        self.assertTrue(isinstance(token, jsonerrors.HTTPBadRequest))

    def testCacheHeaders(self):
        self._process_view()
        self.assertEqual(
            self.request.response.headers.get('Cache-Control'), 'no-store')
        self.assertEqual(
            self.request.response.headers.get('Pragma'), 'no-cache')

    def testMissingUsername(self):
        self.request.POST.pop('username')
        token = self._process_view()
        self.assertTrue(isinstance(token, jsonerrors.HTTPBadRequest))

    def testMissingPassword(self):
        self.request.POST.pop('password')
        token = self._process_view()
        self.assertTrue(isinstance(token, jsonerrors.HTTPBadRequest))

    def testFailedPassword(self):
        self.auth = False
        token = self._process_view()
        self.assertTrue(isinstance(token, jsonerrors.HTTPUnauthorized))

    def testRefreshToken(self):
        token = self._process_view()
        self._validate_token(token)
        self.request = self._create_refresh_token_request(
            token.get('refresh_token'), token.get('user_id'))
        token = self._process_view()
        self._validate_token(token)

    def testMissingRefreshToken(self):
        token = self._process_view()
        self._validate_token(token)
        self.request = self._create_refresh_token_request(
            token.get('refresh_token'), token.get('user_id'))
        self.request.POST.pop('refresh_token')
        token = self._process_view()
        self.assertTrue(isinstance(token, jsonerrors.HTTPBadRequest))

    def testMissingUserId(self):
        token = self._process_view()
        self._validate_token(token)
        self.request = self._create_refresh_token_request(
            token.get('refresh_token'), token.get('user_id'))
        self.request.POST.pop('user_id')
        token = self._process_view()
        self.assertTrue(isinstance(token, jsonerrors.HTTPBadRequest))

    def testInvalidRefreshToken(self):
        token = self._process_view()
        self._validate_token(token)
        self.request = self._create_refresh_token_request(
            'abcd', token.get('user_id'))
        token = self._process_view()
        self.assertTrue(isinstance(token, jsonerrors.HTTPUnauthorized))

    def testRefreshInvalidClientId(self):
        token = self._process_view()
        self._validate_token(token)
        self.request = self._create_refresh_token_request(
            token.get('refresh_token'), token.get('user_id'))
        self.request.headers = self.getAuthHeader(
            '1234', self.client_secret)
        token = self._process_view()
        self.assertTrue(isinstance(token, jsonerrors.HTTPBadRequest))

    def testUserIdMissmatch(self):
        token = self._process_view()
        self._validate_token(token)
        self.request = self._create_refresh_token_request(
            token.get('refresh_token'), '2')
        token = self._process_view()
        self.assertTrue(isinstance(token, jsonerrors.HTTPBadRequest))

    def testRevokedAccessTokenRefresh(self):
        token = self._process_view()
        self._validate_token(token)

        dbtoken = DBSession.query(Oauth2Token).filter_by(
            access_token=token.get('access_token')).first()
        dbtoken.revoke()

        self.request = self._create_refresh_token_request(
            token.get('refresh_token'), token.get('user_id'))
        token = self._process_view()
        self._validate_token(token)

    def testTimeRevokeAccessToken(self):
        token = self._process_view()
        self._validate_token(token)

        dbtoken = DBSession.query(Oauth2Token).filter_by(
            access_token=token.get('access_token')).first()
        dbtoken.expires_in = 0

        self.assertEqual(dbtoken.isRevoked(), True)

    def testTimeRevokeAccessToken2(self):
        token = self._process_view()
        self._validate_token(token)

        dbtoken = DBSession.query(Oauth2Token).filter_by(
            access_token=token.get('access_token')).first()
        dbtoken.expires_in = 10

        self.assertEqual(dbtoken.isRevoked(), False)
