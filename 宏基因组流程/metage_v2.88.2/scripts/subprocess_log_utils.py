#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Run child commands without retaining successful per-script log files.

Cromwell already captures task-level stdout/stderr. Child processes that run in
parallel still need an isolated file so their output does not interleave. The
file is therefore retained only when the command fails.
"""

from __future__ import print_function

import os
import subprocess


def _remove_empty_parents(path, stop_dir=None):
    directory = os.path.dirname(os.path.abspath(path))
    stop = os.path.abspath(stop_dir) if stop_dir else None
    while directory and directory != stop:
        try:
            os.rmdir(directory)
        except OSError:
            break
        directory = os.path.dirname(directory)


def run_with_failure_log(cmd, log_file, cwd=None, stop_dir=None):
    """Run *cmd*, delete its log on success, and retain it on failure."""
    log_file = os.path.abspath(log_file)
    log_dir = os.path.dirname(log_file)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    try:
        with open(log_file, "w") as handle:
            subprocess.check_call(
                cmd,
                cwd=cwd,
                stdout=handle,
                stderr=subprocess.STDOUT,
            )
    except (OSError, subprocess.CalledProcessError):
        raise
    else:
        try:
            os.remove(log_file)
        except OSError:
            pass
        _remove_empty_parents(log_file, stop_dir=stop_dir)


def run_commands_with_failure_log(commands, log_file, cwd=None, stop_dir=None):
    """Run several commands sequentially using one failure-only log file."""
    log_file = os.path.abspath(log_file)
    log_dir = os.path.dirname(log_file)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    try:
        with open(log_file, "w") as handle:
            for cmd in commands:
                subprocess.check_call(
                    cmd,
                    cwd=cwd,
                    stdout=handle,
                    stderr=subprocess.STDOUT,
                )
    except (OSError, subprocess.CalledProcessError):
        raise
    else:
        try:
            os.remove(log_file)
        except OSError:
            pass
        _remove_empty_parents(log_file, stop_dir=stop_dir)
