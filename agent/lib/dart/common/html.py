def sanitize(text):
    if (text is None):
        return None

    from html import escape
    return escape(str(text))


def unsanitize(text):
    if (text is None):
        return None

    from html import unescape
    return unescape(str(text))
