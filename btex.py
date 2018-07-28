# -*- coding: utf-8 -*-
"""
Publication list plugin for Pelican
===================================
Author: Toni Heittola (toni.heittola@gmail.com)

Pelican plugin to produce publication lists automatically from BibTeX-file.

"""

from pelican import signals, contents
from bs4 import BeautifulSoup
from jinja2 import Template
import copy
from datetime import datetime
from docutils.parsers.rst import directives
import cPickle as pickle
import os
import hashlib
import time
import logging
import collections
import shutil
import yaml
from random import randint
from time import sleep
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)
__version__ = '0.1.0'

btex_settings = {
    'google_scholar': {
        'active': True,
        'fetching_timeout': 60*60*24*7,
        'max_updated_entries_per_batch': 10,
        'fetch_item_timeout': [10, 60],
        'cache_filename': 'google_scholar_cache.cpickle',
    },
    'minified': True,
    'generate_minified': True,
    'use_fontawesome_cdn': True,
    'site-url': '',
    'debug_processing': False
}

btex_publication_grouping = {
    0: {
        'id': 0,
        'name': 'Books',
        'label': 'Book',
        'label_short': 'Book',
        'entry_types': ['book', 'phdthesis'],
        'css': 'label label-primary',
    },
    1: {
        'id': 1,
        'name': 'Phd thesis',
        'label': 'Phd',
        'label_short': 'Phd',
        'entry_types': ['phdthesis'],
        'css': 'label label-primary',
    },
    2: {
        'id': 2,
        'name': 'Journal articles',
        'label': 'Journal',
        'label_short': 'Journal',
        'entry_types': ['article'],
        'css': 'label label-success',
    },
    3: {
        'id': 3,
        'name': 'Book chapters',
        'label': 'Chapter',
        'label_short': 'Chapter',
        'entry_types': ['inbook', 'incollection'],
        'css': 'label label-success',
    },
    4: {
        'id': 4,
        'name': 'Conference papers',
        'label': 'Conference',
        'label_short': 'Conf',
        'entry_types': ['conference', 'inproceedings', 'proceedings', 'workshop', 'symposium'],
        'css': 'label label-info',
    },
    5: {
        'id': 5,
        'name': 'Patents',
        'label': 'Patent',
        'label_short': 'Patent',
        'entry_types': ['patent'],
        'css': 'label label-danger',
    },
    6: {
        'id': 6,
        'name': 'Master thesis',
        'label': 'Thesis',
        'label_short': 'Thesis',
        'entry_types': ['mastersthesis'],
        'css': 'label label-warning',
    },
    7: {
        'id': 7,
        'name': 'Other publications',
        'label': 'Other',
        'label_short': 'Other',
        'entry_types': ['techreport', 'manual', 'unpublished'],
        'css': 'label label-default',
    },
    8: {
        'id': 8,
        'name': 'Projects',
        'label': 'Project',
        'label_short': 'Project',
        'entry_types': ['studentproject'],
        'css': 'label label-info',
    },
}


def process_link(text, delimiter='##'):
    if text is not None:
        tmp = text.split(delimiter)
        if len(tmp) == 2:
            return {'url': tmp[0], 'title': tmp[1]}
        else:
            return {'url': text}


def parse_bibtex_file(src_filename):
    try:
        from StringIO import StringIO
    except ImportError:
        from io import StringIO

    try:
        from pybtex.database.input.bibtex import Parser
        from pybtex.database.output.bibtex import Writer
        from pybtex.database import BibliographyData, PybtexError, Entry
        from pybtex.backends import html
        import pybtex.plugin
        import btex_style

    except ImportError:
        logger.warning('`pelican_btex` failed to import `pybtex`')
        return
    try:
        bibdata_all = Parser().parse_file(src_filename)
    except PybtexError as e:
        logger.warning('`pelican_btex` failed to parse file %s: %s' % (
            src_filename,
            str(e)))
        return

    publications = []
    # format entries
    style = btex_style.Style()

    formatted_entries = style.format_entries(bibdata_all.entries.values()) #bibdata_all.entries.itervalues()) #
    html_backend = html.Backend()

    for formatted_entry in formatted_entries:
        item = {}
        key = formatted_entry.key
        entry = bibdata_all.entries[key]

        entry_type = entry.type
        subtype = entry.fields.get('_subtype', None)
        if subtype is not None:
            entry_type = subtype

        item['key'] = key
        item['entry'] = entry
        item['formatted_entry'] = formatted_entry

        item['year'] = entry.fields.get('year')
        title = entry.fields.get('title', None)
        title = title.replace('{', '')
        title = title.replace('}', '')

        item['title'] = title
        item['authors'] = entry.persons['author']
        item['abstract'] = entry.fields.get('abstract', None)
        item['keywords'] = entry.fields.get('keywords', None)

        authors = []
        for author in item['authors']:
            authors.append(author.first()[0]+' ' + ' '.join(author.last()))

        if len(authors) > 1:
            item['authors_text'] = ", ".join(authors[:-1]) + " and " + authors[-1]
        else:
            item['authors_text'] = authors[0]
        if '\\' in item['authors_text']:
            from pylatexenc.latexwalker import LatexWalker
            from pylatexenc.latex2text import LatexNodes2Text
            item['authors_text'] = LatexNodes2Text().nodelist_to_text(LatexWalker(item['authors_text']).get_latex_nodes()[0])

        # Type fields
        item['type'] = entry_type
        item['type_label'] = entry_type
        item['type_label_short'] = entry_type
        item['type_label_css'] = 'label label-default'
        item['type_group_id'] = None
        item['type_group_name'] = None

        for group_id in btex_publication_grouping:
            group = btex_publication_grouping[group_id]
            if entry_type in group['entry_types']:
                item['type_label'] = group['label']
                item['type_label_short'] = group['label_short']
                item['type_label_css'] = group['css']
                item['type_group_id'] =  group_id
                item['type_group_name'] = group['name']
                break

        # Special fields
        item['award'] = entry.fields.get('_award', None)
        item['pdf'] = entry.fields.get('_pdf', None)
        item['demo'] = entry.fields.get('_demo', None)
        item['demo_external'] = entry.fields.get('_demo_external', None)
        item['toolbox'] = entry.fields.get('_toolbox', None)
        item['clients'] = entry.fields.get('_clients', None)
        item['slides'] = entry.fields.get('_slides', None)
        item['poster'] = entry.fields.get('_poster', None)
        item['video'] = entry.fields.get('_video', None)

        item['school'] = entry.fields.get('_school', None)
        item['clients'] = entry.fields.get('_clients', None)
        item['course'] = entry.fields.get('_course', None)

        # Link fields
        item['webpublication'] = process_link(entry.fields.get('_webpublication', None))
        item['link1'] = process_link(entry.fields.get('_link1', None))
        item['link2'] = process_link(entry.fields.get('_link2', None))
        item['link3'] = process_link(entry.fields.get('_link3', None))
        item['link4'] = process_link(entry.fields.get('_link4', None))

        item['data1'] = process_link(entry.fields.get('_data1', None))
        item['data2'] = process_link(entry.fields.get('_data2', None))

        item['code1'] = process_link(entry.fields.get('_code1', None))
        item['code2'] = process_link(entry.fields.get('_code2', None))
        item['code3'] = process_link(entry.fields.get('_code3', None))
        item['code4'] = process_link(entry.fields.get('_code4', None))
        item['code5'] = process_link(entry.fields.get('_code5', None))

        item['git1'] = process_link(entry.fields.get('_git1', None))
        item['git2'] = process_link(entry.fields.get('_git2', None))
        item['git3'] = process_link(entry.fields.get('_git3', None))
        item['git4'] = process_link(entry.fields.get('_git4', None))
        item['git5'] = process_link(entry.fields.get('_git5', None))

        item['_authors'] = entry.fields.get('_authors', None)
        item['_affiliations'] = entry.fields.get('_affiliations', None)
        item['_affiliations_long'] = entry.fields.get('_affiliations_long', None)

        # extra
        item['_extra_info'] = entry.fields.get('_extra_info', None)
        item['_footnote'] = entry.fields.get('_footnote', None)
        item['_bio'] = entry.fields.get('_bio', None)
        item['_profile_photo'] = entry.fields.get('_profile_photo', None)

        # System characteristics
        item['_system_input'] = entry.fields.get('_system_input', None)
        item['_system_sampling_rate'] = entry.fields.get('_system_sampling_rate', None)
        item['_system_data_augmentation'] = entry.fields.get('_system_data_augmentation', None)
        item['_system_features'] = entry.fields.get('_system_features', None)
        item['_system_classifier'] = entry.fields.get('_system_classifier', None)
        item['_system_decision_making'] = entry.fields.get('_system_decision_making', None)

        # render the bibtex string for the entry
        bib_buf = StringIO()
        entry_dict = copy.deepcopy(entry.fields._dict)

        entry_keys = entry_dict.keys()
        for entry_key in entry_keys:
            if entry_key.startswith('_'):
                del entry_dict[entry_key]

        public_entry = Entry(type_=entry.type, fields=entry_dict, persons=entry.persons)
        bibdata_this = BibliographyData(entries={key: public_entry})
        Writer().write_stream(bibdata_this, bib_buf)

        item['text'] = formatted_entry.text.render(html_backend)
        item['bibtex'] = bib_buf.getvalue()
        item['public_entry'] = public_entry

        publications.append(item)

    return publications


def boolean(argument):
    """Conversion function for yes/no True/False."""
    value = directives.choice(argument, ('yes', 'true', 'True', 'no', 'False'))
    return value in ('yes', 'True', 'true')


def boolean_string(value):
    if value:
        return "true"
    else:
        return "false"


def get_attribute(attrs, name, default = None):
    if 'data-'+name in attrs:
        return attrs['data-'+name]
    else:
        return default


def get_default_template(options):
    template = ''
    if options['stats']:
        template += '<div class="panel panel-default"><div class="panel-body">'
        template += 'Publications: {{ meta.publications }} <small><span class="text-muted">( {{ meta.types_html_list}} )</span></small>'
        template += '<br>'
        template += 'Cites: {{meta.cites}} '
        template += '<small>'
        template += '<span class="text-muted">( '
        if options['scholar-link']:
            template += 'according to <a href="' + options['scholar-link'] + '" target="_blank">Google Scholar</a>, '
        template += 'Updated {{meta.cite_update_string}}'
        template += ')</span>'
        template += '</small>'
        template += '</div></div>'

    if options['template'] == 'publications':

        template += """
        <div class="panel-group" id="accordion" role="tablist" aria-multiselectable="true">
            {% for year, year_group in publications|groupby('year')|sort(reverse=True) %}
                <h3>{{year}}</h3>
                {% for item in year_group|sort(attribute='year') %}
                    <div class="panel publication-item" id="{{ item.key }}" style="box-shadow: none">
                        <div class="panel-heading" role="tab" id="heading{{ item.key }}">
                            <div class="row">
                                <div class="col-md-1">
                                    <span class="{{ item.type_label_css }}">{{ item.type_label_short }}</span>
                                </div>
                                <div class="col-xs-8">
                                    <p style="text-align:left">
                                    {{item.text}}
                                    {% if item.award %}<span class="label label-success">{{item.award}}</span>{% endif %}
                                    {% if item.cites %}
                                    <span style="padding-left:5px">
                                    <span title="Number of citations" class="badge">{{ item.cites }} {% if item.cites==1 %}cite{% else %}cites{% endif %}</span>
                                    </span>
                                    {% endif %}
                                    </p>
                                    <button type="button" class="btn btn-default btn-xs" data-toggle="collapse" data-parent="#accordion" href="#collapse{{ item.key }}" aria-expanded="true" aria-controls="collapse{{ item.key }}">
                                    <i class="fa fa-caret-down"></i> Read more...</button>
                                </div>
                                <div class="col-xs-3">
                                    <div class="btn-group">
                                        <button type="button" class="btn btn-xs btn-danger" data-toggle="modal" data-target="#bibtex{{ item.key }}"><i class="fa fa-file-text-o"></i> Bib</button>
                                        {% if item.pdf %}
                                            <a href="{{item.pdf}}" class="btn btn-xs btn-warning btn-btex" rel="tooltip" title="Download pdf" data-placement="bottom"><i class="fa fa-file-pdf-o fa-1x"></i> PDF</a>
                                        {% endif %}
                                        {% if item.demo %}
                                            <a href="{{item.demo}}" class="btn btn-xs btn-primary iframe-demo btn-btex" rel="tooltip" title="Demo" data-placement="bottom"><i class="fa fa-headphones"></i> Demo</a>
                                        {% endif %}
                                        {% if item.demo_external %}
                                            <a href="{{item.demo_external}}" target="_blank" class="btn btn-xs btn-primary btn-btex" rel="tooltip" title="Demo" data-placement="bottom"><i class="fa fa-headphones"></i> Demo</a>
                                        {% endif %}
                                        {% if item.toolbox %}
                                            <a href="{{item.toolbox}}" class="btn btn-xs btn-success btn-btex" rel="tooltip" title="Toolbox" data-placement="bottom"><i class="fa fa-file-code-o"></i> Toolbox</a>
                                        {% endif %}
                                        {% if item.data1 %}
                                            <a href="{{item.data1.url}}" class="btn btn-xs btn-info btn-btex" rel="tooltip" title="{{item.data1.title}}" data-placement="bottom"><i class="fa fa-database"></i></a>
                                        {% endif %}
                                        {% if item.data2 %}
                                            <a href="{{item.data2.url}}" class="btn btn-xs btn-info btn-btex" rel="tooltip" title="{{item.data2.title}}" data-placement="bottom"><i class="fa fa-database"></i></a>
                                        {% endif %}
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div id="collapse{{ item.key }}" class="panel-collapse collapse" role="tabpanel" aria-labelledby="heading{{ item.key }}">
                            <div class="panel-body well well-sm">
                                <h4>{{item.title}}</h4>
                                {% if item.abstract %}
                                    <h5>Abstract</h5>
                                    <p class="text-justify">{{item.abstract}}</p>
                                {% endif %}
                                {% if item.keywords %}
                                    <h5>Keywords</h5>
                                    <p class="text-justify">{{item.keywords}}</p>
                                {% endif %}
                                {% if item.award %}
                                    <p><strong>Awards:</strong> {{item.award}}</p>
                                {% endif %}
                                {% if item.cites %}
                                    <p><strong>Cites:</strong> {{item.cites}} (<a href="{{ item.citation_url }}" target="_blank">see at Google Scholar</a>)</p>
                                {% endif %}
                                <div class="btn-group">
                                    <button type="button" class="btn btn-sm btn-danger" data-toggle="modal" data-target="#bibtex{{ item.key }}"><i class="fa fa-file-text-o"></i> Bibtex</button>
                                    {% if item.pdf %}
                                        <a href="{{item.pdf}}" class="btn btn-sm btn-warning btn-btex2" rel="tooltip" title="Download pdf" data-placement="bottom"><i class="fa fa-file-pdf-o fa-1x"></i> PDF</a>
                                    {% endif %}
                                    {% if item.slides %}
                                        <a href="{{item.slides}}" class="btn btn-sm btn-info btn-btex2" rel="tooltip" title="Download slides" data-placement="bottom"><i class="fa fa-file-powerpoint-o"></i> Slides</a>
                                    {% endif %}
                                    {% if item.poster %}
                                        <a href="{{item.poster}}" class="btn btn-sm btn-info btn-btex2" rel="tooltip" title="Download poster" data-placement="bottom"><i class="fa fa-picture-o"></i> Poster</a>
                                    {% endif %}
                                    {% if item.webpublication %}
                                        <a href="{{item.webpublication.url}}" class="btn btn-sm btn-info btn-btex2" title="{{item.webpublication.title}}"><i class="fa fa-book"></i> Web publication</a>
                                    {% endif %}
                                </div>
                                <div class="btn-group">
                                    {% if item.toolbox %}
                                        <a href="{{item.toolbox}}" class="btn btn-sm btn-success btn-btex2" rel="tooltip" title="Toolbox" data-placement="bottom"><i class="fa fa-file-code-o"></i> Toolbox</a>
                                    {% endif %}
                                    {% if item.data1 %}
                                        <a href="{{item.data1.url}}" class="btn btn-sm btn-info btn-btex2" rel="tooltip" title="Toolbox" data-placement="bottom"><i class="fa fa-database"></i> {{item.data1.title}}</a>
                                    {% endif %}
                                    {% if item.data2 %}
                                        <a href="{{item.data2.url}}" class="btn btn-sm btn-info btn-btex2" rel="tooltip" title="Toolbox" data-placement="bottom"><i class="fa fa-database"></i> {{item.data2.title}}</a>
                                    {% endif %}
                                    {% if item.code1 %}
                                        <a href="{{item.code1.url}}" class="btn btn-sm btn-success btn-btex2" title="{{item.code1.title}}"><i class="fa fa-file-code-o"></i> {{item.code1.title}}</a>
                                    {% endif %}
                                    {% if item.code2 %}
                                        <a href="{{item.code2.url}}" class="btn btn-sm btn-success btn-btex2" title="{{item.code2.title}}"><i class="fa fa-file-code-o"></i> {{item.code2.title}}</a>
                                    {% endif %}
                                    {% if item.demo %}
                                        <a href="{{item.demo}}" class="btn btn-sm btn-primary iframe-demo btn-btex2" rel="tooltip" title="Demo" data-placement="bottom"><i class="fa fa-headphones"></i> Demo</a>
                                    {% endif %}
                                    {% if item.demo_external %}
                                        <a href="{{item.demo_external}}" target="_blank" class="btn btn-sm btn-primary btn-btex2" rel="tooltip" title="Demo" data-placement="bottom"><i class="fa fa-headphones"></i> Demo</a>
                                    {% endif %}
                                    {% if item.link1 %}
                                        <a href="{{item.link1.url}}" class="btn btn-sm btn-info btn-btex2" title="{{item.link1.title}}"><i class="fa fa-external-link-square"></i> {{item.link1.title}}</a>
                                    {% endif %}
                                    {% if item.link2 %}
                                        <a href="{{item.link2.url}}" class="btn btn-sm btn-info btn-btex2" title="{{item.link2.title}}"><i class="fa fa-external-link-square"></i> {{item.link2.title}}</a>
                                    {% endif %}
                                    {% if item.link3 %}
                                        <a href="{{item.link3.url}}" class="btn btn-sm btn-info btn-btex2" title="{{item.link3.title}}"><i class="fa fa-external-link-square"></i> {{item.link3.title}}</a>
                                    {% endif %}
                                    {% if item.link4 %}
                                        <a href="{{item.link4.url}}" class="btn btn-sm btn-info btn-btex2" title="{{item.link4.title}}"><i class="fa fa-external-link-square"></i> {{item.link4.title}}</a>
                                    {% endif %}
                                </div>
                            </div>
                        </div>
                    </div>
                    <!-- Modal -->
                    <div class="modal fade" id="bibtex{{item.key}}" tabindex="-1" role="dialog" aria-labelledby="bibtex{{item.key}}label" aria-hidden="true">
                        <div class="modal-dialog">
                            <div class="modal-content">
                                <div class="modal-header">
                                    <button type="button" class="close" data-dismiss="modal"><span class="glyphicon glyphicon-remove-sign" aria-hidden="true"></span><span class="sr-only">Close</span></button>
                                    <h4 class="modal-title" id="bibtex{{item.key}}label">{{item.title}}</h4>
                                </div>
                                <div class="modal-body">
                                    <pre>{{item.bibtex}}</pre>
                                </div>
                                <div class="modal-footer">
                                    <button type="button" class="btn btn-default" data-dismiss="modal">Close</button>
                                </div>
                            </div>
                        </div>
                    </div>
                {% endfor %}
            {% endfor %}
        </div>
        """
    elif options['template'] == 'latest':

        template += """
    {% for year, year_group in publications|groupby('year')|sort(reverse=True) %}
        {% if (year|int)>(first_visible_year|int) %}
            <h3>{{(year|int)}}</h3>
            {% for item in year_group|sort(attribute='year') %}
                <div class="row publication-item">
                    <div class="col-md-1">
                        <span class="{{ item.type_label_css }}">{{ item.type_label_short }}</span>
                    </div>
                    <div class="col-xs-8">
                        {{item.text}}
                        {% if item.award %}<span class="label label-success">{{item.award}}</span> {% endif %}
                        <a href="{{target_page}}#{{item.key}}" title="Read more..." style="text-decoration:none;border-bottom:0;" ><i class="fa fa-arrow-circle-right"></i></a>
                    </div>
                    <div class="col-xs-3">
                        <div class="btn-group">
                            <button type="button" class="btn btn-xs btn-danger" data-toggle="modal" data-target="#bibtex{{ item.key }}"><i class="fa fa-file-text-o"></i> Bib</button>
                            {% if item.pdf %}
                                <a href="{{item.pdf}}" class="btn btn-xs btn-warning btn-btex" rel="tooltip" title="Download pdf" data-placement="bottom"><i class="fa fa-file-pdf-o fa-1x"></i> PDF</a>
                            {% endif %}
                            {% if item.demo %}
                                <a href="{{item.demo}}" class="btn btn-xs btn-primary iframe-demo btn-btex" rel="tooltip" title="Demo" data-placement="bottom"><i class="fa fa-headphones"></i> Demo</a>
                            {% endif %}
                            {% if item.demo_external %}
                                <a href="{{item.demo_external}}" target="_blank" class="btn btn-xs btn-primary btn-btex" rel="tooltip" title="Demo" data-placement="bottom"><i class="fa fa-headphones"></i> Demo</a>
                            {% endif %}
                            {% if item.toolbox %}
                                <a href="{{item.toolbox}}" class="btn btn-xs btn-success btn-btex" rel="tooltip" title="Toolbox" data-placement="bottom"><i class="fa fa-file-code-o"></i> Toolbox</a>
                            {% endif %}
                            {% if item.data1 %}
                                <a href="{{item.data1.url}}" class="btn btn-xs btn-info btn-btex" rel="tooltip" title="{{item.data1.title}}" data-placement="bottom"><i class="fa fa-database"></i></a>
                            {% endif %}
                            {% if item.data2 %}
                                <a href="{{item.data2.url}}" class="btn btn-xs btn-info btn-btex" rel="tooltip" title="{{item.data2.title}}" data-placement="bottom"><i class="fa fa-database"></i></a>
                            {% endif %}
                            {% if item.code1 %}
                                <a href="{{item.code1.url}}" class="btn btn-xs btn-success btn-btex" rel="tooltip" title="{{item.code1.title}}" data-placement="bottom"><i class="fa fa-file-code-o"></i></a>
                            {% endif %}
                            {% if item.code2 %}
                                <a href="{{item.code2.url}}" class="btn btn-xs btn-success btn-btex" rel="tooltip" title="{{item.code2.title}}" data-placement="bottom"><i class="fa fa-file-code-o"></i></a>
                            {% endif %}
                        </div>
                    </div>
                </div>
                <!-- Modal -->
                <div class="modal fade" id="bibtex{{item.key}}" tabindex="-1" role="dialog" aria-labelledby="bibtex{{item.key}}label" aria-hidden="true">
                    <div class="modal-dialog">
                        <div class="modal-content">
                            <div class="modal-header">
                                <button type="button" class="close" data-dismiss="modal"><span class="glyphicon glyphicon-remove-sign" aria-hidden="true"></span><span class="sr-only">Close</span></button>
                                <h4 class="modal-title" id="bibtex{{item.key}}label">{{item.title}}</h4>
                            </div>
                            <div class="modal-body">
                                <pre>{{item.bibtex}}</pre>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-default" data-dismiss="modal">Close</button>
                            </div>
                        </div>
                    </div>
                </div>
            {% endfor %}
        {% endif %}
    {% endfor %}
        """
    elif options['template'] == 'supervisions':

        template += """
    <div class="panel-group" id="accordion" role="tablist" aria-multiselectable="true">
        {% for year, year_group in publications|groupby('year')|sort(reverse=True) %}
            <h3>{{year}}</h3>
            {% for item in year_group|sort(attribute='year') %}
                <div class="panel publication-item" id="{{ item.key }}" style="box-shadow: none">
                    <div class="panel-heading" role="tab" id="heading{{ item.key }}">
                        <div class="row">
                            <div class="col-md-1">
                                <span class="{{ item.type_label_css }}">{{ item.type_label_short }}</span>
                            </div>
                            <div class="col-xs-8">
                                {{item.text}}
                                {% if item.award %}<span class="label label-success">{{item.award}}</span> {% endif %}
                                <br><button type="button" class="btn btn-default btn-xs" data-toggle="collapse" data-parent="#accordion" href="#collapse{{ item.key }}" aria-expanded="true" aria-controls="collapse{{ item.key }}">
                                <i class="fa fa-caret-down"></i> Read more...</button>
                            </div>
                            <div class="col-xs-3">
                                <div class="btn-group">
                                    {% if item.type!="studentproject" %}
                                        <button type="button" class="btn btn-xs btn-danger" data-toggle="modal" data-target="#bibtex{{ item.key }}"><i class="fa fa-file-text-o"></i> Bib</button>
                                    {% endif %}
                                    {% if item.pdf %}
                                        <a href="{{item.pdf}}" class="btn btn-xs btn-warning btn-btex" rel="tooltip" title="Download pdf" data-placement="bottom"><i class="fa fa-file-pdf-o fa-1x"></i> PDF</a>
                                    {% endif %}
                                    {% if item.demo %}
                                        <a href="{{item.demo}}" class="btn btn-xs btn-primary iframe-demo btn-btex" rel="tooltip" title="Demo" data-placement="bottom"><i class="fa fa-headphones"></i> Demo</a>
                                    {% endif %}
                                    {% if item.demo_external %}
                                        <a href="{{item.demo_external}}" target="_blank" class="btn btn-xs btn-primary btn-btex" rel="tooltip" title="Demo" data-placement="bottom"><i class="fa fa-headphones"></i> Demo</a>
                                    {% endif %}
                                </div>
                            </div>
                        </div>
                    </div>
                    <div id="collapse{{ item.key }}" class="panel-collapse collapse" role="tabpanel" aria-labelledby="heading{{ item.key }}">
                        <div class="panel-body well well-sm">
                            <h4>{{item.title}}</h4>
                            {% if item.abstract %}
                                <h5>Abstract</h5>
                                <p class="text-justify">{{item.abstract}}</p>
                            {% endif %}
                            {% if item.keywords %}
                                <h5>Keywords</h5>
                                <p class="text-justify">{{item.keywords}}</p>
                            {% endif %}
                            {% if item.clients %}
                                <h5>Clients</h5>
                                <p class="text-justify">{{item.clients}}</p>
                            {% endif %}
                            <div class="btn-group">
                                {% if item.type!="studentproject" %}
                                    <button type="button" class="btn btn-sm btn-danger" data-toggle="modal" data-target="#bibtex{{ item.key }}"><i class="fa fa-file-text-o"></i> Bibtex</button>
                                {% endif %}
                                {% if item.pdf %}
                                    <a href="{{item.pdf}}" class="btn btn-sm btn-warning btn-btex2" rel="tooltip" title="Download pdf" data-placement="bottom"><i class="fa fa-file-pdf-o fa-1x"></i> PDF</a>
                                {% endif %}
                                {% if item.slides %}
                                    <a href="{{item.slides}}" class="btn btn-sm btn-info btn-btex2" rel="tooltip" title="Download slides" data-placement="bottom"><i class="fa fa-file-powerpoint-o"></i> Slides</a>
                                {% endif %}
                                {% if item.poster %}
                                    <a href="{{item.poster}}" class="btn btn-sm btn-info btn-btex2" rel="tooltip" title="Download poster" data-placement="bottom"><i class="fa fa-picture-o"></i> Poster</a>
                                {% endif %}
                                {% if item.webpublication %}
                                    <a href="{{item.webpublication.url}}" class="btn btn-sm btn-info btn-btex2" title="{{item.webpublication.title}}"><i class="fa fa-book"></i> Web publication</a>
                                {% endif %}
                            </div>
                            <div class="btn-group">
                                {% if item.toolbox %}
                                    <a href="{{item.toolbox}}" class="btn btn-sm btn-success btn-btex2" rel="tooltip" title="Toolbox" data-placement="bottom"><i class="fa fa-file-code-o"></i> Toolbox</a>
                                {% endif %}
                                {% if item.data1 %}
                                    <a href="{{item.data1.url}}" class="btn btn-sm btn-info btn-btex2" rel="tooltip" title="Toolbox" data-placement="bottom"><i class="fa fa-database"></i> {{item.data1.title}}</a>
                                {% endif %}
                                {% if item.data2 %}
                                    <a href="{{item.data2.url}}" class="btn btn-sm btn-info btn-btex2" rel="tooltip" title="Toolbox" data-placement="bottom"><i class="fa fa-database"></i> {{item.data2.title}}</a>
                                {% endif %}
                                {% if item.code1 %}
                                    <a href="{{item.code1.url}}" class="btn btn-sm btn-success btn-btex2" title="{{item.code1.title}}"><i class="fa fa-file-code-o"></i> {{item.code1.title}}</a>
                                {% endif %}
                                {% if item.code2 %}
                                    <a href="{{item.code2.url}}" class="btn btn-sm btn-success btn-btex2" title="{{item.code2.title}}"><i class="fa fa-file-code-o"></i> {{item.code2.title}}</a>
                                {% endif %}
                                {% if item.demo %}
                                    <a href="{{item.demo}}" class="btn btn-sm btn-primary iframe-demo btn-btex2" rel="tooltip" title="Demo" data-placement="bottom"><i class="fa fa-headphones"></i> Demo</a>
                                {% endif %}
                                {% if item.demo_external %}
                                    <a href="{{item.demo_external}}" target="_blank" class="btn btn-sm btn-primary btn-btex2" rel="tooltip" title="Demo" data-placement="bottom"><i class="fa fa-headphones"></i> Demo</a>
                                {% endif %}
                                {% if item.link1 %}
                                    <a href="{{item.link1.url}}" class="btn btn-sm btn-info btn-btex2" title="{{item.link1.title}}"><i class="fa fa-external-link-square"></i> {{item.link1.title}}</a>
                                {% endif %}
                                {% if item.link2 %}
                                    <a href="{{item.link2.url}}" class="btn btn-sm btn-info btn-btex2" title="{{item.link2.title}}"><i class="fa fa-external-link-square"></i> {{item.link2.title}}</a>
                                {% endif %}
                                {% if item.link3 %}
                                    <a href="{{item.link3.url}}" class="btn btn-sm btn-info btn-btex2" title="{{item.link3.title}}"><i class="fa fa-external-link-square"></i> {{item.link3.title}}</a>
                                {% endif %}
                                {% if item.link4 %}
                                    <a href="{{item.link4.url}}" class="btn btn-sm btn-info btn-btex2" title="{{item.link4.title}}"><i class="fa fa-external-link-square"></i> {{item.link4.title}}</a>
                                {% endif %}
                            </div>                                                        
                        </div>
                    </div>
                </div>
                <!-- Modal -->
                <div class="modal fade" id="bibtex{{item.key}}" tabindex="-1" role="dialog" aria-labelledby="bibtex{{item.key}}label" aria-hidden="true">
                  <div class="modal-dialog">
                    <div class="modal-content">
                      <div class="modal-header">
                        <button type="button" class="close" data-dismiss="modal"><span class="glyphicon glyphicon-remove-sign" aria-hidden="true"></span><span class="sr-only">Close</span></button>
                        <h4 class="modal-title" id="bibtex{{item.key}}label">{{item.title}}</h4>
                      </div>
                      <div class="modal-body">
                        <pre>{{item.bibtex}}</pre>
                      </div>
                      <div class="modal-footer">
                        <button type="button" class="btn btn-default" data-dismiss="modal">Close</button>
                      </div>
                    </div>
                  </div>
                </div>
            {% endfor %}
        {% endfor %}
    </div>
        """
    elif options['template'] == 'minimal':

        template += """
            {% for year, year_group in publications|groupby('year')|sort(reverse=True) %}
                {% if (year|int)>(first_visible_year|int) %}
                    <strong class="text-muted">{{year}}</strong>
                    {% for item in year_group|sort(attribute='year') %}
                        <div class="row">
                            <div class="col-md-1 col-sm-2">
                                <span class="{{ item.type_label_css }}">{{ item.type_label_short }}</span>
                            </div>
                            <div class="col-md-11 col-sm-10">
                                <p style="text-align:left">{{item.text}}
                                {% if item.award %}<span class="label label-success">{{item.award}}</span>{% endif %}
                                {% if item.cites %}
                                <span title="Number of citations" class="badge">{{ item.cites }} {% if item.cites==1 %}cite{% else %}cites{% endif %}</span>
                                {% endif %}
                                {% if item.pdf %}
                                    <a href="{{item.pdf}}" style="text-decoration:none;border-bottom:0;padding-bottom:5px" rel="tooltip" title="Download pdf" data-placement="bottom"><span class="glyphicon glyphicon-file"></span></a>
                                {% endif %}
                                </p>
                            </div>
                        </div>
                    {% endfor %}
                {% endif %}
            {% endfor %}
        """
    elif options['template'] == 'news':
        template += """
        <div class="list-group btex-news-container">
        {% for item in publications %}
            {% if loop.index <= item_count %}
            <a class="list-group-item" href="{{target_page}}#{{item.key}}" title="Read more...">
                <div class="row">
                    <div class="col-sm-12">
                        <h4 class="list-group-item-heading">{{item.title}}</h4>
                    </div>
                </div>
                <div class="row">
                    <div class="col-xs-2">
                        <span class="{{ item.type_label_css }}">{{ item.type_label_short }}</span>
                    </div>
                    <div class="col-xs-10">
                        <span class="authors">{{item.authors_text}}</span>
                    </div>
                </div>
            </a>
            {% endif %}
        {% endfor %}
        </div>
        """

    return template


def get_default_item_template(options):
    template = ''
    if options['template'] == 'default':
        template += """
            <div class="panel panel-default">
                <span class="label label-default" style="padding-top:0.4em;margin-left:0em;margin-top:0em;">Publication<a name="{{ item.key }}"></a></span>
                <div class="panel-body">
                    <div class="row">
                        <div class="col-md-9">
                            <p style="text-align:left">
                            {{item.text}}
                            {% if item.award %}<span class="label label-success">{{item.award}}</span>{% endif %}
                            {% if item.cites %}
                            <span style="padding-left:5px">
                            <span title="Number of citations" class="badge">{{ item.cites }} {% if item.cites==1 %}cite{% else %}cites{% endif %}</span>
                            </span>
                            {% endif %}
                            </p>
                        </div>
                        <div class="col-md-3">
                            <div class="btn-group pull-right">
                                <button type="button" class="btn btn-xs btn-danger" data-toggle="modal" data-target="#bibtex{{ item.key }}{{ uuid }}"><i class="fa fa-file-text-o"></i> Bib</button>
                                {% if item.pdf %}
                                    <a href="{{item.pdf}}" class="btn btn-xs btn-warning btn-btex" rel="tooltip" title="Download pdf" data-placement="bottom"><i class="fa fa-file-pdf-o fa-1x"></i> PDF</a>
                                {% endif %}
                                {% if item.demo %}
                                    <a href="{{item.demo}}" class="btn btn-xs btn-primary iframe-demo btn-btex" rel="tooltip" title="Demo" data-placement="bottom"><i class="fa fa-headphones"></i></a>
                                {% endif %}
                                {% if item.demo_external %}
                                    <a href="{{item.demo_external}}" target="_blank" class="btn btn-xs btn-primary btn-btex" rel="tooltip" title="Demo" data-placement="bottom"><i class="fa fa-headphones"></i></a>
                                {% endif %}
                                {% if item.toolbox %}
                                    <a href="{{item.toolbox}}" class="btn btn-xs btn-success btn-btex" rel="tooltip" title="Toolbox" data-placement="bottom"><i class="fa fa-file-code-o"></i></a>
                                {% endif %}
                                {% if item.data1 %}
                                    <a href="{{item.data1.url}}" class="btn btn-xs btn-info btn-btex" rel="tooltip" title="{{item.data1.title}}" data-placement="bottom"><i class="fa fa-database"></i></a>
                                {% endif %}
                                {% if item.data2 %}
                                    <a href="{{item.data2.url}}" class="btn btn-xs btn-info btn-btex" rel="tooltip" title="{{item.data2.title}}" data-placement="bottom"><i class="fa fa-database"></i></a>
                                {% endif %}
                                <button type="button" class="btn btn-default btn-xs" data-toggle="collapse" data-parent="#btex-items-accordion" href="#collapse{{ item.key }}{{ uuid }}" aria-expanded="true" aria-controls="collapse{{ item.key }}{{ uuid }}">
                                    <i class="fa fa-caret-down"></i>
                                </button>
                            </div>
                        </div>
                    </div>
    
                    <div id="collapse{{ item.key }}{{ uuid }}" class="panel-collapse collapse" role="tabpanel" aria-labelledby="heading{{ item.key }}{{ uuid }}">
                        <h4>{{item.title}}</h4>
                        {% if item.abstract %}
                            <h5>Abstract</h5>
                            <p class="text-justify">{{item.abstract}}</p>
                        {% endif %}
                        {% if item.keywords %}
                            <h5>Keywords</h5>
                            <p class="text-justify">{{item.keywords}}</p>
                        {% endif %}
                        {% if item.award %}
                            <p><strong>Awards:</strong> {{item.award}}</p>
                        {% endif %}
                        {% if item.cites %}
                            <p><strong>Cites:</strong> {{item.cites}} (<a href="{{ item.citation_url }}" target="_blank">see at Google Scholar</a>)</p>
                        {% endif %}
                        <div class="btn-group">
                            <button type="button" class="btn btn-sm btn-danger" data-toggle="modal" data-target="#bibtex{{ item.key }}{{ uuid }}"><i class="fa fa-file-text-o"></i> Bibtex</button>
                            {% if item.pdf %}
                                <a href="{{item.pdf}}" class="btn btn-sm btn-warning btn-btex2" rel="tooltip" title="Download pdf" data-placement="bottom"><i class="fa fa-file-pdf-o fa-1x"></i> PDF</a>
                            {% endif %}
                            {% if item.slides %}
                                <a href="{{item.slides}}" class="btn btn-sm btn-info btn-btex2" rel="tooltip" title="Download slides" data-placement="bottom"><i class="fa fa-file-powerpoint-o"></i> Slides</a>
                            {% endif %}
                            {% if item.poster %}
                                <a href="{{item.poster}}" class="btn btn-sm btn-info btn-btex2" rel="tooltip" title="Download poster" data-placement="bottom"><i class="fa fa-picture-o"></i> Poster</a>
                            {% endif %}
                            {% if item.webpublication %}
                                <a href="{{item.webpublication.url}}" class="btn btn-sm btn-info btn-btex2" title="{{item.webpublication.title}}"><i class="fa fa-book"></i> Web publication</a>
                            {% endif %}
                        </div>
                        <div class="btn-group">
                        {% if item.toolbox %}
                            <a href="{{item.toolbox}}" class="btn btn-sm btn-success btn-btex2" rel="tooltip" title="Toolbox" data-placement="bottom"><i class="fa fa-file-code-o"></i> Toolbox</a>
                        {% endif %}
                        {% if item.data1 %}
                            <a href="{{item.data1.url}}" class="btn btn-sm btn-info btn-btex2" rel="tooltip" title="Toolbox" data-placement="bottom"><i class="fa fa-database"></i> {{item.data1.title}}</a>
                        {% endif %}
                        {% if item.data2 %}
                            <a href="{{item.data2.url}}" class="btn btn-sm btn-info btn-btex2" rel="tooltip" title="Toolbox" data-placement="bottom"><i class="fa fa-database"></i> {{item.data2.title}}</a>
                        {% endif %}
                        {% if item.code1 %}
                            <a href="{{item.code1.url}}" class="btn btn-sm btn-success btn-btex2" title="{{item.code1.title}}"><i class="fa fa-file-code-o"></i> {{item.code1.title}}</a>
                        {% endif %}
                        {% if item.code2 %}
                            <a href="{{item.code2.url}}" class="btn btn-sm btn-success btn-btex2" title="{{item.code2.title}}"><i class="fa fa-file-code-o"></i> {{item.code2.title}}</a>
                        {% endif %}
                        {% if item.demo %}
                            <a href="{{item.demo}}" class="btn btn-sm btn-primary iframe-demo btn-btex2" rel="tooltip" title="Demo" data-placement="bottom"><i class="fa fa-headphones"></i> Demo</a>
                        {% endif %}
                        {% if item.demo_external %}
                            <a href="{{item.demo_external}}" target="_blank" class="btn btn-sm btn-primary btn-btex2" rel="tooltip" title="Demo" data-placement="bottom"><i class="fa fa-headphones"></i> Demo</a>
                        {% endif %}
                        {% if item.link1 %}
                            <a href="{{item.link1.url}}" class="btn btn-sm btn-info btn-btex2" title="{{item.link1.title}}"><i class="fa fa-external-link-square"></i> {{item.link1.title}}</a>
                        {% endif %}
                        {% if item.link2 %}
                            <a href="{{item.link2.url}}" class="btn btn-sm btn-info btn-btex2" title="{{item.link2.title}}"><i class="fa fa-external-link-square"></i> {{item.link2.title}}</a>
                        {% endif %}
                        {% if item.link3 %}
                            <a href="{{item.link3.url}}" class="btn btn-sm btn-info btn-btex2" title="{{item.link3.title}}"><i class="fa fa-external-link-square"></i> {{item.link3.title}}</a>
                        {% endif %}
                        {% if item.link4 %}
                            <a href="{{item.link4.url}}" class="btn btn-sm btn-info btn-btex2" title="{{item.link4.title}}"><i class="fa fa-external-link-square"></i> {{item.link4.title}}</a>
                        {% endif %}
                        </div>
                    </div>
                </div>
            </div>
            <!-- Modal -->
            <div class="modal fade" id="bibtex{{item.key}}{{ uuid }}" tabindex="-1" role="dialog" aria-labelledby="bibtex{{item.key}}{{ uuid }}label" aria-hidden="true">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <button type="button" class="close" data-dismiss="modal"><span class="glyphicon glyphicon-remove-sign" aria-hidden="true"></span><span class="sr-only">Close</span></button>
                            <h4 class="modal-title" id="bibtex{{item.key}}{{ uuid }}label">{{item.title}}</h4>
                        </div>
                        <div class="modal-body">
                            <pre>{{item.bibtex}}</pre>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-default" data-dismiss="modal">Close</button>
                        </div>
                    </div>
                </div>
            </div>
            """

    elif options['template'] == 'fancy_minimal':
        template += """
        <div class="row">
            <div class="col-md-9">
                <h4>{{item.title}}</h4><a name="{{ item.key }}"></a>
                <p>
                    {{item._authors}}<br>
                    <span class="text-muted"><small><em>{{item._affiliations}}</em></small></span>
                </p>                
            </div>
            <div class="col-md-3">
                <div class="btn-group pull-right">                    
                    {% if item.pdf %}
                        <a href="{{item.pdf}}" class="btn btn-xs btn-warning btn-btex" rel="tooltip" title="Download pdf" data-placement="bottom"><i class="fa fa-file-text fa-1x"></i> PDF</a>
                    {% endif %}
                    {% if item.slides %}
                        <a href="{{item.slides}}" class="btn btn-xs btn-info btn-btex" rel="tooltip" title="Download slides" data-placement="bottom"><i class="fa fa-picture-o fa-1x"></i></a>
                    {% endif %}
                    {% if item.poster %}
                        <a href="{{item.poster}}" class="btn btn-xs btn-info btn-btex" rel="tooltip" title="Download poster" data-placement="bottom"><i class="fa fa-picture-o fa-1x"></i></a>
                    {% endif %}   
                    {% if item.video %}
                        <a href="{{item.video}}" class="btn btn-xs btn-success btn-btex" rel="tooltip" title="Video" data-placement="bottom"><i class="fa fa-video-camera fa-1x"></i></a>
                    {% endif %}                    
                    {% if item.demo %}
                        <a href="{{item.demo}}" class="btn btn-xs btn-primary iframe-demo btn-btex" rel="tooltip" title="Demo" data-placement="bottom"><i class="fa fa-headphones"></i></a>
                    {% endif %}
                    {% if item.demo_external %}
                        <a href="{{item.demo_external}}" target="_blank" class="btn btn-xs btn-primary btn-btex" rel="tooltip" title="Demo" data-placement="bottom"><i class="fa fa-headphones"></i></a>
                    {% endif %}
                    {% if item.toolbox %}
                        <a href="{{item.toolbox}}" class="btn btn-xs btn-success btn-btex" rel="tooltip" title="Toolbox" data-placement="bottom"><i class="fa fa-file-code-o"></i></a>
                    {% endif %}
                    {% if item.data1 %}
                        <a href="{{item.data1.url}}" class="btn btn-xs btn-info btn-btex" rel="tooltip" title="{{item.data1.title}}" data-placement="bottom"><i class="fa fa-database"></i></a>
                    {% endif %}
                    {% if item.data2 %}
                        <a href="{{item.data2.url}}" class="btn btn-xs btn-info btn-btex" rel="tooltip" title="{{item.data2.title}}" data-placement="bottom"><i class="fa fa-database"></i></a>
                    {% endif %}
                    {% if item.git1 or item.git2 or item.git3 or item.git4 %}
                        <button type="button" class="btn btn-xs btn-success" data-toggle="collapse" data-parent="#btex-items-accordion" href="#collapse{{ item.key }}{{ uuid }}" aria-expanded="true" aria-controls="collapse{{ item.key }}{{ uuid }}">
                            <i class="fa fa-git"></i>
                        </button>                                        
                    {% endif %}
                    {% if item.abstract or item.keywords %}
                    <button type="button" class="btn btn-default btn-xs" data-toggle="collapse" data-parent="#btex-items-accordion" href="#collapse{{ item.key }}{{ uuid }}" aria-expanded="true" aria-controls="collapse{{ item.key }}{{ uuid }}">
                        <i class="fa fa-caret-down"></i>
                    </button>
                    {% endif %}
                </div>
            </div>            
        </div>
        <div id="collapse{{ item.key }}{{ uuid }}" class="panel-collapse collapse" role="tabpanel" aria-labelledby="heading{{ item.key }}{{ uuid }}">
            {% if item.abstract %}
                <h5>Abstract</h5>
                <p class="text-justify">{{item.abstract}}</p>
            {% endif %}
            {% if item.keywords %}
                <h5>Keywords</h5>
                <p class="text-justify">{{item.keywords}}</p>
            {% endif %}
            {% if item.award %}
                <p><strong>Awards:</strong> {{item.award}}</p>
            {% endif %}
            {% if item.cites %}
                <p><strong>Cites:</strong> {{item.cites}} (<a href="{{ item.citation_url }}" target="_blank">see at Google Scholar</a>)</p>
            {% endif %}
            <div class="btn-group">
                <button type="button" class="btn btn-sm btn-danger" data-toggle="modal" data-target="#bibtex{{ item.key }}{{ uuid }}"><i class="fa fa-file-text-o"></i> Bibtex</button>
                {% if item.pdf %}
                    <a href="{{item.pdf}}" class="btn btn-sm btn-warning btn-btex2" rel="tooltip" title="Download pdf" data-placement="bottom"><i class="fa fa-file-text fa-1x"></i> PDF</a>
                {% endif %}
                {% if item.slides %}
                    <a href="{{item.slides}}" class="btn btn-sm btn-info btn-btex2" rel="tooltip" title="Download slides" data-placement="bottom"><i class="fa fa-picture-o"></i> Slides</a>
                {% endif %}
                {% if item.poster %}
                    <a href="{{item.poster}}" class="btn btn-sm btn-info btn-btex2" rel="tooltip" title="Download poster" data-placement="bottom"><i class="fa fa-picture-o"></i> Poster</a>
                {% endif %}
                {% if item.video %}
                    <a href="{{item.video}}" class="btn btn-sm btn-success btn-btex2" rel="tooltip" title="Video" data-placement="bottom"><i class="fa fa-video-camera"></i> Video</a>
                {% endif %}                
                {% if item.webpublication %}
                    <a href="{{item.webpublication.url}}" class="btn btn-sm btn-info btn-btex2" title="{{item.webpublication.title}}"><i class="fa fa-book"></i> Web publication</a>
                {% endif %}
            </div>
            <div class="btn-group">
                {% if item.toolbox %}
                    <a href="{{item.toolbox}}" class="btn btn-sm btn-success btn-btex2" rel="tooltip" title="Toolbox" data-placement="bottom"><i class="fa fa-file-code-o"></i> Toolbox</a>
                {% endif %}
                {% if item.data1 %}
                    <a href="{{item.data1.url}}" class="btn btn-sm btn-info btn-btex2" rel="tooltip" title="Toolbox" data-placement="bottom"><i class="fa fa-database"></i> {{item.data1.title}}</a>
                {% endif %}
                {% if item.data2 %}
                    <a href="{{item.data2.url}}" class="btn btn-sm btn-info btn-btex2" rel="tooltip" title="Toolbox" data-placement="bottom"><i class="fa fa-database"></i> {{item.data2.title}}</a>
                {% endif %}
                {% if item.code1 %}
                    <a href="{{item.code1.url}}" class="btn btn-sm btn-success btn-btex2" title="{{item.code1.title}}"><i class="fa fa-file-code-o"></i> {{item.code1.title}}</a>
                {% endif %}
                {% if item.code2 %}
                    <a href="{{item.code2.url}}" class="btn btn-sm btn-success btn-btex2" title="{{item.code2.title}}"><i class="fa fa-file-code-o"></i> {{item.code2.title}}</a>
                {% endif %}
                {% if item.git1 %}
                    <a href="{{item.git1.url}}" class="btn btn-sm btn-success" style="text-decoration:none;border-bottom:0;padding-bottom:9px" title="{{item.git1.title}}"><i class="fa fa-git"></i> {{item.git1.title}}</a>                                
                {% endif %}    
                {% if item.git2 %}
                    <a href="{{item.git2.url}}" class="btn btn-sm btn-success" style="text-decoration:none;border-bottom:0;padding-bottom:9px" title="{{item.git2.title}}"><i class="fa fa-git"></i> {{item.git2.title}}</a>                                
                {% endif %}
                {% if item.git3 %}
                    <a href="{{item.git3.url}}" class="btn btn-sm btn-success" style="text-decoration:none;border-bottom:0;padding-bottom:9px" title="{{item.git3.title}}"><i class="fa fa-git"></i> {{item.git3.title}}</a>                                
                {% endif %}
                {% if item.git4 %}
                    <a href="{{item.git4.url}}" class="btn btn-sm btn-success" style="text-decoration:none;border-bottom:0;padding-bottom:9px" title="{{item.git4.title}}"><i class="fa fa-git"></i> {{item.git4.title}}</a>                                
                {% endif %}                
                {% if item.demo %}
                    <a href="{{item.demo}}" class="btn btn-sm btn-primary iframe-demo btn-btex2" rel="tooltip" title="Demo" data-placement="bottom"><i class="fa fa-headphones"></i> Demo</a>
                {% endif %}
                {% if item.demo_external %}
                    <a href="{{item.demo_external}}" target="_blank" class="btn btn-sm btn-primary btn-btex2" rel="tooltip" title="Demo" data-placement="bottom"><i class="fa fa-headphones"></i> Demo</a>
                {% endif %}
                {% if item.link1 %}
                    <a href="{{item.link1.url}}" class="btn btn-sm btn-info btn-btex2" title="{{item.link1.title}}"><i class="fa fa-external-link-square"></i> {{item.link1.title}}</a>
                {% endif %}
                {% if item.link2 %}
                    <a href="{{item.link2.url}}" class="btn btn-sm btn-info btn-btex2" title="{{item.link2.title}}"><i class="fa fa-external-link-square"></i> {{item.link2.title}}</a>
                {% endif %}
                {% if item.link3 %}
                    <a href="{{item.link3.url}}" class="btn btn-sm btn-info btn-btex2" title="{{item.link3.title}}"><i class="fa fa-external-link-square"></i> {{item.link3.title}}</a>
                {% endif %}
                {% if item.link4 %}
                    <a href="{{item.link4.url}}" class="btn btn-sm btn-info btn-btex2" title="{{item.link4.title}}"><i class="fa fa-external-link-square"></i> {{item.link4.title}}</a>
                {% endif %}
            </div>
        </div>
        <!-- Modal -->
        <div class="modal fade" id="bibtex{{item.key}}{{ uuid }}" tabindex="-1" role="dialog" aria-labelledby="bibtex{{item.key}}{{ uuid }}label" aria-hidden="true">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <button type="button" class="close" data-dismiss="modal"><span class="glyphicon glyphicon-remove-sign" aria-hidden="true"></span><span class="sr-only">Close</span></button>
                        <h4 class="modal-title" id="bibtex{{item.key}}{{ uuid }}label">{{item.title}}</h4>
                    </div>
                    <div class="modal-body">
                        <pre>{{item.bibtex}}</pre>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-default" data-dismiss="modal">Close</button>
                    </div>
                </div>
            </div>
        </div>        
        """

    elif options['template'] == 'fancy_minimal_no_bibtex':
        template += """
        <div class="row">
            <div class="col-md-9">
                <h4>{{item.title}}</h4><a name="{{ item.key }}"></a>
                <p>
                    {{item._authors}}<br>
                    <span class="text-muted"><small><em>{{item._affiliations}}</em></small></span>
                </p>
            </div>
            <div class="col-md-3">
                <div class="btn-group pull-right">                    
                    {% if item.pdf %}
                        <a href="{{item.pdf}}" class="btn btn-xs btn-warning btn-btex" rel="tooltip" title="Download pdf" data-placement="bottom"><i class="fa fa-file-text fa-1x"></i> PDF</a>
                    {% endif %}
                    {% if item.slides %}
                        <a href="{{item.slides}}" class="btn btn-xs btn-info btn-btex" rel="tooltip" title="Slides" data-placement="bottom"><i class="fa fa-picture-o fa-1x"></i> Slides</a>
                    {% endif %}
                    {% if item.poster %}
                        <a href="{{item.poster}}" class="btn btn-xs btn-info btn-btex" rel="tooltip" title="Poster" data-placement="bottom"><i class="fa fa-file-picture-o fa-1x"></i> Poster</a>
                    {% endif %}                    
                    {% if item.video %}
                        <a href="{{item.video}}" class="btn btn-xs btn-success btn-btex" rel="tooltip" title="Video" data-placement="bottom"><i class="fa fa-video-camera fa-1x"></i></a>
                    {% endif %}                      
                    {% if item.demo %}
                        <a href="{{item.demo}}" class="btn btn-xs btn-primary iframe-demo btn-btex" rel="tooltip" title="Demo" data-placement="bottom"><i class="fa fa-headphones"></i></a>
                    {% endif %}
                    {% if item.demo_external %}
                        <a href="{{item.demo_external}}" target="_blank" class="btn btn-xs btn-primary btn-btex" rel="tooltip" title="Demo" data-placement="bottom"><i class="fa fa-headphones"></i></a>
                    {% endif %}
                    {% if item.toolbox %}
                        <a href="{{item.toolbox}}" class="btn btn-xs btn-success btn-btex" rel="tooltip" title="Toolbox" data-placement="bottom"><i class="fa fa-file-code-o"></i></a>
                    {% endif %}
                    {% if item.data1 %}
                        <a href="{{item.data1.url}}" class="btn btn-xs btn-info btn-btex" rel="tooltip" title="{{item.data1.title}}" data-placement="bottom"><i class="fa fa-database"></i></a>
                    {% endif %}
                    {% if item.data2 %}
                        <a href="{{item.data2.url}}" class="btn btn-xs btn-info btn-btex" rel="tooltip" title="{{item.data2.title}}" data-placement="bottom"><i class="fa fa-database"></i></a>
                    {% endif %}
                    {% if item.abstract or item.keywords %}
                    <button type="button" class="btn btn-default btn-xs" data-toggle="collapse" data-parent="#btex-items-accordion" href="#collapse{{ item.key }}{{ uuid }}" aria-expanded="true" aria-controls="collapse{{ item.key }}{{ uuid }}">
                        <i class="fa fa-caret-down"></i>
                    </button>
                    {% endif %}
                </div>
            </div>            
        </div>
        <div id="collapse{{ item.key }}{{ uuid }}" class="panel-collapse collapse" role="tabpanel" aria-labelledby="heading{{ item.key }}{{ uuid }}">
            {% if item.abstract %}
                <h5>Abstract</h5>
                <p class="text-justify">{{item.abstract}}</p>
            {% endif %}
            {% if item.keywords %}
                <h5>Keywords</h5>
                <p class="text-justify">{{item.keywords}}</p>
            {% endif %}
            {% if item.award %}
                <p><strong>Awards:</strong> {{item.award}}</p>
            {% endif %}
            {% if item.cites %}
                <p><strong>Cites:</strong> {{item.cites}} (<a href="{{ item.citation_url }}" target="_blank">see at Google Scholar</a>)</p>
            {% endif %}
            <div class="btn-group">
                {% if item.pdf %}
                    <a href="{{item.pdf}}" class="btn btn-sm btn-warning btn-btex2" rel="tooltip" title="Download pdf" data-placement="bottom"><i class="fa fa-file-text fa-1x"></i> PDF</a>
                {% endif %}
                {% if item.slides %}
                    <a href="{{item.slides}}" class="btn btn-sm btn-info btn-btex2" rel="tooltip" title="Download slides" data-placement="bottom"><i class="fa fa-picture-o"></i> Slides</a>
                {% endif %}
                {% if item.poster %}
                    <a href="{{item.poster}}" class="btn btn-sm btn-info btn-btex2" rel="tooltip" title="Download poster" data-placement="bottom"><i class="fa fa-picture-o"></i> Poster</a>
                {% endif %}
                {% if item.video %}
                    <a href="{{item.video}}" class="btn btn-sm btn-success btn-btex2" rel="tooltip" title="Video" data-placement="bottom"><i class="fa fa-video-camera"></i> Video</a>
                {% endif %}
                {% if item.webpublication %}
                    <a href="{{item.webpublication.url}}" class="btn btn-sm btn-info btn-btex2" title="{{item.webpublication.title}}"><i class="fa fa-book"></i> Web publication</a>
                {% endif %}
            </div>
            <div class="btn-group">
                {% if item.toolbox %}
                    <a href="{{item.toolbox}}" class="btn btn-sm btn-success btn-btex2" rel="tooltip" title="Toolbox" data-placement="bottom"><i class="fa fa-file-code-o"></i> Toolbox</a>
                {% endif %}
                {% if item.data1 %}
                    <a href="{{item.data1.url}}" class="btn btn-sm btn-info btn-btex2" rel="tooltip" title="Toolbox" data-placement="bottom"><i class="fa fa-database"></i> {{item.data1.title}}</a>
                {% endif %}
                {% if item.data2 %}
                    <a href="{{item.data2.url}}" class="btn btn-sm btn-info btn-btex2" rel="tooltip" title="Toolbox" data-placement="bottom"><i class="fa fa-database"></i> {{item.data2.title}}</a>
                {% endif %}
                {% if item.code1 %}
                    <a href="{{item.code1.url}}" class="btn btn-sm btn-success btn-btex2" title="{{item.code1.title}}"><i class="fa fa-file-code-o"></i> {{item.code1.title}}</a>
                {% endif %}
                {% if item.code2 %}
                    <a href="{{item.code2.url}}" class="btn btn-sm btn-success btn-btex2" title="{{item.code2.title}}"><i class="fa fa-file-code-o"></i> {{item.code2.title}}</a>
                {% endif %}
                {% if item.git1 %}
                    <a href="{{item.git1.url}}" class="btn btn-sm btn-success" style="text-decoration:none;border-bottom:0;padding-bottom:9px" title="{{item.git1.title}}"><i class="fa fa-git"></i> {{item.git1.title}}</a>                                
                {% endif %}    
                {% if item.git2 %}
                    <a href="{{item.git2.url}}" class="btn btn-sm btn-success" style="text-decoration:none;border-bottom:0;padding-bottom:9px" title="{{item.git2.title}}"><i class="fa fa-git"></i> {{item.git2.title}}</a>                                
                {% endif %}
                {% if item.git3 %}
                    <a href="{{item.git3.url}}" class="btn btn-sm btn-success" style="text-decoration:none;border-bottom:0;padding-bottom:9px" title="{{item.git3.title}}"><i class="fa fa-git"></i> {{item.git3.title}}</a>                                
                {% endif %}
                {% if item.git4 %}
                    <a href="{{item.git4.url}}" class="btn btn-sm btn-success" style="text-decoration:none;border-bottom:0;padding-bottom:9px" title="{{item.git4.title}}"><i class="fa fa-git"></i> {{item.git4.title}}</a>                                
                {% endif %}                 
                {% if item.demo %}
                    <a href="{{item.demo}}" class="btn btn-sm btn-primary iframe-demo btn-btex2" rel="tooltip" title="Demo" data-placement="bottom"><i class="fa fa-headphones"></i> Demo</a>
                {% endif %}
                {% if item.demo_external %}
                    <a href="{{item.demo_external}}" target="_blank" class="btn btn-sm btn-primary btn-btex2" rel="tooltip" title="Demo" data-placement="bottom"><i class="fa fa-headphones"></i> Demo</a>
                {% endif %}
                {% if item.link1 %}
                    <a href="{{item.link1.url}}" class="btn btn-sm btn-info btn-btex2" title="{{item.link1.title}}"><i class="fa fa-external-link-square"></i> {{item.link1.title}}</a>
                {% endif %}
                {% if item.link2 %}
                    <a href="{{item.link2.url}}" class="btn btn-sm btn-info btn-btex2" title="{{item.link2.title}}"><i class="fa fa-external-link-square"></i> {{item.link2.title}}</a>
                {% endif %}
                {% if item.link3 %}
                    <a href="{{item.link3.url}}" class="btn btn-sm btn-info btn-btex2" title="{{item.link3.title}}"><i class="fa fa-external-link-square"></i> {{item.link3.title}}</a>
                {% endif %}
                {% if item.link4 %}
                    <a href="{{item.link4.url}}" class="btn btn-sm btn-info btn-btex2" title="{{item.link4.title}}"><i class="fa fa-external-link-square"></i> {{item.link4.title}}</a>
                {% endif %}
            </div>
        </div>    
        """

    elif options['template'] == 'fancy_minimal_keynote':
        template += """
        <div class="row">
            <div class="col-md-9">
                <h4>{{item.title}}</h4><a name="{{ item.key }}"></a>
                <p>
                    {{item._authors}}<br>
                    <span class="text-muted"><small><em>{{item._affiliations}}</em></small></span>
                </p>
            </div>
            <div class="col-md-3">
                <div class="btn-group pull-right">                    
                    {% if item.pdf %}
                        <a href="{{item.pdf}}" class="btn btn-xs btn-warning btn-btex" rel="tooltip" title="Download pdf" data-placement="bottom"><i class="fa fa-file-text fa-1x"></i> PDF</a>
                    {% endif %}
                    {% if item.slides %}
                        <a href="{{item.slides}}" class="btn btn-xs btn-info btn-btex" rel="tooltip" title="Slides" data-placement="bottom"><i class="fa fa-picture-o fa-1x"></i> Slides</a>
                    {% endif %}
                    {% if item.video %}
                        <a href="{{item.video}}" class="btn btn-xs btn-success btn-btex" rel="tooltip" title="Video" data-placement="bottom"><i class="fa fa-video-camera fa-1x"></i></a>
                    {% endif %}           
                    {% if item.demo %}
                        <a href="{{item.demo}}" class="btn btn-xs btn-primary iframe-demo btn-btex" rel="tooltip" title="Demo" data-placement="bottom"><i class="fa fa-headphones"></i></a>
                    {% endif %}
                    {% if item.demo_external %}
                        <a href="{{item.demo_external}}" target="_blank" class="btn btn-xs btn-primary btn-btex" rel="tooltip" title="Demo" data-placement="bottom"><i class="fa fa-headphones"></i></a>
                    {% endif %}
                    {% if item.toolbox %}
                        <a href="{{item.toolbox}}" class="btn btn-xs btn-success btn-btex" rel="tooltip" title="Toolbox" data-placement="bottom"><i class="fa fa-file-code-o"></i></a>
                    {% endif %}
                    {% if item.data1 %}
                        <a href="{{item.data1.url}}" class="btn btn-xs btn-info btn-btex" rel="tooltip" title="{{item.data1.title}}" data-placement="bottom"><i class="fa fa-database"></i></a>
                    {% endif %}
                    {% if item.data2 %}
                        <a href="{{item.data2.url}}" class="btn btn-xs btn-info btn-btex" rel="tooltip" title="{{item.data2.title}}" data-placement="bottom"><i class="fa fa-database"></i></a>
                    {% endif %}
                    <button type="button" class="btn btn-default btn-xs" data-toggle="collapse" data-parent="#btex-items-accordion" href="#collapse{{ item.key }}{{ uuid }}" aria-expanded="true" aria-controls="collapse{{ item.key }}{{ uuid }}">
                        <i class="fa fa-caret-down"></i>
                    </button>
                </div>
            </div>            
        </div>
        <div id="collapse{{ item.key }}{{ uuid }}" class="panel-collapse collapse" role="tabpanel" aria-labelledby="heading{{ item.key }}{{ uuid }}">
            {% if item.abstract %}
                <h5>Abstract</h5>
                <p class="text-justify">{{item.abstract}}</p>
            {% endif %}
            {% if item._bio %}
                <h5>Biography</h5>
                <p class="text-justify">{{item._bio}}</p>
            {% endif %}                        
            <div class="row">
                <div class="col-md-10">
                    {% if item._authors %}
                        <h5><strong>{{item._authors}}</strong></h5>
                    {% else %}
                        <h5><strong>{{item.authors_text}}</strong></h5>
                    {% endif %}          
                    <p><em>
                    {% if item._affiliations_long %}
                        {{item._affiliations_long}}
                    {% else %}
                        {{item._affiliations}}
                    {% endif %}          
                    </em></p>
                </div>                    
                <div class="col-md-2">
                    {% if item._profile_photo %}
                        <img src="{{item._profile_photo}}" class="img img-rounded">
                    {% endif %}
                </div>
            </div>            
            {% if item.keywords %}
                <h5>Keywords</h5>
                <p class="text-justify">{{item.keywords}}</p>
            {% endif %}
            {% if item.award %}
                <p><strong>Awards:</strong> {{item.award}}</p>
            {% endif %}
            {% if item.cites %}
                <p><strong>Cites:</strong> {{item.cites}} (<a href="{{ item.citation_url }}" target="_blank">see at Google Scholar</a>)</p>
            {% endif %}
            <div class="btn-group">
                {% if item.pdf %}
                    <a href="{{item.pdf}}" class="btn btn-sm btn-warning btn-btex2" rel="tooltip" title="Download pdf" data-placement="bottom"><i class="fa fa-file-text fa-1x"></i> PDF</a>
                {% endif %}
                {% if item.slides %}
                    <a href="{{item.slides}}" class="btn btn-sm btn-info btn-btex2" rel="tooltip" title="Download slides" data-placement="bottom"><i class="fa fa-picture-o"></i> Slides</a>
                {% endif %}
                {% if item.poster %}
                    <a href="{{item.poster}}" class="btn btn-sm btn-info btn-btex2" rel="tooltip" title="Download poster" data-placement="bottom"><i class="fa fa-picture-o"></i> Poster</a>
                {% endif %}
                {% if item.video %}
                    <a href="{{item.video}}" class="btn btn-sm btn-success btn-btex2" rel="tooltip" title="Video" data-placement="bottom"><i class="fa fa-video-camera"></i> Video</a>
                {% endif %}
                {% if item.webpublication %}
                    <a href="{{item.webpublication.url}}" class="btn btn-sm btn-info btn-btex2" title="{{item.webpublication.title}}"><i class="fa fa-book"></i> Web publication</a>
                {% endif %}
            </div>
            <div class="btn-group">
                {% if item.toolbox %}
                    <a href="{{item.toolbox}}" class="btn btn-sm btn-success btn-btex2" rel="tooltip" title="Toolbox" data-placement="bottom"><i class="fa fa-file-code-o"></i> Toolbox</a>
                {% endif %}
                {% if item.data1 %}
                    <a href="{{item.data1.url}}" class="btn btn-sm btn-info btn-btex2" rel="tooltip" title="Toolbox" data-placement="bottom"><i class="fa fa-database"></i> {{item.data1.title}}</a>
                {% endif %}
                {% if item.data2 %}
                    <a href="{{item.data2.url}}" class="btn btn-sm btn-info btn-btex2" rel="tooltip" title="Toolbox" data-placement="bottom"><i class="fa fa-database"></i> {{item.data2.title}}</a>
                {% endif %}
                {% if item.code1 %}
                    <a href="{{item.code1.url}}" class="btn btn-sm btn-success btn-btex2" title="{{item.code1.title}}"><i class="fa fa-file-code-o"></i> {{item.code1.title}}</a>
                {% endif %}
                {% if item.git1 %}
                    <a href="{{item.git1.url}}" class="btn btn-sm btn-success" style="text-decoration:none;border-bottom:0;padding-bottom:9px" title="{{item.git1.title}}"><i class="fa fa-git"></i> {{item.git1.title}}</a>                                
                {% endif %}    
                {% if item.git2 %}
                    <a href="{{item.git2.url}}" class="btn btn-sm btn-success" style="text-decoration:none;border-bottom:0;padding-bottom:9px" title="{{item.git2.title}}"><i class="fa fa-git"></i> {{item.git2.title}}</a>                                
                {% endif %}
                {% if item.git3 %}
                    <a href="{{item.git3.url}}" class="btn btn-sm btn-success" style="text-decoration:none;border-bottom:0;padding-bottom:9px" title="{{item.git3.title}}"><i class="fa fa-git"></i> {{item.git3.title}}</a>                                
                {% endif %}
                {% if item.git4 %}
                    <a href="{{item.git4.url}}" class="btn btn-sm btn-success" style="text-decoration:none;border-bottom:0;padding-bottom:9px" title="{{item.git4.title}}"><i class="fa fa-git"></i> {{item.git4.title}}</a>                                
                {% endif %}                 
                {% if item.code2 %}
                    <a href="{{item.code2.url}}" class="btn btn-sm btn-success btn-btex2" title="{{item.code2.title}}"><i class="fa fa-file-code-o"></i> {{item.code2.title}}</a>
                {% endif %}
                {% if item.demo %}
                    <a href="{{item.demo}}" class="btn btn-sm btn-primary iframe-demo btn-btex2" rel="tooltip" title="Demo" data-placement="bottom"><i class="fa fa-headphones"></i> Demo</a>
                {% endif %}
                {% if item.demo_external %}
                    <a href="{{item.demo_external}}" target="_blank" class="btn btn-sm btn-primary btn-btex2" rel="tooltip" title="Demo" data-placement="bottom"><i class="fa fa-headphones"></i> Demo</a>
                {% endif %}
                {% if item.link1 %}
                    <a href="{{item.link1.url}}" class="btn btn-sm btn-info btn-btex2" title="{{item.link1.title}}"><i class="fa fa-external-link-square"></i> {{item.link1.title}}</a>
                {% endif %}
                {% if item.link2 %}
                    <a href="{{item.link2.url}}" class="btn btn-sm btn-info btn-btex2" title="{{item.link2.title}}"><i class="fa fa-external-link-square"></i> {{item.link2.title}}</a>
                {% endif %}
                {% if item.link3 %}
                    <a href="{{item.link3.url}}" class="btn btn-sm btn-info btn-btex2" title="{{item.link3.title}}"><i class="fa fa-external-link-square"></i> {{item.link3.title}}</a>
                {% endif %}
                {% if item.link4 %}
                    <a href="{{item.link4.url}}" class="btn btn-sm btn-info btn-btex2" title="{{item.link4.title}}"><i class="fa fa-external-link-square"></i> {{item.link4.title}}</a>
                {% endif %}
            </div>
        </div>    
        """

    return template


def search(key, publications):
    return [element for element in publications if element['key'] == key]


def btex(content):
    if isinstance(content, contents.Static):
        return

    google_queries = 0
    soup = BeautifulSoup(content._content, 'html.parser')
    btex_divs = soup.find_all('div', class_='btex')
    btex_item_divs = soup.find_all('div', class_='btex-item')
    if btex_item_divs:
        if btex_settings['debug_processing']:
            logger.debug(msg='[{plugin_name}] title:[{title}] divs:[{div_count}]'.format(
                plugin_name='btex-item',
                title=content.title,
                div_count=len(btex_item_divs)
            ))

        for btex_item_div in btex_item_divs:
            options = {}
            options['uuid'] = uuid.uuid4().hex
            options['css'] = btex_item_div['class']

            options['data_source'] = get_attribute(btex_item_div.attrs, 'source', None)
            options['citations'] = get_attribute(btex_item_div.attrs, 'citations', 'btex_citation_cache.yaml')
            options['template'] = get_attribute(btex_item_div.attrs, 'template', 'default')

            citation_data = load_citation_data(filename=options['citations'])

            options['item'] = get_attribute(btex_item_div.attrs, 'item', None)
            options['scholar-cite-counts'] = boolean(get_attribute(btex_item_div.attrs, 'scholar-cite-counts', 'no'))
            options['scholar-link'] = get_attribute(btex_item_div.attrs, 'scholar-link', None)
            options['target_page'] = get_attribute(btex_item_div.attrs, 'target-page', None)

            publications = parse_bibtex_file(options['data_source'])
            item_data = search(
                key=options['item'],
                publications=publications
            )

            if item_data:
                item_data = item_data[0]

            if item_data:
                meta = {}
                if 'scholar-cite-counts' in options and options['scholar-cite-counts']:
                    google_access_valid = btex_settings['google_scholar']['active']
                    current_timestamp = time.time()
                    if google_access_valid:
                        try:
                            import scholar.scholar as sc

                        except ImportError:
                            logger.warning('[btex] Failed to import `scholar`')

                        citation_update_needed = False
                        citation_update_count = 0
                        current_citation_data = get_citation_data(citation_data, item_data['title'], item_data['year'])
                        if current_citation_data:
                            last_fetch = time.mktime(datetime.strptime(current_citation_data['last_update'], '%Y-%m-%d %H:%M:%S').timetuple())
                            if btex_settings['google_scholar']['fetching_timeout'] + last_fetch < current_timestamp:
                                citation_update_needed = True
                                citation_update_count += 1

                        else:
                            citation_update_needed = True
                            citation_update_count += 1

                        # Update citations before injecting them to the publication list
                        if citation_update_needed:
                            logger.warning("[btex] Citation update needed for articles: " + str(citation_update_count))
                            # Go publications through paper by paper
                            if google_access_valid and google_queries < btex_settings['google_scholar']['max_updated_entries_per_batch']:
                                # Fetch article from google
                                # print "  Query publication ["+pub['title']+"]"

                                # Form author list
                                authors = []
                                for author in item_data['authors']:
                                    authors.append(' '.join(author.first()) + ' ' + ' '.join(author.last()))

                                logger.warning('[btex]  Query publication [{authors}: {title}]'.format(authors=authors.split(',')[0], title=item_data['title']))

                                authors = ", ".join(authors)
                                querier = sc.ScholarQuerier()
                                settings = sc.ScholarSettings()
                                querier.apply_settings(settings)

                                query = sc.SearchScholarQuery()
                                query.set_author(authors.split(',')[0])  # Authors
                                query.set_phrase(item_data['title'])  # Title
                                query.set_scope(True)  # Title only
                                query.set_num_page_results(1)

                                querier.send_query(query)
                                google_queries += 1
                                if len(querier.articles):
                                    update_citation_data(
                                        citation_data=citation_data,
                                        new_data=querier.articles[0].attrs,
                                        title=item_data['title'],
                                        year=item_data['year'],
                                        insert_new=True
                                    )

                                    logger.warning('[btex]    Cites [{num_citations}]'.format(str(querier.articles[0].attrs['num_citations'][0])))

                                else:
                                    update_citation_data_empty(
                                        citation_data=citation_data,
                                        title=item_data['title'],
                                        year=item_data['year']
                                    )

                                    logger.warning('[btex]    Nothing returned, article might not be indexed by Google or your access quota is exceeded!')

                                save_citation_data(
                                    filename=options['citations'],
                                    citation_data=citation_data
                                )

                                # Wait after each query random time in order to avoid flooding Google.
                                wait_time = randint(btex_settings['google_scholar']['fetch_item_timeout'][0],
                                                    btex_settings['google_scholar']['fetch_item_timeout'][1])

                                logger.warning('[btex]  Sleeping [{wait_time} sec]'.format(wait_time=str(wait_time)))
                                sleep(wait_time)

                    # Inject citation information to the publication list
                    current_citation_data = get_citation_data(
                        citation_data=citation_data,
                        title=item_data['title'],
                        year=item_data['year']
                    )

                    if current_citation_data and 'scholar' in current_citation_data and 'total_citations' in current_citation_data['scholar']:
                        item_data['cites'] = current_citation_data['scholar']['total_citations']

                    else:
                        item_data['cites'] = 0

                    if current_citation_data and 'scholar' in current_citation_data and 'citation_list_url' in current_citation_data['scholar']:
                        item_data['citation_url'] = current_citation_data['scholar']['citation_list_url']

                    else:
                        item_data['citation_url'] = None

                meta['cite_update'] = newest_citation_update(citation_data, publications)

                div_text = btex_item_div.text
                div_text = div_text.rstrip('\r\n').replace(" ", "")
                has_template = False
                if len(div_text):
                    has_template = True

                if not has_template:
                    btex_item_div.string = get_default_item_template(options)

                template = Template(btex_item_div.prettify().strip('\t\r\n').replace('&gt;', '>').replace('&lt;', '<'))

                div_html = BeautifulSoup(template.render(
                    item=item_data,
                    meta=meta,
                    target_page=options['target_page'],
                    uuid=options['uuid']
                ), "html.parser")

                btex_item_div.replaceWith(div_html)

    if btex_divs:
        if btex_settings['debug_processing']:
            logger.debug(msg='[{plugin_name}] title:[{title}] divs:[{div_count}]'.format(
                plugin_name='btex',
                title=content.title,
                div_count=len(btex_divs)
            ))
        for btex_div in btex_divs:
            options = {
                'css': btex_div['class'],
                'data_source': get_attribute(btex_div.attrs, 'source', None),
                'citations': get_attribute(btex_div.attrs, 'citations', 'btex_citation_cache.yaml'),
                'template': get_attribute(btex_div.attrs, 'template', 'publications'),
                'years': get_attribute(btex_div.attrs, 'years', None),
                'item_count': get_attribute(btex_div.attrs, 'item-count', None),
                'scholar-cite-counts': boolean(get_attribute(btex_div.attrs, 'scholar-cite-counts', 'no')),
                'scholar-link': get_attribute(btex_div.attrs, 'scholar-link', None),
                'stats': boolean(get_attribute(btex_div.attrs, 'stats', 'no')),
                'target_page': get_attribute(btex_div.attrs, 'target-page', None),
            }

            if options['years']:
                options['first_visible_year'] = int(datetime.now().strftime('%Y')) - int(options['years'])

            else:
                options['first_visible_year'] = ''

            citation_data = load_citation_data(
                filename=options['citations']
            )

            publications = parse_bibtex_file(options['data_source'])

            meta = {}
            if 'scholar-cite-counts' in options and options['scholar-cite-counts']:
                google_access_valid = btex_settings['google_scholar']['active']
                current_timestamp = time.time()
                if google_access_valid:
                    try:
                        import scholar.scholar as sc

                    except ImportError:
                        logger.warning('[btex] Failed to import `scholar`')

                    citation_update_needed = False
                    citation_update_count = 0

                    for pub in publications:
                        current_citation_data = get_citation_data(citation_data, pub['title'], pub['year'])
                        if current_citation_data:
                            last_fetch = time.mktime(datetime.strptime(current_citation_data['last_update'], '%Y-%m-%d %H:%M:%S').timetuple())
                            if btex_settings['google_scholar']['fetching_timeout'] + last_fetch < current_timestamp:
                                citation_update_needed = True
                                citation_update_count += 1

                        else:
                            citation_update_needed = True
                            citation_update_count += 1

                    # Update citations before injecting them to the publication list
                    if citation_update_needed:
                        logger.warning('[btex] Citation update needed for articles: {citation_update_count}'.format(citation_update_count=str(citation_update_count)))

                        # Go publications through paper by paper
                        for pub in publications:
                            if google_access_valid and google_queries < btex_settings['google_scholar']['max_updated_entries_per_batch']:
                                # Check can we query google, as we
                                # only update specified amount of entries (to avoid filling google access quota) with
                                # specified time intervals
                                current_citation_data = get_citation_data(
                                    citation_data=citation_data,
                                    title=pub['title'],
                                    year=pub['year']
                                )

                                citation_update_needed = False

                                if current_citation_data:
                                    last_fetch = time.mktime(datetime.strptime(current_citation_data['last_update'],'%Y-%m-%d %H:%M:%S').timetuple())

                                    if btex_settings['google_scholar']['fetching_timeout'] + last_fetch < current_timestamp:
                                        citation_update_needed = True

                                else:
                                    # We have a new article
                                    citation_update_needed = True

                                if citation_update_needed:
                                    # Fetch article from google
                                    # print "  Query publication ["+pub['title']+"]"
                                    # Form author list
                                    authors = []
                                    for author in pub['authors']:
                                        authors.append(' '.join(author.first()) + ' ' + ' '.join(author.last()))

                                    authors = ', '.join(authors)

                                    logger.warning('[btex]  Query publication [{authors}: {title}]'.format(
                                        authors=authors.split(',')[0],
                                        title=pub['title'])
                                    )

                                    querier = sc.ScholarQuerier()
                                    settings = sc.ScholarSettings()
                                    querier.apply_settings(settings)

                                    query = sc.SearchScholarQuery()
                                    query.set_author(authors.split(',')[0])     # Authors
                                    query.set_phrase(pub['title'])              # Title
                                    query.set_scope(True)                       # Title only
                                    query.set_num_page_results(1)

                                    querier.send_query(query)
                                    google_queries += 1

                                    if len(querier.articles):
                                        update_citation_data(
                                            citation_data=citation_data,
                                            new_data=querier.articles[0].attrs,
                                            title=pub['title'],
                                            year=pub['year'],
                                            insert_new=True
                                        )
                                        logger.warning('[btex]    Cites: {num_citations}'.format(
                                            num_citations=str(querier.articles[0].attrs['num_citations'][0]))
                                        )

                                    else:
                                        update_citation_data_empty(
                                            citation_data=citation_data,
                                            title=pub['title'],
                                            year=pub['year']
                                        )

                                        logger.warning('[btex]    Nothing returned, article might not be indexed by Google or your access quota is exceeded!')

                                    save_citation_data(
                                        filename=options['citations'],
                                        citation_data=citation_data
                                    )

                                    # Wait after each query random time in order to avoid flooding Google.
                                    wait_time = randint(btex_settings['google_scholar']['fetch_item_timeout'][0],
                                                        btex_settings['google_scholar']['fetch_item_timeout'][1])

                                    logger.warning('[btex]  Sleeping [{wait_time} sec]'.format(wait_time=str(wait_time)))
                                    sleep(wait_time)

                # Inject citation information to the publication list
                for pub in publications:
                    current_citation_data = get_citation_data(
                        citation_data=citation_data,
                        title=pub['title'],
                        year=pub['year']
                    )

                    if current_citation_data and 'scholar' in current_citation_data and 'total_citations' in current_citation_data['scholar']:
                        pub['cites'] = current_citation_data['scholar']['total_citations']

                    else:
                        pub['cites'] = 0

                    if current_citation_data and 'scholar' in current_citation_data and 'citation_list_url' in current_citation_data['scholar']:
                        pub['citation_url'] = current_citation_data['scholar']['citation_list_url']

                    else:
                        pub['citation_url'] = None

                meta['cite_update'] = newest_citation_update(citation_data, publications)

            if 'stats' in options and options['stats']:
                meta['publications'] = len(publications)
                meta['pubs_per_year'] = get_publications_per_year(publications)
                meta['cites_per_year'] = get_cites_per_year(publications)
                if options['scholar-cite-counts']:
                    meta['cites'] = 0
                    for pub in publications:
                        if 'cites' in pub:
                            meta['cites'] += pub['cites']

                author_list = []
                type_stats = {}
                for pub in publications:
                    for author in pub['authors']:
                        author_name = " ".join(author.first()) + " " + " ".join(author.last())
                        if author_name not in author_list:
                            author_list.append(author_name)

                    if pub['type_label'] not in type_stats:
                        type_stats[pub['type_label']] = 0

                    type_stats[pub['type_label']] += 1

                meta['unique_authors'] = len(author_list)
                meta['types'] = type_stats

                group_stat = []
                for group_id in btex_publication_grouping:
                    group_data = btex_publication_grouping[group_id]
                    if group_data['label'] in type_stats:
                        group_stat.append('<em>'+group_data['name'] + '</em> : ' + str(type_stats[group_data['label']]))

                meta['types_html_list'] = ", ".join(group_stat)

                if 'cite_update' in meta and meta['cite_update']:
                    meta['cite_update_string'] = format(datetime.fromtimestamp(float(meta['cite_update'])), '%d.%m.%Y')

            div_text = btex_div.text
            div_text = div_text.rstrip('\r\n').replace(" ", "")
            has_template = False

            if len(div_text):
                has_template = True

            if not has_template:
                btex_div.string = get_default_template(options)

            template = Template(btex_div.prettify().strip('\t\r\n').replace('&gt;', '>').replace('&lt;', '<'))

            if not options['item_count']:
                options['item_count'] = len(publications)
            else:
                options['item_count'] = int(options['item_count'])

            div_html = BeautifulSoup(
                template.render(
                    publications=publications,
                    meta=meta,
                    publication_grouping=btex_publication_grouping,
                    first_visible_year=options['first_visible_year'],
                    item_count=options['item_count'],
                    target_page=options['target_page']
                ),
                "html.parser"
            )
            btex_div.replaceWith(div_html)

        if btex_settings['minified']:
            html_elements = {
                'js_include': [
                    '<script type="text/javascript" src="'+btex_settings['site-url']+'/theme/js/btex.min.js"></script>'
                ],
                'css_include': [
                    '<link rel="stylesheet" href="' + btex_settings['site-url'] + '/theme/css/btex.min.css">'
                ]
            }

        else:
            html_elements = {
                'js_include': [
                    '<script type="text/javascript" src="'+btex_settings['site-url']+'/theme/js/btex.js"></script>'
                ],
                'css_include': [
                    '<link rel="stylesheet" href="' + btex_settings['site-url'] + '/theme/css/btex.css">'
                ]
            }

        if btex_settings['use_fontawesome_cdn']:
            html_elements['css_include'].append(
                '<link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/font-awesome/4.6.3/css/font-awesome.min.css">'
            )

        if u'scripts' not in content.metadata:
            content.metadata[u'scripts'] = []

        for element in html_elements['js_include']:
            if element not in content.metadata[u'scripts']:
                content.metadata[u'scripts'].append(element)

        if u'styles' not in content.metadata:
            content.metadata[u'styles'] = []

        for element in html_elements['css_include']:
            if element not in content.metadata[u'styles']:
                content.metadata[u'styles'].append(element)

    content._content = soup.decode()


def get_citation_data(citation_data, title, year):
    if citation_data:
        for cite in citation_data:
            if 'title' in cite and 'year' in cite and str(title).lower() == cite['title'].lower() and int(year) == int(cite['year']):
                return cite

    return None


def update_citation_data(citation_data, new_data, title=None, year=None, insert_new=False):
    current_timestamp = time.time()
    found = False
    if not title:
        title = str(new_data['title'][0]).lower()

    else:
        title = str(title.lower())

    if not year:
        year = int(new_data['year'][0])

    else:
        year = int(year)

    for cite in citation_data:
        if title == cite['title'].lower() and year == int(cite['year']):
            found = True
            cite['last_update'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(current_timestamp))

            if new_data['cluster_id'][0]:
                cite['scholar']['cluster_id'] = str(new_data['cluster_id'][0])

            if new_data['num_citations'][0]:
                cite['scholar']['total_citations'] = int(new_data['num_citations'][0])

            if new_data['url_pdf'][0]:
                cite['scholar']['pdf_url'] = str(new_data['url_pdf'][0])

            if new_data['url_citations'][0]:
                cite['scholar']['citation_list_url'] = str(new_data['url_citations'][0])

            break

    if not found and insert_new:

        current_cite = {
            'title': title,
            'year': year,
            'last_update': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(current_timestamp)),
            'scholar': {}
        }

        if new_data['cluster_id'][0]:
            current_cite['scholar']['cluster_id'] = str(new_data['cluster_id'][0])

        if new_data['num_citations'][0]:
            current_cite['scholar']['total_citations'] = int(new_data['num_citations'][0])

        if new_data['url_pdf'][0]:
            current_cite['scholar']['pdf_url'] = str(new_data['url_pdf'][0])

        if new_data['url_citations'][0]:
            current_cite['scholar']['citation_list_url'] = str(new_data['url_citations'][0])

        citation_data.append(current_cite)

    return citation_data


def update_citation_data_empty(citation_data, title, year):
    current_timestamp = time.time()

    current_cite = {
        'title': str(title).lower(),
        'year': int(year),
        'last_update': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(current_timestamp)),
        'scholar': {
            'total_citations': 0
        }
    }

    citation_data.append(current_cite)
    return citation_data


def load_citation_data(filename):
    if os.path.isfile(filename):
        try:
            with open(filename, 'r') as field:
                citation_data = yaml.load(field)

            if 'data' in citation_data:
                citation_data = citation_data['data']

            return citation_data

        except ValueError:
            logger.warn('[btex] Failed to load file [' + str(filename) + ']')
            return None

    else:
        logger.warning('[btex] No citation data file found [' + str(filename) + ']')
        return []


def save_citation_data(filename, citation_data):
    with open(filename, 'w') as outfile:
        outfile.write(yaml.dump(citation_data, default_flow_style=False))


def oldest_citation_update(citation_data, publications):
    cite_update = None
    for pub in publications:
        current_citation_data = get_citation_data(
            citation_data=citation_data,
            title=pub['title'],
            year=pub['year']
        )

        if current_citation_data and 'last_update' in current_citation_data:
            last_fetch = time.mktime(datetime.strptime(current_citation_data['last_update'], '%Y-%m-%d %H:%M:%S').timetuple())

            if not cite_update:
                cite_update = last_fetch

            if last_fetch < cite_update:
                cite_update = last_fetch

    return cite_update


def newest_citation_update(citation_data, publications):
    cite_update = None
    for pub in publications:
        current_citation_data = get_citation_data(
            citation_data=citation_data,
            title=pub['title'],
            year=pub['year']
        )

        if current_citation_data and 'last_update' in current_citation_data:
            last_fetch = time.mktime(datetime.strptime(current_citation_data['last_update'], '%Y-%m-%d %H:%M:%S').timetuple())

            if not cite_update:
                cite_update = last_fetch

            if last_fetch > cite_update:
                cite_update = last_fetch

    return cite_update


def get_publications_per_year(publications):
    stats = {}
    for pub in publications:
        if 'year' in pub:
            if pub['year'] not in stats:
                stats[pub['year']] = 0

            stats[pub['year']] += 1

    stats = collections.OrderedDict(sorted(stats.items()))
    return stats


def get_cites_per_year(publications):
    stats = {}
    for pub in publications:
        if 'year' in pub:
            if pub['year'] not in stats:
                stats[pub['year']] = 0

            if 'cites' in pub:
                stats[pub['year']] += pub['cites']

    stats = collections.OrderedDict(sorted(stats.items()))
    return stats


def process_page_metadata(generator, metadata):
    """
    Process page metadata and assign css and styles

    """

    if u'styles' not in metadata:
        metadata[u'styles'] = []
    if u'scripts' not in metadata:
        metadata[u'scripts'] = []


def move_resources(gen):
    """
    Move files from js/css folders to output folder, use minified files.

    """

    plugin_paths = gen.settings['PLUGIN_PATHS']
    if btex_settings['minified']:
        if btex_settings['generate_minified']:
            minify_css_directory(gen=gen, source='css', target='css.min')
            minify_js_directory(gen=gen, source='js', target='js.min')

        css_target = os.path.join(gen.output_path, 'theme', 'css', 'btex.min.css')
        js_target = os.path.join(gen.output_path, 'theme', 'js', 'btex.min.js')
        if not os.path.exists(os.path.join(gen.output_path, 'theme', 'js')):
            os.makedirs(os.path.join(gen.output_path, 'theme', 'js'))

        if not os.path.exists(os.path.join(gen.output_path, 'theme', 'css')):
            os.makedirs(os.path.join(gen.output_path, 'theme', 'css'))

        for path in plugin_paths:
            css_source = os.path.join(path, 'pelican-btex', 'css.min', 'btex.min.css')
            js_source = os.path.join(path, 'pelican-btex', 'js.min', 'btex.min.js')

            if os.path.isfile(css_source):  # and not os.path.isfile(css_target):
                shutil.copyfile(css_source, css_target)

            if os.path.isfile(js_source):  # and not os.path.isfile(js_target):
                shutil.copyfile(js_source, js_target)

            if os.path.isfile(js_target) and os.path.isfile(css_target):
               break

    else:
        css_target = os.path.join(gen.output_path, 'theme', 'css', 'btex.css')
        js_target = os.path.join(gen.output_path, 'theme', 'js', 'btex.js')
        if not os.path.exists(os.path.join(gen.output_path, 'theme', 'js')):
            os.makedirs(os.path.join(gen.output_path, 'theme', 'js'))

        for path in plugin_paths:
            css_source = os.path.join(path, 'pelican-btex', 'css', 'btex.css')
            js_source = os.path.join(path, 'pelican-btex', 'js', 'btex.js')

            if os.path.isfile(css_source):  # and not os.path.isfile(css_target):
                shutil.copyfile(css_source, css_target)

            if os.path.isfile(js_source):  # and not os.path.isfile(js_target):
                shutil.copyfile(js_source, js_target)

            if os.path.isfile(js_target) and os.path.isfile(css_target):
                break


def minify_css_directory(gen, source, target):
    """
    Move CSS resources from source directory to target directory and minify. Using rcssmin.

    """
    import rcssmin

    plugin_paths = gen.settings['PLUGIN_PATHS']
    for path in plugin_paths:
        source_ = os.path.join(path, 'pelican-btex', source)
        target_ = os.path.join(path, 'pelican-btex', target)
        if os.path.isdir(source_):
            if not os.path.exists(target_):
                os.makedirs(target_)

            for root, dirs, files in os.walk(source_):
                for current_file in files:
                    if current_file.endswith(".css"):
                        current_file_path = os.path.join(root, current_file)
                        with open(current_file_path) as css_file:
                            with open(os.path.join(target_, current_file.replace('.css', '.min.css')), "w") as minified_file:
                                minified_file.write(rcssmin.cssmin(css_file.read(), keep_bang_comments=True))


def minify_js_directory(gen, source, target):
    """
    Move JS resources from source directory to target directory and minify.

    """

    from jsmin import jsmin

    plugin_paths = gen.settings['PLUGIN_PATHS']
    for path in plugin_paths:
        source_ = os.path.join(path, 'pelican-btex', source)
        target_ = os.path.join(path, 'pelican-btex', target)

        if os.path.isdir(source_):
            if not os.path.exists(target_):
                os.makedirs(target_)

            for root, dirs, files in os.walk(source_):
                for current_file in files:
                    if current_file.endswith(".js"):
                        current_file_path = os.path.join(root, current_file)
                        with open(current_file_path) as js_file:
                            with open(os.path.join(target_, current_file.replace('.js', '.min.js')), "w") as minified_file:
                                minified_file.write(jsmin(js_file.read()))


def init_default_config(pelican):
    # Handle settings from pelicanconf.py
    btex_settings['site-url'] = pelican.settings['SITEURL']

    if 'BTEX_SCHOLAR_ACTIVE' in pelican.settings:
        btex_settings['google_scholar']['active'] = pelican.settings['BTEX_SCHOLAR_ACTIVE']

    if 'BTEX_SCHOLAR_FETCH_TIMEOUT' in pelican.settings:
        btex_settings['google_scholar']['fetching_timeout'] = pelican.settings['BTEX_SCHOLAR_FETCH_TIMEOUT']

    if 'BTEX_SCHOLAR_MAX_ENTRIES_PER_BATCH' in pelican.settings:
        btex_settings['google_scholar']['max_updated_entries_per_batch'] = pelican.settings['BTEX_SCHOLAR_MAX_ENTRIES_PER_BATCH']

    if 'BTEX_MINIFIED' in pelican.settings:
        btex_settings['minified'] = pelican.settings['BTEX_MINIFIED']

    if 'BTEX_GENERATE_MINIFIED' in pelican.settings:
        btex_settings['generate_minified'] = pelican.settings['BTEX_GENERATE_MINIFIED']

    if 'BTEX_USE_FONTAWESOME_CDN' in pelican.settings:
        btex_settings['use_fontawesome_cdn'] = pelican.settings['BTEX_USE_FONTAWESOME_CDN']

    if 'BTEX_DEBUG_PROCESSING' in pelican.settings:
        btex_settings['debug_processing'] = pelican.settings['BTEX_DEBUG_PROCESSING']


def register():
    signals.initialized.connect(init_default_config)
    signals.article_generator_context.connect(process_page_metadata)
    signals.page_generator_context.connect(process_page_metadata)

    signals.article_generator_finalized.connect(move_resources)
    signals.content_object_init.connect(btex)