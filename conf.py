# Configuration file for the Sphinx documentation builder.

# -- Project information

project = 'Searchable transcripts of the UK Covid-19 Inquiry hearings'
copyright = 'Crown copyright, OGL v3.0'
author = 'UK Covid-19 Inquiry (HTMLized by Matthew Somerville)'

# -- General configuration

extensions = [
    "recommonmark",
    "sphinxcontrib.jquery",
]

templates_path = ['_templates']

# -- Options for HTML output

html_theme = 'sphinx_rtd_theme'
html_show_sphinx = False

html_theme_options = {
    'logo_only': False,
    'prev_next_buttons_location': 'bottom',
    'style_external_links': False,
    'style_nav_header_background': '#030f98',
    # Toc options
    'collapse_navigation': False,
    'sticky_navigation': True,
    'navigation_depth': 4,
    'includehidden': True,
    'titles_only': False
}

html_static_path = ['_static']
html_css_files = ['custom.css']

# -- Options for EPUB output
epub_show_urls = 'footnote'
