#!/usr/bin/env python3
#
# Baut ein vorhandenes Toolchain-Archiv auf das relozierbare Layout um, das
# pack.py jetzt erzeugt -- ohne die Toolchain neu zu bauen.
#
# Warum: gcc ist mit --with-sysroot='${prefix}/../../target_<suffix>' konfiguriert
# und rechnet den Pfad zur Laufzeit relativ zum Aufrufort neu (gcc/gcc.cc,
# TARGET_SYSTEM_ROOT_RELOCATABLE).  Es uebernimmt das Ergebnis aber nur, wenn
# access() darauf gelingt.  Das alte Archivlayout (<root>/usr + <root>/sysroot)
# ist eine Ebene flacher als der Build-Baum, der relative Pfad zeigt also aus dem
# Archiv heraus -> gcc faellt auf den einkompilierten Absolutpfad zurueck
# (/home/ramin/openadk/... bzw. /root/openadk/...).  Fuer einen anderen Benutzer
# ist der nicht lesbar: "cc1: error: ...: Permission denied"; auf einer anderen
# Maschine fehlt er ganz: "stdio.h: No such file or directory".
#
# Neues Layout (Geschwister wie im openadk-Baum, plus Kompatibilitaets-Symlinks):
#
#   <archiv>/toolchain_<suffix>/usr/...
#   <archiv>/toolchain_<suffix>/sysroot -> ../target_<suffix>
#   <archiv>/target_<suffix>/...
#   <archiv>/usr     -> toolchain_<suffix>/usr
#   <archiv>/sysroot -> target_<suffix>
#   <archiv>/{config,os-release,prefix,openadk_hash} -> toolchain_<suffix>/...
#
# Aufruf:  ./repack_relocatable.py [--out DIR] [--keep] <tarball> [<tarball> ...]
#          ./repack_relocatable.py --check <tarball>      (nur pruefen, nichts schreiben)

import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile

META_FILES = ("config", "os-release", "prefix", "openadk_hash")


def run(cmd, **kw):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, **kw)


def find_gcc(root):
    hits = glob.glob(root + "/usr/bin/*-gcc")
    hits = [h for h in hits if not h.endswith(("-gcc-ar", "-gcc-nm", "-gcc-ranlib"))]
    if len(hits) != 1:
        raise RuntimeError("kein eindeutiges gcc unter %s/usr/bin: %s" % (root, hits))
    return hits[0]


def sysroot_names(gcc):
    """(toolchain_<suffix>, target_<suffix>) aus dem einkompilierten Sysroot-Pfad.

    -print-sysroot liefert z.B.
        /home/ramin/openadk/toolchain_qemu-nios2_uclibc-ng/usr/../../target_qemu-nios2_uclibc-ng
    """
    out = run(gcc + " -print-sysroot").stdout.strip()
    if not out:
        raise RuntimeError("%s -print-sysroot liefert nichts" % gcc)
    m = re.match(r"^(?P<prefix>.*)/usr/\.\./\.\./(?P<target>[^/]+)$", out)
    if not m:
        raise RuntimeError("unerwarteter Sysroot-Pfad: %s" % out)
    return os.path.basename(m.group("prefix")), m.group("target")


def restructure(root, build_name, target_name):
    tc = os.path.join(root, build_name)
    os.makedirs(tc)
    shutil.move(os.path.join(root, "usr"), os.path.join(tc, "usr"))
    shutil.move(os.path.join(root, "sysroot"), os.path.join(root, target_name))
    for f in META_FILES:
        if os.path.exists(os.path.join(root, f)):
            shutil.move(os.path.join(root, f), os.path.join(tc, f))
            os.symlink(os.path.join(build_name, f), os.path.join(root, f))
    # innerhalb von toolchain_<suffix> sieht der Baum aus wie die alte Archivwurzel,
    # damit bleiben alle relativen Links (usr/<target>/lib -> ../../sysroot/usr/lib)
    # und die CI-Konstruktionen (../../../sysroot/usr/lib/ldscripts) gueltig
    os.symlink(os.path.join("..", target_name), os.path.join(tc, "sysroot"))
    os.symlink(os.path.join(build_name, "usr"), os.path.join(root, "usr"))
    os.symlink(target_name, os.path.join(root, "sysroot"))


def verify(root):
    """Prueft, dass gcc sein Sysroot jetzt innerhalb des Archivs findet."""
    gcc = find_gcc(root)
    real = os.path.realpath(root)
    problems = []

    got = run(gcc + " -print-sysroot").stdout.strip()
    if not os.path.realpath(got).startswith(real):
        problems.append("Sysroot zeigt weiter nach aussen: " + got)
    elif not os.path.isdir(got):
        problems.append("Sysroot existiert nicht: " + got)

    r = run("echo '#include <stdio.h>' | " + gcc + " -E - -o /dev/null")
    if r.returncode != 0:
        problems.append("stdio.h nicht gefunden:\n" + r.stderr.strip())

    crt1 = run(gcc + " -print-file-name=crt1.o").stdout.strip()
    if crt1 == "crt1.o" or not os.path.exists(crt1):
        problems.append("crt1.o nicht gefunden (" + crt1 + ")")
    elif not os.path.realpath(crt1).startswith(real):
        problems.append("crt1.o kommt von ausserhalb: " + crt1)

    return problems


def process(tarball, out_dir, keep, check_only):
    name = os.path.basename(tarball)
    print("=== " + name)
    tmp = tempfile.mkdtemp(prefix="repack-", dir=out_dir or os.path.dirname(os.path.abspath(tarball)))
    try:
        if run("tar -xaf '%s' -C '%s'" % (tarball, tmp)).returncode != 0:
            print("    FEHLER beim Entpacken")
            return False
        roots = [os.path.join(tmp, d) for d in os.listdir(tmp)]
        if len(roots) != 1 or not os.path.isdir(roots[0]):
            print("    FEHLER: unerwarteter Archivinhalt")
            return False
        root = roots[0]

        if os.path.islink(os.path.join(root, "usr")):
            print("    schon umgebaut, uebersprungen")
            return True
        if not os.path.isdir(os.path.join(root, "sysroot")):
            print("    kein sysroot/ im Archiv, uebersprungen")
            return False

        gcc = find_gcc(root)
        build_name, target_name = sysroot_names(gcc)
        print("    %s  +  %s" % (build_name, target_name))

        before = verify(root)
        print("    vorher : " + ("relozierbar" if not before else before[0].split("\n")[0]))
        if check_only:
            return not before

        restructure(root, build_name, target_name)
        after = verify(root)
        if after:
            print("    FEHLER nach Umbau:")
            for p in after:
                print("      " + p)
            return False
        print("    nachher: relozierbar (%s)" % run(find_gcc(root) + " -print-sysroot").stdout.strip())

        target = os.path.join(out_dir, name) if out_dir else os.path.abspath(tarball)
        if keep and os.path.exists(target):
            shutil.copy2(target, target + ".bak")
        tmp_tar = os.path.join(tmp, "out.tar")
        if run("tar -cf '%s' -C '%s' '%s'" % (tmp_tar, tmp, os.path.basename(root))).returncode != 0:
            print("    FEHLER beim Packen")
            return False
        if run("xz -e -9 -T0 -f '%s'" % tmp_tar).returncode != 0:
            print("    FEHLER beim Komprimieren")
            return False
        shutil.move(tmp_tar + ".xz", target)
        print("    geschrieben: %s (%.1f MB)" % (target, os.path.getsize(target) / 1e6))
        return True
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv):
    out_dir = None
    keep = False
    check_only = False
    args = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--out":
            i += 1
            out_dir = argv[i]
        elif a == "--keep":
            keep = True
        elif a == "--check":
            check_only = True
        elif a in ("-h", "--help"):
            print(__doc__ or "siehe Kopf der Datei")
            return 0
        else:
            args.append(a)
        i += 1

    if not args:
        print("Aufruf: repack_relocatable.py [--out DIR] [--keep] [--check] <tarball> ...")
        return 1
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    ok = failed = 0
    for t in args:
        if process(t, out_dir, keep, check_only):
            ok += 1
        else:
            failed += 1
    print("\n%d ok, %d fehlgeschlagen" % (ok, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
