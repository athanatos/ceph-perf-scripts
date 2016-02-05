#!/usr/bin/python
"""
smalliobench tester script

Takes a yaml file describing the test to run:

journal:
    size: <size>
smalliobenchfs: <options>
"""
import argparse
import yaml
import subprocess
import sys
import tempfile
import os
import os.path
import json
import numpy as np
import atexit
import time

parser = argparse.ArgumentParser(
    description='Run smalliobench'
)
parser.add_argument(
    '--config',
    type=str,
    required=True,
)
parser.add_argument(
    '--smalliobench-path',
    type=str,
    required=True,
)
parser.add_argument(
    '--filestore-path',
    type=str,
    required=True,
)
parser.add_argument(
    '--journal-path',
    type=str,
    required=True,
)
parser.add_argument(
    '--output-path',
    type=str,
    required=True,
)

args = parser.parse_args()
print args

config = None
try:
    configstr = ""
    for confpath in args.config.split(','):
        with open(confpath) as config_file:
            configstr += config_file.read()
    print configstr
    config = yaml.load(configstr)
except Exception as e:
    print "Error opening config {config}: {error}".format(
        config=args.config,
        error=e)
    sys.exit(1)

bench_config = config.get('smalliobenchfs', {})
ceph_config = config.get('ceph', {})

def write_ceph_conf(config):
    ret = "[global]\n"
    for (key, value) in config.iteritems():
        print "\t{key} = {value}".format(
            key=key,
            value=value)
    return ret

def process_log_file(fd):
    l1 = fd.readline()
    start = json.loads(l1)['start']
    last = start
    recent = []
    ps = []
    for line in fd.xreadlines():
        val = json.loads(line)
        if val['type'] != 'write_applied':
            continue
        t = val['start']
        recent += [val['latency']]
        if t - last > 1:
            avg = sum(recent)/len(recent)
            npc = np.percentile(recent, 99)
            iops = len(recent) / (t - last)
            print t-start, avg, npc
            ps += [(t, avg, npc, iops)]
            last = t
            current = []
    def project(ind, l):
        return (x[ind] for x in l)
    return {
        '99_latency_stddev': np.std(project(2))
    }
        

OP_DUMP_FILE_NAME = "ops.json"
op_dump_file = os.path.join(args.output_path, OP_DUMP_FILE_NAME)

LOG_FILE_NAME = "log_output.log"
log_file = os.path.join(args.output_path, LOG_FILE_NAME)

JOURNAL_LOG_NAME = "filestore.log"
jlog_file = os.path.join(args.output_path, JOURNAL_LOG_NAME)

FIFO_NAME = "ops.fifo"
fifo_file = os.path.join(args.output_path, FIFO_NAME)

try:
    logfd = open(log_file, 'w')
except Exception, e:
    print "Error opening log file: ", e
    sys.exit(1)

proc = None
def on_exit():
    try:
        proc.kill()
    except:
        pass
atexit.register(on_exit)

with tempfile.NamedTemporaryFile() as ceph_conf_file:
    ceph_conf_file.write(write_ceph_conf(ceph_config))
    argl = [args.smalliobench_path]
    argl += ['-c', ceph_conf_file.name]
    argl += ['--filestore-path', args.filestore_path]
    argl += ['--journal-path', args.journal_path]
    argl += ['--op-dump-file', fifo_file]

    for arg, val in bench_config.iteritems():
        argl += ['--' + str(arg), str(val)]
    try:
        os.mkfifo(fifo_file)
        proc = subprocess.Popen(
            argl,
            stdout = open('/dev/null', 'w'),
            stderr = open('/dev/null', 'w'))

        with open(fifo_file, 'r') as fifo_fd:
            print process_log_file(fifo_fd)
        proc.wait()
    except Exception, e:
        print "Error starting smalliobench: ", e
        sys.exit(1)
