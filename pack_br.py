#!/usr/bin/python

import os
import re
import sys
import glob
import subprocess

from pprint import pprint

"""
        gcc version erkennen und anhängen
"""


with open( ".config", 'r') as config_file:
        config_lines = config_file.readlines()

values = {}
for l in config_lines:
        
        if l.startswith("# Buildroot"):
                regex_pattern = r'\s*([\d.]+)'
                match = re.search(regex_pattern, l)
                br_version = match.group(1)
                continue
        
        
        if l.startswith("#"): continue
       
        
        tmp = l.split("=")
        
        if tmp[0] == '\n': continue
        tmp[1] = tmp[1].replace("\n","").replace("\"","")
        
        values[tmp[0]] = tmp[1]

#pprint( values )

#os.system("make prepare-sdk")

print( "Buildroot : " + br_version )

#exit ( 1 )



host_path = "output/host/"
search_path = host_path+ "usr/bin/*-buildroot-*-gcc.br_real"
#print( search_path )

prefix_tmp = glob.glob( search_path  )
if len ( prefix_tmp ) > 1:
        print("Error detecting prefix")
        exit(1)

#print( host_path )
#print( prefix_tmp[0] )        

prefix = prefix_tmp[0].replace(host_path + "usr/bin/","")
prefix = prefix[:-11]
version=subprocess.getstatusoutput(prefix_tmp[0] + " --version")
version=version[1].split("\n")[0]
#print(version)
regex_pattern = r'\)\s*([\d.]+)$'
match = re.search(regex_pattern, version)


print("Prefix    : " + prefix )
if match:
    version = match.group(1)
    print("Version   : " + version)
else:
    print("gcc version nicht erkannt")
    print("   search string : " + version )
    exit(1)


mmu = ""
if values["BR2_NORMALIZED_ARCH"] == "xtensa":
    if "BR2_XTENSA_OVERLAY_FILE" in values:
        arch_variant = values["BR2_XTENSA_OVERLAY_FILE"].split("overlays/")[1].replace(".tar.gz","")
        overlay_file = values["BR2_XTENSA_OVERLAY_FILE"]
        
    if not "BR2_XTENSA_USE_MMU" in values:
        mmu = "_nommu"

toolchain_name = "toolchain-br-" + arch_variant + "-gcc-" + version + "_"+values["BR2_ENDIAN"] + mmu


if "BR2_STATIC_LIBS" in values and values["BR2_STATIC_LIBS"] == "y":
    toolchain_name += "_static"

print( "Archive   : \033[01;32m" + toolchain_name + "\033[00m")

if os.path.exists( toolchain_name+ ".tar.xz"):
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

os.system("rm -rf " + toolchain_name + "*" )
os.system("mkdir -p " + toolchain_name + "" )
#os.system("mkdir -p " + toolchain_name + "/usr/bin" )
#os.system("mkdir -p " + toolchain_name + "/lib" )


os.system("cp -ar " + host_path + "* " + toolchain_name+ "/" )  


sysroot=host_path+ prefix[:-1] + "/sysroot"
print("Sysroot   : " + sysroot)
os.system("cp -ar " + sysroot + " " + toolchain_name )


#os.system("cp " + host_path + "usr/bin/" + prefix+ "* " + toolchain_name+ "/usr/bin" )
#br_wrapped = glob.glob( toolchain_name+ "/usr/bin/*br_real"  )
#for bw in br_wrapped:
#        os.system( "mv " + bw + " " + bw[:-8] )
#os.system("cp -r " + host_path + "libexec/ " + toolchain_name+ "/" )        
#os.system("cp -r " + host_path + "lib/* " + toolchain_name+ "/lib/" )        
#os.system("cp -r " + host_path + "usr/lib " + toolchain_name+ "/usr/" )        
#os.system("cp -r " + host_path + "share " + toolchain_name+ "/" )        
#os.system("rm -rf " + toolchain_name+ "/lib/python*" )        
#os.system("cp  " + host_path + "/relocate-sdk.sh  " + toolchain_name )
#os.system("cp -r " + host_path + "/* " + toolchain_name+ "/" ) 

       

os.system("rm -rf " + toolchain_name+ "/bin/python*" )     
os.system("rm -rf " + toolchain_name+ "/bin/qemu*" )        
os.system("rm -rf " + toolchain_name+ "/share/qemu*" )        
os.system("rm -rf " + toolchain_name+ "/lib/python*" )        
os.system("rm -rf " + toolchain_name+ "/lib/libpython*" )        
os.system("rm -rf " + toolchain_name+ "/usr/include/python*" )  
os.system("rm -rf " + toolchain_name+ "/lib/pkgconfig/python*")


os.system("cp .config " + toolchain_name + "/config" )
os.system("cp /etc/os-release " + toolchain_name )

with open( toolchain_name + "/buildroot_version","w") as f:
        f.write( br_version )


with open( toolchain_name + "/prefix","w") as f:
        f.write( prefix )

os.system("tar -cf " + toolchain_name +".tar " + toolchain_name )
os.system("xz -e -9 -v "+ toolchain_name +".tar")
#os.system("xz -1 -v "+ toolchain_name +".tar")

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
    
os.system("cp " + toolchain_name +".tar.xz toolchains")
os.system('cd toolchains; git add pack.py pack_br.py ; git add ' + toolchain_name + '.tar.xz; git commit -m "toolchain ' + toolchain_name + '" ; git push  ')
