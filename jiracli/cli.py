#!/usr/bin/env python
# -*- coding: utf-8 -*-

import getpass
import re
import os
import optparse
import tempfile
import xmlrpclib
import socket
import pickle
import sys
import xml
from termcolor import colored as colorfunc

JIRABASE = None
JIRAOBJ = None
TOKEN = None
TYPES = {}
COLOR = True
if not sys.stdout.isatty():
    colorfunc = lambda *a, **k: str(a[0])  # NOQA
    COLOR = False
DEFAULT_EDITOR_TEXT = '''-- enter the text for the %s
-- all lines starting with '--' will be removed'''


def get_text_from_editor(def_text):
    tmp = tempfile.mktemp()
    open(tmp, 'w').write(def_text)
    editor = os.environ.setdefault('EDITOR', 'vim')
    os.system('%s %s' % (editor, tmp))
    return '\n'.join([k for k in open(tmp).read().split('\n') if not k.startswith('--')])


def setup_home_dir():
    if not os.path.isdir(os.path.expanduser('~/.jira-cli')):
        os.makedirs(os.path.expanduser('~/.jira-cli'))


def get_issue_type(issuetype):
    if issuetype:
        issuetype = issuetype.lower()
    if os.path.isfile(os.path.expanduser('~/.jira-cli/types.pkl')):
        issue_types = pickle.load(open(os.path.expanduser('~/.jira-cli/types.pkl'), 'rb'))
    else:
        issue_types = JIRAOBJ.jira1.getIssueTypes(TOKEN)
        pickle.dump(issue_types, open(os.path.expanduser('~/.jira-cli/types.pkl'), 'wb'))

    if not issuetype:
        return issue_types
    else:
        for types in issue_types:
            if types['name'].lower() == issuetype:
                return types['id']


def get_issue_status(stat):
    if stat:
        stat = stat.lower()
    if os.path.isfile(os.path.expanduser('~/.jira-cli/statuses.pkl')):
        issue_statuses = pickle.load(open(os.path.expanduser('~/.jira-cli/statuses.pkl'), 'rb'))
    else:
        issue_statuses = JIRAOBJ.jira1.getStatuses(TOKEN)
        pickle.dump(issue_statuses, open(os.path.expanduser('~/.jira-cli/statuses.pkl'), 'wb'))

    if not stat:
        return issue_statuses
    else:
        for status in issue_statuses:
            if status['id'].lower() == stat:
                return status['name']


def get_issue_priority(priority):
    if priority:
        priority = priority.lower()
    if os.path.isfile(os.path.expanduser('~/.jira-cli/priorities.pkl')):
        issue_priorities = pickle.load(open(os.path.expanduser('~/.jira-cli/priorities.pkl'), 'rb'))
    else:
        issue_priorities = JIRAOBJ.jira1.getPriorities(TOKEN)
        pickle.dump(issue_priorities, open(os.path.expanduser('~/.jira-cli/priorities.pkl'), 'wb'))

    if not priority:
        return issue_priorities
    else:
        for prio in issue_priorities:
            if prio['name'].lower() == priority:
                return prio['id']


def search_issues(criteria):
    return JIRAOBJ.jira1.getIssuesFromTextSearch(TOKEN, criteria)


def check_auth(username, password):
    global JIRABASE, JIRAOBJ, TOKEN

    setup_home_dir()

    def _login(username, password):
        if not username:
            sys.stderr.write('enter username:')
            username = sys.stdin.readline().strip()
        if not password:
            password = getpass.getpass('enter password:')
        try:
            return JIRAOBJ.jira1.login(username, password)
        except:
            print >> sys.stderr, colorfunc('username or password incorrect, try again.', 'red')
            return _login(None, None)

    def _validate_jira_url(url=None):
        global JIRABASE, JIRAOBJ, TOKEN
        if not url:
            JIRABASE = raw_input('base url for your jira instance (e.g http://issues.apache.org/jira):')
        else:
            JIRABASE = url
        try:
            JIRAOBJ = xmlrpclib.ServerProxy('%s/rpc/xmlrpc' % JIRABASE)
            # lame ping method
            JIRAOBJ.getIssueTypes()
        except (xml.parsers.expat.ExpatError, xmlrpclib.ProtocolError, socket.gaierror, IOError):
            print >> colorfunc('invalid url %s. Please provide the correct url for your jira installation' % JIRABASE,
                               'red')
            return _validate_jira_url()
        except Exception:
            open(os.path.expanduser('~/.jira-cli/config'), 'w').write(JIRABASE)
        return None

    if os.path.isfile(os.path.expanduser('~/.jira-cli/config')):
        JIRABASE = open(os.path.expanduser('~/.jira-cli/config')).read().strip()
    _validate_jira_url(JIRABASE)
    if os.path.isfile(os.path.expanduser('~/.jira-cli/auth')):
        TOKEN = open(os.path.expanduser('~/.jira-cli/auth')).read()
    try:
        JIRAOBJ = xmlrpclib.ServerProxy('%s/rpc/xmlrpc' % JIRABASE)
        JIRAOBJ.jira1.getIssueTypes(TOKEN)
    except Exception:
        TOKEN = _login(username, password)
        open(os.path.expanduser('~/.jira-cli/auth'), 'w').write(TOKEN)


def format_issue(issue, mode=0, formatter=None, comments_only=False):
    fields = {}
    global colorfunc
    status_color = 'blue'
    status_string = get_issue_status(issue.setdefault('status', '1')).lower()
    if status_string in ['resolved', 'closed']:
        status_color = 'green'
    elif status_string in ['open', 'unassigned', 'reopened']:
        status_color = 'red'

    special_fields = {'status': get_issue_status, 'priority': get_issue_priority, 'type': get_issue_type}

    if formatter:
        groups = re.compile("(%([\w]+))").findall(formatter)
        ret_str = formatter
        for key, value in groups:
            if value.lower() in special_fields.keys():
                meth = special_fields[value.lower()]
                key = issue[value.lower()]
                mappings = meth(None)
                data = ''
                for item in mappings:
                    if item['id'] == key:
                        data = item['name']
                ret_str = ret_str.replace(key, data)
            else:
                ret_str = ret_str.replace(key, issue.setdefault(value.lower(), ''))
        return ret_str

    if mode >= 0:
        # minimal
        fields['issue'] = issue['key']
        fields['status'] = colorfunc(get_issue_status(issue['status']), status_color)
        fields['reporter'] = issue.setdefault('reporter', '')
        fields['assignee'] = issue.setdefault('assignee', '')
        fields['summary'] = issue.setdefault('summary', '')
        fields['link'] = colorfunc('%s/browse/%s' % (JIRABASE, issue['key']), 'white', attrs=['underline'])
    if mode >= 1 or comments_only:
        fields['description'] = issue.setdefault('description', '')
        fields['priority'] = get_issue_priority(issue.setdefault('priority', ''))
        fields['type'] = get_issue_type(issue.setdefault('type', ''))
        comments = get_comments(issue['key'])
        fields['comments'] = '\n'
        for comment in comments:
            comment_str = comment['body'].strip()
            fields['comments'] += '%s %s : %s\n' % (colorfunc(comment['created'], 'blue'), colorfunc(comment['author'],
                                                    'green'), comment_str)
    if comments_only:
        return fields['comments'].strip()
    elif mode < 0:
        url_str = colorfunc('%s/browse/%s' % (JIRABASE, issue['key']), 'white', attrs=['underline'])
        if COLOR:
            ret_str = colorfunc(issue['key'], status_color)
        else:
            ret_str = issue['key'] + ' [%s] ' % get_issue_status(issue['status'])
        ret_str += ' ' + issue.setdefault('summary', '') + ' ' + url_str
        return ret_str
    for key, value in fields.items():
        if not value:
            fields[key] = ''
    return '\n'.join(': '.join((k.ljust(20), v)) for (k, v) in fields.items()) + '\n'


def get_jira(jira_id):
    try:
        return JIRAOBJ.jira1.getIssue(TOKEN, jira_id)
    except:
        return {'key': jira_id}


def get_filters(favorites=False):
    filters = None
    if favorites:
        favorites = JIRAOBJ.jira1.getFavouriteFilters(TOKEN)
        filters = dict((k['name'], k) for k in favorites)
    else:
        saved = JIRAOBJ.jira1.getSavedFilters(TOKEN)
        filters = dict((k['name'], k) for k in saved)

    return filters.values()


def get_filter_id_from_name(name):
    filters = [k for k in get_filters() if k['name'].lower() == name.lower()]
    if filters:
        return filters[0]['id']
    else:
        raise RuntimeError('invalid filter name %s' % name)


def get_issues_from_filter(filter_name):
    fid = get_filter_id_from_name(filter_name)
    if fid:
        return JIRAOBJ.jira1.getIssuesFromFilter(TOKEN, fid)
    return []


def get_comments(jira_id):
    return JIRAOBJ.jira1.getComments(TOKEN, jira_id)


def add_comment(jira_id, comment):
    if comment == DEFAULT_EDITOR_TEXT:
        comment = get_text_from_editor(DEFAULT_EDITOR_TEXT % 'comment')
    res = JIRAOBJ.jira1.addComment(TOKEN, jira_id, comment)
    if res:
        return '%s added to %s' % (comment, jira_id)
    else:
        return 'failed to add comment to %s' % jira_id


def create_issue(project, issue_type=0, summary='', description='', priority='Major'):
    if description == DEFAULT_EDITOR_TEXT:
        description = get_text_from_editor(DEFAULT_EDITOR_TEXT % 'new issue')

    issue = {
        'project': project.upper(),
        'type': get_issue_type(issue_type),
        'summary': summary,
        'description': description,
        'priority': get_issue_priority(priority),
    }
    return JIRAOBJ.jira1.createIssue(TOKEN, issue)


def main():
    example_usage = \
        '''
------------------------------------------------------------------------------------------
view jira: jira-cli BE-193
view multiple jiras: jira-cli XYZ-123 ZZZ-123 ABC-123
add a comment: jira-cli BE-193 -c "i am sam"
create a new issue: jira-cli -n bug -p BE -t "i am sam" "and this is my long description
ending
here"
------------------------------------------------------------------------------------------
'''
    parser = optparse.OptionParser()
    parser.usage = example_usage
    parser.add_option('', '--list-types', dest='listtypes', help="print out the different jira 'types'",
                      action='store_true')
    parser.add_option('', '--list-prios', dest='listprios', help="print out the different jira 'priorities'",
                      action='store_true')
    parser.add_option('', '--list-filters', dest='listfilters', help='print out the different jira filters available',
                      action='store_true')
    parser.add_option('-s', '--search', dest='search', help='search criteria')
    parser.add_option('', '--filter', dest='filter',
                      help='filter(s) to use for listing jiras. use a comma to separate multiple filters')
    # options which require jira-id to act on:
    parser.add_option('-c', '--comment', dest='comment', help='comment on jira(s)')
    parser.add_option('-n', '--new', dest='issue_type', help='create a new issue with given title')
    parser.add_option('-p', '--priority', dest='issue_priority', help='priority of new issue', default='minor')
    parser.add_option('-t', '--title', dest='issue_title', help='new issue title')
    parser.add_option('-P', '--project', dest='jira_project', help='the jira project to act on')
    # options wich formatting output:
    parser.add_option('', '--oneline', dest='oneline', help='print only one line of info', action='store_true')
    parser.add_option('', '--comments-only', dest='commentsonly', help='show only the comments for a jira',
                      action='store_true')
    parser.add_option('-v', dest='verbose', action='store_true', help='print extra information')
    parser.add_option('-f', '--format', dest='format', default=None,
                      help="""format for outputting information. allowed tokens:
%status,
%priority,
%updated,
%votes,
%components,
%project,
%reporter,
%created,
%fixVersions,
%summary,
%environment,
%assignee,
%key,
%affectsVersions,
%type.
examples: "%priority,%reporter","(%key) %priority, reported by %reporter" """)
    parser.add_option('', '--user', dest='username', help='username to login as', default=None)
    parser.add_option('', '--password', dest='password', help='passowrd', default=None)

    opts, args = parser.parse_args()
    check_auth(opts.username, opts.password)
    try:
        if opts.listfilters:
            for idx, filt in enumerate(get_filters(), start=1):
                print '%d. %s (Owner: %s)' % (idx, colorfunc(filt['name'], 'green'), filt['author'])
        elif opts.listprios:
            for idx, prio in enumerate(get_issue_priority(None), start=1):
                print '%d. %s: %s' % (idx, colorfunc(prio['name'], 'green'), prio['description'])
        elif opts.listtypes:
            for idx, typ in enumerate(get_issue_type(None)):
                print '%d. %s: %s' % (idx, colorfunc(typ['name'], 'green'), typ['description'])
        else:
            if opts.issue_type:
                if not opts.jira_project:
                    parser.error('specify a project to create a jira in')
                if args:
                    description = ' '.join(args)
                else:
                    description = DEFAULT_EDITOR_TEXT
                print format_issue(create_issue(opts.jira_project, opts.issue_type, opts.issue_title, description,
                                   opts.issue_priority), 0, opts.format)
            elif opts.comment:
                if not args:
                    parser.error('specify the jira(s) to comment on')
                for arg in args:
                    print add_comment(arg, opts.comment)
            elif opts.search:
                issues = search_issues(opts.search)
                for issue in issues:
                    mode = (0 if not opts.verbose else 1)
                    mode = (-1 if opts.oneline else mode)
                    print format_issue(issue, mode, opts.format)
            else:
                # otherwise we're just showing the jira.
                # maybe by filter
                if opts.filter:
                    for f in opts.filter.split(','):
                        issues = get_issues_from_filter(f)
                        for issue in issues:
                            mode = (0 if not opts.verbose else 1)
                            mode = (-1 if opts.oneline else mode)
                            print format_issue(issue, mode, opts.format, opts.commentsonly)
                else:
                    if not args:
                        parser.error('jira(s) id must be provided')
                    if args:
                        for arg in args:
                            issue = get_jira(arg)
                            mode = (0 if not opts.verbose else 1)
                            mode = (-1 if opts.oneline else mode)
                            print format_issue(issue, mode, opts.format, opts.commentsonly)
    except Exception, e:
        parser.error(colorfunc(str(e), 'red'))


if __name__ == '__main__':
    main()
