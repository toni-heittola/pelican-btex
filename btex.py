# -*- coding: utf-8 -*-
"""
Publication list plugin for Pelican
===================================
Author: Toni Heittola (toni.heittola@gmail.com)

Pelican plugin to produce publication lists automatically from BibTeX-file.

"""

from IPython import embed
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
from random import randint
from time import sleep

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
        item['toolbox'] = entry.fields.get('_toolbox', None)
        item['clients'] = entry.fields.get('_clients', None)
        item['slides'] = entry.fields.get('_slides', None)
        item['poster'] = entry.fields.get('_poster', None)

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
                                            <a href="{{item.pdf}}" class="btn btn-xs btn-warning" style="text-decoration:none;border-bottom:0;padding-bottom:5px" rel="tooltip" title="Download pdf" data-placement="bottom"><i class="fa fa-file-pdf-o fa-1x"></i> PDF</a>
                                        {% endif %}
                                        {% if item.demo %}
                                            <a href="{{item.demo}}" class="btn btn-xs btn-primary iframeDemo" style="text-decoration:none;border-bottom:0;padding-bottom:5px" rel="tooltip" title="Demo" data-placement="bottom"><i class="fa fa-headphones"></i> Demo</a>
                                        {% endif %}
                                        {% if item.toolbox %}
                                            <a href="{{item.toolbox}}" class="btn btn-xs btn-success" style="text-decoration:none;border-bottom:0;padding-bottom:5px" rel="tooltip" title="Toolbox" data-placement="bottom"><i class="fa fa-file-code-o"></i> Toolbox</a>
                                        {% endif %}
                                        {% if item.data1 %}
                                            <a href="{{item.data1.url}}" class="btn btn-xs btn-info" style="text-decoration:none;border-bottom:0;padding-bottom:5px" rel="tooltip" title="{{item.data1.title}}" data-placement="bottom"><i class="fa fa-database"></i></a>
                                        {% endif %}
                                        {% if item.data2 %}
                                            <a href="{{item.data2.url}}" class="btn btn-xs btn-info" style="text-decoration:none;border-bottom:0;padding-bottom:5px" rel="tooltip" title="{{item.data2.title}}" data-placement="bottom"><i class="fa fa-database"></i></a>
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
                                        <a href="{{item.pdf}}" class="btn btn-sm btn-warning" style="text-decoration:none;border-bottom:0;padding-bottom:9px" rel="tooltip" title="Download pdf" data-placement="bottom"><i class="fa fa-file-pdf-o fa-1x"></i> PDF</a>
                                    {% endif %}
                                    {% if item.slides %}
                                        <a href="{{item.slides}}" class="btn btn-sm btn-info" style="text-decoration:none;border-bottom:0;padding-bottom:9px" rel="tooltip" title="Download slides" data-placement="bottom"><i class="fa fa-file-powerpoint-o"></i> Slides</a>
                                    {% endif %}
                                    {% if item.webpublication %}
                                        <a href="{{item.webpublication.url}}" class="btn btn-sm btn-info" style="text-decoration:none;border-bottom:0;padding-bottom:9px" title="{{item.webpublication.title}}"><i class="fa fa-book"></i> Web publication</a>
                                    {% endif %}
                                </div>
                                <div class="btn-group">
                                {% if item.toolbox %}
                                    <a href="{{item.toolbox}}" class="btn btn-sm btn-success" style="text-decoration:none;border-bottom:0;padding-bottom:9px" rel="tooltip" title="Toolbox" data-placement="bottom"><i class="fa fa-file-code-o"></i> Toolbox</a>
                                {% endif %}
                                {% if item.data1 %}
                                    <a href="{{item.data1.url}}" class="btn btn-sm btn-info" style="text-decoration:none;border-bottom:0;padding-bottom:9px" rel="tooltip" title="Toolbox" data-placement="bottom"><i class="fa fa-database"></i> {{item.data1.title}}</a>
                                {% endif %}
                                {% if item.data2 %}
                                    <a href="{{item.data2.url}}" class="btn btn-sm btn-info" style="text-decoration:none;border-bottom:0;padding-bottom:9px" rel="tooltip" title="Toolbox" data-placement="bottom"><i class="fa fa-database"></i> {{item.data2.title}}</a>
                                {% endif %}
                                {% if item.code1 %}
                                    <a href="{{item.code1.url}}" class="btn btn-sm btn-success" style="text-decoration:none;border-bottom:0;padding-bottom:9px" title="{{item.code1.title}}"><i class="fa fa-file-code-o"></i> {{item.code1.title}}</a>
                                {% endif %}
                                {% if item.code2 %}
                                    <a href="{{item.code2.url}}" class="btn btn-sm btn-success" style="text-decoration:none;border-bottom:0;padding-bottom:9px" title="{{item.code2.title}}"><i class="fa fa-file-code-o"></i> {{item.code2.title}}</a>
                                {% endif %}
                                {% if item.demo %}
                                    <a href="{{item.demo}}" class="btn btn-sm btn-primary iframeDemo" style="text-decoration:none;border-bottom:0;padding-bottom:9px" rel="tooltip" title="Demo" data-placement="bottom"><i class="fa fa-headphones"></i> Demo</a>
                                {% endif %}
                                {% if item.link1 %}
                                    <a href="{{item.link1.url}}" class="btn btn-sm btn-info" style="text-decoration:none;border-bottom:0;padding-bottom:9px" title="{{item.link1.title}}"><i class="fa fa-external-link-square"></i> {{item.link1.title}}</a>
                                {% endif %}
                                {% if item.link2 %}
                                    <a href="{{item.link2.url}}" class="btn btn-sm btn-info" style="text-decoration:none;border-bottom:0;padding-bottom:9px" title="{{item.link2.title}}"><i class="fa fa-external-link-square"></i> {{item.link2.title}}</a>
                                {% endif %}
                                {% if item.link3 %}
                                    <a href="{{item.link3.url}}" class="btn btn-sm btn-info" style="text-decoration:none;border-bottom:0;padding-bottom:9px" title="{{item.link3.title}}"><i class="fa fa-external-link-square"></i> {{item.link3.title}}</a>
                                {% endif %}
                                {% if item.link4 %}
                                    <a href="{{item.link4.url}}" class="btn btn-sm btn-info" style="text-decoration:none;border-bottom:0;padding-bottom:9px" title="{{item.link4.title}}"><i class="fa fa-external-link-square"></i> {{item.link4.title}}</a>
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
                        <a href="bibtexx_md#{{item.key}}" title="Read more..." style="text-decoration:none;border-bottom:0;" ><i class="fa fa-arrow-circle-right"></i></a>
                    </div>
                    <div class="col-xs-3">
                        <div class="btn-group">
                            <button type="button" class="btn btn-xs btn-danger" data-toggle="modal" data-target="#bibtex{{ item.key }}"><i class="fa fa-file-text-o"></i> Bib</button>
                            {% if item.pdf %}
                                <a href="{{item.pdf}}" class="btn btn-xs btn-warning" style="text-decoration:none;border-bottom:0;padding-bottom:5px" rel="tooltip" title="Download pdf" data-placement="bottom"><i class="fa fa-file-pdf-o fa-1x"></i> PDF</a>
                            {% endif %}
                            {% if item.demo %}
                                <a href="{{item.demo}}" class="btn btn-xs btn-primary iframeDemo" style="text-decoration:none;border-bottom:0;padding-bottom:5px" rel="tooltip" title="Demo" data-placement="bottom"><i class="fa fa-headphones"></i> Demo</a>
                            {% endif %}
                            {% if item.toolbox %}
                                <a href="{{item.toolbox}}" class="btn btn-xs btn-success" style="text-decoration:none;border-bottom:0;padding-bottom:5px" rel="tooltip" title="Toolbox" data-placement="bottom"><i class="fa fa-file-code-o"></i> Toolbox</a>
                            {% endif %}
                            {% if item.data1 %}
                                <a href="{{item.data1.url}}" class="btn btn-xs btn-info" style="text-decoration:none;border-bottom:0;padding-bottom:5px" rel="tooltip" title="{{item.data1.title}}" data-placement="bottom"><i class="fa fa-database"></i></a>
                            {% endif %}
                            {% if item.data2 %}
                                <a href="{{item.data2.url}}" class="btn btn-xs btn-info" style="text-decoration:none;border-bottom:0;padding-bottom:5px" rel="tooltip" title="{{item.data2.title}}" data-placement="bottom"><i class="fa fa-database"></i></a>
                            {% endif %}
                            {% if item.code1 %}
                                <a href="{{item.code1.url}}" class="btn btn-xs btn-success" style="text-decoration:none;border-bottom:0;padding-bottom:5px" rel="tooltip" title="{{item.code1.title}}" data-placement="bottom"><i class="fa fa-file-code-o"></i></a>
                            {% endif %}
                            {% if item.code2 %}
                                <a href="{{item.code2.url}}" class="btn btn-xs btn-success"  style="text-decoration:none;border-bottom:0;padding-bottom:5px" rel="tooltip" title="{{item.code2.title}}" data-placement="bottom"><i class="fa fa-file-code-o"></i></a>
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
                                        <a href="{{item.pdf}}" class="btn btn-xs btn-warning" style="text-decoration:none;border-bottom:0;padding-bottom:5px" rel="tooltip" title="Download pdf" data-placement="bottom"><i class="fa fa-file-pdf-o fa-1x"></i> PDF</a>
                                    {% endif %}
                                    {% if item.demo %}
                                        <a href="{{item.demo}}" class="btn btn-xs btn-primary iframeDemo" style="text-decoration:none;border-bottom:0;padding-bottom:5px" rel="tooltip" title="Demo" data-placement="bottom"><i class="fa fa-headphones"></i> Demo</a>
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
                                <a href="{{item.pdf}}" class="btn btn-sm btn-warning" style="text-decoration:none;border-bottom:0;padding-bottom:9px" rel="tooltip" title="Download pdf" data-placement="bottom"><i class="fa fa-file-pdf-o fa-1x"></i> PDF</a>
                            {% endif %}
                            {% if item.slides %}
                                <a href="{{item.slides}}" class="btn btn-sm btn-info" style="text-decoration:none;border-bottom:0;padding-bottom:9px" rel="tooltip" title="Download slides" data-placement="bottom"><i class="fa fa-file-powerpoint-o"></i> Slides</a>
                            {% endif %}
                            {% if item.webpublication %}
                                <a href="{{item.webpublication.url}}" style="text-decoration:none;border-bottom:0;padding-bottom:9px" class="btn btn-sm btn-info" title="{{item.webpublication.title}}"><i class="fa fa-book"></i> Web publication</a>
                            {% endif %}
                            </div>
                            <div class="btn-group">
                            {% if item.demo %}
                                <a href="{{item.demo}}" style="text-decoration:none;border-bottom:0;padding-bottom:9px" class="btn btn-sm btn-primary iframeDemo" rel="tooltip" title="Demo" data-placement="bottom"><i class="fa fa-headphones"></i> Demo</a>
                            {% endif %}
                            {% if item.link1 %}
                                <a href="{{item.link1.url}}" style="text-decoration:none;border-bottom:0;padding-bottom:9px" class="btn btn-sm btn-info" title="{{item.link1.title}}"><i class="fa fa-external-link-square"></i> {{item.link1.title}}</a>
                            {% endif %}
                            {% if item.link2 %}
                                <a href="{{item.link2.url}}" style="text-decoration:none;border-bottom:0;padding-bottom:9px" class="btn btn-sm btn-info" title="{{item.link2.title}}"><i class="fa fa-external-link-square"></i> {{item.link2.title}}</a>
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
                <strong class="text-muted">{{year}}</strong>
                {% for item in year_group|sort(attribute='year') %}
                    <div class="row">
                        <div class="col-md-1">
                            <span class="{{ item.type_label_css }}">{{ item.type_label_short }}</span>
                        </div>
                        <div class="col-md-11">
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
            {% endfor %}
        """
    return template


def btex_parse(content):
    if isinstance(content, contents.Static):
        return

    soup = BeautifulSoup(content._content, 'html.parser')
    btex_divs = soup.find_all('div', class_='btex')

    for btex_div in btex_divs:
        options = {}
        options['css'] = btex_div['class']
        options['data_source'] = get_attribute(btex_div.attrs, 'source', None)
        options['template'] = get_attribute(btex_div.attrs, 'template', 'publications')

        options['years'] = get_attribute(btex_div.attrs, 'years', None)
        options['scholar-cite-counts'] = boolean(get_attribute(btex_div.attrs, 'scholar-cite-counts', 'no'))
        options['scholar-link'] = get_attribute(btex_div.attrs, 'scholar-link', None)

        options['stats'] = boolean(get_attribute(btex_div.attrs, 'stats', 'no'))

        if options['years']:
            options['first_visible_year'] = int(datetime.now().strftime('%Y')) - int(options['years'])
        else:
            options['first_visible_year'] = ''
        publications = parse_bibtex_file(options['data_source'])

        meta = {}
        if 'scholar-cite-counts' in options and options['scholar-cite-counts']:
            google_queries = 0
            citation_tmp_cache = []

            # Greedy way to grab most common author
            if os.path.isfile(btex_settings['google_scholar']['cache_filename']):
                citation_cache = pickle.load(open(btex_settings['google_scholar']['cache_filename'], 'rb'))
            else:
                citation_cache = {}

            google_access_valid = btex_settings['google_scholar']['active']
            if google_access_valid:
                try:
                    import scholar.scholar as sc

                    author_list = []
                    citation_update_needed = False
                    citation_update_count = 0
                    for pub in publications:
                        for author in pub['authors']:
                            name = " ".join(author.first()) + " " + " ".join(author.last())
                            author_list.append(name)

                            # Form author list
                            authors = []
                            for author in pub['authors']:
                                authors.append(" ".join(author.first()) + " " + " ".join(author.last()))
                            authors = ", ".join(authors)
                            # Form cache key
                            cache_key = authors + pub['title']
                            cache_key_hash = hashlib.md5(cache_key.encode('utf-8')).hexdigest()

                            if cache_key_hash in citation_cache:
                                last_fetch = int(citation_cache[cache_key_hash]['time_stamp'])
                                if btex_settings['google_scholar']['fetching_timeout'] + last_fetch < time.time():
                                    citation_update_needed = True
                                    citation_update_count += 1
                            else:
                                citation_update_needed = True
                                citation_update_count += 1

                    if citation_update_needed and google_queries < btex_settings['google_scholar']['max_updated_entries_per_batch']:
                        # Fetch 19 first papers from most common author.
                        # This is one way to minimize the amount of queries to Google.
                        logger.warning(" Citation update needed for articles: " +str(citation_update_count))

                        most_common_author = max(set(author_list), key=author_list.count)
                        querier = sc.ScholarQuerier()
                        settings = sc.ScholarSettings()
                        querier.apply_settings(settings)

                        query = sc.SearchScholarQuery()
                        query.set_author(most_common_author)  # Author
                        query.set_num_page_results(19)
                        querier.send_query(query)
                        google_queries += 1
                        if len(querier.articles):
                            for a in querier.articles:
                                citation_tmp_cache.append(a.attrs)
                        else:
                            google_access_valid = False
                            logger.warning("    It seems your Google access quota is exceeded! ")

                    # Go publications through paper by paper
                    for pub in publications:
                        article_data = None
                        current_timestamp = time.time()

                        for a in citation_tmp_cache:
                            if a['title'][0] == pub['title']:
                                article_data = a
                                break

                        if not article_data and google_access_valid and google_queries < btex_settings['google_scholar']['max_updated_entries_per_batch']:
                            # We did now have article in the cache, check can we query google, as we
                            # only update specified amount of entries (to avoid filling google access quota) with
                            # specified time intervals
                            citation_update_needed = False

                            # Form author list
                            authors = []
                            for author in pub['authors']:
                                authors.append(" ".join(author.first()) + " " + " ".join(author.last()))
                            authors = ", ".join(authors)

                            # Form cache key
                            cache_key = authors+pub['title']
                            cache_key_hash = hashlib.md5(cache_key.encode('utf-8')).hexdigest()

                            if cache_key_hash in citation_cache:
                                last_fetch = int(citation_cache[cache_key_hash]['time_stamp'])
                                if btex_settings['google_scholar']['fetching_timeout'] + last_fetch < current_timestamp:
                                    citation_update_needed = True
                            else:
                                # We have a new article
                                citation_update_needed = True

                            if citation_update_needed:
                                # Fetch article from google
                                #print "  Query publication ["+pub['title']+"]"
                                logger.warning("  Query publication ["+pub['title']+"]")

                                querier = sc.ScholarQuerier()
                                settings = sc.ScholarSettings()
                                querier.apply_settings(settings)

                                query = sc.SearchScholarQuery()
                                query.set_author(authors.split(',')[0])  # Authors
                                query.set_phrase(pub['title'])  # Title
                                query.set_scope(True)  # Title only
                                query.set_num_page_results(1)

                                querier.send_query(query)
                                google_queries += 1
                                if len(querier.articles):
                                    article_data = querier.articles[0].attrs
                                    logger.warning("    Cites: "+str(article_data['num_citations'][0]))
                                else:
                                    logger.warning("    Nothing returned, article might not be indexed by Google or your access quota is exceeded! ")

                                # Wait after each query random time in order to avoid flooding Google.
                                wait_time = randint(btex_settings['google_scholar']['fetch_item_timeout'][0],
                                                    btex_settings['google_scholar']['fetch_item_timeout'][1])
                                print "  Sleeping [" + str(wait_time) + " sec]"
                                sleep(wait_time)

                        if article_data:
                            if cache_key_hash not in citation_cache or (article_data['num_citations'][0] > 0 and citation_cache[cache_key_hash]['article_data']['num_citations'][0] == 0):
                                #print "    UPDATED"
                                logger.warning("    UPDATED")
                                if cache_key_hash in citation_cache:
                                    citation_cache[cache_key_hash]['time_stamp'] = current_timestamp
                                    citation_cache[cache_key_hash]['article_data'] = article_data
                                else:
                                    citation_cache[cache_key_hash] = {
                                        'time_stamp': current_timestamp,
                                        'article_data': article_data
                                    }
                            else:
                                if cache_key_hash in citation_cache:
                                    citation_cache[cache_key_hash]['time_stamp'] = current_timestamp
                                else:
                                    citation_cache[cache_key_hash] = {
                                        'time_stamp': current_timestamp,
                                    }
                            if 'article_data' in citation_cache[cache_key_hash] and 'num_citations' in citation_cache[cache_key_hash]['article_data']:
                                pub['cites'] = citation_cache[cache_key_hash]['article_data']['num_citations'][0]

                            if 'article_data' in citation_cache[cache_key_hash] and 'url_citations' in citation_cache[cache_key_hash]['article_data']:
                                pub['citation_url'] = citation_cache[cache_key_hash]['article_data']['url_citations'][0]

                            # Save citation cache each time to avoid loosing data.
                            pickle.dump(citation_cache, open(btex_settings['google_scholar']['cache_filename'], "wb"))
                        else:
                            pub['cites'] = 0

                except ImportError:
                    logger.warning('`pelican_btex` failed to import `scholar`')
                    pass

            else:
                for pub in publications:
                    # Form author list
                    authors = []
                    for author in pub['authors']:
                        authors.append(" ".join(author.first()) + " " + " ".join(author.last()))
                    authors = ", ".join(authors)

                    # Form cache key
                    cache_key = authors + pub['title']
                    cache_key_hash = hashlib.md5(cache_key.encode('utf-8')).hexdigest()
                    if cache_key_hash in citation_cache:
                        if 'article_data' in citation_cache[cache_key_hash] and 'num_citations' in citation_cache[cache_key_hash]['article_data']:
                            pub['cites'] = citation_cache[cache_key_hash]['article_data']['num_citations'][0]
                        else:
                            pub['cites'] = 0

                        if 'article_data' in citation_cache[cache_key_hash] and 'url_citations' in citation_cache[cache_key_hash]['article_data']:
                            pub['citation_url'] = citation_cache[cache_key_hash]['article_data']['url_citations'][0]
                        else:
                            pub['citation_url'] = None
                    else:
                        pub['cites'] = 0

            meta['cite_update'] = oldest_citation_update(citation_cache, publications)

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

            if 'cite_update' in meta:
                meta['cite_update_string'] = format(datetime.fromtimestamp(meta['cite_update']), '%d.%m.%Y')
        div_text = btex_div.text
        div_text = div_text.rstrip('\r\n').replace(" ", "")
        has_template = False
        if len(div_text):
            has_template = True

        if not has_template:
            btex_div.string = get_default_template(options)

        template = Template(btex_div.prettify().strip('\t\r\n').replace('&gt;', '>').replace('&lt;', '<'))

        div_html = BeautifulSoup(template.render(publications=publications,
                                                 meta=meta,
                                                 publication_grouping=btex_publication_grouping,
                                                 first_visible_year=options['first_visible_year']
                                                 ), "html.parser")
        btex_div.replaceWith(div_html)

    if btex_settings['minified']:
        html_elements = {
            'js_include': [
                '<script type="text/javascript" src="theme/js/btex.min.js"></script>'
            ],
            'css_include': [
            #    '<link rel="stylesheet" href="theme/css/btex.min.css">'
            ]
        }
    else:
        html_elements = {
            'js_include': [
                '<script type="text/javascript" src="theme/js/btex.js"></script>'
            ],
            'css_include': [
            #    '<link rel="stylesheet" href="theme/css/btex.css">'
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


def oldest_citation_update(citation_cache, publications):
    cite_update = None
    for pub in publications:
        # Form author list
        authors = []
        for author in pub['authors']:
            authors.append(" ".join(author.first()) + " " + " ".join(author.last()))
        authors = ", ".join(authors)

        # Form cache key
        cache_key = authors + pub['title']
        cache_key_hash = hashlib.md5(cache_key.encode('utf-8')).hexdigest()

        if cache_key_hash in citation_cache:
            last_fetch = int(citation_cache[cache_key_hash]['time_stamp'])

            # store latest fetch timestamp
            if not cite_update:
                cite_update = last_fetch
            if last_fetch < cite_update:
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
            #minify_css_directory(gen=gen, source='css', target='css.min')
            minify_js_directory(gen=gen, source='js', target='js.min')

        #css_target = os.path.join(gen.output_path, 'theme', 'css', 'btex.min.css')
        js_target = os.path.join(gen.output_path, 'theme', 'js', 'btex.min.js')
        if not os.path.exists(os.path.join(gen.output_path, 'theme', 'js')):
            os.makedirs(os.path.join(gen.output_path, 'theme', 'js'))

        for path in plugin_paths:
            #css_source = os.path.join(path, 'pelican-btex', 'css.min', 'btex.min.css')
            js_source = os.path.join(path, 'pelican-btex', 'js.min', 'btex.min.js')

            #if os.path.isfile(css_source):  # and not os.path.isfile(css_target):
            #    shutil.copyfile(css_source, css_target)

            if os.path.isfile(js_source):  # and not os.path.isfile(js_target):
                shutil.copyfile(js_source, js_target)

            if os.path.isfile(js_target): # and os.path.isfile(css_target):
               break
    else:
        #css_target = os.path.join(gen.output_path, 'theme', 'css', 'btex.css')
        js_target = os.path.join(gen.output_path, 'theme', 'js', 'btex.js')
        if not os.path.exists(os.path.join(gen.output_path, 'theme', 'js')):
            os.makedirs(os.path.join(gen.output_path, 'theme', 'js'))

        for path in plugin_paths:
            #css_source = os.path.join(path, 'pelican-btex', 'css', 'btex.css')
            js_source = os.path.join(path, 'pelican-btex', 'js', 'btex.js')

            #if os.path.isfile(css_source):  # and not os.path.isfile(css_target):
            #    shutil.copyfile(css_source, css_target)

            if os.path.isfile(js_source):  # and not os.path.isfile(js_target):
                shutil.copyfile(js_source, js_target)

            if os.path.isfile(js_target): # and os.path.isfile(css_target):
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


def register():
    signals.initialized.connect(init_default_config)
    signals.content_object_init.connect(btex_parse)
    signals.article_generator_context.connect(process_page_metadata)
    signals.page_generator_context.connect(process_page_metadata)

    signals.article_generator_finalized.connect(move_resources)
