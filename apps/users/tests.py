from django.conf import settings
from django.test import Client
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.models import User

from l10n.urlresolvers import reverse
from drumbeat.utils import get_partition_id
from users.models import UserProfile, create_profile

from test_utils import TestCase


class TestLogins(TestCase):

    test_username = 'testuser'
    test_password = 'testpassword'
    test_email = 'test@mozillafoundation.org'

    def setUp(self):
        self.locale = 'en'
        self.client = Client()
        django_user = User(username=self.test_username,
                           email=self.test_email)
        self.user = create_profile(django_user)
        self.user.set_password(self.test_password)
        self.user.save()
        self.old_recaptcha_pubkey = settings.RECAPTCHA_PUBLIC_KEY
        self.old_recaptcha_privkey = settings.RECAPTCHA_PRIVATE_KEY
        settings.RECAPTCHA_PUBLIC_KEY, settings.RECAPTCHA_PRIVATE_KEY = '', ''
        
    def tearDown(self):
        settings.RECAPTCHA_PUBLIC_KEY = self.old_recaptcha_pubkey
        settings.RECAPTCHA_PRIVATE_KEY = self.old_recaptcha_privkey

    def test_authenticated_redirects(self):
        """Test that authenticated users are redirected in specific views."""
        self.client.login(username=self.test_username,
                          password=self.test_password)
        paths = ('login/', 'register/',
                 'confirm/123456/username/',
                 'confirm/resend/username/')
        for path in paths:
            full = "/%s/%s" % (self.locale, path)
            response = self.client.get(full)
            print response
            self.assertRedirects(response, '/', status_code=302,
                                 target_status_code=301)
        self.client.logout()

    def test_unauthenticated_redirects(self):
        """Test that anonymous users are redirected for specific views."""
        paths = ('logout/', 'profile/edit/', 'profile/edit/image/')
        for path in paths:
            full = "/%s/%s" % (self.locale, path)
            response = self.client.get(full)
            from django.conf import settings
            expected = "%s?next=/%s/%s" % (settings.LOGIN_URL, self.locale, path)
            self.assertRedirects(response, expected, status_code=302,
                                 target_status_code=301)

    def test_login_post(self):
        """Test logging in."""
        path = "/%s/login/" % (self.locale,)
        response = self.client.post(path, {
            'username': self.test_username,
            'password': self.test_password,
        })
        self.assertRedirects(response, '/', status_code=302,
                             target_status_code=301)
        # TODO - Improve this so it doesn't take so many redirects to get a 200
        response2 = self.client.get(response["location"])
        response3 = self.client.get(response2["location"])
        self.assertContains(response3, 'id="dashboard"')
        self.client.logout()

        response5 = self.client.post(path, {
            'username': 'nonexistant',
            'password': 'password',
        })
        self.assertContains(response5, 'id="id_username"')

    def test_login_redirect_param(self):
        """Test that user is redirected properly after logging in."""
        path = "/%s/login/?%s=/%s/profile/edit/" % (
            self.locale, REDIRECT_FIELD_NAME, self.locale)
        response = self.client.post(path, {
            'username': self.test_username,
            'password': self.test_password,
        })
        self.assertEqual(
            "http://testserver/%s/profile/edit/" % (self.locale,),
            response["location"],
        )

    def test_login_redirect_param_header_injection(self):
        """
        Test that we can't inject headers into response with redirect param.
        """
        path = "/%s/login/" % (self.locale,)
        redirect_param = "foo\r\nLocation: http://example.com"
        response = self.client.post(path + "?%s=%s" % (
            REDIRECT_FIELD_NAME, redirect_param), {
            'username': self.test_username,
            'password': self.test_password,
        })
        self.assertNotEqual('http://example.com', response['location'])

    def test_redirect_param_outside_site(self):
        """
        Test that redirect parameter cannot be used as an open redirector.
        """
        path = "/%s/login/" % (self.locale,)
        redirect_param = "http://www.mozilla.org/"
        response = self.client.post(path + "?%s=%s" % (
            REDIRECT_FIELD_NAME, redirect_param), {
            'username': self.test_username,
            'password': self.test_password,
        })
        self.assertNotEqual('http://www.mozilla.org/', response['location'])

    def test_profile_image_directories(self):
        """Test that we partition image directories properly."""
        for i in range(1, 1001):
            p_id = get_partition_id(i)
            self.assertEqual(1, p_id)
        for i in range(1001, 2001):
            p_id = get_partition_id(i)
            self.assertEqual(2, p_id)
        for i in range(10001, 11001):
            p_id = get_partition_id(i)
            self.assertEqual(11, p_id)
        self.assertEqual(12, get_partition_id(11002))

    def test_protected_usernames(self):
        """
        Ensure that users cannot register using usernames that would conflict
        with other urlpatterns.
        """
        path = reverse('users_register')
        bad = ('groups', 'admin', 'people', 'events')
        for username in bad:
            response = self.client.post(path, {
                'username': username,
                'password': 'foobar123',
                'password_confirm': 'foobar123',
                'email': 'foobar123@example.com',
            })
            self.assertContains(response, 'Please choose another')
        ok = self.client.post(path, {
            'username': 'iamtrulyunique',
            'password': 'foobar123',
            'password_confirm': 'foobar123',
            'email': 'foobar123@example.com',
        })
        self.assertEqual(302, ok.status_code)

    def test_check_username_uniqueness(self):
        path = "/ajax/check_username/"
        existing = self.client.get(path, {
            'username': self.test_username,
        })
        self.assertEqual(200, existing.status_code)
        notfound = self.client.get(path, {
            'username': 'butterfly',
        })
        self.assertEqual(404, notfound.status_code)
