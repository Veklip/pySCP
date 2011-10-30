#!/usr/bin/python

import sys

def reverse_echo() :
    try :
        text = sys.stdin.readline()
        if len(text) :
            # put '\n' at the end
            sys.stdout.write(text[:-1][::-1] + text[-1])
    except KeyboardInterrupt :
        print >> sys.stdout, "Interrupted"

if __name__ == "__main__" :
    sys.exit(reverse_echo())
