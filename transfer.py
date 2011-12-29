#!/usr/bin/python

import os
import sys
import time
import error

def _print_progress(p, file_name, sent, size, time_elapsed) :
    # progress line format
    # file name ==========> percentage size speed time
    import math
    # TODO: get real line width. Currently
    # no unified way between unix and windows exists.
    line_width = 80
    size_width = 8 # xxx.xxXB
    speed_width = 10 # xxx.xxXB/s
    time_width = 6 # mmm:ss
    file_width = int(math.floor(line_width / 3.0))
    spaces = 4
    bar_width = line_width - file_width - size_width - \
                speed_width - time_width - spaces

    percent = float(sent) / size if size > 0 else 1.0
    actual_bar_width = int(math.ceil((bar_width - 5) * percent))
    bar = '=' * (actual_bar_width - 1)
    bar += '>' if percent < 1.0 else '='
    bar += ' ' * (bar_width - 5 - len(bar))
    bar += ' %3d%%' % int(math.floor(percent * 100))

    size_mark = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'ZB']
    mark_index = 0
    sent_bytes = sent
    while sent_bytes >= 1000.0 :
        if mark_index == (len(size_mark) - 1) :
            break
        sent_bytes /= 1024.0
        mark_index += 1
    sent_str = '%6.2lf%2s' % (round(sent_bytes, 2), size_mark[mark_index])

    if time_elapsed > 0.0 :
        min_elapsed = time_elapsed / 60
        sec_elapsed = time_elapsed % 60
        time_str = '%3d:%02d' % (min_elapsed, sec_elapsed)

        mark_index = 0
        speed = sent / time_elapsed
        while speed >= 1000.0 :
            if mark_index == (len(size_mark) - 1) :
                break
            speed /= 1024.0
            mark_index += 1
        speed_str = '%6.2lf%2s/s' % (round(speed, 2), size_mark[mark_index])
    else :
        time_str = '---:--'
        speed_str = '---.-- B/s'

    # build line format
    line_format = '%-' + str(file_width) + 's %s %s %s %s'
    line = line_format % (file_name[:file_width], bar[:bar_width],
                          sent_str[:size_width], speed_str[:speed_width],
                          time_str[:time_width])
    line += '\r' if percent < 1.0 else '\n'
    p.write(line)
    p.flush()

def send_file(i, o, progress, file_path, preserve) :
    stat = os.stat(file_path)

    # command: touch
    if preserve :
        i.write('T%s 0 %s 0\n' % (stat.st_mtime, stat.st_atime))
        i.flush()
        ret = o.read(1)
        if ret != '\0' :
            return error.E_UNK

    bytes_to_send = stat.st_size
    mode = oct(stat.st_mode & 0x1FF)
    # command: sending file
    i.write('C%s %ld %s\n' % (mode, bytes_to_send, os.path.basename(file_path)))
    i.flush()
    ret = o.read(1)
    if ret != '\0' :
        return error.E_UNK

    # data transfer starts right after C command
    fo = open(file_path, 'rb')
    start = time.time()
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
        if progress is not None :
            _print_progress(progress, os.path.basename(file_path),
                            stat.st_size - bytes_to_send, stat.st_size,
                            time.time() - start)
        if bytes_to_send <= 0 :
            break
    fo.close()
    # data transfer end
    i.write('\0')
    i.flush()
    ret = o.read(1)
    if ret != '\0' :
        return error.E_TFR

    return error.E_OK

def send_dir(i, o, progress, dir_path, preserve) :
    name = os.path.basename(dir_path)
    stat = os.stat(dir_path)

    # command: touch
    if preserve :
        i.write('T%s 0 %s 0\n' % (stat.st_mtime, stat.st_atime))
        i.flush()
        ret = o.read(1)
        if ret != '\0' :
            return error.E_UNK

    mode = oct(stat.st_mode & 0x1FF)
    # command: sending directory
    i.write('D%s 0 %s\n' % (mode, name))
    i.flush()
    ret = o.read(1)
    if ret != '\0' :
        return error.E_UNK

    items = os.listdir(dir_path)
    ret = error.E_OK
    for it in items :
        p = os.path.join(dir_path, it)
        if os.path.isdir(p) :
            ret = send_dir(i, o, progress, p, preserve)
        elif os.path.isfile(p) :
            ret = send_file(i, o, progress, p, preserve)
        if ret != error.E_OK :
            return ret

    i.write('E\n');
    i.flush();
    ret = o.read(1)
    if ret != '\0' :
        return error.E_UNK

    return error.E_OK

def send(i, o, progress, paths, preserve) :
    # check if receiving end is ready
    ret = o.read(1)
    if ret != '\0' :
        return error.E_RDY

    ret = error.E_OK
    for p in paths :
        if os.path.isfile(p) :
            ret = send_file(i, o, progress, p, preserve)
        elif os.path.isdir(p) :
            ret = send_dir(i, o, progress, p, preserve)
        if ret != error.E_OK :
            break
    return ret

def recv_file_dir_or_end(i, o, progress, target_dir, preserve) :
    command = o.readline()
    if len(command) == 0 :
        return error.E_END # end of transfer ?
    if command[0] == 'E' :
        i.write('\0')
        i.flush()
        return error.E_END # end of directory
    times = None
    if preserve :
        if command[0] == 'T' :
            times = command[1:-1].split(' ', 3)
            if len(times) != 4 :
                i.write('\2')
                i.flush()
                return E_UNK
            # ready tuple for utime (atime, mtime)
            times = (int(times[2]), int(times[0]))
            i.write('\0')
            i.flush()
            command = o.readline()
            if len(command) == 0 : # should never happen
                return error.E_UNK
        else :
            i.write('\2')
            i.flush()
            return E_UNK
    ret = error.E_UNK
    if command[0] == 'C' :
        i.write('\0')
        i.flush()
        ret = recv_file(i, o, progress, target_dir, command, preserve, times)
    elif command[0] == 'D' :
        i.write('\0')
        i.flush()
        ret = recv_dir(i, o, progress, target_dir, command, preserve, times)
    else :
        i.write('\2')
        i.flush()
    return ret

def recv_file(i, o, progress, target_dir, command, preserve, times) :
    # TODO: add regex check on the command format
    # ignore the '\n' at the end
    mode, size, path = command[1:-1].split(' ', 2)
    size = int(size)
    mode = int(mode, 8)

    if os.path.isdir(target_dir) :
        file_path = os.path.join(target_dir, path)
    else :
        file_path = target_dir
    fo = open(file_path, 'wb')
    full_size = size
    start = time.time()
    while True :
        if size < 4096 :
            chunk = size
        else :
            chunk = 4096
        buf = o.read(chunk)
        if len(buf) :
            fo.write(buf)
            size = size - len(buf)
        if progress is not None :
            _print_progress(progress, os.path.basename(file_path),
                            full_size - size, full_size,
                            time.time() - start)
        if size <= 0 :
            fo.flush()
            break
    fo.close()
    os.chmod(file_path, mode)
    if preserve :
        os.utime(file_path, times)
    ret = o.read(1)
    if ret != '\0' :
        i.write('\2')
        i.flush()
        return error.E_TFR
    else :
        i.write('\0')
        i.flush()

    return error.E_OK

def recv_dir(i, o, progress, dir_path, command, preserve, times) :
    # ignore the '\n' at the end
    mode, size, name = command[1:-1].split(' ', 2)
    mode = int(mode, 8)

    # TODO: check if sending dir is the same
    new_dir_path = os.path.join(dir_path, name)
    if not os.path.exists(new_dir_path) :
        os.mkdir(new_dir_path, mode)
    else :
        os.chmod(new_dir_path, mode)

    while True :
        ret = recv_file_dir_or_end(i, o, progress, new_dir_path, preserve)
        if ret == error.E_END :
            if preserve :
                os.utime(new_dir_path, times)
            return error.E_OK
        if ret != error.E_OK :
            if preserve :
                os.utime(new_dir_path, times)
            return ret

def recv(i, o, progress, dir_path, preserve) :
    i.write('\0') # ready to receive
    i.flush()

    while True :
        ret = recv_file_dir_or_end(i, o, progress, dir_path, preserve)
        if ret == error.E_END :
            return error.E_OK
        if ret != error.E_OK :
            return ret
