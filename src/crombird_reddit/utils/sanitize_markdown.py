import marko
import html


class _ParseableTextRenderer(marko.HTMLRenderer):
    def render_paragraph(self, element):
        children = self.render_children(element)
        if element._tight:
            return children
        else:
            return f"{children}\n"

    def render_list(self, element):
        return self.render_children(element)

    def render_list_item(self, element):
        return f"{self.render_children(element)}\n"

    def render_quote(self, element):
        return ""  # Skipped

    def render_fenced_code(self, element):
        return ""  # Skipped

    def render_code_block(self, element):
        return ""  # Skipped

    def render_html_block(self, element):
        return ""  # Skipped

    def render_thematic_break(self, element):
        return ""

    def render_heading(self, element):
        return self.render_children(element)

    def render_setext_heading(self, element):
        return self.render_heading(element)

    def render_blank_line(self, element):
        return ""

    def render_link_ref_def(self, element):
        return ""

    def render_emphasis(self, element):
        return self.render_children(element)

    def render_strong_emphasis(self, element):
        return self.render_children(element)

    def render_inline_html(self, element):
        return ""  # Skipped

    def render_plain_text(self, element):
        if isinstance(element.children, str):
            return html.unescape(element.children)
        return self.render_children(element)

    def render_link(self, element):
        return ""  # Skipped

    def render_auto_link(self, element):
        return ""  # Skipped

    def render_image(self, element):
        return ""  # Skipped (images are links too)

    def render_line_break(self, element):
        return "\n"

    def render_code_span(self, element):
        return ""  # Skipped

    def render_raw_text(self, element):
        return html.unescape(element.children)


_markdown = marko.Markdown(renderer=_ParseableTextRenderer)


def sanitize_markdown(text: str) -> str:
    """
    Removes all links and code-blocks from markdown text.
    """
    return _markdown.convert(text)
