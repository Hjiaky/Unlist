# First run

This page takes you from a freshly started Unlist to your first requests, the replies that come back, and the follow-up. Page names and button labels may differ a little from what is written here; this guide describes pages by what they are for.

**The loop in one line:** import mail, discover Organizations, send requests, track each Case, re-check.

The words used here are the ones in the app. An **Operator** is you. A **Subject** is a person whose data you want removed. An **Organization** is any company that may hold a Subject's data. A **Case** is everything Unlist does for one Subject at one Organization. A **Broker** is an Organization that collects and sells or publishes personal data. A **Listing** is an Organization's record about a Subject.

## Create the Operator

Open Unlist in your browser. Until an Operator exists, every page sends you to the setup page (`/setup/`).

Choose a user name and a password of at least 12 characters. This is the one login of the instance. Write the user name down: you need it if you ever [change the password](install.md#changing-the-operator-password).

There is only ever one Operator. Unlist does not hide one Subject's data from the Operator, so the people you act for must trust you with it.

## Add a Subject

In the sidebar choose "Add a Subject" (the page is at `/subjects/add/`). Enter:

- **Name**, as Organizations know the person.
- **Country of residence.** It decides which Supervisory Authority (the data protection regulator) a Complaint would go to.
- **An email address.** More can be added later. Unlist matches mail by address.
- **Year of birth** (optional). Needed only to recognise children.
- **Who holds parental responsibility** (for a child).

On the Subject's page you can then add **identifying details** that Organizations often ask for: customer numbers (with the Organization's name), previous addresses, a date of birth. Unlist puts into a request only the details that Organization is known to ask for. It never stores ID documents.

## Record consent

Unlist drafts nothing for a Subject until consent is recorded. On the Subject's page, open the consent page (`/subjects/<number>/consent/`). It shows exactly what the consent covers:

> Import the Subject's mail; send Access Requests and Removal Requests from the Subject's address (each approved by the Operator first); read and store the replies; draft Complaints.

Read it out to the person, or let them read it, and tick the confirmation. The record keeps who agreed, when, and the wording.

**Adults** agree for themselves.

**Children** (under 18, by the year of birth): a parent or guardian agrees and you record "a parent". From age 12 the Subject is flagged as needing their own involvement: talk to them, because a child's data rights belong to the child, and the parent acts on their behalf only as long as that is appropriate. Unlist cannot judge that for you.

Consent can be **withdrawn** at any time. Open Cases for that Subject then stop. **Deleting a Subject** erases their Cases, replies, attachments, discovery results, details, consent record and stored credentials, after one confirmation.

## Import mail

Unlist finds Organizations by reading who has mailed the Subject. The standard way is a file export. It needs no password and works with every provider. On the Subject's page choose "Import mail" (`/mail/subjects/<number>/import/`) and upload an `.mbox` file.

What Unlist does with the file:

- It reads the sender of each message. A sender counts only if the provider's own checks passed (DMARC, or an aligned DKIM signature), so that forged mail does not create false results.
- For order and booking mail it reads the message's HTML for order markup.
- It keeps, per Organization: name, domain, first and last date, number of messages, the kind of evidence, and the subject line of the strongest message. It **never stores a message body**, and it deletes your uploaded file when the scan is done.
- Personal mail (no bulk-mail markers, from personal mailbox domains) and Spam and Trash are skipped.

### Gmail: Google Takeout, step by step

These steps follow Unlist's own help text on the import page. Google changes its pages from time to time, so the wording of the menus here is not checked against Google's current site.

1. Open `takeout.google.com` while signed in to the Gmail account.
2. Choose "Deselect all", then select only **Mail**. You can limit it to some labels. "All Mail data included" gives the most results. Mail is exported in **mbox** format.
3. Create the export. Google emails a download link when it is ready. This can take hours or days.
4. Download and **unpack** the archive (it is a `.zip` or `.tgz`). The mail is in `Takeout/Mail/`, in a file ending in `.mbox`.
5. Upload that `.mbox` file on the Subject's import page. Optionally say which of the Subject's addresses it came from.

The file can be very large. If you use a reverse proxy, make sure it allows big uploads (see [install](install.md#behind-your-own-https-reverse-proxy)).

If the result says "no messages found", you probably uploaded the archive and not the `.mbox` file inside it.

### Other providers

Most mail programs can save a folder as mbox. In Thunderbird, add the account, then use the ImportExportTools NG add-on: right-click the folder and export it (or "save all messages") as mbox. Providers with their own export function, for example Fastmail, Posteo and mailbox.org, usually offer mbox or a format Thunderbird can open. Exact menus differ between providers and change over time; this guide cannot give them step by step, so check your provider's help pages.

### Outlook.com and Microsoft 365

These mailboxes are **import-only**. Microsoft has turned off password sign-in for IMAP and Unlist does not use OAuth, so it cannot connect to them live. Add the account to Thunderbird (it signs in on Microsoft's own page), export the folders as mbox as above, and import the file. Requests for these Subjects are handed over for the Subject to send (see [approve drafts and send them](#approve-drafts-and-send-them)).

### Live connection

If you would rather not export files, a [live connection](live-connection.md) can scan a mailbox for you. It is optional.

## The discovery list

After an import, open the Subject's discovered Organizations (`/mail/subjects/<number>/discoveries/`). The page first reports what the import read and skipped. Then it lists every Organization that mailed the Subject, strongest evidence first, with how many messages and from when to when.

**Evidence kinds**, from strongest to weakest:

1. **Order or booking markup** in the mail (a machine-readable receipt).
2. **Orders, receipts, invoices and shipping mail.**
3. **Account mail**: welcomes, verification, password resets, security and policy notices.
4. **Newsletters and other bulk mail.**

An Organization with account or order evidence almost certainly holds data. A newsletter sender may hold only an address.

Each row is marked **new**, **already a Case**, or **ignored**. Brokers are labelled. An Organization that is on no Organization List appears as a "local stub": nothing is sent to it until you confirm its contact.

For each new row you can:

- **Pursue** it: this opens a Case and drafts an Access Request. There is also "Pursue all" for every row with account evidence. Nothing is sent before you approve it.
- **Ignore** it. This is remembered across later imports. You can bring it back.

### Unassigned senders

Some senders cannot be matched to one Organization: shared platform and email-service domains (mass mailers, hosting and newsletter platforms) and domains no list knows. They appear under "senders to assign". For each, you can assign it to an Organization (searching the lists, or creating a local stub), or ignore it.

## Open Cases

A Case starts with an **Access Request**: a polite email asking the Organization to confirm whether it holds data about the Subject, and to give a copy and say where it came from and who received it. Only if the Organization shows it holds a Listing does a **Removal Request** follow ("ask, then delete"). For one Case you can choose to request removal directly.

The Case page shows its state, who has to act next, the timeline, the deadline and the rule used to work it out, the drafts, replies and attachments.

If an Organization is reachable only by web form or by post, the draft turns into text for the form or a printable letter, and the step is handed to the Subject.

## Approve drafts and send them

Every email that leaves in a Subject's name is a **draft** that waits for you. Read it. You can edit it, discard it, or approve it. If the Organization's request language has no template (only English and German exist), the English text is used; if you have set up the [optional language model](llm.md), an "adapt" button can offer a translation to review.

The approve button shows exactly the recipient and whether Unlist sends the mail or hands it over.

- In **live mode**, approving sends the email through the Subject's own mailbox, and the clock starts that day. (See [live connection](live-connection.md).)
- In **import-only mode**, approving **hands the draft over**: Unlist does not send anything. On the Case you get:
  - a downloadable **`.eml` file** you can open in a mail program and send from the Subject's own address,
  - a **`mailto:` link** that opens a new message in the Subject's mail program, or
  - the form link or printable letter for web-form and postal Organizations.

  When the Subject has sent it, press **Mark sent** and enter the date it was sent. **The clock starts on that date**, not when you approved it. Unlist can only count days from a date you tell it, so enter the real one.

You can review several drafts at once on one screen listing every recipient.

## Replies

Replies come back to the Subject's mailbox, not to Unlist. Bring them in:

- **One reply at a time:** on the Case page, upload the reply as an `.eml` file (save the email from your mail program). Do not upload anything with an ID document attached; Unlist does not store those.
- **In a later import:** replies found in a new mbox import are matched and offered.
- **With a live connection:** replies are read and attached automatically.

Unlist matches a reply to a Case, in this order: by the email's reply headers, by the reference code in the subject line (for example `[Ref U-7KQ3]`), or by the sender's authenticated domain if that Organization has exactly one open Case for the Subject. Anything left goes to the **review queue** (`/cases/replies/`), where you assign it to a Case or dismiss it. Only matched mail is kept.

Bounces (delivery failure notices) put the Case in "undeliverable" automatically, and the clock never started. Fix the Organization's contact, then prepare the request again. Auto-replies are attached without changing anything.

For every other reply, Unlist **suggests** what happened, using keyword rules (or a language model if you set one up). **You confirm it.** The outcomes are: it holds nothing, it sent the data (a Listing exists), it confirms removal (with or without a Suppression Record for Brokers), it refused or did only part (you write down the exception it cited), it asked for ID or more details, it asks which data is meant, or it announced an extension.

If an Organization asks for an **ID document**, Unlist first drafts a polite pushback: the request came from the address the Organization already knows, and a copy of ID is generally disproportionate. If it insists, you and the Subject choose: send ID yourselves (Unlist drafts a reply, and the Subject attaches the document from their own device, ideally with unneeded details blacked out), or draft a Complaint. If it asks for **details** (a customer number, a previous address), Unlist answers from the stored details, with exactly what was asked.

## Deadlines

An Organization has **one month** from receiving a request to answer. Unlist works out the due date and shows how, step by step, on the Case.

- **Counting.** The due date is the same day-number in the next month (the last day of the month if there is none). If that is a weekend or a public holiday in the Organization's country, it moves to the next working day.
- **Extension.** An Organization may extend by two more months, but only if it says so within the first month and gives reasons. Otherwise Unlist records the claim and ignores it.
- **Pauses.** When an Organization asks for ID or more details, the clock pauses until the Subject answers (EU rule). In the UK a fresh month starts when the answer is sent. When it asks which data a broad Access Request means, the clock pauses (EU) or the days between asking and answering do not count (UK).
- **Grace.** A Case counts as **overdue 3 days after** the due date.
- **Reminder.** Overdue Cases get a polite **reminder** draft, which also waits for your approval. It names the original request and gives **14 days**.
- If that passes too, Unlist offers a **Complaint draft**.

The scheduler does the counting in the background. It marks overdue Cases and prepares reminders and re-checks. It never sends anything.

**Holidays.** Public holidays are built in for AT, BE, CH, CZ, DE, DK, ES, FI, FR, GB, IE, IT, LU, NL, PL, PT and SE, national holidays only. Regional holidays are not included, which is one reason for the 3-day grace. For other countries only weekends are skipped. Check the date shown if it matters.

## Re-checks

Data comes back, especially with Brokers. Resting Cases come back for a **re-check**, which is a new Access Request prepared when it is due and waiting for your approval:

- **Brokers:** 90 days after "removed" or "nothing held".
- **Other Organizations:** 365 days after "removed". After "nothing held" they simply close.
- No re-check after you accepted a refusal of access, or chose to keep a Listing.

You can change the interval, or choose "close", for one Case or one Organization. Fresh mail from a resting Organization in a later import suggests an early re-check. A Listing that returns after a confirmed Suppression Record may go straight to a Complaint draft.

## Complaints

A Complaint goes to the **Supervisory Authority** (the data protection regulator) of the Subject's country. Unlist offers a draft after a missed deadline plus a reminder, after a refusal, or after repeated ID demands. It never offers one before the request was sent.

A Complaint draft contains the Subject's details, the Organization's identity, a dated timeline from the Case, the problem in plain words, what is being asked for, and the earlier contact. You can download the evidence (the sent request with its headers, the reminder, the replies). In the UK, a short complaint to the Organization itself comes first, which the Subject may skip.

**You lodge the Complaint yourself.** Unlist never submits it. It shows the authority's channel and gives the text or a PDF. After the Subject has lodged it, press the button to mark it lodged. A late answer still moves the Case on.

## Statistics

The statistics page (`/statistics/`) is for looking, not for nagging. It shows, per Subject and for the household: Organizations by evidence kind and how many are Brokers, Cases by state, outcomes (including Suppression Records confirmed), and a month-by-month chart of Organizations holding data versus removed. Per Organization it shows how fast it answers, how often on time, and how often it demanded ID. These numbers come only from your own instance. Every number links to the Cases behind it.

## The breach check

The breach check (`/breaches/`) shows publicly known breaches at the Organizations a Subject deals with. It looks only at Organization domains. It **never looks up an email address** and sends nothing about a Subject anywhere. It does not claim the Subject's own address was in a breach.

- It uses the free breach catalogue of Have I Been Pwned, which ships with each release as a snapshot (CC BY 4.0, attribution shown wherever it is used). It works fully offline.
- **Updating the catalogue is manual.** The "Update breach list" button sends one request to Have I Been Pwned (haveibeenpwned.com). That is **an outside service that is not free software** (a nonfree service). Nothing is sent unless you press the button, and Unlist is complete without it.
- Breaches with no domain can be assigned to Organizations by hand.

## If something is stuck

- Nothing is sent: in import-only mode, that is expected. Approve, send it yourself, then press **Mark sent**.
- A reply does not show up: upload it as `.eml` on its Case, or look in the review queue.
- The wrong contact: on the Organization's page, save a local override. See [Organization Lists](organization-lists.md).

## Next

- [Optional live connection](live-connection.md)
- [Optional language model](llm.md)
- [Back up](backup.md) before you do anything important
- [What Unlist does and does not do](legal.md)
