#!/usr/bin/python

import os
import sys
import getpass

def parse_paths(paths) :
    parsed_paths = []
    for path in paths :
        host_path = path.split(':', 1)
        if len(host_path) == 1 :
            # local path
            parsed_paths.append({'user':'current', 'host':'local', 'path':host_path[0]})
        else :
            # remote path
            usr_host = host_path[0].split('@', 1)
            if len(usr_host) == 1 :
                parsed_paths.append({'user':'current', 'host':usr_host[0], 'path':host_path[1]})
            else :
                parsed_paths.append({'user':usr_host[0], 'host':usr_host[1], 'path':host_path[1]})
    return parsed_paths

def analyse_paths(paths) :
    user = paths[0]['user']
    host = paths[0]['host']
    stripped = [paths[0]['path']]

    for i in range(1, len(paths) - 1) :
        if user != paths[i]['user'] or host != paths[i]['host'] :
            sys.stderr.write("Error: all source paths need to be from the same user and host\n")
            return False, "", "", []
        stripped.append(paths[i]['path'])

    if host == paths[-1]['host'] :
        sys.stderr.write("Error: source and sink files need to be with different hosts\n")
        return False, "", "", []
    stripped.append(paths[-1]['path'])

    if host == "local" :
        if paths[-1]['user'] != 'current' :
            return True, paths[-1]['user'], paths[-1]['host'], stripped
        else :
            return True, getpass.getuser(), paths[-1]['host'], stripped
    else :
        if user != 'current' :
            return False, user, host, stripped
        else :
            return False, getpass.getuser(), host, stripped

def check_pkeys(pkey_files) :
    if pkey_files is None :
        return True

    for key in pkey_files :
        if not os.path.exists(key) :
            sys.stderr.write("Key file '{0}' doesn't exist\n".format(key))
            return False
    return True
