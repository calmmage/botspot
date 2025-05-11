from botspot.utils.formatting_utils import is_html, markdown_to_html


class TestIsHTML:
    def test_plain_text(self):
        """Test that plain text is not detected as HTML"""
        text = "This is plain text without any HTML tags"
        assert not is_html(text)

    def test_with_html_tags(self):
        """Test that text with HTML tags is correctly detected"""
        text = "This contains <b>bold</b> text"
        assert is_html(text)

    def test_with_angle_brackets(self):
        """Test that text with angle brackets but no valid HTML is not detected as HTML"""
        text = "This contains angle brackets like 2 < 3 and 5 > 4"
        assert not is_html(text)

    def test_html_in_code_block(self):
        """Test that HTML tags inside code blocks are ignored"""
        text = "Normal text\n```\n<b>This is in a code block</b>\n```\nMore text"
        assert not is_html(text)

    def test_html_outside_code_block(self):
        """Test that HTML tags outside code blocks are detected"""
        text = "<i>Italic text</i>\n```\nCode block content\n```\n<b>Bold text</b>"
        assert is_html(text)

    def test_empty_string(self):
        """Test that an empty string is not detected as HTML"""
        assert not is_html("")

    def test_complex_math_expressions(self):
        """Test that complex mathematical expressions with angle brackets are not detected as HTML"""
        text = "For all x, if x < y and y > z then x < z. Also, 3 <= 4 and 5 >= 4."
        assert not is_html(text)

    def test_xml_like_syntax(self):
        """Test that XML-like syntax is correctly detected as HTML"""
        text = 'This is <custom-tag attr="value">content</custom-tag>'
        assert is_html(text)

    def test_incomplete_tags(self):
        """Test that incomplete tags are not detected as HTML"""
        text = "This is an incomplete tag: < not closed"
        assert not is_html(text)

    def test_telegram_supported_tags(self):
        """Test that all Telegram supported tags are detected"""
        text = (
            "<b>bold</b> <i>italic</i> <u>underline</u> <s>strike</s>"
            " <code>code</code> <pre>block</pre> <a href='link'>link</a>"
        )
        assert is_html(text)


class TestMarkdownToHTML:
    def test_already_html(self):
        """Test that HTML content is returned as-is"""
        html = "<b>Bold text</b> and <i>italic</i>"
        assert markdown_to_html(html) == html

    def test_bold_text(self):
        """Test converting markdown bold to HTML bold"""
        markdown = "This is **bold** text"
        expected = "This is <b>bold</b> text\n"
        assert markdown_to_html(markdown) == expected

    def test_italic_text(self):
        """Test converting markdown italic to HTML italic"""
        markdown = "This is *italic* text"
        expected = "This is <i>italic</i> text\n"
        assert markdown_to_html(markdown) == expected

    def test_strikethrough(self):
        """Test converting markdown strikethrough to HTML strikethrough"""
        markdown = "This is ~~strikethrough~~ text"
        expected = "This is <s>strikethrough</s> text\n"
        assert markdown_to_html(markdown) == expected

    def test_link(self):
        """Test converting markdown link to HTML link"""
        markdown = "This is a [link](https://example.com)"
        expected = 'This is a <a href="https://example.com">link</a>\n'
        assert markdown_to_html(markdown) == expected

    def test_code_block(self):
        """Test converting markdown code block to HTML pre"""
        markdown = "```python\nprint('Hello World')\n```"
        expected = "<pre language=\"python\">print('Hello World')\n</pre>\n"
        assert markdown_to_html(markdown) == expected

    def test_heading(self):
        """Test converting markdown headings to HTML bold"""
        markdown = "# Heading 1\n## Heading 2\n### Heading 3"
        expected = "<b>HEADING 1</b>\n\n<b>Heading 2</b>\n\n<b>Heading 3</b>\n"
        assert markdown_to_html(markdown) == expected

    def test_unordered_list(self):
        """Test converting markdown unordered list to bullet points"""
        markdown = "- Item 1\n- Item 2\n- Item 3"
        expected = "• Item 1\n• Item 2\n• Item 3\n"
        assert markdown_to_html(markdown) == expected

    def test_ordered_list(self):
        """Test converting markdown ordered list to numbered points"""
        markdown = "1. Item 1\n2. Item 2\n3. Item 3"
        expected = "1. Item 1\n2. Item 2\n3. Item 3\n"
        assert markdown_to_html(markdown) == expected

    def test_image(self):
        """Test converting markdown image to HTML link"""
        markdown = "![Alt text](https://example.com/image.jpg)"
        expected = '<a href="https://example.com/image.jpg">Alt text</a>\n'
        assert markdown_to_html(markdown) == expected

    def test_basic_text_render(self):
        """Test that hashtags are converted to plain text"""
        markdown = "This is a #hashtag test"
        expected = "This is a #hashtag test\n"
        assert markdown_to_html(markdown) == expected

    def test_complex_markdown(self):
        """Test converting complex markdown with multiple elements"""
        markdown = """# Title
        
This is a paragraph with **bold** and *italic* text.

- List item 1
- List item 2

```python
def hello():
    print("Hello World")
```

[Link to example](https://example.com)"""

        # We don't need to test the exact output, just that it converts without errors
        result = markdown_to_html(markdown)
        assert "<b>TITLE</b>" in result
        assert "<b>bold</b>" in result
        assert "<i>italic</i>" in result
        assert "• List item" in result
        assert '<pre language="python">' in result
        assert '<a href="https://example.com">Link to example</a>' in result
