#!/bin/sh -e
set -x
isort --force-single-line-imports asyncoptoma
autoflake --remove-all-unused-imports --recursive --remove-unused-variables --in-place asyncoptoma
black asyncoptoma
isort asyncoptoma
