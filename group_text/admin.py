from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Group, Membership, Message, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    model = User
    list_display = ("phone_number", "name", "is_staff", "is_active")
    search_fields = ("phone_number", "name")
    ordering = ("phone_number",)
    fieldsets = (
        (None, {"fields": ("phone_number", "password")}),
        ("Personal info", {"fields": ("name",)}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "phone_number",
                    "name",
                    "password1",
                    "password2",
                    "is_staff",
                    "is_superuser",
                    "is_active",
                ),
            },
        ),
    )


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("name", "created_by", "proxy_number", "created_at")
    search_fields = (
        "name",
        "proxy_number",
        "created_by__name",
        "created_by__phone_number",
    )
    ordering = ("-created_at",)
    raw_id_fields = ("created_by",)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("group", "sender", "created_at")
    search_fields = (
        "group__name",
        "sender__name",
        "sender__phone_number",
        "body",
    )
    ordering = ("-created_at",)
    raw_id_fields = ("group", "sender")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "group", "is_admin", "joined_at")
    list_filter = ("is_admin", "joined_at")
    search_fields = ("user__name", "user__phone_number", "group__name")
    ordering = ("joined_at",)
    raw_id_fields = ("user", "group")
