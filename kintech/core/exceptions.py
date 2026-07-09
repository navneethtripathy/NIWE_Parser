class KintechParseError(Exception):
    pass

class HeaderFormatError(KintechParseError):
    pass

class ChannelDefinitionError(KintechParseError):
    pass

class RecordParseError(KintechParseError):

    def __init__(self, line_number: int, raw_line: str, reason: str):
        self.line_number = line_number
        self.raw_line = raw_line
        self.reason = reason
        super().__init__(f'Line {line_number}: {reason} | raw={raw_line!r}')