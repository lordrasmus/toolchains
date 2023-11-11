#!/usr/bin/python

import os
import sys
import signal
import subprocess

from pprint import pprint


def strg_c_handler(signum, frame):
    print("Strg+C wurde gedrückt. Beende das Programm.")
    sys.exit(1)

signal.signal(signal.SIGINT, strg_c_handler)

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
                values["BUSYBOX_NOMMU"] = True
                continue
        
        if l.startswith("BUSYBOX_"): continue
        
        tmp = l.split("=")
        
        if tmp[0] == '\n': continue
        tmp[1] = tmp[1].replace("\n","").replace("\"","")
        
        values[tmp[0]] = tmp[1]

pprint( values )

arch=values["ADK_TARGET_CPU_ARCH"]


gcc=None
if "ADK_TOOLCHAIN_GCC_7" in values: gcc="7"
if "ADK_TOOLCHAIN_GCC_8" in values: gcc="8"
if "ADK_TOOLCHAIN_GCC_9" in values: gcc="9"
if "ADK_TOOLCHAIN_GCC_10" in values: gcc="10"
if "ADK_TOOLCHAIN_GCC_11" in values: gcc="11"
if "ADK_TOOLCHAIN_GCC_12" in values: gcc="12"
if "ADK_TOOLCHAIN_GCC_13" in values: gcc="13"
if "ADK_TOOLCHAIN_GCC_KVX" in values: gcc="kvx"

if gcc == None:
        print( "No GCC detect" )
        sys.exit(1)



target=values["ADK_TARGET_SYSTEM"]
lib=values["ADK_TARGET_LIBC"]


tc2="toolchain-" + arch + "-gcc-" + gcc
build_path="toolchain_" + target + "_" + lib
sysroot_path="target_" + target + "_" + lib



if 'ADK_TARGET_CPU_TYPE' in values:
        tmp=values["ADK_TARGET_CPU_TYPE"]
        
        if arch == "microblazeel":
                build_path += "_microblazeel"
                sysroot_path +=  "_microblazeel"
                tc2="toolchain-" + arch + "_gcc-" + gcc
        else:
                build_path += "_" + tmp
                sysroot_path +=  "_" + tmp
                tc2="toolchain-" + arch + "_" + tmp + "-gcc-" + gcc
                
        if arch == "mipsel" and tmp == "mips32":
                tc2="toolchain-mips32el-gcc-" + gcc

if 'ADK_TARGET_ENDIAN_SUFFIX' in values:
         build_path += "" + values["ADK_TARGET_ENDIAN_SUFFIX"]
         sysroot_path += "" + values["ADK_TARGET_ENDIAN_SUFFIX"]

#print( "Buildpath : "+ build_path )
#print( "sysroot_path : "+ sysroot_path )
print( "tc2 :" + tc2 )

if 'ADK_TARGET_FLOAT' in values:
        build_path += "_" + values["ADK_TARGET_FLOAT"]
        sysroot_path += "_" + values["ADK_TARGET_FLOAT"]
        tc2 += "_" + values["ADK_TARGET_FLOAT"]


if 'ADK_TARGET_ABI' in values:
        build_path += "_" + values["ADK_TARGET_ABI"]
        sysroot_path += "_"+ values["ADK_TARGET_ABI"]
        tc2 += "_"+ values["ADK_TARGET_ABI"]



if 'ADK_TARGET_INSTRUCTION_SET' in values:
        
        #if [[ $tmp != "" ]] ; then
                build_path += "_" + values["ADK_TARGET_INSTRUCTION_SET"] 
                sysroot_path += "_" + values["ADK_TARGET_INSTRUCTION_SET"] 
                tc2 += "_" + values["ADK_TARGET_INSTRUCTION_SET"] 

if 'ADK_TARGET_BINFMT' in values:
        
        #if [[ $tmp != "" ]] ; then
                build_path += "_" + values["ADK_TARGET_BINFMT"] 
                sysroot_path += "_" + values["ADK_TARGET_BINFMT"] 
                tc2 += "_" + values["ADK_TARGET_BINFMT"] 
        

if 'BUSYBOX_NOMMU' in values:
        #if [[ $tmp != "" ]] ; then
                build_path += "_nommu"
                sysroot_path += "_nommu"
                tc2 += "_nommu"



print( "" )
print( "GCC       : " + gcc  )
print( "ARCH      : " + arch )
print( "" )

if not os.path.exists( build_path + "/usr/bin" ):
        print( "" )
        print(  "build_path unvollständig : suche \n\033[01;32m" +build_path +"/usr/bin\033[00m")
        
        os.system("ls | grep " + arch)
        print( "" )
        sys.exit( 1 )

if not os.path.exists( sysroot_path + "/usr/lib/crt1.o" ):
        print( "" )
        print( "Sysroot unvollständig   : suche \n\033[01;32m"+ sysroot_path +"\033[00m" )
        os.system("ls | grep " + arch)
        print( "" )
        sys.exit( 1)

print( sysroot_path )
if os.path.exists( sysroot_path + "/usr/lib/!m4"):
        print(" !! ERROR !m4 im sysroot gefunden. fixing")
        os.system("mv " + sysroot_path + "/usr/lib/!m4/* " + sysroot_path + "/usr/lib" )
        os.system("rm -rf " + sysroot_path + "/usr/lib/!m4/")
        

#sys.exit(1)



print( "Buildpath : "+ build_path )
print( "Sysroot   : "+ sysroot_path )
print( "Archive   : \033[01;32m" +tc2 + "\033[00m" )


build_path


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

os.system("cp .config " + tc + "/config" )
os.system("cp /etc/os-release " + tc )

os.system("mkdir -p " +tc+"/sysroot")
os.system("cp -r " + sysroot_path +"/* "+ tc +"/sysroot")


os.system("rm -rf " + tc2 )
os.system("cp -r " + tc + " " + tc2 )

os.system("rm -f " + tc2 + ".tar.xz")
os.system("tar -cf " + tc2 + ".tar " +tc2 )
os.system("xz -e -9 -v " + tc2 +".tar")

os.system("find " + tc2 + "/usr/bin")

print(  "Archive   : \033[01;32m" + tc2 + "\033[00m" )



if not os.path.exists( "toolchains" ):
	os.system("git clone git@github.com:lordrasmus/toolchains.git")


if not os.path.exists( "toolchains" ):
	print("toolchain git error" )
	os.exit( 1 )
        
os.system("cp " + tc2 +".tar.xz toolchains")



print("")
response = input( "\033[01;32mstaring git commit. Do you want to proceed? (y/n):\033[00m ")

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

