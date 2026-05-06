from typing import cast

from django.contrib.auth import authenticate
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Exists, OuterRef
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from .models import Group, Membership, User
from .sms import send_welcome_sms

# ── Auth ─────────────────────────────────────────────────────────────────────


def login_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("home")
    if request.method == "POST":
        phone = request.POST.get("phone_number", "").strip()
        password = request.POST.get("password", "")
        # USERNAME_FIELD is phone_number; authenticate() maps username→phone_number
        user = authenticate(request, username=phone, password=password)
        if user is not None:
            auth_login(request, user)
            return redirect(request.GET.get("next") or "home")
        return render(
            request,
            "group_text/login.html",
            {"error": "Invalid phone number or password."},
        )
    return render(request, "group_text/login.html")


def register_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("home")
    if request.method == "POST":
        phone = request.POST.get("phone_number", "").strip()
        name = request.POST.get("name", "").strip()
        password = request.POST.get("password", "")

        error = None
        if not phone or not name or not password:
            error = "All fields are required."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        elif User.objects.filter(phone_number=phone).exists():
            error = "That phone number is already registered."

        if error:
            return render(
                request,
                "group_text/register.html",
                {"error": error, "phone": phone, "name": name},
            )

        user = User.objects.create_user(
            phone_number=phone, name=name, password=password
        )
        auth_login(request, user)
        return redirect("home")

    return render(request, "group_text/register.html")


@require_POST
def logout_view(request: HttpRequest) -> HttpResponse:
    auth_logout(request)
    return redirect("login")


# ── Home ──────────────────────────────────────────────────────────────────────


@login_required
def home_view(request: HttpRequest) -> HttpResponse:
    return render(request, "group_text/home.html")


# ── Group partials (HTMX endpoints) ──────────────────────────────────────────


@login_required
@require_GET
def group_list_view(request: HttpRequest) -> HttpResponse:
    """
    Returns the group_list partial. Called by HTMX on page load, on search
    input (with ?q=...), and on 'refresh' events after create/join/leave.
    """
    q = request.GET.get("q", "").strip()

    user = cast(User, request.user)

    groups = Group.objects.annotate(
        member_count=Count("members", distinct=True),
        # Single EXISTS subquery — one extra column, no extra round-trip
        is_member=Exists(Membership.objects.filter(group=OuterRef("pk"), user=user)),
    ).select_related("created_by")

    if q:
        groups = groups.filter(name__icontains=q)

    return render(
        request,
        "group_text/partials/group_list.html",
        {"groups": groups, "query": q},
    )


@login_required
@require_POST
def group_create_view(request: HttpRequest) -> HttpResponse:
    name = request.POST.get("name", "").strip()

    if not name:
        return HttpResponse(
            '<p class="text-red-500 text-sm">Group name is required.</p>'
        )
    if len(name) > 100:
        return HttpResponse(
            '<p class="text-red-500 text-sm">Name must be 100 characters or fewer.</p>'
        )
    if Group.objects.filter(name__iexact=name).exists():
        return HttpResponse(
            f'<p class="text-red-500 text-sm">'
            f"<strong>{name}</strong> already exists. Try a different name."
            f"</p>"
        )

    user = cast(User, request.user)
    group = Group.objects.create(name=name, created_by=user)
    Membership.objects.create(user=user, group=group, is_admin=True)

    # Empty body — the HX-Trigger header does the work: Alpine closes the modal,
    # HTMX fires 'refresh' on the group list to reload it.
    response = HttpResponse("")
    response["HX-Trigger"] = "group-created"
    return response


@login_required
@require_POST
def group_join_view(request: HttpRequest, group_id: int) -> HttpResponse:
    group = get_object_or_404(Group, id=group_id)
    user = cast(User, request.user)
    _, created = Membership.objects.get_or_create(user=user, group=group)
    if created:
        send_welcome_sms(user=user, group=group)
    member_count = group.members.count()

    response = render(
        request,
        "group_text/partials/membership_section.html",
        {"group": group, "is_member": True, "member_count": member_count},
    )
    response["HX-Trigger"] = "membership-changed"
    return response


@login_required
@require_POST
def group_leave_view(request: HttpRequest, group_id: int) -> HttpResponse:
    group = get_object_or_404(Group, id=group_id)
    user = cast(User, request.user)
    Membership.objects.filter(user=user, group=group).delete()
    member_count = group.members.count()

    response = render(
        request,
        "group_text/partials/membership_section.html",
        {"group": group, "is_member": False, "member_count": member_count},
    )
    response["HX-Trigger"] = "membership-changed"
    return response
