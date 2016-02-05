#!env python
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

OP_DUMP_FILE_NAME = "ops.json"
op_dump_file = os.path.join(args.output_path, OP_DUMP_FILE_NAME)
LOG_FILE_NAME = "log_output.log"
log_file = os.path.join(args.output_path, LOG_FILE_NAME)

try:
    logfd = open(log_file, 'w')
except Exception, e:
    print "Error opening log file: ", e
    sys.exit(1)

proc = None
with tempfile.NamedTemporaryFile() as ceph_conf_file:
    ceph_conf_file.write(write_ceph_conf(ceph_config))
    args = ['args.smalliobench_path']
    args += ['-c', ceph_conf_file.name]
    args += ['--op-dump-file', op_dump_file]
    args += ['--filestore-path', args.filestore_path]
    args += ['--journal-path', args.journal_path]
    for arg, val in bench_config.iteritems():
        args += ['--' + str(arg), str(val)]
    try:
        proc = subprocess.Popen(
            args,
            stdout = logfd,
            stderr = logfd)
    except Exception, e:
        print "Error starting smalliobench: ", e
        sys.exit(1)
