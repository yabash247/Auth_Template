# scrimmages/tests.py
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
from .models import Scrimmage, ScrimmageParticipation, League, LeagueTeam, PerformanceStat

User = get_user_model()

class BaseTestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="player@example.com", password="testpass123")
        self.other = User.objects.create_user(email="other@example.com", password="pass123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.scrimmage = Scrimmage.objects.create(
            title="Evening Scrimmage",
            description="Friendly match under lights",
            creator=self.user,
            start_time=timezone.now() + timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=3),
            visibility="public",
            status="published",
            max_participants=10,
        )


class ScrimmageTests(BaseTestCase):
    def test_create_scrimmage(self):
        url = reverse("scrimmages-list")
        payload = {
            "title": "Morning Game",
            "description": "Early morning practice",
            "start_time": timezone.now() + timedelta(days=1),
            "end_time": timezone.now() + timedelta(days=1, hours=2),
            "visibility": "public",
        }
        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Scrimmage.objects.count(), 2)

    def test_join_scrimmage(self):
        url = reverse("scrimmages-join", args=[self.scrimmage.id])
        res = self.client.post(url)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(
            ScrimmageParticipation.objects.filter(user=self.user, scrimmage=self.scrimmage).exists()
        )

    def test_scrimmage_full(self):
        self.scrimmage.max_participants = 1
        self.scrimmage.save()
        # Someone already joined
        ScrimmageParticipation.objects.create(user=self.other, scrimmage=self.scrimmage, status="confirmed")

        url = reverse("scrimmages-join", args=[self.scrimmage.id])
        res = self.client.post(url)
        self.assertEqual(res.status_code, 400)
        self.assertIn("full", res.data["detail"].lower())


    def test_leave_scrimmage(self):
        ScrimmageParticipation.objects.create(user=self.user, scrimmage=self.scrimmage, status="confirmed")
        url = reverse("scrimmages-leave", args=[self.scrimmage.id])
        res = self.client.post(url)
        self.assertEqual(res.status_code, 200)
        self.assertFalse(
            ScrimmageParticipation.objects.filter(user=self.user, scrimmage=self.scrimmage).exists()
        )

    def test_checkin_scrimmage(self):
        part = ScrimmageParticipation.objects.create(user=self.user, scrimmage=self.scrimmage, status="confirmed")
        url = reverse("scrimmages-checkin", args=[self.scrimmage.id])
        res = self.client.post(url)
        part.refresh_from_db()
        self.assertEqual(res.status_code, 200)
        self.assertEqual(part.status, "checked_in")

    def test_invite_player(self):
        url = reverse("scrimmages-invite", args=[self.scrimmage.id])
        payload = {"user_id": self.other.id}
        res = self.client.post(url, payload)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(
            ScrimmageParticipation.objects.filter(user=self.other, scrimmage=self.scrimmage, status="invited").exists()
        )

from datetime import date, timedelta

class LeagueTests(BaseTestCase):
    def setUp(self):
        super().setUp()  # ✅ Reuse BaseTestCase setup
        self.league = League.objects.create(
            name="Winter League",
            organizer=self.user,
            description="Competitive winter league",
            start_date=date.today(),  # ✅ required
            end_date=date.today() + timedelta(days=30),  # ✅ required
            is_active=True,
        )

    def test_create_league(self):
        url = reverse("leagues-list")
        payload = {
            "name": "Summer League",
            "description": "Fun tournament",
            "start_date": date.today().isoformat(),  # ✅ required
            "end_date": (date.today() + timedelta(days=45)).isoformat(),  # ✅ required
        }
        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertTrue(League.objects.filter(name="Summer League").exists())

    def test_add_team_to_league(self):
        url = reverse("leagues-add-team", args=[self.league.id])
        payload = {"name": "Team Alpha"}  # minimal payload
        res = self.client.post(url, payload, format="json")
        print("DEBUG Response:", res.status_code, res.data)  # 👈 Add this line
        self.assertEqual(res.status_code, 201)
        self.assertTrue(
            LeagueTeam.objects.filter(name="Team Alpha", league=self.league).exists()
        )

