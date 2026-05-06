from django.contrib import admin
from django.urls import path

from group_text import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_view, name="logout"),
    path("", views.home_view, name="home"),
    path("groups/", views.group_list_view, name="group-list"),
    path("groups/create/", views.group_create_view, name="group-create"),
    path("groups/<int:group_id>/join/", views.group_join_view, name="group-join"),
    path("groups/<int:group_id>/leave/", views.group_leave_view, name="group-leave"),
    path(
        "webhooks/twilio/sms/", views.twilio_sms_webhook_view, name="twilio-sms-webhook"
    ),
]
