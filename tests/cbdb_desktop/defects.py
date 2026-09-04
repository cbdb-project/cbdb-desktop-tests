"""How this suite records a defect in the shipped build.

A test that has found a real defect must do three things at once: stay
out of the way of a green run (a permanently red suite teaches people to
ignore it), say loudly what is wrong on every run, and *notice when the
defect is fixed* so the marker can be removed.

``pytest.mark.xfail(strict=True)`` does all three -- but on its own it
also swallows any *other* failure of the same test.  A test marked
"expected to fail because the search index is empty" would go on quietly
xfailing if the endpoint started returning 500, or malformed JSON, or a
different wrong answer entirely.

So a defect is signalled by raising :class:`KnownShippedDefect` after the
test has confirmed the *exact* known signature, and the marker is
narrowed to that exception:

    @pytest.mark.xfail(strict=True, raises=KnownShippedDefect, reason=...)
    def test_something(app):
        result = app.json(...)
        if result == the_known_wrong_answer:
            raise KnownShippedDefect("...")
        assert result == the_right_answer

Now: the known defect xfails; anything else fails as a failure; and a fix
turns the test green-unexpectedly, which pytest reports as an error.
"""
from __future__ import annotations


class KnownShippedDefect(AssertionError):
    """Raised when a test confirms a defect already known to be shipped.

    Subclasses AssertionError so the message reads like a normal test
    failure when it does escape (for instance under ``--runxfail``).
    """
