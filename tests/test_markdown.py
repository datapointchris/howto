"""The file shape cards and Labs share: front matter in, title from the first H1."""

from howto import markdown


def test_front_matter_splits_from_the_body():
    meta, body = markdown.split_frontmatter('---\ntags: [a, b]\n---\n\n# Heading\nbody\n')
    assert meta == {'tags': ['a', 'b']}
    assert body.startswith('# Heading')
    assert markdown.split_frontmatter('# Heading\nbody\n') == ({}, '# Heading\nbody\n')


def test_a_scalar_front_matter_block_reads_as_none():
    assert markdown.split_frontmatter('---\nfoo\n---\n# H\n')[0] == {}


def test_the_title_is_the_first_h1():
    assert markdown.first_heading('# The Title\n\ntext\n## Sub\n') == 'The Title'
    assert markdown.first_heading('no heading here\n') == ''


def test_slugify():
    assert markdown.slugify('Find Files Fast!') == 'find-files-fast'
    assert markdown.slugify('  rg/search  ') == 'rgsearch'
