#!/usr/bin/python

import os
import re
import sys
import signal
import subprocess
import glob

from pprint import pprint


def strg_c_handler(signum, frame):
    print("Strg+C wurde gedrückt. Beende das Programm.")
    sys.exit(1)

signal.signal(signal.SIGINT, strg_c_handler)


def read_config( path ):
        values = {}
        with open( path, 'r' ) as config_file:
                for l in config_file:
                        if l.startswith("#") or "=" not in l: continue
                        k, v = l.split("=", 1)
                        values[k] = v.strip().replace("\"", "")
        return values


# Archive name, field by field and always in this order:
#
#   toolchain-<arch>[-<cpu>]-gcc-<version>-<threads>-<link>
#            [-nommu-<format>][-<abi>][-<float>][-<instruction set>][-fpud][-sfp]
#
# threads is npt, lt or no (as in the CI target names); it also says whether
# gcc has real TLS -- openadk builds it with --enable-tls for NPTL only
# (toolchain/gcc/Makefile) -- and check_tls() below checks gcc -v for it.
# link is static for ADK_TARGET_USE_STATIC_LIBS_ONLY, shared otherwise.
def toolchain_name( values, version ):
        arch = values["ADK_TARGET_CPU_ARCH"]

        cpu = None
        if values.get("ADK_TARGET_CPU_H8300H") == "y":
                cpu = "h8300h"
        elif values.get("ADK_TARGET_CPU_TYPE"):
                cpu = values["ADK_TARGET_CPU_TYPE"]
                # microblaze/microblazeel, mips64/mips64el: nothing to add
                if arch.startswith( cpu ):
                        cpu = None
        # riscv has no CPU_TYPE, its ISA is ADK_TARGET_GCC_ARCH; on bfin,
        # csky, sh and h8300 that field holds a compiler flag instead.
        elif re.match(r"^[A-Za-z0-9_]+$", values.get("ADK_TARGET_GCC_ARCH", "")):
                cpu = values["ADK_TARGET_GCC_ARCH"]
                if arch.startswith( cpu ):      # i686: arch and ISA are one
                        cpu = None

        if values.get("ADK_TARGET_WITH_NPTL") == "y":
                threads = "npt"
        elif values.get("ADK_TARGET_WITH_LT") == "y":
                threads = "lt"
        else:
                threads = "no"

        link = "static" if values.get("ADK_TARGET_USE_STATIC_LIBS_ONLY") == "y" else "shared"

        nommu = values.get("ADK_TARGET_WITH_MMU") == "n" or \
                ( "ADK_TARGET_WITH_MMU" not in values and values.get("BUSYBOX_NOMMU") == "y" )

        name = "toolchain-" + arch
        if cpu:
                name += "-" + cpu
        name += "-gcc-" + version + "-" + threads + "-" + link
        if nommu:
                fmt = values.get("ADK_TARGET_BINFMT")
                if not fmt:     # older openadk: only ADK_TARGET_BINFMT_<FMT>=y
                        fmt = "elf"
                        for f in ( "flat", "fdpic", "elf" ):     # not FLAT_ONE, a FLAT option
                                if values.get("ADK_TARGET_BINFMT_" + f.upper()) == "y":
                                        fmt = f
                                        break
                name += "-nommu-" + fmt
        for key in ( "ADK_TARGET_ABI", "ADK_TARGET_FLOAT", "ADK_TARGET_INSTRUCTION_SET" ):
                if values.get( key ):
                        name += "-" + values[key]
        # ARC HS with the double precision FPU; the single precision one is
        # the default and keeps the name it always had.
        if values.get("ADK_TARGET_ARCH_ARC_WITH_FPU_DP") == "y":
                name += "-fpud"
        # libgcc lets the C library keep the soft-float environment; the
        # toolchain without it stays available under the old name.
        if values.get("ADK_TOOLCHAIN_GCC_SOFTFP_FENV") == "y":
                name += "-sfp"
        return name, threads


# The thread field says how openadk configured gcc: --enable-tls for NPTL
# only.  Check that against "gcc -v".  What gcc then emits is reported, not
# enforced: nios2 emits real TLS whatever --disable-tls says
# (gcc/config/nios2/nios2.cc: TARGET_HAVE_TLS is TARGET_LINUX_ABI).
def check_tls( gcc, threads ):
        conf = subprocess.run( [ gcc, "-v" ], capture_output=True, text=True ).stderr
        if "--enable-tls" in conf:
                configured = True
        elif "--disable-tls" in conf:
                configured = False
        else:
                configured = None
        if configured is not None and configured != ( threads == "npt" ):
                print( " !! ERROR: Name sagt threads=" + threads + ", gcc ist mit "
                       + ( "--enable-tls" if configured else "--disable-tls" ) + " gebaut" )
                sys.exit( 1 )

        r = subprocess.run( [ gcc, "-O2", "-S", "-xc", "-", "-o", "-" ],
                            input="extern __thread int x; int f(void){return x;}\n",
                            capture_output=True, text=True )
        if r.returncode != 0:
                print( r.stderr )
                print( " !! ERROR: gcc kann keine __thread-Variable uebersetzen" )
                sys.exit( 1 )
        emulated = "__emutls" in r.stdout
        print( "TLS       : " + ( "emuliert" if emulated else "echt" ) + " im erzeugten Code" )
        if emulated == ( threads == "npt" ):
                print( " !! HINWEIS: das Backend haelt sich nicht an --"
                       + ( "enable" if configured else "disable" ) + "-tls" )


# pack.py --name <openadk config> <gcc version>: only print the name,
# for renaming archives that already exist.
if len( sys.argv ) == 4 and sys.argv[1] == "--name":
        print( toolchain_name( read_config( sys.argv[2] ), sys.argv[3] )[0] )
        sys.exit( 0 )

if len( sys.argv ) == 1:
        with open(".config", 'r') as config_file:
                config_lines = config_file.readlines()
else:
        with open(sys.argv[1], 'r') as config_file:
                config_lines = config_file.readlines()

values = {}
for l in config_lines:
        if l.startswith("#"): continue
        if l.startswith("ADK_LINUX_KERNEL_"): continue
        if l.startswith("ADK_COMPILE_"): continue
        if l.startswith("ADK_RUNTIME_"): continue
        if l.startswith("ADK_PACKAGE_"): continue
        if l.startswith("ADK_HOST_"): continue
        
        if l.startswith("BUSYBOX_NOMMU"): 
                tmp = l.split("=")
        
                if tmp[0] == '\n': continue
                tmp[1] = tmp[1].replace("\n","").replace("\"","")
                
                values[tmp[0]] = tmp[1]
                continue
        
        if l.startswith("BUSYBOX_"): continue
        
        tmp = l.split("=")
        
        if tmp[0] == '\n': continue
        tmp[1] = tmp[1].replace("\n","").replace("\"","")
        
        values[tmp[0]] = tmp[1]

pprint( values )

arch=values["ADK_TARGET_CPU_ARCH"]

"""
gcc=None
if "ADK_TOOLCHAIN_GCC_7" in values: gcc="7"
if "ADK_TOOLCHAIN_GCC_8" in values: gcc="8"
if "ADK_TOOLCHAIN_GCC_9" in values: gcc="9"
if "ADK_TOOLCHAIN_GCC_10" in values: gcc="10"
if "ADK_TOOLCHAIN_GCC_11" in values: gcc="11"
if "ADK_TOOLCHAIN_GCC_12" in values: gcc="12"
if "ADK_TOOLCHAIN_GCC_13" in values: gcc="13"
if "ADK_TOOLCHAIN_GCC_14" in values: gcc="14"
if "ADK_TOOLCHAIN_GCC_15" in values: gcc="15"
if "ADK_TOOLCHAIN_GCC_16" in values: gcc="16"
if "ADK_TOOLCHAIN_GCC_KVX" in values: gcc="kvx"

if gcc == None:
        print( "No GCC detect" )
        sys.exit(1)
"""


target=values["ADK_TARGET_SYSTEM"]
lib=values["ADK_TARGET_LIBC"]


build_path="toolchain_" + target + "_" + lib
sysroot_path="target_" + target + "_" + lib

# openadk's directory names; the archive name comes from toolchain_name().
if 'ADK_TARGET_CPU_TYPE' in values:
        tmp=values["ADK_TARGET_CPU_TYPE"]
        # microblaze: CPU_TYPE is always "microblaze", the endianness suffix
        # follows below with ENDIAN_SUFFIX.
        build_path += "_" + tmp
        sysroot_path +=  "_" + tmp

if 'ADK_TARGET_ENDIAN_SUFFIX' in values:
         build_path += "" + values["ADK_TARGET_ENDIAN_SUFFIX"]
         sysroot_path += "" + values["ADK_TARGET_ENDIAN_SUFFIX"]


if 'ADK_TARGET_FLOAT' in values:
        build_path += "_" + values["ADK_TARGET_FLOAT"]
        sysroot_path += "_" + values["ADK_TARGET_FLOAT"]

if 'ADK_TARGET_ABI' in values:
        build_path += "_" + values["ADK_TARGET_ABI"]
        sysroot_path += "_"+ values["ADK_TARGET_ABI"]

if 'ADK_TARGET_INSTRUCTION_SET' in values:
        build_path += "_" + values["ADK_TARGET_INSTRUCTION_SET"]
        sysroot_path += "_" + values["ADK_TARGET_INSTRUCTION_SET"]

if 'ADK_TARGET_BINFMT' in values:
        build_path += "_" + values["ADK_TARGET_BINFMT"]
        sysroot_path += "_" + values["ADK_TARGET_BINFMT"]

# nommu must be last to match openadk's mk/vars.mk (ADK_SUFFIX += _nommu, line 35)
if 'ADK_TARGET_WITH_MMU' in values:
        if values["ADK_TARGET_WITH_MMU"] == "n":
                build_path += "_nommu"
                sysroot_path += "_nommu"
else:
        if 'BUSYBOX_NOMMU' in values:
                if values["BUSYBOX_NOMMU"] == "y":
                        build_path += "_nommu"
                        sysroot_path += "_nommu"

print( "Buildpath : "+ build_path )
#print( "sysroot_path : "+ sysroot_path )
#print( "tc2 :" + tc2 )

"""
        gcc version erkennen und anhängen
"""
prefix_tmp = glob.glob( build_path + "/usr/bin/*-gcc" )
if len ( prefix_tmp ) > 1:
        print("Error detecting prefix")
        exit(1)
        
print( prefix_tmp )

prefix = prefix_tmp[0].replace(build_path + "/usr/bin/","")
prefix = prefix[:-3]
version=subprocess.getstatusoutput(prefix_tmp[0] + " --version")
version_line=version[1].split("\n")[0]
regex_pattern = r'\b\d+\.\d+\.\d+\b'
matches = re.findall(regex_pattern, version_line)
version=matches[0]
# Ein gcc aus dem Trunk oder kurz vor dem Release meldet sich als
# "17.0.0 20261019 (experimental)" bzw. "(prerelease)". Alte Staende brauchen
# wir nicht, also "gcc-17-pre" statt eines Datums; ein neuer Stand ersetzt den
# alten unter demselben Namen.
if "(experimental)" in version_line or "(prerelease)" in version_line:
        version = version.split(".")[0] + "-pre"
tc2, threads = toolchain_name( values, version )
check_tls( prefix_tmp[0], threads )

static_conf_ok=False
if 'ADK_TARGET_USE_SHARED_LIBS_ONLY' in values:
        if values["ADK_TARGET_USE_SHARED_LIBS_ONLY"] == "y":
                static_conf_ok=True
                

if 'ADK_TARGET_USE_STATIC_LIBS_ONLY' in values:
        if values["ADK_TARGET_USE_STATIC_LIBS_ONLY"] == "y":
                static_conf_ok=True
                
                
# Beide Varianten im Sysroot: kein Namenszusatz, die Toolchain kann shared
# und statisch linken.
if 'ADK_TARGET_USE_SHARED_AND_STATIC_LIBS' in values:
        if values["ADK_TARGET_USE_SHARED_AND_STATIC_LIBS"] == "y":
                static_conf_ok=True


if static_conf_ok == False:
        print("ADK_TARGET_USE_SHARED_LIBS_ONLY, ADK_TARGET_USE_STATIC_LIBS_ONLY")
        print("oder ADK_TARGET_USE_SHARED_AND_STATIC_LIBS setzen")
        exit(1)



print( "" )
print( "GCC       : " + version  )
print( "ARCH      : " + arch )
print( "" )

if not os.path.exists( build_path + "/usr/bin" ):
        print( "" )
        print(  "build_path unvollständig : suche \n      \033[01;32m" +build_path +"/usr/bin\033[00m")
        
        os.system("ls | grep " + arch)
        print( "" )
        sys.exit( 1 )

if not os.path.exists( sysroot_path + "/usr/lib/crt1.o" ):
        print( "" )
        print( "Sysroot unvollständig   : suche \n\033[01;32m"+ sysroot_path +"\033[00m" )
        os.system("ls | grep " + arch)
        print( "" )
        sys.exit( 1)

#print( sysroot_path )
if os.path.exists( sysroot_path + "/usr/lib/!m4"):
        print(" !! ERROR !m4 im sysroot gefunden. fixing")
        os.system("mv " + sysroot_path + "/usr/lib/!m4/* " + sysroot_path + "/usr/lib" )
        os.system("rm -rf " + sysroot_path + "/usr/lib/!m4/")
        

#sys.exit(1)



        
        


print( "Buildpath : "+ build_path )
print( "Sysroot   : "+ sysroot_path )
print( "Prefix    : " + prefix )
print( "Version   : " + version)
print( "Archive   : \033[01;32m" +tc2 + "\033[00m" )



if os.path.exists( tc2+ ".tar.xz"):
        print( "" )
        
        response = input("Archive exists. Do you want to proceed? (y/n): ")

        if response.lower() == 'y':
            print("You entered 'y'. Proceeding.")
        elif response.lower() == 'n':
            print("You entered 'n'. Aborting.")
            sys.exit(1)
        else:
            print("Invalid input. Please enter 'y' or 'n'.")
            sys.exit(1)
    

tc = build_path

with open( tc+ "/openadk_hash", "w") as datei:
    subprocess.call("git rev-parse HEAD", shell=True, stdout=datei)

with open( tc + "/prefix", "w") as f:
        f.write( prefix )
        
os.system("cp .config " + tc + "/config" )

os.system("cp .config " + tc + "/config" )
os.system("cp /etc/os-release " + tc )

# gcc aus git: openadk klont ohne .git, der Stand stuende sonst nirgends.
# Commit (dl/gcc-git.COMMIT, beim Anlegen der Quelle geschrieben) und die
# angewendeten Patches gehen mit ins Archiv.
meta_files = [ "config", "os-release", "prefix", "openadk_hash" ]
if values.get("ADK_TOOLCHAIN_GCC_GIT") == "y":
        if os.path.exists("dl/gcc-git.COMMIT"):
                os.system("cp dl/gcc-git.COMMIT " + tc + "/gcc_commit")
                meta_files.append("gcc_commit")
        else:
                print(" !! WARNUNG: dl/gcc-git.COMMIT fehlt, gcc-Stand unbekannt")
        if os.path.isdir("toolchain/gcc/patches/git"):
                os.system("rm -rf " + tc + "/gcc_patches; cp -r toolchain/gcc/patches/git " + tc + "/gcc_patches")
                meta_files.append("gcc_patches")

# Archivlayout: Toolchain und Sysroot liegen nebeneinander, genau wie im
# openadk-Baum. gcc ist mit --with-sysroot='${prefix}/../../target_<suffix>'
# konfiguriert (toolchain/gcc/Makefile) und rechnet den Pfad zur Laufzeit
# relativ zum Aufrufort neu, uebernimmt das Ergebnis aber nur, wenn access()
# darauf gelingt (gcc/gcc.cc, TARGET_SYSTEM_ROOT_RELOCATABLE). Solange das
# Sysroot flach unter <archiv>/sysroot lag, war das Archiv eine Ebene flacher
# als der Build-Baum, der relative Pfad zeigte aus dem Archiv heraus und gcc
# benutzte weiter den einkompilierten Absolutpfad ins Build-Verzeichnis: fuer
# fremde Benutzer nicht lesbar ("cc1: error: ...: Permission denied", z.B. bei
# einem Build unter /root), auf fremden Maschinen gar nicht vorhanden
# ("stdio.h: No such file or directory").
#
# Die Symlinks in der Archivwurzel halten <archiv>/usr, <archiv>/sysroot und die
# Metadateien fuer CI, uc_devel und build_tool.sh unveraendert erreichbar;
# innerhalb von toolchain_<suffix> sieht der Baum aus wie die alte Archivwurzel,
# damit bleiben auch die relativen Links unten und in der CI gueltig.
os.system("rm -rf " + tc2 )
os.system("mkdir -p " + tc2 )
os.system("cp -r " + build_path + " " + tc2 + "/" + build_path )
os.system("cp -r " + sysroot_path + " " + tc2 + "/" + sysroot_path )
os.system("cd " + tc2 + "/" + build_path + " ; ln -s ../" + sysroot_path + " sysroot" )
os.system("cd " + tc2 + " ; ln -s " + build_path + "/usr usr ; ln -s " + sysroot_path + " sysroot" )
for meta_file in meta_files:
        os.system("cd " + tc2 + " ; ln -s " + build_path + "/" + meta_file + " " + meta_file )


# Point the toolchain's usr/<target>/lib symlink at sysroot/usr/lib (NOT
# sysroot/lib): elf2flt.ld and the static-link bits crt*.o/libc.a etc.
# live under sysroot/usr/lib for uClibc-ng FLAT toolchains, while
# sysroot/lib is empty. Without this, ld-elf2flt fails to find its
# linker script. Survey of 11 existing FLAT toolchain tarballs confirms
# elf2flt.ld is always in sysroot/usr/lib, never in sysroot/lib.
os.system("cd "+ tc2 + "/usr/" + prefix[:-1] + " ; rm lib; ln -s ../../sysroot/usr/lib lib"  )
os.system("cd "+ tc2 + "/usr/" + prefix[:-1] + " ; rm sys-include; ln -s ../../sysroot/usr/include sys-include"  )
#
# update 1) scheinbar doch nicht. der link muss auf sysroot/lib zeigen. dafür dann aber die ldscripts nach /lib kopieren
#os.system("cp -a "+ tc2 + "/sysroot/lib/* " + tc2 + "/sysroot/usr/lib/"  )
os.system("cp -r "+ tc2 + "/sysroot/usr/lib/ldscripts " + tc2 + "/sysroot/lib/"  )

os.system("cp -r "+ tc2 + "/sysroot/usr/lib/ck807/* " + tc2 + "/sysroot/usr/lib/"  )


#os.system("ls "+ tc2 + "/usr/" + prefix[:-1] + "/lib/ -all "  )

#exit(1)

os.system("rm -f " + tc2 + ".tar.xz")
os.system("tar -cf " + tc2 + ".tar " +tc2 )
os.system("xz -e -9 -v " + tc2 +".tar")

#os.system("find " + tc2 + "/usr/bin")

print(  "Archive   : \033[01;32m" + tc2 + "\033[00m" )



if not os.path.exists( "toolchains" ):
	os.system("git clone git@github.com:lordrasmus/toolchains.git")


if not os.path.exists( "toolchains" ):
	print("toolchain git error" )
	sys.exit( 1 )
        
os.system("cp " + tc2 +".tar.xz toolchains")



print("")
response = input( "\033[01;32mstarting git commit. Do you want to proceed? (y/n):\033[00m ")

# Check if the input is "y" or "n"
if response.lower() == 'y':
    print( "You entered 'y'. Proceeding." )
elif response.lower() == 'n':
    print( "You entered 'n'. Aborting." )
    sys.exit( 1 )
else:
    print(" Invalid input. Please enter 'y' or 'n'.")
    sys.exit( 1 )

os.system('cd toolchains; git add pack.py ; git add ' + tc2 + '.tar.xz; git commit -m "toolchain ' + tc2 + '" ; git push  ')

