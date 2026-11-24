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
  change or delete files it did not create.

It does this only when the owner asks it to. Sending an email or deleting an event
needs a confirmation the owner presses on screen.

## Where the data goes

- Google sign-in tokens are stored only on the owner's computers, in
  `config/token_google.json`. Deleting that file, or removing access at
  <https://myaccount.google.com/permissions>, signs the app out.
- To answer a request, the relevant text (for example an email being read out) is
  sent to the AI model the owner has chosen — Google Gemini by default, or
  Anthropic's Claude if configured — under that provider's own terms.
- Nothing is sold, shared with anyone else, or used for advertising.
- Google user data is used only to provide these features to the owner, in line
  with the [Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy),
  including its Limited Use requirements.

## Contact

Open an issue on this repository: <https://github.com/Yugam2508/Mark-LVII/issues>
