import html


def sanitize(text):
    if (text is None):
        return None

    return html.escape(text)
