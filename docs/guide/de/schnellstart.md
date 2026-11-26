# Schnellstart

[English: install and first run](../install.md)

Unlist ist eine Anwendung, die Sie selbst betreiben. Sie hilft Ihnen und Ihrem Haushalt herauszufinden, welche Unternehmen persönliche Daten über Sie haben, und diese Unternehmen höflich um Auskunft und Löschung zu bitten. Grundlage sind Ihre eigenen Rechte nach der DSGVO (und, im Vereinigten Königreich, der UK GDPR). Unlist ist **kein Rechtsrat** und keine Anwaltskanzlei (siehe [Rechtliches](rechtliches.md)).

Die Person, die Unlist betreibt, heißt hier **Betreiber** (im englischen Programm „Operator“). Die Menschen, für die er handelt, heißen **Betroffene** („Subjects“). **Wichtig:** Die Oberfläche von Unlist ist auf Englisch. Die Begriffe in Klammern helfen Ihnen, die Seiten zu finden.

## Was Sie brauchen

- Einen Rechner, der läuft, solange Sie Unlist nutzen (Laptop, Heimserver, kleiner Server).
- **Docker** mit dem Compose-Plugin.
- Etwa **1 GB freien Speicherplatz**.
- Einen Webbrowser.

Sie brauchen kein Konto bei irgendjemandem. Unlist nimmt von sich aus mit niemandem Kontakt auf.

## Starten

```sh
git clone https://github.com/Hjiaky/Unlist.git
cd Unlist
docker compose up -d --build
docker compose logs unlist
sudo cp key/unlist.key /ein/sicherer/ort/unlist.key
```

Was die Befehle tun:

1. Unlist herunterladen und in den Ordner wechseln.
2. Das Programm bauen und starten. Beim ersten Start entstehen die Ordner `data` und `key`, und ein Schlüssel wird erzeugt.
3. Das Protokoll anzeigen. Es nennt, wo der neue Schlüssel liegt.
4. Den Schlüssel an einem sicheren, privaten Ort **getrennt von `data`** aufbewahren. `sudo` brauchen Sie nur, wenn Ihr Benutzer die Datei nicht lesen darf.

### Die beiden Ordner

| Ordner | Inhalt |
|---|---|
| `./data` | Alles, was Unlist weiß: eine SQLite-Datei, die Anhänge und die Sicherungen. Enthält persönliche Daten. |
| `./key` | Der Schlüssel, der gespeicherte Postfach-Passwörter verschlüsselt. Er liegt bewusst **nicht** in `data`, damit eine Sicherung von `data` den Schlüssel nicht enthält. |

Verlieren Sie den Schlüssel, geht nichts anderes verloren: Sie müssen nur Postfach-Passwörter neu eingeben.

## Öffnen

Öffnen Sie <http://localhost:8000>. Von einem anderen Gerät im selben Netz: `http://<Name oder IP-Adresse des Rechners>:8000`.

Diese Verbindung ist **unverschlüsselt (HTTP)**. Das ist in einem vertrauenswürdigen Heimnetz vertretbar, aber nicht über das Internet. Für den Zugriff von außen brauchen Sie einen eigenen HTTPS-Reverse-Proxy (siehe [Installation, englisch](../install.md#behind-your-own-https-reverse-proxy)). Leiten Sie Port 8000 nicht am Router weiter.

## Erste Schritte in Unlist

1. **Betreiber anlegen.** Beim ersten Aufruf bittet Unlist um einen Benutzernamen und ein Passwort (mindestens 12 Zeichen). Notieren Sie den Benutzernamen.
2. **Betroffene Person hinzufügen** („Add a Subject“): Name, Wohnland (es bestimmt die zuständige **Aufsichtsbehörde**), eine E-Mail-Adresse. Bei Kindern: Geburtsjahr und wer die elterliche Sorge hat.
3. **Einwilligung festhalten** („Record consent“). Unlist erstellt nichts, bevor die Einwilligung der Person festgehalten ist. Bei Kindern willigt ein Elternteil ein; ab 12 Jahren sollte das Kind selbst einbezogen werden.
4. **E-Mails importieren** („Import mail“). Unlist erkennt Unternehmen daran, wer der Person geschrieben hat.
   - **Gmail:** Auf `takeout.google.com` alles abwählen, nur **Mail** auswählen, den Export erstellen (es kann Stunden oder Tage dauern), das Archiv entpacken und die Datei mit der Endung `.mbox` im Ordner `Takeout/Mail/` hochladen. Die Menüs von Google ändern sich; diese Schritte folgen dem Hilfetext in Unlist.
   - **Andere Anbieter:** Die meisten Mailprogramme können einen Ordner als mbox speichern, zum Beispiel Thunderbird mit dem Zusatz ImportExportTools NG.
   - **Outlook.com und Microsoft 365** lassen sich nur über eine Datei importieren (Microsoft erlaubt für IMAP keine Passwortanmeldung mehr).
5. **Gefundene Unternehmen ansehen** („Discovered Organizations“). Die Liste ist nach der Stärke des Belegs sortiert: Bestellungen und Rechnungen vor Konto-Mails vor Newslettern. Mit „Pursue“ eröffnen Sie einen **Fall** und lassen einen Auskunftsantrag entwerfen, mit „Ignore“ lassen Sie das Unternehmen aus.
6. **Entwürfe prüfen und freigeben.** **Jede E-Mail, die im Namen einer Person versendet wird, wartet auf Ihre Freigabe.** Ohne Postfach-Verbindung („nur Import“) versendet Unlist nichts selbst: Sie laden die `.eml`-Datei herunter oder öffnen den `mailto:`-Link, senden die E-Mail aus dem eigenen Postfach der Person und drücken dann „Mark sent“ mit dem **echten Absendedatum**. Ab diesem Datum läuft die Frist.
7. **Antworten einspielen:** Speichern Sie die E-Mail als `.eml` und laden Sie sie beim Fall hoch, oder importieren Sie das Postfach später erneut. Unlist schlägt vor, was die Antwort bedeutet; **Sie bestätigen**.
8. **Fristen:** Unternehmen haben **einen Monat** Zeit. Unlist rechnet das Datum aus und zeigt den Rechenweg. Nach der Frist plus 3 Tagen Karenz bereitet es eine **Erinnerung** vor, danach den Entwurf einer **Beschwerde**.
9. **Beschwerde:** Eine Beschwerde reichen die Betroffenen **selbst** bei ihrer Aufsichtsbehörde ein. Unlist übermittelt sie nie, es schreibt nur den Entwurf.

Alles Weitere steht in der [Anleitung „First run“](../first-run.md) (englisch).

## Sicherung

Machen Sie vor jedem Update eine Sicherung: Seite „Backup“ im Programm, Knopf „Download backup“. Die Sicherung enthält die Daten des Haushalts, aber **nicht** den Schlüssel. Bewahren Sie sie verschlüsselt und privat auf. Mehr dazu: [Backup and restore](../backup.md) (englisch).

## Aktualisieren

```sh
git pull
docker compose up -d --build
```

Die Datenbank wird beim Start automatisch auf den neuen Stand gebracht. Machen Sie vorher eine Sicherung.

## Passwort ändern

```sh
docker compose exec --user unlist unlist python manage.py changepassword <Benutzername>
```

## Probleme melden

<https://github.com/Hjiaky/Unlist/issues>. Bitte **keine persönlichen Daten** in ein Ticket schreiben (keine echten Namen, Adressen oder Aktenzeichen).
