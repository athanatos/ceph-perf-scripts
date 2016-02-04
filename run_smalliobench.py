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

journal_config = config.get('journal', {})
bench_config = config.get('smalliobenchfs', {})
ceph_config = config.get('ceph', {})

def write_ceph_conf(config):
    ret = "[global]"
    for (key, value) in config.iteritems():
        print "\t{key} = {value}".format(
            key=key,
            value=value)

with tempfile.NamedTemporaryFile() as ceph_conf_file:
    ceph_conf_file.write(write_ceph_conf(ceph_config))
    proc = subprocess.Popen(
        args.smalliobench,
        
