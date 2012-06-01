import os
import shell
import tempfile

from gitcvs import util

# One CVS checkout per branch, because CVS switches branches slowly/poorly,
# so there is one CVS object per branch, not per repository.
# No checkout directory is created for exporting

def setCVSROOT(fn):
    def wrapper(self, *args, **kwargs):
        self.setEnvironment()
        fn(self, *args, **kwargs)
    return wrapper

def inCVSPATH(fn):
    def wrapper(self, *args, **kwargs):
        oldDir = os.getcwd()
        os.chdir(self.path)
        try:
            fn(self, *args, **kwargs)
        finally:
            os.chdir(oldDir)
    return wrapper

def inCVSDIR(fn):
    def wrapper(self, *args, **kwargs):
        oldDir = os.getcwd()
        os.chdir(os.path.dirname(self.path))
        try:
            fn(self, *args, **kwargs)
        finally:
            os.chdir(oldDir)
    return wrapper

class CVS(object):
    def __init__(self, ctx, repo, branch, username):
        self.ctx = ctx
        self.location = self.ctx.getCVSPath(repo)
        self.path = ctx.getCVSBranchCheckoutDir(repo, branch)
        self.pathbase = ctx.getRepositoryName(repo)
        self.branch = branch
        self.log = self.ctx.logs[repo]
        self.root = ctx.getCVSRoot(repo, username)

    def setEnvironment(self):
        os.environ['CVSROOT'] = self.root

    def listFiles(self, path):
        allfiles = []
        dirlen = len(path) + 1
        for root, dirs, files in os.walk(path):
            if 'CVS' in dirs:
                dirs.remove('CVS') 
            allfiles.extend(['/'.join((root, x))[dirlen:] for x in files])
        return allfiles

    def listContentFiles(self):
        return self.listFiles(self.path)

    @setCVSROOT
    def export(self, targetDir):
        shell.run(self.log,
            'cvs', 'export', '-d', targetDir, '-r', self.branch, self.location)

    def cleanKeywords(self, fileList):
        shell.run(self.log,
            'sed', '-i', '-r',
            r's/\$(Author|Date|Header|Id|Name|Locker|RCSfile|Revision|Source|State):[^\$]*\$/$\1$/g',
            *fileList)

    @setCVSROOT
    @inCVSDIR
    def checkout(self):
        shell.run(self.log,
            'cvs', 'checkout', '-d', self.pathbase, '-r', self.branch, self.location)

    @inCVSPATH
    def update(self):
        shell.run(self.log, 'cvs', 'update', '-d')

    @inCVSPATH
    def deleteFiles(self, fileNames):
        if fileNames:
            for fileName in fileNames:
                os.remove(fileName)
            shell.run(self.log, 'cvs', 'remove', *fileNames)

    def copyFiles(self, sourceDir, fileNames):
        'call addFiles for any files being added rather than updated'
        util.copyFiles(sourceDir, self.path, fileNames)

    @inCVSPATH
    def addFiles(self, fileNames):
        if fileNames:
            shell.run(self.log, 'cvs', 'add', *fileNames)

    @inCVSPATH
    def commit(self, message):
        fd, name = tempfile.mkstemp('.gitcvs')
        os.write(fd, message)
        try:
            shell.run(self.log, 'cvs', 'commit', '-r', self.branch, '-R', '-F', name)
        finally:
            os.remove(name)
            os.close(fd)
