#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import argparse
import os
import subprocess
from tempfile import NamedTemporaryFile

def checkQmakePath(path):
    if path is None:
        return False

    if path == "**Unknown**":
        return False

    if not os.path.isdir(path):
        return False

    return True

def findProgram(path, progName):
    if not checkQmakePath(path):
        return None

    progPath = os.path.join(path, progName)
    if not os.path.isfile(progPath):
        # On Windows the host tools (built by the contrib static cross build)
        # carry a .exe suffix; os.path.isfile does not resolve PATHEXT.
        progPathExe = progPath + ".exe"
        if not os.path.isfile(progPathExe):
            return None
        return progPathExe

    return progPath


class QmlModuleChecker:
    def __init__(self):
        self.qt5 = True
        self.qmlimportscanner = None
        self.qmlpath = None

    def genQmlFile(self, f, modules):
        for module, version in modules:
            f.write("import {} {}\n".format(module, version))
        f.write("Item {}\n")
        f.flush()

    def scanImports(self, f, modules):
        ret = subprocess.run(
            [
                self.qmlimportscanner,
                "-qmlFiles", f.name,
                "-importPath", self.qmlpath
            ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )

        if ret.returncode != 0:
            print(ret.stderr.strip())
            return None

        return json.loads(ret.stdout)

    def checkImports(self, scanlist, modules):
        ret = True
        for name, version in modules:
            found = False
            for entry in scanlist:
                if entry["type"] == "module" and entry["name"] == name:
                    #qt6 modules have no version
                    if self.qt5 and not  entry["version"] == version:
                        continue
                    if "classname" in entry:
                        found = True
                        break
            print("checking for {} {}... {}".format(name, version, "yes" if found else "no"))
            if not found:
                ret = False

        return ret


    def getInstallInfo(self, qmake, qtconf):
        qmake_cmd = [ qmake, "-query" ]
        if qtconf:
            qmake_cmd += [ "-qtconf", qtconf ]
        ret = subprocess.run(
            qmake_cmd,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            encoding="utf8"
        )

        if ret.returncode != 0:
            print(ret.stderr.strip())
            return False

        binpath_host = None
        libexec_host = None
        binpath_install = None
        libexec_install = None
        qtmajor = ""
        for l in ret.stdout.splitlines():
            l = l.strip()
            if l.startswith("QT_HOST_BINS:"):
                binpath_host = l.split(":", 1)[1]
            elif l.startswith("QT_HOST_LIBEXECS:"):
                libexec_host = l.split(":", 1)[1]
            elif l.startswith("QT_INSTALL_BINS:"):
                binpath_install = l.split(":", 1)[1]
            elif l.startswith("QT_INSTALL_LIBEXECS:"):
                libexec_install = l.split(":", 1)[1]
            elif l.startswith("QT_INSTALL_QML:"):
                self.qmlpath = l.split(":", 1)[1]
            elif l.startswith("QT_VERSION:"):
                qmlversion = l.split(":", 1)[1]
                qtmajor = qmlversion.split(".")[0]

        if qtmajor == "6":
            self.qt5 = False

        if not checkQmakePath(self.qmlpath):
            print("Qml path {} not found".format(self.qmlpath))
            return False

        self.qmlimportscanner = findProgram(binpath_install, "qmlimportscanner")
        if self.qmlimportscanner is not None:
            return True

        #Qt6 may place qmlimportscanner in libexec_host
        self.qmlimportscanner = findProgram(libexec_install, "qmlimportscanner")
        if self.qmlimportscanner is not None:
            return True

        self.qmlimportscanner = findProgram(binpath_host, "qmlimportscanner")
        if self.qmlimportscanner is not None:
            return True

        #Qt6 may place qmlimportscanner in libexec_host
        self.qmlimportscanner = findProgram(libexec_host, "qmlimportscanner")
        if self.qmlimportscanner is not None:
            return True

        print("qmlimportscanner not found")
        return False


class KeyValue(argparse.Action):
    def __call__( self , parser, namespace,
                  values, option_string = None):
        setattr(namespace, self.dest, [])

        for value in values:
            key, value = value.split('=')
            getattr(namespace, self.dest).append((key, value))

def main():
    parser = argparse.ArgumentParser("check for qml runtime dependencies")
    parser.add_argument(
        "--qmake", type=str, required=True,
        help="native qmake path")

    parser.add_argument(
        "--qtconf", type=str, required=False,
        help="qmake qtconf path")

    parser.add_argument(
        "--modules", nargs="+", action=KeyValue, required=True,
        help="list of modules to check in the form module=version (ex QtQuick=2.12)")

    args = parser.parse_args()

    moduleChecker = QmlModuleChecker()
    if not moduleChecker.getInstallInfo(args.qmake, args.qtconf):
        exit(-1)

    # The generated .qml file must be closed before qmlimportscanner reads it.
    # On Windows a file kept open in w+ mode is not reliably readable by the
    # spawned qmlimportscanner process (it parses the file as empty/garbage and
    # reports "Expected token numeric literal"), so no modules are detected.
    tmpf = NamedTemporaryFile(mode="w+", suffix=".qml", delete=False)
    try:
        moduleChecker.genQmlFile(tmpf, args.modules)
    finally:
        tmpf.close()

    scanlist = moduleChecker.scanImports(tmpf, args.modules)
    if scanlist is None:
        exit(-1)

    if not moduleChecker.checkImports(scanlist, args.modules):
        exit(-1)

    os.unlink(tmpf.name)
    exit(0)

if __name__ == "__main__":
    main()
