"""A spoken note becomes an issue: nothing private leaves, nothing is lost, the key is never shown."""

import io
import json
import subprocess
import tempfile
import unittest
import urllib.error
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from onebutton import report

KEY = "github_pat_SECRET123"
SLUG = "MarcoArmenta/OneButton"
REPO = "https://github.com/MarcoArmenta/OneButton.git"
ISSUE = "https://github.com/MarcoArmenta/OneButton/issues/7"

LOG = """2026-11-27T17:03:10 SISTEMA: auth: {'loggedIn': True, 'email': 'jose@example.org'}
2026-11-27T17:03:12 BOTÓN: talk short (idle) -> talk
2026-11-27T17:03:15 GRABACIÓN: 2.8 s, nivel 0.04
2026-11-27T17:03:16 TÚ: escribe mi contraseña es girasol
2026-11-27T17:03:18 BOT: Claro, aquí tienes la carta para tu médico.
Segunda línea de la respuesta, con BOTÓN: dentro.
2026-11-27T17:03:19 LATEX: equis al cuadrado -> x^2
2026-11-27T17:03:20 PERMISO: Bash(rm notas-privadas.txt)
2026-11-27T17:03:21 LOGIN: código 4821
2026-11-27T17:03:22 EQUIPO: {"do": "type", "text": "querida Ana"}
2026-11-27T17:03:23 EQUIPO: error en type: Command '['python', 'desktop.py', 'type', 'querida Ana']' timed out after 30 seconds
2026-11-27T17:03:24 EQUIPO: error en focus: no hay ninguna ventana que se llame Diario
2026-11-27T17:03:25 EQUIPO: error en click: FailSafeException: mouse moved to a corner
2026-11-27T17:03:30 BOTÓN: talk long (idle) -> report
"""
PRIVATE = ["jose@example.org", "girasol", "contraseña", "carta", "médico", "Segunda línea", "equis", "x^2",
           "notas-privadas", "4821", "querida Ana", "Diario", "mouse moved",
           "TÚ", "BOT:", "SISTEMA", "LATEX", "PERMISO", "LOGIN"]


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
        self.closed = False

    def read(self):
        return self.payload

    def close(self):
        self.closed = True


def http_error(code, message=""):
    body = io.BytesIO(json.dumps({"message": message}).encode("utf-8"))
    return urllib.error.HTTPError("https://api.github.com/x", code, "refused", {}, body)


def opener_that(answer):
    """An urlopen that records what it was asked and answers (or raises) `answer`."""
    calls = []

    def opener(request, timeout=None):
        calls.append((request, timeout))
        if isinstance(answer, BaseException):
            raise answer
        return answer

    opener.calls = calls
    return opener


class TechnicalLinesTests(unittest.TestCase):
    def test_keeps_presses_recordings_and_failed_orders_oldest_first(self):
        self.assertEqual(report.technical_lines(LOG), [
            "2026-11-27T17:03:12 BOTÓN: talk short (idle) -> talk",
            "2026-11-27T17:03:15 GRABACIÓN: 2.8 s, nivel 0.04",
            "2026-11-27T17:03:23 EQUIPO: error en type: timed out",
            "2026-11-27T17:03:24 EQUIPO: error en focus",
            "2026-11-27T17:03:25 EQUIPO: error en click: FailSafeException",
            "2026-11-27T17:03:30 BOTÓN: talk long (idle) -> report",
        ])

    def test_never_returns_what_he_said_what_was_answered_or_his_account(self):
        joined = "\n".join(report.technical_lines(LOG, limit=1000))
        for secret in PRIVATE:
            self.assertNotIn(secret, joined)

    def test_a_failed_order_keeps_its_name_and_kind_never_the_text_he_typed(self):
        log = "2026-11-27T17:03:23 EQUIPO: error en type: Command '['py', 'type', 'mi clave es 1234']' timed out\n"
        self.assertEqual(report.technical_lines(log), ["2026-11-27T17:03:23 EQUIPO: error en type: timed out"])
        odd = "2026-11-27T17:03:23 EQUIPO: error mi clave es 1234\n"
        self.assertEqual(report.technical_lines(odd), ["2026-11-27T17:03:23 EQUIPO: error"])

    def test_lines_that_do_not_parse_are_dropped(self):
        log = "BOTÓN: sin fecha\nayer BOTÓN: fecha rara\n\n   \n2026-11-27T17:03:12 BOTÓN sin dos puntos\n"
        self.assertEqual(report.technical_lines(log), [])
        self.assertEqual(report.technical_lines(""), [])

    def test_an_unknown_kind_of_line_stays_private(self):
        self.assertEqual(report.technical_lines("2026-11-27T17:03:12 NUEVO: algo que dijo\n"), [])

    def test_limit_keeps_the_last_ones(self):
        log = "".join(f"2026-11-27T17:00:{i:02d} BOTÓN: press {i}\n" for i in range(50))
        lines = report.technical_lines(log)
        self.assertEqual(len(lines), 40)
        self.assertTrue(lines[0].endswith("press 10") and lines[-1].endswith("press 49"))
        self.assertEqual(report.technical_lines(log, limit=2),
                         ["2026-11-27T17:00:48 BOTÓN: press 48", "2026-11-27T17:00:49 BOTÓN: press 49"])
        self.assertEqual(report.technical_lines(log, limit=0), [])

    def test_a_very_long_line_is_cut(self):
        line = report.technical_lines("2026-11-27T17:03:12 BOTÓN: " + "x" * 5000)[0]
        self.assertLessEqual(len(line), report.LINE_MAX)
        self.assertTrue(line.endswith("…"))


class ComposeTests(unittest.TestCase):
    INFO = {"when": "2026-11-27 17:03", "version": "v0.9.2", "system": "Windows 11", "speaks": "es",
            "buttons": ["space", "enter"], "screen": "", "module": None}

    def test_title_is_the_note_on_one_line(self):
        title, _ = report.compose("El botón\n no  respondió", {})
        self.assertEqual(title, "Voice note: El botón no respondió")

    def test_a_long_title_is_cut_with_an_ellipsis(self):
        title, body = report.compose("palabra " * 40, {})
        self.assertLessEqual(len(title), 70)
        self.assertTrue(title.startswith("Voice note: palabra") and title.endswith("…"))
        self.assertIn(("palabra " * 40).strip(), body, "the body keeps the whole note")

    def test_the_note_is_quoted_as_he_said_it(self):
        _, body = report.compose("Se quedó escuchando.\nNo paró cuando solté el botón.", {})
        self.assertTrue(body.startswith("> Se quedó escuchando.\n> No paró cuando solté el botón.\n\n"))

    def test_details_in_order_without_the_empty_ones(self):
        _, body = report.compose("nota", self.INFO)
        self.assertIn("## Details\n\n- when: 2026-11-27 17:03\n- version: v0.9.2\n- system: Windows 11\n"
                      "- speaks: es\n- buttons: space, enter\n\n", body)
        self.assertNotIn("screen", body)
        self.assertNotIn("module", body)

    def test_the_last_presses_go_in_a_code_block(self):
        _, body = report.compose("nota", {}, LOG)
        self.assertIn("## Last presses and recordings\n\n```text\n2026-11-27T17:03:12 BOTÓN: talk short (idle) -> talk\n",
                      body)
        self.assertIn("-> report\n```\n\n", body)

    def test_no_section_when_the_log_has_nothing_technical(self):
        for log in ("", "2026-11-27T17:03:16 TÚ: hola\n2026-11-27T17:03:18 BOT: hola\n"):
            _, body = report.compose("nota", {}, log)
            self.assertNotIn("Last presses", body)
            self.assertNotIn("```", body)
            self.assertNotIn("## Details", body)

    def test_never_leaks_what_he_said_what_was_answered_or_his_account(self):
        title, body = report.compose("El botón no respondió", self.INFO, LOG)
        for secret in PRIVATE:
            self.assertNotIn(secret, title + body)

    def test_the_last_line_says_where_it_comes_from_and_what_it_leaves_out(self):
        _, body = report.compose("nota", self.INFO, LOG)
        last = body.splitlines()[-1]
        self.assertIn("Sent by voice from OneButton", last)
        self.assertIn("nothing that was said to the computer", last)

    def test_a_line_with_backticks_cannot_close_the_block(self):
        _, body = report.compose("nota", {}, "2026-11-27T17:03:12 BOTÓN: ``` raro\n")
        self.assertIn("````text\n2026-11-27T17:03:12 BOTÓN: ``` raro\n````", body)

    def test_an_empty_note_still_makes_an_issue(self):
        title, body = report.compose("  ", {})
        self.assertEqual(title, "Voice note: (empty)")
        self.assertTrue(body.startswith("> (empty)"))


class RepoSlugTests(unittest.TestCase):
    def test_the_usual_spellings(self):
        for url in ("https://github.com/MarcoArmenta/OneButton.git", "https://github.com/MarcoArmenta/OneButton",
                    "https://github.com/MarcoArmenta/OneButton/", "git@github.com:MarcoArmenta/OneButton.git",
                    "ssh://git@github.com/MarcoArmenta/OneButton.git", "https://someone@GitHub.com/MarcoArmenta/OneButton",
                    "  http://www.github.com/MarcoArmenta/OneButton.git\n"):
            self.assertEqual(report.repo_slug(url), SLUG, url)

    def test_a_dot_in_the_name_is_kept(self):
        self.assertEqual(report.repo_slug("https://github.com/owner/my.repo.git"), "owner/my.repo")

    def test_anything_not_on_github_is_none(self):
        for url in ("https://gitlab.com/MarcoArmenta/OneButton.git", "https://github.com.evil.org/a/b",
                    "https://github.com@evil.org/a/b", "https://evilgithub.com/a/b", "https://github.com/onlyowner",
                    "https://github.com/a/b/issues", "https://github.com/a/..", "/home/marco/OneButton", "", None):
            self.assertIsNone(report.repo_slug(url), url)


class TokenTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.file = Path(self.dir.name) / "credentials.env"

    def no_gh(self, *args, **kwargs):
        raise AssertionError("gh must not be asked when the file has the key")

    def test_reads_the_line_among_comments_and_other_keys(self):
        self.file.write_text("# keys\n\nANTHROPIC_API_KEY=sk-other\n# ONEBUTTON_GITHUB_TOKEN=old\n"
                             f"export ONEBUTTON_GITHUB_TOKEN = \"{KEY}\" \n", encoding="utf-8")
        self.assertEqual(report.token(self.file, run=self.no_gh), KEY)

    def test_single_quotes_and_a_byte_order_mark(self):
        self.file.write_text(f"ONEBUTTON_GITHUB_TOKEN='{KEY}'\n", encoding="utf-8-sig")
        self.assertEqual(report.token(self.file, run=self.no_gh), KEY)

    def test_an_empty_value_does_not_count_and_gh_is_asked(self):
        self.file.write_text("ONEBUTTON_GITHUB_TOKEN=\nONEBUTTON_GITHUB_TOKEN=''\n", encoding="utf-8")
        asked = []

        def gh(cmd, **kwargs):
            asked.append((cmd, kwargs))
            return SimpleNamespace(returncode=0, stdout="gho_fromcli\n")

        self.assertEqual(report.token(self.file, run=gh), "gho_fromcli")
        self.assertEqual(asked, [(["gh", "auth", "token"], {"capture_output": True, "text": True, "timeout": 10})])

    def test_no_file_and_gh_not_signed_in_is_none(self):
        missing = Path(self.dir.name) / "missing.env"
        self.assertIsNone(report.token(missing, run=lambda *a, **k: SimpleNamespace(returncode=1, stdout="")))
        self.assertIsNone(report.token(missing, run=lambda *a, **k: SimpleNamespace(returncode=0, stdout=" \n")))
        self.assertIsNone(report.token(missing, run=lambda *a, **k: SimpleNamespace(returncode=1, stdout="gho_x")))

    def test_gh_missing_or_stuck_is_none(self):
        def missing(*args, **kwargs):
            raise FileNotFoundError("gh")

        def stuck(*args, **kwargs):
            raise subprocess.TimeoutExpired("gh", 10)

        self.assertIsNone(report.token(self.file, run=missing))
        self.assertIsNone(report.token(self.file, run=stuck))


class SendTests(unittest.TestCase):
    def test_posts_the_issue_and_returns_its_address(self):
        response = FakeResponse({"html_url": ISSUE, "number": 7})
        opener = opener_that(response)
        self.assertEqual(report.send("Voice note: x", "> x", SLUG, KEY, opener=opener), ISSUE)
        (request, timeout), = opener.calls
        self.assertEqual(request.full_url, "https://api.github.com/repos/MarcoArmenta/OneButton/issues")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(json.loads(request.data.decode("utf-8")), {"title": "Voice note: x", "body": "> x"})
        headers = {name.lower(): value for name, value in request.header_items()}
        self.assertEqual(headers, {
            "authorization": f"Bearer {KEY}", "accept": "application/vnd.github+json",
            "x-github-api-version": "2022-11-28", "user-agent": "OneButton", "content-type": "application/json"})
        self.assertEqual(timeout, 20)
        self.assertTrue(response.closed)

    def test_the_key_is_not_carried_along_a_redirect(self):
        opener = opener_that(FakeResponse({"html_url": ISSUE}))
        report.send("t", "b", SLUG, KEY, opener=opener)
        request = opener.calls[0][0]
        self.assertNotIn("Authorization", request.headers)   # these are the ones urllib copies to a new address
        self.assertEqual(request.get_header("Authorization"), f"Bearer {KEY}")

    def test_github_saying_no_is_a_report_error_with_the_code(self):
        with self.assertRaises(report.ReportError) as caught:
            report.send("t", "b", SLUG, KEY, opener=opener_that(http_error(401, "Bad credentials")))
        self.assertEqual(str(caught.exception), "GitHub did not accept the key (401): Bad credentials")
        with self.assertRaises(report.ReportError) as caught:
            report.send("t", "b", SLUG, KEY, opener=opener_that(http_error(500)))
        self.assertEqual(str(caught.exception), "GitHub refused the note (500)")

    def test_no_connection_and_no_answer_in_time(self):
        cases = [(urllib.error.URLError(OSError("nodename nor servname provided")), "no connection to GitHub"),
                 (ConnectionResetError("reset"), "no connection to GitHub"),
                 (TimeoutError("timed out"), "GitHub did not answer in time"),
                 (urllib.error.URLError(TimeoutError("timed out")), "GitHub did not answer in time")]
        for failure, message in cases:
            with self.assertRaises(report.ReportError) as caught:
                report.send("t", "b", SLUG, KEY, opener=opener_that(failure))
            self.assertEqual(str(caught.exception), message)

    def test_an_answer_that_is_not_an_issue(self):
        for payload in (b"<html>proxy login</html>", {"number": 7}, [{"html_url": ISSUE}], {"html_url": 7},
                        {"html_url": "javascript:alert(1)"}):
            with self.assertRaises(report.ReportError) as caught:
                report.send("t", "b", SLUG, KEY, opener=opener_that(FakeResponse(payload)))
            self.assertEqual(str(caught.exception), "unexpected answer from GitHub")

    def test_the_key_never_appears_in_an_error(self):
        failures = [http_error(401, f"Bad credentials for Bearer {KEY}"), http_error(404, "Not Found"),
                    urllib.error.URLError(f"proxy refused Authorization: Bearer {KEY}"), TimeoutError(KEY),
                    ValueError(f"Invalid header value b'Bearer {KEY}'"), RuntimeError(f"Bearer {KEY}"),
                    FakeResponse(b"not json " + KEY.encode()), FakeResponse({"message": KEY})]
        for failure in failures:
            with self.assertRaises(report.ReportError) as caught:
                report.send("t", "b", SLUG, KEY, opener=opener_that(failure))
            self.assertNotIn(KEY, str(caught.exception), repr(failure))
            self.assertNotIn("SECRET", str(caught.exception), repr(failure))
            self.assertLess(len(str(caught.exception)), 200)

    def test_a_broken_key_is_refused_before_anything_is_sent_and_not_quoted(self):
        opener = opener_that(FakeResponse({"html_url": ISSUE}))
        for broken in ("", "   ", "github_pat_SECRET\nX-Other: 1", "two words"):
            with self.assertRaises(report.ReportError) as caught:
                report.send("t", "b", SLUG, broken, opener=opener)
            self.assertEqual(str(caught.exception), "the key is not valid")
        self.assertEqual(opener.calls, [])

    def test_a_slug_that_is_not_owner_and_repo_is_refused(self):
        opener = opener_that(FakeResponse({"html_url": ISSUE}))
        for slug in ("", "owner", "owner/repo/../../user", "owner/repo?x=1", None):
            with self.assertRaises(report.ReportError):
                report.send("t", "b", slug, KEY, opener=opener)
        self.assertEqual(opener.calls, [])


class SavedNotesTests(unittest.TestCase):
    NOW = datetime(2026, 11, 27, 17, 3, 12)

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.folder = Path(self.dir.name) / "reports"

    def test_save_makes_the_folder_and_names_the_file_by_the_time(self):
        path = report.save("Voice note: x", "> x\n\nfooter", self.folder, now=self.NOW)
        self.assertEqual(path, self.folder / "20261127-170312.md")
        self.assertEqual(path.read_text(encoding="utf-8"), "# Voice note: x\n\n> x\n\nfooter\n")

    def test_two_notes_in_the_same_second_do_not_overwrite_each_other(self):
        names = [report.save(f"t{i}", "b", self.folder, now=self.NOW).name for i in range(3)]
        self.assertEqual(names, ["20261127-170312.md", "20261127-170312-2.md", "20261127-170312-3.md"])

    def test_a_name_already_used_by_a_sent_note_is_not_taken_again(self):
        first = report.save("first", "b", self.folder, now=self.NOW)
        sent = report.mark_sent(first, ISSUE)
        second = report.save("second", "b", self.folder, now=self.NOW)
        self.assertEqual(second.name, "20261127-170312-2.md")
        self.assertEqual(report.read_saved(sent)[0], "first")

    def test_pending_is_oldest_first_and_leaves_out_the_sent_ones(self):
        later = report.save("later", "b", self.folder, now=datetime(2026, 11, 27, 18, 0, 0))
        first = report.save("first", "b", self.folder, now=self.NOW)
        second = report.save("second", "b", self.folder, now=self.NOW)      # -2: after "first", before "later"
        gone = report.save("gone", "b", self.folder, now=datetime(2026, 11, 26, 9, 0, 0))
        report.mark_sent(gone, ISSUE)
        (self.folder / "notes.txt").write_text("not a note")
        self.assertEqual(report.pending(self.folder), [first, second, later])

    def test_pending_of_a_folder_that_is_not_there_is_empty(self):
        self.assertEqual(report.pending(self.folder / "nowhere"), [])

    def test_mark_sent_renames_and_adds_the_address(self):
        path = report.save("Voice note: x", "> x", self.folder, now=self.NOW)
        sent = report.mark_sent(path, ISSUE)
        self.assertEqual(sent, self.folder / "20261127-170312.sent.md")
        self.assertFalse(path.exists())
        self.assertEqual(sent.read_text(encoding="utf-8"), f"# Voice note: x\n\n> x\n\n\nSent: {ISSUE}\n")
        self.assertEqual(report.mark_sent(sent, ISSUE), sent, "marking twice changes nothing")

    def test_read_saved_gives_back_what_was_saved(self):
        title, body = report.compose("Se quedó escuchando.\nNo paró.", {"version": "v0.9.2"}, LOG)
        path = report.save(title, body, self.folder, now=self.NOW)
        self.assertEqual(report.read_saved(path), (title, body))
        self.assertEqual(report.read_saved(report.mark_sent(path, ISSUE)), (title, body))

    def test_read_saved_of_a_file_written_by_hand(self):
        self.folder.mkdir()
        odd = self.folder / "odd.md"
        odd.write_text("just some words\n", encoding="utf-8")
        self.assertEqual(report.read_saved(odd), ("Voice note", "just some words"))


class DeliverTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.folder = Path(self.dir.name) / "reports"
        self.sent = []

    def sender(self, title, body, slug, key):
        self.sent.append((title, body, slug, key))
        return f"https://github.com/{slug}/issues/{len(self.sent)}"

    def offline(self, title, body, slug, key):
        raise report.ReportError("no connection to GitHub")

    def deliver(self, note, **kwargs):
        kwargs.setdefault("get_token", lambda: KEY)
        kwargs.setdefault("sender", self.sender)
        return report.deliver(note, {"version": "v0.9.2"}, LOG, kwargs.pop("repo", REPO), self.folder, **kwargs)

    def test_sends_the_note_and_marks_it_sent(self):
        res = self.deliver("El botón no respondió")
        self.assertEqual(res["url"], f"https://github.com/{SLUG}/issues/1")
        self.assertEqual((res["error"], res["sent"]), (None, 1))
        self.assertTrue(res["saved"].name.endswith(".sent.md") and res["saved"].exists())
        self.assertEqual(report.pending(self.folder), [])
        (title, body, slug, key), = self.sent
        self.assertEqual((title, slug, key), ("Voice note: El botón no respondió", SLUG, KEY))
        self.assertIn("> El botón no respondió", body)
        for secret in PRIVATE:
            self.assertNotIn(secret, title + body)
        self.assertNotIn(KEY, res["saved"].read_text(encoding="utf-8"))

    def test_without_a_key_it_is_kept(self):
        res = self.deliver("nota", get_token=lambda: None)
        self.assertEqual((res["url"], res["error"], res["sent"]), (None, "no key", 0))
        self.assertEqual(report.pending(self.folder), [res["saved"]])
        self.assertEqual(self.sent, [])

    def test_a_repository_that_is_not_on_github_is_kept_and_the_key_is_not_even_asked_for(self):
        def never():
            raise AssertionError("no reason to look for the key")

        res = self.deliver("nota", repo="https://gitlab.com/a/b.git", get_token=never)
        self.assertEqual((res["url"], res["error"], res["sent"]), (None, "not a GitHub repository", 0))
        self.assertEqual(report.pending(self.folder), [res["saved"]])

    def test_a_note_that_could_not_go_is_sent_with_the_next_one_oldest_first(self):
        first = self.deliver("primera", sender=self.offline)
        self.assertEqual((first["url"], first["error"], first["sent"]), (None, "no connection to GitHub", 0))
        self.assertEqual(report.pending(self.folder), [first["saved"]])
        second = self.deliver("segunda")
        self.assertEqual((second["error"], second["sent"]), (None, 2))
        self.assertEqual([title for title, *_ in self.sent], ["Voice note: primera", "Voice note: segunda"])
        self.assertEqual(second["url"], f"https://github.com/{SLUG}/issues/2")
        self.assertEqual(report.pending(self.folder), [])
        self.assertIn(f"Sent: https://github.com/{SLUG}/issues/1", first["saved"].with_suffix("").with_suffix(".sent.md")
                      .read_text(encoding="utf-8"))

    def test_stops_at_the_first_failure_and_keeps_the_rest(self):
        self.deliver("primera", get_token=lambda: None)
        self.deliver("segunda", get_token=lambda: None)

        def second_fails(title, body, slug, key):
            if "segunda" in title:
                raise report.ReportError("GitHub did not answer in time")
            return self.sender(title, body, slug, key)

        res = self.deliver("tercera", sender=second_fails)
        self.assertEqual((res["url"], res["error"], res["sent"]), (None, "GitHub did not answer in time", 1))
        self.assertEqual([title for title, *_ in self.sent], ["Voice note: primera"])
        self.assertEqual(len(report.pending(self.folder)), 2)
        self.assertEqual(report.pending(self.folder)[-1], res["saved"])

    def test_never_raises_whatever_breaks(self):
        def broken_sender(title, body, slug, key):
            raise RuntimeError(f"boom with Bearer {key}")

        def broken_key():
            raise OSError("keychain locked")

        res = self.deliver("nota", sender=broken_sender)
        self.assertIn("RuntimeError", res["error"])
        self.assertNotIn(KEY, res["error"])
        self.assertEqual(report.pending(self.folder), [res["saved"]], "still on disk for the next time")
        res = self.deliver("nota", get_token=broken_key)
        self.assertIn("keychain locked", res["error"])
        self.assertTrue(res["saved"].exists())

    def test_a_folder_that_cannot_be_written_is_an_error_not_an_exception(self):
        blocker = Path(self.dir.name) / "file"
        blocker.write_text("in the way")
        res = report.deliver("nota", {}, "", REPO, blocker / "reports", get_token=lambda: KEY, sender=self.sender)
        self.assertIsNone(res["saved"])
        self.assertTrue(res["error"])
        self.assertEqual((res["url"], res["sent"]), (None, 0))

    def test_with_the_real_sender_a_dead_network_is_a_short_reason(self):
        def sender(title, body, slug, key):
            return report.send(title, body, slug, key, opener=opener_that(urllib.error.URLError("unreachable")))

        res = self.deliver("nota", sender=sender)
        self.assertEqual((res["url"], res["error"], res["sent"]), (None, "no connection to GitHub", 0))


if __name__ == "__main__":
    unittest.main()
