from .sanitize_markdown import sanitize_markdown


class TestSanitizeMarkdown:
    def test_plain_text_unchanged(self):
        assert sanitize_markdown("Hello world") == "Hello world\n"

    def test_bold_stripped_to_content(self):
        assert sanitize_markdown("**bold text**") == "bold text\n"

    def test_italic_stripped_to_content(self):
        assert sanitize_markdown("*italic text*") == "italic text\n"

    def test_link_removed(self):
        assert sanitize_markdown("[link text](https://example.com)") == "\n"

    def test_inline_code_removed(self):
        assert sanitize_markdown("some `code` here") == "some  here\n"

    def test_fenced_code_block_removed(self):
        text = "```python\ndef hello():\n    pass\n```"
        assert sanitize_markdown(text) == ""

    def test_indented_code_block_removed(self):
        text = "    def hello():\n        pass"
        assert sanitize_markdown(text) == ""

    def test_blockquote_removed(self):
        assert sanitize_markdown("> quoted text") == ""

    def test_html_entities_unescaped(self):
        assert sanitize_markdown("Tom &amp; Jerry") == "Tom & Jerry\n"
        assert sanitize_markdown("2 &lt; 3 &gt; 1") == "2 < 3 > 1\n"

    def test_heading_content_preserved(self):
        assert sanitize_markdown("# Heading") == "Heading"
        assert sanitize_markdown("## Subheading") == "Subheading"

    def test_unordered_list_items_preserved(self):
        text = "- item 1\n- item 2"
        result = sanitize_markdown(text)
        assert "item 1" in result
        assert "item 2" in result

    def test_ordered_list_items_preserved(self):
        text = "1. first\n2. second"
        result = sanitize_markdown(text)
        assert "first" in result
        assert "second" in result

    def test_image_removed(self):
        assert sanitize_markdown("![alt text](image.png)") == "\n"

    def test_autolink_removed(self):
        assert sanitize_markdown("<https://example.com>") == "\n"

    def test_inline_html_tags_removed(self):
        assert sanitize_markdown("text <b>bold</b> more") == "text bold more\n"

    def test_horizontal_rule_removed(self):
        assert sanitize_markdown("---") == ""

    def test_line_break_preserved(self):
        result = sanitize_markdown("line one  \nline two")
        assert "line one" in result
        assert "line two" in result

    def test_mixed_content(self):
        text = "Check out **this** [link](url) and `code`"
        result = sanitize_markdown(text)
        assert "Check out" in result
        assert "this" in result
        assert "link" not in result
        assert "url" not in result
        assert "code" not in result

    def test_empty_string(self):
        assert sanitize_markdown("") == ""

    def test_nested_emphasis(self):
        assert sanitize_markdown("***bold italic***") == "bold italic\n"
