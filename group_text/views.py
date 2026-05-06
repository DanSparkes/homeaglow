from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

# Demo data representative of the group_text domain (contacts & groups).
# Replace with real queryset calls once the Contact/Group models exist.
DEMO_CONTACTS = [
    {"name": "Alice Johnson", "phone": "+1 (555) 100-0001", "group": "Family"},
    {"name": "Bob Smith", "phone": "+1 (555) 200-0002", "group": "Work"},
    {"name": "Carol Williams", "phone": "+1 (555) 300-0003", "group": "Friends"},
    {"name": "David Brown", "phone": "+1 (555) 400-0004", "group": "Work"},
    {"name": "Eva Martinez", "phone": "+1 (555) 500-0005", "group": "Family"},
    {"name": "Frank Davis", "phone": "+1 (555) 600-0006", "group": "Friends"},
    {"name": "Grace Wilson", "phone": "+1 (555) 700-0007", "group": "Work"},
    {"name": "Henry Taylor", "phone": "+1 (555) 800-0008", "group": "Family"},
    {"name": "Iris Anderson", "phone": "+1 (555) 900-0009", "group": "Friends"},
    {"name": "Jack Thomas", "phone": "+1 (555) 000-0010", "group": "Work"},
]


def home_view(request: HttpRequest) -> HttpResponse:
    return render(request, "group_text/home.html")
