import sys, os
import sparekeys

## General

project = 'Spare Keys'
copyright = '2020, Kale Kundert'
version = sparekeys.__version__
release = sparekeys.__version__

master_doc = 'index'
source_suffix = '.rst'
templates_path = ['_templates']
exclude_patterns = ['_build']
html_static_path = ['_static']
default_role = 'any'

## Extensions

extensions = [
        'autoclasstoc',
        'sphinx.ext.autodoc',
        'sphinx.ext.autosummary',
        'sphinx.ext.viewcode',
        'sphinx.ext.intersphinx',
        'sphinx.ext.napoleon',
        'sphinx_rtd_theme',
]
intersphinx_mapping = {
        'python': ('https://docs.python.org/3', None),
}
autosummary_generate = True
autodoc_default_options = {
        'exclude-members': '__dict__,__weakref__,__module__',
}
html_theme = 'sphinx_rtd_theme'
pygments_style = 'sphinx'

