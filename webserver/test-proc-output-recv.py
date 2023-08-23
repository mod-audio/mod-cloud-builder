#!/usr/bin/env python3
# MOD Cloud Builder
# SPDX-FileCopyrightText: 2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

#from subprocess import PIPE, STDOUT, Popen, TimeoutExpired
from asyncio.subprocess import create_subprocess_exec, PIPE, STDOUT
from asyncio import run
from time import sleep

loop = 0
async def main():
    p = await create_subprocess_exec("carla", stdout=PIPE, stderr=STDOUT)
    while True:
        stdout = await p.stdout.readline()
        if stdout == b'':
            break
        print('----------------------', stdout.decode('utf-8'), end='')

        global loop
        loop += 1
        if loop == 9:
            p.kill()

run(main())
