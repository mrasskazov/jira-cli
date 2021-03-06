#!/usr/bin/env python
# -*- coding: utf-8 -*-

import getpass
import re
import os
import argparse
import tempfile
import socket
import json
import sys
import urllib2
import logging
import ConfigParser
from suds.client import Client
from suds import WebFault
from termcolor import colored as colorfunc

CONFIG = {'color': True}
JIRAOBJ = None
TOKEN = None

if not sys.stdout.isatty():
    colorfunc = lambda *a, **k: str(a[0])  # NOQA  # silence pyflakes
    CONFIG['color'] = False
DEFAULT_EDITOR_TEXT = '''-- enter the text for the %s
-- all lines starting with '--' will be removed'''

logging.basicConfig(level=logging.INFO)
logging.getLogger('suds.client').setLevel(logging.CRITICAL)


# @TODO more test coverage

def get_text_from_editor(def_text):
    tmp = tempfile.mktemp()
    open(tmp, 'w').write(def_text)
    editor = os.environ.setdefault('EDITOR', 'vim')
    os.system('%s %s' % (editor, tmp))
    return '\n'.join([k for k in open(tmp).read().split('\n') if not k.startswith('--')])


def get_issue_type(issuetype):
    ''' get either all available issue types if no `issuetype` given, or issue type id found by name'''

    issue_types_file = os.path.expanduser('~/.jira-cli/types.json')

    if os.path.isfile(issue_types_file):
        with open(issue_types_file, 'rb') as fh:
            issue_types = json.load(fh)
    else:
        issue_types = JIRAOBJ.service.getIssueTypes(TOKEN)
        issue_types = map(lambda x: dict(x), issue_types)
        with open(issue_types_file, 'wb') as fh:
            json.dump(issue_types, fh)

    if not issuetype:
        return issue_types
    else:
        issuetype = issuetype.lower()
        for it in issue_types:
            if it['name'].lower() == issuetype:
                return it['id']


def get_issue_status(status):
    ''' get either all available statuses if no `stat` given, or status name found by id'''

    issue_statuses_file = os.path.expanduser('~/.jira-cli/statuses.json')

    if os.path.isfile(issue_statuses_file):
        with open(issue_statuses_file, 'rb') as fh:
            issue_statuses = json.load(fh)
    else:
        issue_statuses = JIRAOBJ.service.getStatuses(TOKEN)
        issue_statuses = map(lambda x: dict(x), issue_statuses)
        with open(issue_statuses_file, 'wb') as fh:
            json.dump(issue_statuses, fh)

    if not status:
        return issue_statuses
    else:
        status = status.lower()
        for st in issue_statuses:
            if st['id'].lower() == status:
                return st['name']


def get_issue_priority(priority):
    ''' get either all available priorities if no `priority` given, or priority id found by name'''

    issue_priorities_file = os.path.expanduser('~/.jira-cli/priorities.json')

    if os.path.isfile(issue_priorities_file) and os.stat(issue_priorities_file)[6] < 0:
        with open(issue_priorities_file, 'rb') as fh:
            issue_priorities = json.load(fh)
    else:
        issue_priorities = JIRAOBJ.service.getPriorities(TOKEN)
        issue_priorities = map(lambda x: dict(x), issue_priorities)
        with open(issue_priorities_file, 'wb') as fh:
            json.dump(issue_priorities, fh)

    if not priority:
        return issue_priorities
    else:
        priority = priority.lower()
        for ip in issue_priorities:
            if ip['name'].lower() == priority:
                return ip['id']


def check_auth():
    ''' check credentials against jira instance and authenticate '''

    global JIRAOBJ, TOKEN

    def _validate_login(token=None):
        if token:
            try:
                JIRAOBJ.service.getPriorities(token)
                return token
            except WebFault:
                return _validate_login()

        try:
            token = JIRAOBJ.service.login(config('user'), config('password'))
            open(os.path.expanduser('~/.jira-cli/token'), 'w').write(token)
            return token
        except WebFault:
            print colorfunc('username or password incorrect, try again.', 'red')
            config('user', unset=True)
            config('password', unset=True)
            return _validate_login()

    def _validate_jira_url():
        jirabase = config('jirabase')

        try:
            urllib2.urlopen('%s/rpc/soap/jirasoapservice-v2?wsdl' % jirabase)
            return Client('%s/rpc/soap/jirasoapservice-v2?wsdl' % jirabase)
        except (socket.gaierror, IOError):
            print colorfunc('invalid url %s. Please provide the correct url for your jira instance' % jirabase, 'red')
            config('jirabase', unset=True)
            return _validate_jira_url()
        except Exception, ex:
            raise ex

    JIRAOBJ = _validate_jira_url()
    logging.debug(JIRAOBJ)

    if os.path.isfile(os.path.expanduser('~/.jira-cli/token')):
        TOKEN = open(os.path.expanduser('~/.jira-cli/token')).read().strip()
    TOKEN = _validate_login(TOKEN)
    logging.debug(TOKEN)


def config(key, unset=False):
    '''reading / generating config file or updating it, and returning val if key is given'''

    config_file = os.path.expanduser('~/.jira-cli/config')
    parser = ConfigParser.ConfigParser()

    if os.path.isfile(config_file):
        parser.read(config_file)
    else:
        print 'no config file found, generating it'
        if not os.path.isdir(os.path.expanduser('~/.jira-cli')):
            os.makedirs(os.path.expanduser('~/.jira-cli'))

    parser.has_section('general') or parser.add_section('general')

    if unset:
        del CONFIG[key]
        parser.remove_option('general', key)

    if CONFIG.has_key(key):
        logging.debug('retrieving key "%s" from config' % key)
        return CONFIG.get(key)
    elif parser.has_option('general', key):
        logging.debug('retrieving key "%s" from file' % key)
        CONFIG[key] = parser.get('general', key)
        return parser.get('general', key)
    elif key == 'jirabase':
        jirabase = raw_input('base url for your jira instance (e.g http://issues.apache.org/jira):')
        CONFIG['jirabase'] = jirabase
        parser.set('general', 'jirabase', jirabase)
    elif key == 'user':
        user = raw_input('enter username:')
        CONFIG['user'] = user
        parser.set('general', 'user', user)
    elif key == 'password':
        password = getpass.getpass('enter password:')
        CONFIG['password'] = password
        parser.set('general', 'password', password)

    with open(config_file, 'wb') as fh:
        parser.write(fh)
    return CONFIG[key]


def format_issue(issue, mode=0, formatter=None, comments_only=False):
    ''' formatting output for a issue according the different modes '''

    # @TODO rework 'mode' to use args too
    # @TODO better formatting for "multiline" fields

    fields = {}
    status_string = get_issue_status(issue.status).lower()
    status_color = 'blue'
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
        fields['link'] = colorfunc('%s/browse/%s' % (config('jirabase'), issue['key']), 'white', attrs=['underline'])
    if mode >= 1 or comments_only:
        fields['description'] = issue.description.strip()
        fields['priority'] = get_issue_priority(issue.priority)
        fields['type'] = get_issue_type(issue.type)
        fields['components'] = ', '.join([component.name for component in issue.components])
        comments = get_comments(issue['key'])
        fields['comments'] = ''
        for comment in comments:
            comment_body = comment['body'].strip()
            fields['comments'] += '\n' + 20 * ' ' + ': %s %s - "%s"' % (colorfunc(comment['created'], 'blue'),
                    colorfunc(comment['author'], 'green'), comment_body)
    if comments_only:
        return fields['comments'].strip()
    elif mode < 0:
        url_str = colorfunc('%s/browse/%s' % (config('jirabase'), issue['key']), 'white', attrs=['underline'])
        if CONFIG['color']:
            ret_str = colorfunc(issue['key'], status_color)
        else:
            ret_str = issue['key'] + ' [%s] ' % get_issue_status(issue['status'])
        ret_str += ' ' + issue.summary + ' ' + url_str
        return ret_str.encode('utf-8')
    for key, value in fields.items():
        if not value:
            fields[key] = ''
    return '\n'.join(': '.join((k.ljust(20), v.encode('utf-8'))) for (k, v) in fields.items()) + '\n'


def add_comment(jira_id, comment):
    try:
        JIRAOBJ.service.addComment(TOKEN, jira_id, {'body': comment})
        return 'comment "%s" added to %s' % (comment, jira_id)
    except WebFault, ex:
        error_msg = str(ex).replace('\n', ' ')
        return 'failed to add comment to %s: %s' % (jira_id, error_msg)


def create_issue(project, issue_type=0, summary='', description='', priority='Major', components=None):
    summary = summary.strip()

    remote_components = []
    if components and isinstance(components, list):
        for remote_component in get_components(project):
            for component in components:
                if component in [remote_component.id, remote_component.name]:
                    remote_components.append(remote_component)
    issue = {
        'project': project.upper(),
        'type': get_issue_type(issue_type),
        'summary': summary,
        'description': description,
        'priority': get_issue_priority(priority),
        'components': remote_components,
    }
    return JIRAOBJ.service.createIssue(TOKEN, issue)


def progress(issue_id, action):
    '''perform transition action on issue '''

    return JIRAOBJ.service.progressWorkflowAction(TOKEN, issue_id, action.id)


# --- simple "getter" functions ---

def search_issues(criteria, limit=100):
    return JIRAOBJ.service.getIssuesFromTextSearchWithLimit(TOKEN, criteria, 0, limit)


def search_issues_jql(query, limit=100):
    try:
        return JIRAOBJ.service.getIssuesFromJqlSearch(TOKEN, query, limit)
    except WebFault, ex:
        error_msg = str(ex).replace('\n', ' ')
        sys.exit('failed to get issues by %s: %s' % (query, error_msg))


def get_issue(jira_id):
    try:
        return JIRAOBJ.service.getIssue(TOKEN, jira_id)
    except WebFault, ex:
        error_msg = str(ex).replace('\n', ' ')
        sys.exit('failed to get issue %s: %s' % (jira_id, error_msg))


def get_filter_by_name(name):
    return next((x for x in get_filters() if x.name.lower() == name.lower()), None)


def get_issues_by_filter(filter):
    return JIRAOBJ.service.getIssuesFromFilter(TOKEN, filter.id)


def get_filters():
    return JIRAOBJ.service.getFavouriteFilters(TOKEN)


def get_components(project):
    return JIRAOBJ.service.getComponents(TOKEN, project.upper())


def get_comments(jira_id):
    return JIRAOBJ.service.getComments(TOKEN, jira_id)


def get_actions(jira_id):
    return JIRAOBJ.service.getAvailableActions(TOKEN, jira_id)


# --- command functions ---

def command_list(args):
    ''' entry point for 'list' subcommand '''

    if not any([
        args.filters,
        args.prios,
        args.statuses,
        args.types,
        args.search,
        args.jqlsearch,
        args.filter,
        args.project,
    ]):
        if not args.issue:
            raise Exception('issue id must be provided')
        for issue in args.issue:
            issue_id = get_issue(issue)
            mode = (0 if not args.verbose else 1)
            mode = (-1 if args.oneline else mode)
            print format_issue(issue_id, mode, args.format, args.commentsonly)

    if args.filters:
        for idx, filt in enumerate(get_filters(), start=1):
            print '%d. %s: %s (Owner: %s)' % (idx, colorfunc(filt.id, 'green'), filt.name, colorfunc(filt.author, 'blue'
                                              ))

    if args.types:
        for idx, typ in enumerate(get_issue_type(None), start=1):
            print '%d. %s: %s' % (idx, colorfunc(typ['name'], 'green'), typ['description'])

    if args.statuses:
        for idx, status in enumerate(get_issue_status(None), start=1):
            print '%d. %s: %s' % (idx, colorfunc(status['name'], 'green'), status['description'])

    if args.prios:
        for idx, prio in enumerate(get_issue_priority(None), start=1):
            print '%d. %s: %s' % (idx, colorfunc(prio['name'], 'green'), prio['description'])

    if args.project:
        for idx, comp in enumerate(get_components(args.project), start=1):
            print '%d. %s: %s' % (idx, colorfunc(comp['id'], 'green'), comp['name'])

    if args.search:
        issues = search_issues(args.search)
        for issue in issues:
            mode = (0 if not args.verbose else 1)
            mode = (-1 if args.oneline else mode)
            print format_issue(issue, mode, args.format)

    if args.jqlsearch:
        issues = search_issues_jql(args.jqlsearch)
        mode = (0 if not args.verbose else 1)
        mode = (-1 if args.oneline else mode)
        for issue in issues:
            print format_issue(issue, mode, args.format)

    if args.filter:
        for filt in args.filter:
            issues = get_issues_by_filter(get_filter_by_name(filt))
            for issue in issues:
                mode = (0 if not args.verbose else 1)
                mode = (-1 if args.oneline else mode)
                print format_issue(issue, mode, args.format, args.commentsonly)


def command_create(args):
    '''entry point for 'create' subcommand '''

    if args.summary:
        summary = ' '.join(args.summary)
    else:
        summary = get_text_from_editor(DEFAULT_EDITOR_TEXT % 'issue summary')
    summary = summary.strip()
    if not summary:
        sys.exit('Issue summary can not be empty')

    if args.description:
        description = ' '.join(args.description)
    else:
        description = get_text_from_editor(DEFAULT_EDITOR_TEXT % 'issue description')
    description = description.strip()

    print format_issue(create_issue(args.project, args.type, summary, description, args.priority,
                       components=args.components), 0, args.format)


def command_comment(args):
    '''entry point for 'comment' subcommand '''

    if args.comment:
        comment = ' '.join(args.comment)
    else:
        comment = get_text_from_editor(DEFAULT_EDITOR_TEXT % 'comment')
    comment = comment.strip()
    if not comment:
        sys.exit('Comment body can not be empty')

    print add_comment(args.issue, comment)


def command_progress(args):
    '''entry point for 'progress' subcommand '''

    def find_by_attr(list, attr, value):
        return next((x for x in list if x[attr].lower() == value), None)

    if not args.issue:
        raise Exception('issue id must be provided')

    available_actions = get_actions(args.issue)
    available_actions_names = [action.name.lower() for action in available_actions]

    if args.actions:
        for idx, action in enumerate(available_actions, start=1):
            print '%d. %s: "%s"' % (idx, colorfunc(action.id, 'green'), action.name)

    if args.start:
        if any(map(lambda a: a in available_actions_names, ['start progress', 'in progress >>'])):
            action = None
            for a in ['start progress', 'in progress >>']:
                action = find_by_attr(available_actions, 'name', a)
                if action:
                    break
            print format_issue(progress(args.issue, action), 0, args.format)
        else:
            sys.exit('unable to start progress on "%s", available actions are: "%s"' % (args.issue,
                     available_actions_names))

    if args.stop:
        if 'stop progress' in available_actions_names:
            print format_issue(progress(args.issue, find_by_attr(available_actions, 'name', 'stop progress')), 0,
                               args.format)
        else:
            sys.exit('unable to stop progress on "%s", available actions are: "%s"' % (args.issue,
                     available_actions_names))

    if args.toggle:
        if 'start progress' in available_actions_names:
            print format_issue(progress(args.issue, find_by_attr(available_actions, 'name', 'start progress')), 0,
                               args.format)
        elif 'stop progress' in available_actions_names:
            print format_issue(progress(args.issue, find_by_attr(available_actions, 'name', 'stop progress')), 0,
                               args.format)
        else:
            sys.exit('unable to toggle progress on "%s", available actions are: "%s"' % (args.issue,
                     available_actions_names))

    if args.transist:
        if args.transist.lower() in available_actions_names:
            print format_issue(progress(args.issue, find_by_attr(available_actions, 'name', args.transist.lower())), 0,
                               args.format)
            available_actions = get_actions(args.issue)
            available_actions_names = [action.name.lower() for action in available_actions]
            print 'available actions from this state are:'
            for idx, action in enumerate(available_actions, start=1):
                print '%d. %s: "%s"' % (idx, colorfunc(action.id, 'green'), action.name)
        else:
            sys.exit('unable to perform transition "%s" on "%s", available actions are: "%s"' % (args.transist,
                     args.issue, available_actions_names))

    if args.close:
        if 'close issue' in available_actions_names:
            print format_issue(progress(args.issue, find_by_attr(available_actions, 'name', 'close issue')), 0,
                               args.format)
        else:
            sys.exit('unable to close "%s", available actions are: "%s"' % (args.issue, available_actions_names))


# --- boiler plate and main entry point ---

def setup_argparser():
    '''setting up and returning command line arguments parser'''

    parser = argparse.ArgumentParser(prog='jira-cli', description='command line utility for interacting with jira')

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
    parser_list.set_defaults(func=command_list)
    parser_list.add_argument('issue', help='issue id to list', nargs='*')
    parser_list.add_argument('--types', help="print all issue 'types'", action='store_true')
    parser_list.add_argument('--statuses', help="print all issue 'statuses'", action='store_true')
    parser_list.add_argument('--prios', help="print all issue 'priorities'", action='store_true')
    parser_list.add_argument('--filters', help='print available filters', action='store_true')
    parser_list.add_argument('--components', help='print components by project', dest='project')
    parser_list.add_argument('-f', '--filter', help='filter(s) to use for listing issues', nargs='+')
    parser_list.add_argument('-s', '--search', help='fuzzy text search')
    parser_list.add_argument('-j', '--jqlsearch',
                             help='search by JQL query, example: "assignee = currentUser() AND resolution = unresolved AND status != "Waiting for Feedback" ORDER BY priority DESC, updated DESC" '
                             )

    parser_create = subparsers.add_parser('create')
    parser_create.set_defaults(func=command_create)
    parser_create.add_argument('project', help='project to create the issue in')
    parser_create.add_argument('-s', '--summary', help='create a new issue with given summary', nargs='*')
    parser_create.add_argument('-d', '--description', help='type of new issue', nargs='*')
    parser_create.add_argument('-p', '--priority', help='priority of new issue', default='major')
    parser_create.add_argument('-t', '--type', help='type of new issue', default='task')
    parser_create.add_argument('-c', '--components', help='components of new issue', nargs='*')

    parser_comment = subparsers.add_parser('comment')
    parser_comment.set_defaults(func=command_comment)
    parser_comment.add_argument('issue', help='issue to comment')
    parser_comment.add_argument('-c', '--comment', help='comment on issue', nargs='*')

    parser_progress = subparsers.add_parser('progress')
    parser_progress.set_defaults(func=command_progress)
    parser_progress.add_argument('issue', help='issue to progress')
    parser_progress.add_argument('-a', '--actions', help='list available actions', action='store_true')
    group = parser_progress.add_mutually_exclusive_group()
    group.add_argument('--start', help='start progress', action='store_true')
    group.add_argument('--stop', help='stop progress', action='store_true')
    group.add_argument('-t', '--toggle', help='toggle start / stop', action='store_true')
    group.add_argument('-c', '--close', help='close issue', action='store_true')
    group.add_argument('--transist', help='perform transition')

    return parser


def main():
    try:
        parser = setup_argparser()
        args = parser.parse_args()
        logging.debug(args)
    except Exception, ex:
        sys.exit(colorfunc(str(ex), 'red'))
    check_auth()
    args.func(args)


if __name__ == '__main__':
    main()

