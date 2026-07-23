from rag.chunker import chunk_confluence_storage

PAGE_TITLE = "Beta Pipeline Design"


def test_chunks_are_scoped_to_their_heading_with_breadcrumb():
    html = """
    <h1>Overview</h1>
    <p>This pipeline ingests events from Kafka.</p>
    <h2>Architecture</h2>
    <p>The consumer writes to a staging table.</p>
    <h3>Data Flow</h3>
    <p>Staging rows are deduped then merged into the warehouse.</p>
    """

    chunks = chunk_confluence_storage(html, page_id="123", title=PAGE_TITLE, url="https://x/123")

    assert [c.heading_path for c in chunks] == [
        f"{PAGE_TITLE} > Overview",
        f"{PAGE_TITLE} > Overview > Architecture",
        f"{PAGE_TITLE} > Overview > Architecture > Data Flow",
    ]
    assert "Kafka" in chunks[0].text
    assert "staging table" in chunks[1].text
    assert "warehouse" in chunks[2].text


def test_sibling_headings_do_not_nest_under_each_other():
    html = """
    <h1>Section A</h1>
    <p>Content A.</p>
    <h1>Section B</h1>
    <p>Content B.</p>
    """

    chunks = chunk_confluence_storage(html, page_id="1", title=PAGE_TITLE)

    assert chunks[0].heading_path == f"{PAGE_TITLE} > Section A"
    assert chunks[1].heading_path == f"{PAGE_TITLE} > Section B"


def test_content_before_any_heading_falls_back_to_the_page_title():
    html = "<p>Intro paragraph with no heading above it.</p>"

    chunks = chunk_confluence_storage(html, page_id="1", title=PAGE_TITLE)

    assert len(chunks) == 1
    assert chunks[0].heading_path == PAGE_TITLE
    assert "Intro paragraph" in chunks[0].text


def test_empty_body_produces_no_chunks():
    assert chunk_confluence_storage("", page_id="1", title=PAGE_TITLE) == []
    assert chunk_confluence_storage("<p></p>", page_id="1", title=PAGE_TITLE) == []


def test_long_section_is_split_with_overlap():
    words = [f"word{i}" for i in range(100)]
    html = f"<h1>Long Section</h1><p>{' '.join(words)}</p>"

    chunks = chunk_confluence_storage(
        html, page_id="1", title=PAGE_TITLE, max_words=40, overlap_words=10
    )

    # 100 words at 40/window, 10 overlap -> windows [0:40], [30:70], [60:100]
    assert len(chunks) == 3
    assert chunks[0].order == 0
    assert chunks[-1].order == 2
    # every chunk after the first repeats the last `overlap_words` words of the previous one
    prev_tail = chunks[0].text.split()[-10:]
    next_head = chunks[1].text.split()[:10]
    assert prev_tail == next_head
    # chunk_id encodes page + order for stable upsert/delete keys
    assert chunks[0].chunk_id == "1:0"


def test_chunk_metadata_is_carried_through():
    html = "<h1>Overview</h1><p>Some content.</p>"

    chunks = chunk_confluence_storage(
        html,
        page_id="456",
        title=PAGE_TITLE,
        space_key="ENG",
        url="https://example.atlassian.net/wiki/x/456",
        updated="2026-07-01T00:00:00.000Z",
    )

    chunk = chunks[0]
    assert chunk.page_id == "456"
    assert chunk.space_key == "ENG"
    assert chunk.url == "https://example.atlassian.net/wiki/x/456"
    assert chunk.updated == "2026-07-01T00:00:00.000Z"
