# Edge1 Gmail Mail Room intake

Dormant-by-default read-only Gmail API intake. The worker requests only `https://www.googleapis.com/auth/gmail.readonly`, preserves exact raw messages and Gmail labels, excludes Trash and Drafts, retains Spam in the Mail Room Junk review path, and performs no provider mutations.

`/etc/wwcx/gmail-mail.json` contains only account names and the path to the private Google OAuth client JSON. OAuth client material and refresh tokens are never committed. Use a Google OAuth **Desktop app** client; `gmail_mail_import.py authorize --account ADDRESS` listens only on `127.0.0.1:8765`, so browser authorization can be carried over an SSH loopback tunnel without copying authorization codes or tokens into chat. The timer stays disabled until at least one account is authorized and commissioned.
