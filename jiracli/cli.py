#!/usr/bin/env python
# -*- coding: utf-8 -*-

import getpass
import re
import os
import argparse
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
        groups = re.compile('(\$([\w]+))').findall(formatter)
        ret_str = formatter
        for key, value in groups:

            if value.lower() in special_fields.keys():
                id = issue[value.lower()]
                meth = special_fields[value.lower()]
                mappings = meth(None)
                data = ''
                for item in mappings:
                    if item['id'] == id:
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
        raise RuntimeError('invalid filter name "%s"' % name)


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
        return 'comment "%s" added to %s' % (comment, jira_id)
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


def list(args):

    if not any([args.filters, args.prios, args.types, args.search, args.filter]):
        if not args.issue:
            raise Exception('issue id must be provided')
        for issue in args.issue:
            issue_id = get_jira(issue)
            mode = (0 if not args.verbose else 1)
            mode = (-1 if args.oneline else mode)
            print format_issue(issue_id, mode, args.format, args.commentsonly)

    if args.filters:
        for idx, filt in enumerate(get_filters(), start=1):
            print '%d. %s (Owner: %s)' % (idx, colorfunc(filt['name'], 'green'), filt['author'])

    if args.prios:
        for idx, prio in enumerate(get_issue_priority(None), start=1):
            print '%d. %s: %s' % (idx, colorfunc(prio['name'], 'green'), prio['description'])

    if args.types:
        for idx, typ in enumerate(get_issue_type(None)):
            print '%d. %s: %s' % (idx, colorfunc(typ['name'], 'green'), typ['description'])

    if args.search:
        issues = search_issues(args.search)
        for issue in issues:
            mode = (0 if not args.verbose else 1)
            mode = (-1 if args.oneline else mode)
            print format_issue(issue, mode, args.format)

    if args.filter:
        for filt in args.filter:
            issues = get_issues_from_filter(filt)
            for issue in issues:
                mode = (0 if not args.verbose else 1)
                mode = (-1 if args.oneline else mode)
                print format_issue(issue, mode, args.format, args.commentsonly)


def create(args):

    if not args.project:
        raise Exception('specify a project to create a issue in')

    if not args.title:
        raise Exception('specify a issue title')
    else:
        title = ' '.join(args.title)

    if args.description:
        description = ' '.join(args.description)
    else:
        description = DEFAULT_EDITOR_TEXT

    print format_issue(create_issue(args.project, args.type, title, description,
                                    args.priority), 0, args.format)


def comment(args):

    if args.comment:
        comment = ' '.join(args.comment)
    else:
        comment = DEFAULT_EDITOR_TEXT

    print add_comment(args.issue, comment)


def main():
    parser = argparse.ArgumentParser(prog='jira-cli', description='command line utility for interacting with jira')
    parser.add_argument('--user', dest='username', help='username to login as', default=None)
    parser.add_argument('--password', dest='password', help='password', default=None)

    # options for output formatting:
    group = parser.add_mutually_exclusive_group()

    group.add_argument('-o', '--oneline', help='print only one line of info', action='store_true')
    group.add_argument('-c', '--comments-only', dest='commentsonly', help='show only the comments for a issue',
                       action='store_true')
    group.add_argument('-v', '--verbose', help='print extra information', action='store_true')
    group.add_argument('-f', '--format', default=None,
                       help='''custom format for output. allowed tokens:
$status,
$priority,
$updated,
$votes,
$components,
$project,
$reporter,
$created,
$fixVersions,
$summary,
$environment,
$assignee,
$key,
$affectsVersions,
$type.

examples:
'$priority,$reporter'
'$key $priority, reported by $reporter' ''')

    # sub-commands:
    subparsers = parser.add_subparsers(title='subcommands')

    parser_list = subparsers.add_parser('list')
    parser_list.set_defaults(func=list)

    parser_list.add_argument('issue', help='issue id to list', nargs='*')
    parser_list.add_argument('--types', help="print all issue 'types'", action='store_true')
    parser_list.add_argument('--prios', help="print all issue 'priorities'", action='store_true')
    parser_list.add_argument('--filters', help='print available filters', action='store_true')
    parser_list.add_argument('-f', '--filter', help='filter(s) to use for listing issues', nargs='+')
    parser_list.add_argument('-s', '--search', help='search criteria')

    parser_create = subparsers.add_parser('create')
    parser_create.set_defaults(func=create)
    parser_create.add_argument('project', help='project to create the issue in')
    parser_create.add_argument('-T', '--title', help='create a new issue with given title', nargs='+')
    parser_create.add_argument('-d', '--description', help='type of new issue', nargs='*')
    parser_create.add_argument('-p', '--priority', help='priority of new issue', default='minor')
    parser_create.add_argument('-t', '--type', help='type of new issue', default='task')

    parser_comment = subparsers.add_parser('comment')
    parser_comment.set_defaults(func=comment)
    parser_comment.add_argument('issue', help='issue to comment')
    parser_comment.add_argument('-c', '--comment', help='comment on issue', nargs='*')

    try:
        args = parser.parse_args()
        check_auth(args.username, args.password)
        args.func(args)
    except Exception, e:
        parser.error(colorfunc(str(e), 'red'))


if __name__ == '__main__':
    main()
