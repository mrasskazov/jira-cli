Introduction
============
Simple command line utility to interact with your jira instance.

.. image:: https://api.travis-ci.org/skoenig/jira-cli.png
   :alt: build status
   :target: https://travis-ci.org/#!/skoenig/jira-cli

Installation
============

* from source::

    git clone http://github.com/skoenig/jira-cli
    cd jira-cli
    python setup.py build
    sudo python setup.py install

* after installation, a few configuration steps will be prompted upon invoking jira-cli for the first time::

    skoenig@home ~ $ jira-cli list --types
    base url for your jira instance (e.g http://issues.apache.org/jira):http://jira.yourdomain.com
    enter username:skoenig
    enter password:*********

  The details of your jira instance will be kept in ~/.jira-cli/config and the authentication token will be stored in ~/.jira-cli/token.

Usage
=====

A few examples to get started.
------------------------------
create an issue with only a title in project TP with default priority and type Bug (description will be added interactively)::

    skoenig@home ~ $ jira-cli create TP -t Bug --summary "Test Bug" --priority Major
    link                 : http://jira.yourdomain.com/browse/TP-24
    assignee             :
    summary              : Test Bug
    issue                : TP-24
    reporter             : skoenig

create an issue with priority Major and a description::

    skoenig@home ~ $ jira-cli create TP -t Bug --summary "Test Bug" --priority Major -d the description
    link                 : http://jira.yourdomain.com/browse/TP-25
    assignee             :
    summary              : Test Bug
    issue                : TP-25
    reporter             : skoenig

list the issue TP-25::

    skoenig@home ~ $ jira-cli list TP-25
    link                 : http://jira.yourdomain.com/browse/TP-25
    assignee             :
    summary              : Test Bug
    issue                : TP-25
    reporter             : skoenig


list the issues TP-20 & TP-21::

    skoenig@home ~ $ jira-cli list TP-20 TP-21
    link                 : http://jira.yourdomain.com/browse/TP-20
    assignee             : skoenig
    summary              : test
    issue                : TP-20
    reporter             : skoenig

    link                 : http://jira.yourdomain.com/browse/TP-21
    assignee             :
    summary              : Test Bug
    issue                : TP-21
    reporter             : skoenig

list the issues in short form::

    skoenig@home ~ $ jira-cli --oneline list TP-20 TP-21 TP-22
    TP-20 test < http://jira.yourdomain.com/browse/TP-20 >
    TP-21 Test Bug < http://jira.yourdomain.com/browse/TP-21 >
    TP-22 Test Bug < http://jira.yourdomain.com/browse/TP-22 >

add a comment to an existing issue::

    skoenig@home ~ $ jira-cli comment TP-20 -c this is a new comment
    comment "this is a new comment" added to TP-20

provide your own formatting::

    skoenig@home ~ $ jira-cli --format='$reporter, $summary, $status' list TP-20

free text search for issues::

    skoenig@home ~ $ jira-cli list --search some random words

list only the comments for an issue::

    skoenig@home ~ $ jira-cli --comments-only list TP-20
    Thu Nov 10 08:42:55 UTC 2011 skoenig : this is a new comment
    Fri Dec 02 00:19:40 UTC 2011 skoenig : another comment
    Sat Mar 10 11:08:34 UTC 2012 skoenig : test comment
    Sat Mar 10 11:08:51 UTC 2012 skoenig : another test comment

