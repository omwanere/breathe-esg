from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken
from datetime import timedelta
from django.utils import timezone
from esg_platform.models import Tenant, User

class AuthTests(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Demo Tenant", slug="demo")
        self.user = User.objects.create_user(username="analyst@demo.com", password="password", tenant=self.tenant)

    def test_8_1_unauthenticated_access_blocked(self):
        url = reverse('rawactivityrow-list')
        response = self.client.get(url)
        # Verify 401 Unauthorized
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data['error'], 'not_authenticated')

    def test_8_2_expired_token_rejected(self):
        # We manually construct an expired token or configure SimpleJWT to output an expired one
        # Let's generate a token and then sign it with a past expiration
        token = RefreshToken.for_user(self.user)
        # Create an expired token by setting its current time to past
        access_token = token.access_token
        access_token.set_exp(lifetime=-timedelta(days=1))
        
        url = reverse('rawactivityrow-list')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(access_token)}')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_8_3_token_refresh_works(self):
        token = RefreshToken.for_user(self.user)
        refresh_token_str = str(token)
        
        url = reverse('token_refresh')
        response = self.client.post(url, {'refresh': refresh_token_str})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
