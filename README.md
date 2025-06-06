Pelican-btex - Automatic publication list generation for Pelican
================================================================

`pelican-btex` is an open source Pelican plugin to generate publication list automatically from a BibTeX-file. It is following idea of [pelican-bibtex](https://github.com/vene/pelican-bibtex) plugin by Vlad Niculae, however, the `pelican-btex` adds some key features:
 
 - Additional meta data through BibTeX, e.g. links to pdf, demos, code, and datasets.
 - Default templates for publication lists and possibility to use custom Jinja2 template
 - Grouping publications based on the publication type (journal, conference papers, etc.)
 - Fetch cite counts automatically from Google Scholar (using [scholar.py](https://github.com/ckreibich/scholar.py))

**Author**

Toni Heittola (toni.heittola@gmail.com), [GitHub](https://github.com/toni-heittola), [Home page](http://www.cs.tut.fi/~heittolt/)

Installation instructions
=========================

## Requirements

**pybtex** is required to process Bibtex files. To ensure that all external modules are installed, run:

    pip install -r requirements.txt

**bs4** (BeautifulSoup) for parsing HTML content

    pip install beautifulsoup4

**pybtex** for processing BIBTEX files

    pip install pybtex

**pyyaml**, for yaml reading 

    pip install pyyaml

In order to regenerate minified CSS and JS files you need also: 

**rcssmin** a CSS Minifier

    pip install rcssmin
    
**jsmin** a JS Minifier

    pip install jsmin
    
    
## Pelican installation

Make sure you include [Bootstrap](http://getbootstrap.com/) and [Jquery](https://jquery.com/) in your template. Default templates use icons from fontawesome, either use `BTEX_USE_FONTAWESOME_CDN` to include CDN version over internet or include local version in site template.

Make sure the directory where the plugin was installed is set in `pelicanconf.py`. For example if you installed in `plugins/pelican-btex`, add:

    PLUGIN_PATHS = ['plugins']

Enable pelican-btex:

    PLUGINS = ['pelican-btex']

To allow plugin in include css and js files, one needs to add following to the `base.html` template, in the head (to include css files):

    {% if article %}
        {% if article.styles %}
            {% for style in article.styles %}
    {{ style }}
            {% endfor %}
        {% endif %}
    {% endif %}
    {% if page %}
        {% if page.styles %}
            {% for style in page.styles %}
    {{ style }}
            {% endfor %}
        {% endif %}
    {% endif %}

At the bottom of the page before `</body>` tag (to include js files):

    {% if article %}
        {% if article.scripts %}
            {% for script in article.scripts %}
    {{ script }}
            {% endfor %}
        {% endif %}
    {% endif %}

    {% if page %}
        {% if page.scripts %}
            {% for script in page.scripts %}
    {{ script }}
            {% endfor %}
        {% endif %}
    {% endif %}

Usage
=====

Publication list generation is injected to `<div>` tags with class `btex`. 

| Parameter                 | Type      | Default       | Description  |
|---------------------------|-----------|---------------|--------------|
| data-source               | String    | None          | bibtex-file relative to the Pelican project root  |
| data-template             | String    | 'publications'  | Template type: `publications` (publications list), `minimal` (compact publications list), `latest` (compresses list of latest publications), and `supervisions` (list of supervised thesis and student projects).  |
| data-years                | Number    | None          | Number of the most recent year to be shown |
| data-stats                | Boolean   | False         | Show statistics of the publication list, e.g. entries per publication groups |
| data-citations            | String    | 'btex_citation_cache.yaml' | Citation cache file, YAML file |
| data-scholar-cite-counts  | Boolean   | False         | Query citation counts for the publications from Google Scholar |
| data-scholar-link         | String    | None          | Link to Google Scholar profile |
| data-target-page          | String    | None          | Page slug containing full publication list, used in `latest` template. |

Publication list showing citations counts and publications counts per publication types, example:
 
    <div class="btex" data-source="content/data/publications.bib" data-citations="content/data/citations.yaml" data-scholar-cite-counts="true" data-stats="true" data-template="publications"></div>
 
Latest publications from last two years, example:

    <div class="btex" data-source="content/data/publications.bib" data-years="2" data-template="latest" data-target-page="publications"></div>

### Bibtex

Plugin supports basic entry types (TechReport, InProceedings, Article, InCollection, Book, and Patent), and most of the commonly used fields. 

In addition to basic fields, there are some extra ones to associate information to the publications:
 
- `_award`, award associated to the publication
- `_pdf`, link to PDF associated to the publication
- `_slides`, link to Slides associated to the publication
- `_poster`, link to Poster associated to the publication
- `_webpublication`, link to web publication associated to the publication
- `_demo`, link to Demo associated to the publication
- `_demo_external`, link to external Demo associated to the publication
- `_toolbox`, link to Toolbox associated to the publication
- `_data1` and `_data2`, link to data packages associated to the publication
- `_code1` and `_code2`, link to code packages associated to the publication
- `_link1`, `_link2`, `_link3` and `_link4`, link to generic links associated to the publication, format: url##link-title
- `_clients`, client for the project, used with `supervision` template and `misc` entry type
- `_school`, school for the project, used with `supervision` template and `misc` entry type
- `_course`, school for the project, used with `supervision` template and `misc` entry type
- `_subtype`, sub type for the project, used with `supervision` template and `misc` entry type. Currently supported values: `studentproject`

All fields starting with underscore are omitted from bibtex found in `item.bibtex` (see Custon template section). 

### Custom template

One can use own custom template by having Jinja2 template within the `<div>`-tag. Fields:

- `meta`
    - `meta.publications`, publication count
    - `meta.types_html_list`, pre-formatted list of publication counts per type
    - `meta.cites`, total cite count
    - `meta.cite_update_string`, date string of oldest update article
    
- `publications`
    - `item.key`, bibtex key
    - `item.text`, formatted citation
    - `item.title`, title of the publication 
    - `item.abstract`, abstract if set in bibtex, use `abstract` field to set in bibtex
    - `item.keywords`, keywords if set in bibtex, use `keywords` field to set in bibtex
    - `item.bibtex`, raw bibtex entry
    - `item.type_label_short`, publication type label
    - `item.type_label_css`, css label class assigned to the publication type     
    - `item.award`, award associated to the publication, use `_award` field to set in bibtex
    - `item.cites`, cite count by Google Scholar
    - `item.pdf`, link to PDF associated to the publication, use `_pdf` field to set in bibtex
    - `item.slides`, link to Slides associated to the publication, use `_slides` field to set in bibtex
    - `item.webpublication`, link to web publication associated to the publication, use `_webpublication` field to set in bibtex
    - `item.demo`, link to Demo associated to the publication, use `_demo` field to set in bibtex
    - `item.toolbox`, link to Toolbox associated to the publication, use `_toolbox` field to set in bibtex
    - `item.data1` and `item.data2`, link to data packages associated to the publication, use `_data1` and `_data2` fields to set in bibtex
    - `item.code1` and `item.code2`, link to code packages associated to the publication, use `_code1` and `_code2` fields to set in bibtex
    - `item.link1`, `item.link2`, `item.link3`, and `item.link4`, link to generic links associated to the publication, use `_link1`, `_link2`, `_link3` and `_link4` fields to set in bibtex
 
 Example:
 
    <div class="btex" data-source="content/data/publications.bib" data-scholar-cite-counts="yes" data-stats="yes">    
        <div class="panel panel-default">
            <div class="panel-body">
                Publications: {{ meta.publications }} <span class="text-muted">({{ meta.types_html_list}})</span>
                <br>
                Cites: {{ meta.cites }} <small><span class="text-muted">(Updated {{  meta.cite_update_string }})</span></small>
            </div>
        </div>
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
    </div>
 
## Global parameters

Parameters for the plugin can be set in  `pelicanconf.py' with following parameters:

| Parameter                 | Type      | Default       | Description  |
|---------------------------|-----------|---------------|--------------|
| BTEX_SCHOLAR_ACTIVE       | Boolean   | True          | Activates Google Scholar citation count fetching  |
| BTEX_SCHOLAR_FETCH_TIMEOUT| Number    | 60*60*24*7    | Amount of seconds required between queries to Scholar per entry |
| BTEX_SCHOLAR_MAX_ENTRIES_PER_BATCH | Number    | 10       | How many queries are made per publication list generation |
| BTEX_SCHOLAR_USE_PROXY    | Boolean   | False         | Use freeproxies during Google Scholar fetching to avoid IP blocking, requires scholarly package (version >= 1.7.2) |
| BTEX_SCHOLAR_PROXY_ROTATIONS | Number | 10            | Amount of retries to find working proxy |
| BTEX_MINIFIED             | Boolean   | True          | Do we use minified CSS and JS files. Disable in case of debugging.  |
| BTEX_GENERATE_MINIFIED    | Boolean   | False         | CSS and JS files are minified each time, Enable in case of development.   |
| BTEX_USE_FONTAWESOME_CDN  | Boolean   | True          | Include CDN version of Fontawesome, disable if site template already includes this | 
| BTEX_DEBUG_PROCESSING     | Boolean   | False         | Show extra information in when run with `DEBUG=1` |

## Getting citation counts 

This plugin is fetching citation counts for articles from Google by using [scholarly](https://github.com/scholarly-python-package/scholarly) python package. As a fallback, the plugin uses [scholar.py](https://github.com/ckreibich/scholar.py). Google has query limits and exceeding these limits will blacklist your IP for a while. The plugin will try to minimize amount of queries and to use proxies when making queries. All query results are stored in the cache file at the root of the Pelican project (`btex_citation_cache.yaml`, or set file with `data-citations`). Timestamps are used to decide which articles needs update, and only predefined amount of queries are made per session.     
