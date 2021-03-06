#
# Copyright 2012 SAS Institute
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import gzip
import os
import stat
import time
import weakref

class Log(object):
    def __init__(self, ctx, repo, cache):
        self.ctx = ctx
        self.cache = None
        if cache is not None:
            self.cache = weakref.ref(cache)
        self.repo = repo
        logDir = ctx.getLogDir()
        repoLogDir = '/'.join((logDir, ctx.getRepositoryName(repo)))
        basename = time.strftime('%Y%m%d-%H:%M:%S')
        if not os.path.exists(repoLogDir):
            os.makedirs(repoLogDir)
        self.thislog = '%s/%s.log' %(repoLogDir, basename)
        self.thiserr = '%s/%s.err' %(repoLogDir, basename)
        self.stdout = os.open(self.thislog, os.O_CREAT|os.O_RDWR, 0700)
        self.stderr = os.open(self.thiserr, os.O_CREAT|os.O_RDWR, 0700)
        self.start_mark = (None, None)
        self.stop_mark = (None, None)

    @staticmethod
    def tell(fd):
        return os.lseek(fd, 0, os.SEEK_CUR)

    def writeError(self, message):
        os.write(self.stderr, message)

    def currentMark(self):
        return (self.tell(self.stdout),
                self.tell(self.stderr))

    def markStart(self):
        self.start_mark = self.currentMark()
        self.stop_mark = (None, None)

    def markStop(self):
        self.stop_mark = self.currentMark()

    @staticmethod
    def read(filename, start, stop):
        f = file(filename)
        f.seek(start)
        return f.read(stop - start)

    def lastError(self):
        if None in (self.start_mark + self.stop_mark):
            return None
        return self.read(self.thiserr, self.start_mark[1], self.stop_mark[1])

    def lastOutput(self):
        if None in (self.start_mark + self.stop_mark):
            return (None, None)
        return (self.read(self.thislog, self.start_mark[0], self.stop_mark[0]),
                self.read(self.thiserr, self.start_mark[1], self.stop_mark[1]))

    def mailLastOutput(self, command):
        self.ctx.mails[self.repo].addOutput(command, *self.lastOutput())

    def _compress(self, filename):
        if not self.ctx.getCompressLogs():
            return
        gzo = gzip.GzipFile(filename + '.gz', 'w', 9)
        gzo.writelines(open(filename))
        gzo.close()
        os.remove(filename)

    def close(self):
        outstat = os.fstat(self.stdout)
        errstat = os.fstat(self.stderr)
        os.close(self.stdout)
        os.close(self.stderr)

        if errstat.st_size:
            # errors have been written
            self.ctx.mails[self.repo].send(
                file(self.thislog).read(),
                file(self.thiserr).read())
            self._compress(self.thiserr)

        if outstat.st_size:
            self._compress(self.thislog)

        if self.cache and self.cache():
            del self.cache()[self.repo]

class LogCache(dict):
    def __init__(self, ctx):
        self.ctx = ctx

    def __getitem__(self, name):
        if not self.has_key(name):
            self.__setitem__(name, Log(self.ctx, name, self))
        return dict.__getitem__(self, name)
