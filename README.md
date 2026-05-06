# homeaglow

Technical Decisions:

I've decided to go with Django for this group SMS app. Its "batteries-included" setup handles the heavy lifting on security and speed. Using ORM manages the many-to-many relationships between users and group chats, keeping message routing fast and accurate even when users are bouncing between a bunch of different threads.

Since this is SMS based, I wanted to move from the standard username login, so people can use their phone number as the username. It fits perfectly with the metadata coming in from every text.

| Feature | Django (Selected) | FastAPI / Flask |
| --- | --- | --- |
| Authentication | Built-in, easily customizable for phone numbers. | Requires external libraries (e.g., OAuth2). |
| Admin Interface | Automatic, robust CRUD for group management. | None; requires manual build or third-party tools. |
| ORM Capability | Sophisticated, handles complex M2M relationships natively. | SQLAlchemy is powerful but requires more boilerplate. |
| HTMX Integration | Seamless through template partials and django-htmx. | Possible, but requires more manual template management. |
| Security | Comprehensive CSRF and SQL injection protection by default. | Requires manual middleware configuration. |
