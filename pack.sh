#!/bin/bash


arch=$(grep ADK_TARGET_CPU_ARCH= .config)
arch="${arch/ADK_TARGET_CPU_ARCH=}"
arch="${arch/\"}"
arch="${arch/\"}"

gcc="none"
if [[ $(grep ADK_TOOLCHAIN_GCC_7 .config) == "ADK_TOOLCHAIN_GCC_7=y" ]]; then   gcc="7"  ; fi
if [[ $(grep ADK_TOOLCHAIN_GCC_8 .config) == "ADK_TOOLCHAIN_GCC_8=y" ]]; then   gcc="8"  ; fi
if [[ $(grep ADK_TOOLCHAIN_GCC_9 .config) == "ADK_TOOLCHAIN_GCC_9=y" ]]; then   gcc="9"  ; fi
if [[ $(grep ADK_TOOLCHAIN_GCC_10 .config) == "ADK_TOOLCHAIN_GCC_10=y" ]]; then   gcc="10"  ; fi
if [[ $(grep ADK_TOOLCHAIN_GCC_11 .config) == "ADK_TOOLCHAIN_GCC_11=y" ]]; then   gcc="11"  ; fi
if [[ $(grep ADK_TOOLCHAIN_GCC_12 .config) == "ADK_TOOLCHAIN_GCC_12=y" ]]; then   gcc="12"  ; fi
if [[ $(grep ADK_TOOLCHAIN_GCC_13 .config) == "ADK_TOOLCHAIN_GCC_13=y" ]]; then   gcc="13"  ; fi

if [[ $gcc == "none" ]] ; then echo "No GCC detect"; exit 1 ; fi

echo ""
echo "GCC : $gcc"
echo "ARCH: $arch"
echo ""



target=$(grep ADK_TARGET_SYSTEM= .config)
target="${target/ADK_TARGET_SYSTEM=}"
target="${target/\"}"
target="${target/\"}"

lib=$(grep ADK_TARGET_LIBC= .config)
lib="${lib/ADK_TARGET_LIBC=}"
lib="${lib/\"}"
lib="${lib/\"}"



tc2="toolchain-"$arch"-gcc-"$gcc

build_path="toolchain_"$target"_"$lib
sysroot_path="target_"$target"_"$lib

if grep -q 'ADK_TARGET_CPU_TYPE' .config; then
        tmp=$(grep ADK_TARGET_CPU_TYPE= .config)
        tmp="${tmp/ADK_TARGET_CPU_TYPE=}"
        tmp="${tmp/\"}"
        tmp="${tmp/\"}"

        build_path=$build_path"_"$tmp
        sysroot_path=$sysroot_path"_"$tmp
        tc2="toolchain-"$arch"_"$tmp"-gcc-"$gcc
fi

if grep -q 'ADK_TARGET_FLOAT' .config; then
        tmp=$(grep ADK_TARGET_FLOAT= .config)
        tmp="${tmp/ADK_TARGET_FLOAT=}"
        tmp="${tmp/\"}"
        tmp="${tmp/\"}"

        build_path=$build_path"_"$tmp
        sysroot_path=$sysroot_path"_"$tmp
        tc2=$tc2"_"$tmp
fi

if grep -q 'ADK_TARGET_ABI' .config; then
        tmp=$(grep ADK_TARGET_ABI= .config)
        tmp="${tmp/ADK_TARGET_ABI=}"
        tmp="${tmp/\"}"
        tmp="${tmp/\"}"

        build_path=$build_path"_"$tmp
        sysroot_path=$sysroot_path"_"$tmp
        tc2=$tc2"_"$tmp
fi

if grep -q 'ADK_TARGET_INSTRUCTION_SET' .config; then
        tmp=$(grep ADK_TARGET_INSTRUCTION_SET= .config)
        tmp="${tmp/ADK_TARGET_INSTRUCTION_SET=}"
        tmp="${tmp/\"}"
        tmp="${tmp/\"}"
        
        if [[ $tmp != "" ]] ; then
                build_path=$build_path"_"$tmp
                sysroot_path=$sysroot_path"_"$tmp
                tc2=$tc2"_"$tmp
        fi
fi

if grep -q 'ADK_TARGET_BINFMT' .config; then
        tmp=$(grep ADK_TARGET_BINFMT= .config)
        tmp="${tmp/ADK_TARGET_BINFMT=}"
        tmp="${tmp/\"}"
        tmp="${tmp/\"}"

        if [[ $tmp != "" ]] ; then
                build_path=$build_path"_"$tmp
                sysroot_path=$sysroot_path"_"$tmp
                tc2=$tc2"_"$tmp
        fi
fi

if grep -q 'BUSYBOX_NOMMU=y' .config; then
        tmp=$(grep BUSYBOX_NOMMU=y .config)
        tmp="${tmp/BUSYBOX_NOMMU=y}"
        tmp="${tmp/\"}"
        tmp="${tmp/\"}"
        
        build_path=$build_path"_nommu"
        sysroot_path=$sysroot_path"_nommu"
        tc2=$tc2"_nommu"
fi


if [ ! -e $build_path/usr/bin ] ; then
        echo "Toolchain unvollständig : suche $build_path/usr/bin"
        exit 1
fi

if [ ! -e $sysroot_path/usr/lib/crt1.o ] ; then
        echo "Sysroot unvollständig   : suche $sysroot_path"
        exit 1
fi


echo "Toolchain : $build_path"
echo "Sysroot   : $sysroot_path"
echo -e "Archive   : \033[01;32m$tc2\033[00m"



tc=$build_path


if [ -e $tc2.tar.xz ] ; then

        echo ""
        echo "Archive exists. Do you want to proceed? (y/n): "
        read response

        # Check if the input is "y" or "n"
        if [ "$response" = "y" ]; then
            echo "You entered 'y'. Proceeding."
        elif [ "$response" = "n" ]; then
            echo "You entered 'n'. Aborting."
            exit 1
        else
            echo "Invalid input. Please enter 'y' or 'n'."
            exit 1
        fi
fi


git rev-parse HEAD > $tc/openadk_hash
cp .config $tc/config
cp /etc/os-release $tc


mkdir -p $tc/sysroot
cp -r $sysroot_path/* $tc/sysroot



rm -rf $tc2
cp -r $tc $tc2

rm -f $tc2.tar.xz
tar -cvf $tc2.tar $tc2
xz -e -9 -v $tc2.tar

find $tc2/usr/bin

echo -e "Archive   : \033[01;32m$tc2\033[00m"


if [ ! -e toolchains ] ; then
	git clone git@github.com:lordrasmus/toolchains.git
fi

if [ ! -e toolchains ] ; then
	echo "toolchain git error"
	exit 1
fi
cp $tc2.tar.xz toolchains



echo ""
echo -e "\033[01;32mstaring git commit. Do you want to proceed? (y/n):\033[00m "
echo ""
read response

# Check if the input is "y" or "n"
if [ "$response" = "y" ]; then
    echo "You entered 'y'. Proceeding."
elif [ "$response" = "n" ]; then
    echo "You entered 'n'. Aborting."
    exit 1
else
    echo "Invalid input. Please enter 'y' or 'n'."
    exit 1
fi
( cd toolchains; git add pack.sh ; git add $tc2.tar.xz; git commit -m "toolchain $tc2" ; git push  )
