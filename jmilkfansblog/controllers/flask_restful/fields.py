from html.parser import HTMLParser
from flask.ext.restful import fields


class HTMLField(fields.Raw):
    """Define a new fields for filter the HTML tags string."""

    def format(self, value):
        return strip_tags(str(value))


class HTMLStripper(HTMLParser):
    """HTML Parser of Stripper."""

    def __init__(self):
        # Python 3's HTMLParser needs its own constructor to run.
        HTMLParser.__init__(self, convert_charrefs=True)
        self.reset()
        self.fed = []

    def handle_data(self, data_object):
        self.fed.append(data_object)

    def get_data(self):
        return ''.join(self.fed)


def strip_tags(html):
    """Filter the tags string of HTML for data object of Restful api."""

    stripper = HTMLStripper()
    stripper.feed(html)
    stripper.close()

    return stripper.get_data()