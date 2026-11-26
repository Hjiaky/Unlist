# Live mailbox connection (optional)

You do not need this. [Importing a mail file](first-run.md#import-mail) finds the same Organizations, works with every provider, and needs no password. A live connection is a convenience: Unlist can rescan a mailbox for you, read replies as they arrive, and send approved requests itself.

## What it does

A live connection uses an **app password** (see below) to talk to the Subject's mail provider with two standard protocols:

**Reading (IMAP).**

- Logs in over TLS (the certificate and host name are checked).
- Opens the folder **read-only**. It never changes, moves, deletes or flags anything, and it **never marks mail as read**.
- Fetches **only the headers** of mail for discovery: who sent it, when, the subject line and the provider's authentication results. Message bodies are not fetched for discovery.
- Remembers where it stopped, so the next scan reads only new mail.
- For replies, it makes one exception: a message that looks like an answer to one of your Cases (it refers to a request Unlist sent, names a Case reference, or comes from an Organization with an open Case) is fetched **in full** and attached to that Case as evidence.
- Which folder: if the provider has an "all mail" folder, only that one is scanned (Gmail's All Mail, for example, which leaves out Spam and Trash). Otherwise the Inbox.

**Sending (SMTP).**

- Sends **only drafts you approved**, **from the Subject's own address**, through the Subject's own provider.
- Keeps the Message-ID and the full sent message as evidence on the Case.
- Does **not** copy the message into the mailbox's Sent folder. The Case holds the copy (you can download it as `.eml`).

**Contact.** Unlist talks to the mail servers only when you press a button on the connection page, or if you have switched scheduled re-scans on. Nothing else.

The app password is stored **encrypted** with the instance's [key](install.md#the-key).

## Set it up

1. Open the Subject's page, then "Live connection" (`/mail/subjects/<number>/connections/`). Each email address of the Subject is listed with its mode: *Import only* or *Live connection*.
2. Choose **Connect** for the address.
3. Pick the provider. This fills in the server names and ports and tells you where to create an app password. For another provider, enter the server values from its help pages.
4. Create an app password at the provider (next section) and enter it. The user name is usually the full email address.
5. Press **Test connection**. It only logs in to IMAP and SMTP and logs out again. Nothing is read, sent or saved.
6. Press **Save and use live**. From now on, approving a draft from this address sends it.
7. On the connection page, press **Scan now** for the first scan.

IMAP always uses TLS (port 993 by default). For sending, choose port 465 (SSL/TLS) or 587 (STARTTLS).

## App passwords

An **app password** is a separate password that a provider creates for one program. It can be revoked at any time without changing your real password. Many providers offer one only after you turn on two-factor authentication. Unlist cannot sign in with your real password where the provider requires an app password, and it does not use OAuth ("Sign in with Google").

What Unlist's built-in provider notes say, in general terms:

| Provider | App password |
|---|---|
| Gmail | Turn on 2-Step Verification, then create an app password in the Google Account settings. The option is missing for work and school accounts, for accounts protected only by security keys, and with Advanced Protection: import a Takeout file instead. |
| GMX, WEB.DE | Turn on POP3/IMAP access in the web mail settings. With two-factor authentication on, create an application-specific password in the security settings. |
| Posteo | Uses the account password for IMAP and SMTP; no separate app passwords. |
| mailbox.org | The account password, or with two-factor authentication an application password from the settings. |
| Fastmail | An app password in the settings under Privacy & Security, with access to IMAP and SMTP. |
| iCloud Mail | Turn on two-factor authentication, then create an app-specific password in the Apple Account's sign-in and security settings. |

**Warning: these provider settings are not verified.** The server names, ports and instructions in Unlist's provider list were written from the providers' help pages as remembered, and were not checked against the live services. Providers rename menus and change their rules. The list is marked as unverified in Unlist's own data file. If a value does not work, correct it in the form using your provider's current help page, and consider reporting it.

## Scheduled re-scans (optional, off by default)

On the connection page you can switch on **scheduled re-scans**. Unlist then scans that mailbox by itself, at most every **6 hours**, to find replies and new Organizations. Without it, the mailbox is scanned only when you press "Scan now". Switch it off again at any time. Scheduled re-scans only prepare things (new discoveries, replies waiting for your review). Nothing is ever sent without your approval.

## Disconnecting

On the connection page, press **Disconnect**. It deletes the stored app password and makes the address **import-only** again. Approved requests from it are then handed over for the Subject to send. Existing discoveries and Cases stay. Also revoke the app password at the provider if you no longer want it to exist.

Deleting the Subject also deletes the stored credentials. If the key is lost, saved passwords cannot be read: connect again and enter the app password again.

## Outlook.com and Microsoft 365

These generally require OAuth for IMAP, which Unlist does not use. Unlist will warn you, and a live connection is unlikely to work. Keep these mailboxes **import-only**: export the mail to mbox, import the file, and let Unlist hand over the requests for the Subject to send. See [first run](first-run.md#outlookcom-and-microsoft-365).

## If it does not work

- The connection page shows the last problem in plain words. "Test connection" runs the same check again.
- Check the app password, the server names and the ports against the provider's current help.
- Many providers need IMAP switched on in the web mail settings.
- If the provider has no app passwords, use file import. It finds the same Organizations.
