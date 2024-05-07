"""
Adds an expandable Read More section to a text block.

The following rules are followed to determine where the content is split:
- If the text is HTML and contains a special tag (class="expand_here"), then
  that will be where the split occurs.
- If the text is HTML and contains at least two paragraphs, the content will
  be split in two after the first <p> or <div> tag.
- If the text contains two paragraphs separated by two concurrent newlines,
  then split after the first two concurrent newlines.
- else for single paragraph, no need to split just return the content

This is intended for use with a Wagtail RichText field.
"""

import uuid

from bs4 import BeautifulSoup
from django import template

register = template.Library()


@register.filter(name="expand", is_safe=True, needs_autoescape=False)
def expand(text):
    soup = BeautifulSoup(text, "html.parser")

    container_uuid = str(uuid.uuid4())
    pre = post = output = None

    expand_here = soup.find_all(["p", "div"], attrs={"class": "expand-here"}, limit=1)

    if len(expand_here) > 0:
        pre = "".join([str(sib) for sib in expand_here.find_previous_siblings()])
        post = "".join([str(sib) for sib in expand_here.find_next_siblings()])

        output = f'{pre}<p class="expand_here_container"><a href="#" class="expand_here_link" data-expand-body="{container_uuid}">Show More</a></p><div class="expand_here_body" id="exp{container_uuid}">{expand_here[0]!s}{post}</div>'
    elif len(soup.find_all(["p", "div"])) > 1:
        expand_here = soup.find_all(["p", "div"], limit=2)
        pre = str(expand_here[0])
        post = "".join([str(sib) for sib in expand_here[1].find_next_siblings()])

        output = f'<!-- pre -->{pre}<!-- /pre --><p class="expand_here_container"><a href="#" class="expand_here_link fade" data-expand-body="{container_uuid}">Show More</a></p><div class="expand_here_body hide" id="exp{container_uuid}">{expand_here[1]!s}{post}</div>'
    elif len(text.split("\n\n")) > 1:
        (pre, post) = text.split("\n\n", maxsplit=1)

        output = f'{pre}<p class="expand_here_container"><a href="#" class="expand_here_link" data-expand-body="exp{container_uuid}">Show More</a></p><div class="expand_here_body" id="{container_uuid}">{post}</div>'
    else:
        output = text
    return output
