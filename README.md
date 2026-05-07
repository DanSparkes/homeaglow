# homeaglow

## Project Setup

### Twilio setup

Add the following variables to the root `.env` file before sending real SMS messages:

- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN` — used for both outbound sending **and** inbound webhook signature verification. If you rotate this token, update it in one place and both paths stay secure.
- `TWILIO_PHONE_NUMBER` — the fallback sender number used when a group has no dedicated proxy number assigned.

When a user joins a group for the first time, the app sends a welcome SMS through the configured Twilio number. Repeat joins stay idempotent and do not send duplicate welcome texts.

### Webhook configuration

To receive inbound SMS messages and fan them out to group members, configure Twilio to POST to your server:

1. In the [Twilio Console](https://console.twilio.com), go to **Phone Numbers → Manage → Active Numbers**.
2. Select the number you want to use and set **A message comes in** → **Webhook** to:
   ```
   https://your-domain.com/webhooks/twilio/sms/
   ```
3. Set the HTTP method to **HTTP POST**.

The endpoint verifies the `X-Twilio-Signature` header on every request using `TWILIO_AUTH_TOKEN`. Requests with an invalid or missing signature are rejected with a 403.

> **Proxy numbers per group:** Each `Group` has an optional `proxy_number` field. When set, inbound messages to that number are routed to that specific group and fan-out replies come from the same number. Groups without a proxy number fall back to `TWILIO_PHONE_NUMBER` for outbound, but inbound routing will not work — the webhook resolves the group by matching `To` against `proxy_number`. Assign unique numbers to each group via the Django admin or a migration.

### Running Django Project
```
docker compose up -d

docker compose exec web python manage.py migrate
```

`http://localhost:8000/register/` will bring you to account setup


## Technical Decisions:

I've decided to go with Django for this group SMS app. Its "batteries-included" setup handles the heavy lifting on security and speed. Using ORM manages the many-to-many relationships between users and group chats, keeping message routing fast and accurate even when users are bouncing between a bunch of different threads.

Since this is SMS based, I wanted to move from the standard username login, so people can use their phone number as the username. It fits perfectly with the metadata coming in from every text.

| Feature | Django (Selected) | FastAPI / Flask |
| --- | --- | --- |
| Authentication | Built-in, easily customizable for phone numbers. | Requires external libraries (e.g., OAuth2). |
| Admin Interface | Automatic, robust CRUD for group management. | None; requires manual build or third-party tools. |
| ORM Capability | Sophisticated, handles complex M2M relationships natively. | SQLAlchemy is powerful but requires more boilerplate. |
| HTMX Integration | Seamless through template partials and django-htmx. | Possible, but requires more manual template management. |
| Security | Comprehensive CSRF and SQL injection protection by default. | Requires manual middleware configuration. |

For this proof of concept, I went with HTMX and Alpine.js instead of a heavy SPA. It kept things lean by letting me skip the overhead of managing a separate JSON API and a complex JavaScript build pipeline. Since the backend handles the UI state through server-side rendering, I could ship the core features without the boilerplate of a full frontend framework.

While this setup is perfect for speed and simplicity right now, the plan for an enterprise-scale version is to split the frontend into its own dedicated project. Decoupling would allow for more specialized scaling, better team autonomy, and a more robust interface once the initial concept is proven.

## Known limitations

### Synchronous fan-out blocks the request
Every Twilio API call in the fan-out loop is made inline inside the Django request/response cycle. On a large group this means the HTTP request takes N × (Twilio round-trip) to complete. For inbound webhooks specifically, Twilio expects a response within 15 seconds — if fan-out takes longer it will retry the webhook, causing duplicate messages to be persisted and resent. The fix is a Celery task queue so the webhook returns immediately and delivery runs in the background.

### No webhook idempotency
Twilio retries webhooks on timeout or network error. Because there is no deduplication check (e.g. storing and checking the Twilio `MessageSid` before processing), a retried request will create a duplicate `Message` row and trigger a second fan-out. Adding a `twilio_sid` unique field to the `Message` model and checking for it before persisting would fix this.

### `proxy_number` has no uniqueness constraint
The database does not enforce that two groups cannot share the same proxy number. If they do, inbound routing resolves to whichever group `filter().first()` returns, silently dropping messages intended for the other. A `unique=True` constraint on `Group.proxy_number` (with `blank=True` preserved) would prevent this at the database level.

### No rate limiting on the web send endpoint
An authenticated group member can POST unlimited messages from the dashboard. Each POST triggers a synchronous fan-out of N Twilio API calls. There is no per-user or per-group rate limit, which could exhaust the Twilio account balance or hit Twilio's API rate limits under load.

### SMS body length
Twilio splits messages longer than 160 characters into multipart SMS, billed as multiple segments. Prepending the sender's name (e.g. `"Primary User: "`) eats into that budget. Long messages sent from the dashboard are not truncated or warned about.

### No phone number format validation at registration
Users can register with any string as their phone number. Twilio validates the format at send time and rejects malformed numbers silently (the error is logged server-side but the sender receives no feedback). Adding E.164 format validation at registration (e.g. via a regex or the `phonenumbers` library) would catch bad numbers before they reach Twilio.
