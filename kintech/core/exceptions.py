"""Exception hierarchy for the Kintech parser.

Keeping these distinct (rather than raising bare ValueError/Exception)
lets the CLI and any calling code distinguish "this file isn't a Kintech
Atlas file at all" from "this file IS Kintech format but a specific
record/field couldn't be parsed", which matters for batch-processing many
files where you want to skip-and-log rather than abort.
"""


class KintechParseError(Exception):
    """Base class for all parser-raised errors."""


class HeaderFormatError(KintechParseError):
    """Raised when the file signature/metadata header doesn't match the
    expected Kintech Atlas Output Data File structure."""


class ChannelDefinitionError(KintechParseError):
    """Raised when the embedded JSON channel-definition block is missing,
    malformed, or inconsistent with the column header rows."""


class RecordParseError(KintechParseError):
    """Raised when a single data record/row cannot be parsed. Carries the
    line number and raw text so problems can be pinpointed."""

    def __init__(self, line_number: int, raw_line: str, reason: str):
        self.line_number = line_number
        self.raw_line = raw_line
        self.reason = reason
        super().__init__(f"Line {line_number}: {reason} | raw={raw_line!r}")
