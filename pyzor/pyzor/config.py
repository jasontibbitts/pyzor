"""Functions that handle parsing pyzor configuration files."""

import os
import logging
import collections

import pyzor
import pyzor.account

# Configuration files for the Pyzor Server

def load_access_file(access_fn, accounts):
    """Load the ACL from the specified file, if it exists, and return an
    ACL dictionary, where each key is a username and each value is a set
    of allowed permissions (if the permission is not in the set, then it
    is not allowed).

    'accounts' is a dictionary of accounts that exist on the server - only
    the keys are used, which must be the usernames (these are the users
    that are granted permission when the 'all' keyword is used, as
    described below).

    Each line of the file should be in the following format:
        operation : user : allow|deny
    where 'operation' is a space-separated list of pyzor commands or the
    keyword 'all' (meaning all commands), 'username' is a space-separated
    list of usernames or the keyword 'all' (meaning all users) - the
    anonymous user is called "anonymous", and "allow|deny" indicates whether
    or not the specified user(s) may execute the specified operations.

    The file is processed from top to bottom, with the final match for
    user/operation being the value taken.  Every file has the following
    implicit final rule:
        all : all : deny

    If the file does not exist, then the following default is used:
        check report ping info : anonymous : allow
    """
    log = logging.getLogger("pyzord")
    # A defaultdict is safe, because if we get a non-existant user, we get
    # the empty set, which is the same as a deny, which is the final
    # implicit rule.
    acl = collections.defaultdict(set)
    if not os.path.exists(access_fn):
        log.info("Using default ACL: the anonymous user may use the check, "
                 "report, ping and info commands.")
        acl[pyzor.anonymous_user] = set(("check", "report", "ping", "pong",
                                         "info"))
        return acl
    for line in open(access_fn):
        if not line.strip() or line[0] == "#":
            continue
        try:
            operations, users, allowed = [part.lower().strip()
                                          for part in line.split(":")]
        except ValueError:
            log.warn("Invalid ACL line: %r", line)
            continue
        try:
            allowed = {"allow": True, "deny" : False}[allowed]
        except KeyError:
            log.warn("Invalid ACL line: %r", line)
            continue
        if operations == "all":
            operations = ("check", "report", "ping", "pong", "info",
                          "whitelist")
        else:
            operations = [operation.strip()
                          for operation in operations.split()]
        if users == "all":
            users = accounts
        else:
            users = [user.strip() for user in users.split()]
        for user in users:
            if allowed:
                log.debug("Granting %s to %s.", ",".join(operations), user)
                # If these operations are already allowed, this will have
                # no effect.
                acl[user].update(operations)
            else:
                log.debug("Revoking %s from %s.", ",".join(operations), user)
                # If these operations are not allowed yet, this will have
                # no effect.
                acl[user].difference_update(operations)
    log.info("ACL: %r", acl)
    return acl

def load_passwd_file(passwd_fn):
    """Load the accounts from the specified file.

    Each line of the file should be in the format:
        username : key

    If the file does not exist, then an empty dictionary is returned;
    otherwise, a dictionary of (username, key) items is returned.
    """
    log = logging.getLogger("pyzord")
    accounts = {}
    if not os.path.exists(passwd_fn):
        log.info("Accounts file does not exist - only the anonymous user "
                 "will be available.")
        return accounts
    for line in open(passwd_fn):
        if not line.strip() or line[0] == "#":
            continue
        try:
            user, key = line.split(":")
        except ValueError:
            log.warn("Invalid accounts line: %r", line)
            continue
        user = user.strip()
        key = key.strip()
        log.debug("Creating an account for %s with key %s.", user, key)
        accounts[user] = key
    # Don't log the keys at 'info' level, just ther usernames.
    log.info("Accounts: %s", ",".join(accounts))
    return accounts

# Configuration files for the Pyzor Client

def load_accounts(filename):
    """Layout of file is: host : port : username : salt,key"""
    accounts = {}
    log = logging.getLogger("pyzor")
    if os.path.exists(filename):
        for lineno, orig_line in enumerate(open(filename)):
            line = orig_line.strip()
            if not line or line.startswith('#'):
                continue
            try:
                host, port, username, key = [x.strip()
                                             for x in line.split(":")]
            except ValueError:
                log.warn("account file: invalid line %d: wrong number of "
                         "parts", lineno)
                continue
            try:
                port = int(port)
            except ValueError, e:
                log.warn("account file: invalid line %d: %s", lineno, e)
            address = (host, port)
            salt, key = pyzor.account.key_from_hexstr(key)
            if not salt and not key:
                log.warn("account file: invalid line %d: keystuff can't be "
                         "all None's", lineno)
                continue
            try:
                accounts[address] = pyzor.account.Account(username, salt, key)
            except ValueError, e:
                log.warn("account file: invalid line %d: %s", lineno, e)
    else:
        log.warn("No accounts are setup.  All commands will be executed by "
                 "the anonymous user.")
    return accounts