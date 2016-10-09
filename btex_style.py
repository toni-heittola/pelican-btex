# pybtex style for pelican-btex
# based on plain style of pybtex

import re
from pybtex.style.formatting.unsrt import Style as UnsrtStyle
from pybtex.style.formatting import BaseStyle, toplevel
from pybtex.style.template import (
    join, words, field, optional, first_of,
    names, sentence, tag, optional_field, href
)
from pybtex.richtext import Text, Symbol
from IPython import embed


def dashify(text):
    dash_re = re.compile(r'-+')
    return Text(Symbol('ndash')).join(dash_re.split(text.plaintext()))

pages = field('pages', apply_func=dashify)

date = words[optional_field('month'), field('year')]


class Style(UnsrtStyle):
    name = 'btex'

    def format_btitle(self, e, which_field, as_sentence=True):
        formatted_title = field(which_field)
        if as_sentence:
            return sentence[ formatted_title ]
        else:
            return formatted_title

    def format_title(self, e, which_field, as_sentence=True):

        def protected_capitalize(x):
            """Capitalize string, but protect {...} parts."""
            return x.capitalize().plaintext()

        formatted_title = field(which_field, apply_func=protected_capitalize)

        if as_sentence:
            return tag('emph') [sentence(capfirst=False) [ formatted_title ]]
        else:
            return tag('emph') [formatted_title]

    def format_names(self, role, as_sentence=True):
        formatted_names = names(role, sep=', ', sep2 = ' and ', last_sep=', and ')
        if as_sentence:
            return sentence(capfirst=False) [formatted_names]
        else:
            return formatted_names

    def format_article(self, e):
        volume_and_pages = first_of[
            # volume and pages, with optional issue number
            optional[
                join[
                    field('volume'),
                    optional['(', field('number'), ')'],
                    ':', pages
                ],
            ],
            # pages only
            words['pp', pages],
        ]
        template = toplevel[
            self.format_names('author'),
            self.format_title(e, 'title'),
            sentence(capfirst=False)[
                field('journal'),
                optional[volume_and_pages],
                date],
            sentence(capfirst=False)[optional_field('note')],
            #self.format_web_refs(e),
        ]

        return template.format_data(e)

    def format_book(self, e):
        template = toplevel [
            words[sentence [self.format_names('author')], '(Eds.)'],
            self.format_title(e, 'title'),
            sentence[date],
            words['ISBN: ', sentence(capfirst=False) [ optional_field('isbn') ]],
        ]
        return template.format_data(e)

    def format_incollection(self, e):
        template = toplevel [
            self.format_names('author'),
            sentence(capfirst=False) [
                self.format_title(e, 'title'),
            ],
            sentence(capfirst=False) [
                field('booktitle'),
                field('series'),
                optional[
                    words['pp', field('pages')],
                ],
                date,
            ],
        ]
        return template.format_data(e)

    def format_inproceedings(self, e):
        template = toplevel[
            sentence[self.format_names('author')],
            self.format_title(e, 'title'),
            words[
                'In',
                sentence(capfirst=False)[
                    optional[self.format_editor(e, as_sentence=False)],
                    self.format_btitle(e, 'booktitle', as_sentence=False),
                    self.format_volume_and_series(e, as_sentence=False),
                    optional[
                        words['pp', field('pages')],
                    ],
                ],
                self.format_address_organization_publisher_date(e),
            ],
            sentence(capfirst=False)[optional_field('note')],
            #self.format_web_refs(e),
        ]
        return template.format_data(e)

    def format_patent(self, e):
        template = toplevel[
            sentence[self.format_names('author')],
            self.format_title(e, 'title'),
            sentence(capfirst=False)[
                tag('emph')[field('number')],
                date],
        ]
        return template.format_data(e)

    def format_mastersthesis(self, e):
        template = toplevel[
            sentence[self.format_names('author')],
            self.format_title(e, 'title'),
            sentence[
                "Master's thesis",
                field('school'),
                optional_field('address'),
                date,
            ],
            sentence(capfirst=False)[optional_field('note')],
            #self.format_web_refs(e),
        ]
        return template.format_data(e)

    def format_misc(self, e):
        if '_subtype' in e.fields and e.fields['_subtype'] == 'studentproject':
            template = toplevel [
                sentence [self.format_names('author')],
                self.format_title(e, 'title'),
                sentence[
                    field('_school'),
                    field('_course'),
                    date,
                ],
                sentence(capfirst=False) [ optional_field('note') ],
                #self.format_web_refs(e),
            ]
        else:
            template = toplevel [
                sentence [self.format_names('author')],
                self.format_title(e, 'title'),
                sentence[
                    date,
                ],
                sentence(capfirst=False) [ optional_field('note') ],
                #self.format_web_refs(e),
            ]
        return template.format_data(e)