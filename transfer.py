#!/usr/bin/python

import os
import sys

# TODO: add T command
def send_file(i, o, file_path) :
    stat = os.stat(file_path)
    bytes_to_send = stat.st_size
    mode = oct(stat.st_mode & 0x1FF)
    # command: sending file
    i.write('C%s %ld %s\n' % (mode, bytes_to_send, os.path.basename(file_path)))
    i.flush()
    ret = o.read(1)
    if ret != '\0' :
        return 1

    # data transfer starts right after C command
    fo = open(file_path, 'rb')
    while True :
        if bytes_to_send < 4096 :
            chunk = bytes_to_send
        else :
            chunk = 4096
        buf = fo.read(chunk)
        if len(buf) :
            i.write(buf)
            i.flush()
            bytes_to_send = bytes_to_send - len(buf)
        if bytes_to_send <= 0 :
            break
    fo.close()
    # data transfer end
    i.write('\0')
    i.flush()
    ret = o.read(1)
    if ret != '\0' :
        return 2

    return 0

def send_dir(i, o, dir_path) :
    name = os.path.basename(dir_path)
    stat = os.stat(dir_path)
    mode = oct(stat.st_mode & 0x1FF)
    # command: sending directory
    i.write('D%s 0 %s\n' % (mode, name))
    i.flush()
    ret = o.read(1)
    if ret != '\0' :
        return 1

    items = os.listdir(dir_path)
    ret = 0
    for it in items :
        p = os.path.join(dir_path, it)
        if os.path.isdir(p) :
            ret = send_dir(i, o, p)
        elif os.path.isfile(p) :
            ret = send_file(i, o, p)
        if ret != 0 :
            return ret

    i.write('E\n');
    i.flush();
    ret = o.read(1)
    if ret != '\0' :
        return 2

    return 0

def send(i, o, paths) :
    # check if receiving end is ready
    ret = o.read(1)
    if ret != '\0' :
        return 1

    ret = 0
    for p in paths :
        if os.path.isfile(p) :
            ret = send_file(i, o, p)
        elif os.path.isdir(p) :
            ret = send_dir(i, o, p)
        if ret != 0 :
            break
    return ret

def recv_file_dir_or_end(i, o, target_dir) :
    # TODO: handle the return codes of the _recv_* functions
    command = o.readline()
    if len(command) == 0 :
        return -1 # end of transfer ?
    ret = 65535 # big enough number
    if command[0] == 'C' :
        i.write('\0')
        i.flush()
        ret = recv_file(i, o, target_dir, command)
    elif command[0] == 'D' :
        i.write('\0')
        i.flush()
        ret = recv_dir(i, o, target_dir, command)
    elif command[0] == 'E' :
        i.write('\0')
        i.flush()
        ret = -1 # end of directory
    else :
        i.write('\2')
        i.flush()
    return ret

def recv_file(i, o, target_dir, command) :
    # TODO: add regex check on the command format
    # ignore the '\n' at the end
    mode, size, path = command[1:-1].split(' ', 3)
    size = int(size)
    mode = int(mode, 8)

    if os.path.isdir(target_dir) :
        file_path = os.path.join(target_dir, path)
    else :
        file_path = target_dir
    fo = open(file_path, 'wb')
    while True :
        if size < 4096 :
            chunk = size
        else :
            chunk = 4096
        buf = o.read(chunk)
        if len(buf) :
            fo.write(buf)
            size = size - len(buf)
        if size <= 0 :
            fo.flush()
            break
    fo.close()
    os.chmod(file_path, mode)
    ret = o.read(1)
    if ret != '\0' :
        i.write('\2')
        i.flush()
        return 2
    else :
        i.write('\0')
        i.flush()

    return 0

def recv_dir(i, o, dir_path, command) :
    # ignore the '\n' at the end
    mode, size, name = command[1:-1].split(' ', 3)
    mode = int(mode, 8)

    # TODO: check if sending dir is the same
    new_dir_path = os.path.join(dir_path, name)
    if not os.path.exists(new_dir_path) :
        os.mkdir(new_dir_path, mode)
    else :
        os.chmod(new_dir_path, mode)

    while True :
        ret = recv_file_dir_or_end(i, o, new_dir_path)
        if ret == -1 :
            return 0 # E command
        if ret == 65535 :
            return 1 # wrong command
        if ret != 0 :
            return 2 # error in transfer

def recv(i, o, dir_path) :
    i.write('\0') # ready to receive
    i.flush()

    while True :
        ret = recv_file_dir_or_end(i, o, dir_path)
        if ret == -1 :
            return 0 # E command
        if ret == 65535 :
            return 1 # wrong command
        if ret != 0 :
            return 2 # error in transfer
