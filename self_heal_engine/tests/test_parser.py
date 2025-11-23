import pytest
from bs4 import BeautifulSoup, Tag

from self_heal_engine.parser import parse_html, get_visible_texts, find_elements_by_attr, css_count


# Sample HTML for testing
SAMPLE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Page</title>
    <style>
        .hidden { display: none; }
        body { font-family: Arial; }
    </style>
</head>
<body>
    <header>
        <h1>Welcome to Test Page</h1>
        <nav>
            <ul>
                <li><a href="#home">Home</a></li>
                <li><a href="#about">About</a></li>
                <li><a href="#contact">Contact</a></li>
            </ul>
        </nav>
    </header>

    <main>
        <section id="home">
            <h2>Home Section</h2>
            <p>This is a paragraph with <strong>bold text</strong> and <em>italic text</em>.</p>
            <p class="hidden">This paragraph is hidden</p>
        </section>

        <section id="about">
            <h2>About Section</h2>
            <div class="content">
                <p>Some content here.</p>
                <img src="image1.jpg" alt="Image 1">
                <img src="image2.jpg" alt="Image 2" data-custom="value">
            </div>
        </section>
    </main>

    <footer>
        <p>&copy; 2023 Test Company</p>
    </footer>

    <script>
        console.log('This should not appear in visible text');
    </script>
</body>
</html>
"""


class TestParseHtml:
    def test_parse_valid_html(self):
        html = "<html><body><h1>Hello</h1></body></html>"
        soup = parse_html(html)
        assert isinstance(soup, BeautifulSoup)
        assert soup.find('h1').text == "Hello"

    def test_parse_empty_string_raises_error(self):
        with pytest.raises(ValueError, match="HTML string cannot be empty"):
            parse_html("")

    def test_parse_whitespace_only_raises_error(self):
        with pytest.raises(ValueError, match="HTML string cannot be empty"):
            parse_html("   \n\t   ")

    def test_parse_none_raises_error(self):
        with pytest.raises(ValueError, match="HTML string cannot be empty"):
            parse_html(None)


class TestGetVisibleTexts:
    def test_get_visible_texts_basic(self):
        soup = parse_html(SAMPLE_HTML)
        texts = get_visible_texts(soup)
        assert isinstance(texts, list)
        assert "Welcome to Test Page" in texts
        assert "Home Section" in texts
        assert "About Section" in texts

    def test_get_visible_texts_excludes_script(self):
        soup = parse_html(SAMPLE_HTML)
        texts = get_visible_texts(soup)
        assert "This should not appear in visible text" not in texts

    def test_get_visible_texts_excludes_hidden_elements(self):
        soup = parse_html(SAMPLE_HTML)
        texts = get_visible_texts(soup)
        assert "This paragraph is hidden" not in texts

    def test_get_visible_texts_includes_nested_text(self):
        soup = parse_html(SAMPLE_HTML)
        texts = get_visible_texts(soup)
        assert "bold text" in texts
        assert "italic text" in texts


class TestFindElementsByAttr:
    def test_find_elements_by_attr_href(self):
        soup = parse_html(SAMPLE_HTML)
        elements = find_elements_by_attr(soup, 'href')
        assert len(elements) == 3
        assert all(isinstance(el, Tag) for el in elements)
        hrefs = [el['href'] for el in elements]
        assert "#home" in hrefs
        assert "#about" in hrefs
        assert "#contact" in hrefs

    def test_find_elements_by_attr_id(self):
        soup = parse_html(SAMPLE_HTML)
        elements = find_elements_by_attr(soup, 'id')
        assert len(elements) == 2
        ids = [el['id'] for el in elements]
        assert "home" in ids
        assert "about" in ids

    def test_find_elements_by_attr_src(self):
        soup = parse_html(SAMPLE_HTML)
        elements = find_elements_by_attr(soup, 'src')
        assert len(elements) == 2
        srcs = [el['src'] for el in elements]
        assert "image1.jpg" in srcs
        assert "image2.jpg" in srcs

    def test_find_elements_by_attr_nonexistent(self):
        soup = parse_html(SAMPLE_HTML)
        elements = find_elements_by_attr(soup, 'nonexistent')
        assert len(elements) == 0


class TestCssCount:
    def test_css_count_by_tag(self):
        soup = parse_html(SAMPLE_HTML)
        count = css_count(soup, 'p')
        assert count == 4  # 4 paragraphs total

    def test_css_count_by_class(self):
        soup = parse_html(SAMPLE_HTML)
        count = css_count(soup, '.hidden')
        assert count == 1

    def test_css_count_by_id(self):
        soup = parse_html(SAMPLE_HTML)
        count = css_count(soup, '#home')
        assert count == 1

    def test_css_count_complex_selector(self):
        soup = parse_html(SAMPLE_HTML)
        count = css_count(soup, 'section h2')
        assert count == 2

    def test_css_count_no_matches(self):
        soup = parse_html(SAMPLE_HTML)
        count = css_count(soup, 'nonexistent')
        assert count == 0
