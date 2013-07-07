#!/usr/bin/env python
# -*- coding: utf-8 -*-

import getpass
import re
import os
import argparse
import tempfile
import socket
import pickle
import sys
import urllib2
import logging
from suds.client import Client
from suds import WebFault
from termcolor import colored as colorfunc

JIRABASE = None
JIRAOBJ = None
TOKEN = None
COLOR = True
if not sys.stdout.isatty():
    colorfunc = lambda *a, **k: str(a[0])  # NOQA
    COLOR = False
DEFAULT_EDITOR_TEXT = '''-- enter the text for the %s
-- all lines starting with '--' will be removed'''

logging.basicConfig(level=logging.INFO)
logging.getLogger('suds.client').setLevel(logging.INFO)


def get_text_from_editor(def_text):
    tmp = tempfile.mktemp()
    open(tmp, 'w').write(def_text)
    editor = os.environ.setdefault('EDITOR', 'vim')
    os.system('%s %s' % (editor, tmp))
    return '\n'.join([k for k in open(tmp).read().split('\n') if not k.startswith('--')])


def get_issue_type(issuetype):
    if os.path.isfile(os.path.expanduser('~/.jira-cli/types.pkl')):
        issue_types = pickle.load(open(os.path.expanduser('~/.jira-cli/types.pkl'), 'rb'))
    else:
        issue_types = JIRAOBJ.service.getIssueTypes(TOKEN)
        pickle.dump(issue_types, open(os.path.expanduser('~/.jira-cli/types.pkl'), 'wb'))

    if not issuetype:
        return issue_types
    else:
        issuetype = issuetype.lower()
        for types in issue_types:
            if types['name'].lower() == issuetype:
                return types['id']


def get_issue_status(stat):
    if os.path.isfile(os.path.expanduser('~/.jira-cli/statuses.pkl')):
        issue_statuses = pickle.load(open(os.path.expanduser('~/.jira-cli/statuses.pkl'), 'rb'))
    else:
        issue_statuses = JIRAOBJ.service.getStatuses(TOKEN)
        pickle.dump(issue_statuses, open(os.path.expanduser('~/.jira-cli/statuses.pkl'), 'wb'))

    if not stat:
        return issue_statuses
    else:
        stat = stat.lower()
        for status in issue_statuses:
            if status['id'].lower() == stat:
                return status['name']


def get_issue_priority(priority):
    if os.path.isfile(os.path.expanduser('~/.jira-cli/priorities.pkl')):
        issue_priorities = pickle.load(open(os.path.expanduser('~/.jira-cli/priorities.pkl'), 'rb'))
    else:
        issue_priorities = JIRAOBJ.service.getPriorities(TOKEN)
        pickle.dump(issue_priorities, open(os.path.expanduser('~/.jira-cli/priorities.pkl'), 'wb'))

    if not priority:
        return issue_priorities
    else:
        priority = priority.lower()
        for prio in issue_priorities:
            if prio['name'].lower() == priority:
                return prio['id']


def check_auth(username, password, jirabase):
    global JIRABASE, JIRAOBJ, TOKEN

    if not os.path.isdir(os.path.expanduser('~/.jira-cli')):
        os.makedirs(os.path.expanduser('~/.jira-cli'))

    def _validate_login(username, password, token=None):
        if token:
            try:
                JIRAOBJ.service.getIssueTypes(token)
                return token
            except Exception, ex:
                print vars(ex)
                return _validate_login(None, None)

        if not username:
            username = raw_input('enter username:')
        if not password:
            password = getpass.getpass('enter password:')
        try:
            token = JIRAOBJ.login(username, password)
        except Exception, ex:
            print vars(ex)
            print colorfunc('username or password incorrect, try again.', 'red')
            return _validate_login(None, None)
        open(os.path.expanduser('~/.jira-cli/auth'), 'w').write(token)
        return token

    def _validate_jira_url(url=None):
        if not url:
            JIRABASE = raw_input('base url for your jira instance (e.g http://issues.apache.org/jira):')
        else:
            JIRABASE = url
        try:
            urllib2.urlopen('%s/rpc/soap/jirasoapservice-v2?wsdl' % JIRABASE)
            Client('%s/rpc/soap/jirasoapservice-v2?wsdl' % JIRABASE)
        except (socket.gaierror, IOError):
            print colorfunc('invalid url %s. Please provide the correct url for your jira instance' % JIRABASE, 'red')
            return _validate_jira_url()
        except Exception, ex:
            raise ex
        open(os.path.expanduser('~/.jira-cli/config'), 'w').write(JIRABASE)
        return JIRABASE

    if os.path.isfile(os.path.expanduser('~/.jira-cli/config')):
        JIRABASE = open(os.path.expanduser('~/.jira-cli/config')).read().strip()
    if jirabase:
        JIRABASE = jirabase
    JIRABASE = _validate_jira_url(JIRABASE)
    JIRAOBJ = Client('%s/rpc/soap/jirasoapservice-v2?wsdl' % JIRABASE)
    logging.warn(JIRAOBJ)

    if os.path.isfile(os.path.expanduser('~/.jira-cli/auth')):
        TOKEN = open(os.path.expanduser('~/.jira-cli/auth')).read().strip()
    TOKEN = _validate_login(username, password, token=TOKEN)


def format_issue(issue, mode=0, formatter=None, comments_only=False):
    fields = {}
    status_color = 'blue'
    status_string = get_issue_status(issue.status).lower()
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
                issue_id = issue[value.lower()]
                meth = special_fields[value.lower()]
                mappings = meth(None)
                data = ''
                for item in mappings:
                    if item['id'] == issue_id:
                        data = item['name']
                ret_str = ret_str.replace(key, data)
            else:
                ret_str = ret_str.replace(key, str(getattr(issue, value)))
        return ret_str

    if mode >= 0:
        fields['issue'] = issue['key']
        fields['status'] = colorfunc(get_issue_status(issue['status']), status_color)
        fields['reporter'] = issue.reporter
        fields['assignee'] = issue.assignee
        fields['summary'] = issue.summary
        fields['link'] = colorfunc('%s/browse/%s' % (JIRABASE, issue['key']), 'white', attrs=['underline'])
    if mode >= 1 or comments_only:
        fields['description'] = issue.description
        fields['priority'] = get_issue_priority(issue.priority)
        fields['type'] = get_issue_type(issue.type)
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
        ret_str += ' ' + issue.summary + ' ' + url_str
        return ret_str
    for key, value in fields.items():
        if not value:
            fields[key] = ''
    return '\n'.join(': '.join((k.ljust(20), v)) for (k, v) in fields.items()) + '\n'


def search_issues(criteria):
    return JIRAOBJ.service.getIssuesFromTextSearch(TOKEN, criteria)


def get_issue(jira_id):
    try:
        return JIRAOBJ.service.getIssue(TOKEN, jira_id)
    except Exception, ex:
        print vars(ex)
        sys.exit(colorfunc('This issue does not exist', 'red'))


def get_filters(favorites=False):
    filters = None
    if favorites:
        favorites = JIRAOBJ.service.getFavouriteFilters(TOKEN)
        filters = dict((k['name'], k) for k in favorites)
    else:
        saved = JIRAOBJ.service.getSavedFilters(TOKEN)
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
        return JIRAOBJ.service.getIssuesFromFilter(TOKEN, fid)
    return []


def get_comments(jira_id):
    return JIRAOBJ.service.getComments(TOKEN, jira_id)


def add_comment(jira_id, comment):
    if not comment or comment == DEFAULT_EDITOR_TEXT:
        comment = get_text_from_editor(DEFAULT_EDITOR_TEXT % 'comment')
    try:
        JIRAOBJ.service.addComment(TOKEN, jira_id,  comment)
        return 'comment "%s" added to %s' % (comment, jira_id)
    except WebFault, ex:
        error_msg = str(ex).replace('\n', ' ')
        return 'failed to add comment to %s: %s' % (jira_id, error_msg)


def create_issue(project, issue_type=0, summary='', description='', priority='Major'):
    if not description or description == DEFAULT_EDITOR_TEXT:
        description = get_text_from_editor(DEFAULT_EDITOR_TEXT % 'new issue')

    issue = {
        'project': project.upper(),
        'type': get_issue_type(issue_type),
        'summary': summary,
        'description': description,
        'priority': get_issue_priority(priority),
    }
    return JIRAOBJ.service.createIssue(TOKEN, issue)


def list(args):

    if not any([args.filters, args.prios, args.types, args.search, args.filter]):
        if not args.issue:
            raise Exception('issue id must be provided')
        for issue in args.issue:
            issue_id = get_issue(issue)
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

    print format_issue(create_issue(args.project, args.type, title, description, args.priority), 0, args.format)


def comment(args):

    if args.comment:
        comment = ' '.join(args.comment)
    else:
        comment = DEFAULT_EDITOR_TEXT

    print add_comment(args.issue, comment)


def setup_argparser():
    """setting up and returning command line arguments parser"""

    parser = argparse.ArgumentParser(prog='jira-cli', description='command line utility for interacting with jira')
    parser.add_argument('--user', dest='username', help='username to login as', default=None)
    parser.add_argument('--password', dest='password', help='password', default=None)
    parser.add_argument('--jirabase', help='base url to jira instance', default=None)

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

    return parser


def main():
    try:
        parser = setup_argparser()
        args = parser.parse_args()
    except Exception, e:
        parser.error(colorfunc(str(e), 'red'))
    check_auth(args.username, args.password, args.jirabase)
    args.func(args)


if __name__ == '__main__':
    main()
