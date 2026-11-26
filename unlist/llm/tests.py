# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""The optional LLM endpoint and its four jobs (#56). No test touches the network."""

import email.message
import json
import os
import urllib.error
import urllib.request
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from unlist import crypto
from unlist.backup import hooks as backup_hooks
from unlist.cases import replies, services
from unlist.cases.models import Draft
from unlist.cases.tests.helpers import DAY0, make_organization, make_subject, send
from unlist.cases.tests.mail import DataDirMixin, make_message
from unlist.llm import client, endpoint, fetch, hooks, jobs
from unlist.llm.forms import SettingsForm
from unlist.llm.models import LlmSettings
from unlist.llm.redaction import Redactor
from unlist.mail.models import Discovery, UnassignedSender
from unlist.organizations import services as organization_services
from unlist.organizations.models import LocalOverride, Organization
from unlist.subjects.models import IdentifyingDetail, Mailbox

NAME, EMAIL, OTHER_EMAIL = "Robin Quillfeather", "robin.q@mailbox.test", "rq.second@post.test"
DETAIL = "CN-4471-9902"
BIRTH = "14.02.1987"
SECRETS = (NAME, "Robin", "Quillfeather", EMAIL, OTHER_EMAIL, DETAIL, BIRTH)
PUBLIC_ADDRESS = [(2, 1, 6, "", ("93.184.216.34", 443))]


class FakeResponse:
    def __init__(self, data: bytes, content_type="application/json; charset=utf-8"):
        self.data = data
        self.headers = email.message.Message()
        self.headers["Content-Type"] = content_type

    def read(self, size=-1):
        return self.data if size is None or size < 0 else self.data[:size]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeLlm:
    """Stands in for ``client.urlopen``: records each request and answers ``answer`` (text or callable)."""

    def __init__(self, answer='{"outcome": "none"}'):
        self.answer = answer
        self.requests = []

    def __call__(self, request, timeout):
        body = json.loads(request.data.decode("utf-8"))
        self.requests.append(
            SimpleNamespace(
                url=request.full_url,
                method=request.get_method(),
                body=body,
                raw=request.data.decode("utf-8"),
                authorization=request.get_header("Authorization"),
                user_agent=request.get_header("User-agent"),
                timeout=timeout,
            )
        )
        content = self.answer(body["messages"][-1]["content"]) if callable(self.answer) else self.answer
        return FakeResponse(json.dumps({"choices": [{"message": {"role": "assistant", "content": content}}]}).encode())

    @property
    def sent(self) -> str:
        """The user message of the only request."""
        assert len(self.requests) == 1, self.requests
        return self.requests[0].body["messages"][-1]["content"]


class KeyMixin:
    def setUp(self):
        super().setUp()
        patcher = mock.patch.dict(os.environ, {"UNLIST_KEY": crypto.generate_key()})
        patcher.start()
        crypto.reset_cache()
        self.addCleanup(patcher.stop)
        self.addCleanup(crypto.reset_cache)


def switch_on(base_url="http://localhost:11434/v1", *, accept=False, **fields):
    settings = LlmSettings.load()
    settings.enabled, settings.base_url, settings.model = True, base_url, fields.pop("model", "llama3.1")
    for name, value in fields.items():
        setattr(settings, name, value)
    settings.save()
    if accept:
        settings.accept_notice()
    return settings


class NoNetwork:
    """Patch every way the LLM code could reach another host; record whether it tried."""

    def __enter__(self):
        self.llm = mock.patch.object(client, "urlopen", side_effect=AssertionError("LLM contacted")).start()
        self.page = mock.patch.object(fetch, "urlopen", side_effect=AssertionError("page fetched")).start()
        self.dns = mock.patch.object(fetch.socket, "getaddrinfo", side_effect=AssertionError("DNS looked up")).start()
        return self

    def __exit__(self, *exc):
        mock.patch.stopall()

    @property
    def called(self):
        return self.llm.called or self.page.called or self.dns.called


class World(KeyMixin, DataDirMixin, TestCase):
    """A Subject with two addresses and identifying details, an Organization, and a Case."""

    def setUp(self):
        super().setUp()
        self.subject = make_subject(name=NAME, email=EMAIL)
        Mailbox.objects.create(subject=self.subject, email=OTHER_EMAIL)
        IdentifyingDetail.objects.create(
            subject=self.subject, kind="customer_number", value=DETAIL, organization_label="acme"
        )
        IdentifyingDetail.objects.create(subject=self.subject, kind="date_of_birth", value=BIRTH)
        self.organization = make_organization(request_language="fr")
        self.case = services.open_case(self.subject, self.organization, on=DAY0)
        self.draft = self.case.pending_draft
        user = get_user_model().objects.create_user("operator", password="a long enough passphrase")
        self.client.force_login(user)

    def assertNothingIdentifying(self, text):
        for secret in SECRETS:
            self.assertNotIn(secret.lower(), text.lower())


# --- Local or remote -------------------------------------------------------------------------


class EndpointDetectionTests(SimpleTestCase):
    def test_local_addresses(self):
        for url in [
            "http://localhost:11434/v1",
            "http://LOCALHOST./v1",
            "http://127.0.0.1:8080/v1",
            "http://127.5.6.7/v1",
            "http://[::1]:11434/v1",
            "http://10.1.2.3/v1",
            "http://172.16.0.1/v1",
            "http://172.31.255.254/v1",
            "http://192.168.1.20:11434/v1",
            "http://gpu-box.local:11434/v1",
            "http://llm.lan/v1",
            "http://host.docker.internal:11434/v1",
            "http://ollama:11434/v1",
            "http://[fd12:3456::1]/v1",
            "http://[::ffff:192.168.0.5]/v1",
        ]:
            self.assertTrue(endpoint.is_local_url(url), url)

    def test_remote_addresses(self):
        for url in [
            "https://api.openai.com/v1",
            "https://api.mistral.ai/v1",
            "http://8.8.8.8/v1",
            "http://172.32.0.1/v1",
            "http://192.169.0.1/v1",
            "http://11.0.0.1/v1",
            "http://[2001:db8::1]/v1",
            "http://localhost.example.com/v1",
            "http://evil.local.example.com/v1",
            "",
            "not a url",
        ]:
            self.assertFalse(endpoint.is_local_url(url), url)

    def test_chat_url(self):
        self.assertEqual(endpoint.chat_url("http://localhost:11434/v1/"), "http://localhost:11434/v1/chat/completions")


class SettingsTests(KeyMixin, TestCase):
    def test_off_by_default(self):
        settings = LlmSettings.load()
        self.assertFalse(settings.enabled)
        self.assertFalse(settings.usable)
        self.assertIsNone(settings.pk and LlmSettings.objects.first())  # reading creates no row

    def test_operator_overrides_detection(self):
        settings = switch_on("http://ollama-vps.example.com/v1")
        self.assertTrue(settings.remote)
        settings.is_remote = False
        self.assertFalse(settings.remote)
        self.assertTrue(settings.usable)
        settings = switch_on("http://localhost:11434/v1", is_remote=True)
        self.assertTrue(settings.remote)
        self.assertFalse(settings.usable)

    def test_remote_endpoint_unusable_until_the_notice_is_accepted(self):
        settings = switch_on("https://api.provider.example/v1")
        self.assertTrue(settings.needs_notice)
        self.assertFalse(settings.usable)
        fake = FakeLlm("hello")
        with mock.patch.object(client, "urlopen", fake):
            with self.assertRaises(client.LlmUnavailable):
                client.chat(settings, [{"role": "user", "content": "hi"}])
            self.assertEqual(fake.requests, [])
            settings.accept_notice()
            self.assertTrue(settings.usable)
            self.assertEqual(client.chat(settings, [{"role": "user", "content": "hi"}]), "hello")
        self.assertEqual(len(fake.requests), 1)

    def test_a_new_host_asks_for_the_notice_again(self):
        settings = switch_on("https://api.provider.example/v1", accept=True)
        form = SettingsForm(
            {"enabled": "on", "base_url": "https://other.example/v1", "model": "m", "location": "detect"},
            settings=settings,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.apply(settings)
        self.assertIsNone(LlmSettings.load().remote_notice_accepted_at)

    def test_api_key_is_stored_encrypted(self):
        settings = switch_on()
        settings.set_api_key("sk-secret-123")
        settings.save()
        stored = LlmSettings.objects.values_list("api_key_encrypted", flat=True).get()
        self.assertNotIn("sk-secret-123", stored)
        self.assertEqual(crypto.decrypt(stored), "sk-secret-123")
        self.assertEqual(LlmSettings.load().api_key(), "sk-secret-123")

    def test_settings_form_keeps_the_key_when_left_empty(self):
        settings = switch_on()
        settings.set_api_key("sk-keep")
        settings.save()
        data = {"enabled": "on", "base_url": settings.base_url, "model": "m", "location": "detect", "api_key": ""}
        form = SettingsForm(data, settings=settings)
        self.assertTrue(form.is_valid(), form.errors)
        form.apply(settings)
        self.assertEqual(LlmSettings.load().api_key(), "sk-keep")
        form = SettingsForm({**data, "forget_api_key": "on"}, settings=settings)
        self.assertTrue(form.is_valid())
        form.apply(settings)
        self.assertFalse(LlmSettings.load().has_api_key)

    def test_enabling_needs_an_address_and_a_model(self):
        form = SettingsForm({"enabled": "on", "base_url": "", "model": "", "location": "detect"})
        self.assertFalse(form.is_valid())
        self.assertIn("base_url", form.errors)
        self.assertIn("model", form.errors)
        form = SettingsForm({"enabled": "on", "base_url": "ftp://x.example", "model": "m", "location": "detect"})
        self.assertFalse(form.is_valid())

    def test_registered_with_backup_and_replies(self):
        self.assertIn(hooks.api_key_tokens, backup_hooks.stored_secrets)
        self.assertIn(jobs.suggest_reply_outcome, replies.suggesters)

    def test_labels(self):
        self.assertEqual(switch_on().source_label, "Suggested by the local model")
        label = switch_on("https://api.provider.example/v1").source_label
        self.assertEqual(label, "Suggested by api.provider.example — a remote, nonfree service")


# --- The client ------------------------------------------------------------------------------


class ClientTests(KeyMixin, TestCase):
    def test_request_shape(self):
        settings = switch_on()
        fake = FakeLlm("answer")
        with mock.patch.object(client, "urlopen", fake):
            self.assertEqual(client.chat(settings, [{"role": "user", "content": "hi"}]), "answer")
        request = fake.requests[0]
        self.assertEqual(request.url, "http://localhost:11434/v1/chat/completions")
        self.assertEqual(request.method, "POST")
        self.assertEqual(
            request.body, {"model": "llama3.1", "messages": [{"role": "user", "content": "hi"}], "temperature": 0}
        )
        self.assertIsNone(request.authorization)
        self.assertIn("Unlist", request.user_agent)
        self.assertEqual(request.timeout, client.TIMEOUT)

    def test_bearer_only_with_a_key(self):
        settings = switch_on()
        settings.set_api_key("sk-123")
        settings.save()
        fake = FakeLlm("ok")
        with mock.patch.object(client, "urlopen", fake):
            client.chat(settings, [{"role": "user", "content": "hi"}])
        self.assertEqual(fake.requests[0].authorization, "Bearer sk-123")

    def test_errors_become_llm_errors(self):
        settings = switch_on()
        messages = [{"role": "user", "content": "hi"}]
        cases = [
            urllib.error.URLError("refused"),
            urllib.error.HTTPError("http://x", 500, "boom", {}, None),
            TimeoutError("slow"),
        ]
        for error in cases:
            with mock.patch.object(client, "urlopen", side_effect=error), self.assertRaises(client.LlmError):
                client.chat(settings, messages)
        for data in [b"not json", b'{"choices": []}', b"x" * (client.RESPONSE_MAX + 10)]:
            with (
                mock.patch.object(client, "urlopen", return_value=FakeResponse(data)),
                self.assertRaises(client.LlmError),
            ):
                client.chat(settings, messages)
        with mock.patch.object(client, "urlopen") as opened, self.assertRaises(client.LlmError):
            client.chat(settings, [{"role": "user", "content": "x" * (client.REQUEST_MAX + 1)}])
        opened.assert_not_called()

    def test_redirects_are_not_followed(self):
        handler = client._NoRedirect()
        request = urllib.request.Request("http://localhost/v1/chat/completions", data=b"{}")
        self.assertIsNone(handler.redirect_request(request, None, 302, "Found", {}, "https://elsewhere.example/"))

    def test_json_in_prose(self):
        self.assertEqual(client.parse_json_object('Sure! ```json\n{"a": 1}\n```'), {"a": 1})
        with self.assertRaises(client.LlmError):
            client.parse_json_object("no json here")


# --- Disabled: nothing is contacted and every job falls back ---------------------------------


class DisabledTests(World):
    def test_no_job_contacts_anyone(self):
        discovery = Discovery.objects.create(subject=self.subject, organization=self.organization, evidence="none")
        with NoNetwork() as network:
            self.assertIsNone(jobs.sort_leftover(discovery))
            self.assertIsNone(jobs.adapt_draft(self.draft))
            self.assertIsNone(jobs.find_privacy_contact("https://acme.example/privacy"))
            reply = SimpleNamespace(subject=self.subject, body="We have deleted your data.")
            self.assertIsNone(jobs.suggest_reply_outcome(reply))
            # Reply matching falls back to the keyword rules.
            self.draft = send(self.case, DAY0)
            reply = replies.ingest_message(
                self.subject,
                make_message(in_reply_to=self.draft.message_id, body="We have deleted all of your personal data."),
                source="imap",
            )
        self.assertFalse(network.called)
        self.assertEqual((reply.suggested_outcome, reply.suggestion_source), ("removed", "rules"))

    def test_pages_show_no_llm_buttons_and_views_refuse(self):
        discovery = Discovery.objects.create(subject=self.subject, organization=self.organization, evidence="none")
        with NoNetwork() as network:
            page = self.client.get(f"/mail/subjects/{self.subject.pk}/discoveries/")
            self.assertNotContains(page, "Ask the LLM")
            self.assertNotContains(self.client.get(f"/cases/{self.case.pk}/"), "Adapt to")
            self.assertNotContains(self.client.get("/organizations/o/acme/"), "Find privacy contact")
            response = self.client.post(f"/llm/sort/discovery/{discovery.pk}/", follow=True)
            self.assertContains(response, "not switched on")
            response = self.client.post(f"/llm/drafts/{self.draft.pk}/adapt/")
            self.assertRedirects(response, f"/cases/{self.case.pk}/", fetch_redirect_response=False)
            response = self.client.post("/llm/organizations/acme/contact/", {"url": "https://acme.example/privacy"})
            self.assertRedirects(response, "/organizations/o/acme/", fetch_redirect_response=False)
        self.assertFalse(network.called)

    def test_remote_without_notice_counts_as_off(self):
        switch_on("https://api.provider.example/v1")
        discovery = Discovery.objects.create(subject=self.subject, organization=self.organization, evidence="none")
        with NoNetwork() as network:
            self.assertIsNone(jobs.sort_leftover(discovery))
            self.assertIsNone(jobs.adapt_draft(self.draft))
            self.assertIsNone(jobs.suggest_reply_outcome(SimpleNamespace(subject=self.subject, body="Deleted.")))
        self.assertFalse(network.called)


# --- 1. Discovery leftovers ------------------------------------------------------------------


class SortTests(World):
    def setUp(self):
        super().setUp()
        switch_on()
        self.sender = UnassignedSender.objects.create(
            subject=self.subject,
            domain="mailer.example",
            display_name="Shop Mailer",
            evidence="none",
            strongest_subject=f"Hello {NAME}, about {EMAIL} and {DETAIL}",
        )

    def test_sends_sender_and_subject_line_only(self):
        fake = FakeLlm('{"evidence": "account", "reason": "welcome mail"}')
        with mock.patch.object(client, "urlopen", fake):
            suggestion = jobs.sort_leftover(self.sender)
        self.assertEqual(suggestion.evidence, "account")
        self.assertEqual(suggestion.label, "Suggested by the local model")
        self.assertEqual(
            fake.sent,
            "Sender: Shop Mailer (mailer.example)\nSubject line: Hello {{NAME}}, about {{EMAIL}} and {{DETAIL}}",
        )
        self.assertNothingIdentifying(fake.requests[0].raw)
        self.assertEqual([m["role"] for m in fake.requests[0].body["messages"]], ["system", "user"])
        self.sender.refresh_from_db()
        self.assertEqual(self.sender.evidence, "none")  # a suggestion changes nothing

    def test_discovery_sends_organization_and_subject_line(self):
        self.organization.domains = ["acme.example"]
        self.organization.save()
        discovery = Discovery.objects.create(
            subject=self.subject, organization=self.organization, evidence="none", strongest_subject="Your parcel"
        )
        fake = FakeLlm('{"evidence": "transaction"}')
        with mock.patch.object(client, "urlopen", fake):
            self.assertEqual(jobs.sort_leftover(discovery).evidence, "transaction")
        self.assertEqual(fake.sent, "Sender: ACME Ltd (acme.example)\nSubject line: Your parcel")

    def test_only_unsorted_mail_and_known_kinds(self):
        self.sender.evidence = "bulk"
        with NoNetwork() as network:
            self.assertIsNone(jobs.sort_leftover(self.sender))
        self.assertFalse(network.called)
        self.sender.evidence = "none"
        for answer in ['{"evidence": "order_markup"}', "no idea", '{"evidence": "spam"}']:
            with mock.patch.object(client, "urlopen", FakeLlm(answer)), self.assertLogs("unlist.llm", "WARNING"):
                self.assertIsNone(jobs.sort_leftover(self.sender))
        with (
            mock.patch.object(client, "urlopen", side_effect=urllib.error.URLError("down")),
            self.assertLogs("unlist.llm", "WARNING") as logged,
        ):
            self.assertIsNone(jobs.sort_leftover(self.sender))
        self.assertIn("could not be reached", logged.output[0])

    def test_pages_offer_the_button_and_apply_only_on_click(self):
        page = self.client.get(f"/mail/subjects/{self.subject.pk}/unassigned/")
        self.assertContains(page, "Ask the LLM")
        fake = FakeLlm('{"evidence": "account", "reason": "welcome mail"}')
        with mock.patch.object(client, "urlopen", fake):
            response = self.client.post(f"/llm/sort/sender/{self.sender.pk}/")
        self.assertContains(response, "Account notice")
        self.assertContains(response, "Suggested by the local model")
        self.sender.refresh_from_db()
        self.assertEqual(self.sender.evidence, "none")
        response = self.client.post(f"/llm/sort/sender/{self.sender.pk}/apply/", {"evidence": "account"})
        self.assertRedirects(response, f"/mail/subjects/{self.subject.pk}/unassigned/", fetch_redirect_response=False)
        self.sender.refresh_from_db()
        self.assertEqual(self.sender.evidence, "account")
        self.assertNotContains(self.client.get(f"/mail/subjects/{self.subject.pk}/unassigned/"), "Ask the LLM")

    def test_apply_refuses_order_markup_and_sorted_mail(self):
        self.client.post(f"/llm/sort/sender/{self.sender.pk}/apply/", {"evidence": "order_markup"})
        self.sender.refresh_from_db()
        self.assertEqual(self.sender.evidence, "none")
        self.sender.evidence = "bulk"
        self.sender.save()
        self.client.post(f"/llm/sort/sender/{self.sender.pk}/apply/", {"evidence": "account"})
        self.sender.refresh_from_db()
        self.assertEqual(self.sender.evidence, "bulk")

    def test_remote_label(self):
        switch_on("https://api.provider.example/v1", accept=True)
        with mock.patch.object(client, "urlopen", FakeLlm('{"evidence": "bulk"}')):
            response = self.client.post(f"/llm/sort/sender/{self.sender.pk}/")
        self.assertContains(response, "Suggested by api.provider.example — a remote, nonfree service")


# --- 2. Drafts in another language -----------------------------------------------------------


def pretend_translation(text):
    """A 'translation' that keeps the placeholders, as a well-behaved model does."""
    first, _, rest = text.partition("\n")
    return f"{first} (fr)\n\nBonjour,\n" + "\n".join(f"FR {line}" for line in rest.splitlines())


class AdaptTests(World):
    def setUp(self):
        super().setUp()
        switch_on()
        self.draft.body += f"\nCustomer number: {DETAIL}\nDate of birth: {BIRTH}\nReach me at {EMAIL}.\n{NAME}\n"
        self.draft.save()

    def test_draft_needs_a_language_without_template(self):
        self.assertEqual(self.draft.lang, "en")
        self.assertEqual(jobs.adapt_target(self.draft), "fr")
        self.assertEqual(jobs.language_name("fr"), "French")

    def test_placeholders_go_out_and_real_values_come_back(self):
        fake = FakeLlm(pretend_translation)
        with mock.patch.object(client, "urlopen", fake):
            proposal = jobs.adapt_draft(self.draft)
        self.assertNothingIdentifying(fake.requests[0].raw)
        self.assertNotIn(self.case.reference, fake.requests[0].raw)
        for placeholder in ("{{NAME}}", "{{EMAIL}}", "{{DETAIL}}", "{{REFERENCE}}"):
            self.assertIn(placeholder, fake.sent)
        self.assertIn("French", fake.requests[0].body["messages"][0]["content"])
        self.assertIn(self.case.reference, proposal.subject_line)
        for value in (NAME, EMAIL, DETAIL, BIRTH):
            self.assertIn(value, proposal.body)
        self.assertIn("Bonjour", proposal.body)
        self.assertNotIn("{{", proposal.body + proposal.subject_line)
        self.draft.refresh_from_db()
        self.assertNotIn("Bonjour", self.draft.body)  # nothing changes before the Operator accepts

    def test_an_answer_that_loses_a_placeholder_is_dropped(self):
        def lossy(text):
            return pretend_translation(text).replace("{{DETAIL}}", "[number]")

        with mock.patch.object(client, "urlopen", FakeLlm(lossy)), self.assertLogs("unlist.llm", "WARNING") as logged:
            self.assertIsNone(jobs.adapt_draft(self.draft))
        self.assertIn("{{DETAIL}}", logged.output[0])
        with (
            mock.patch.object(client, "urlopen", FakeLlm("Bonjour, no subject line")),
            self.assertLogs("unlist.llm", "WARNING"),
        ):
            self.assertIsNone(jobs.adapt_draft(self.draft))

    def test_button_proposal_and_accept(self):
        self.assertContains(self.client.get(f"/cases/{self.case.pk}/"), "Adapt to French")
        with mock.patch.object(client, "urlopen", FakeLlm(pretend_translation)):
            response = self.client.post(f"/llm/drafts/{self.draft.pk}/adapt/")
        self.assertContains(response, "Suggested by the local model")
        proposal = response.context["form"].initial
        self.assertIn("Bonjour", proposal["body"])
        response = self.client.post(f"/llm/drafts/{self.draft.pk}/accept/", proposal)
        self.assertRedirects(response, f"/cases/{self.case.pk}/", fetch_redirect_response=False)
        self.draft.refresh_from_db()
        self.assertIn("Bonjour", self.draft.body)
        self.assertEqual(self.draft.status, Draft.Status.AWAITING_APPROVAL)  # still needs approval
        self.assertTrue(self.case.events.filter(details__text="The Operator edited the draft.").exists())

    def test_no_button_when_a_template_exists(self):
        self.organization.request_language = "en"
        self.organization.save()
        self.assertIsNone(jobs.adapt_target(Draft.objects.get(pk=self.draft.pk)))
        self.assertNotContains(self.client.get(f"/cases/{self.case.pk}/"), "Adapt to")


class RedactorTests(SimpleTestCase):
    def test_round_trip(self):
        redactor = Redactor.build(
            name="Alex Example",
            emails=["alex@example.org"],
            details=["Old Street 1\n12345 Town", "42"],
            reference="U-7KQ3",
        )
        text = (
            "Dear Ms Example,\nAlex Example (ALEX@example.org), Old Street 1\n12345 Town, ref U-7KQ3, 42 days, "
            "Alexander"
        )
        redacted = redactor.redact(text)
        self.assertNotIn("Example", redacted)
        self.assertNotIn("alex@", redacted.lower())
        self.assertNotIn("Old Street", redacted)
        self.assertNotIn("U-7KQ3", redacted)
        self.assertIn("42 days", redacted)  # too short to identify anyone
        self.assertIn("Alexander", redacted)  # whole words only
        self.assertEqual(
            redactor.restore(redacted),
            text.replace("ALEX@example.org", "alex@example.org"),
        )
        self.assertEqual(redactor.missing_in(redacted, redacted.replace("{{REFERENCE}}", "")), {"{{REFERENCE}}"})


# --- 3. Reply outcomes -----------------------------------------------------------------------


class ReplyTests(World):
    def setUp(self):
        super().setUp()
        self.draft = send(self.case, DAY0)
        self.body = (
            f"Dear {NAME},\n\nWe have now erased your account. You will stay on our suppression list.\n\n"
            f"On 3 March 2025 {NAME} <{EMAIL}> wrote:\n"
            f"> Customer number: {DETAIL}\n> Date of birth: {BIRTH}\n"
        )

    def ingest(self, body=None):
        message = make_message(in_reply_to=self.draft.message_id, body=body or self.body, subject="Re: your request")
        return replies.ingest_message(self.subject, message, source="imap")

    def test_sends_only_the_new_reply_text(self):
        switch_on()
        fake = FakeLlm('{"outcome": "removed", "reason": "says the account was erased"}')
        with mock.patch.object(client, "urlopen", fake):
            reply = self.ingest()
        self.assertEqual(
            fake.sent, "Dear {{NAME}},\n\nWe have now erased your account. You will stay on our suppression list."
        )
        self.assertNothingIdentifying(fake.requests[0].raw)
        self.assertNotIn("Re: your request", fake.requests[0].raw)
        self.assertNotIn("privacy@acme.example", fake.requests[0].raw)
        self.assertEqual(fake.requests[0].timeout, jobs.REPLY_TIMEOUT)
        self.assertEqual((reply.suggested_outcome, reply.suggestion_source), ("removed", "llm"))
        self.assertTrue(reply.suggestion_note.startswith("Suggested by the local model: says the account"))
        self.assertTrue(reply.suggested_suppression)
        self.assertEqual(reply.status, "to_confirm")  # a suggestion, never applied

    def test_rules_apply_when_the_llm_has_no_answer(self):
        switch_on()
        for answer in ['{"outcome": "none"}', '{"outcome": "bounce"}']:
            with mock.patch.object(client, "urlopen", FakeLlm(answer)):
                reply = self.ingest(f"We have deleted all of your personal data. ({answer})")
            self.assertEqual((reply.suggested_outcome, reply.suggestion_source), ("removed", "rules"), answer)
        with mock.patch.object(client, "urlopen", FakeLlm("garbage")), self.assertLogs("unlist.llm", "WARNING"):
            reply = self.ingest("We have deleted all of your personal data. (garbage)")
        self.assertEqual((reply.suggested_outcome, reply.suggestion_source), ("removed", "rules"))
        with (
            mock.patch.object(client, "urlopen", side_effect=TimeoutError("slow")),
            self.assertLogs("unlist.llm", "WARNING"),
        ):
            reply = self.ingest("We have deleted all of your personal data. (timeout)")
        self.assertEqual((reply.suggested_outcome, reply.suggestion_source), ("removed", "rules"))

    def test_refusal_keeps_the_cited_exception_from_the_text(self):
        switch_on()
        body = "We cannot delete your invoices because we must retain them for 10 years under § 147 AO."
        with mock.patch.object(client, "urlopen", FakeLlm('{"outcome": "refused", "reason": "tax retention"}')):
            reply = self.ingest(body)
        self.assertEqual((reply.suggested_outcome, reply.suggestion_source), ("refused", "llm"))
        self.assertIn("147 AO", reply.suggested_exception)

    def test_queue_shows_the_llm_source(self):
        switch_on("https://api.provider.example/v1", accept=True)
        with mock.patch.object(client, "urlopen", FakeLlm('{"outcome": "removed", "reason": "erased"}')):
            self.ingest()
        page = self.client.get("/cases/replies/")
        self.assertContains(page, "Suggested by api.provider.example — a remote, nonfree service")


# --- 4. Privacy contact ----------------------------------------------------------------------

POLICY = b"""<html><head><title>Privacy</title><script>var x = 1;</script></head><body>
<h1>Privacy policy</h1><p>Contact our data protection officer at dpo@shop.example or write to
Shop GmbH, Datenschutz, Hauptstr. 1, 10115 Berlin.</p></body></html>"""


class ContactTests(World):
    def setUp(self):
        super().setUp()
        switch_on()
        self.stub = organization_services.create_stub("shop.example", "The Shop")
        self.answer = json.dumps(
            {
                "email": "dpo@shop.example",
                "address": "Shop GmbH\nDatenschutz\nHauptstr. 1\n10115 Berlin",
                "webform": "",
                "reason": "named as DPO contact",
            }
        )

    def fetching(self, data=POLICY, content_type="text/html; charset=utf-8"):
        return mock.patch.object(fetch, "urlopen", return_value=FakeResponse(data, content_type))

    def test_sends_only_the_page_text(self):
        fake = FakeLlm(self.answer)
        with (
            mock.patch.object(fetch.socket, "getaddrinfo", return_value=PUBLIC_ADDRESS),
            self.fetching() as fetched,
            mock.patch.object(client, "urlopen", fake),
        ):
            proposal = jobs.find_privacy_contact("https://shop.example/privacy")
        request = fetched.call_args.args[0]
        self.assertIn("Unlist", request.get_header("User-agent"))
        self.assertEqual(request.full_url, "https://shop.example/privacy")
        self.assertIn("Contact our data protection officer at dpo@shop.example", fake.sent)
        self.assertNotIn("var x", fake.sent)
        self.assertNotIn("shop.example/privacy", fake.requests[0].raw)
        self.assertNothingIdentifying(fake.requests[0].raw)
        self.assertEqual(proposal.email, "dpo@shop.example")
        self.assertEqual(proposal.address.splitlines()[-1], "10115 Berlin")

    def test_private_addresses_and_big_pages_are_refused(self):
        with (
            mock.patch.object(fetch.socket, "getaddrinfo", return_value=[(2, 1, 6, "", ("192.168.1.1", 443))]),
            self.fetching() as fetched,
            self.assertRaises(fetch.FetchError),
        ):
            fetch.page_text("http://router.example/")
        fetched.assert_not_called()
        with (
            mock.patch.object(fetch.socket, "getaddrinfo", return_value=PUBLIC_ADDRESS),
            self.fetching(b"x" * (fetch.PAGE_MAX + 1)),
            self.assertRaises(fetch.FetchError),
        ):
            fetch.page_text("https://shop.example/privacy")
        with self.assertRaises(fetch.FetchError):
            fetch.page_text("file:///etc/passwd")

    def test_invalid_values_are_dropped(self):
        answer = json.dumps({"email": "not an email", "address": "", "webform": "javascript:alert(1)"})
        with (
            mock.patch.object(fetch.socket, "getaddrinfo", return_value=PUBLIC_ADDRESS),
            self.fetching(),
            mock.patch.object(client, "urlopen", FakeLlm(answer)),
        ):
            self.assertIsNone(jobs.find_privacy_contact("https://shop.example/privacy"))

    def test_proposal_then_confirm_sets_overrides_and_confirms_the_contact(self):
        self.assertFalse(self.stub.contact_confirmed)
        page = self.client.get(f"/organizations/o/{self.stub.slug}/")
        self.assertContains(page, "Find privacy contact")
        with (
            mock.patch.object(fetch.socket, "getaddrinfo", return_value=PUBLIC_ADDRESS),
            self.fetching(),
            mock.patch.object(client, "urlopen", FakeLlm(self.answer)),
        ):
            response = self.client.post(
                f"/llm/organizations/{self.stub.slug}/contact/", {"url": "https://shop.example/privacy"}
            )
        self.assertContains(response, "Suggested by the local model")
        self.assertContains(response, "dpo@shop.example")
        self.assertFalse(LocalOverride.objects.filter(organization_slug=self.stub.slug, field="email").exists())
        initial = response.context["proposal_form"].initial
        response = self.client.post(f"/llm/organizations/{self.stub.slug}/contact/confirm/", initial)
        self.assertRedirects(response, f"/organizations/o/{self.stub.slug}/", fetch_redirect_response=False)
        organization = Organization.objects.get(slug=self.stub.slug)
        self.assertEqual(organization.email, "dpo@shop.example")
        self.assertIn("Hauptstr. 1", organization.address)
        self.assertTrue(organization.contact_confirmed)
        override = LocalOverride.objects.get(organization_slug=self.stub.slug, field="email")
        self.assertIn("shop.example/privacy", override.note)
        self.assertFalse(LocalOverride.objects.filter(organization_slug=self.stub.slug, field="webform").exists())


# --- The settings page -----------------------------------------------------------------------


class SettingsPageTests(KeyMixin, TestCase):
    def setUp(self):
        super().setUp()
        user = get_user_model().objects.create_user("operator", password="a long enough passphrase")
        self.client.force_login(user)

    def test_needs_login(self):
        self.client.logout()
        for url in ["/llm/", "/llm/organizations/acme/contact/"]:
            self.assertEqual(self.client.get(url).status_code, 302, url)

    def test_explains_and_lists_what_each_job_sends(self):
        page = self.client.get("/llm/")
        self.assertContains(page, "Unlist is complete without an LLM")
        self.assertContains(page, "http://localhost:11434/v1")
        self.assertContains(page, "llama.cpp")
        for job, _ in jobs.SENDS:
            self.assertContains(page, job)

    def test_save_and_accept_a_remote_endpoint(self):
        response = self.client.post(
            "/llm/",
            {
                "enabled": "on",
                "base_url": "https://api.provider.example/v1",
                "model": "big",
                "api_key": "sk-abc",
                "location": "detect",
            },
        )
        self.assertRedirects(response, "/llm/", fetch_redirect_response=False)
        settings = LlmSettings.load()
        self.assertTrue(settings.enabled and settings.needs_notice and not settings.usable)
        page = self.client.get("/llm/")
        self.assertContains(page, "api.provider.example is a remote service")
        self.assertContains(page, "nonfree")
        self.assertNotContains(page, "sk-abc")
        self.client.post("/llm/accept-notice/")
        self.assertTrue(LlmSettings.load().usable)
