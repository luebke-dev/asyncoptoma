#!/bin/sh -e
set -x
isort --recursive --force-single-line-imports --apply asyncoptoma
autoflake --remove-all-unused-imports --recursive --remove-unused-variables --in-place asyncoptoma
black asyncoptoma
isort --recursive --apply asyncoptoma