#!/bin/bash

DIRECTORY=~/sjust/output/$1-$(date '+%Y-%m-%d-%H:%M:%S')
echo $DIRECTORY
mkdir $DIRECTORY
for i in $(ls confs)
do
        rm -rf /mnt/filestore/*
        mkdir $DIRECTORY/$i
        ./run_smalliobench.py  --smalliobench-path $2 --journal-path /dev/disk/by-partlabel/journal-64 --config confs/$i --filestore-path /mnt/filestore --output-path $DIRECTORY/$i
done
