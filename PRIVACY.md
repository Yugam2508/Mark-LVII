# Privacy policy — JARVIS (personal fork of Mark LVII)

This is a personal assistant that runs on its owner's own computers. It has one
user: the owner. There is no JARVIS server, no account system, no analytics and no
advertising.

## What it accesses

When the owner connects Google, the app can read and act on that account's:

- **Gmail** — to list, read, draft, send and reply to email and mark it read
  (scope `gmail.modify`; it cannot permanently delete mail).
- **Google Calendar** — to list, search, create and delete events (`calendar.events`).
- **Google Tasks** — to manage the to-do list (`tasks`).
- **Google Drive** — to find and read the owner's files (`drive.readonly`), and to
  create Google Docs and add to the Docs it created itself (`drive.file`). It cannot
  change or delete files it did not create. With the same permission it keeps a
  "JARVIS Money" spreadsheet it creates itself (Google Sheets).

It does this when the owner asks, and — if the owner leaves "proactive alerts"
switched on — it also checks every few minutes for new important email, upcoming
events and to-dos that are due, so it can tell the owner about them. Sending an
email or deleting an event always needs a confirmation the owner presses on screen.

## Where the data goes

- Google sign-in tokens are stored only on the owner's computers, in
  `config/token_google.json`. Deleting that file, or removing access at
  <https://myaccount.google.com/permissions>, signs the app out.
- To answer a request, the relevant text (for example an email being read out, or
  an email it is suggesting a reply to) is sent to the AI model the owner has
  chosen — Google Gemini by default, or Anthropic's Claude (through the owner's own
  Claude account or API key) if configured — under that provider's own terms.
- If the owner sets up phone alerts, short notifications (for example "Email from
  Sarah: Project meeting?") and the replies to phone commands pass through the ntfy
  server the owner chose (ntfy.sh by default, or their own), on private topics.
- Nothing is sold, shared with anyone else, or used for advertising.
- Google user data is used only to provide these features to the owner, in line
  with the [Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy),
  including its Limited Use requirements.

## Contact

Open an issue on this repository: <https://github.com/Yugam2508/Mark-LVII/issues>
